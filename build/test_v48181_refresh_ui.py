from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent.parent/'buildsrc'
js=(ROOT/'app'/'v48181_refresh.js').read_text(encoding='utf-8')
html=f'''<!doctype html><html><body><script>
window.__calls=[];window.__n=0;window.__reconnected=0;
window.fetch=async function(input,init={{}}){{
  const method=String(init.method||'GET').toUpperCase();
  window.__calls.push({{url:String(input),method}});
  window.__n++;
  if(window.__n<3)throw new Error('temporary offline');
  return new Response(JSON.stringify({{ok:true,appVersion:'4.8.18.1-DESKTOP'}}),{{status:200,headers:{{'Content-Type':'application/json'}}}});
}};
window.addEventListener('sokhna:reconnected',()=>window.__reconnected++);
</script><script>{js}</script></body></html>'''

with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page()
    page.set_content(html,wait_until='domcontentloaded')
    page.wait_for_timeout(5200)
    calls=page.evaluate('window.__calls')
    assert len(calls)>=3,calls
    assert all(c['url']=='/api/health' and c['method']=='GET' for c in calls),calls
    assert page.evaluate('window.__reconnected')>=1
    before=len(calls)
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    page.wait_for_timeout(250)
    calls2=page.evaluate('window.__calls')
    assert len(calls2)>before,(before,calls2)
    assert page.evaluate("typeof window.sokhnaRefreshConnection")=='function'
    browser.close()

print('v4.8.18.1 GET-ONLY AUTO-RECONNECT UI QA PASS')
