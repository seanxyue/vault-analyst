#!/usr/bin/env python3
"""Small helpers for install.sh — JSON config, hashes, folder discovery.

Keeps all parsing/serialization out of bash. Stdlib only.

Subcommands:
  get <config.json> <key>                       print config value ("" if missing)
  write-config <config.json> <vault> <excludes> write/merge config (excludes comma-separated, may be "")
  top-folders <vault> [<excludes>]              print discovered top-level folder names, one per line
  record-hashes <config.json> <dir> <f1> [...]  store sha256 of <dir>/<fN> into config "file_hashes"
  check-hashes <config.json> <dir>              exit 0 = clean/no record, exit 3 = user-modified files
"""

import hashlib
import json
import sys
from pathlib import Path

EXCLUDE_DIRS = {
    ".git", ".obsidian", ".trash", "venv", ".venv", "node_modules",
    "site-packages", "__pycache__", "dist", "build", "_attachments",
}


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def save(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, cfg_path = sys.argv[1], Path(sys.argv[2])

    if cmd == "get":
        value = load(cfg_path).get(sys.argv[3], "")
        if isinstance(value, list):
            print(",".join(value))
        else:
            print(value)
        return 0

    if cmd == "write-config":
        cfg = load(cfg_path)
        cfg["schema_version"] = 1
        cfg["vault_path"] = sys.argv[3]
        excludes = [e.strip() for e in sys.argv[4].split(",") if e.strip()] if len(sys.argv) > 4 else []
        cfg["exclude_folders"] = excludes
        save(cfg_path, cfg)
        return 0

    if cmd == "top-folders":
        vault = Path(sys.argv[3]).expanduser()
        excludes = set(e.strip() for e in sys.argv[4].split(",") if e.strip()) if len(sys.argv) > 4 else set()
        if not vault.is_dir():
            return 2
        for d in sorted(vault.iterdir(), key=lambda p: p.name.lower()):
            if d.is_dir() and not d.name.startswith(".") and d.name not in EXCLUDE_DIRS and d.name not in excludes:
                print(d.name)
        return 0

    if cmd == "record-hashes":
        base = Path(sys.argv[3])
        cfg = load(cfg_path)
        cfg["file_hashes"] = {name: sha256(base / name) for name in sys.argv[4:] if (base / name).is_file()}
        save(cfg_path, cfg)
        return 0

    if cmd == "check-hashes":
        base = Path(sys.argv[3])
        hashes = load(cfg_path).get("file_hashes", {})
        for name, expected in hashes.items():
            p = base / name
            if p.is_file() and sha256(p) != expected:
                print(name)  # report which files were modified
                sys.exit(3)
        return 0

    print(f"unknown subcommand: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
