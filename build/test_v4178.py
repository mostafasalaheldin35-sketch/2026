from pathlib import Path
import sys, tempfile, zipfile

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import backend


def worksheet_order(path: Path):
    out=[]
    with zipfile.ZipFile(path,'r') as z:
        for name in sorted(n for n in z.namelist() if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')):
            text=z.read(name).decode('utf-8')
            m=text.find('<mergeCells'); a=text.find('<autoFilter')
            out.append((name,a,m))
            if a>=0 and m>=0:
                assert a<m,(name,a,m)
    return out

base=Path(tempfile.mkdtemp(prefix='sokhna_v4178_'))
root=base/'Sokhna Port Data'
store=backend.DesktopStore(root)
try:
    now=backend.now_iso()
    store.put('companies',{'id':'c1','name':'شركة اختبار Excel','companySerial':1,'createdAt':now,'modifiedAt':now})
    store.put('items',{'id':'i1','companyId':'c1','name':'رخصة التشغيل','position':1,'expiryDate':'2027-01-01','createdAt':now,'modifiedAt':now})
    store.put('inspections',{'id':'n1','companyId':'c1','date':'2026-09-28','inspectionCode':'INS-1-2026-1','inspectionNo':'INS-1-2026-1','createdAt':now,'modifiedAt':now})
    store.put('findings',{'id':'f1','inspectionId':'n1','companyId':'c1','no':'1','description':'ملاحظة Excel','requirement':'متطلب Excel','status':'Open','createdAt':now,'modifiedAt':now})
    live=Path(store.refresh_live_excel_now())
    assert live.is_file() and live.stat().st_size>1000
    worksheet_order(live)
    pkg=store.create_company_excel_backups('MANUAL')
    company_files=list(pkg.rglob('*.xlsx'))
    assert len(company_files)==1,company_files
    company=company_files[0]
    worksheet_order(company)
    # Exact field regression: company workbook has both mergeCells and autoFilter,
    # and strict Excel-required order must be autoFilter then mergeCells.
    with zipfile.ZipFile(company,'r') as z:
        for n in ('xl/worksheets/sheet1.xml','xl/worksheets/sheet2.xml'):
            text=z.read(n).decode('utf-8')
            assert '<autoFilter' in text and '<mergeCells' in text
            assert text.find('<autoFilter') < text.find('<mergeCells')
    store._validate_xlsx(company)
finally:
    store.close()

html=(ROOT/'app'/'index.html').read_text(encoding='utf-8')
js=(ROOT/'app'/'v4177_patch.js').read_text(encoding='utf-8')
be=(ROOT/'v4178_backend_ext.py').read_text(encoding='utf-8')
backend_text=(ROOT/'backend.py').read_text(encoding='utf-8')
assert '4.8.17.8-DESKTOP' in html
assert '_v4178_backend_ext.install(globals())' in backend_text
assert 's77DesktopShortcut' in js and '/api/create-desktop-shortcut' in js
for token in ('User Shell Folders','cscript.exe','Sokhna Port.cmd','autoFilter must precede mergeCells'):
    assert token in be,token
print('v4.8.17.8 EXCEL/SHORTCUT QA PASS')
