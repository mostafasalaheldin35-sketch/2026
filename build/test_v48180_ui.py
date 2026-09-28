from pathlib import Path
import re,sys
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent;APP=ROOT/'app'
html=(APP/'index.html').read_text(encoding='utf-8')
html=re.sub(r'<link rel="stylesheet" href="([^"]+)">',lambda m:'<style>'+((APP/m.group(1)).read_text(encoding='utf-8'))+'</style>',html)
html=re.sub(r'<script src="([^"]+)"></script>',lambda m:'<script>'+((APP/m.group(1)).read_text(encoding='utf-8'))+'</script>',html)
mock=r'''<script>
window.__moCount=0;const NativeMO=window.MutationObserver;window.MutationObserver=class extends NativeMO{constructor(cb){super((...a)=>{window.__moCount++;return cb(...a)})}};
window.fetch=async function(input,init={}){const u=String(typeof input==='string'?input:(input&&input.url)||'');const ok=x=>new Response(JSON.stringify(x),{status:200,headers:{'Content-Type':'application/json'}});
if(u.includes('/api/health'))return ok({ok:true,appVersion:'4.8.18.0-DESKTOP',quickCheck:'ok',dataRoot:'D:/Sokhna Port Data',database:'D:/Sokhna Port Data/Database/company_master.sqlite3',attachmentsRoot:'D:/Sokhna Port Data/Attachments',backupsRoot:'D:/Sokhna Port Data/Backup Recovery',excelRoot:'D:/Sokhna Port Data/Excel',mobileExchangeRoot:'D:/Sokhna Port Data/Mobile SQL Exchange'});
if(u.includes('/api/store/'))return ok({ok:true,rows:[]});
if(u.includes('/api/storage-audit'))return ok({ok:true,audit:{quickCheck:'ok',paths:{root:'D:/Sokhna Port Data',database:'D:/Sokhna Port Data/Database',attachments:'D:/Sokhna Port Data/Attachments',backupRecovery:'D:/Sokhna Port Data/Backup Recovery',excel:'D:/Sokhna Port Data/Excel',mobile:'D:/Sokhna Port Data/Mobile SQL Exchange',logs:'D:/Sokhna Port Data/Logs'},counts:{},attachments:{},legacyFoldersRemaining:[],backupCount:0,excelFileCount:0,mobileExchangeFileCount:0}});
if(u.includes('/api/backups'))return ok({ok:true,backups:[]});if(u.includes('/api/v4179-settings'))return ok({ok:true,dailyRetentionDays:30,attachmentIndex:'D:/Sokhna Port Data/Database/Attachments Index.sqlite'});if(u.includes('/api/ping'))return ok({ok:true});return ok({ok:true});};
</script>'''
html=html.replace('<head>','<head>'+mock,1)
with sync_playwright() as pw:
    if sys.platform.startswith('win'):
        browser=pw.chromium.launch(channel='msedge',headless=True)
    else:
        exe='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None
        browser=pw.chromium.launch(headless=True,executable_path=exe,args=['--no-sandbox'] if exe else None)
    page=browser.new_page();page.set_default_timeout(4000);page.set_content(html,wait_until='domcontentloaded');page.wait_for_timeout(500)
    assert page.locator('#view-dashboard').evaluate("e=>e.classList.contains('active')")
    before=page.evaluate('window.__moCount')
    for _ in range(25):
        page.click('.bottom button[data-nav="sync"]');page.wait_for_timeout(15)
        assert page.locator('#view-sync').evaluate("e=>e.classList.contains('active')")
        assert page.locator('.sync79-settings').count()==1
        assert page.evaluate('1+1')==2
        page.click('.bottom button[data-nav="dashboard"]');page.wait_for_timeout(15)
    after=page.evaluate('window.__moCount')
    assert after-before<1000,(before,after)
    for nav in ('all-items','inspections','settings','dashboard'):
        sel=(f'.bottom button[data-nav="{nav}"]' if nav!='settings' else 'button[data-nav="settings"]')
        page.click(sel);page.wait_for_timeout(30)
        assert page.locator('#view-'+nav).evaluate("e=>e.classList.contains('active')")
        assert page.evaluate('2+2')==4
    page.click('.bottom button[data-nav="inspections"]');page.wait_for_timeout(30)
    page.click('#openInspectionAnalyticsBtn');page.wait_for_timeout(50)
    assert page.locator('#view-inspection-analytics').evaluate("e=>e.classList.contains('active')")
    assert page.locator('#analyticsCompanyFilter79').count()==1
    assert page.evaluate('3+3')==6
    browser.close()
print('v4.8.18.0 UI/NAVIGATION/SYNC-FREEZE/ANALYTICS REGRESSION QA PASS')
