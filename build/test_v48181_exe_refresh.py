import sys
from playwright.sync_api import sync_playwright

url=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:18766/app/index.html'
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page()
    page.set_default_timeout(8000)
    requests=[]
    page.on('request',lambda r: requests.append((r.method,r.url)))
    page.goto(url,wait_until='domcontentloaded',timeout=15000)
    page.wait_for_selector('#view-dashboard.active',timeout=15000)
    assert page.evaluate("typeof window.sokhnaRefreshConnection")=='function'
    assert page.evaluate("window.sokhnaRefreshConnection()") is True
    for _ in range(5):
        page.evaluate("window.dispatchEvent(new Event('focus'))")
        page.wait_for_timeout(120)
    health=[x for x in requests if '/api/health' in x[1]]
    assert health and all(m=='GET' for m,_ in health),health
    assert page.evaluate('40+2')==42
    browser.close()
print('PACKAGED EXE v4.8.18.1 REFRESH/FOCUS/GET-ONLY PASS')
