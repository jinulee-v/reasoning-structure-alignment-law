from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from rsa_formalizer.stages.reasoning_structure_alignment import provision_testing as tests
from rsa_formalizer.stages.reasoning_structure_alignment import provision_repair as repair
from rsa_formalizer.stages.reasoning_structure_alignment import candidate_review as provision_candidate_review
from rsa_formalizer.stages import utils as exp


class CandidateReviewTest(unittest.TestCase):
    def test_generated_clerk_files_are_removed_before_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            workspace = run / "workspace"
            generated = workspace / "_build" / "Api.catala_en"
            generated.parent.mkdir(parents=True)
            generated.write_text("generated")

            def validate(_input, checked_workspace):
                self.assertEqual(checked_workspace, workspace)
                self.assertFalse(generated.exists())
                raise RuntimeError("validation reached")

            with mock.patch.object(provision_candidate_review.exp, "validate_workspace",
                                   side_effect=validate):
                with self.assertRaisesRegex(RuntimeError, "validation reached"):
                    provision_candidate_review.review(run, {})

    def test_replay_exposes_complete_evidence_for_new_and_intermediate_mismatches(self):
        from rsa_formalizer.bobcat.records import ReplayRecords
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            base = run / 'provision_repair'
            workspace = run / 'workspace'
            workspace.mkdir()
            (workspace / 'law.catala_en').write_text('source')
            base.mkdir()
            retained = []
            prior = []
            current = []
            for identifier in ['old', 'new-final', 'new-intermediate', 'aligned']:
                retained.append({'case': {'id': identifier, 'inputs': {'income': 123}},
                                 'reasoning': {'id': identifier, 'output_text': 'Full reasoning for ' + identifier}})
                prior.append({'id': identifier, 'catala_answer': 1,
                              'final_answer_aligned': identifier != 'old'})
                row = {'id': identifier, 'catala_answer': 2, 'llm_final_answer': 1,
                       'final_answer_aligned': identifier in {'new-intermediate', 'aligned'}}
                if identifier == 'new-intermediate':
                    row['computation_graph_alignment'] = {
                        'value_mismatches': [{'quantity': 'Upstream.value', 'catala_value': 2, 'llm_value': 1}]}
                current.append(row)
            exp.atomic_json(base / 'executable_tests.json', {'results': [{'accepted_tests': retained}]})
            exp.atomic_json(base / 'computation_oracles.json', {'cases': {t['case']['id']: {'steps': []} for t in retained}})
            exp.atomic_json(base / 'before.json', {'cases': prior, 'final_answers_aligned': 3,
                                                 'computation_value_mismatch_cases': 0})
            # Only one case was originally reported. New cases must still have evidence.
            exp.atomic_json(base / 'feedback/index.json', {'reports': [{'case_id': 'old'}]})
            candidate = {'cases': current, 'final_answers_aligned': 2,
                         'computation_value_mismatch_cases': 1}

            def replay(_run, _config, state, cases, **kwargs):
                output = Path(state['_stage_directory']) / 'tests_bobcat_symbolic_results'
                output.mkdir()
                exp.atomic_json(output / 'build_errors.json', {})
                paths = []
                for case in cases:
                    path = output / (case['id'] + '.json')
                    exp.atomic_json(path, {'id': case['id'], 'execution_tree': ['concrete trace']})
                    paths.append(path)
                return ReplayRecords(paths)

            with mock.patch.object(provision_candidate_review.exp, 'validate_workspace'), \
                 mock.patch.object(provision_candidate_review, 'replay_compiled', side_effect=replay) as replay_mock, \
                 mock.patch.object(provision_candidate_review.comparison, 'compare', return_value=candidate):
                report = provision_candidate_review.review(run, {})
                self.assertEqual(report['evidence_cases'], 4)
                self.assertEqual(set(report['remaining_case_ids']), {'old', 'new-final', 'new-intermediate'})
                self.assertEqual(report['evidence_index'], '/rsa/feedback/replays/attempt-1/index.json')
                # Same-snapshot cache must preserve the public evidence pointer.
                self.assertEqual(provision_candidate_review.review(run, {}), report)
                self.assertEqual(replay_mock.call_count, 1)
            evidence = base / 'feedback/replays/attempt-1'
            for identifier in ['old', 'new-final', 'new-intermediate', 'aligned']:
                folder = evidence / identifier
                data = exp.load_json(folder / 'report.json')
                self.assertEqual(data['case']['inputs'], {'income': 123})
                self.assertEqual(data['baseline_comparison']['catala_answer'], 1)
                self.assertEqual(data['comparison']['catala_answer'], 2)
                self.assertEqual((folder / 'llm_reasoning.txt').read_text(), 'Full reasoning for ' + identifier)
                self.assertEqual(exp.load_json(folder / 'llm_computation_graph.json'), {'steps': []})
                self.assertTrue((folder / 'computation_graph_alignment.json').exists())
                self.assertEqual(exp.load_json(folder / 'catala_replay.json')['execution_tree'], ['concrete trace'])



class ProvisionTestingTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.run = Path(temporary.name)
        self.baseline = self.run / "baseline"
        self.baseline.mkdir()
        (self.baseline / "law.catala_en").write_text(
            'First rule applies when x is true.\n'
            '<!-- rsa-block-id: law:b1; role: provision; provision-id: law/section1(a); -->\n'
            '```catala\nscope Answer:\n definition result equals true\n```\n'
            'The companion rule applies when x is false.\n'
            '<!-- rsa-block-id: law:b2; role: provision; provision-id: law/section1(b); -->\n'
            '```catala\ndeclaration helper content boolean equals false\n```\n')
        input_root = self.run / "input"
        input_root.mkdir()
        shutil.copy2(self.baseline / "law.catala_en", input_root / "law.catala_en")
        (input_root / "remote.catala_en").write_text(
            '> Module Remote\nRemote provision from a different document.\n'
            '<!-- rsa-block-id: remote:b1; role: provision; provision-id: law/section2(a); -->\n'
            '```catala\ndeclaration implementation_secret content integer equals 999\n```\n')
        shutil.copy2(input_root / "remote.catala_en", self.baseline / "remote.catala_en")
        self.manifest = {"documents": [{"path": "law.catala_en", "blocks": [
            {"block_id": "law:b1", "kind": "catala", "provision_id": "law/section1(a)"},
            {"block_id": "law:b2", "kind": "catala", "provision_id": "law/section1(b)"},
            {"block_id": "unannotated", "kind": "catala", "provision_id": "law/section1(c)"}]},
            {"path": "remote.catala_en", "blocks": []}]}
        exp.atomic_json(input_root / "RSA_MANIFEST.json", self.manifest)
        self.scope = {"scope": "Answer", "compiler_file": "law.catala_en", "source": "law.catala_en",
            "input_schema": {"type": "object", "properties": {"x": {"type": "boolean"}}, "required": ["x"]},
            "output_schema": {"type": "object", "properties": {"result": {"type": "boolean"}}, "required": ["result"]}}
        self.target = {"provision_id": "law/section1(a)", "blocks": [{"source": "law.catala_en", "block_id": "law:b1"}],
                       "entry_points": [self.scope]}
        self.sampled = {"output_text": json.dumps({"inputs_json": json.dumps({"x": True}),
                                                  "condition_explanation": "x satisfies the target condition"})}
        self.case = {"id": "candidate", "target": "Answer", "source": "law.catala_en",
                     "inputs": {"x": True}, "branches": [], "statute_ids": [], "test_strategy": "specification_only"}
        self.response = {"output_text": '1. Under section 1(a), result is true.\n<answer>\n{"result":true}\n</answer>',
                         "execution_tree": {"steps": [{"id": 0, "provision": "section1(a)", "claim": "result is true", "premises": []}]}}

    def test_citation_gate_requires_exact_leaf_in_prose(self):
        for text in ('Under section 1(a), true.', 'Under §1(a), true.', 'section1 (a) gives true.'):
            self.assertTrue(tests.cites_target(text, "law/section1(a)"), text)
        for text in ('section 1(a)(1) applies.', 'section 1 applies.', '<answer>section 1(a)</answer>', 'section 11(a) applies.'):
            self.assertFalse(tests.cites_target(text, "law/section1(a)"), text)

    def test_discovery_targets_only_annotated_fences_and_groups_ids(self):
        manifest = {"documents": [{"path": "law.catala_en", "blocks": [
            {"block_id": "law:b1", "kind": "catala", "provision_id": "law/section1(a)"},
            {"block_id": "law:b2", "kind": "catala", "provision_id": "law/section1(b)"},
            {"block_id": "unannotated", "kind": "catala", "provision_id": "law/section1(c)"}]}]}
        targets = tests.discover_targets(self.baseline, manifest, {"scopes": [self.scope]})
        self.assertEqual([t["provision_id"] for t in targets], ["law/section1(a)", "law/section1(b)"])
        self.assertTrue(all(t["entry_points"][0]["scope"] == "Answer" for t in targets))

    def test_all_provisions_use_full_frozen_corpus_without_code(self):
        context = tests.all_provisions(self.run, {})
        self.assertIn("First rule", context)
        self.assertIn("companion rule", context)
        self.assertIn("Remote provision", context)
        self.assertNotIn("implementation_secret", context)
        self.assertNotIn("definition result", context)
        self.assertNotIn("> Module", context)

    def test_discovery_maps_every_provision_to_public_entry_point(self):
        endpoint = {**self.scope, "scope": "WholeProgram", "compiler_file": "Api.catala_en"}
        mapping = {"requirements": [{"requirement_id": "WHOLE", "file": "Api.catala_en",
                                     "scope": "WholeProgram", "output": "result"}]}
        with mock.patch.object(tests.exp, "load_requirement_outputs", return_value=mapping):
            targets = tests.discover_targets(self.baseline,
                {"documents": [self.manifest["documents"][0]]}, {"scopes": [self.scope, endpoint]})
        self.assertEqual(len(targets), 2)
        self.assertTrue(all(t["entry_points"][0]["scope"] == "WholeProgram" for t in targets))
        self.assertTrue(all(t["entry_points"][0]["source"] == "Api.catala_en" for t in targets))

    def test_no_fallback_to_internal_scopes_when_api_contract_is_missing(self):
        with self.assertRaisesRegex(exp.RunnerError, "public API"):
            tests.entry_points(self.baseline, {"scopes": [self.scope, {**self.scope, "scope": "Internal"}]})

    def generate(self, budget=3):
        from rsa_formalizer.stages.reasoning_structure_alignment import computation_alignment
        def graph_for(run, config, baseline, case, response):
            provision = ("section1(b)" if "section 1(b)" in response["output_text"]
                         else "section1(a)")
            return {"status": "complete", "graph": {"nodes": [
                {"id": 0, "provision": provision, "premises": [],
                 "evidence": f"Under {provision}"},
                {"id": 1, "provision": None, "premises": [0], "quantity": "Answer.result",
                 "value": "true", "evidence": '"result":true'},
            ]}}
        with mock.patch.object(computation_alignment, "extract_before_replay", side_effect=graph_for):
            return tests.generate_target(self.run, {}, self.target, self.baseline,
                                         {"scopes": [self.scope]}, budget)

    def test_graph_selection_happens_after_shared_generation(self):
        rejected = {**self.response, "output_text": 'Under section 1(b), true.\n<answer>{"result":true}</answer>'}
        with mock.patch.object(tests, "_sample_input", return_value=self.sampled) as design, \
             mock.patch.object(tests.reasoning, "reason", side_effect=[[rejected], [self.response], [self.response]]) as reason:
            result = self.generate()
            self.assertEqual(result["status"], "accepted")
            retained = result["accepted_tests"]
            self.assertEqual([test["attempt"] for test in retained], [0, 1, 2])
            self.assertEqual(result["attempt_count"], 3)
            self.assertEqual(result["attempts"], [])
            self.assertEqual(design.call_count, 3)
            self.assertEqual(reason.call_count, 3)
            from rsa_formalizer.stages.utils.input_history import expand
            second_prompt = design.call_args_list[1].args[2]
            history = expand(json.loads(second_prompt.suffix.split("PREVIOUS SCHEMA-VALID INPUTS\n", 1)[1]))
            self.assertEqual([item["attempt"] for item in history], [0])
            self.assertNotIn("natural_language_facts", retained[0]["case"])
            self.assertNotIn("generated_expected_answer", retained[0]["case"])
            self.assertEqual(retained[0]["case"]["input_authority"], "structured_json")
            reasoned_case = reason.call_args.args[3][0]
            self.assertEqual(reasoned_case["inputs"], retained[-1]["case"]["inputs"])
            self.assertIn("Remote provision", reasoned_case["statute_context"])
            self.assertEqual(self.generate(), result)
            self.assertEqual(reason.call_count, 3)
            oracles = {retained[0]["case"]["id"]: {"status": "complete", "graph": {"nodes": []}}}
            oracles.update({test["case"]["id"]: {"status": "extraction_error"} for test in retained[1:]})
            selected = tests.select_by_computation_graph([result], oracles)
            self.assertEqual([test["attempt"] for test in selected[0]["accepted_tests"]], [1, 2])

    def test_three_successes_are_all_retained_with_compact_input_history(self):
        from rsa_formalizer.stages.utils.input_history import expand
        with mock.patch.object(tests, "_sample_input", return_value=self.sampled) as design, \
             mock.patch.object(tests.reasoning, "reason", return_value=[self.response]) as reason:
            result = self.generate(3)
        self.assertEqual(len(result["accepted_tests"]), 3)
        self.assertEqual(design.call_count, 3)
        self.assertEqual(reason.call_count, 3)
        prompts = [call.args[2] for call in design.call_args_list]
        self.assertTrue(all(prompt.prefix == prompts[0].prefix for prompt in prompts))
        for index, prompt in enumerate(prompts):
            history = expand(json.loads(prompt.suffix.split("PREVIOUS SCHEMA-VALID INPUTS\n", 1)[1]))
            self.assertEqual(len(history), index)
            self.assertTrue(all(item["inputs"] == {"x": True} for item in history))
            self.assertNotIn("satisfies the target condition", prompt)
        self.assertEqual(len({test["case"]["id"] for test in result["accepted_tests"]}), 3)
        # Historical inputs and designer explanations never enter independent reasoner cases.
        self.assertTrue(all("previous_inputs" not in call.args[3][0] for call in reason.call_args_list))

    def test_partial_success_survives_later_failures(self):
        rejected = {**self.response, "output_text": 'Under section 1(b), true.\n<answer>{"result":true}</answer>'}
        with mock.patch.object(tests, "_sample_input", return_value=self.sampled), \
             mock.patch.object(tests.reasoning, "reason", side_effect=[[self.response], [rejected], [rejected]]):
            result = self.generate(3)
        self.assertEqual(result["status"], "accepted")
        self.assertEqual([test["attempt"] for test in result["accepted_tests"]], [0, 1, 2])
        self.assertEqual(len(result["attempts"]), 0)
        self.assertEqual(result["attempt_count"], 3)

    def test_citation_is_provisionally_retained_without_tree_extraction(self):
        response = {**self.response, "execution_tree": {"steps": [{"provision": "section1(b)"}]}}
        with mock.patch.object(tests, "_sample_input", return_value=self.sampled), \
             mock.patch.object(tests.reasoning, "reason", return_value=[response]):
            result = self.generate(1)
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(len(result["accepted_tests"]), 1)

    def test_computation_graph_is_sole_structured_target_gate(self):
        result = {"status": "accepted", "target": self.target, "attempts": [],
                  "accepted_tests": [{"attempt": 0, "case": self.case, "reasoning": self.response}]}
        graph = {"status": "complete", "graph": {"nodes": [
            {"id": 0, "provision": "section1(a)", "premises": [], "evidence": "Section 1(a) applies"},
            {"id": 1, "provision": None, "premises": [], "evidence": '"result":true'}]}}
        rejected = tests.select_by_computation_graph([result], {self.case["id"]: graph})[0]
        self.assertEqual(rejected["status"], "attempt_budget_exhausted")
        self.assertEqual(rejected["attempts"][0]["reason"], "target_not_used_in_computation_graph")
        diagnostic = tests.select_by_computation_graph(
            [result], {self.case["id"]: graph}, reject_unapplied=False)[0]
        self.assertEqual(diagnostic["status"], "accepted")
        self.assertEqual(diagnostic["attempts"], [])
        self.assertEqual(diagnostic["accepted_tests"][0]["computation_graph_selection"]["status"], "not_applied")
        graph["graph"]["nodes"][1]["premises"] = [0]
        kept = tests.select_by_computation_graph([result], {self.case["id"]: graph})[0]
        self.assertEqual(kept["accepted_tests"][0]["computation_graph_selection"]["status"], "applied")

    def test_generator_receives_all_provisions_schema_and_failure_feedback(self):
        invalid = {"output_text": json.dumps({"inputs_json": json.dumps({"x": "bad"}),
                                             "condition_explanation": "invalid value"})}
        with mock.patch.object(tests, "_sample_input", side_effect=[invalid, self.sampled]) as sample, \
             mock.patch.object(tests.reasoning, "reason", return_value=[self.response]) as reason:
            result = self.generate(2)
        self.assertEqual(result["status"], "accepted")
        first_prompt = sample.call_args_list[0].args[2]
        second_prompt = sample.call_args_list[1].args[2]
        self.assertIn("Remote provision", first_prompt)
        self.assertIn(json.dumps(self.scope["input_schema"], sort_keys=True), first_prompt)
        self.assertNotIn("implementation_secret", first_prompt)
        self.assertIn("invalid_input_schema", second_prompt)
        self.assertIn('"path": ["x"]', second_prompt)
        self.assertIn("not of type", second_prompt)
        reason.assert_called_once()

    def test_structured_json_is_only_fact_authority_for_reasoning(self):
        case = {**self.case, "input_authority": "structured_json",
                "natural_language_facts": "NARRATIVE_ONLY_SECRET", "test_rationale": "DESIGNER_ONLY_SECRET"}
        prompt = tests.reasoning._prompt("ALL_PROVISIONS", case, self.scope["output_schema"])
        self.assertIn("complete authoritative case", prompt)
        self.assertNotIn("NARRATIVE_ONLY_SECRET", prompt)
        self.assertNotIn("DESIGNER_ONLY_SECRET", prompt)

    def test_intermediate_scope_inputs_are_rejected_for_full_program_case(self):
        schema = {"type": "object", "additionalProperties": False,
                  "required": ["world", "taxpayer", "period"], "properties": {
                      "world": {"type": "object"}, "taxpayer": {"type": "integer"},
                      "period": {"type": "integer"}}}
        self.target["entry_points"] = [{**self.scope, "scope": "WholeProgram",
                                        "source": "Api.catala_en", "input_schema": schema}]
        full_input = {"world": {}, "taxpayer": 1, "period": 2026}
        samples = [{"output_text": json.dumps({"inputs_json": json.dumps(value), "condition_explanation": "target"})}
                   for value in ({"taxable_income": 50000, "married": True}, full_input)]
        with mock.patch.object(tests, "_sample_input", side_effect=samples), \
             mock.patch.object(tests.reasoning, "reason", return_value=[self.response]) as reason:
            result = self.generate(2)
        retained = result["accepted_tests"][0]
        self.assertEqual(retained["attempt"], 1)
        self.assertEqual(retained["case"]["target"], "WholeProgram")
        self.assertEqual(retained["case"]["source"], "Api.catala_en")
        self.assertEqual(retained["case"]["inputs"], full_input)
        reason.assert_called_once()

    def test_overlapping_catala_money_schema_accepts_integer_zero(self):
        schema = {"type": "object", "required": ["amount"], "properties": {
            "amount": {"oneOf": [{"type": "integer"}, {"type": "number"}, {"type": "string"}]}}}
        self.assertEqual(tests._schema_errors({"amount": 0}, schema), [])

    def test_old_scope_level_cache_is_rejected(self):
        root = self.run / "provision_repair/tests" / tests.target_slug(self.target["provision_id"])
        exp.atomic_json(root / "result.json", {"status": "accepted", "case": self.case})
        with self.assertRaisesRegex(exp.RunnerError, "stale provision tests"):
            self.generate()

    def test_changed_contract_prose_invalidates_saved_cases(self):
        source = self.run / "input/Definitions.catala_en"
        source.write_text('Public input convention: endpoints are inclusive.\n'
            '```catala-metadata\ndeclaration structure Request: # Public facts.\n'
            '  data x content boolean # Supplied condition.\n```\n')
        self.scope["input_schema"] = {"$ref": "#/definitions/Definitions.Request", "definitions": {
            "Definitions.Request": {"type": "object", "properties": {"x": {"type": "boolean"}},
                                    "required": ["x"]}}}
        with mock.patch.object(tests, "_sample_input", return_value=self.sampled) as sample, \
             mock.patch.object(tests.reasoning, "reason", return_value=[self.response]):
            self.assertEqual(self.generate(1)["status"], "accepted")
            source.write_text(source.read_text().replace("endpoints are inclusive", "final endpoint is excluded"))
            with self.assertRaisesRegex(exp.RunnerError, "stale provision tests"):
                self.generate(1)
            sample.assert_called_once()

    def test_uncited_reasoning_is_rejected_before_structure_extraction(self):
        exp.atomic_json(self.run / "tests_bobcat_symbolic_results/input_formats.json", {"scopes": [self.scope]})
        case = {**self.case, "required_provision": "law/section1(a)"}
        config = {"run_id": "test", "reasoning_trace": {"model": "mock", "provider": "openai", "jobs": 1}}
        with mock.patch.object(tests.reasoning, "_statutes", return_value="[section1(a)] Rule."), \
             mock.patch.object(tests.reasoning, "requirement_descriptions", return_value={}), \
             mock.patch.object(tests.reasoning.usage_tracking, "api_call",
                               side_effect=lambda directory, context, key, call: call()), \
             mock.patch.object(tests.reasoning, "_sample", return_value={
                 "output_text": 'Under section 1(b), false.\n<answer>{"result":false}</answer>'}) as sample:
            result = tests.reasoning.reason(self.run, config, {"_stage_directory": str(self.run)}, [case])[0]
        self.assertFalse(result["target_provision_cited"])
        self.assertIsNone(result["execution_tree"])
        sample.assert_called_once()

    def test_provision_reasoning_skips_tree_extraction(self):
        exp.atomic_json(self.run / "tests_bobcat_symbolic_results/input_formats.json", {"scopes": [self.scope]})
        case = {**self.case, "input_authority": "structured_json",
                "required_provision": "law/section1(a)"}
        config = {"run_id": "test", "reasoning_trace": {"model": "mock", "provider": "openai", "jobs": 1}}
        state = {"_stage_directory": str(self.run),
                 "_skip_reasoning_structure_extraction": True}
        with mock.patch.object(tests.reasoning, "_statutes", return_value="[section1(a)] Rule."), \
             mock.patch.object(tests.reasoning, "requirement_descriptions", return_value={}), \
             mock.patch.object(tests.reasoning.usage_tracking, "api_call", return_value={
                 "output_text": self.response["output_text"]}) as api:
            result = tests.reasoning.reason(self.run, config, state, [case])[0]
        self.assertEqual(api.call_count, 1)
        self.assertIsNone(result["execution_tree"])
        self.assertIsNone(result["execution_tree_extraction_error"])

    def test_incomplete_answer_is_retained_for_branch_diagnostics(self):
        response = {**self.response, "output_text": 'Under section 1(a), true.\n<answer>{"other":true}</answer>'}
        with mock.patch.object(tests, "_sample_input", return_value=self.sampled), \
             mock.patch.object(tests.reasoning, "reason", return_value=[response]):
            result = self.generate(1)
        self.assertEqual(len(result["accepted_tests"]), 1)

    def test_reports_include_answer_or_value_mismatch_but_not_attribution_only(self):
        results = []
        rows = []
        for index in range(6):
            case = {**self.case, "id": str(index)}
            results.append({"status": "accepted", "target": self.target, "case": case, "reasoning": self.response})
            rows.append({"id": str(index), "final_answer_aligned": index != 0,
                         "provision_alignment": {"catala_only": [], "llm_only": []}})
        rows[1]["provision_alignment"]["llm_only"] = ["section1(a)"]
        rows[1]["computation_graph_alignment"] = {
            "status": "compared", "provision_attribution_differences": [{"llm_provision": "section1(a)"}]}
        rows[2]["code_execution_error"] = True
        rows[3]["computation_graph_alignment"] = {
            "status": "compared", "value_mismatches": [{"quantity": "TaxStatus.eligible", "catala_value": False,
                                                        "llm_value": "true"}]}
        rows[4]["computation_graph_alignment"] = {"status": "extraction_error", "error": "unavailable"}
        rows[5]["provision_alignment"]["catala_only"] = ["section1(a)"]
        index = tests.write_reports(self.run, results, {"cases": rows}, [{"id": "0", "execution_tree": ["raw"]}])
        self.assertEqual([r["case_id"] for r in index["reports"]], ["0", "3"])
        self.assertEqual(index["reports"][0]["report_reasons"], ["final_answer_failure"])
        self.assertEqual(index["reports"][1]["report_reasons"], ["intermediate_value_divergence"])
        self.assertEqual(len(index["diagnostics"]), 2)
        first = exp.load_json(self.run / "feedback" / index["reports"][0]["report"])
        self.assertEqual(first["comparison"]["id"], "0")

    def test_reports_preserve_multiple_cases_for_the_same_provision(self):
        records = [{"attempt": i, "case": {**self.case, "id": f"case-{i}"}, "reasoning": self.response}
                   for i in range(3)]
        results = [{"status": "accepted", "target": self.target, "accepted_tests": records}]
        rows = [{"id": test["case"]["id"], "final_answer_aligned": False} for test in records]
        index = tests.write_reports(self.run, results, {"cases": rows})
        self.assertEqual(len(index["reports"]), 3)
        self.assertEqual(len({row["report"] for row in index["reports"]}), 3)


class NonrecursiveCoordinatorTest(unittest.TestCase):
    def test_one_agent_session_and_same_cases_replayed_afterward(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            base = run / "provision_repair"
            baseline = base / "analysis/snapshot"
            baseline.mkdir(parents=True)
            (baseline / "law.catala_en").write_text('before')
            workspace = run / "workspace"
            workspace.mkdir()
            (workspace / "law.catala_en").write_text('after')
            case = {"id": "fixed-test"}
            target = {"provision_id": "law/section1(a)", "blocks": [], "scopes": []}
            extra_case = {"id": "second-fixed-test"}
            gap_target = {**target, "provision_id": "law/section1(b)"}
            results = [{"status": "accepted", "target": target, "attempt_count": 3,
                        "accepted_tests": [{"case": item, "reasoning": {"id": item["id"], "output_text": "raw reasoning"}}
                                           for item in [case, extra_case]]},
                       {"status": "attempt_budget_exhausted", "target": gap_target,
                        "accepted_tests": [], "attempt_count": 3, "attempts": []}]
            exp.atomic_json(base / "formats.json", {"scopes": []})
            exp.atomic_json(base / "plan.json", {"targets": [target, gap_target], "generation_format": tests.FORMAT})
            exp.atomic_json(base / "tests.json", {"results": results})
            before = {"cases": [{"id": "fixed-test", "final_answer_aligned": False}], "final_answers_misaligned": 1}
            after = {"cases": [{"id": "fixed-test", "final_answer_aligned": True}], "final_answers_misaligned": 0}
            state = {"provision_phase": "compare", "completed_stages": ["initialized"]}
            config = {"repair": {"mode": "reasoning_structure_alignment", "computation_graph_alignment": {"enabled": True}}}
            oracles = {item["id"]: {"status": "extraction_error"} for item in [case, extra_case]}
            oracles[case["id"]] = {"status": "complete", "graph": {"nodes": []}}
            exp.atomic_json(base / "computation_oracles.json", {"cases": oracles})
            from rsa_formalizer.stages import formalization, validation
            with mock.patch.object(repair, "replay_compiled", return_value=[
                 {"id": item["id"], "output": {"result": True}, "error": None}
                 for item in [case, extra_case]]) as replay, \
                 mock.patch.object(repair.comparison, "compare", side_effect=[before, after]) as compare, \
                 mock.patch.object(formalization, "run") as agent, \
                 mock.patch.object(validation, "run", return_value=True), \
                 mock.patch.object(repair.exp, "publish_stage_snapshot"), \
                 mock.patch("rsa_formalizer.stages.reasoning_structure_alignment.artifact_retention.prune_completed"):
                self.assertEqual(repair.run(run, config, state)["provision_phase"], "agent")
                self.assertEqual(repair.run(run, config, state)["provision_phase"], "evaluate")
                result = repair.run(run, config, state)
            agent.assert_called_once()
            self.assertEqual(compare.call_args_list[0].args[3], compare.call_args_list[1].args[3])
            self.assertEqual(compare.call_args_list[1].args[3][0]["computation_graph"], oracles["fixed-test"])
            self.assertEqual(replay.call_count, 2)
            self.assertEqual(replay.call_args_list[0].args[3], replay.call_args_list[1].args[3])
            self.assertEqual(result["next_stage"], "finished")
            self.assertNotIn("recursive_repair_queue", result)
            self.assertEqual(exp.load_json(base / "summary.json")["summarizer_calls"], 0)
            summary = exp.load_json(base / "summary.json")
            self.assertEqual(summary["accepted_cases"], 2)
            self.assertEqual(summary["accepted_provisions"], 1)
            self.assertEqual(summary["generation_gaps"], 1)
            self.assertEqual(summary["generation_attempts"], 6)
            self.assertEqual(replay.call_args_list[0].args[3], [case, extra_case])


if __name__ == "__main__":
    unittest.main()
