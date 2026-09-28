from pathlib import Path

p=Path("buildsrc/v4179_backend_ext.py")
s=p.read_text(encoding="utf-8")
needle="def install(ns: Dict[str, Any]) -> None:\n"
repl="def install(ns: Dict[str, Any]) -> None:\n    ns['APP_VERSION']='4.8.17.9-DESKTOP'\n"
if repl not in s:
    if needle not in s:
        raise SystemExit("v4179 install marker missing")
    s=s.replace(needle,repl,1)
p.write_text(s,encoding="utf-8")
print("v4.8.17.9 runtime version fix applied")
