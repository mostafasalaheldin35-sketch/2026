from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent
SRC=ROOT.parent/'buildsrc'
if not SRC.is_dir():
    raise SystemExit('buildsrc missing')

shutil.copy2(ROOT/'v4178_backend_ext.py', SRC/'v4178_backend_ext.py')

backend=SRC/'backend.py'
s=backend.read_text(encoding='utf-8')
needle='import v4177_backend_ext as _v4177_backend_ext\n_v4177_backend_ext.install(globals())\n'
repl=needle+'\nimport v4178_backend_ext as _v4178_backend_ext\n_v4178_backend_ext.install(globals())\n'
if '_v4178_backend_ext.install(globals())' not in s:
    if needle not in s: raise SystemExit('v4177 install anchor missing')
    s=s.replace(needle,repl,1)
backend.write_text(s,encoding='utf-8')

index=SRC/'app'/'index.html'
h=index.read_text(encoding='utf-8')
h=h.replace("const APP_VERSION='4.8.17.7-DESKTOP';", "const APP_VERSION='4.8.17.8-DESKTOP';", 1)
index.write_text(h,encoding='utf-8')

js=SRC/'app'/'v4177_patch.js'
j=js.read_text(encoding='utf-8')
anchor='<button class="outline" id="s77OpenLogs">فتح Logs</button><button class="primary" id="s77MoveRoot">تغيير / نقل مكان البيانات</button>'
replacement='<button class="outline" id="s77OpenLogs">فتح Logs</button><button class="outline" id="s77DesktopShortcut">إنشاء / إصلاح اختصار سطح المكتب</button>\n    <button class="primary" id="s77MoveRoot">تغيير / نقل مكان البيانات</button>'
if 's77DesktopShortcut' not in j:
    if anchor not in j: raise SystemExit('storage button anchor missing')
    j=j.replace(anchor,replacement,1)
bind_anchor="id('s77MoveRoot').onclick=moveRoot;"
bind_repl="id('s77DesktopShortcut').onclick=async()=>{try{const r=await post('/api/create-desktop-shortcut',{});say('تم إنشاء اختصار سطح المكتب\\n'+(r.shortcut||''));note('اختصار Sokhna Port جاهز على سطح المكتب')}catch(e){note('تعذر إنشاء الاختصار: '+(e?.message||e))}};\n "+bind_anchor
if "'/api/create-desktop-shortcut'" not in j:
    if bind_anchor not in j: raise SystemExit('bind anchor missing')
    j=j.replace(bind_anchor,bind_repl,1)
j=j.replace('v4.8.17.7 — reviewed storage / backup / Excel / mobile fixes','v4.8.17.8 — Excel compatibility + shortcut reliability',1)
js.write_text(j,encoding='utf-8')

print('Applied v4.8.17.8 Excel compatibility + shortcut hotfix')
