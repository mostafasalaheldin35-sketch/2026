from pathlib import Path

p = Path('buildsrc/backend.py')
s = p.read_text(encoding='utf-8')
old = '    root = Path(args.data_root).expanduser().resolve() if args.data_root else choose_data_root()\n'
new = '    root = selected_data_root(Path(args.data_root)) if args.data_root else choose_data_root()\n'
if new in s:
    print('v4.8.17.4 CLI data-root canonicalization already applied')
elif old in s:
    p.write_text(s.replace(old, new, 1), encoding='utf-8')
    print('v4.8.17.4 CLI data-root canonicalization applied')
else:
    raise SystemExit('Expected v4.8.17.4 backend data-root line not found')
