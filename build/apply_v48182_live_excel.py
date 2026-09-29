from pathlib import Path
import hashlib, shutil

ROOT=Path(__file__).resolve().parent.parent
SRC=ROOT/'buildsrc'
if not (SRC/'backend.py').is_file():
    raise SystemExit(f'buildsrc not found under {ROOT}')

template=SRC/'app'/'sugar_template.xlsx'
if not template.is_file():
    raise SystemExit('Approved sugar_template.xlsx is missing')
digest=hashlib.sha256(template.read_bytes()).hexdigest()
expected='55e2257b0362d58b62403816ea44bf02e7cfe0e643a189ff74b7b0ad0b11874d'
if digest!=expected:
    raise SystemExit(f'Approved Excel template hash changed: {digest}')

be=SRC/'v4179_backend_ext.py'
s=be.read_text(encoding='utf-8')
if "ns['APP_VERSION']='4.8.18.1-DESKTOP'" not in s:
    raise SystemExit('Expected v4.8.18.1 backend version not found')
s=s.replace("ns['APP_VERSION']='4.8.18.1-DESKTOP'","ns['APP_VERSION']='4.8.18.2-DESKTOP'",1)
s=s.replace("Handler.server_version='CompanyInspectionDesktop/4.8.18.1'","Handler.server_version='CompanyInspectionDesktop/4.8.18.2'",1)
old="""    def do_POST(self):
        path=ns['urllib'].parse.urlparse(self.path).path
        if path not in {'/api/v4179-settings','/api/repair-attachments','/api/refresh-live-excel','/api/manual-recovery'}:return old_post(self)
        try:
            body=self._read_json();s=ns['STORE']
"""
new="""    def do_POST(self):
        path=ns['urllib'].parse.urlparse(self.path).path
        if path not in {'/api/v4179-settings','/api/repair-attachments','/api/refresh-live-excel','/api/manual-recovery','/api/open-live-excel-folder'}:return old_post(self)
        try:
            body=self._read_json();s=ns['STORE']
"""
if old not in s:
    raise SystemExit('Expected v4.8.18.1 POST wrapper not found')
s=s.replace(old,new,1)
anchor="""            if path=='/api/refresh-live-excel':
                out=s.refresh_live_excel_now();self._send_json({'ok':True,'path':str(Path(out).resolve()),'audit':s.validate_live_excel(out)});return
"""
insert="""            if path=='/api/open-live-excel-folder':
                root=Path(s.paths['excel_default']);root.mkdir(parents=True,exist_ok=True);refresh_error=''
                try:s.refresh_live_excel_now()
                except Exception as e:refresh_error=str(e)
                opened=False
                if os.name=='nt':
                    try:os.startfile(str(root.resolve()));opened=True
                    except Exception:
                        try:
                            sp=__import__('subprocess');flags=getattr(sp,'CREATE_NO_WINDOW',0);sp.Popen(['explorer.exe',str(root.resolve())],stdout=sp.DEVNULL,stderr=sp.DEVNULL,creationflags=flags);opened=True
                        except Exception:pass
                if not opened:ns['open_in_file_manager'](root)
                self._send_json({'ok':True,'path':str(root.resolve()),'refreshError':refresh_error});return
            if path=='/api/refresh-live-excel':
                out=s.refresh_live_excel_now();self._send_json({'ok':True,'path':str(Path(out).resolve()),'audit':s.validate_live_excel(out)});return
"""
if anchor not in s:
    raise SystemExit('Expected refresh-live-excel route not found')
s=s.replace(anchor,insert,1)
be.write_text(s,encoding='utf-8')

idx=SRC/'app'/'index.html'
h=idx.read_text(encoding='utf-8')
if "const APP_VERSION='4.8.18.1-DESKTOP'" not in h:
    raise SystemExit('Expected v4.8.18.1 UI version not found')
h=h.replace("const APP_VERSION='4.8.18.1-DESKTOP'","const APP_VERSION='4.8.18.2-DESKTOP'",1)
anchor='<link rel="stylesheet" href="v4177_patch.css"><script src="v4177_patch.js"></script><link rel="stylesheet" href="v4179_patch.css"><script src="v4179_patch.js"></script><script src="v48181_refresh.js"></script>'
if anchor not in h:
    raise SystemExit('Expected v4.8.18.1 asset anchor not found')
h=h.replace(anchor,anchor+'<link rel="stylesheet" href="v48182_live_excel.css"><script src="v48182_live_excel.js"></script>',1)
idx.write_text(h,encoding='utf-8')

shutil.copy2(ROOT/'build'/'v48182_live_excel.js',SRC/'app'/'v48182_live_excel.js')
shutil.copy2(ROOT/'build'/'v48182_live_excel.css',SRC/'app'/'v48182_live_excel.css')
print('Applied v4.8.18.2 Live Excel/open-folder controls only')
