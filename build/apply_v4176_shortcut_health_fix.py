from pathlib import Path

p=Path("buildsrc/v4176_backend_ext.py")
s=p.read_text(encoding="utf-8")
old='''    def health(self) -> Dict[str, Any]:
        h = old_health(self)
        h["appVersion"] = ns["APP_VERSION"]
        h["excelReportsRoot"] = str(Path(self.paths["root"]) / "Backups" / "Excel Reports")
        h["backupsRoot"] = str(Path(self.paths["root"]) / "Backups" / "Recovery")
        return h
'''
new='''    def health(self) -> Dict[str, Any]:
        h = old_health(self)
        h["appVersion"] = ns["APP_VERSION"]
        h["excelReportsRoot"] = str(Path(self.paths["root"]) / "Backups" / "Excel Reports")
        h["backupsRoot"] = str(Path(self.paths["root"]) / "Backups" / "Recovery")
        desktop = ns["windows_desktop_dir"]() if os.name == "nt" else None
        shortcut = (Path(desktop) / "Sokhna Port.lnk") if desktop else None
        h["desktopShortcut"] = str(shortcut) if shortcut else ""
        h["desktopShortcutExists"] = bool(shortcut and shortcut.is_file() and shortcut.stat().st_size > 0)
        return h
'''
if s.count(old)!=1:
    raise SystemExit(f"shortcut-health marker count mismatch: {s.count(old)}")
p.write_text(s.replace(old,new),encoding="utf-8",newline="\n")
print("v4.8.17.6 shortcut health reporting fixed")
