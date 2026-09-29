from pathlib import Path
import re,sys
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent;APP=ROOT/'app'
html=(APP/'index.html').read_text(encoding='utf-8')
html=re.sub(r'<link rel="stylesheet" href="([^"]+)">',lambda m:'<style>'+((APP/m.group(1)).read_text(encoding='utf-8'))+'</style>',html)
html=re.sub(r'<script src="([^"]+)"></script>',lambda m:'<script>'+((APP/m.group(1)).read_text(encoding='utf-8'))+'</script>',html)
mock=r'''<script>
window.__openLiveCalls=0;
window.fetch=async function(input,init={}){const u=String(typeof input==='string'?input:(input&&input.url)||'');const ok=x=>new Response(JSON.stringify(x),{status:200,headers:{'Content-Type':'application/json'}});
if(u.includes('/api/health'))return ok({ok:true,appVersion:'4.8.18.2-DESKTOP',quickCheck:'ok'});
if(u.includes('/api/store/'))return ok({ok:true,rows:[]});
if(u.includes('/api/storage-audit'))return ok({ok:true,audit:{quickCheck:'ok',paths:{root:'D:/Sokhna Port Data',database:'D:/Sokhna Port Data/Database',attachments:'D:/Sokhna Port Data/Attachments',backupRecovery:'D:/Sokhna Port Data/Backup Recovery',excel:'D:/Sokhna Port Data/Excel',mobile:'D:/Sokhna Port Data/Mobile SQL Exchange',logs:'D:/Sokhna Port Data/Logs'},counts:{},attachments:{},legacyFoldersRemaining:[],backupCount:0,excelFileCount:0,mobileExchangeFileCount:0}});
if(u.includes('/api/backups'))return ok({ok:true,backups:[]});
if(u.includes('/api/v4179-settings'))return ok({ok:true,dailyRetentionDays:30,attachmentIndex:'D:/Sokhna Port Data/Database/Attachments Index.sqlite'});
if(u.includes('/api/open-live-excel-folder')){window.__openLiveCalls++;return ok({ok:true,path:'D:/Sokhna Port Data/Excel/Live',refreshError:''});}
if(u.includes('/api/ping'))return ok({ok:true});return ok({ok:true});};
</script>'''
html=html.replace('<head>','<head>'+mock,1)
with sync_playwright() as pw:
    if sys.platform.startswith('win'):browser=pw.chromium.launch(channel='msedge',headless=True)
    else:
        exe='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None
        browser=pw.chromium.launch(headless=True,executable_path=exe,args=['--no-sandbox'] if exe else None)
    page=browser.new_page();page.set_default_timeout(5000);page.set_content(html,wait_until='domcontentloaded');page.wait_for_timeout(600)
    page.click('.bottom button[data-nav="sync"]');page.wait_for_timeout(250)
    assert page.locator('#openLiveExcelFolder48182').count()==1
    assert page.locator('[data-open="live-excel"]').count()==0
    assert page.locator('#openLiveExcelFolder48182').inner_text()=='فتح فولدر Live Excel'
    assert page.locator('#s77LiveExcel').inner_text()=='تحديث Live Excel الآن'
    assert page.locator('.live-excel-note-48182').count()==1
    style=page.locator('#openLiveExcelFolder48182').evaluate("e=>{const s=getComputedStyle(e);return {color:s.color,bg:s.backgroundColor,h:e.getBoundingClientRect().height,vis:s.visibility,disp:s.display}}")
    assert style['vis']=='visible' and style['disp']!='none' and style['h']>=40,style
    assert style['color'] not in ('rgba(0, 0, 0, 0)','rgb(255, 255, 255)'),style
    page.click('#openLiveExcelFolder48182');page.wait_for_timeout(150)
    assert page.evaluate('window.__openLiveCalls')==1
    assert 'Excel/Live' in page.locator('#syncLog').inner_text()
    browser.close()
print('v4.8.18.2 LIVE EXCEL BUTTON/TEXT/UI QA PASS')
