"""Regression tests for infrastructure failures, without project data or models."""

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from scripts.check_infrastructure import check_file, repository_files


class InfrastructureTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def test_syntax_errors_are_reported_without_executing_code(self):
        self.write('example.py', 'raise RuntimeError("must not execute")\n')
        self.assertEqual(check_file(self.root, 'example.py'), ('python', []))
        self.write('example.py', 'def broken(:\n')
        self.assertTrue(check_file(self.root, 'example.py')[1])
        self.assertFalse((self.root / '__pycache__').exists())

    def test_json_rejects_duplicate_keys_constants_and_malformed_input(self):
        for text in ('{"x": 1, "x": 2}', '{"x": {"y": 1, "y": 2}}',
                     '{"x": NaN}', '{"x": Infinity}', '{'):
            with self.subTest(text=text):
                self.write('config/example.json', text)
                self.assertTrue(check_file(self.root, 'config/example.json')[1])
        self.write('config/example.json', '{"x": [1, true, null]}')
        self.assertEqual(check_file(self.root, 'config/example.json'), ('json', []))

    def test_links_resolve_from_document_and_ignore_code_and_external_urls(self):
        self.write('docs/target file.md', '# Target\n')
        self.write('docs/guide.md', '\n'.join((
            '[target](target%20file.md?raw=1#target)',
            '[spaces](<target file.md>)', '![image](target%20file.md)',
            '[web](https://example.invalid/missing)', '[anchor](#heading)',
            '`[inline example](missing.md)`', '```md', '[example](missing.md)',
            '```', '~~~', '[example](missing.md)', '~~~',
        )))
        self.assertEqual(check_file(self.root, 'docs/guide.md'), ('docs', []))

    def test_missing_and_outside_checkout_links_fail(self):
        self.write('README.md', '[missing](missing.md)\n[outside](../)\n')
        self.assertEqual(len(check_file(self.root, 'README.md')[1]), 2)

    def test_data_and_content_documents_are_outside_scope(self):
        for name in ('data/batch.json', 'drafts/status.json', 'archive/config/plan.json',
                     'prompts/example.md', 'policy/example.md'):
            with self.subTest(name=name):
                self.write(name, '{ invalid [link](missing.md)')
                self.assertEqual(check_file(self.root, name), (None, []))

    def test_discovery_includes_new_files_but_excludes_ignored_environment(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.write('.gitignore', '.venv*/\n')
        self.write('new.py', 'pass\n')
        self.write('.venv-dev/ignored.py', 'broken syntax')
        files = repository_files(self.root)
        self.assertIn('new.py', files)
        self.assertNotIn('.venv-dev/ignored.py', files)


if __name__ == '__main__':
    unittest.main()
