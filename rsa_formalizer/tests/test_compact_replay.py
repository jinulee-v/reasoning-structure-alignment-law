"""Compact replay preserves dependencies and bounds case loading."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from rsa_formalizer.bobcat.compact_trace import annotated_scopes, ocaml_projection
from rsa_formalizer.bobcat.records import ReplayRecords
from rsa_formalizer.bobcat.trace import persist_execution_forests
from rsa_formalizer.stages import utils as exp


class CompactReplayTest(unittest.TestCase):
    def test_unannotated_blocks_do_not_inherit_previous_annotation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'law.catala_en').write_text('''<!-- rsa-block-id: rule:1; provision-id: rule/P1; -->
```catala
scope Rule:
 definition result equals true
```
```catala
scope Helper:
 definition secret equals true
```
''')
            self.assertEqual(annotated_scopes(root), ['Rule'])

    def test_disk_records_and_forest_index_do_not_load_all_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for i in range(3):exp.atomic_json(root/f'case-{i}.json', {'id':f'case-{i}', 'execution_tree':[]})
            records = ReplayRecords(sorted(root.glob('case-*.json')))
            with mock.patch('rsa_formalizer.bobcat.records.exp.load_json', wraps=exp.load_json) as load:
                self.assertEqual(len(records), 3)
                persist_execution_forests(root, records)
                load.assert_not_called()
                self.assertEqual(next(iter(records))['id'], 'case-0')
                self.assertEqual(load.call_count, 1)
                self.assertEqual(records.get('case-2')['id'], 'case-2')
                self.assertEqual(load.call_count, 2)
            index = exp.load_json(root/'execution_tree.json')
            self.assertEqual(index['storage'], 'per_case_files')
            self.assertEqual(len(index['case_files']), 3)
            self.assertNotIn('roots', index)

    def test_native_projection_preserves_hidden_dependencies_and_call_context(self):
        environment = exp.toolchain_environment({})
        compiler = shutil.which('ocamlopt', path=environment['PATH'])
        if not compiler:self.skipTest('OCaml unavailable')
        runtime = '''module Catala_runtime = struct
 type read_dependency = {definition_id:int; field:string option}
 type raw_event = BeginCall of string list | EndCall of string list
  | VariableDefinition of string list * bool * int * int * read_dependency list
  | DecisionTaken of int | BranchTaken of int * bool
end
'''
        program = runtime + ocaml_projection(['Entry','Rule']) + '''
open Catala_runtime
let read id field = {definition_id=id; field=field}
let () =
 let input = VariableDefinition (["Entry";"input"], true, 42, 0, []) in
 let result = rsa_project_trace [BeginCall ["Api.catala_en::Entry"];input;
  BeginCall ["Helpers.catala_en::hidden"]; BranchTaken (10,true);
  VariableDefinition (["Helpers.catala_en::hidden";"$return"],false,42,1,[read 0 (Some "value")]);
  VariableDefinition (["Helpers.catala_en::hidden";"$return"],false,42,2,[read 1 None;read 0 (Some "value")]);
  EndCall ["Helpers.catala_en::hidden"]; BeginCall ["Rule"]; BranchTaken (20,false);
  VariableDefinition (["Rule";"result"],false,42,3,[read 2 None]); EndCall ["Rule"];
  EndCall ["Api.catala_en::Entry"]] in
 assert (List.length result = 7);
 assert (List.exists (function BranchTaken (20,false) -> true | _ -> false) result);
 assert (not (List.exists (function BranchTaken (10,_) -> true | _ -> false) result));
 assert (List.exists (function VariableDefinition (_,_,42,3,[{definition_id=0;field=Some "value"}]) -> true | _ -> false) result);
 assert (not (List.exists (function VariableDefinition (_,_,_,(1|2),_) -> true | _ -> false) result));
 (try ignore (rsa_project_trace [VariableDefinition (["Rule";"bad"],false,0,1,[read 999 None])]); assert false
  with Failure _ -> ());
 print_endline "dependencies, fields and invocation boundaries preserved"
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);source=root/'projection.ml';source.write_text(program)
            built=subprocess.run([compiler,'-o',str(root/'projection'),str(source)],env=environment,cwd=root,capture_output=True,text=True,timeout=30)
            self.assertEqual(built.returncode,0,built.stderr)
            result=subprocess.run([str(root/'projection')],env=environment,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('preserved',result.stdout)


if __name__ == '__main__':unittest.main()
