#!/usr/bin/env python3
"""Generate _vault-index.md — a machine-generated router index for an Obsidian vault.

Walks the vault, counts notes per branch, pulls descriptions from existing
_index.md files, flags large folders that lack an index, and writes a
two-tier routing file at the vault root that an AI agent reads first to
navigate the vault.

Vault root resolution (first match wins):
  1. --vault <path> argument
  2. "vault_path" in config.json located one directory above this script
     (the installer writes it to ~/.claude/skills/vault-analyst/config.json)

Modes:
  (default)   write <vault>/_vault-index.md
  --dry-run   print the index to stdout instead of writing
  --profile   print frontmatter field coverage as JSON (consumed by install.sh)

Stdlib only — no pip installs required. Python 3.9+.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Windows consoles may default to a legacy codepage; index content is UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR.parent / "config.json"

# Directories that hold code artifacts or app noise, never knowledge notes.
EXCLUDE_DIRS = {
    ".git", ".obsidian", ".trash", "venv", ".venv", "node_modules",
    "site-packages", "__pycache__", "dist", "build", "_attachments",
}

# Folder names (any depth) whose contents are usually low-value for analysis
# routing: archives, dumps, done-piles. Extendable via config "low_priority".
DEFAULT_LOW_PRIORITY = {"Archive", "_archive", "Dump", "_dump", "_Done", "Trash"}

NO_INDEX_FLAG_THRESHOLD = 15   # folders with >= this many notes and no _index.md get flagged
EXPAND_THRESHOLD = 200         # level-2 folders with >= this many notes get subfolders listed too
FRONTMATTER_SCAN_LINES = 60    # how deep to look for the closing '---'


def load_config(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def iter_md(folder: Path):
    """Yield all .md files under folder, pruning excluded dirs."""
    stack = [folder]
    while stack:
        d = stack.pop()
        try:
            for p in d.iterdir():
                if p.is_dir():
                    if p.name in EXCLUDE_DIRS or p.name.startswith("."):
                        continue
                    stack.append(p)
                elif p.suffix.lower() == ".md":
                    yield p
        except (PermissionError, OSError):
            continue


def count_md(folder: Path) -> int:
    return sum(1 for _ in iter_md(folder))


def frontmatter_keys(note: Path):
    """Return the set of frontmatter field names in a note, or None if no frontmatter."""
    try:
        with note.open(encoding="utf-8", errors="replace") as f:
            first = f.readline()
            if first.strip() != "---":
                return None
            keys = set()
            for _ in range(FRONTMATTER_SCAN_LINES):
                line = f.readline()
                if not line or line.strip() == "---":
                    break
                m = re.match(r"^([A-Za-z0-9_-]+)\s*:", line)
                if m:
                    keys.add(m.group(1))
            return keys
    except OSError:
        return None


def index_description(index_file: Path) -> str:
    """Pull the blockquote TL;DR (or H1) from an _index.md, single line."""
    try:
        text = index_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")  # tolerate CRLF vaults synced from Windows
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)
    for line in body.splitlines():
        line = line.strip()
        if line.startswith(">"):
            return line.lstrip("> ").strip()
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def discover_top_folders(vault: Path, excluded: set):
    return sorted(
        (d for d in vault.iterdir()
         if d.is_dir()
         and d.name not in EXCLUDE_DIRS
         and d.name not in excluded
         and not d.name.startswith(".")),
        key=lambda d: d.name.lower(),
    )


def build_profile(vault: Path, top_folders, low_priority) -> dict:
    """Measure frontmatter field coverage per top folder. Powers install-time profiling."""
    overall_fields, overall_untagged, overall_total = {}, 0, 0
    by_folder = {}
    for folder in top_folders:
        fields, untagged, total = {}, 0, 0
        for note in iter_md(folder):
            total += 1
            keys = frontmatter_keys(note)
            if not keys:
                untagged += 1
                continue
            for k in keys:
                fields[k] = fields.get(k, 0) + 1
        by_folder[folder.name] = {"total": total, "fields": fields, "untagged": untagged}
        overall_total += total
        overall_untagged += untagged
        for k, v in fields.items():
            overall_fields[k] = overall_fields.get(k, 0) + v
    # root-level loose notes
    root_notes = [p for p in vault.iterdir() if p.is_file() and p.suffix.lower() == ".md"]
    return {
        "schema_version": 1,
        "total": overall_total + len(root_notes),
        "root_notes": len(root_notes),
        "overall": {"fields": overall_fields, "untagged": overall_untagged},
        "by_folder": by_folder,
        "top_folders": [f.name for f in top_folders],
        "low_priority": sorted(low_priority),
    }


def build_index(vault: Path, top_folders, low_priority) -> str:
    lines, flags, total_notes = [], [], 0

    def rel(p: Path) -> str:
        return p.relative_to(vault).as_posix()

    lines.append("# Vault Router Index")
    lines.append("")
    lines.append("> Machine-generated by vault-analyst (`generate_vault_index.py`) — do NOT hand-edit.")
    lines.append(f"> Regenerated {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}. "
                 "Read this file first, then drill into the linked `_index.md` for the relevant branch.")
    lines.append("")

    root_notes = [p for p in vault.iterdir() if p.is_file() and p.suffix.lower() == ".md"]
    if root_notes:
        total_notes += len(root_notes)
        lines.append(f"## (root) — {len(root_notes)} loose notes at vault root")
        lines.append("")

    for folder in top_folders:
        n = count_md(folder)
        if n == 0:
            continue
        total_notes += n
        top_index = folder / "_index.md"
        link = f" — [index]({rel(top_index)})" if top_index.exists() else ""
        suffix = ""
        if folder.name in low_priority:
            suffix = " — (low priority: archive/dump)"
        elif not top_index.exists() and n >= NO_INDEX_FLAG_THRESHOLD:
            suffix = " — ⚠ no index"
            flags.append(f"{rel(folder)} ({n} notes)")
        lines.append(f"## {folder.name} — {n} notes{link}{suffix}")
        desc = index_description(top_index) if top_index.exists() else ""
        if desc:
            lines.append(desc)
        lines.append("")

        subs = sorted(
            (d for d in folder.iterdir()
             if d.is_dir() and d.name not in EXCLUDE_DIRS and not d.name.startswith(".")),
            key=lambda d: d.name.lower(),
        )
        deep_indexes = []
        for sub in subs:
            sn = count_md(sub)
            if sn == 0:
                continue
            sub_index = sub / "_index.md"
            parts = [f"- **{sub.name}** — {sn} notes"]
            if sub_index.exists():
                parts.append(f"[index]({rel(sub_index)})")
                d = index_description(sub_index)
                if d:
                    parts.append(d)
            elif sn >= NO_INDEX_FLAG_THRESHOLD and sub.name not in low_priority:
                parts.append("⚠ no index")
                flags.append(f"{rel(sub)} ({sn} notes)")
            if sub.name in low_priority:
                parts.append("(low priority: archive/dump)")
            lines.append(" — ".join(parts))

            if sn >= EXPAND_THRESHOLD:
                for s3 in sorted(
                    (d for d in sub.iterdir()
                     if d.is_dir() and d.name not in EXCLUDE_DIRS and not d.name.startswith(".")),
                    key=lambda d: d.name.lower(),
                ):
                    s3n = count_md(s3)
                    if s3n == 0:
                        continue
                    s3_index = s3 / "_index.md"
                    p3 = [f"  - {s3.name} — {s3n} notes"]
                    if s3_index.exists():
                        p3.append(f"[index]({rel(s3_index)})")
                    elif s3n >= NO_INDEX_FLAG_THRESHOLD and s3.name not in low_priority:
                        p3.append("⚠ no index")
                        flags.append(f"{rel(s3)} ({s3n} notes)")
                    lines.append(" — ".join(p3))

        # deeper _index.md files within this branch (depth >= 3)
        for p in iter_md(folder):
            if p.name == "_index.md" and len(p.relative_to(vault).parts) >= 3:
                deep_indexes.append(p)
        if deep_indexes:
            deep_indexes.sort()
            lines.append("- *Deeper indexes:* " + " · ".join(
                f"[{p.parent.name}]({rel(p)})" for p in deep_indexes))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"**Total: {total_notes} notes.**")
    lines.append("")
    if flags:
        lines.append(f"## Maintenance flags — folders ≥{NO_INDEX_FLAG_THRESHOLD} notes with no `_index.md`")
        lines.append("")
        for f in flags:
            lines.append(f"- `{f}`")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a router index for an Obsidian vault.")
    ap.add_argument("--vault", help="path to the vault root (overrides config.json)")
    ap.add_argument("--config", help="path to config.json (default: ../config.json relative to this script)")
    ap.add_argument("--dry-run", action="store_true", help="print the index instead of writing it")
    ap.add_argument("--profile", action="store_true", help="print frontmatter coverage JSON and exit")
    args = ap.parse_args()

    config = load_config(Path(args.config) if args.config else DEFAULT_CONFIG)

    vault_arg = args.vault or config.get("vault_path")
    if not vault_arg:
        print("ERROR: no vault path. Pass --vault <path> or set vault_path in config.json.", file=sys.stderr)
        return 2
    vault = Path(vault_arg).expanduser()
    if not vault.is_dir():
        print(f"ERROR: vault path does not exist or is not a directory: {vault}", file=sys.stderr)
        return 2

    excluded = set(config.get("exclude_folders", []))
    low_priority = DEFAULT_LOW_PRIORITY | set(config.get("low_priority", []))
    top_folders = discover_top_folders(vault, excluded)

    if args.profile:
        print(json.dumps(build_profile(vault, top_folders, low_priority), indent=2, ensure_ascii=False))
        return 0

    out = build_index(vault, top_folders, low_priority)
    if args.dry_run:
        print(out)
    else:
        target = vault / "_vault-index.md"
        target.write_text(out, encoding="utf-8")
        print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
