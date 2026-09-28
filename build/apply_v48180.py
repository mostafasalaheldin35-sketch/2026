from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
SRC=ROOT/'buildsrc'
if not (SRC/'backend.py').is_file():
    raise SystemExit(f'buildsrc not found under {ROOT}')

# 1) Fix the v4.8.17.9 sync-page MutationObserver feedback loop.
js=SRC/'app'/'v4179_patch.js'
s=js.read_text(encoding='utf-8')
old_sync="""async function sync79(){const v=$('view-sync');if(!v)return;qa('.s77-backup-row',v).forEach(r=>{if(/أسبوعي|شهري|Weekly|Monthly/i.test(r.textContent))r.remove()});qa('*',v).forEach(el=>{if(el.childElementCount===0&&typeof el.textContent==='string'){el.textContent=el.textContent.replace(/Daily \/ Weekly \/ Monthly \/ Manual/g,'Daily / Manual').replace(/Live \/ Daily \/ Weekly \/ Monthly \/ Manual/g,'Live / Daily / Manual')}});if(!v.querySelector('.sync79-settings')){const host=v.querySelector('.s77-grid,.sync-workspace')||v;const box=document.createElement('div');box.className='sync79-settings';box.innerHTML=`<h3>إعدادات النسخ اليومية</h3><div class="sync79-settings-grid"><label>الاحتفاظ بالنسخ اليومية لمدة (يوم)<input type="number" min="1" max="3650" id="dailyRetention79" value="30"></label><button type="button" class="primary" id="saveRetention79">حفظ</button></div><div class="mini" id="attachmentIndex79" style="margin-top:7px"></div>`;host.prepend(box);try{const s=await api79('/api/v4179-settings');$('dailyRetention79').value=s.dailyRetentionDays||30;$('attachmentIndex79').textContent='فهرس المرفقات: '+(s.attachmentIndex||'—')}catch{}$('saveRetention79').onclick=async()=>{try{const r=await api79('/api/v4179-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dailyRetentionDays:Number($('dailyRetention79').value||30)})});toast(`تم ضبط الاحتفاظ على ${r.dailyRetentionDays} يوم`)}catch(e){toast(e.message)}}}}
new MutationObserver(()=>{if($('view-sync')?.classList.contains('active'))sync79()}).observe(document.body,{subtree:true,childList:true});
setTimeout(()=>{if($('view-sync')?.classList.contains('active'))sync79()},500);"""
new_sync="""async function sync79(){const v=$('view-sync');if(!v)return;qa('.s77-backup-row',v).forEach(r=>{if(/أسبوعي|شهري|Weekly|Monthly/i.test(r.textContent))r.remove()});qa('*',v).forEach(el=>{if(el.childElementCount===0&&typeof el.textContent==='string'){const current=el.textContent;const next=current.replace(/Daily \/ Weekly \/ Monthly \/ Manual/g,'Daily / Manual').replace(/Live \/ Daily \/ Weekly \/ Monthly \/ Manual/g,'Live / Daily / Manual');if(next!==current)el.textContent=next}});if(!v.querySelector('.sync79-settings')){const host=v.querySelector('.s77-grid,.sync-workspace')||v;const box=document.createElement('div');box.className='sync79-settings';box.innerHTML=`<h3>إعدادات النسخ اليومية</h3><div class="sync79-settings-grid"><label>الاحتفاظ بالنسخ اليومية لمدة (يوم)<input type="number" min="1" max="3650" id="dailyRetention79" value="30"></label><button type="button" class="primary" id="saveRetention79">حفظ</button></div><div class="mini" id="attachmentIndex79" style="margin-top:7px"></div>`;host.prepend(box);try{const s=await api79('/api/v4179-settings');$('dailyRetention79').value=s.dailyRetentionDays||30;$('attachmentIndex79').textContent='فهرس المرفقات: '+(s.attachmentIndex||'—')}catch{}$('saveRetention79').onclick=async()=>{try{const r=await api79('/api/v4179-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dailyRetentionDays:Number($('dailyRetention79').value||30)})});toast(`تم ضبط الاحتفاظ على ${r.dailyRetentionDays} يوم`)}catch(e){toast(e.message)}}}}
let sync79Busy=false,sync79Queued=false;
async function runSync79(){if(sync79Busy){sync79Queued=true;return}sync79Busy=true;try{do{sync79Queued=false;await sync79()}while(sync79Queued)}finally{sync79Busy=false}}
const renderSyncBefore79=window.renderSync;window.renderSync=async function(...args){const result=await renderSyncBefore79.apply(this,args);await runSync79();return result};
setTimeout(()=>{if($('view-sync')?.classList.contains('active'))runSync79()},500);"""
if old_sync not in s:
    raise SystemExit('Expected v4.8.17.9 sync observer block not found')
s=s.replace(old_sync,new_sync)
old_bulk="new MutationObserver(()=>{if($('view-inspection-detail')?.classList.contains('active'))installBulkTarget()}).observe(document.body,{subtree:true,childList:true});"
new_bulk="const inspectionDetail79=$('view-inspection-detail');if(inspectionDetail79)new MutationObserver(()=>{if(inspectionDetail79.classList.contains('active'))installBulkTarget()}).observe(inspectionDetail79,{subtree:true,childList:true});"
if old_bulk not in s: raise SystemExit('Expected global inspection observer not found')
s=s.replace(old_bulk,new_bulk)
old_selector='#inspectionAnalyticsBtn,[data-action="inspection-analytics"]'
new_selector='#openInspectionAnalyticsBtn,#inspectionAnalyticsBtn,[data-action="inspection-analytics"]'
if old_selector not in s: raise SystemExit('Expected analytics selector not found')
s=s.replace(old_selector,new_selector)
js.write_text(s,encoding='utf-8')

# 2) Restore stale-instance recovery and bound startup work.
be=SRC/'v4179_backend_ext.py'
s=be.read_text(encoding='utf-8')
old_idle="""    # ------------------------------------------------------------------
    # Local service lifetime: do NOT infer app close from browser timer gaps.
    # ------------------------------------------------------------------
    def start_idle_shutdown(server):
        return None
    ns['start_idle_shutdown']=start_idle_shutdown
"""
new_idle="""    # ------------------------------------------------------------------
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
if old_idle not in s: raise SystemExit('Expected disabled idle-shutdown block not found')
s=s.replace(old_idle,new_idle)
old_index="""    # Wrap init so the index exists before any later accidental loss.
    old_init=Store.__init__
    def __init__(self,*a,**kw):
        old_init(self,*a,**kw)
        try:self.refresh_attachment_index()
        except Exception:pass
    Store.__init__=__init__
"""
new_index="""    # Keep startup bounded: create the metadata index schema immediately,
    # but defer full-file hashing to maintenance / explicit audit.
    old_init=Store.__init__
    def __init__(self,*a,**kw):
        old_init(self,*a,**kw)
        try:
            con=self._idx_conn();con.close()
        except Exception:pass
    Store.__init__=__init__
"""
if old_index not in s: raise SystemExit('Expected synchronous attachment-index startup block not found')
s=s.replace(old_index,new_index)
s=s.replace("ns['APP_VERSION']='4.8.17.9-DESKTOP'","ns['APP_VERSION']='4.8.18.0-DESKTOP'")
s=s.replace("Handler.server_version='CompanyInspectionDesktop/4.8.17.9'","Handler.server_version='CompanyInspectionDesktop/4.8.18.0'")
be.write_text(s,encoding='utf-8')

# 3) Runtime/UI version.
idx=SRC/'app'/'index.html'
s=idx.read_text(encoding='utf-8')
old="const APP_VERSION='4.8.17.9-DESKTOP'"
if old not in s: raise SystemExit('Expected v4.8.17.9 UI version not found')
s=s.replace(old,"const APP_VERSION='4.8.18.0-DESKTOP'",1)
idx.write_text(s,encoding='utf-8')
print('Applied Sokhna Port v4.8.18.0 stability corrections')
