"""Match Catala's inline closing fences without losing protected prose."""
from pathlib import Path
import tempfile
import unittest

from rsa_formalizer.stages.utils.common import (
    RunnerError, normalize_protected_whitespace, parse_fenced_document,
)
from rsa_formalizer.stages.utils.workspace_validation import (
    catala_block_ids, validate_workspace, workspace_fence_progress,
)


class FencedDocumentTest(unittest.TestCase):
    def test_inline_closings_preserve_blocks_integrity_and_progress(self):
        baseline = (
            'Protected statute.\n'
            '<!-- rsa-block-id: example:b1; role: provision; -->\n'
            '```catala-metadata\n```\n'
            'More protected statute.\n'
            '<!-- rsa-block-id: example:b2; role: provision; -->\n'
            '```catala\n```\n'
        )
        candidate = baseline.replace(
            '```catala-metadata\n```',
            '```catala-metadata\ndeclaration scope Answer:\n'
            '  output value content integer```',
        ).replace(
            '```catala\n```',
            '```catala\nscope Answer:\n  definition value equals 1```',
        )
        for newline in ('\n', '\r\n'):
            for at_eof in (False, True):
                with self.subTest(newline=repr(newline), at_eof=at_eof), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp); before = root/'input'; after = root/'workspace'
                    before.mkdir(); after.mkdir()
                    original = before/'law.catala_en'; edited = after/original.name
                    original.write_bytes(baseline.replace('\n', newline).encode())
                    text = candidate.rstrip('\n') if at_eof else candidate
                    edited.write_bytes(text.replace('\n', newline).encode())
                    parsed = parse_fenced_document(edited)
                    self.assertEqual(len(parsed.blocks), 2)
                    self.assertTrue(parsed.blocks[1].endswith(('  definition value equals 1'+newline).encode()))
                    self.assertNotIn(b'```', b''.join(parsed.blocks))
                    self.assertEqual(normalize_protected_whitespace(parsed.skeleton), normalize_protected_whitespace(parse_fenced_document(original).skeleton))
                    self.assertEqual(catala_block_ids(edited), ('example:b1', 'example:b2'))
                    self.assertEqual(workspace_fence_progress(before, after), {'total':2, 'filled':2, 'valid':2, 'changed':2})
                    self.assertEqual(validate_workspace(before, after)['valid_code_blocks'], 2)
                    edited.write_text(text.replace('More protected statute.', 'Changed statute.'))
                    with self.assertRaisesRegex(RunnerError, 'statute prose'):
                        validate_workspace(before, after)

    def test_standalone_and_inline_closings_have_the_same_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'law.catala_en'
            p.write_text('```catala\nscope Answer:\n  definition value equals 1\n```\n')
            standalone=parse_fenced_document(p)
            p.write_text('```catala\nscope Answer:\n  definition value equals 1```\n')
            self.assertEqual(parse_fenced_document(p),standalone)

    def test_new_module_import_does_not_unprotect_statute(self):
        baseline = (
            '> Module Law\n> Using Definitions as W\n\n'
            'Protected statute.\n```catala\n'
            'scope Answer:\n  definition value equals 0\n```\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before, after = root/'input', root/'workspace'
            before.mkdir(); after.mkdir()
            (before/'law.catala_en').write_text(baseline)
            candidate = baseline.replace(
                '> Using Definitions as W\n',
                '> Using Definitions as W\n> Using Section152 as S152\n',
            ).replace('definition value equals 0', 'definition value equals 1')
            edited = after/'law.catala_en'
            edited.write_text(candidate)
            self.assertEqual(validate_workspace(before, after)['changed_blocks'], 1)
            edited.write_text(candidate.replace('Protected statute.', 'Changed statute.'))
            with self.assertRaisesRegex(RunnerError, 'statute prose'):
                validate_workspace(before, after)

    def test_unclosed_and_wrong_length_markers_still_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'law.catala_en'
            for end in ('', '``', '````', '```not-a-closing-fence'):
                with self.subTest(end=end):
                    p.write_text('```catala\nscope Answer:\n  definition value equals 1'+end+'\n')
                    with self.assertRaisesRegex(RunnerError, 'unclosed Catala fence'):
                        parse_fenced_document(p)


if __name__ == '__main__':
    unittest.main()
