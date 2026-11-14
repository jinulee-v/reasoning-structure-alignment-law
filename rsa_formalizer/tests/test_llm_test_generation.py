from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rsa_formalizer.stages.reasoning_structure_alignment import generate_llm_test


class LlmTestGenerationTest(unittest.TestCase):
    def test_missing_required_fact_sentinels_are_found_recursively(self):
        self.assertEqual(
            generate_llm_test._missing_fact_paths(
                {
                    "itinerary": {
                        "items": [{"price": "MISSING_REQUIRED_FACT: not stated"}]
                    }
                }
            ),
            ["$.itinerary.items[0].price"],
        )
        self.assertEqual(generate_llm_test._missing_fact_paths("ordinary text"), [])

    def test_grounding_fidelity_rejects_representable_but_omitted_facts(self):
        audit = {
            "facts": [
                {
                    "fact": "One worker receives $9,000.",
                    "status": "represented",
                    "candidate_requirements": [
                        "facts.employees[].cash_remuneration"
                    ],
                },
                {
                    "fact": "The year is 2024.",
                    "status": "represented",
                    "candidate_requirements": ["facts.year"],
                },
            ]
        }
        inputs = {
            "facts": {
                "year": 2024,
                "employees": [{"cash_remuneration": None}],
            }
        }

        observed = generate_llm_test._grounding_fidelity(audit, inputs)

        self.assertEqual(observed["status"], "omitted_material_facts")
        self.assertEqual(
            observed["omissions"],
            [
                {
                    "fact": "One worker receives $9,000.",
                    "missing_paths": ["facts.employees[].cash_remuneration"],
                }
            ],
        )

    def test_grounding_fidelity_accepts_false_zero_and_nested_values(self):
        audit = {
            "facts": [
                {
                    "fact": "The amount is zero and the condition is false.",
                    "status": "represented",
                    "candidate_requirements": [
                        "facts.items[].amount",
                        "facts.condition",
                    ],
                }
            ]
        }
        inputs = {"facts": {"items": [{"amount": 0}], "condition": False}}

        observed = generate_llm_test._grounding_fidelity(audit, inputs)

        self.assertEqual(observed, {"status": "faithful", "omissions": []})

    def test_scope_mapping_includes_transitive_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            (snapshot / "law.catala_en").write_text(
                "<!-- rsa-document-id: law/doc -->\n"
                "Rule A.\n"
                "<!-- rsa-block-id: a; role: provision; provision-id: law/a; -->\n"
                "```catala\nscope Leaf:\n definition value equals true\n```\n"
                "Rule B.\n"
                "<!-- rsa-block-id: b; role: provision; provision-id: law/b; -->\n"
                "```catala\nscope Middle:\n definition value equals true\n```\n"
                "```catala\nscope Root:\n definition value equals true\n```\n",
                encoding="utf-8",
            )
            plan = [
                {
                    "id": "law.catala_en::Root",
                    "source": "law.catala_en",
                    "scope": "Root",
                    "dependencies": ["law.catala_en::Middle"],
                },
                {
                    "id": "law.catala_en::Middle",
                    "source": "law.catala_en",
                    "scope": "Middle",
                    "dependencies": ["law.catala_en::Leaf"],
                },
                {
                    "id": "law.catala_en::Leaf",
                    "source": "law.catala_en",
                    "scope": "Leaf",
                    "dependencies": [],
                },
            ]

            observed = generate_llm_test.mapped_provision_ids(
                snapshot,
                {"recursive_repair_plan": plan},
                plan[0],
            )

            self.assertEqual(observed, ["law/b", "law/a"])

    def test_scope_mapping_excludes_unused_dependency_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            (snapshot / "law.catala_en").write_text(
                "```catala-metadata\n"
                "declaration scope Leaf:\n"
                " output used content boolean\n"
                " output unrelated content boolean\n"
                "declaration scope Root:\n"
                " output answer content boolean\n"
                "```\n"
                "<!-- rsa-block-id: a; role: provision; provision-id: law/used; -->\n"
                "```catala\nscope Leaf:\n definition used equals true\n```\n"
                "<!-- rsa-block-id: b; role: provision; provision-id: law/unrelated; -->\n"
                "```catala\nscope Leaf:\n definition unrelated equals true\n```\n"
                "```catala\nscope Root:\n definition answer equals\n"
                "  (output of Leaf with { }).used\n```\n",
                encoding="utf-8",
            )
            plan = [
                {
                    "id": "law.catala_en::Root",
                    "source": "law.catala_en",
                    "scope": "Root",
                    "dependencies": ["law.catala_en::Leaf"],
                },
                {
                    "id": "law.catala_en::Leaf",
                    "source": "law.catala_en",
                    "scope": "Leaf",
                    "dependencies": [],
                },
            ]

            observed = generate_llm_test.mapped_provision_ids(
                snapshot, {"recursive_repair_plan": plan}, plan[0]
            )

            self.assertEqual(observed, ["law/used"])

    def test_statute_context_selects_only_mapped_passages(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "input").mkdir()
            (run / "input/RSA_MANIFEST.json").write_text(
                json.dumps({"documents": [{"path": "law.catala_en"}]}),
                encoding="utf-8",
            )
            (run / "input/law.catala_en").write_text(
                "First rule.\n"
                "<!-- rsa-block-id: a; role: provision; provision-id: law/a; -->\n"
                "```catala\nsecret A\n```\n"
                "Second rule.\n"
                "<!-- rsa-block-id: b; role: provision; provision-id: law/b; -->\n"
                "```catala\nsecret B\n```\n",
                encoding="utf-8",
            )

            context, identifiers = generate_llm_test.statute_context(run, ["law/a"])

            self.assertEqual(identifiers, ["law/a"])
            self.assertIn("First rule", context)
            self.assertNotIn("Second rule", context)
            self.assertNotIn("secret", context)

    def test_designer_prompt_is_sealed_from_implementation(self):
        prompt = generate_llm_test._generation_prompt("[law/a] Rule text.", 3)

        self.assertIn("Rule text", prompt)
        self.assertIn("Generate exactly 3", prompt)
        self.assertNotIn("JSON schema", prompt)
        self.assertNotIn("BOBCat", prompt)
        self.assertNotIn("Catala", prompt)

    def test_generation_schema_requires_the_full_candidate_budget(self):
        cases = generate_llm_test._generation_schema(7, ["law/a"])["properties"][
            "cases"
        ]
        self.assertEqual(cases["minItems"], 7)
        self.assertEqual(cases["maxItems"], 7)

    def test_diverse_selection_prioritizes_new_provisions(self):
        def case(identifier, *provisions):
            return {
                "id": identifier,
                "generated_reasoning_tree": {
                    "steps": [
                        {"provision": provision} for provision in provisions
                    ]
                },
            }

        selected = generate_llm_test._select_diverse_executable(
            [
                case("narrow", "law/a"),
                case("broad", "law/a", "law/b"),
                case("novel", "law/c"),
            ],
            2,
        )

        self.assertEqual([item["id"] for item in selected], ["broad", "novel"])

    def test_representability_audit_receives_nl_provisions_for_relevance(self):
        prompt = generate_llm_test._audit_prompt(
            {
                "cases": [
                    {
                        "id": "nl-1",
                        "facts": "The person is unmarried and has never married.",
                        "material_facts": [
                            "The person is unmarried and has never married."
                        ],
                    }
                ]
            },
            {"fields": {"married_at_year_end": "Year-end status."}},
            "[law/a] The rule tests marital status at year end.",
        )

        self.assertIn("The rule tests marital status at year end", prompt)
        self.assertIn("legally relevant", prompt)

    def test_audit_accepts_only_verbatim_additional_narrative_facts(self):
        generated = {
            "cases": [
                {
                    "id": "nl-1",
                    "facts": "The traveler has one bag. There is one check-in location.",
                    "material_facts": ["The traveler has one bag."],
                }
            ]
        }
        base = {
            "id": "nl-1",
            "status": "possible_gap",
            "facts": [
                {
                    "fact": "The traveler has one bag.",
                    "status": "represented",
                    "candidate_requirements": ["bags"],
                    "explanation": "represented",
                },
                {
                    "fact": "There is one check-in location.",
                    "status": "missing",
                    "candidate_requirements": [],
                    "explanation": "missing",
                },
            ],
        }

        self.assertIsNone(generate_llm_test._validate_audit(generated, {"cases": [base]}))
        base["facts"][1]["fact"] = "The trip has a single check-in."
        self.assertIn(
            "paraphrases",
            generate_llm_test._validate_audit(generated, {"cases": [base]}),
        )

    def test_audit_normalization_drops_invented_fact_and_recomputes_status(self):
        generated = {
            "cases": [
                {
                    "id": "nl-1",
                    "facts": "The traveler has one bag.",
                    "material_facts": ["The traveler has one bag."],
                }
            ]
        }
        audit = {
            "cases": [
                {
                    "id": "nl-1",
                    "status": "possible_gap",
                    "facts": [
                        {"fact": "The traveler has one bag.", "status": "represented"},
                        {"fact": "There is one check-in.", "status": "missing"},
                    ],
                }
            ]
        }

        normalized = generate_llm_test._normalize_audit(generated, audit)
        self.assertEqual(normalized["cases"][0]["status"], "representable")
        self.assertEqual(len(normalized["cases"][0]["facts"]), 1)

    def test_generated_case_is_audited_grounded_and_preserves_nl_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            stage = run / "analysis"
            snapshot = stage / "snapshot"
            snapshot.mkdir(parents=True)
            (run / "input").mkdir()
            source = (
                "A person satisfying the condition receives the result.\n"
                "<!-- rsa-block-id: a; role: provision; provision-id: law/a; -->\n"
                "```catala\nscope Answer:\n definition result equals count > 0\n```\n"
            )
            (run / "input/law.catala_en").write_text(source, encoding="utf-8")
            (snapshot / "law.catala_en").write_text(source, encoding="utf-8")
            (run / "input/RSA_MANIFEST.json").write_text(
                json.dumps({"documents": [{"path": "law.catala_en"}]}),
                encoding="utf-8",
            )
            scope = {
                "id": "law.catala_en::Answer",
                "scope": "Answer",
                "source": "law.catala_en",
                "compiler_file": "law.catala_en",
                "dependencies": [],
                "input_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"count": {"type": "integer"}},
                    "required": ["count"],
                },
            }
            generated = {
                "cases": [
                    {
                        "id": "nl-1",
                        "title": "positive condition",
                        "test_purpose": "exercise the stated condition",
                        "facts": "The person has count two.",
                        "material_facts": ["The count is two."],
                        "question": "Does the person receive the result?",
                        "expected_answer": "Yes.",
                        "reasoning_steps": [
                            {
                                "id": 0,
                                "claim": "The condition is satisfied.",
                                "provision": "law/a",
                                "premises": [],
                            }
                        ],
                    }
                ]
            }
            generated_sample = {
                "output_text": json.dumps(generated),
                "raw_response": {},
                "request_id": "generation",
                "usage": {},
            }
            audit = {
                "parsed": {
                    "cases": [
                        {
                            "id": "nl-1",
                            "status": "representable",
                            "facts": [
                                {
                                    "fact": "The count is two.",
                                    "status": "represented",
                                    "candidate_requirements": ["count"],
                                    "explanation": "Exact match.",
                                }
                            ],
                        }
                    ]
                },
                "parse_error": None,
                "raw_response": {},
                "request_id": "audit",
                "usage": {},
            }
            grounding = {
                "parsed": {"count": 2},
                "parse_error": None,
                "raw_response": {},
                "request_id": "grounding",
                "usage": {},
            }
            config = {
                "run_id": "fixture",
                "reasoning_trace": {"provider": "openai", "model": "reasoner"},
                "information_extraction": {
                    "provider": "openai",
                    "model": "extractor",
                },
            }
            state = {
                "_stage_directory": str(stage),
                "recursive_repair_plan": [scope],
            }
            with (
                mock.patch.object(
                    generate_llm_test.generate_llm_trace,
                    "_sample",
                    return_value=generated_sample,
                ),
                mock.patch.object(
                    generate_llm_test,
                    "_call_ie",
                    side_effect=[audit, grounding],
                ),
                mock.patch.object(
                    generate_llm_test.usage_tracking,
                    "api_call",
                    side_effect=lambda _run, _context, _key, invoke: invoke(),
                ),
            ):
                cases = generate_llm_test.augment_tests(
                    run, config, state, scope, [], 1
                )

            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0]["inputs"], {"count": 2})
            self.assertEqual(cases[0]["generated_expected_answer"], "Yes.")
            self.assertEqual(cases[0]["case_origin"], "llm_generated_nl")
            designer_prompt = (
                stage / "tests_llm_generated/designer.prompt.txt"
            ).read_text()
            self.assertNotIn("count", designer_prompt)
            self.assertNotIn("scope Answer", designer_prompt)


if __name__ == "__main__":
    unittest.main()
