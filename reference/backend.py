#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Company Inspection Desktop local backend.
Stdlib-only: SQLite master DB + physical attachment files + local web server.
"""
from __future__ import annotations

import argparse
import base64
import copy
import ctypes
import datetime as dt
import hashlib
import html
import io
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sqlite3
import sys
import threading
import time
import urllib.parse
import webbrowser
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

APP_VERSION = "4.8.16.11-DESKTOP"
SCHEMA_VERSION = 4
STORES = ["companies", "items", "attachments", "inspections", "findings", "ncrs", "masterItems", "inspectionMasterItems"]
DEFAULT_PORT = 8766
MAX_JSON_BODY = 1024 * 1024 * 1024  # 1 GiB, local-only server
HEARTBEAT_LOCK = threading.Lock()
LAST_HEARTBEAT = 0.0
HEARTBEAT_STARTED = False


# PyInstaller-safe web asset root. In a frozen build, bundled assets live under sys._MEIPASS.
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
WEB_ROOT = APP_DIR / "app"


def local_appdata() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        return Path(root) / "CompanyInspectionDesktop"
    return Path.home() / ".company_inspection_desktop"

CONFIG_DIR = local_appdata()
CONFIG_FILE = CONFIG_DIR / "config.json"


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_part(value: Any, fallback: str = "x") -> str:
    s = str(value or fallback).strip()
    s = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return (s[:120] or fallback)


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def ensure_dirs(root: Path) -> Dict[str, Path]:
    paths = {
        "root": root,
        "database": root / "Database",
        "attachments": root / "Attachments",
        "daily": root / "Backups" / "Daily",
        "weekly": root / "Backups" / "Weekly",
        "manual": root / "Backups" / "Manual",
        "recovery_weekly": root / "Recovery" / "Weekly",
        "recovery_manual": root / "Recovery" / "Manual",
        "logs": root / "Logs",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


def is_fixed_windows_drive(path: Path) -> bool:
    if os.name != "nt":
        return True
    drive = path.resolve().drive
    if not drive:
        return False
    # DRIVE_FIXED = 3. Prevent putting the master DB on USB/removable/network media.
    try:
        return int(ctypes.windll.kernel32.GetDriveTypeW(drive + "\\")) == 3
    except Exception:
        return True


def choose_data_root() -> Path:
    """Return a stable internal-disk data location without requiring Python/Tkinter.

    The desktop EXE is fully self-contained. On first run we store the master SQLite
    database, physical attachments, backups and recovery files under LOCALAPPDATA.
    This avoids failures on PCs without Python/Tkinter and keeps the master data on
    the Windows system drive rather than beside a removable copy of the EXE.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            old = Path(data.get("dataRoot", ""))
            if old and old.exists() and is_fixed_windows_drive(old):
                return old
    except Exception:
        pass

    if os.name == "nt":
        root_base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home()))
        root = root_base / "SokhnaPort" / "CompanyInspectionData"
    else:
        root = Path.home() / "CompanyInspectionData"
    root.mkdir(parents=True, exist_ok=True)
    try:
        CONFIG_FILE.write_text(json.dumps({"dataRoot": str(root)}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return root


class FileLock:
    def __init__(self, path: Path):
        self.path = path
        self.fp = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fp = open(self.path, "a+b")
        self.fp.seek(0)
        self.fp.write(b"0")
        self.fp.flush()
        self.fp.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.fp.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            try:
                self.fp.close()
            except Exception:
                pass
            self.fp = None
            raise RuntimeError("البرنامج مفتوح بالفعل على هذا المجلد. أغلق النسخة الأخرى ثم أعد المحاولة.")

    def release(self) -> None:
        if not self.fp:
            return
        try:
            self.fp.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.fp.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fp.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            self.fp.close()
        except Exception:
            pass
        self.fp = None


class DesktopStore:
    def __init__(self, root: Path):
        self.paths = ensure_dirs(root)
        self.db_path = self.paths["database"] / "company_master.sqlite3"
        self.lock = threading.RLock()
        self.file_lock = FileLock(self.paths["database"] / ".company_master.lock")
        self.file_lock.acquire()
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=20)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def close(self) -> None:
        with self.lock:
            try:
                self.conn.close()
            except Exception:
                pass
            self.file_lock.release()

    def _init_db(self) -> None:
        with self.lock:
            c = self.conn
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=FULL")
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA busy_timeout=10000")
            c.executescript("""
                CREATE TABLE IF NOT EXISTS records(
                    store TEXT NOT NULL,
                    id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    modified_at TEXT,
                    created_at TEXT,
                    is_deleted INTEGER NOT NULL DEFAULT 0,
                    company_id TEXT,
                    inspection_id TEXT,
                    entity_id TEXT,
                    PRIMARY KEY(store,id)
                );
                CREATE INDEX IF NOT EXISTS idx_records_store_deleted ON records(store,is_deleted);
                CREATE INDEX IF NOT EXISTS idx_records_company ON records(store,company_id);
                CREATE INDEX IF NOT EXISTS idx_records_inspection ON records(store,inspection_id);
                CREATE INDEX IF NOT EXISTS idx_records_entity ON records(store,entity_id);
                CREATE TABLE IF NOT EXISTS meta(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
            c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('desktopAppVersion',?)", (APP_VERSION,))
            c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schemaVersion',?)", (str(SCHEMA_VERSION),))
            c.commit()

    def _record_row(self, store: str, rec: Dict[str, Any]) -> Tuple[Any, ...]:
        return (
            store,
            str(rec.get("id", "")),
            json_dumps(rec),
            str(rec.get("modifiedAt", "") or ""),
            str(rec.get("createdAt", "") or ""),
            1 if rec.get("isDeleted") else 0,
            str(rec.get("companyId", "") or ""),
            str(rec.get("inspectionId", "") or ""),
            str(rec.get("entityId", "") or ""),
        )

    def _upsert(self, cur: sqlite3.Cursor, store: str, rec: Dict[str, Any]) -> None:
        if store not in STORES:
            raise ValueError(f"مخزن غير معروف: {store}")
        if not isinstance(rec, dict) or not rec.get("id"):
            raise ValueError(f"سجل غير صالح في {store}")
        rec = self._externalize_record(store, copy.deepcopy(rec), cur)
        cur.execute(
            """INSERT INTO records(store,id,data,modified_at,created_at,is_deleted,company_id,inspection_id,entity_id)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(store,id) DO UPDATE SET
                 data=excluded.data, modified_at=excluded.modified_at, created_at=excluded.created_at,
                 is_deleted=excluded.is_deleted, company_id=excluded.company_id,
                 inspection_id=excluded.inspection_id, entity_id=excluded.entity_id""",
            self._record_row(store, rec),
        )

    @staticmethod
    def _parse_data_url(data_url: str) -> Tuple[str, bytes]:
        if not isinstance(data_url, str) or not data_url.startswith("data:"):
            raise ValueError("بيانات الملف ليست Data URL")
        head, sep, body = data_url.partition(",")
        if not sep:
            raise ValueError("Data URL غير صالح")
        mime = head[5:].split(";", 1)[0] or "application/octet-stream"
        if ";base64" in head:
            raw = base64.b64decode(body, validate=False)
        else:
            raw = urllib.parse.unquote_to_bytes(body)
        return mime, raw

    def _write_bytes(self, rel: str, raw: bytes) -> Tuple[str, int]:
        rel = rel.replace("\\", "/").lstrip("/")
        target = (self.paths["root"] / rel).resolve()
        root = self.paths["root"].resolve()
        if root not in target.parents and target != root:
            raise ValueError("مسار مرفق غير مسموح")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        with open(tmp, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
        return hashlib.sha256(raw).hexdigest(), len(raw)

    def _get_existing_raw(self, cur: sqlite3.Cursor, store: str, rec_id: str) -> Optional[Dict[str, Any]]:
        row = cur.execute("SELECT data FROM records WHERE store=? AND id=?", (store, rec_id)).fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except Exception:
            return None

    def _externalize_attachment(self, rec: Dict[str, Any], cur: sqlite3.Cursor) -> Dict[str, Any]:
        existing = self._get_existing_raw(cur, "attachments", str(rec.get("id"))) or {}
        data = rec.get("dataUrl", "")
        if isinstance(data, str) and data.startswith("data:"):
            mime, raw = self._parse_data_url(data)
            ext = Path(str(rec.get("filename") or "")).suffix.lower()
            if not ext:
                ext = mimetypes.guess_extension(mime) or ".bin"
            entity_type = safe_part(rec.get("entityType") or "other")
            entity_id = safe_part(rec.get("entityId") or "unknown")
            rel = f"Attachments/{entity_type}/{entity_id}/{safe_part(rec.get('id'))}{ext}"
            sha, size = self._write_bytes(rel, raw)
            rec["relativePath"] = rel
            rec["externalPath"] = rel.replace("Attachments/", "", 1)
            rec["externalAttachment"] = True
            rec["sha256"] = sha
            rec["size"] = int(size)
            rec["mime"] = rec.get("mime") or mime
            rec["dataUrl"] = ""
        elif isinstance(data, str) and data.startswith("/api/file"):
            rec["dataUrl"] = ""
            for k in ("relativePath", "externalPath", "externalAttachment", "sha256", "size", "mime"):
                if not rec.get(k) and existing.get(k) not in (None, ""):
                    rec[k] = existing.get(k)
        elif not data:
            # A normal fetched record has dataUrl='' in SQLite. Keep its physical metadata.
            for k in ("relativePath", "externalPath", "externalAttachment", "sha256", "size", "mime"):
                if not rec.get(k) and existing.get(k) not in (None, ""):
                    rec[k] = existing.get(k)
            rec["dataUrl"] = ""
        else:
            # Unknown URL should never be persisted as the master file source.
            rec["dataUrl"] = ""
        return rec

    def _externalize_finding_photo(self, rec: Dict[str, Any], role: str, existing: Dict[str, Any]) -> None:
        field = f"{role}PhotoData"
        path_field = f"_{role}PhotoPath"
        sha_field = f"_{role}PhotoSha256"
        mime_field = f"_{role}PhotoMime"
        size_field = f"_{role}PhotoSize"
        marker_field = f"{role}PhotoExternal"
        value = rec.get(field, None)
        if isinstance(value, str) and value.startswith("data:"):
            mime, raw = self._parse_data_url(value)
            ext = mimetypes.guess_extension(mime) or ".jpg"
            if ext == ".jpe":
                ext = ".jpg"
            rel = f"Attachments/finding/{safe_part(rec.get('id'))}/{role}_{safe_part(rec.get('id'))}{ext}"
            sha, size = self._write_bytes(rel, raw)
            rec[path_field] = rel
            rec[sha_field] = sha
            rec[mime_field] = mime
            rec[size_field] = int(size)
            rec[marker_field] = True
            rec[field] = ""
        elif isinstance(value, str) and value.startswith("/api/file"):
            rec[field] = ""
            for k in (path_field, sha_field, mime_field, size_field, marker_field):
                if rec.get(k) in (None, "") and existing.get(k) not in (None, ""):
                    rec[k] = existing.get(k)
        elif value == "":
            # Data-only sync records deliberately have no embedded photo but DO carry path/hash metadata.
            # Preserve that linkage. A UI deletion clears the path metadata too (patched in desktop HTML).
            if rec.get(path_field):
                rec[field] = ""
                rec[marker_field] = bool(rec.get(marker_field, True))
            else:
                # Logical deletion: unlink it from the record. The old physical file stays on disk for recovery safety.
                rec[field] = ""
                rec[path_field] = ""
                rec[sha_field] = ""
                rec[size_field] = 0
                rec[marker_field] = False
        elif value is None:
            # Field omitted: preserve existing linkage.
            rec[field] = ""
            for k in (path_field, sha_field, mime_field, size_field, marker_field):
                if k not in rec and k in existing:
                    rec[k] = existing[k]
        else:
            rec[field] = ""

    def _externalize_record(self, store: str, rec: Dict[str, Any], cur: sqlite3.Cursor) -> Dict[str, Any]:
        if store == "attachments":
            return self._externalize_attachment(rec, cur)
        if store == "findings":
            existing = self._get_existing_raw(cur, "findings", str(rec.get("id"))) or {}
            self._externalize_finding_photo(rec, "before", existing)
            self._externalize_finding_photo(rec, "after", existing)
        return rec

    def put(self, store: str, rec: Dict[str, Any]) -> None:
        with self.lock:
            cur = self.conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE")
                self._upsert(cur, store, rec)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def put_many(self, store: str, rows: Iterable[Dict[str, Any]]) -> None:
        with self.lock:
            cur = self.conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE")
                for rec in rows:
                    self._upsert(cur, store, rec)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def atomic_batches(self, batches: Dict[str, List[Dict[str, Any]]]) -> None:
        with self.lock:
            cur = self.conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE")
                for store, rows in batches.items():
                    for rec in rows or []:
                        self._upsert(cur, store, rec)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def clear(self, store: str) -> None:
        if store not in STORES:
            raise ValueError("مخزن غير معروف")
        with self.lock:
            self.conn.execute("DELETE FROM records WHERE store=?", (store,))
            self.conn.commit()

    def delete_one(self, store: str, rec_id: str) -> None:
        if store not in STORES:
            raise ValueError("مخزن غير معروف")
        with self.lock:
            self.conn.execute("DELETE FROM records WHERE store=? AND id=?", (store, rec_id))
            self.conn.commit()

    def raw_one(self, store: str, rec_id: str) -> Optional[Dict[str, Any]]:
        if store not in STORES:
            raise ValueError("مخزن غير معروف")
        with self.lock:
            row = self.conn.execute("SELECT data FROM records WHERE store=? AND id=?", (store, rec_id)).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def raw_all(self, store: str) -> List[Dict[str, Any]]:
        if store not in STORES:
            raise ValueError("مخزن غير معروف")
        with self.lock:
            rows = self.conn.execute("SELECT data FROM records WHERE store=? ORDER BY rowid", (store,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def all_data(self) -> Dict[str, List[Dict[str, Any]]]:
        return {s: self.raw_all(s) for s in STORES}

    @staticmethod
    def _file_url(rel: str) -> str:
        return "/api/file?path=" + urllib.parse.quote(rel.replace("\\", "/"), safe="")

    def client_record(self, store: str, rec: Dict[str, Any]) -> Dict[str, Any]:
        out = copy.deepcopy(rec)
        if store == "attachments" and not out.get("isDeleted") and out.get("relativePath"):
            p = self.paths["root"] / str(out.get("relativePath"))
            if p.exists():
                out["dataUrl"] = self._file_url(str(out.get("relativePath")))
        if store == "findings" and not out.get("isDeleted"):
            for role in ("before", "after"):
                pf = f"_{role}PhotoPath"
                df = f"{role}PhotoData"
                rel = out.get(pf)
                if rel and (self.paths["root"] / str(rel)).exists():
                    out[df] = self._file_url(str(rel))
        return out

    def get_one(self, store: str, rec_id: str) -> Optional[Dict[str, Any]]:
        r = self.raw_one(store, rec_id)
        return self.client_record(store, r) if r else None

    def get_all(self, store: str) -> List[Dict[str, Any]]:
        return [self.client_record(store, r) for r in self.raw_all(store)]

    def replace_all(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        for store in STORES:
            rows = data.get(store, [])
            if not isinstance(rows, list):
                raise ValueError(f"بيانات {store} غير صالحة")
            for rec in rows:
                if not isinstance(rec, dict) or not rec.get("id"):
                    raise ValueError(f"يوجد سجل غير صالح في {store}")
        # Mandatory safety copy immediately before destructive full replacement.
        self.create_backup("PRE_RESTORE")
        with self.lock:
            cur = self.conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE")
                cur.execute("DELETE FROM records")
                for store in STORES:
                    for rec in data.get(store, []):
                        self._upsert(cur, store, rec)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def _rel_file_bytes(self, rel: str) -> Optional[bytes]:
        if not rel:
            return None
        p = (self.paths["root"] / rel).resolve()
        root = self.paths["root"].resolve()
        if root not in p.parents or not p.is_file():
            return None
        return p.read_bytes()

    @staticmethod
    def _data_url(mime: str, raw: bytes) -> str:
        return f"data:{mime or 'application/octet-stream'};base64," + base64.b64encode(raw).decode("ascii")

    def export_data(self, include_files: bool, since: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        data: Dict[str, List[Dict[str, Any]]] = {}
        for store in STORES:
            rows = self.raw_all(store)
            if since:
                rows = [r for r in rows if str(r.get("modifiedAt") or r.get("createdAt") or "") > since]
            out_rows = []
            for rec0 in rows:
                rec = copy.deepcopy(rec0)
                if store == "attachments":
                    rec["dataUrl"] = ""
                    if include_files and not rec.get("isDeleted") and rec.get("relativePath"):
                        raw = self._rel_file_bytes(str(rec.get("relativePath")))
                        if raw is not None:
                            rec["dataUrl"] = self._data_url(str(rec.get("mime") or "application/octet-stream"), raw)
                elif store == "findings":
                    for role in ("before", "after"):
                        df = f"{role}PhotoData"
                        pf = f"_{role}PhotoPath"
                        mf = f"_{role}PhotoMime"
                        rec[df] = ""
                        if include_files and not rec.get("isDeleted") and rec.get(pf):
                            raw = self._rel_file_bytes(str(rec.get(pf)))
                            if raw is not None:
                                rec[df] = self._data_url(str(rec.get(mf) or "image/jpeg"), raw)
                out_rows.append(rec)
            data[store] = out_rows
        return data

    def export_payload(self, kind: str, include_files: bool, since: Optional[str], source_device_id: str, source_device_name: str) -> Dict[str, Any]:
        generated = now_iso()
        data = self.export_data(include_files=include_files, since=since)
        payload = {
            "schema": "company-mobile-sync",
            "schemaVersion": SCHEMA_VERSION,
            "kind": kind,
            "exportId": hashlib.sha256((generated + source_device_id + kind).encode()).hexdigest()[:32],
            "sourceRole": "computer-master",
            "sourceDeviceId": source_device_id or "computer-master",
            "sourceDeviceName": source_device_name or "الكمبيوتر الرئيسي",
            "generatedAt": generated,
            "since": since or "1970-01-01T00:00:00.000Z",
            "appVersion": APP_VERSION,
            "attachmentMode": "embedded" if include_files else "index-only",
            "data": data,
            "counts": {s: len(data.get(s, [])) for s in STORES},
            "companySerialHighWater": max([int(c.get("companySerial") or 0) for c in data.get("companies", [])] + [0]),
        }
        return payload

    def _sqlite_snapshot(self, out_db: Path) -> None:
        out_db.parent.mkdir(parents=True, exist_ok=True)
        if out_db.exists():
            out_db.unlink()
        with self.lock:
            dst = sqlite3.connect(str(out_db))
            try:
                self.conn.backup(dst)
            finally:
                dst.close()

    def create_backup(self, category: str = "Manual") -> Path:
        cat = category.upper()
        if cat == "DAILY":
            dest_dir = self.paths["daily"]
            prefix = "DAILY"
        elif cat == "WEEKLY":
            dest_dir = self.paths["weekly"]
            prefix = "WEEKLY"
        else:
            dest_dir = self.paths["manual"]
            prefix = safe_part(category.upper(), "MANUAL")
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / f"{prefix}_BACKUP_{stamp()}.zip"
        tmp_db = self.paths["database"] / f".backup_{stamp()}.sqlite3"
        self._sqlite_snapshot(tmp_db)
        try:
            with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
                z.write(tmp_db, arcname="Database/company_master.sqlite3")
                att_root = self.paths["attachments"]
                for p in att_root.rglob("*"):
                    if p.is_file():
                        z.write(p, arcname=str(p.relative_to(self.paths["root"])).replace("\\", "/"))
                manifest = {
                    "type": "Company Inspection Desktop Backup",
                    "version": APP_VERSION,
                    "createdAt": now_iso(),
                    "category": category,
                    "dataRoot": str(self.paths["root"]),
                }
                z.writestr("BACKUP_INFO.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        finally:
            try:
                tmp_db.unlink()
            except Exception:
                pass
        return out

    def _xlsx_xml_escape(self, value: Any) -> str:
        return html.escape(str(value if value is not None else ""), quote=False)

    def create_recovery_xlsx(self, category: str = "Manual") -> Path:
        cat = category.upper()
        dest_dir = self.paths["recovery_weekly"] if cat == "WEEKLY" else self.paths["recovery_manual"]
        prefix = "WEEKLY" if cat == "WEEKLY" else "MANUAL"
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / f"{prefix}_RECOVERY_{stamp()}.xlsx"
        data = self.all_data()
        sheets: List[Tuple[str, List[List[Any]]]] = []
        for store in STORES:
            rows = data.get(store, [])
            keys: List[str] = []
            preferred = ["id", "name", "companyId", "inspectionId", "entityType", "entityId", "filename", "inspectionCode", "date", "status", "no", "modifiedAt", "createdAt", "isDeleted"]
            all_keys = set()
            for r in rows:
                all_keys.update(r.keys())
            for k in preferred:
                if k in all_keys and k not in keys:
                    keys.append(k)
            for k in sorted(all_keys):
                if k not in keys and k not in {"dataUrl", "beforePhotoData", "afterPhotoData"}:
                    keys.append(k)
            table: List[List[Any]] = [keys + ["JSON_FULL"]]
            for r in rows:
                vals = []
                for k in keys:
                    v = r.get(k, "")
                    if isinstance(v, (dict, list)):
                        v = json.dumps(v, ensure_ascii=False)
                    vals.append(v)
                vals.append(json.dumps(r, ensure_ascii=False))
                table.append(vals)
            sheets.append((store[:31], table))

        def col_name(n: int) -> str:
            s = ""
            while n:
                n, r = divmod(n - 1, 26)
                s = chr(65 + r) + s
            return s

        content_types = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
            '<Default Extension="xml" ContentType="application/xml"/>',
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
        ]
        for i in range(len(sheets)):
            content_types.append(f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        content_types.append('</Types>')

        root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
        wb_sheets = []
        wb_rels = []
        for i, (name, _) in enumerate(sheets, 1):
            wb_sheets.append(f'<sheet name="{html.escape(name, quote=True)}" sheetId="{i}" r:id="rId{i}"/>')
            wb_rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
        styles_id = len(sheets) + 1
        wb_rels.append(f'<Relationship Id="rId{styles_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
        workbook = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{''.join(wb_sheets)}</sheets></workbook>'''
        workbook_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{''.join(wb_rels)}</Relationships>'''
        styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Arial"/></font><font><b/><sz val="11"/><name val="Arial"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs></styleSheet>'''

        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", "".join(content_types))
            z.writestr("_rels/.rels", root_rels)
            z.writestr("xl/workbook.xml", workbook)
            z.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
            z.writestr("xl/styles.xml", styles)
            for idx, (_, table) in enumerate(sheets, 1):
                xml_rows = []
                for rno, row in enumerate(table, 1):
                    cells = []
                    for cno, value in enumerate(row, 1):
                        ref = f"{col_name(cno)}{rno}"
                        style = ' s="1"' if rno == 1 else ""
                        text = self._xlsx_xml_escape(value)
                        cells.append(f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{text}</t></is></c>')
                    xml_rows.append(f'<row r="{rno}">{"".join(cells)}</row>')
                sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheetViews><sheetView rightToLeft="1" workbookViewId="0"/></sheetViews><sheetData>{''.join(xml_rows)}</sheetData></worksheet>'''
                z.writestr(f"xl/worksheets/sheet{idx}.xml", sheet_xml)
        return out

    @staticmethod
    def retain(directory: Path, pattern: str, keep: int) -> None:
        files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in files[keep:]:
            try:
                p.unlink()
            except Exception:
                pass

    def automatic_maintenance(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        today = dt.date.today()
        daily_tag = today.strftime("%Y%m%d")
        if not list(self.paths["daily"].glob(f"DAILY_BACKUP_{daily_tag}_*.zip")):
            result["daily"] = str(self.create_backup("DAILY"))
        iso = today.isocalendar()
        weekly_marker = f"{iso.year}-W{iso.week:02d}"
        weekly_meta = self.paths["weekly"] / ".last_weekly.txt"
        old = weekly_meta.read_text(encoding="utf-8").strip() if weekly_meta.exists() else ""
        if old != weekly_marker:
            result["weekly"] = str(self.create_backup("WEEKLY"))
            result["recoveryWeekly"] = str(self.create_recovery_xlsx("WEEKLY"))
            weekly_meta.write_text(weekly_marker, encoding="utf-8")
        self.retain(self.paths["daily"], "DAILY_BACKUP_*.zip", 7)
        self.retain(self.paths["weekly"], "WEEKLY_BACKUP_*.zip", 4)
        self.retain(self.paths["recovery_weekly"], "WEEKLY_RECOVERY_*.xlsx", 4)
        return result

    def health(self) -> Dict[str, Any]:
        with self.lock:
            q = self.conn.execute("PRAGMA quick_check").fetchone()
            counts = {s: self.conn.execute("SELECT COUNT(*) FROM records WHERE store=?", (s,)).fetchone()[0] for s in STORES}
        def newest(folder: Path, glob: str) -> str:
            arr = sorted(folder.glob(glob), key=lambda p: p.stat().st_mtime, reverse=True)
            return arr[0].name if arr else ""
        return {
            "ok": True,
            "appVersion": APP_VERSION,
            "schemaVersion": SCHEMA_VERSION,
            "database": str(self.db_path),
            "dataRoot": str(self.paths["root"]),
            "attachmentsRoot": str(self.paths["attachments"]),
            "quickCheck": q[0] if q else "unknown",
            "counts": counts,
            "lastDailyBackup": newest(self.paths["daily"], "DAILY_BACKUP_*.zip"),
            "lastWeeklyBackup": newest(self.paths["weekly"], "WEEKLY_BACKUP_*.zip"),
            "lastWeeklyRecovery": newest(self.paths["recovery_weekly"], "WEEKLY_RECOVERY_*.xlsx"),
        }


STORE: DesktopStore


class Handler(BaseHTTPRequestHandler):
    server_version = "CompanyInspectionDesktop/4.8.16.11"

    def log_message(self, fmt: str, *args: Any) -> None:
        try:
            log = STORE.paths["logs"] / "server.log"
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {self.address_string()} {fmt % args}\n")
        except Exception:
            pass

    def _send_json(self, obj: Any, status: int = 200) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _error(self, exc: Exception, status: int = 400) -> None:
        self._send_json({"ok": False, "error": str(exc)}, status)

    def _read_json(self) -> Any:
        try:
            n = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > MAX_JSON_BODY:
            raise ValueError("حجم الطلب غير صالح")
        raw = self.rfile.read(n)
        return json.loads(raw.decode("utf-8"))

    def _serve_file(self, path: Path, download_name: Optional[str] = None, mime: Optional[str] = None) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        ctype = mime or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        size = path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        if download_name:
            quoted = urllib.parse.quote(download_name)
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quoted}")
        self.end_headers()
        with open(path, "rb") as f:
            shutil.copyfileobj(f, self.wfile, length=1024 * 1024)

    def do_GET(self) -> None:
        try:
            u = urllib.parse.urlparse(self.path)
            path = u.path
            q = urllib.parse.parse_qs(u.query)
            if path == "/api/health":
                self._send_json(STORE.health())
                return
            if path.startswith("/api/store/"):
                parts = path.strip("/").split("/")
                if len(parts) < 3:
                    raise ValueError("مسار غير صالح")
                store = parts[2]
                if len(parts) == 3:
                    self._send_json({"ok": True, "rows": STORE.get_all(store)})
                else:
                    rec_id = urllib.parse.unquote("/".join(parts[3:]))
                    self._send_json({"ok": True, "row": STORE.get_one(store, rec_id)})
                return
            if path == "/api/file":
                rel = urllib.parse.unquote((q.get("path") or [""])[0]).replace("\\", "/").lstrip("/")
                root = STORE.paths["root"].resolve()
                target = (root / rel).resolve()
                if root not in target.parents:
                    raise ValueError("مسار غير مسموح")
                self._serve_file(target)
                return
            if path == "/api/export":
                mode = (q.get("mode") or ["full"])[0]
                include_files = (q.get("files") or ["1"])[0] == "1"
                since = (q.get("since") or [""])[0] or None
                device_id = (q.get("deviceId") or ["computer-master"])[0]
                device_name = (q.get("deviceName") or ["الكمبيوتر الرئيسي"])[0]
                if mode == "mobile-full":
                    kind = "full-mobile-snapshot" if include_files else "full-mobile-data-only"
                    since = None
                    fname = f"MOBILE_{'FULL' if include_files else 'DATA_ONLY'}_{stamp()}.sync.json"
                elif mode == "incremental":
                    kind = "incremental-with-attachments" if include_files else "incremental-data-only"
                    fname = f"SYNC_{'FULL' if include_files else 'DATA_ONLY'}_{stamp()}.sync.json"
                elif mode == "backup":
                    kind = "full-backup"
                    since = None
                    fname = f"BACKUP_{APP_VERSION}_{stamp()}.json"
                else:
                    raise ValueError("نوع تصدير غير معروف")
                payload = STORE.export_payload(kind, include_files, since, device_id, device_name)
                raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Disposition", f"attachment; filename={fname}")
                self.send_header("X-Generated-At", str(payload.get("generatedAt") or ""))
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)
                return

            if path == "/api/ping":
                note_heartbeat()
                self._send_json({"ok": True})
                return
            if path in ("/", ""):
                self.send_response(302)
                self.send_header("Location", "/app/index.html")
                self.end_headers()
                return
            if path.startswith("/app/"):
                rel = urllib.parse.unquote(path[len("/app/"):]) or "index.html"
                target = (WEB_ROOT / rel).resolve()
                if WEB_ROOT.resolve() not in target.parents and target != WEB_ROOT.resolve():
                    raise ValueError("مسار غير مسموح")
                self._serve_file(target)
                return
            self.send_error(404)
        except BrokenPipeError:
            pass
        except Exception as e:
            self._error(e, 400)

    def do_POST(self) -> None:
        try:
            u = urllib.parse.urlparse(self.path)
            path = u.path
            body = self._read_json()
            if path == "/api/put":
                STORE.put(str(body.get("store")), body.get("row"))
                self._send_json({"ok": True})
                return
            if path == "/api/put-many":
                STORE.put_many(str(body.get("store")), body.get("rows") or [])
                self._send_json({"ok": True})
                return
            if path == "/api/atomic-batches":
                STORE.atomic_batches(body.get("batches") or {})
                self._send_json({"ok": True})
                return
            if path == "/api/clear":
                STORE.clear(str(body.get("store")))
                self._send_json({"ok": True})
                return
            if path == "/api/delete-one":
                STORE.delete_one(str(body.get("store")), str(body.get("id")))
                self._send_json({"ok": True})
                return
            if path == "/api/replace-all":
                STORE.replace_all(body.get("data") or {})
                self._send_json({"ok": True})
                return
            if path == "/api/manual-backup":
                p = STORE.create_backup("MANUAL")
                self._send_json({"ok": True, "path": str(p), "name": p.name})
                return
            if path == "/api/manual-recovery":
                p = STORE.create_recovery_xlsx("MANUAL")
                self._send_json({"ok": True, "path": str(p), "name": p.name})
                return
            self.send_error(404)
        except BrokenPipeError:
            pass
        except Exception as e:
            self._error(e, 400)


def note_heartbeat() -> None:
    global LAST_HEARTBEAT, HEARTBEAT_STARTED
    with HEARTBEAT_LOCK:
        LAST_HEARTBEAT = time.time()
        HEARTBEAT_STARTED = True


def launch_app_window(url: str) -> None:
    """Open the local UI like a desktop app. No Python/Batch/external project files required."""
    if os.name == "nt":
        candidates = [
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
        ]
        edge = next((x for x in candidates if str(x) and x.exists()), None)
        if edge:
            profile = CONFIG_DIR / "EdgeAppProfile"
            profile.mkdir(parents=True, exist_ok=True)
            try:
                subprocess.Popen([
                    str(edge),
                    f"--app={url}",
                    f"--user-data-dir={profile}",
                    "--no-first-run",
                    "--disable-features=msEdgeSidebarV2",
                    "--start-maximized",
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except Exception:
                pass
    webbrowser.open(url)


def start_idle_shutdown(server: ThreadingHTTPServer) -> None:
    """Close the hidden local server after the app window has been closed."""
    def worker():
        while True:
            time.sleep(5)
            with HEARTBEAT_LOCK:
                started = HEARTBEAT_STARTED
                age = time.time() - LAST_HEARTBEAT if started else 0
            if started and age > 35:
                try:
                    server.shutdown()
                except Exception:
                    pass
                return
    threading.Thread(target=worker, daemon=True).start()


def select_port(start: int) -> int:
    import socket
    for p in range(start, start + 20):
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p))
            return p
        except OSError:
            pass
        finally:
            s.close()
    raise RuntimeError("تعذر إيجاد منفذ محلي متاح لتشغيل البرنامج")


def main() -> int:
    global STORE
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default="")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    root = Path(args.data_root).expanduser().resolve() if args.data_root else choose_data_root()
    if os.name == "nt" and not args.data_root and not is_fixed_windows_drive(root):
        raise RuntimeError("مجلد قاعدة البيانات يجب أن يكون على هارد داخلي ثابت")
    STORE = DesktopStore(root)
    try:
        port = select_port(args.port)
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        # Delay automatic backup/recovery a few seconds so first-run default lists are already seeded.
        threading.Timer(8.0, lambda: STORE.automatic_maintenance()).start()
        url = f"http://127.0.0.1:{port}/app/index.html"
        print("=" * 68)
        print("برنامج متابعة الشركات والتفتيشات — نسخة الكمبيوتر")
        print(f"الإصدار: {APP_VERSION}")
        print(f"قاعدة البيانات: {STORE.db_path}")
        print(f"المرفقات: {STORE.paths['attachments']}")
        print(f"الرابط المحلي: {url}")
        print("اترك هذه النافذة مفتوحة أثناء استخدام البرنامج.")
        print("=" * 68)
        start_idle_shutdown(server)
        if not args.no_browser:
            threading.Timer(0.7, lambda: launch_app_window(url)).start()
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            server.server_close()  # type: ignore[name-defined]
        except Exception:
            pass
        STORE.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
