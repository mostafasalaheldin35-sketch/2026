from pathlib import Path
import base64, gzip, hashlib, shutil

ROOT=Path(__file__).resolve().parent.parent
clean=ROOT/'build'/'v4174_backend_clean.py'
target=ROOT/'buildsrc'/'backend.py'
payload=ROOT/'build'/'v4175_backend_ext.b64'
ext=ROOT/'buildsrc'/'v4175_backend_ext.py'

if not clean.is_file():
    raise SystemExit('Missing clean v4.8.17.4 backend snapshot')
if not payload.is_file():
    raise SystemExit('Missing v4.8.17.5 backend extension payload')

raw=gzip.decompress(base64.b64decode(payload.read_text(encoding='ascii').strip(), validate=True))
expected='a4fa126cc26a176b3cb9aa4bea8930436b762f90f94fa4173cd6a30df2b8c28e'
digest=hashlib.sha256(raw).hexdigest()
if digest != expected:
    raise SystemExit(f'v4.8.17.5 backend extension SHA mismatch: {digest}')
ext.write_bytes(raw)

source=clean.read_text(encoding='utf-8')
marker='\ndef main() -> int:\n'
if marker not in source:
    raise SystemExit('backend main marker missing')
install='\n# Master Attachments are not duplicated inside Recovery backups.\nimport v4175_backend_ext as _v4175_backend_ext\n_v4175_backend_ext.install(globals())\n'
source=source.replace(marker,install+marker,1)
target.write_text(source,encoding='utf-8',newline='\n')
print('v4.8.17.5 clean backend + extension installed:', digest)
