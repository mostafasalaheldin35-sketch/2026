from pathlib import Path
import json, shutil, subprocess, sys, tempfile, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parent
base=Path(tempfile.mkdtemp(prefix='sokhna_http48180_')); port=18818; proc=None

def req(method,path,body=None,timeout=30):
    data=None if body is None else json.dumps(body,ensure_ascii=False).encode('utf-8')
    headers={'Content-Type':'application/json'} if body is not None else {}
    r=urllib.request.Request(f'http://127.0.0.1:{port}{path}',data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(r,timeout=timeout) as x:
            raw=x.read();status=x.status;ct=x.headers.get('Content-Type','')
    except urllib.error.HTTPError as e:
        raw=e.read();status=e.code;ct=e.headers.get('Content-Type','')
    obj=json.loads(raw.decode('utf-8')) if raw and 'json' in ct else None
    return status,obj,raw
try:
    proc=subprocess.Popen([sys.executable,str(ROOT/'backend.py'),'--data-root',str(base/'parent'),'--port',str(port),'--no-browser'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    deadline=time.time()+20
    while time.time()<deadline:
        if proc.poll() is not None: raise RuntimeError(proc.stdout.read() if proc.stdout else 'backend exited')
        try:
            st,h,_=req('GET','/api/health',timeout=2)
            if st==200: break
        except Exception: time.sleep(.15)
    else: raise RuntimeError('startup timeout')
    assert h['appVersion']=='4.8.18.0-DESKTOP' and h['quickCheck']=='ok',h
    now='2026-09-29T12:00:00Z'
    seed={
      'companies':{'id':'c1','name':'شركة HTTP','companySerial':1,'createdAt':now,'modifiedAt':now},
      'items':{'id':'i1','companyId':'c1','name':'رخصة التشغيل','applicable':True,'position':1,'expiryDate':'2027-01-01','createdAt':now,'modifiedAt':now},
      'inspections':{'id':'in1','companyId':'c1','date':'2026-09-29','inspectionCode':'INS-1-2026-1','inspectionNo':'INS-1-2026-1','createdAt':now,'modifiedAt':now},
      'findings':{'id':'f1','inspectionId':'in1','companyId':'c1','no':'1','description':'ملاحظة HTTP','requirement':'متطلب','status':'Open','createdAt':now,'modifiedAt':now},
    }
    for store,row in seed.items():
        st,j,_=req('POST','/api/put',{'store':store,'row':row});assert st==200 and j['ok']
    def one(i):
        row={'id':f'h{i}','companyId':'c1','name':f'HTTP {i}','applicable':True,'position':i+2,'expiryDate':'2027-12-31','createdAt':now,'modifiedAt':now}
        st,j,_=req('POST','/api/put',{'store':'items','row':row});return st,j
    with ThreadPoolExecutor(max_workers=10) as ex: out=list(ex.map(one,range(30)))
    assert all(st==200 and j.get('ok') for st,j in out)
    st,a,_=req('GET','/api/storage-audit');assert st==200 and a['audit']['quickCheck']=='ok'
    st,s,_=req('GET','/api/v4179-settings');assert st==200 and s['dailyRetentionDays']==30
    st,s,_=req('POST','/api/v4179-settings',{'dailyRetentionDays':31});assert st==200 and s['dailyRetentionDays']==31
    st,x,_=req('POST','/api/refresh-live-excel',{},60);assert st==200 and x['audit']['verifiedAgainstSQLite'] and Path(x['path']).is_dir()
    st,m,_=req('POST','/api/manual-recovery',{},60);assert st==200 and m['audit']['verifiedAgainstSQLite'] and list(Path(m['path']).rglob('*.xlsx'))
    st,b,_=req('POST','/api/manual-backup',{},30);assert st==200 and Path(b['path']).is_file()
    st,v,_=req('POST','/api/verify-backup',{'path':b['path']});assert st==200 and v['valid']
    st,pv,_=req('POST','/api/backup-preview',{'path':b['path']});assert st==200 and pv['ok']
    st,r,_=req('POST','/api/restore-backup',{'path':b['path']},30);assert st==200 and Path(r['beforeRestore']).is_file()
    st,mob,_=req('POST','/api/mobile-export',{'since':'','includeAttachments':False},60);assert st==200 and Path(mob['path']).is_file()
    st,h2,_=req('GET','/api/health');assert st==200 and h2['quickCheck']=='ok'
    st,_,raw=req('GET','/app/index.html');assert st==200 and b'4.8.18.0-DESKTOP' in raw
    st,_,raw=req('GET','/app/v4179_patch.js');assert st==200 and b'renderSyncBefore79' in raw
    print('v4.8.18.0 HTTP/API/CONCURRENCY/EXCEL/BACKUP/RESTORE/MOBILE QA PASS')
finally:
    if proc and proc.poll() is None:
        proc.terminate()
        try:proc.wait(5)
        except:proc.kill()
    shutil.rmtree(base,ignore_errors=True)
