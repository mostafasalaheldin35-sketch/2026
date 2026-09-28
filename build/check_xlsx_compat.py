from pathlib import Path
import sys
import zipfile

if len(sys.argv) < 2:
    raise SystemExit("Usage: check_xlsx_compat.py <workbook.xlsx> [...]")

for arg in sys.argv[1:]:
    path = Path(arg)
    with zipfile.ZipFile(path, "r") as z:
        for name in z.namelist():
            if not (name.startswith("xl/worksheets/sheet") and name.endswith(".xml")):
                continue
            text = z.read(name).decode("utf-8")
            auto_filter = text.find("<autoFilter")
            merge_cells = text.find("<mergeCells")
            if auto_filter >= 0 and merge_cells >= 0 and auto_filter > merge_cells:
                raise SystemExit(f"Invalid Excel OOXML order: {path} / {name}")

print("EXCEL OOXML COMPAT PASS")
