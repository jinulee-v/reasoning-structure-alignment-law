"""Large trace export must preserve order without consuming linear stack space."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from rsa_formalizer.bobcat.compiled_json import generate_source
from rsa_formalizer.stages.utils.catala import toolchain_environment


class TraceExportTest(unittest.TestCase):
    def test_half_million_events_preserve_order(self):
        environment = toolchain_environment({})
        compiler = shutil.which('ocamlopt', path=environment['PATH'])
        if not compiler:
            self.skipTest('OCaml compiler unavailable')
        generated = generate_source('', [])
        match = re.search(r'let events = (.*?) in\n\s*print_endline', generated, re.S)
        self.assertIsNotNone(match)
        program = '''module Catala_runtime = struct
  let retrieve_log () = List.init 500000 (fun i -> i)
  module Json = struct let raw_event = string_of_int end
end
module Json_input = struct let from_string = int_of_string end
let () =
  let events = ''' + match[1] + ''' in
  assert (List.length events = 500000);
  List.iteri (fun i event -> assert (i = event)) events;
  print_endline "500000 ordered events exported"
'''
        with tempfile.TemporaryDirectory(prefix='rsa-trace-export-test-') as directory:
            root = Path(directory)
            source = root / 'export.ml'
            source.write_text(program)
            built = subprocess.run([compiler, '-o', str(root/'export'), str(source)],
                                   cwd=root, env=environment, capture_output=True, text=True, timeout=30)
            self.assertEqual(built.returncode, 0, built.stderr)
            replay = subprocess.run([str(root/'export')], cwd=root, env=environment,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertEqual(replay.stdout.strip(), '500000 ordered events exported')


if __name__ == '__main__':
    unittest.main()
