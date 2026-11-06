from __future__ import annotations

import json
import hashlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rtdf_formalizer.stages import utils as experiment
from rtdf_formalizer.stages import reasoning_trace_diff_fuzzing as stage
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing import (
    generate_bobcat_test as bobcat_stage,
)
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing import (
    generate_llm_trace as llm_stage,
)
from rtdf_formalizer.bobcat import comparison as comparison_stage
from rtdf_formalizer.bobcat import trace as trace_stage
from rtdf_formalizer.bobcat import compiled_json
from bobcat_scripts.bobcatlib import run as bobcat_run


class PostValidationTest(unittest.TestCase):
    def test_stop_before_reasoning_preserves_resumable_boundary(self):
        config = {"reasoning_trace_diff_fuzzing": {"stop_before_reasoning": True}}
        state = {"completed_stages": ["verification"]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                mock.patch.object(stage, "backfill_options", return_value={}),
                mock.patch.object(stage, "generate_tests", return_value=[]),
                mock.patch.object(stage, "replay_compiled", return_value=[]),
                mock.patch.object(stage, "reason") as reason,
            ):
                stage.run(root, config, state)
                reason.assert_not_called()
            self.assertEqual(state["next_stage"], "reasoning")
            self.assertEqual(
                state["completed_stages"], ["verification", "bobcat", "compiled_replay"]
            )
            self.assertEqual(experiment.load_json(root / "state.json"), state)

    def test_json_comparison_tolerates_only_money_errors_below_one(self):
        schema = {
            "$ref": "#/definitions/Output",
            "definitions": {
                "Output": {
                    "type": "object",
                    "properties": {
                        "amount": {"$ref": "#/definitions/money"},
                        "rate": {"$ref": "#/definitions/decimal"},
                        "nested": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/money"},
                        },
                    },
                    "required": ["amount", "rate", "nested"],
                },
                "money": {"title": "Catala Money", "type": "number"},
                "decimal": {"title": "Catala Decimal", "type": "number"},
            },
        }
        self.assertTrue(
            compiled_json.json_equivalent(
                {"amount": "10.99", "rate": "0.25", "nested": ["5.01"]},
                {"amount": 10, "rate": 0.25, "nested": [5]},
                schema,
            )
        )
        self.assertFalse(
            compiled_json.json_equivalent(
                {"amount": 11, "rate": 0.25, "nested": [5]},
                {"amount": 10, "rate": 0.25, "nested": [5]},
                schema,
            )
        )
        self.assertFalse(
            compiled_json.json_equivalent(
                {"amount": "11.01", "rate": 0.25, "nested": [5]},
                {"amount": 10, "rate": 0.25, "nested": [5]},
                schema,
            )
        )
        self.assertFalse(
            compiled_json.json_equivalent(
                {"amount": 10, "rate": "0.26", "nested": [5]},
                {"amount": 10, "rate": "0.25", "nested": [5]},
                schema,
            )
        )

    def test_compiled_decoder_accepts_empty_scope_input_struct(self):
        schema = {"type": "object", "additionalProperties": False}
        generated = compiled_json.DecoderGenerator({"Fixed_in": schema}).generate(
            [{"$ref": "#/definitions/Fixed_in"}]
        )
        self.assertIn("decode_fixed_in j : Fixed_in.t = ()", generated)

    def test_compiled_decoder_preserves_qualified_ocaml_module_paths(self):
        definitions = {
            "AirlineWorld.Cabin": {
                "type": "string",
                "enum": ["MainCabin", "First"],
            }
        }
        generated = compiled_json.DecoderGenerator(definitions).generate(
            [{"$ref": "#/definitions/AirlineWorld.Cabin"}]
        )
        self.assertIn("decode_airlineWorld_Cabin j : AirlineWorld.Cabin.t", generated)
        self.assertIn("AirlineWorld.Cabin.MainCabin", generated)
        self.assertNotIn("AirlineWorld_Cabin", generated)

    def test_compiled_decoder_wraps_defaulted_scope_inputs_as_optional(self):
        definitions = {
            "Example_in": {
                "type": "object",
                "properties": {
                    "required_count": {"type": "integer"},
                    "default_count": {"type": "integer"},
                    "default_facts": {"$ref": "#/definitions/Facts"},
                },
                "required": ["required_count"],
            },
            "Facts": {
                "type": "object",
                "properties": {
                    "active": {"type": "boolean"},
                    "nickname": {"type": "string"},
                },
                "required": ["active"],
            },
        }
        generated = compiled_json.DecoderGenerator(definitions).generate(
            [{"$ref": "#/definitions/Example_in"}]
        )
        self.assertIn(
            'Example_in.required_count_in = (integer) (field "required_count" j);',
            generated,
        )
        self.assertIn(
            'Example_in.default_count_in = optional_field (integer) "default_count" j;',
            generated,
        )
        self.assertIn(
            'Example_in.default_facts_in = optional_field (decode_facts) "default_facts" j;',
            generated,
        )
        self.assertIn('Facts.active = (boolean) (field "active" j);', generated)
        self.assertNotIn("optional_field (boolean)", generated)
        self.assertIn(
            'Facts.nickname = optional_value_field (text) "nickname" j;', generated
        )

        generated = compiled_json.DecoderGenerator(
            definitions, {"default_count_in"}
        ).generate([{"$ref": "#/definitions/Example_in"}])
        self.assertIn(
            'Example_in.default_count_in = optional_value_field (integer) "default_count" j;',
            generated,
        )

    def test_optional_field_helper_treats_missing_and_null_as_absent(self):
        self.assertIn(
            "| None | Some `Null -> Catala_runtime.Optional.Absent",
            compiled_json.HELPERS,
        )
        self.assertIn(
            "Catala_runtime.Optional.Present\n             (decoder value, bridge_input_location)",
            compiled_json.HELPERS,
        )
        self.assertIn(
            "Catala_runtime.Optional.Present (decoder value)",
            compiled_json.HELPERS,
        )

    def test_compiled_bridge_parenthesizes_let_valued_record_field(self):
        generated = (
            "  {Outer.zero = false;\n"
            "   Outer.first =\n"
            "     let value = inner () in\n"
            "     {Inner.answer = value};\n"
            "   Outer.second = true}\n"
        )
        repaired = compiled_json._parenthesize_record_field_lets(generated)
        self.assertIn("     (let value = inner () in", repaired)
        self.assertIn("     {Inner.answer = value});", repaired)

    def test_compiled_bridge_traces_only_selected_constant_arm(self):
        source = (
            "<!-- rtdf-block-id: b1; provision-id: law/fee; -->\n"
            "```catala\n"
            "declaration domestic_first_fee content money equals $40\n"
            "```\n"
        )
        generated = (
            "let domestic_first_fee : money = integer_of_int 4000\n"
            "let first_fee = if domestic then domestic_first_fee else nearby_first_fee\n"
        )
        traced = compiled_json._trace_conditional_constant_reads(
            generated, source, "fees.catala_en"
        )
        self.assertIn("then (let _ = log_decision_taken ", traced)
        self.assertIn('filename = "../fees.catala_en"', traced)
        self.assertIn("start_line=3", traced)
        self.assertIn("true in domestic_first_fee)", traced)
        self.assertIn("else nearby_first_fee", traced)

    def test_compiled_bridge_wraps_helpers_but_not_scopes_or_constants(self):
        generated = (
            "(* Toplevel def fee *)\n"
            "let fee : integer -> integer =\n"
            "  fun (x: integer) ->\n"
            "    x\n\n"
            "(* Toplevel def countries *)\n"
            "let countries : integer array =\n"
            "  [|integer_of_int 1|]\n\n"
            "(* Scope Answer *)\n"
            "let answer : Answer_in.t -> Answer.t = fun answer_in ->\n"
            "  answer_in\n"
        )
        traced = compiled_json._trace_generated_function_calls(
            generated, "law.catala_en"
        )
        self.assertIn('log_runtime_call "law.catala_en::fee" (fun () ->', traced)
        self.assertNotIn("law.catala_en::Answer", traced)
        self.assertNotIn("law.catala_en::countries", traced)

    def test_compiled_bridge_qualifies_native_nested_scope_calls(self):
        generated = (
            'ignore (log_begin_call ["Helper"; "direct"] ());\n'
            'log_end_call ["Helper"; "direct"] result\n'
        )
        traced = compiled_json._qualify_generated_scope_calls(
            generated, "nested/law.catala_en"
        )
        self.assertIn('log_begin_call ["law.catala_en::Helper"]', traced)
        self.assertIn('log_end_call ["law.catala_en::Helper"]', traced)
        self.assertNotIn('"direct"', traced)

    def test_compiled_bridge_records_helper_return_dependencies(self):
        generated = (
            "open Catala_runtime\n"
            "(* Toplevel def fee *)\n"
            "let fee : integer -> integer = fun x ->\n"
            "  x\n"
        )
        traced = compiled_json._instrument_trace_source(generated, "", "law.catala_en")
        self.assertIn('let token = "$call-return:" ^ name', traced)
        self.assertIn(
            'log_variable_definition_with_reads token [name; "$return"]', traced
        )
        self.assertIn("Value.embed Value.Polymorphic value", traced)
        self.assertIn("log_variable_read token value", traced)

    def test_statute_labels_precede_the_prose_they_identify(self):
        prose = (
            "<!-- rtdf-document-id: law -->\n"
            "### Something\n(a) something\n"
            "<!-- rtdf-block-id: b1; role: provision; provision-id: law/tag1; source-lines: 1-2; relation: formalizes-preceding -->\n"
            "(b) something else\n"
            "<!-- rtdf-block-id: b2; role: provision; provision-id: law/tag2; source-lines: 3-3; relation: formalizes-preceding -->\n"
        )
        self.assertEqual(
            llm_stage._labeled_statute_prose(prose),
            "[law/tag1] ### Something\n(a) something\n\n[law/tag2] (b) something else",
        )

    def test_statute_rendering_labels_every_stored_provision_marker(self):
        prose = (
            "Parent rule\n"
            "<!-- rtdf-block-id: b1; role: provision; provision-id: law(a); source-lines: 1-1; relation: formalizes-preceding -->\n"
            "Child one\n"
            "<!-- rtdf-block-id: b2; role: provision; provision-id: law(a)(i); source-lines: 2-2; relation: formalizes-preceding -->\n"
            "Child two\n"
            "<!-- rtdf-block-id: b3; role: provision; provision-id: law(a)(ii); source-lines: 3-3; relation: formalizes-preceding -->\n"
            "Closing text\n"
            "<!-- rtdf-block-id: b4; role: provision; provision-id: law(a):closing; source-lines: 4-4; relation: formalizes-preceding -->\n"
        )
        rendered = llm_stage._labeled_statute_prose(prose)
        self.assertIn("Parent rule", rendered)
        self.assertIn("Closing text", rendered)
        self.assertIn("[law(a)] Parent rule", rendered)
        self.assertIn("[law(a):closing] Closing text", rendered)
        self.assertIn("[law(a)(i)] Child one", rendered)
        self.assertIn("[law(a)(ii)] Child two", rendered)
        self.assertEqual(
            llm_stage._allowed_provision_ids(rendered),
            ["law(a)", "law(a)(i)", "law(a)(ii)", "law(a):closing"],
        )

    def test_prompt_requests_a_json_step_by_step_solution(self):
        schema = {
            "$ref": "#/definitions/Answer",
            "definitions": {
                "Answer": {
                    "type": "object",
                    "properties": {
                        "eligible": {"type": "boolean"},
                        "items": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["eligible", "items"],
                }
            },
        }
        prompt = llm_stage._prompt(
            "[airline/law:a] Law text.",
            {"target": "Decide", "requirement_id": "AIRLINE-FEE", "inputs": {"x": 1}},
            schema,
            dataset="airline",
            requirement_description="calculate the passenger fee",
        )
        self.assertIn(
            "Calculate these values under the supplied statutes:\n"
            "- eligible: calculate the passenger fee\n"
            "- items: calculate the passenger fee\n",
            prompt,
        )
        self.assertIn(
            "Give a step-by-step solution that traces the concrete value flow", prompt
        )
        self.assertIn(
            "Use only the supplied statutes and their local semantics", prompt
        )
        self.assertIn(
            "Do not discuss alternative filing statuses, untaken branches", prompt
        )
        self.assertTrue(prompt.startswith("Statutes:\n[law:a] Law text."))
        self.assertNotIn("airline/", prompt)
        self.assertLess(
            prompt.index("Statutes:"), prompt.index("The case is as follows")
        )
        self.assertIn(
            "Produce your final answer in the question-specific JSON format", prompt
        )
        self.assertIn("Dependencies include legal or control dependencies", prompt)
        self.assertIn("even when the conclusion supplies no numeric operand", prompt)
        self.assertIn("emit exactly one literal <answer> opening tag", prompt)
        self.assertIn("Do not use Markdown code fences anywhere", prompt)
        self.assertIn("Do not write anything after the closing tag", prompt)
        self.assertIn(
            "Do not emit JSON for the steps, citation lists, premise IDs", prompt
        )
        self.assertIn(
            "Show all arithmetic needed to reproduce the final result", prompt
        )
        self.assertIn("unquoted JSON numbers and booleans", prompt)
        self.assertIn(
            '<answer>\n{\n  "eligible": "<boolean>",\n  "items": [\n'
            '    "<integer>"\n  ]\n}\n</answer>',
            prompt,
        )
        self.assertNotIn("final_answer", prompt)
        self.assertNotIn("reasoning_trace", prompt)
        self.assertNotIn('"$ref"', prompt)
        self.assertNotIn('"$schema"', prompt)

    def test_answer_example_preserves_nested_objects_and_complex_lists(self):
        schema = {
            "$ref": "#/definitions/Answer",
            "definitions": {
                "Answer": {
                    "type": "object",
                    "properties": {
                        "history": {"$ref": "#/definitions/History"},
                        "rows": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/Row"},
                        },
                    },
                    "required": ["history", "rows"],
                },
                "History": {
                    "type": "object",
                    "properties": {
                        "employee_ids": {"type": "array", "items": {"type": "integer"}}
                    },
                    "required": ["employee_ids"],
                },
                "Row": {
                    "type": "object",
                    "properties": {
                        "accepted": {"type": "boolean"},
                        "amount": {"type": "number"},
                    },
                    "required": ["accepted", "amount"],
                },
            },
        }
        self.assertEqual(
            llm_stage._answer_example(schema),
            {
                "history": {"employee_ids": ["<integer>"]},
                "rows": [{"accepted": "<boolean>", "amount": "<number>"}],
            },
        )

    def test_final_answer_parser_requires_one_parseable_tagged_json_value(self):
        value, error = llm_stage.parse_final_answer(
            'Reasoning first.\n<answer>{"ids": [1, 2], "ok": true}</answer>'
        )
        self.assertIsNone(error)
        self.assertEqual(value, {"ids": [1, 2], "ok": True})
        self.assertIsNotNone(llm_stage.parse_final_answer('{"ok": true}')[1])
        self.assertIsNotNone(llm_stage.parse_final_answer("<answer>{bad}</answer>")[1])

    def test_optional_catala_values_project_to_the_prompt_schema(self):
        schema = {
            "type": "object",
            "properties": {
                "total": {"type": "number"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"amount": {"type": "number"}},
                        "required": ["amount"],
                    },
                },
            },
            "required": ["items"],
        }
        self.assertEqual(
            llm_stage._answer_example(schema),
            {
                "total": "<number; optional—omit property if absent>",
                "items": [{"amount": "<number>"}],
            },
        )
        self.assertEqual(
            compiled_json.project_output_json(
                {"total": {"Present": 3}, "items": [{"amount": 4}]}, schema
            ),
            {"total": 3, "items": [{"amount": 4}]},
        )
        self.assertEqual(
            compiled_json.project_output_json({"total": "Absent", "items": []}, schema),
            {"items": []},
        )

    def test_execution_tree_schema_constrains_provisions(self):
        schema = llm_stage._execution_tree_schema(["law/a", "law/b"])
        provision = schema["properties"]["steps"]["items"]["properties"]["provision"]
        self.assertEqual(provision["anyOf"][0]["enum"], ["law/a", "law/b"])
        self.assertEqual(provision["anyOf"][1], {"type": "null"})
        self.assertFalse(schema["additionalProperties"])

    def test_execution_tree_validation_requires_topological_contiguous_ids(self):
        valid = {
            "steps": [
                {"id": 0, "claim": "Income is 10.", "provision": None, "premises": []},
                {"id": 1, "claim": "Tax is 1.", "provision": "law/a", "premises": [0]},
            ]
        }
        self.assertIsNone(llm_stage._validate_execution_tree(valid, {"law/a"}))
        invalid = {
            "steps": [
                valid["steps"][0],
                {"id": 2, "claim": "Tax is 1.", "provision": "law/a", "premises": [0]},
            ]
        }
        self.assertIn(
            "must equal 1", llm_stage._validate_execution_tree(invalid, {"law/a"})
        )

    def test_execution_tree_prompt_omits_answer_and_lists_allowed_provisions(self):
        candidate = '1. Income is 10.\n<answer>\n{"total": 1}\n</answer>'
        prose = llm_stage._reasoning_without_answer(candidate)
        prompt = llm_stage._execution_tree_prompt(prose, ["law/a"])
        self.assertNotIn("<answer>", prompt)
        self.assertIn('"law/a"', prompt)
        self.assertIn("Every premise ID must be smaller", prompt)
        self.assertIn("Premises include legal or control dependencies", prompt)
        self.assertIn("Each must have a directed path to the final-result step", prompt)
        self.assertIn("Omit rejected alternatives and negative conclusions", prompt)

    def test_reasoning_prompt_requests_the_most_specific_provision(self):
        prompt = llm_stage._prompt(
            "[law(a)] Parent.\n[law(a)(i)] Child.",
            {"inputs": {}, "target": "Answer"},
            {
                "type": "object",
                "properties": {"total": {"type": "number"}},
                "required": ["total"],
            },
        )
        self.assertIn("Only identifiers shown in square brackets", prompt)
        self.assertIn("cite its labeled leaf provision", prompt)
        self.assertIn("ancestor text remains part of the rule context", prompt)

    def test_provision_overlap_accepts_only_exact_or_ancestor_ids(self):
        self.assertTrue(
            trace_stage.provision_ids_overlap("section1(a)", "section1(a)(ii)")
        )
        self.assertTrue(
            trace_stage.provision_ids_overlap("section1(a)(ii)", "section1(a)")
        )
        self.assertTrue(
            trace_stage.provision_ids_overlap("section1(a)(ii)", "section1(a)(ii)")
        )
        self.assertFalse(
            trace_stage.provision_ids_overlap("section1(a)(2)", "section1(a)(ii)")
        )
        self.assertFalse(
            trace_stage.provision_ids_overlap("section1(a)(i)", "section1(a)(ii)")
        )
        self.assertFalse(
            trace_stage.provision_ids_overlap("section1(a)", "section1(ab)")
        )

    def test_provision_overlap_ignores_dataset_namespace(self):
        self.assertTrue(
            trace_stage.provision_ids_overlap("sara/section1(a)(ii)", "section1(a)(ii)")
        )
        self.assertTrue(
            trace_stage.provision_ids_overlap("sara/section1(a)", "section1(a)(ii)")
        )
        self.assertFalse(
            trace_stage.provision_ids_overlap("sara/section1(a)(2)", "section1(a)(ii)")
        )

    def test_provision_comparison_auto_matches_parent_and_child(self):
        self.assertEqual(
            trace_stage.compare_provision_ids(["section1(a)"], ["section1(a)(ii)"]),
            {
                "overlaps": [{"catala": "section1(a)", "llm": "section1(a)(ii)"}],
                "catala_only": [],
                "llm_only": [],
            },
        )

    def test_provision_comparison_ignores_dataset_namespace(self):
        self.assertEqual(
            trace_stage.compare_provision_ids(
                ["sara/section1(a)", "sara/section1(a)(ii)"], ["section1(a)(ii)"]
            ),
            {
                "overlaps": [
                    {
                        "catala": "sara/section1(a)(ii)",
                        "llm": "section1(a)(ii)",
                    }
                ],
                "catala_only": [],
                "llm_only": [],
            },
        )

    def test_provision_comparison_does_not_mask_sibling_conflict_with_parent(self):
        self.assertEqual(
            trace_stage.compare_provision_ids(
                ["section1(a)", "section1(a)(ii)"], ["section1(a)", "section1(a)(2)"]
            ),
            {
                "overlaps": [],
                "catala_only": ["section1(a)(ii)"],
                "llm_only": ["section1(a)(2)"],
            },
        )

    def test_anthropic_capture_keeps_reasoning_blocks_and_usage(self):
        raw = {
            "id": "msg-1",
            "content": [
                {"type": "thinking", "thinking": "visible trace"},
                {"type": "text", "text": "step-by-step answer"},
            ],
            "usage": {"input_tokens": 8, "output_tokens": 4},
        }
        response = io.BytesIO(json.dumps(raw).encode())
        with (
            mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            mock.patch.object(
                llm_stage.urllib.request, "urlopen", return_value=response
            ) as sent,
        ):
            observed = llm_stage._sample(
                {"reasoning_trace": {"provider": "anthropic", "model": "example"}},
                "test prompt",
            )
        self.assertEqual(
            observed["raw_response"]["content"][0]["thinking"], "visible trace"
        )
        self.assertEqual(observed["usage"]["input_tokens"], 8)
        payload = json.loads(sent.call_args.args[0].data)
        self.assertNotIn("output_config", payload)

    def test_claude_code_capture_uses_pinned_model_and_usage(self):
        raw = {
            "session_id": "session-1",
            "result": "step-by-step answer",
            "usage": {"input_tokens": 8, "output_tokens": 4},
        }
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(raw), stderr=""
        )
        with mock.patch.object(
            llm_stage.subprocess, "run", return_value=completed
        ) as sent:
            observed = llm_stage._sample(
                {
                    "reasoning_trace": {
                        "provider": "claude-code",
                        "model": "claude-sonnet-5-5",
                    }
                },
                "test prompt",
            )
        self.assertEqual(observed["output_text"], "step-by-step answer")
        self.assertEqual(observed["request_id"], "session-1")
        self.assertEqual(observed["usage"]["input_tokens"], 8)
        self.assertIn("claude-sonnet-5-5", sent.call_args.args[0])
        self.assertEqual(sent.call_args.kwargs["input"], "test prompt")

    def test_claude_code_provider_error_raises_with_structured_result(self):
        raw = {
            "session_id": "session-1",
            "result": "You've hit your session limit · resets 9:50pm (America/Chicago)",
            "is_error": True,
            "api_error_status": 429,
            "usage": {},
        }
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=json.dumps(raw),
            stderr='[claude-code:unrecognized_model] {"model":"claude-sonnet-5-5"}',
        )
        with mock.patch.object(llm_stage.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(
                experiment.RunnerError, "session limit"
            ) as raised:
                llm_stage._sample(
                    {
                        "reasoning_trace": {
                            "provider": "claude-code",
                            "model": "claude-sonnet-5-5",
                        }
                    },
                    "test prompt",
                )
        self.assertNotIn("unrecognized_model", str(raised.exception))

    def test_openai_request_uses_free_text_output(self):
        output = mock.Mock(output_text="step-by-step answer")
        output.model_dump.return_value = {"id": "response-1", "usage": {}}
        with mock.patch("openai.OpenAI") as client_class:
            client_class.return_value.responses.create.return_value = output
            llm_stage._sample(
                {"reasoning_trace": {"provider": "openai", "model": "example"}},
                "question",
            )
        kwargs = client_class.return_value.responses.create.call_args.kwargs
        self.assertNotIn("text", kwargs)

    def test_openai_execution_tree_request_uses_strict_schema(self):
        output = mock.Mock(output_text='{"steps": []}')
        output.model_dump.return_value = {"id": "response-1", "usage": {}}
        schema = llm_stage._execution_tree_schema(["law/a"])
        with mock.patch("openai.OpenAI") as client_class:
            client_class.return_value.responses.create.return_value = output
            llm_stage._sample(
                {"reasoning_trace": {"provider": "openai", "model": "example"}},
                "extract",
                schema,
            )
        kwargs = client_class.return_value.responses.create.call_args.kwargs
        self.assertTrue(kwargs["text"]["format"]["strict"])
        self.assertEqual(kwargs["text"]["format"]["schema"], schema)

    def test_compatible_provider_requests_free_text_output(self):
        choice = mock.Mock()
        choice.message.content = "step-by-step answer"
        output = mock.Mock(choices=[choice])
        output.model_dump.return_value = {"id": "completion-1", "usage": {}}
        with mock.patch("openai.OpenAI") as client_class:
            client_class.return_value.chat.completions.create.return_value = output
            llm_stage._sample(
                {
                    "reasoning_trace": {
                        "provider": "compatible",
                        "model": "example",
                        "base_url": "https://example.test/v1",
                    }
                },
                "question",
            )
        kwargs = client_class.return_value.chat.completions.create.call_args.kwargs
        self.assertNotIn("response_format", kwargs)

    def test_private_scope_runs_as_traced_compiled_ocaml(self):
        source = (
            experiment.ROOT
            / "bobcat_scripts/tests/fixtures"
            / "goal_directed_unsat.catala_en"
        )
        environment = experiment.toolchain_environment({"runtime": {}})
        if not source.is_file() or any(
            shutil.which(name, path=environment["PATH"]) is None
            for name in ("catala", "clerk", "ocamlfind", "ocamlobjinfo")
        ):
            self.skipTest("compiled Catala toolchain is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            shutil.copy2(source, project / source.name)
            formats = experiment.extract_input_formats(
                project, environment=environment, timeout=60
            )
            errors = compiled_json.build_bridges(
                project,
                formats,
                environment=environment,
                timeout=60,
                selected={(source.name, "GoalDirected")},
            )
            self.assertEqual(errors, {})
            executable = compiled_json.compiled_path(
                project, source.name, "GoalDirected"
            )
            completed = subprocess.run(
                [str(executable), "GoalDirected", "--trace"],
                input='{"x": false}\n',
                text=True,
                capture_output=True,
                cwd=project,
                env=environment,
                timeout=10,
                check=True,
            )
            observed = json.loads(completed.stdout)
            self.assertEqual(observed["result"], {"result": "3"})
            branches = [
                event
                for event in observed["events"]
                if event["event"] == "BranchTaken"
            ]
            self.assertEqual(len(branches), 1)
            self.assertEqual(branches[0]["outcome"], False)
            tree = trace_stage.execution_tree(observed["events"])
            self.assertEqual(tree[0]["kind"], "call")
            self.assertTrue(
                any(
                    event["event"] == "DecisionTaken"
                    for event in trace_stage.execution_tree_events(tree)
                )
            )
            self.assertTrue(
                any(
                    event["event"] == "BranchTaken"
                    for event in trace_stage.execution_tree_events(tree)
                )
            )

    def test_execution_tree_deduplicates_list_calls_and_slices_at_output(self):
        position = {"filename": "law.catala_en", "start_line": 7}
        events = [
            {"event": "BeginCall", "name": "Answer"},
            {"event": "DecisionTaken", "pos": position},
            {"event": "BeginCall", "name": "item"},
            {"event": "EndCall", "name": "item"},
            {"event": "BeginCall", "name": "item"},
            {"event": "EndCall", "name": "item"},
            {
                "event": "VariableDefinition",
                "name": "Answer.total",
                "io": {"io_output": True},
                "value": "3",
            },
            {"event": "DecisionTaken", "pos": {**position, "start_line": 9}},
            {
                "event": "VariableDefinition",
                "name": "Answer.unused",
                "io": {"io_output": True},
                "value": "0",
            },
            {"event": "EndCall", "name": "Answer"},
        ]
        for identifier, event in enumerate(
            e for e in events if e["event"] == "VariableDefinition"
        ):
            event.update(definition_id=identifier, reads=[])
        tree = trace_stage.execution_tree(events)
        item = next(node for node in tree[0]["children"] if node.get("name") == "item")
        self.assertEqual(item["occurrences"], 2)
        sliced = trace_stage.slice_execution_tree(
            trace_stage.execution_tree(events, deduplicate=False),
            "Answer",
            "total",
            {"Answer": {"total": set(), "unused": set()}},
        )
        self.assertEqual(sliced[0]["children"][-1]["name"], "Answer.total")
        self.assertNotIn("Answer.unused", json.dumps(sliced))

        whole_scope = trace_stage.slice_execution_tree(
            trace_stage.execution_tree(events, deduplicate=False), "Answer", None
        )
        self.assertIn("Answer.total", json.dumps(whole_scope))
        self.assertIn("Answer.unused", json.dumps(whole_scope))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace_stage.persist_execution_forests(
                root,
                [
                    {
                        "execution_tree": tree,
                        "dynamic_slice_tree": sliced,
                    }
                ],
            )
            complete = json.loads((root / "execution_tree.json").read_text())
            dynamic = json.loads((root / "dynamic_slice_tree.json").read_text())
            self.assertIn("Answer.unused", json.dumps(complete))
            self.assertNotIn("Answer.unused", json.dumps(dynamic))

    def test_causal_execution_trace_attaches_branch_guards(self):
        events = [
            {"event": "BeginCall", "name": "Answer"},
            {
                "event": "BranchTaken",
                "pos": {
                    "filename": "../law.catala_en",
                    "start_line": 3,
                    "start_column": 8,
                    "end_line": 3,
                    "end_column": 16,
                },
                "outcome": False,
            },
            {
                "event": "VariableDefinition",
                "name": "Answer.choice",
                "io": {"io_output": False},
                "value": 0,
                "definition_id": 0,
                "reads": [],
            },
            {
                "event": "VariableDefinition",
                "name": "Answer.total",
                "io": {"io_output": True},
                "value": 0,
                "definition_id": 1,
                "reads": [{"definition_id": 0}],
            },
            {"event": "EndCall", "name": "Answer"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "law.catala_en").write_text(
                "scope Answer:\n  definition choice equals\n    if eligible then 1 else 0\n",
                encoding="utf-8",
            )
            tree = trace_stage.execution_tree(events, deduplicate=False)
            causal = trace_stage.causal_execution_trace(root, tree)
        self.assertEqual(causal[0]["branch_guards"][0]["condition"], "eligible")
        self.assertEqual(causal[0]["branch_guards"][0]["outcome"], False)
        self.assertEqual(causal[0]["branch_guards"][0]["selected_arm"], "else")
        self.assertEqual(causal[0]["branch_guards"][0]["relation"], "direct")
        self.assertEqual(causal[1]["branch_guards"][0]["relation"], "inherited")
        replayed = trace_stage.execution_tree_events(tree)
        self.assertIn("BranchTaken", {event["event"] for event in replayed})

    def test_dynamic_slice_follows_dependencies_not_execution_prefix(self):
        events = [
            {"event": "BeginCall", "name": "Answer"},
            {
                "event": "VariableDefinition",
                "name": "Answer.input",
                "io": {"io_output": False},
                "value": 1,
            },
            {"event": "DecisionTaken", "pos": {"start_line": 2}},
            {
                "event": "VariableDefinition",
                "name": "Answer.unrelated",
                "io": {"io_output": False},
                "value": 2,
            },
            {"event": "DecisionTaken", "pos": {"start_line": 3}},
            {
                "event": "VariableDefinition",
                "name": "Answer.total",
                "io": {"io_output": True},
                "value": 1,
            },
            {"event": "EndCall", "name": "Answer"},
        ]
        variables = [
            event for event in events if event["event"] == "VariableDefinition"
        ]
        for identifier, event in enumerate(variables):
            event.update(definition_id=identifier, reads=[])
        variables[-1]["reads"] = [{"definition_id": 0}]
        tree = trace_stage.execution_tree(events, deduplicate=False)
        sliced = trace_stage.slice_execution_tree(
            tree,
            "Answer",
            "total",
            {
                "Answer": {"input": set(), "unrelated": set(), "total": {"input"}},
            },
        )
        rendered = json.dumps(sliced)
        self.assertIn("Answer.input", rendered)
        self.assertIn("Answer.total", rendered)
        self.assertNotIn("Answer.unrelated", rendered)
        self.assertNotIn('"start_line": 2', rendered)
        self.assertIn('"start_line": 3', rendered)

    def test_dynamic_slice_recursively_prunes_calls_owned_by_live_definition(self):
        events = [
            {"event": "BeginCall", "name": "Answer"},
            {"event": "BeginCall", "name": "law.catala_en::unused_helper"},
            {"event": "EndCall", "name": "law.catala_en::unused_helper"},
            {
                "event": "VariableDefinition",
                "name": "Answer.unused",
                "definition_id": 0,
                "reads": [],
                "value": 0,
            },
            {"event": "BeginCall", "name": "law.catala_en::outer"},
            {"event": "BeginCall", "name": "law.catala_en::inner"},
            {"event": "EndCall", "name": "law.catala_en::inner"},
            {"event": "EndCall", "name": "law.catala_en::outer"},
            {
                "event": "VariableDefinition",
                "name": "Answer.total",
                "definition_id": 1,
                "reads": [],
                "value": 1,
            },
            {"event": "EndCall", "name": "Answer"},
        ]
        sliced = trace_stage.slice_execution_tree(
            trace_stage.execution_tree(events, deduplicate=False), "Answer", "total"
        )
        rendered = json.dumps(sliced)
        self.assertNotIn("unused_helper", rendered)
        self.assertIn("law.catala_en::outer", rendered)
        self.assertNotIn("law.catala_en::inner", rendered)

    def test_dynamic_slice_follows_explicit_helper_returns(self):
        tree = [
            {
                "kind": "call",
                "name": "Answer",
                "children": [
                    {
                        "kind": "call",
                        "name": "law.catala_en::outer",
                        "children": [
                            {
                                "kind": "call",
                                "name": "law.catala_en::inner",
                                "children": [
                                    {
                                        "kind": "variable",
                                        "name": "Inner.unused",
                                        "definition_id": 0,
                                        "reads": [],
                                        "children": [],
                                    },
                                    {
                                        "kind": "variable",
                                        "name": "law.catala_en::inner.$return",
                                        "definition_id": 1,
                                        "reads": [],
                                        "children": [],
                                    },
                                ],
                            },
                            {
                                "kind": "variable",
                                "name": "law.catala_en::outer.$return",
                                "definition_id": 2,
                                "reads": [{"definition_id": 1}],
                                "children": [],
                            },
                        ],
                    },
                    {
                        "kind": "variable",
                        "name": "Answer.total",
                        "definition_id": 3,
                        "reads": [{"definition_id": 2}],
                        "children": [],
                    },
                ],
            }
        ]
        sliced = trace_stage.slice_execution_tree(tree, "Answer", "total")
        rendered = json.dumps(sliced)
        self.assertIn("law.catala_en::outer", rendered)
        self.assertIn("law.catala_en::inner", rendered)
        self.assertIn("inner.$return", rendered)
        self.assertNotIn("Inner.unused", rendered)

    def test_helper_call_projects_to_annotated_provision(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            (snapshot / "law.catala_en").write_text(
                "<!-- rtdf-block-id: b1; role: provision; provision-id: law/p1; "
                "source-lines: 1-1; relation: formalizes-preceding -->\n"
                "```catala-metadata\n"
                "declaration fee content integer\n"
                "  depends on x content integer\n"
                "  equals x\n"
                "```\n",
                encoding="utf-8",
            )
            tree = [{"kind": "call", "name": "law.catala_en::fee", "children": []}]
            self.assertEqual(
                trace_stage.execution_statute_tree(snapshot, tree), ["law/p1"]
            )

    def test_dynamic_slice_uses_runtime_dependencies_despite_static_overapproximation(
        self,
    ):
        events = [
            {"event": "BeginCall", "name": "Answer"},
            {
                "event": "VariableDefinition",
                "name": "Nested.kept",
                "definition_id": 1,
                "reads": [],
                "io": {"io_output": True},
                "value": 10,
            },
            {
                "event": "VariableDefinition",
                "name": "Nested.untaken",
                "definition_id": 2,
                "reads": [],
                "io": {"io_output": True},
                "value": 20,
            },
            {
                "event": "VariableDefinition",
                "name": "Answer.result",
                "definition_id": 3,
                "reads": [{"definition_id": 1}],
                "io": {"io_output": False},
                "value": {},
            },
            {"event": "DecisionTaken", "pos": {"start_line": 7}},
            {
                "event": "VariableDefinition",
                "name": "Answer.total",
                "definition_id": 4,
                "reads": [{"definition_id": 3, "field": "kept"}],
                "io": {"io_output": True},
                "value": 10,
            },
            {"event": "EndCall", "name": "Answer"},
        ]
        tree = trace_stage.execution_tree(events, deduplicate=False)
        sliced = trace_stage.slice_execution_tree(
            tree,
            "Answer",
            "total",
            {
                # The static graph deliberately over-approximates both fields.
                "Answer": {"total": {"result"}, "result": set()},
            },
        )
        rendered = json.dumps(sliced)
        self.assertIn("Nested.kept", rendered)
        self.assertIn("Answer.result", rendered)
        self.assertIn("Answer.total", rendered)
        self.assertNotIn("Nested.untaken", rendered)
        self.assertIn('"kind": "decision"', rendered)

    def test_dependency_edges_reverse_compiler_edges(self):
        self.assertEqual(
            trace_stage.dependency_edges(
                {
                    "intra_scopes": {
                        "Answer": {
                            "nodes": {"1": "input", "2": "total", "3": "unused"},
                            "edges": [{"from": 1, "to": 2}],
                        },
                    }
                }
            ),
            {
                "Answer": {
                    "input": set(),
                    "total": {"input"},
                    "unused": set(),
                }
            },
        )

    def test_execution_statute_tree_collapses_only_adjacent_equal_leaves(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            (snapshot / "law.catala_en").write_text(
                "<!-- rtdf-block-id: a; role: provision; provision-id: law/a; "
                "source-lines: 1-1; relation: formalizes-preceding -->\n"
                "```catala\nscope Answer:\n  definition amount equals 5\n```\n",
                encoding="utf-8",
            )
            position = {"filename": "law.catala_en", "start_line": 3}
            tree = [
                {
                    "kind": "call",
                    "children": [
                        {
                            "kind": "decision",
                            "pos": position,
                            "children": [],
                            "occurrences": 2,
                        },
                        {"kind": "decision", "pos": position, "children": []},
                    ],
                }
            ]
            self.assertEqual(
                trace_stage.execution_statute_tree(snapshot, tree),
                [
                    {
                        "children": ["law/a"],
                    }
                ],
            )
            separator = {"children": ["law/b"]}
            self.assertEqual(
                trace_stage._collapse_adjacent_statute_leaves(
                    ["law/a", "law/a", separator, "law/a", "law/a"]
                ),
                ["law/a", separator, "law/a"],
            )

    def test_compiled_bridge_runs_with_defaulted_context_and_enum_output(self):
        environment = experiment.toolchain_environment({"runtime": {}})
        if any(
            shutil.which(name, path=environment["PATH"]) is None
            for name in ("catala", "clerk", "ocamlfind", "ocamlobjinfo")
        ):
            self.skipTest("compiled Catala toolchain is unavailable")
        source_text = """\
```catala
declaration enumeration Choice:
  -- First
  -- Second

declaration scope Defaulted:
  context choose_first content boolean
  output choice content Choice
  output is_second content boolean

scope Defaulted:
  definition choose_first equals false
  definition choice equals if choose_first then First else Second
  definition is_second equals choice = Second
```
"""
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / "defaulted.catala_en"
            source.write_text(source_text, encoding="utf-8")
            formats = experiment.extract_input_formats(
                project, environment=environment, timeout=60
            )
            scope = next(
                item for item in formats["scopes"] if item["scope"] == "Defaulted"
            )
            input_definition = scope["input_schema"]["definitions"]["Defaulted_in"]
            self.assertNotIn("choose_first", input_definition.get("required", []))
            errors = compiled_json.build_bridges(
                project,
                formats,
                environment=environment,
                timeout=60,
                selected={(source.name, "Defaulted")},
            )
            self.assertEqual(errors, {})
            executable = compiled_json.compiled_path(project, source.name, "Defaulted")
            for inputs, expected in (
                ({}, {"choice": "Second", "is_second": True}),
                ({"choose_first": True}, {"choice": "First", "is_second": False}),
            ):
                completed = subprocess.run(
                    [str(executable), "Defaulted"],
                    input=json.dumps(inputs) + "\n",
                    text=True,
                    capture_output=True,
                    cwd=project,
                    env=environment,
                    timeout=10,
                    check=True,
                )
                self.assertEqual(json.loads(completed.stdout), expected)

    def test_generation_excludes_scopes_with_empty_input_or_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "iterations/000/snapshot"
            snapshot.mkdir(parents=True)
            (snapshot / "program.catala_en").write_text("", encoding="utf-8")
            cached = root / "iterations/000/validation/input_formats.json"
            cached.parent.mkdir()
            cached.write_text(
                json.dumps(
                    {
                        "candidate": {
                            "scopes": [
                                {
                                    "file": "program.catala_en",
                                    "compiler_file": "program.catala_en",
                                    "scope": name,
                                    "input_schema": {
                                        "$ref": "#/definitions/Input",
                                        "definitions": {
                                            "Input": {
                                                "type": "object",
                                                "properties": {
                                                    "number": {"type": "integer"}
                                                },
                                            }
                                        },
                                    },
                                    "output_schema": {
                                        "$ref": "#/definitions/Output",
                                        "definitions": {
                                            "Output": {
                                                "type": "object",
                                                "properties": {
                                                    "answer": {"type": "integer"}
                                                },
                                            }
                                        },
                                    },
                                }
                                for name in ("First", "Second")
                            ]
                            + [
                                {
                                    "file": "program.catala_en",
                                    "compiler_file": "program.catala_en",
                                    "scope": "EmptyInput",
                                    "input_schema": {"type": "object"},
                                    "output_schema": {
                                        "type": "object",
                                        "properties": {"answer": {"type": "integer"}},
                                    },
                                },
                                {
                                    "file": "program.catala_en",
                                    "compiler_file": "program.catala_en",
                                    "scope": "EmptyOutput",
                                    "input_schema": {
                                        "type": "object",
                                        "properties": {"number": {"type": "integer"}},
                                    },
                                    "output_schema": {"type": "object"},
                                },
                                {
                                    "file": "program.catala_en",
                                    "compiler_file": "program.catala_en",
                                    "scope": "WithoutJsonSchema",
                                    "input_schema": None,
                                    "output_schema": None,
                                },
                            ]
                        }
                    }
                )
            )
            config = {"dataset": {"name": "example"}, "runtime": {}}
            seen = []

            def fake_run(target, project):
                seen.append((target.scope, target.timeout, target.harness))
                payload = {
                    "input": {"number": 3},
                    "outputs": {"answer": "3"},
                    "branches": [],
                }
                return bobcat_run.RunResult(
                    stdout="[RESULT] BOBCAT_REPLAY " + json.dumps(payload) + "\n",
                    stderr="",
                    returncode=0,
                    seconds=0.1,
                    timed_out=False,
                    command=["catala", "bobcat"],
                )

            with (
                mock.patch.object(
                    stage.exp, "publish_iteration_snapshot", return_value=snapshot
                ),
                mock.patch.object(bobcat_run, "prepare_project", return_value=snapshot),
                mock.patch.object(bobcat_run, "run_bobcat", side_effect=fake_run),
            ):
                rows = bobcat_stage.generate_tests(
                    root, config, {"iteration": 0}, trace_stage.DEFAULTS
                )
            self.assertEqual({scope for scope, _, _ in seen}, {"First", "Second"})
            self.assertTrue(
                all(
                    timeout == 1800 and harness == snapshot / "program.catala_en"
                    for _, timeout, harness in seen
                )
            )
            self.assertEqual(len(rows), 2)

    def test_generate_tests_include_scopes_outside_requirement_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            iteration = root / "iterations/000"
            validation = iteration / "validation"
            validation.mkdir(parents=True)
            (validation / "requirement_outputs.json").write_text(
                json.dumps(
                    {
                        "requirements": [
                            {
                                "requirement_id": "R1",
                                "scope": "Answer",
                                "output": "amount",
                                "file": "program.catala_en",
                            },
                        ]
                    }
                )
            )
            snapshot = iteration / "snapshot"
            snapshot.mkdir()
            source = snapshot / "program.catala_en"
            source.write_text("", encoding="utf-8")
            scopes = [
                {
                    "scope": "Answer",
                    "file": "program.catala_en",
                    "compiler_file": "program.catala_en",
                },
                {
                    "scope": "Helper",
                    "file": "program.catala_en",
                    "compiler_file": "program.catala_en",
                },
            ]
            seen = []

            def fake_run(target, project):
                seen.append((target.scope, target.output))
                payload = {
                    "input": {"number": 3},
                    "outputs": {"answer": "3"},
                    "branches": [],
                }
                return bobcat_run.RunResult(
                    stdout="[RESULT] BOBCAT_REPLAY " + json.dumps(payload) + "\n",
                    stderr="",
                    returncode=0,
                    seconds=0.1,
                    timed_out=False,
                    command=["catala", "bobcat"],
                )

            config = {"dataset": {"name": "fixture"}}
            with (
                mock.patch.object(
                    stage.exp, "publish_iteration_snapshot", return_value=snapshot
                ),
                mock.patch.object(bobcat_stage, "_all_scopes", return_value=scopes),
                mock.patch.object(bobcat_run, "prepare_project", return_value=snapshot),
                mock.patch.object(bobcat_run, "run_bobcat", side_effect=fake_run),
            ):
                rows = bobcat_stage.generate_tests(
                    root, config, {"iteration": 0}, trace_stage.DEFAULTS
                )

            self.assertEqual(seen, [("Answer", None), ("Helper", None)])
            self.assertEqual({row["target"] for row in rows}, {"Answer", "Helper"})
            self.assertTrue(all("requirement_id" not in row for row in rows))

    def test_block_path_keeps_first_concrete_visit_per_statute(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.catala_en"
            source.write_text(
                "<!-- rtdf-block-id: b1; role: provision; provision-id: law/a; source-lines: 1-1; relation: formalizes-preceding -->\n"
                "```catala\nx\n```\n"
                "<!-- rtdf-block-id: b2; role: provision; provision-id: law/b; source-lines: 2-2; relation: formalizes-preceding -->\n"
                "```catala\ny\n```\n",
                encoding="utf-8",
            )
            self.assertEqual(
                trace_stage.provision_path(
                    Path(directory),
                    [
                        "default@sample.catala_en:7:1-7:2/other@sample.catala_en:3:1-3:2",
                        "default@sample.catala_en:7:1-7:2",
                    ],
                ),
                ["law/b", "law/a"],
            )
            self.assertEqual(
                trace_stage.traced_provision_path(
                    Path(directory),
                    [
                        {
                            "event": "DecisionTaken",
                            "pos": {"filename": "../sample.catala_en", "start_line": 7},
                        },
                        {
                            "event": "DecisionTaken",
                            "pos": {"filename": "../sample.catala_en", "start_line": 3},
                        },
                    ],
                ),
                ["law/b", "law/a"],
            )
            scoped = Path(directory) / "scoped.catala_en"
            scoped.write_text(
                "<!-- rtdf-block-id: root; role: provision; provision-id: law/root; source-lines: 1-1; relation: formalizes-preceding -->\n"
                "scope Root:\n"
                "<!-- rtdf-block-id: nested; role: provision; provision-id: law/nested; source-lines: 2-2; relation: formalizes-preceding -->\n"
                "scope Nested:\n",
                encoding="utf-8",
            )
            self.assertEqual(
                trace_stage.traced_provision_path(
                    Path(directory),
                    [{"event": "BeginCall", "name": "Nested.direct"}],
                    entry_scope="Root",
                    entry_source="scoped.catala_en",
                ),
                [],
            )

    def test_scope_anchor_uses_parent_and_runtime_reentry_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "section.catala_en"
            source.write_text(
                "<!-- rtdf-block-id: parent; role: provision; provision-id: law/1(a):flush; source-lines: 1-1; relation: formalizes-preceding -->\n"
                "```catala\ndeclaration scope Rate:\n  input amount content integer\n```\n"
                "<!-- rtdf-block-id: child; role: provision; provision-id: law/1(a)(i); source-lines: 2-2; relation: formalizes-preceding -->\n"
                "```catala\nscope Rate:\n  definition tax under condition amount > 0 consequence equals 1\n```\n"
            )
            self.assertEqual(
                trace_stage.scope_statute_anchor(Path(directory), source.name, "Rate"),
                "law/1(a)",
            )
            siblings = Path(directory) / "siblings.catala_en"
            siblings.write_text(
                "<!-- rtdf-document-id: law/whole-tax -->\n"
                "<!-- rtdf-block-id: a; role: provision; provision-id: law/1(a); source-lines: 1-1; relation: formalizes-preceding -->\n"
                "```catala\nscope Tax:\n  definition joint equals 1\n```\n"
                "<!-- rtdf-block-id: b; role: provision; provision-id: law/1(b); source-lines: 2-2; relation: formalizes-preceding -->\n"
                "```catala\nscope Tax:\n  definition head equals 2\n```\n"
            )
            self.assertEqual(
                trace_stage.scope_statute_anchor(Path(directory), siblings.name, "Tax"),
                "law/whole-tax",
            )
            flat = Path(directory) / "flat.catala_en"
            flat.write_text(
                "<!-- rtdf-block-id: f1; role: provision; provision-id: law/flat:p0001; source-lines: 1-1; relation: formalizes-preceding -->\n"
                "```catala\nscope Amount:\n  definition one equals 1\n```\n"
                "<!-- rtdf-block-id: f2; role: provision; provision-id: law/flat:p0002; source-lines: 2-2; relation: formalizes-preceding -->\n"
                "```catala\nscope Amount:\n  definition two equals 2\n```\n"
            )
            self.assertEqual(
                trace_stage.scope_statute_anchor(Path(directory), flat.name, "Amount"),
                "law/flat",
            )
            events = [
                {
                    "event": "DecisionTaken",
                    "pos": {"filename": source.name, "start_line": 9},
                },
                {"event": "BeginCall", "name": "Rate"},
                {
                    "event": "DecisionTaken",
                    "pos": {"filename": source.name, "start_line": 9},
                },
            ]
            self.assertEqual(
                trace_stage.traced_provision_path(Path(directory), events),
                ["law/1(a)(i)"],
            )

    def test_declared_scope_call_maps_to_its_annotated_block(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "section.catala_en"
            source.write_text(
                "<!-- rtdf-block-id: child; role: provision; provision-id: law/child; source-lines: 1-1; relation: formalizes-preceding -->\n"
                "```catala-metadata\n"
                "declaration scope Child:\n  output result content boolean\n"
                "```\n",
                encoding="utf-8",
            )
            self.assertEqual(
                trace_stage.execution_blocks(
                    Path(directory),
                    [
                        {
                            "kind": "call",
                            "name": "section.catala_en::Child",
                            "children": [],
                        }
                    ],
                ),
                ["child"],
            )

    def test_summary_retains_reasoning_and_uses_blocks_as_slice_units(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "iterations/000/snapshot"
            snapshot.mkdir(parents=True)
            (snapshot / "law.catala_en").write_text(
                "<!-- rtdf-block-id: a; role: provision; provision-id: law/a; source-lines: 1-1; relation: formalizes-preceding -->\n"
                "```catala\nscope Answer:\n  definition amount equals 5\n```\n"
            )
            position = {"filename": "law.catala_en", "start_line": 3}
            formal = [
                {
                    "id": "one",
                    "output": {"amount": "5000.00"},
                    "inputs": {"amount": "5"},
                    "statute_ids": ["law/a", "law/b"],
                    "error": None,
                    "execution_tree": [
                        {
                            "kind": "call",
                            "children": [
                                {"kind": "decision", "pos": position, "children": []}
                            ],
                        }
                    ],
                    "dynamic_slice_tree": [
                        {
                            "kind": "call",
                            "children": [
                                {"kind": "decision", "pos": position, "children": []}
                            ],
                        }
                    ],
                },
                {
                    "id": "two",
                    "output": {"amount": "4.00"},
                    "inputs": {"amount": "4"},
                    "statute_ids": ["law/a"],
                    "error": None,
                    "execution_tree": [],
                    "dynamic_slice_tree": [],
                },
            ]
            natural = [
                {
                    "id": "one",
                    "output_text": 'First apply law/b, then law/a.\n<answer>{"amount": 5000}</answer>',
                },
                {
                    "id": "two",
                    "output_text": 'The amount is wrong.\n<answer>{"amount": 3}</answer>',
                },
            ]
            result = comparison_stage.compare(root, {"iteration": 0}, formal, natural)
            self.assertEqual((result["total"], result["llm_traces_generated"]), (2, 2))
            self.assertEqual(
                (
                    result["final_answers_parsed"],
                    result["final_answers_aligned"],
                    result["final_answers_misaligned"],
                    result["final_answer_parse_errors"],
                ),
                (2, 1, 1, 0),
            )
            self.assertEqual(result["cases"][0]["inputs"], {"amount": "5"})
            self.assertEqual(
                result["cases"][0]["llm_reasoning_trace"],
                'First apply law/b, then law/a.\n<answer>{"amount": 5000}</answer>',
            )
            self.assertEqual(result["cases"][0]["llm_final_answer"], {"amount": 5000})
            self.assertTrue(result["cases"][0]["final_answer_aligned"])
            self.assertFalse(result["cases"][1]["final_answer_aligned"])
            self.assertNotIn("catala_statute_ids", result["cases"][0])
            self.assertNotIn("llm_output", result["cases"][0])
            self.assertNotIn("llm_statute_ids", result["cases"][0])
            self.assertEqual(
                result["cases"][0]["catala_execution_tree"], [{"children": ["law/a"]}]
            )
            self.assertEqual(
                result["cases"][0]["catala_dynamic_slice_tree"],
                [{"children": ["law/a"]}],
            )
            self.assertEqual(
                result["cases"][0]["provision_alignment"],
                {"overlaps": [], "catala_only": ["law/a"], "llm_only": []},
            )
            self.assertEqual(result["cases"][0]["catala_execution_blocks"], ["a"])
            self.assertEqual(result["cases"][0]["catala_dynamic_slice_blocks"], ["a"])
            self.assertEqual(
                (
                    result["cases"][0]["catala_execution_block_count"],
                    result["cases"][0]["catala_dynamic_slice_block_count"],
                    result["cases"][0]["catala_slice_reduction_blocks"],
                ),
                (1, 1, 0),
            )
            self.assertEqual(
                result["block_sizes"],
                {
                    "execution_blocks": 1,
                    "dynamic_slice_blocks": 1,
                    "reduction_blocks": 0,
                    "reduced_cases": 0,
                    "equal_cases": 2,
                },
            )
            self.assertEqual(
                result["trace_event_counts"],
                {
                    "execution_nodes": 2,
                    "dynamic_slice_nodes": 2,
                },
            )
            self.assertTrue(
                (root / "iterations/000/tests_bobcat_comparison/summary.json").is_file()
            )

    def test_summary_does_not_count_provider_error_text_as_a_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "iterations/000/snapshot").mkdir(parents=True)
            formal = [
                {
                    "id": "one",
                    "output": {"amount": 4},
                    "inputs": {},
                    "error": None,
                    "execution_tree": [],
                    "dynamic_slice_tree": [],
                }
            ]
            natural = [
                {
                    "id": "one",
                    "output_text": "You've hit your session limit",
                    "error": "HTTP 429",
                }
            ]
            result = comparison_stage.compare(root, {"iteration": 0}, formal, natural)
            self.assertEqual(result["llm_traces_generated"], 0)
            self.assertEqual(result["final_answers_parsed"], 0)
            self.assertEqual(result["final_answer_parse_errors"], 1)

    def test_reason_retries_cached_error_response(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            formats = (
                root / "iterations/000/tests_bobcat_symbolic_results/input_formats.json"
            )
            formats.parent.mkdir(parents=True)
            formats.write_text(json.dumps({"scopes": []}))
            destination = (
                root
                / "iterations/000/tests_bobcat_natural_language_results"
                / "case-1.json"
            )
            destination.parent.mkdir()
            prompt_hash = hashlib.sha256(b"test prompt").hexdigest()
            destination.write_text(
                json.dumps(
                    {
                        "id": "case-1",
                        "format": "reasoning_with_json_answer",
                        "prompt_sha256": prompt_hash,
                        "output_text": "session limit",
                        "error": "HTTP 429",
                    }
                )
            )
            config = {
                "run_id": "run",
                "dataset": {"name": "law"},
                "reasoning_trace": {"provider": "openai", "model": "test"},
            }
            case = {
                "id": "case-1",
                "source": "law.catala_en",
                "target": "Calculate",
                "inputs": {},
            }
            sampled = {
                "raw_response": {"id": "response-1"},
                "output_text": '<answer>{"amount": 4}</answer>',
                "request_id": "response-1",
                "usage": {"input_tokens": 2, "output_tokens": 3},
            }
            with (
                mock.patch.object(llm_stage, "_statutes", return_value=""),
                mock.patch.object(
                    llm_stage, "requirement_descriptions", return_value={}
                ),
                mock.patch.object(llm_stage, "_prompt", return_value="test prompt"),
                mock.patch.object(llm_stage, "_sample", return_value=sampled) as sent,
            ):
                observed = llm_stage.reason(root, config, {"iteration": 0}, [case])
            self.assertEqual(sent.call_count, 2)
            self.assertEqual(len(sent.call_args_list[0].args), 2)
            self.assertIsInstance(sent.call_args_list[1].args[2], dict)
            self.assertNotIn("error", observed[0])
            self.assertEqual(
                json.loads(destination.read_text())["request_id"], "response-1"
            )

    def test_reason_persists_provider_error_and_stops_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            formats = (
                root / "iterations/000/tests_bobcat_symbolic_results/input_formats.json"
            )
            formats.parent.mkdir(parents=True)
            formats.write_text(json.dumps({"scopes": []}))
            config = {
                "run_id": "run",
                "dataset": {"name": "law"},
                "reasoning_trace": {"provider": "openai", "model": "test"},
            }
            case = {
                "id": "case-1",
                "source": "law.catala_en",
                "target": "Calculate",
                "inputs": {},
            }
            with (
                mock.patch.object(llm_stage, "_statutes", return_value=""),
                mock.patch.object(
                    llm_stage, "requirement_descriptions", return_value={}
                ),
                mock.patch.object(llm_stage, "_prompt", return_value="test prompt"),
                mock.patch.object(
                    llm_stage,
                    "_sample",
                    side_effect=experiment.RunnerError("HTTP 429"),
                ),
            ):
                with self.assertRaisesRegex(
                    experiment.RunnerError, "reasoning case case-1"
                ):
                    llm_stage.reason(root, config, {"iteration": 0}, [case])
            saved = json.loads(
                (
                    root
                    / "iterations/000/tests_bobcat_natural_language_results"
                    / "case-1.json"
                ).read_text()
            )
            self.assertIn("HTTP 429", saved["error"])
            self.assertIsNone(saved["output_text"])

    def test_reasoning_persists_raw_output_and_per_sample_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input").mkdir()
            (root / "input/statute.catala_en").write_text(
                "<!-- rtdf-block-id: b1; role: provision; provision-id: law/a; source-lines: 1-1; relation: formalizes-preceding -->\n"
                "Law text.\n```catala\nsecret code\n```\n",
                encoding="utf-8",
            )
            (root / "input/RTDF_MANIFEST.json").write_text(
                json.dumps(
                    {"documents": [{"path": "statute.catala_en", "document_id": "law"}]}
                )
            )
            formats = (
                root / "iterations/000/tests_bobcat_symbolic_results/input_formats.json"
            )
            formats.parent.mkdir(parents=True)
            formats.write_text(
                json.dumps(
                    {
                        "scopes": [
                            {
                                "compiler_file": "statute.catala_en",
                                "scope": "Calculate",
                                "input_schema": {
                                    "type": "object",
                                    "properties": {"amount": {"type": "number"}},
                                    "required": ["amount"],
                                },
                                "output_schema": {
                                    "type": "object",
                                    "properties": {"amount": {"type": "number"}},
                                    "required": ["amount"],
                                },
                            }
                        ]
                    }
                )
            )
            snapshot = root / "iterations/000/snapshot"
            snapshot.mkdir()
            (snapshot / "statute.catala_en").write_text(
                "<!-- rtdf-block-id: b1; role: provision; provision-id: law/a; source-lines: 1-1; relation: formalizes-preceding -->\n"
                "```catala\nscope Calculate:\n  definition amount equals 5000\n```\n"
            )
            config = {
                "run_id": "run",
                "dataset": {"name": "law"},
                "reasoning_trace": {"provider": "openai", "model": "test"},
            }
            case = {
                "id": "case-1",
                "source": "statute.catala_en",
                "target": "Calculate",
                "inputs": {"amount": "5000.00"},
            }
            sampled = {
                "raw_response": {"id": "r1", "output": [{"type": "reasoning"}]},
                "output_text": "Apply law/a. The amount is 5000.",
                "request_id": "r1",
                "usage": {"input_tokens": 42, "output_tokens": 12},
            }
            extracted = {
                "raw_response": {"id": "r2"},
                "output_text": json.dumps(
                    {
                        "steps": [
                            {
                                "id": 0,
                                "claim": "The amount is 5000.",
                                "provision": "a",
                                "premises": [],
                            }
                        ]
                    }
                ),
                "request_id": "r2",
                "usage": {"input_tokens": 30, "output_tokens": 10},
            }
            with mock.patch.object(
                llm_stage, "_sample", side_effect=[sampled, extracted]
            ):
                results = llm_stage.reason(root, config, {"iteration": 0}, [case])
            self.assertEqual(
                results[0]["output_text"], "Apply law/a. The amount is 5000."
            )
            self.assertEqual(results[0]["format"], llm_stage.REASONING_RESULT_FORMAT)
            self.assertEqual(results[0]["execution_tree"]["steps"][0]["provision"], "a")
            self.assertIsNone(results[0]["execution_tree_extraction_error"])
            self.assertNotIn("parsed", results[0])
            self.assertNotIn("response_schema", results[0])
            prompt = (
                root
                / "iterations/000/tests_bobcat_natural_language_results/case-1.prompt.txt"
            ).read_text()
            self.assertIn("The case is as follows (YAML):", prompt)
            self.assertNotIn("secret code", prompt)
            self.assertNotIn("<!--", prompt)
            self.assertIn("[a]", prompt)
            self.assertNotIn("[law/a]", prompt)
            usage = json.loads((root / "usage.jsonl").read_text().splitlines()[0])
            self.assertEqual(usage["input_tokens"], 42)


if __name__ == "__main__":
    unittest.main()
