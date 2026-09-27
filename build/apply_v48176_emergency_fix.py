from pathlib import Path

root=Path('buildsrc')

p=root/'v4175_backend_ext.py'
s=p.read_text(encoding='utf-8')
old='def emergency_copy(self) -> Dict[str,Any]:\n        selected=browse_for_folder("اختر مكان حفظ نسخة SQLite الطوارئ") if os.name=="nt" else self.paths["exports"]'
new='def emergency_copy(self, target_dir: str=\'\') -> Dict[str,Any]:\n        selected=Path(target_dir) if target_dir else (browse_for_folder("اختر مكان حفظ نسخة SQLite الطوارئ") if os.name=="nt" else self.paths["exports"])'
if new not in s:
    if old not in s:
        raise SystemExit('emergency_copy method marker missing')
    s=s.replace(old,new,1)
old2="if path=='/api/emergency-copy': self._send_json({'ok':True,**store.emergency_copy()}); return"
new2="if path=='/api/emergency-copy': self._send_json({'ok':True,**store.emergency_copy(str(body.get('targetDir') or ''))}); return"
if new2 not in s:
    if old2 not in s:
        raise SystemExit('emergency-copy route marker missing')
    s=s.replace(old2,new2,1)
p.write_text(s,encoding='utf-8',newline='\n')

p=root/'test_v48176.py'
s=p.read_text(encoding='utf-8')
old3='st,em = http_json(base+"/api/emergency-copy","POST",{})'
new3='st,em = http_json(base+"/api/emergency-copy","POST",{"targetDir":str(store.paths["exports"])})'
if new3 not in s:
    if old3 not in s:
        raise SystemExit('emergency-copy test marker missing')
    s=s.replace(old3,new3,1)
p.write_text(s,encoding='utf-8',newline='\n')

print('Applied v4.8.17.6 emergency-copy headless verification fix')
