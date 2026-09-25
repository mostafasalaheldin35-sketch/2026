from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'buildsrc'
html=(BUILD/'app/index.html').read_text(encoding='utf-8')
backend=(BUILD/'backend.py').read_text(encoding='utf-8')
assert "const APP_VERSION='4.8.16.9-FINAL-DESKTOP'" in html
assert 'font-family:"Segoe UI",Tahoma,Arial,sans-serif!important' in html
assert '/api/move-data-root' in html
assert '/api/export-excel-package' in html
assert '/api/refresh-live-excel' in html
assert 'def move_data_root' in backend
assert 'def export_excel_package' in backend
assert 'def automatic_maintenance' in backend
assert 'def _friendly_attachment_rel' in backend
print('BASELINE DESKTOP QA PASSED')
