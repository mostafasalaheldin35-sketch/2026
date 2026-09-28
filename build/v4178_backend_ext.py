"""v4.8.17.8 Excel compatibility + desktop shortcut reliability hotfix."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional


def install(ns: Dict[str, Any]) -> None:
    ns["APP_VERSION"] = "4.8.17.8-DESKTOP"
    Store = ns["DesktopStore"]
    Handler = ns["Handler"]

    # ------------------------------------------------------------------
    # Excel compatibility: Excel enforces the OOXML worksheet child order.
    # autoFilter must appear before mergeCells. v4.8.17.7 emitted the two
    # elements in the opposite order, which strict Microsoft Excel repairs.
    # Repair existing workbooks and every newly generated workbook.
    # ------------------------------------------------------------------
    old_validate_xlsx = Store._validate_xlsx

    def _excel_compat_repair(path: Path) -> bool:
        path = Path(path)
        if not path.is_file() or path.suffix.lower() != ".xlsx":
            return False
        changed: Dict[str, bytes] = {}
        try:
            with zipfile.ZipFile(path, "r") as zin:
                infos = zin.infolist()
                for info in infos:
                    name = info.filename
                    if not (name.startswith("xl/worksheets/sheet") and name.endswith(".xml")):
                        continue
                    raw = zin.read(name)
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    m1 = text.find("<mergeCells")
                    m2 = text.find("</mergeCells>")
                    a1 = text.find("<autoFilter")
                    if m1 < 0 or m2 < 0 or a1 < 0 or m1 > a1:
                        continue
                    a2 = text.find("/>", a1)
                    if a2 < 0:
                        a2 = text.find("</autoFilter>", a1)
                        if a2 < 0:
                            continue
                        a2 += len("</autoFilter>") - 1
                    else:
                        a2 += 1
                    merge_block = text[m1:m2 + len("</mergeCells>")]
                    auto_block = text[a1:a2 + 1]
                    # Remove later block first to keep indexes stable.
                    pieces = [(m1, m2 + len("</mergeCells>")), (a1, a2 + 1)]
                    for start, end in sorted(pieces, reverse=True):
                        text = text[:start] + text[end:]
                    insert_at = text.find("</sheetData>")
                    if insert_at < 0:
                        continue
                    insert_at += len("</sheetData>")
                    text = text[:insert_at] + auto_block + merge_block + text[insert_at:]
                    changed[name] = text.encode("utf-8")
                if not changed:
                    return False
                fd, tmp_name = tempfile.mkstemp(prefix=path.stem + "_compat_", suffix=".xlsx", dir=str(path.parent))
                os.close(fd)
                tmp = Path(tmp_name)
                try:
                    with zipfile.ZipFile(tmp, "w") as zout:
                        for info in infos:
                            data = changed.get(info.filename)
                            if data is None:
                                data = zin.read(info.filename)
                            zout.writestr(info, data)
                    os.replace(tmp, path)
                finally:
                    try:
                        tmp.unlink(missing_ok=True)
                    except Exception:
                        pass
            return True
        except (zipfile.BadZipFile, OSError):
            return False

    def _excel_compat_assert(path: Path) -> None:
        with zipfile.ZipFile(path, "r") as z:
            for name in sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")):
                text = z.read(name).decode("utf-8", errors="strict")
                m = text.find("<mergeCells")
                a = text.find("<autoFilter")
                if m >= 0 and a >= 0 and a > m:
                    raise ValueError(f"Excel OOXML order invalid in {name}: autoFilter must precede mergeCells")

    def validate_xlsx(self, path: Path) -> None:
        p = Path(path)
        _excel_compat_repair(p)
        old_validate_xlsx(self, p)
        _excel_compat_assert(p)

    Store._validate_xlsx = validate_xlsx
    Store._excel_compat_repair = staticmethod(_excel_compat_repair)
    Store._excel_compat_assert = staticmethod(_excel_compat_assert)

    old_init = Store.__init__
    def init_with_excel_repair(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        try:
            excel_root = Path(self.paths.get("excel_root") or "")
            if excel_root.is_dir():
                for xlsx in excel_root.rglob("*.xlsx"):
                    try:
                        _excel_compat_repair(xlsx)
                    except Exception:
                        pass
        except Exception:
            pass
    Store.__init__ = init_with_excel_repair

    # ------------------------------------------------------------------
    # Desktop shortcut: avoid depending only on PowerShell and resolve the
    # real redirected Desktop path from Windows Explorer's user-shell setting.
    # A clickable .cmd launcher is created only as a fallback if .lnk creation
    # is blocked by Windows policy/security software.
    # ------------------------------------------------------------------
    def windows_desktop_dir() -> Optional[Path]:
        if os.name != "nt":
            return None
        try:
            import winreg
            for key_name in (
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            ):
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_name) as key:
                        value, _ = winreg.QueryValueEx(key, "Desktop")
                    value = os.path.expandvars(str(value or "").strip())
                    if value:
                        return Path(value)
                except OSError:
                    pass
        except Exception:
            pass
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(32768)
            hr = ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)
            if int(hr) == 0 and buf.value:
                return Path(buf.value)
        except Exception:
            pass
        candidates = []
        one = os.environ.get("OneDrive")
        if one:
            candidates.append(Path(one) / "Desktop")
        candidates.append(Path.home() / "Desktop")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[-1] if candidates else None

    def _vbs_quote(value: str) -> str:
        return '"' + value.replace('"', '""') + '"'

    def ensure_installed_exe_and_shortcut() -> Optional[Path]:
        if os.name != "nt" or not getattr(ns["sys"], "frozen", False):
            return None
        source = Path(ns["sys"].executable).resolve()
        install_dir = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / "Sokhna Port"
        install_dir.mkdir(parents=True, exist_ok=True)
        target = install_dir / "Sokhna Port.exe"
        try:
            if source != target:
                needs_copy = True
                if target.exists():
                    try:
                        needs_copy = source.stat().st_size != target.stat().st_size
                        if not needs_copy:
                            import hashlib
                            def sha256(p: Path) -> str:
                                h = hashlib.sha256()
                                with p.open("rb") as fh:
                                    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                                        h.update(chunk)
                                return h.hexdigest()
                            needs_copy = sha256(source) != sha256(target)
                    except Exception:
                        needs_copy = True
                if needs_copy:
                    shutil.copy2(source, target)
            else:
                target = source
        except Exception:
            target = source

        desktop = windows_desktop_dir()
        if not desktop:
            return target
        try:
            desktop.mkdir(parents=True, exist_ok=True)
        except Exception:
            return target
        shortcut = desktop / "Sokhna Port.lnk"
        fallback = desktop / "Sokhna Port.cmd"

        # First choice: Windows Script Host through cscript (no PowerShell policy dependency).
        try:
            vbs = install_dir / "create-shortcut.vbs"
            vbs.write_text(
                "Set ws = CreateObject(\"WScript.Shell\")\r\n"
                f"Set s = ws.CreateShortcut({_vbs_quote(str(shortcut))})\r\n"
                f"s.TargetPath = {_vbs_quote(str(target))}\r\n"
                f"s.WorkingDirectory = {_vbs_quote(str(target.parent))}\r\n"
                f"s.IconLocation = {_vbs_quote(str(target) + ',0')}\r\n"
                "s.Description = \"Sokhna Port\"\r\n"
                "s.Save\r\n",
                encoding="utf-8-sig",
            )
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.run(["cscript.exe", "//Nologo", str(vbs)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=20, check=False, creationflags=creationflags)
            try:
                vbs.unlink(missing_ok=True)
            except Exception:
                pass
        except Exception:
            pass

        # Second choice: previous PowerShell path, still useful on some managed PCs.
        if not shortcut.is_file():
            try:
                def ps_quote(v: str) -> str:
                    return "'" + v.replace("'", "''") + "'"
                script = (
                    "$ws=New-Object -ComObject WScript.Shell;"
                    f"$s=$ws.CreateShortcut({ps_quote(str(shortcut))});"
                    f"$s.TargetPath={ps_quote(str(target))};"
                    f"$s.WorkingDirectory={ps_quote(str(target.parent))};"
                    f"$s.IconLocation={ps_quote(str(target) + ',0')};"
                    "$s.Description='Sokhna Port';$s.Save()"
                )
                subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except Exception:
                pass

        # Last-resort clickable Desktop launcher; only present when .lnk creation failed.
        if shortcut.is_file():
            try:
                fallback.unlink(missing_ok=True)
            except Exception:
                pass
        else:
            try:
                fallback.write_text(f'@echo off\r\nstart "" "{str(target).replace("%", "%%")}"\r\n', encoding="utf-8-sig")
            except Exception:
                pass
        return target

    ns["windows_desktop_dir"] = windows_desktop_dir
    ns["ensure_installed_exe_and_shortcut"] = ensure_installed_exe_and_shortcut

    # Manual shortcut repair button/API.
    old_post = Handler.do_POST
    def do_POST(self):
        path = ns["urllib"].parse.urlparse(self.path).path
        if path != "/api/create-desktop-shortcut":
            return old_post(self)
        try:
            target = ensure_installed_exe_and_shortcut()
            desktop = windows_desktop_dir()
            lnk = (desktop / "Sokhna Port.lnk") if desktop else None
            cmd = (desktop / "Sokhna Port.cmd") if desktop else None
            ok = bool((lnk and lnk.is_file()) or (cmd and cmd.is_file()))
            if not ok:
                raise RuntimeError("تعذر إنشاء اختصار سطح المكتب")
            self._send_json({
                "ok": True,
                "target": str(target or ""),
                "shortcut": str(lnk) if lnk and lnk.is_file() else str(cmd or ""),
                "kind": "lnk" if lnk and lnk.is_file() else "cmd",
            })
        except Exception as exc:
            self._error(exc, 400)
    Handler.do_POST = do_POST
    Handler.server_version = "CompanyInspectionDesktop/4.8.17.8"
