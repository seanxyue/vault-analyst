#!/usr/bin/env python3
"""Build a procedurally-generated fixture vault for testing vault-analyst.

Creates generic folders and lorem-ipsum notes — nothing derived from any
real vault. Usage: python tests/make_fixture.py <target-dir>
"""

import sys
from pathlib import Path

LOREM = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor.\n"


def note(path: Path, title: str, fm: dict | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = []
    if fm is not None:
        parts.append("---")
        for k, v in fm.items():
            parts.append(f"{k}: {v}")
        parts.append("---")
        parts.append("")
    parts.append(f"# {title}")
    parts.append("")
    parts.append(LOREM)
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: make_fixture.py <target-dir>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)
    (root / ".obsidian").mkdir(exist_ok=True)  # mark as an Obsidian vault

    # loose root-level notes
    note(root / "inbox-note.md", "Inbox Note")
    note(root / "scratch.md", "Scratch", {"tags": "[scratch]"})

    # FolderA: tagged notes, has _index.md
    (root / "FolderA" / "_index.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "FolderA" / "_index.md").write_text(
        "# Folder A\n\n> Notes about topic A — fully tagged.\n", encoding="utf-8")
    for i in range(8):
        note(root / "FolderA" / f"note-a{i}.md", f"Note A{i}",
             {"category": "alpha", "tags": f"[topic-a, item-{i}]", "date": "2026-01-01"})

    # FolderB: 20 untagged notes, NO _index.md (should raise the ⚠ flag)
    for i in range(20):
        note(root / "FolderB" / f"note-b{i}.md", f"Note B{i}")

    # Folder With Spaces & unicode: mixed tagging
    sp = root / "Folder With Spaces"
    for i in range(3):
        note(sp / f"nota-ünïcode-{i}.md", f"Nota {i}",
             {"keywords": "[mixed]"} if i % 2 == 0 else None)

    # ArchiveDump cases
    note(root / "Archive" / "old.md", "Old Stuff")

    # nested subfolder with deep index
    (root / "FolderA" / "Deep" ).mkdir(parents=True, exist_ok=True)
    (root / "FolderA" / "Deep" / "_index.md").write_text(
        "# Deep\n\n> Deep sub-area of A.\n", encoding="utf-8")
    note(root / "FolderA" / "Deep" / "deep-note.md", "Deep Note", {"category": "alpha"})

    # excluded noise that must NOT be counted
    note(root / "FolderB" / "node_modules" / "junk.md", "Junk")
    note(root / ".trash" / "deleted.md", "Deleted")

    print(f"Fixture vault created at {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
