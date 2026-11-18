from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
from unittest import TestCase, mock

from rsa_formalizer.stages.reasoning_structure_alignment import provision_testing
from rsa_formalizer.stages.reasoning_structure_alignment import generate_llm_trace as reasoning
from rsa_formalizer.stages.utils import prompt_cache, usage
from rsa_formalizer.stages.utils.input_contract import field_descriptions


class PromptCacheTest(TestCase):
    def setUp(self):
        self.addCleanup(prompt_cache._BASELINES.clear)
        prompt_cache._BASELINES.clear()

    def test_generation_prefix_is_identical_across_targets_and_retries(self):
        first = provision_testing.input_prompt("ALL PROVISIONS", {"type": "object"}, "section1(a)", [])
        second = provision_testing.input_prompt("ALL PROVISIONS", {"type": "object"}, "section2(b)", [{"reason": "bad date"}])
        self.assertIsInstance(first, prompt_cache.CacheablePrompt)
        self.assertEqual(first.prefix, second.prefix)
        self.assertIn("ALL PROVISIONS", first.prefix)
        self.assertIn('"type": "object"', first.prefix)
        self.assertNotIn("section1(a)", first.prefix)
        self.assertIn("section2(b)", second.suffix)
        self.assertIn("bad date", second.suffix)

    def test_reasoning_prefix_is_identical_across_different_cases(self):
        case = {"inputs": {"x": True}, "target": "WholeProgram", "input_authority": "structured_json"}
        schema = {"type": "object", "properties": {"result": {"type": "boolean"}}}
        first = reasoning._prompt("ALL PROVISIONS", case, schema)
        second = reasoning._prompt("ALL PROVISIONS", {**case, "inputs": {"x": False}}, schema)
        self.assertEqual(first.prefix, second.prefix)
        self.assertIn("ALL PROVISIONS", first.prefix)
        self.assertIn("result", first.prefix)
        self.assertNotIn("x: true", first.prefix)
        self.assertIn("x: true", first.suffix)
        self.assertIn("x: false", second.suffix)

    def test_frozen_field_documentation_reaches_both_static_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "input").mkdir()
            (run / "input/Definitions.catala_en").write_text(
                '```catala\n'
                'declaration structure RelationshipFact: # Family or residence fact.\n'
                '  data relative_1 content Entity # Parent or home/place; id 0 means absent.\n'
                'declaration enumeration Entity: # An identity.\n'
                '  -- Atom # Ordinary person or place.\n'
                'declaration structure Internal: # PRIVATE_TYPE\n'
                '  data secret content integer # PRIVATE_FIELD\n'
                'scope Implementation:\n  definition result equals SECRET_CODE\n```\n')
            schema = {"$ref": "#/definitions/Definitions.RelationshipFact", "definitions": {
                "Definitions.RelationshipFact": {"properties": {"relative_1": {
                    "$ref": "#/definitions/Definitions.Entity"}}},
                "Definitions.Entity": {"type": "string"},
                "Definitions.Internal": {"type": "object"}}}
            documentation = field_descriptions(run, schema)
        self.assertIn("Definitions.RelationshipFact.relative_1", documentation)
        self.assertIn("Parent or home/place; id 0 means absent.", documentation)
        self.assertIn("Definitions.Entity.Atom", documentation)
        self.assertNotIn("PRIVATE", documentation)
        self.assertNotIn("SECRET_CODE", documentation)
        case = {"inputs": {"relative_1": 4}, "target": "WholeProgram",
                "input_authority": "structured_json", "required_provision": "TARGET_SECRET",
                "test_rationale": "RATIONALE_SECRET"}
        output_schema = {"type": "object", "properties": {"total_tax": {"type": "number"}},
                         "required": ["total_tax"]}
        generator = provision_testing.input_prompt("STATUTES", schema, "section1(a)", [], documentation)
        other_generator = provision_testing.input_prompt("STATUTES", schema, "section2(b)", [], documentation)
        reasoner = reasoning._prompt("STATUTES", case, output_schema, field_documentation=documentation)
        other_reasoner = reasoning._prompt("STATUTES", {**case, "inputs": {"relative_1": 5}},
                                          output_schema, field_documentation=documentation)
        self.assertEqual(generator.prefix, other_generator.prefix)
        self.assertEqual(reasoner.prefix, other_reasoner.prefix)
        for prompt in (generator, reasoner):
            self.assertIn(documentation, prompt.prefix)
            self.assertNotIn("INPUT FIELD DESCRIPTIONS", prompt.suffix)
        self.assertIn(json.dumps(schema, sort_keys=True), generator.prefix)
        self.assertNotIn("TARGET_SECRET", reasoner)
        self.assertNotIn("RATIONALE_SECRET", reasoner)
        self.assertIn('"total_tax": "<number>"', reasoner.prefix)
        self.assertIn("relative_1: 4", reasoner.suffix)

    def test_subscription_cache_uses_stable_prefix_and_automatic_routing_key(self):
        config = {"reasoning_trace": {"provider": "openai", "model": "gpt-6-luna"},
                  "prompt_cache": {"enabled": True, "ttl": "30m"}}
        responses = [
            {"id": "first", "usage": {"input_tokens": 2000}},
            {"id": "second", "usage": {"input_tokens": 2001,
                "input_tokens_details": {"cached_tokens": 1800}}},
        ]
        with mock.patch.object(reasoning.subscription_api, "codex_response", side_effect=responses) as sent, contextlib.redirect_stdout(io.StringIO()):
            reasoning._sample(config, prompt_cache.CacheablePrompt("references", "first", "generation"))
            second = reasoning._sample(config, prompt_cache.CacheablePrompt("references", "second", "generation"))
        first_request, second_request = [call.args[0] for call in sent.call_args_list]
        self.assertEqual(first_request["input"][0], second_request["input"][0])
        self.assertNotEqual(first_request["input"][1], second_request["input"][1])
        self.assertEqual(first_request["prompt_cache_key"], second_request["prompt_cache_key"])
        self.assertNotIn("extra_body", first_request)
        self.assertNotIn("prompt_cache_breakpoint", first_request["input"][0])
        self.assertEqual(second["usage"]["input_tokens_details"]["cached_tokens"], 1800)

    def test_cache_identity_separates_incompatible_output_formats(self):
        prompt = prompt_cache.CacheablePrompt("references", "question", "test")
        first = {"model": "m", "text": {"format": {"type": "json_object"}}}
        second = {"model": "m"}
        self.assertNotEqual(prompt_cache.configure_request(first, prompt, {}),
                            prompt_cache.configure_request(second, prompt, {}))

    def test_cache_write_accounting_is_not_added_to_input_tokens(self):
        counts = usage.api_counts({"input_tokens": 12000, "output_tokens": 100,
            "input_tokens_details": {"cached_tokens": 4000, "cache_write_tokens": 7000}})
        self.assertEqual(counts["input_tokens"], 12000)
        self.assertEqual(counts["cached_input_tokens"], 4000)
        self.assertEqual(counts["cache_write_tokens"], 7000)
        self.assertEqual(counts["total_tokens"], 12100)
