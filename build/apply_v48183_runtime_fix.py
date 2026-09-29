from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
p=ROOT/'buildsrc'/'app'/'v48183_polish.js'
s=p.read_text(encoding='utf-8')
old="new MutationObserver(()=>compactItemEditor()).observe(byId('itemDialog')||document.body,{childList:true,subtree:true});"
new="setTimeout(compactItemEditor,0);"
if old not in s:
    raise SystemExit('Expected v4.8.18.3 item-dialog observer not found')
p.write_text(s.replace(old,new,1),encoding='utf-8')
print('Applied v4.8.18.3 runtime stability fix')
