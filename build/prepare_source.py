from __future__ import annotations
import hashlib, json, shutil, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'Sokhna-Port-2026-Approved-Baseline.zip'
BUILD=ROOT/'buildsrc'
EXPECTED={
    'app/index.html':'61a7f549eecb803a7996c528302774ba5d1f89083e811da53cffe70be37f1705',
    'app/manifest.json':'252b34437a0bf4c0feb8e2049a1ef0b6934376a704a3fd696dee6e7bb45d4a14',
    'backend.py':'8d36add532e94daa9854ffa882292dc6a818a9737b957520fbc132d926f253ac',
    'launcher.py':'ed7513ed0ad5e43faa02e88766956c4328ee75ab376223c803699ffc469245a8',
}
def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
if not PACK.is_file():
    raise SystemExit('Missing approved baseline pack: Sokhna-Port-2026-Approved-Baseline.zip')
if BUILD.exists(): shutil.rmtree(BUILD)
BUILD.mkdir(parents=True)
with zipfile.ZipFile(PACK) as z:
    z.extractall(BUILD)
for rel,want in EXPECTED.items():
    p=BUILD/rel
    if not p.is_file(): raise SystemExit(f'Missing baseline file: {rel}')
    got=sha(p)
    if got!=want: raise SystemExit(f'Baseline SHA mismatch for {rel}: {got} != {want}')
print('APPROVED BASELINE VERIFIED')
for rel in EXPECTED: print(rel,EXPECTED[rel])
