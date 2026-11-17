"""Civilian-only I/O integration tests; no dataset loading or model requests.

All writes and child-process markers stay in TemporaryDirectory fixtures.
Imports read application configuration, but no production records or prompts.
"""

from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from sentinel_dataset import checkpoints as cp
from sentinel_dataset import core, model
from sentinel_dataset import __main__ as cli


SOURCE = Path(__file__).resolve().parents[1]
CIVIL = {'text': 'The community library opens at nine.', 'visitors': 12}
CHILD = r'''
import os, pathlib, sys, threading
source, folder, mode = sys.argv[1:]
root = pathlib.Path(folder).resolve()
protected = tuple((pathlib.Path(source) / name).resolve() for name in
                  ('data', 'metadata', 'drafts', 'reports', 'archive', 'prompts', 'policy'))
def audit(event, args):
    if event == 'socket.connect':
        raise RuntimeError('Network is forbidden in system tests')
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = pathlib.Path(os.fsdecode(args[0])).resolve()
        if any(path.is_relative_to(item) for item in protected):
            raise RuntimeError('Production content access is forbidden')
        if args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
            if not path.is_relative_to(root):
                raise RuntimeError('Writes outside fixture are forbidden')
sys.addaudithook(audit)
sys.path.insert(0, source)
from sentinel_dataset import checkpoints as cp
cp.ROOT = root
cp.git = lambda *args: str(root)
def ready():
    (root / 'ready').write_text('ready', encoding='utf-8')
    threading.Event().wait()
if mode == 'lock':
    with cp.checkpoint_lock():
        ready()
elif mode in ('before_replace', 'after_replace'):
    original = pathlib.Path.replace
    def replace(path, target):
        if mode == 'before_replace':
            ready()
        result = original(path, target)
        ready()
        return result
    pathlib.Path.replace = replace
    cp.write_file(root / 'record.json', b'{"text":"City park reopens."}\n')
elif mode == 'write':
    cp.write_file(root / 'record.json', b'{"text":"City park reopens."}\n')
elif mode in ('before_link', 'after_link'):
    original = os.link
    def link(source, target):
        if mode == 'before_link':
            ready()
        original(source, target)
        ready()
    os.link = link
    cp.write_file(root / 'record.json', b'{"text":"City park reopens."}\n', overwrite=False)
elif mode == 'exclusive_race':
    import time
    original = os.link
    def link(source, target):
        (root / 'ready').write_text('ready', encoding='utf-8')
        deadline = time.monotonic() + 10
        while not (root / 'continue').exists():
            if time.monotonic() > deadline:
                raise RuntimeError('Timed out waiting for competing writer')
            time.sleep(0.01)
        original(source, target)
    os.link = link
    try:
        cp.write_file(root / 'record.json', b'{"text":"Bus route notice"}\n', overwrite=False)
    except FileExistsError:
        raise SystemExit(17)
elif mode == 'cli':
    from sentinel_dataset.__main__ import main
    sys.argv = ['sentinel_dataset', 'generate', str(root / 'job.json'),
                str(root / 'output.jsonl'), '--model', 'civil-fixture']
    main()
'''


class SystemIOTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='sentinel-civil-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        # Prevent accidental use of a real endpoint even if a test is changed.
        self.env = patch.dict(os.environ, {'DATASET_MODEL_BASE_URL': '',
                                         'DATASET_MODEL_API_KEY': ''})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.network = patch.object(model, 'urlopen', side_effect=AssertionError('No network'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def child(self, mode):
        process = subprocess.Popen(
            [sys.executable, '-B', '-c', CHILD, str(SOURCE), str(self.root), mode],
            cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.addCleanup(self.stop_child, process)
        return process

    @staticmethod
    def stop_child(process):
        if process.poll() is None:
            process.kill()
        return process.communicate(timeout=10)

    def wait_ready(self, process):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if (self.root / 'ready').exists():
                return
            if process.poll() is not None:
                self.fail(f'Child exited before marker: {process.communicate(timeout=10)}')
            time.sleep(0.01)
        self.fail('Child did not reach interruption point within 10 seconds')

    def generation_args(self):
        return cli.cli().parse_args(['generate', str(self.root / 'job.json'),
                                    str(self.root / 'output.jsonl'), '--model', 'civil-fixture'])

    @contextmanager
    def civil_generator(self, rows):
        with patch.object(cli, 'generate', return_value=rows), \
             patch.object(cli, 'scenario_catalog', return_value=({}, {})):
            yield

    def test_json_and_jsonl_roundtrip_unicode_and_newlines(self):
        row = dict(CIVIL, text='Caf\u00e9 notice\nLibrary hours: 09:00. \u05e9\u05dc\u05d5\u05dd')
        path = self.root / 'nested' / 'record.json'
        cp.write_file(path, core.json_bytes(row))
        self.assertEqual(core.read_json(path), row)
        self.assertTrue(path.read_bytes().endswith(b'\n'))
        lines = self.root / 'records.jsonl'
        cp.write_file(lines, core.jsonl_bytes([row, CIVIL]))
        self.assertEqual(core.read_jsonl(lines), [row, CIVIL])
        self.assertEqual(len(lines.read_bytes().splitlines()), 2)

    def test_malformed_and_truncated_json_are_rejected_without_mutation(self):
        path = self.root / 'record.json'
        for payload in (b'{', b'{"text":', b'\xff', b'{"x":1} trailing'):
            with self.subTest(payload=payload):
                path.write_bytes(payload)
                with self.assertRaises((ValueError, UnicodeError)):
                    core.read_json(path)
                self.assertEqual(path.read_bytes(), payload)
        path.write_bytes(b'{"text":"Bus schedule"}\n{bad}\n')
        with self.assertRaises(ValueError):
            core.read_jsonl(path)

    def test_missing_input_and_directory_destination_fail_cleanly(self):
        with self.assertRaises(FileNotFoundError):
            core.read_json(self.root / 'missing.json')
        target = self.root / 'directory'
        target.mkdir()
        with self.assertRaises(OSError):
            cp.write_file(target, b'civil notice')
        self.assertEqual(list(self.root.iterdir()), [target])

    def test_replace_failure_keeps_original_and_cleans_temporary_file(self):
        target = self.root / 'record.json'
        target.write_bytes(core.json_bytes(CIVIL))
        original = target.read_bytes()
        with patch.object(Path, 'replace', side_effect=PermissionError('simulated sharing violation')):
            with self.assertRaises(PermissionError):
                cp.write_file(target, b'new civil notice')
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(list(self.root.iterdir()), [target])

    def test_partial_write_failure_preserves_target_and_cleans_temporary_file(self):
        target = self.root / 'record.json'
        target.write_bytes(core.json_bytes(CIVIL))
        original = target.read_bytes()
        real_temporary_file = cp.NamedTemporaryFile

        @contextmanager
        def failing_file(*args, **kwargs):
            with real_temporary_file(*args, **kwargs) as stream:
                class BrokenStream:
                    name = stream.name

                    def write(self, content):
                        stream.write(content[:4])
                        raise OSError('simulated disk full')
                yield BrokenStream()

        with patch.object(cp, 'NamedTemporaryFile', failing_file):
            with self.assertRaisesRegex(OSError, 'disk full'):
                cp.write_file(target, core.json_bytes({'text': 'City park notice'}))
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(list(self.root.iterdir()), [target])

    def test_generate_serialization_failure_does_not_reserve_output(self):
        (self.root / 'job.json').write_text('{}', encoding='utf-8')
        with self.civil_generator([dict(CIVIL, invalid=object())]):
            with self.assertRaises(TypeError):
                cli.run(self.generation_args())
        self.assertFalse((self.root / 'output.jsonl').exists())
        with self.civil_generator([CIVIL]):
            cli.run(self.generation_args())
        self.assertEqual(core.read_jsonl(self.root / 'output.jsonl'), [CIVIL])

    def test_generate_preserves_existing_output(self):
        (self.root / 'job.json').write_text('{}', encoding='utf-8')
        target = self.root / 'output.jsonl'
        target.write_bytes(b'Existing library notice\n')
        with self.civil_generator([CIVIL]):
            with self.assertRaises(FileExistsError):
                cli.run(self.generation_args())
        self.assertEqual(target.read_bytes(), b'Existing library notice\n')

    def test_exclusive_publication_race_preserves_competing_writer(self):
        process = self.child('exclusive_race')
        self.wait_ready(process)
        target = self.root / 'record.json'
        target.write_bytes(core.json_bytes(CIVIL))
        (self.root / 'continue').write_text('continue', encoding='utf-8')
        _, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 17, stderr)
        self.assertEqual(core.read_json(target), CIVIL)
        self.assertEqual(set(self.root.iterdir()),
                         {target, self.root / 'ready', self.root / 'continue'})

    def test_exclusive_publication_failure_leaves_no_empty_output(self):
        target = self.root / 'record.json'
        with patch.object(cp.os, 'link', side_effect=OSError('simulated unsupported hard links')):
            with self.assertRaisesRegex(OSError, 'unsupported hard links'):
                cp.write_file(target, core.json_bytes(CIVIL), overwrite=False)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_partial_two_file_operation_can_resume_without_global_rollback(self):
        first = self.root / 'library.json'
        second = self.root / 'park.json'
        cp.write_file(first, core.json_bytes({'text': 'Library opens at nine.'}))
        cp.write_file(second, core.json_bytes({'text': 'Park opens at eight.'}))
        cp.write_file(first, core.json_bytes({'text': 'Library opens at ten.'}))
        with patch.object(Path, 'replace', side_effect=OSError('simulated second-file failure')):
            with self.assertRaises(OSError):
                cp.write_file(second, core.json_bytes({'text': 'Park opens at nine.'}))
        self.assertEqual(core.read_json(first), {'text': 'Library opens at ten.'})
        self.assertEqual(core.read_json(second), {'text': 'Park opens at eight.'})
        cp.write_file(second, core.json_bytes({'text': 'Park opens at nine.'}))
        self.assertEqual(core.read_json(second), {'text': 'Park opens at nine.'})
        self.assertEqual(set(self.root.iterdir()), {first, second})

    def test_interruption_before_exclusive_link_leaves_no_reserved_output(self):
        process = self.child('before_link')
        self.wait_ready(process)
        self.stop_child(process)
        target = self.root / 'record.json'
        self.assertFalse(target.exists())
        cp.write_file(target, core.json_bytes(CIVIL), overwrite=False)
        self.assertEqual(core.read_json(target), CIVIL)

    def test_interruption_after_exclusive_link_leaves_complete_output(self):
        process = self.child('after_link')
        self.wait_ready(process)
        self.stop_child(process)
        target = self.root / 'record.json'
        self.assertEqual(core.read_json(target), {'text': 'City park reopens.'})
        with self.assertRaises(FileExistsError):
            cp.write_file(target, core.json_bytes(CIVIL), overwrite=False)
        self.assertEqual(core.read_json(target), {'text': 'City park reopens.'})

    def test_cli_rejects_bad_job_without_traceback_or_output(self):
        (self.root / 'job.json').write_text('{bad', encoding='utf-8')
        process = self.child('cli')
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 1, (stdout, stderr))
        self.assertIn('Error:', stderr)
        self.assertNotIn('Traceback', stderr)
        self.assertFalse((self.root / 'output.jsonl').exists())

    def test_interruption_before_replace_keeps_old_file_and_retry_succeeds(self):
        target = self.root / 'record.json'
        target.write_bytes(core.json_bytes(CIVIL))
        process = self.child('before_replace')
        self.wait_ready(process)
        self.stop_child(process)
        self.assertEqual(core.read_json(target), CIVIL)
        # A hard kill cannot execute finally; an inert temporary file may remain.
        orphaned = set(self.root.iterdir()) - {target, self.root / 'ready'}
        self.assertEqual(len(orphaned), 1)
        retry = self.child('write')
        _, stderr = retry.communicate(timeout=10)
        self.assertEqual(retry.returncode, 0, stderr)
        self.assertEqual(core.read_json(target), {'text': 'City park reopens.'})

    def test_interruption_after_replace_leaves_complete_new_file(self):
        target = self.root / 'record.json'
        target.write_bytes(core.json_bytes(CIVIL))
        process = self.child('after_replace')
        self.wait_ready(process)
        self.stop_child(process)
        self.assertEqual(core.read_json(target), {'text': 'City park reopens.'})

    def test_lock_contention_and_recovery_after_process_kill(self):
        process = self.child('lock')
        self.wait_ready(process)
        with patch.object(cp, 'git', return_value=str(self.root)):
            with self.assertRaisesRegex(ValueError, 'already running'):
                with cp.checkpoint_lock():
                    self.fail('Contended lock was acquired')
            self.stop_child(process)
            with cp.checkpoint_lock():
                pass

    def test_lock_is_released_after_exception(self):
        with patch.object(cp, 'git', return_value=str(self.root)):
            with self.assertRaisesRegex(RuntimeError, 'civil failure'):
                with cp.checkpoint_lock():
                    raise RuntimeError('civil failure')
            with cp.checkpoint_lock():
                pass

    def test_git_wrapper_uses_only_isolated_repository_and_surfaces_errors(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        with patch.object(cp, 'ROOT', self.root):
            self.assertEqual(Path(cp.git('rev-parse', '--show-toplevel')).resolve(), self.root)
            with self.assertRaisesRegex(ValueError, 'git rev-parse failed'):
                cp.git('rev-parse', '--verify', 'refs/heads/nonexistent')

    def test_remote_response_shape_is_rejected(self):
        for response in ('', 'not-a-sha\trefs/heads/civil', 'abc\textra\tline'):
            with self.subTest(response=response), patch.object(cp, 'git', return_value=response):
                with self.assertRaises(ValueError):
                    cp.remote_head('unused-fixture-remote')

    def test_http_transport_errors_do_not_escape_as_raw_network_errors(self):
        for error in (HTTPError('http://civil.invalid', 503, 'unavailable', {}, None),
                      URLError('simulated offline')):
            with self.subTest(error=type(error).__name__), \
                 patch.dict(os.environ, {'DATASET_MODEL_BASE_URL': 'http://civil.invalid/v1'}), \
                 patch.object(model, 'urlopen', side_effect=error):
                with self.assertRaisesRegex(ValueError, 'Model request failed'):
                    model.chat('civil-fixture', 'Library notice', {'text': CIVIL['text']})

    def test_http_bad_json_response_is_rejected_without_real_request(self):
        with patch.dict(os.environ, {'DATASET_MODEL_BASE_URL': 'http://civil.invalid/v1'}), \
             patch.object(model, 'urlopen', return_value=io.BytesIO(b'{broken')):
            with self.assertRaises(ValueError):
                model.chat('civil-fixture', 'Library notice', CIVIL)


if __name__ == '__main__':
    unittest.main()
