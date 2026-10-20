"""Offline regression checks for cost guards, single submission and recovery."""
import argparse
import hashlib
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import free_media as media


class GuardsAndRecovery(unittest.TestCase):
    def test_rejects_paid_runtime_and_changed_revision(self):
        backend = media.BACKENDS['video']
        for runtime in (
            {'stage': 'RUNNING', 'hardware': {'current': 'a100-large'}, 'sha': backend['revision']},
            {'stage': 'RUNNING', 'hardware': {'current': 'zero-a10g'}, 'sha': 'unreviewed'},
        ):
            client = mock.Mock()
            client.json.return_value = runtime
            with self.assertRaises(media.Stopped):
                media.inspect(client, backend)
            self.assertEqual(client.json.call_count, 1)

    def test_rejects_external_url_and_never_attaches_credentials(self):
        backend = media.BACKENDS['image']
        for url in ('http://127.0.0.1/file', 'https://example.com/file',
                    'https://user:password@huggingface.co/file'):
            with self.assertRaises(media.Stopped):
                media.allowed_url(url, backend)
        with mock.patch.dict('os.environ', {'HF_TOKEN': 'dummy-test-token'}):
            client = media.PublicClient(backend)
            client.opener = mock.Mock()
            client.open(backend['base'] + '/config')
        request = client.opener.open.call_args.args[0]
        self.assertFalse(request.has_header('Authorization'))
        self.assertFalse(request.has_header('Cookie'))

    def test_sse_multiline_complete_and_error(self):
        stream = io.BytesIO(b'event: heartbeat\ndata: null\n\nevent: complete\ndata: [\ndata: {"url":"x"}, 42]\n\n')
        self.assertEqual(list(media.events(stream)), [('heartbeat', None), ('complete', [{'url': 'x'}, 42])])

    def test_lock_prevents_concurrent_collection_and_releases(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = pathlib.Path(folder)
            with media.request_lock(directory):
                with self.assertRaises(media.Stopped):
                    with media.request_lock(directory):
                        self.fail('A second process acquired the same request.')
            with media.request_lock(directory):
                pass

    def test_quota_error_submits_only_once_and_preserves_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = pathlib.Path(folder)
            prompt = directory / 'prompt.txt'
            prompt.write_text('A garden at dawn.')
            args = argparse.Namespace(backend='image', width=512, height=512, seed=42,
                                      duration=2.0, reference=[], prompt_file=str(prompt),
                                      output_dir=str(directory / 'result'))
            client = mock.Mock()
            client.json.return_value = {'event_id': 'saved-job'}
            client.open.return_value = io.BytesIO(b'event: error\ndata: "GPU quota exceeded"\n\n')
            with mock.patch.object(media, 'PublicClient', return_value=client), \
                    mock.patch.object(media, 'inspect', return_value={'auth': 'anonymous'}):
                with self.assertRaises(media.Stopped):
                    media.generate(args)
                with self.assertRaises(media.Stopped):
                    media.generate(args)
            self.assertEqual(client.json.call_count, 1)
            record = json.loads((directory / 'result' / 'request.json').read_text())
            self.assertEqual(record['state'], 'failed')
            self.assertEqual(record['event_id'], 'saved-job')

    def test_recovers_published_output_without_new_generation_or_download(self):
        backend = media.BACKENDS['image']
        with tempfile.TemporaryDirectory() as folder:
            directory = pathlib.Path(folder)
            output = directory / 'output.png'
            contents = b'known-result-bytes'
            output.write_bytes(contents)
            record = {'backend': 'image', 'state': 'unknown', 'event_id': 'saved-job',
                      'result': [{'url': backend['base'] + '/gradio_api/file=/tmp/output.png'}, 42],
                      'download': {'path': str(output), 'bytes': len(contents),
                                   'sha256': hashlib.sha256(contents).hexdigest()}}
            manifest = directory / 'request.json'
            media.save_manifest(manifest, record)
            client = mock.Mock()
            media.collect(client, backend, record, manifest)
            client.open.assert_not_called()
            client.json.assert_not_called()
            self.assertEqual(json.loads(manifest.read_text())['state'], 'complete')
            self.assertEqual(output.read_bytes(), contents)

    def test_does_not_accept_or_overwrite_corrupt_existing_output(self):
        backend = media.BACKENDS['image']
        with tempfile.TemporaryDirectory() as folder:
            directory = pathlib.Path(folder)
            output = directory / 'output.png'
            output.write_bytes(b'corrupt')
            record = {'download': {'path': str(output), 'bytes': 7, 'sha256': 'wrong'}}
            client = mock.Mock()
            with self.assertRaises(media.Stopped):
                media.download_result(client, backend,
                                      [{'url': backend['base'] + '/gradio_api/file=/tmp/output.png'}],
                                      directory, record, directory / 'request.json')
            client.open.assert_not_called()
            self.assertEqual(output.read_bytes(), b'corrupt')


if __name__ == '__main__':
    unittest.main()
