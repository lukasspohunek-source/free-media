#!/usr/bin/env python3
"""Two reviewed public ZeroGPU backends. Standard library; anonymous requests only."""
import argparse
import contextlib
import hashlib
import json
import mimetypes
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BACKENDS = {
    'image': {
        'space': 'black-forest-labs/FLUX.2-klein-4B',
        'base': 'https://black-forest-labs-flux-2-klein-4b.hf.space',
        'revision': '0207e56c7ec73975b6ebeadfaf88c8d338d61a8d',
        'model': 'black-forest-labs/FLUX.2-klein-4B',
        'endpoint': 'infer',
        'parameters': ['prompt', 'input_images', 'mode_choice', 'seed', 'randomize_seed',
                       'width', 'height', 'num_inference_steps', 'guidance_scale', 'prompt_upsampling'],
        'defaults': (1024, 576), 'grid': 8, 'min_size': 256, 'max_size': 1024,
    },
    'video': {
        'space': 'Lightricks/LTX-2.5',
        'base': 'https://lightricks-ltx-2-5.hf.space',
        'revision': 'c42e4cd512ec0a861024699f031538eb7bf093a7',
        'model': 'Lightricks/LTX-2.5-Diffusers',
        'endpoint': 'run',
        'parameters': ['prompt', 'image_path', 'height', 'width', 'duration_s', 'seed', 'decoder',
                       'auto_len', 'randomize_seed', 'do_enhance'],
        'defaults': (896, 512), 'grid': 64, 'min_size': 512, 'max_size': 1536,
    },
}
MAX_FILE_BYTES = 64 * 1024 * 1024


class Stopped(RuntimeError):
    pass


def emit(**value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def allowed_url(url, backend):
    parsed = urllib.parse.urlsplit(url)
    hosts = {'huggingface.co', urllib.parse.urlsplit(backend['base']).hostname}
    if (parsed.scheme != 'https' or parsed.hostname not in hosts or parsed.username
            or parsed.password or parsed.port not in (None, 443)):
        raise Stopped('Unexpected remote URL. Review it; do not forward credentials or files.')
    return url


class CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, backend):
        self.backend = backend

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        allowed_url(newurl, self.backend)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PublicClient:
    def __init__(self, backend):
        self.backend = backend
        # No token, auth handler, cookie jar, browser session or credential discovery.
        self.opener = urllib.request.build_opener(CheckedRedirect(backend))

    def open(self, url, data=None, content_type=None):
        headers = {'User-Agent': 'free-media/1.0'}
        if content_type:
            headers['Content-Type'] = content_type
        req = urllib.request.Request(allowed_url(url, self.backend), data=data, headers=headers)
        try:
            return self.opener.open(req, timeout=45)
        except urllib.error.HTTPError as exc:
            detail = exc.read(2048).decode('utf-8', errors='replace')
            raise Stopped(f'HTTP {exc.code}: {detail}. No automatic retry or paid fallback.') from None

    def json(self, url, data=None):
        payload = None if data is None else json.dumps(data).encode()
        with self.open(url, payload, 'application/json' if payload else None) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise Stopped('Unexpectedly large API response.')
        return json.loads(raw)


def inspect(client, backend):
    runtime = client.json('https://huggingface.co/api/spaces/' + backend['space'] + '/runtime')
    if runtime.get('stage') != 'RUNNING':
        raise Stopped('Space is not RUNNING. Stop; do not provision a paid GPU.')
    if not runtime.get('hardware', {}).get('current', '').startswith('zero-'):
        raise Stopped('Space is not on ZeroGPU. Free-only check failed.')
    if runtime.get('sha') != backend['revision']:
        raise Stopped('Space revision changed. Review its code and cost path before updating this preset.')
    info = client.json(backend['base'] + '/gradio_api/info')
    endpoint = info.get('named_endpoints', {}).get('/' + backend['endpoint'], {})
    names = [item.get('parameter_name') for item in endpoint.get('parameters', [])]
    if names != backend['parameters'] or endpoint.get('api_visibility') != 'public':
        raise Stopped('Public API schema changed. Review before generating.')
    return {'space': backend['space'], 'revision': runtime['sha'], 'model': backend['model'],
            'hardware': runtime['hardware']['current'], 'endpoint': '/' + backend['endpoint'],
            'auth': 'anonymous', 'enhancer': False, 'automatic_retry': False,
            'schema_sha256': hashlib.sha256(json.dumps(endpoint, sort_keys=True).encode()).hexdigest()}


def validate(args, backend):
    args.width = backend['defaults'][0] if args.width is None else args.width
    args.height = backend['defaults'][1] if args.height is None else args.height
    for side in (args.width, args.height):
        if not backend['min_size'] <= side <= backend['max_size'] or side % backend['grid']:
            raise Stopped(f'Dimensions must be {backend["min_size"]}–{backend["max_size"]}, '
                          f'divisible by {backend["grid"]}.')
    if not 0 <= args.seed <= 2**31 - 1:
        raise Stopped('Seed must be an integer from 0 to 2147483647.')
    if not 1 <= args.duration <= 5 or args.duration * 2 != int(args.duration * 2):
        raise Stopped('Video duration must be 1–5 seconds in half-second steps.')
    if args.backend == 'video' and len(args.reference) > 1:
        raise Stopped('This video preset accepts one starting image.')
    # A modest client limit, not a claim about the model maximum.
    if len(args.reference) > 4:
        raise Stopped('This client accepts up to four image references per request.')
    references = []
    for path in args.reference:
        path = pathlib.Path(path).resolve()
        if not path.is_file() or not 0 < path.stat().st_size <= 15 * 1024 * 1024:
            raise Stopped('Each reference must be a regular image file under 15 MiB.')
        if path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
            raise Stopped('Reference types: PNG, JPEG or WebP.')
        references.append(path)
    prompt = pathlib.Path(args.prompt_file).read_text(encoding='utf-8').strip()
    if not prompt or len(prompt) > 12000:
        raise Stopped('Supply a nonempty UTF-8 prompt of at most 12000 characters.')
    return prompt, references


def upload(client, backend, path):
    boundary = 'free-media-' + uuid.uuid4().hex
    filename = 'reference' + path.suffix.lower()
    mime = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\n'
            f'Content-Type: {mime}\r\n\r\n').encode() + path.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
    with client.open(backend['base'] + '/gradio_api/upload', body,
                     'multipart/form-data; boundary=' + boundary) as response:
        result = json.loads(response.read(1024 * 1024))
    if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], str):
        raise Stopped('Unexpected upload result.')
    return {'path': result[0], 'orig_name': filename, 'meta': {'_type': 'gradio.FileData'}}


def payload(args, prompt, uploaded):
    if args.backend == 'image':
        gallery = [{'image': item, 'caption': None} for item in uploaded]
        return [prompt, gallery, 'Distilled (4 steps)', args.seed, False,
                args.width, args.height, 4, 1.0, False]
    return [prompt, uploaded[0] if uploaded else None, args.height, args.width,
            args.duration, args.seed, 'conv', False, False, False]


def save_manifest(path, record):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


@contextlib.contextmanager
def request_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / '.request.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise Stopped('This request is locked by another process. If a process crashed, '
                      'confirm it is no longer running before removing its lock.') from None
    try:
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def events(stream):
    kind, data = '', []
    for raw in stream:
        line = raw.decode('utf-8').rstrip('\r\n')
        if not line:
            if data:
                yield kind, json.loads('\n'.join(data))
            kind, data = '', []
        elif line.startswith('event:'):
            kind = line[6:].strip()
        elif line.startswith('data:'):
            data.append(line[5:].lstrip())


def download_result(client, backend, result, directory, record, manifest):
    item = result[0]
    if isinstance(item, dict) and isinstance(item.get('video'), dict):
        item = item['video']
    if not isinstance(item, dict) or not item.get('url'):
        raise Stopped('Result has no downloadable file URL. The complete response is saved.')
    url = allowed_url(item['url'], backend)
    # Generation output must originate at the reviewed Space, not another Hub repository.
    if urllib.parse.urlsplit(url).hostname != urllib.parse.urlsplit(backend['base']).hostname:
        raise Stopped('Output URL does not belong to the selected Space.')
    suffix = pathlib.PurePosixPath(urllib.parse.unquote(urllib.parse.urlsplit(url).path)).suffix.lower()
    valid = ('.png', '.jpg', '.jpeg', '.webp') if backend is BACKENDS['image'] else ('.mp4', '.webm')
    if suffix not in valid:
        raise Stopped('Unexpected output file type. Inspect the saved result.')
    output = directory / ('output' + suffix)
    if output.exists():
        expected = record.get('download', {})
        if (expected.get('path') == str(output) and output.is_file()
                and output.stat().st_size == expected.get('bytes')
                and hashlib.sha256(output.read_bytes()).hexdigest() == expected.get('sha256')):
            return expected
        raise Stopped('An existing output does not match the recorded download. No overwrite.')
    temporary = directory / ('output' + suffix + '.part')
    total, digest = 0, hashlib.sha256()
    with client.open(url) as response, temporary.open('wb') as destination:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise Stopped('Output exceeded the 64 MiB transfer limit.')
            digest.update(chunk)
            destination.write(chunk)
    if not total:
        raise Stopped('Empty output file.')
    expected = {'path': str(output), 'bytes': total, 'sha256': digest.hexdigest()}
    # A resumed request can verify a file published just before an interrupted manifest update.
    record['download'] = expected
    save_manifest(manifest, record)
    temporary.replace(output)
    return expected


def collect(client, backend, record, manifest):
    event_id = record.get('event_id', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', event_id):
        raise Stopped('No valid event ID to resume; do not submit another job automatically.')
    if record.get('result') is None:
        url = backend['base'] + '/gradio_api/call/' + backend['endpoint'] + '/' + event_id
        start, last_update = time.monotonic(), 0
        with client.open(url) as stream:
            for event, data in events(stream):
                elapsed = time.monotonic() - start
                if elapsed > 300:
                    raise Stopped('Result wait exceeded five minutes. Resume this event ID later.')
                if event == 'error':
                    record.update(state='failed', remote_error=data)
                    save_manifest(manifest, record)
                    raise Stopped('Free Space error: ' + json.dumps(data, ensure_ascii=False))
                if event == 'complete':
                    record.update(state='generated', result=data, result_wait_s=round(elapsed, 2))
                    save_manifest(manifest, record)
                    break
                if elapsed - last_update >= 25:
                    emit(state='waiting', elapsed_s=round(elapsed), event_id=event_id)
                    last_update = elapsed
        if record.get('result') is None:
            raise Stopped('Stream ended without completion. Resume the saved event; do not resubmit.')
    output = download_result(client, backend, record['result'], manifest.parent, record, manifest)
    record.update(state='complete', output=output)
    record.pop('error', None)
    save_manifest(manifest, record)
    emit(state='complete', output=output['path'], manifest=str(manifest), bytes=output['bytes'])


def generate(args):
    backend = BACKENDS[args.backend]
    prompt, references = validate(args, backend)
    directory = pathlib.Path(args.output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / 'request.json'
    # Exclusive creation prevents a second invocation from submitting the same request twice.
    try:
        with manifest.open('x') as handle:
            handle.write('{}')
    except FileExistsError:
        raise Stopped('request.json exists. Inspect it or resume its event ID; use a new directory for a new job.')
    record = {'backend': args.backend, 'state': 'checking', 'prompt': prompt, 'seed': args.seed,
              'width': args.width, 'height': args.height,
              'duration_s': args.duration if args.backend == 'video' else None,
              'references': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in references]}
    save_manifest(manifest, record)
    client = PublicClient(backend)
    try:
        record.update(inspect(client, backend), state='uploading')
        save_manifest(manifest, record)
        uploaded = [upload(client, backend, p) for p in references]
        record['state'] = 'submitting'
        save_manifest(manifest, record)
        response = client.json(backend['base'] + '/gradio_api/call/' + backend['endpoint'],
                               {'data': payload(args, prompt, uploaded)})
        record.update(event_id=response['event_id'], state='queued')
        save_manifest(manifest, record)
        emit(state='queued', backend=args.backend, event_id=record['event_id'], manifest=str(manifest))
        collect(client, backend, record, manifest)
    except Exception as exc:
        if record['state'] not in ('complete', 'failed'):
            record['state'] = 'unknown' if record['state'] in ('submitting', 'queued', 'generated') else 'stopped'
        record['error'] = str(exc)
        save_manifest(manifest, record)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('inspect', help='Read-only runtime, revision and schema checks.')
    check.add_argument('--backend', choices=BACKENDS, required=True)
    run = commands.add_parser('generate', help='Submit exactly one anonymous free request.')
    run.add_argument('--backend', choices=BACKENDS, required=True)
    run.add_argument('--prompt-file', required=True)
    run.add_argument('--reference', action='append', default=[])
    run.add_argument('--output-dir', required=True)
    run.add_argument('--width', type=int)
    run.add_argument('--height', type=int)
    run.add_argument('--duration', type=float, default=2.0)
    run.add_argument('--seed', type=int, default=2402)
    resume = commands.add_parser('resume', help='Collect one saved job without submitting a new one.')
    resume.add_argument('--manifest', required=True)
    args = parser.parse_args()
    if args.command == 'inspect':
        backend = BACKENDS[args.backend]
        emit(state='ready', **inspect(PublicClient(backend), backend))
    elif args.command == 'generate':
        with request_lock(pathlib.Path(args.output_dir).resolve()):
            generate(args)
    else:
        manifest = pathlib.Path(args.manifest).resolve()
        with request_lock(manifest.parent):
            record = json.loads(manifest.read_text())
            if record.get('state') in ('complete', 'failed', 'stopped'):
                raise Stopped('This request is already terminal. No new generation or duplicate download.')
            backend = BACKENDS[record['backend']]
            collect(PublicClient(backend), backend, record, manifest)


if __name__ == '__main__':
    try:
        main()
    except (Stopped, OSError, ValueError, KeyError, TypeError) as exc:
        emit(state='stopped', error=str(exc), paid_fallback=False, automatic_retry=False)
        raise SystemExit(1)
