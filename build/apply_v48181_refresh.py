from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
SRC=ROOT/'buildsrc'
if not (SRC/'backend.py').is_file():
    raise SystemExit(f'buildsrc not found under {ROOT}')

# Refresh-only release on top of the reviewed Codex v4.8.18.0 source.
# Intentionally leave all storage/sync/Excel/analytics/business logic untouched.

be=SRC/'v4179_backend_ext.py'
s=be.read_text(encoding='utf-8')
old="""    # ------------------------------------------------------------------
    # Local service lifetime: recover cleanly when the app window disappears
    # or its renderer becomes unresponsive. A generous production timeout
    # avoids false shutdown from normal timer throttling/minimization.
    # ------------------------------------------------------------------
    def start_idle_shutdown(server):
        import threading
        def worker():
            try: idle_limit=max(1.0,float(os.environ.get('SOKHNA_IDLE_SHUTDOWN_SECONDS','120')))
            except Exception: idle_limit=120.0
            while True:
                time.sleep(min(5.0,max(0.2,idle_limit/4.0)))
                lock=ns.get('HEARTBEAT_LOCK')
                if lock is None: continue
                with lock:
                    started=bool(ns.get('HEARTBEAT_STARTED',False))
                    last=float(ns.get('LAST_HEARTBEAT',0.0) or 0.0)
                if started and last and time.time()-last>idle_limit:
                    try: server.shutdown()
                    except Exception: pass
                    return
        threading.Thread(target=worker,daemon=True,name='sokhna-idle-shutdown').start()
    ns['start_idle_shutdown']=start_idle_shutdown
"""
new="""    # ------------------------------------------------------------------
    # Local service lifetime: do not infer application close from heartbeat
    # gaps. Windows sleep and Edge timer throttling can pause browser timers
    # for minutes while the user still expects the desktop app to remain live.
    # Connection recovery is handled by the UI with safe GET-only health checks.
    # ------------------------------------------------------------------
    def start_idle_shutdown(server):
        return None
    ns['start_idle_shutdown']=start_idle_shutdown
"""
if old not in s:
    raise SystemExit('Expected v4.8.18.0 idle-shutdown block not found')
s=s.replace(old,new,1)
if "ns['APP_VERSION']='4.8.18.0-DESKTOP'" not in s:
    raise SystemExit('Expected v4.8.18.0 backend version not found')
s=s.replace("ns['APP_VERSION']='4.8.18.0-DESKTOP'","ns['APP_VERSION']='4.8.18.1-DESKTOP'",1)
s=s.replace("Handler.server_version='CompanyInspectionDesktop/4.8.18.0'","Handler.server_version='CompanyInspectionDesktop/4.8.18.1'",1)
be.write_text(s,encoding='utf-8')

idx=SRC/'app'/'index.html'
h=idx.read_text(encoding='utf-8')
if "const APP_VERSION='4.8.18.0-DESKTOP'" not in h:
    raise SystemExit('Expected v4.8.18.0 UI version not found')
h=h.replace("const APP_VERSION='4.8.18.0-DESKTOP'","const APP_VERSION='4.8.18.1-DESKTOP'",1)
anchor='<link rel="stylesheet" href="v4177_patch.css"><script src="v4177_patch.js"></script><link rel="stylesheet" href="v4179_patch.css"><script src="v4179_patch.js"></script>'
if anchor not in h:
    raise SystemExit('Expected v4.8.18.0 asset anchor not found')
h=h.replace(anchor,anchor+'<script src="v48181_refresh.js"></script>',1)
idx.write_text(h,encoding='utf-8')

refresh=SRC/'app'/'v48181_refresh.js'
refresh.write_text(r"""(()=>{
'use strict';

/* v4.8.18.1: connection-only auto refresh / reconnect.
   - GET only: never repeats POST/PUT/DELETE or any save/backup action.
   - No full page reload: avoids losing unsaved form state.
   - Runs on focus/visibility/pageshow/online and after a detected sleep gap.
   - The backend is intentionally not closed because of heartbeat timing gaps. */
const HEALTH_URL='/api/health';
const CHECK_EVERY_MS=30000;
const WAKE_GAP_MS=45000;
const REQUEST_TIMEOUT_MS=4000;
const RETRY_DELAYS_MS=[1000,2000,5000,10000,15000,30000];
let checking=false;
let retryTimer=0;
let retryStep=0;
let disconnected=false;
let lastTick=Date.now();

function clearRetry(){
  if(retryTimer){clearTimeout(retryTimer);retryTimer=0;}
}
function scheduleRetry(){
  if(retryTimer)return;
  const delay=RETRY_DELAYS_MS[Math.min(retryStep,RETRY_DELAYS_MS.length-1)];
  retryStep++;
  retryTimer=setTimeout(()=>{retryTimer=0;checkConnection('retry');},delay);
}
async function checkConnection(reason='manual'){
  if(checking)return false;
  checking=true;
  const controller=typeof AbortController==='function'?new AbortController():null;
  const timer=controller?setTimeout(()=>controller.abort(),REQUEST_TIMEOUT_MS):0;
  try{
    const response=await fetch(HEALTH_URL,{cache:'no-store',signal:controller?.signal});
    if(!response.ok)throw new Error('HTTP '+response.status);
    const payload=await response.json();
    if(!payload||payload.ok!==true)throw new Error('health check failed');
    const recovered=disconnected;
    disconnected=false;
    retryStep=0;
    clearRetry();
    if(recovered){
      try{window.dispatchEvent(new CustomEvent('sokhna:reconnected',{detail:{reason}}));}catch(_e){}
    }
    return true;
  }catch(_err){
    disconnected=true;
    scheduleRetry();
    return false;
  }finally{
    if(timer)clearTimeout(timer);
    checking=false;
  }
}

function immediateCheck(reason){
  Promise.resolve().then(()=>checkConnection(reason)).catch(()=>{});
}

document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='visible')immediateCheck('visible');
});
window.addEventListener('focus',()=>immediateCheck('focus'));
window.addEventListener('pageshow',()=>immediateCheck('pageshow'));
window.addEventListener('online',()=>immediateCheck('online'));

setInterval(()=>{
  const now=Date.now();
  const gap=now-lastTick;
  lastTick=now;
  if(gap>WAKE_GAP_MS){immediateCheck('wake');return;}
  if(document.visibilityState==='visible')immediateCheck('interval');
},CHECK_EVERY_MS);

setTimeout(()=>immediateCheck('startup'),1500);
window.sokhnaRefreshConnection=()=>checkConnection('manual');
})();
""",encoding='utf-8')

print('Applied refresh-only v4.8.18.1 changes')
