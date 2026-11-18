"""Frozen public contract documentation survives code-blind prompt assembly."""
from pathlib import Path
import json
import tempfile
import unittest

from rsa_formalizer.stages.utils.input_contract import field_descriptions
from rsa_formalizer.stages.reasoning_structure_alignment.provision_testing import input_prompt
from rsa_formalizer.stages.reasoning_structure_alignment.generate_llm_trace import _prompt


class InputContractTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.run = Path(temporary.name)
        (self.run / 'input').mkdir()
        self.source = self.run / 'input/shared.catala_en'
        self.source.write_text('''# Public input conventions
> Module Facts
> Using Hidden as H

An active interval includes both recorded endpoints.

```catala-metadata
declaration structure Request: # Public request.
  data value content integer # Recorded measurement.
  # Negative means unavailable, not an actual measurement.
declaration structure Private: # PRIVATE_TYPE
  data secret content integer # PRIVATE_FIELD
```

Missing timestamps remain absent; do not invent one.
<!-- rsa-block-id: private; provision-id: example/private; -->
```catala
declaration includes_period content boolean # Requires exact interval endpoints.
  depends on request content Request
  equals EXECUTABLE_SECRET
# IMPLEMENTATION_COMMENT_SECRET
scope Implementation:
  definition result equals CANDIDATE_SECRET
```

The supplied request is the complete factual record.
''')
        self.schema = {'$ref': '#/definitions/Facts.Request', 'definitions': {
            'Facts.Request': {'type': 'object', 'properties': {'value': {'type': 'integer'}}},
            'Facts.Private': {'type': 'object'}}}

    def test_prose_and_helper_comments_survive_without_bodies(self):
        text = field_descriptions(self.run, self.schema)
        for fragment in ['includes both recorded endpoints', 'Missing timestamps remain absent',
                         'complete factual record', 'Requires exact interval endpoints',
                         'Facts.Request.value', 'Negative means unavailable']:
            self.assertIn(fragment, text)
        for fragment in ['EXECUTABLE_SECRET', 'CANDIDATE_SECRET', 'IMPLEMENTATION_COMMENT_SECRET',
                         'PRIVATE_TYPE', 'PRIVATE_FIELD', 'depends on', 'definition result',
                         'rsa-block-id', '> Module', '> Using', '```', '<RSA-CATALA-BODY>']:
            self.assertNotIn(fragment, text)

    def test_modules_omitted_from_statute_manifest_still_reach_both_prefixes(self):
        (self.run / 'input/RSA_MANIFEST.json').write_text(json.dumps({'documents': [{'path': 'Rules.catala_en'}]}))
        text = field_descriptions(self.run, self.schema)
        output = {'type': 'object', 'properties': {'result': {'type': 'integer'}}}
        case = {'inputs': {'value': 3}, 'target': 'WholeProgram', 'input_authority': 'structured_json'}
        first = input_prompt('SPECIFICATION', self.schema, 'example/P1', [], text)
        second = input_prompt('SPECIFICATION', self.schema, 'example/P2', [{'reason': 'retry'}], text)
        reasoner = _prompt('SPECIFICATION', case, output, field_documentation=text)
        other = _prompt('SPECIFICATION', {**case, 'inputs': {'value': 8}}, output, field_documentation=text)
        self.assertEqual(first.prefix, second.prefix)
        self.assertEqual(reasoner.prefix, other.prefix)
        for prompt in [first, second, reasoner, other]:
            self.assertIn('Requires exact interval endpoints.', prompt.prefix)
            self.assertIn('Missing timestamps remain absent', prompt.prefix)
            self.assertNotIn('EXECUTABLE_SECRET', prompt)
            self.assertNotIn('CANDIDATE_SECRET', prompt)

    def test_unreachable_modules_and_workspace_are_excluded(self):
        (self.run / 'input/Unrelated.catala_en').write_text('''PRIVATE_PROSE
```catala-metadata
declaration structure Secret: # PRIVATE_OTHER_TYPE
 data key content integer # PRIVATE_OTHER_FIELD
```
''')
        (self.run / 'workspace').mkdir()
        (self.run / 'workspace/shared.catala_en').write_text('WORKSPACE_SECRET')
        text = field_descriptions(self.run, self.schema)
        self.assertNotIn('PRIVATE', text)
        self.assertNotIn('WORKSPACE_SECRET', text)

    def test_inline_closing_fences_do_not_corrupt_documentation(self):
        standalone = field_descriptions(self.run, self.schema)
        self.source.write_text(self.source.read_text().replace(
            '# Negative means unavailable, not an actual measurement.\n```',
            '# Negative means unavailable, not an actual measurement.```').replace(
            '  definition result equals CANDIDATE_SECRET\n```',
            '  definition result equals CANDIDATE_SECRET```'))
        self.assertEqual(field_descriptions(self.run, self.schema), standalone)

    def test_documentation_changes_change_both_prompt_prefixes(self):
        first = field_descriptions(self.run, self.schema)
        self.source.write_text(self.source.read_text().replace('includes both recorded endpoints', 'excludes the final endpoint'))
        second = field_descriptions(self.run, self.schema)
        self.assertNotEqual(first, second)
        self.assertNotEqual(input_prompt('S', self.schema, 'P1', [], first).prefix,
                            input_prompt('S', self.schema, 'P1', [], second).prefix)
        case = {'inputs': {'value': 3}, 'target': 'WholeProgram', 'input_authority': 'structured_json'}
        self.assertNotEqual(_prompt('S', case, {}, field_documentation=first).prefix,
                            _prompt('S', case, {}, field_documentation=second).prefix)

    def test_crlf_preserves_prose_without_fence_markers(self):
        expected = field_descriptions(self.run, self.schema)
        self.source.write_bytes(self.source.read_text().replace('\n', '\r\n').encode())
        self.assertEqual(field_descriptions(self.run, self.schema), expected)


if __name__ == '__main__':
    unittest.main()
