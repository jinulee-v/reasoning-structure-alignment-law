from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from rtdf_formalizer.bobcat.replay import _sync_case_metadata
from rtdf_formalizer.bobcat.trace import branch_provision_outcomes
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.metamorphic_pairs import (
    _schema,
    bobcat_pairs,
    evaluate_pairs,
    llm_pairs,
)


class MetamorphicPairTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.snapshot = Path(self.temporary.name)
        (self.snapshot / "law.catala_en").write_text(
            """<!-- rtdf-block-id: law:b1; role: provision; provision-id: law:p1; -->
```catala
scope Rule:
  definition result equals
    if eligible then 1 else 0
```
""",
            encoding="utf-8",
        )

    @staticmethod
    def tree(outcome: bool, *, json_position: bool = False):
        position = (
            {"file": "../law.catala_en", "start": {"line": 4, "character": 0}}
            if json_position
            else {"filename": "law.catala_en", "start_line": 5}
        )
        return [{"kind": "branch", "pos": position, "outcome": outcome, "children": []}]

    def test_branch_mapping_accepts_json_source_ranges(self):
        branches = branch_provision_outcomes(
            self.snapshot, self.tree(True, json_position=True)
        )
        self.assertEqual(branches[0]["provision"], "law:p1")
        self.assertTrue(branches[0]["outcome"])

    def test_bobcat_pair_requires_output_and_exact_branch_divergence(self):
        rows = [
            {
                "id": "left",
                "case_origin": "bobcat",
                "output": {"value": 0},
                "dynamic_slice_tree": self.tree(False),
            },
            {
                "id": "right",
                "case_origin": "bobcat",
                "output": {"value": 1},
                "dynamic_slice_tree": self.tree(True),
            },
        ]
        pairs = bobcat_pairs(self.snapshot, rows, 2)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["property"]["divergence_provision"], "law:p1")
        self.assertTrue(pairs[0]["preserved"])

    def test_zero_limit_disables_bobcat_pairs(self):
        self.assertEqual(bobcat_pairs(self.snapshot, [], 0), [])

    def test_llm_pair_response_schema_is_valid(self):
        Draft202012Validator.check_schema(_schema(["left", "right"], ["law:p1"], 2))

    def test_cached_pair_properties_are_revalidated_without_resampling(self):
        stage = self.snapshot / "analysis"
        (stage / "snapshot").mkdir(parents=True)
        (stage / "snapshot/law.catala_en").write_text(
            (self.snapshot / "law.catala_en").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        root = stage / "tests_metamorphic_pairs"
        root.mkdir()
        exp = {
            "format": "provision_metamorphic_pairs_v1",
            "bobcat_pairs": [
                {
                    "origin": "bobcat",
                    "left_case_id": "left",
                    "right_case_id": "right",
                    "property": {
                        "output_relation": "different",
                        "divergence_provision": "law:p1",
                        "left_branch_outcomes": [False],
                        "right_branch_outcomes": [True],
                    },
                    "preserved": True,
                }
            ],
            "llm_pairs": [
                {
                    "origin": "llm_generated_nl",
                    "left_case_id": "nl-left",
                    "right_case_id": "nl-right",
                    "property": {
                        "output_relation": "different",
                        "exclusive_provision": "law:p1",
                        "executed_in": "left",
                        "rationale": "Only the left case takes the rule.",
                    },
                    "preserved": True,
                }
            ],
            "llm_generation_error": None,
        }
        (root / "summary.json").write_text(
            json.dumps(exp), encoding="utf-8"
        )
        symbolic = [
            {"id": "left", "output": 0, "dynamic_slice_tree": self.tree(False)},
            {"id": "right", "output": 1, "dynamic_slice_tree": self.tree(True)},
            {"id": "nl-left", "output": 0, "dynamic_slice_tree": self.tree(True)},
            {"id": "nl-right", "output": 1, "dynamic_slice_tree": []},
        ]
        state = {"_stage_directory": str(stage)}

        with mock.patch(
            "rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.metamorphic_pairs.usage_tracking.api_call",
            side_effect=AssertionError("must not resample"),
        ):
            summary = evaluate_pairs(
                self.snapshot,
                {},
                state,
                {"id": "law::Rule"},
                symbolic,
                2,
                comparison={
                    "cases": [
                        {
                            "id": "nl-left",
                            "case_origin": "llm_generated_nl",
                            "llm_final_answer": {"answer": 0},
                        },
                        {
                            "id": "nl-right",
                            "case_origin": "llm_generated_nl",
                            "llm_final_answer": {"answer": 1},
                        },
                    ]
                },
            )

        self.assertTrue(summary["reused_properties"])
        self.assertEqual(summary["preserved"], 2)

        summary = evaluate_pairs(
            self.snapshot,
            {},
            state,
            {"id": "law::Rule"},
            symbolic,
            2,
            comparison={
                "cases": [
                    {
                        "id": "nl-left",
                        "case_origin": "llm_generated_nl",
                        "llm_final_answer": {"answer": None},
                    },
                    {
                        "id": "nl-right",
                        "case_origin": "llm_generated_nl",
                        "llm_final_answer": {"answer": 1},
                    },
                ]
            },
        )
        self.assertEqual(summary["llm_pairs"][0]["validation_status"], "grounding_unavailable")
        self.assertEqual(summary["preserved"], 1)

    def test_replay_preserves_generated_design_id(self):
        replayed = {}
        self.assertTrue(
            _sync_case_metadata(replayed, {"generated_design_id": "nl-1"})
        )
        self.assertEqual(replayed["generated_design_id"], "nl-1")

    def test_llm_pair_generation_uses_design_ids_for_executable_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            stage = run / "analysis"
            generated = stage / "tests_llm_generated"
            generated.mkdir(parents=True)
            (stage / "snapshot").mkdir()
            (generated / "generation.json").write_text(
                """{"generated":{"cases":[
                  {"id":"nl-1","facts":"A.","question":"Q?","expected_answer":"1","reasoning_steps":[]},
                  {"id":"nl-2","facts":"B.","question":"Q?","expected_answer":"2","reasoning_steps":[]}
                ]},"selected_provision_ids":["law:p1"]}""",
                encoding="utf-8",
            )
            symbolic = [
                {"id": "hashed-left", "generated_design_id": "nl-1", "output": 1},
                {"id": "hashed-right", "generated_design_id": "nl-2", "output": 2},
            ]
            scope = {"id": "law::Rule"}
            state = {"recursive_phase": "scope", "_stage_directory": str(stage)}
            config = {
                "run_id": "fixture",
                "reasoning_trace": {"provider": "openai", "model": "model"},
            }
            with mock.patch(
                "rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.metamorphic_pairs.statute_context",
                return_value=("[law:p1] Rule.", ["law:p1"]),
            ), mock.patch(
                "rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.metamorphic_pairs.usage_tracking.api_call",
                return_value={"output_text": '{"pairs":[]}', "usage": None},
            ):
                pairs, _ = llm_pairs(run, config, state, scope, symbolic, 2)

            self.assertEqual(pairs, [])


if __name__ == "__main__":
    unittest.main()
