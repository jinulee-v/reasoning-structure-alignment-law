from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rtdf_formalizer.stages import utils as exp
from rtdf_formalizer.stages import reasoning_trace_diff_fuzzing as pipeline
from rtdf_formalizer.bobcat import comparison as comparison_stage
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing import repair
from rtdf_formalizer.bobcat import compiled_json
from rtdf_formalizer.main import argument_parser
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.repair import (
    bundle_report,
    replay,
)
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.repair import (
    recursive as recursive_repair,
)


SCHEMA = {
    "type": "object",
    "properties": {
        "tax": {"$ref": "#/definitions/money"},
        "unrelated": {"type": "integer"},
    },
    "required": ["tax", "unrelated"],
    "definitions": {"money": {"type": "number", "title": "Catala Money"}},
}


class RepairTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.run = Path(self.temporary.name)
        (self.run / "workspace").mkdir()

    def state(self, iteration=0, stage="agent"):
        return {
            "iteration": iteration,
            "next_stage": stage,
            "status": "running",
            "completed_stages": [],
            "active_attempt": None,
        }

    def test_cli_exposes_recursive_mode(self):
        parser = argument_parser()
        start = parser._subparsers._group_actions[0].choices["start"]
        action = next(item for item in start._actions if item.dest == "repair_mode")
        self.assertEqual(
            set(action.choices), {"no-testing", "answer-only", "recursive"}
        )
        self.assertEqual(start.get_default("max_iteration"), 2)
        with self.assertRaisesRegex(exp.RunnerError, "must be"):
            repair.mode({"repair": {"mode": "rsa"}})

    def test_recursive_scope_order_is_dependency_first(self):
        scopes = [
            {"compiler_file": "api", "scope": "Top"},
            {"compiler_file": "law", "scope": "LeafB"},
            {"compiler_file": "law", "scope": "LeafA"},
            {"compiler_file": "law", "scope": "Middle"},
        ]
        sid = recursive_repair.scope_id
        dependencies = {
            sid("api", "Top"): {sid("law", "Middle")},
            sid("law", "Middle"): {sid("law", "LeafA"), sid("law", "LeafB")},
        }
        plan = recursive_repair.topological_scope_order(scopes, dependencies)
        self.assertEqual(
            [item["scope"] for item in plan], ["LeafA", "LeafB", "Middle", "Top"]
        )

    def test_recursive_descendant_edit_requeues_descendant(self):
        plan = [
            {"id": "law::Leaf", "source": "law", "scope": "Leaf", "dependencies": []},
            {
                "id": "law::Top",
                "source": "law",
                "scope": "Top",
                "dependencies": ["law::Leaf"],
            },
        ]
        state = {
            "recursive_repair_plan": plan,
            "recursive_repair_queue": [],
            "recursive_active_scope": "law::Top",
            "recursive_revision": 0,
            "recursive_processed": {"law::Leaf": {"fingerprint": "old"}},
        }
        requeued = recursive_repair.record_processed(
            state, {"law::Leaf": "new", "law::Top": "same"}, {"law::Leaf"}
        )
        self.assertEqual(requeued, {"law::Leaf"})
        self.assertEqual(state["recursive_repair_queue"], ["law::Leaf"])

    def test_later_descendant_change_invalidates_processed_caller(self):
        plan = [
            {"id": "law::Leaf", "source": "law", "scope": "Leaf", "dependencies": []},
            {
                "id": "law::Top",
                "source": "law",
                "scope": "Top",
                "dependencies": ["law::Leaf"],
            },
        ]
        state = {
            "recursive_repair_plan": plan,
            "recursive_repair_queue": [],
            "recursive_active_scope": "law::Leaf",
            "recursive_revision": 1,
            "recursive_processed": {"law::Top": {"fingerprint": "old"}},
        }
        recursive_repair.record_processed(
            state, {"law::Leaf": "new", "law::Top": "same"}, {"law::Leaf"}
        )
        self.assertEqual(state["recursive_repair_queue"], ["law::Top"])

    def test_processed_scope_tree_is_collapsed_without_inputs(self):
        state = {
            "recursive_active_scope": "law::Top",
            "recursive_processed": {"law::Leaf": {}},
            "recursive_repair_plan": [
                {"id": "law::Leaf", "scope": "Leaf"},
                {"id": "law::Top", "scope": "Top"},
            ],
        }
        tree = {
            "kind": "scope_call",
            "name": "Leaf",
            "inputs": {"large": [1, 2]},
            "output": {"answer": 3},
            "children": [{"kind": "variable"}],
        }
        collapsed = recursive_repair.prune_execution_tree(tree, state)
        self.assertEqual(collapsed["kind"], "processed_scope")
        self.assertNotIn("inputs", collapsed)
        self.assertNotIn("children", collapsed)

    def test_recursive_artifacts_do_not_use_iteration_directory(self):
        initial = {"iteration": 0, "recursive_phase": "initial"}
        self.assertEqual(exp.stage_directory(self.run, initial), self.run / "initial")
        state = {
            "iteration": 0,
            "recursive_phase": "scope",
            "recursive_step": "analysis",
            "recursive_active_scope": "law::Leaf",
            "recursive_revision": 1,
            "recursive_repair_plan": [{"id": "law::Leaf", "scope": "Leaf"}],
        }
        self.assertEqual(
            exp.stage_directory(self.run, state),
            self.run
            / "refinement"
            / recursive_repair.scope_slug(state["recursive_repair_plan"][0])
            / "revisions/001/analysis",
        )

    def test_scope_bundle_contains_only_raw_case_evidence(self):
        state = {
            "recursive_active_scope": "law::Leaf",
            "recursive_processed": {},
            "recursive_repair_plan": [
                {"id": "law::Leaf", "source": "law.catala_en", "scope": "Leaf"}
            ],
        }
        cases = [{"id": "case:1", "inputs": {"income": 2}, "branches": ["private"]}]
        symbolic = [
            {"id": "case:1", "output": {"tax": 1}, "error": None, "execution_tree": []}
        ]
        natural = [
            {
                "id": "case:1",
                "output_text": '<answer>{"tax": 1}</answer>',
                "execution_tree": {"steps": []},
            }
        ]
        bundle = recursive_repair.write_scope_bundle(
            self.run, state, cases, symbolic, natural
        )
        record = json.loads((bundle / "cases/case_1/case.json").read_text())
        self.assertEqual(record["llm_answer"], {"tax": 1})
        self.assertEqual(
            set(record),
            {
                "case_id",
                "input",
                "catala_output",
                "catala_error",
                "llm_answer",
                "llm_error",
            },
        )
        self.assertNotIn("branches", record)
        self.assertEqual(bundle_report(bundle)[0]["input"], {"income": 2})

    def test_summary_requires_every_remaining_case_exactly_once(self):
        value = {
            "scope": "Leaf",
            "change_summary": ["No code change."],
            "remaining_disagreements": [
                {"case_id": "a", "rationale": "The LLM omitted the threshold."}
            ],
        }
        self.assertIs(recursive_repair.validate_summary(value, "Leaf", {"a"}), value)
        with self.assertRaisesRegex(ValueError, "case IDs"):
            recursive_repair.validate_summary(value, "Leaf", {"a", "b"})

    def test_changed_helper_requeues_its_scope_users(self):
        affected = {"law::shared": {"law::Leaf", "law::Top"}}
        self.assertEqual(
            recursive_repair.helper_affected_scopes({"law::shared"}, affected),
            {"law::Leaf", "law::Top"},
        )

    def test_answer_only_pauses_before_reasoning(self):
        state = self.state(stage="reasoning_trace_diff_fuzzing")
        config = {"repair": {"mode": "answer-only"}}
        with (
            mock.patch.object(pipeline, "backfill_options", return_value={}),
            mock.patch.object(pipeline, "generate_tests", return_value=[]),
            mock.patch.object(pipeline, "replay_compiled", return_value=[]),
            mock.patch.object(pipeline, "reason") as reasoning,
        ):
            pipeline.run(self.run, config, state)
        reasoning.assert_not_called()
        self.assertEqual(state["status"], "awaiting_reasoning")

    def test_report_and_replay_support_requirement_contract(self):
        formats = {
            "scopes": [
                {
                    "file": "tax.catala_en",
                    "compiler_file": "tax.catala_en",
                    "scope": "Tax",
                    "input_schema": {
                        "type": "object",
                        "properties": {"income": {"type": "number"}},
                    },
                    "output_schema": SCHEMA,
                }
            ]
        }
        root = self.run / "iterations/000/tests_bobcat_symbolic_results"
        exp.atomic_json(root / "input_formats.json", formats)
        symbolic = [
            {
                "id": "0",
                "source": "tax.catala_en",
                "target": "Tax",
                "requirement_id": "TAX",
                "output_name": "tax",
                "inputs": {"income": 1},
                "output": {"tax": 10, "unrelated": 1},
                "error": None,
            }
        ]
        natural = [{"id": "0", "output_text": '<answer>{"tax": 10}</answer>'}]
        summary = comparison_stage.compare(self.run, self.state(), symbolic, natural)
        report = repair.publish_report(self.run, self.state(), summary)
        row = json.loads(report.read_text())[0]
        self.assertEqual(row["source"], "tax.catala_en")
        self.assertEqual(row["scope"], "Tax")

    def test_replay_rebuilds_current_workspace(self):
        report = self.run / "report.json"
        exp.atomic_json(report, [{"requirement_id": "TAX", "input": {"income": 20}}])
        mappings = {
            "requirements": [
                {
                    "requirement_id": "TAX",
                    "file": "tax.catala_en",
                    "scope": "Tax",
                    "output": "tax",
                }
            ]
        }
        formats = {
            "scopes": [
                {
                    "file": "tax.catala_en",
                    "compiler_file": "tax.catala_en",
                    "scope": "Tax",
                    "output_schema": SCHEMA,
                }
            ]
        }

        def build(project, formats, **kwargs):
            binary = compiled_json.compiled_path(project, "tax.catala_en", "Tax")
            binary.parent.mkdir(parents=True)
            binary.touch()
            return {}

        with (
            mock.patch.object(exp, "load_requirement_outputs", return_value=mappings),
            mock.patch.object(exp, "extract_input_formats", return_value=formats),
            mock.patch.object(compiled_json, "build_bridges", side_effect=build),
            mock.patch(
                "rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.repair.subprocess.run",
                return_value=mock.Mock(
                    returncode=0, stdout='{"tax":42,"unrelated":99}', stderr=""
                ),
            ),
        ):
            rows = replay(report, self.run / "workspace")
        self.assertEqual(rows[0]["code_execution_output"], {"tax": 42})


if __name__ == "__main__":
    unittest.main()
