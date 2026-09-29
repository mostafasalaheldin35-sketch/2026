from pathlib import Path
import os, sys, threading, time

ROOT=Path(__file__).resolve().parent.parent/'buildsrc'
sys.path.insert(0,str(ROOT))
import backend

assert backend.APP_VERSION=='4.8.18.1-DESKTOP', backend.APP_VERSION
be=(ROOT/'v4179_backend_ext.py').read_text(encoding='utf-8')
html=(ROOT/'app'/'index.html').read_text(encoding='utf-8')
js=(ROOT/'app'/'v48181_refresh.js').read_text(encoding='utf-8')

assert "def start_idle_shutdown(server):\n        return None" in be
assert "SOKHNA_IDLE_SHUTDOWN_SECONDS" not in be
assert "const APP_VERSION='4.8.18.1-DESKTOP'" in html
assert '<script src="v48181_refresh.js"></script>' in html

for token in ("visibilitychange","pageshow","focus","online","WAKE_GAP_MS","/api/health","sokhnaRefreshConnection"):
    assert token in js, token
for forbidden in ("location.reload","method:'POST'","method:\"POST\"","/api/shutdown"):
    assert forbidden not in js, forbidden

class FakeServer:
    def __init__(self): self.stopped=threading.Event()
    def shutdown(self): self.stopped.set()

os.environ['SOKHNA_IDLE_SHUTDOWN_SECONDS']='1'
backend.note_heartbeat()
fake=FakeServer()
backend.start_idle_shutdown(fake)
assert not fake.stopped.wait(2.5), 'service shut down because of a heartbeat timing gap'
os.environ.pop('SOKHNA_IDLE_SHUTDOWN_SECONDS',None)

print('v4.8.18.1 REFRESH-ONLY BACKEND/STATIC QA PASS')
