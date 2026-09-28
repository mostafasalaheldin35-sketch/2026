import sys
from playwright.sync_api import sync_playwright
url=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:18766/app/index.html'
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page();page.set_default_timeout(8000)
    page.goto(url,wait_until='domcontentloaded',timeout=15000)
    page.wait_for_selector('#view-dashboard.active',timeout=15000)
    for _ in range(15):
        page.click('.bottom button[data-nav="sync"]');page.wait_for_timeout(50)
        assert page.locator('#view-sync').evaluate("e=>e.classList.contains('active')")
        assert page.locator('.sync79-settings').count()==1
        assert page.evaluate('40+2')==42
        page.click('.bottom button[data-nav="dashboard"]');page.wait_for_timeout(50)
    page.click('.bottom button[data-nav="inspections"]');page.wait_for_timeout(50)
    page.click('#openInspectionAnalyticsBtn');page.wait_for_timeout(80)
    assert page.locator('#view-inspection-analytics').evaluate("e=>e.classList.contains('active')")
    assert page.locator('#analyticsCompanyFilter79').count()==1
    browser.close()
print('PACKAGED EXE UI FREEZE/NAVIGATION/ANALYTICS PASS')
