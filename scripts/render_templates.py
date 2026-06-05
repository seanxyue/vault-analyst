#!/usr/bin/env python3
"""Render the vault-analyst skill templates with install-time values.

Called by install.sh. Does ALL placeholder substitution in Python so the
installer never passes user input through sed — paths with slashes, spaces,
ampersands, or unicode are safe.

Usage:
  render_templates.py --vault <vault-path> --generator <installed-generator-path>
                      --profile <profile.json> --templates <skill-template-dir>
                      --out <output-dir>

Writes to <output-dir>: SKILL.md, references/retrieval-recipes.md,
references/vault-profile.md. Exits nonzero if any {{TOKEN}} survives rendering.
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def render(text: str, mapping: dict) -> str:
    for key, value in mapping.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


def check_no_orphans(text: str, name: str):
    orphans = re.findall(r"\{\{[^}]+\}\}", text)
    if orphans:
        print(f"ERROR: unrendered tokens in {name}: {', '.join(sorted(set(orphans)))}", file=sys.stderr)
        sys.exit(1)


def profile_table(profile: dict) -> str:
    total = max(profile["total"] - profile.get("root_notes", 0), 1)
    fields = profile["overall"]["fields"]
    if not fields:
        return "_No frontmatter fields found — this vault is untagged. Use body-text search and whole-slice reads._"
    rows = ["| Field | Notes carrying it | Coverage |", "|---|---|---|"]
    for name, count in sorted(fields.items(), key=lambda kv: -kv[1])[:10]:
        rows.append(f"| `{name}:` | {count} | {round(100 * count / total)}% |")
    return "\n".join(rows)


def strategy_note(profile: dict) -> str:
    total = max(profile["total"] - profile.get("root_notes", 0), 1)
    untagged_pct = round(100 * profile["overall"]["untagged"] / total)
    fields = profile["overall"]["fields"]
    best = max((100 * c / total for c in fields.values()), default=0)
    if best >= 50:
        best_fields = [n for n, c in fields.items() if 100 * c / total >= 50]
        return (f"good coverage on {', '.join('`' + f + ':`' for f in sorted(best_fields))} — "
                "lead with frontmatter greps on those fields, fall back to body text for the untagged share.")
    if untagged_pct >= 60 or not fields:
        return ("this vault is mostly untagged — frontmatter filtering will miss most notes. "
                "Lead with body-text search and whole-slice subagent reads; treat any frontmatter hit as a bonus.")
    return ("moderate tagging — use frontmatter greps as a first pass but ALWAYS pair with a "
            "body-text pass; the untagged share is too large to ignore.")


def slice_table(profile: dict) -> str:
    rows = ["| Branch | Notes | Strategy |", "|---|---|---|"]
    folders = sorted(profile["by_folder"].items(), key=lambda kv: -kv[1]["total"])
    for name, data in folders:
        n = data["total"]
        if n == 0:
            continue
        if n > 150:
            strat = "split by subfolder, fan out 3–5 subagents"
        elif n >= 30:
            strat = "one subagent reads the whole slice"
        else:
            strat = "read directly"
        rows.append(f"| {name} | {n} | {strat} |")
    return "\n".join(rows)


def low_priority_list(profile: dict) -> str:
    present = [n for n in profile.get("low_priority", []) if n in profile.get("top_folders", [])]
    generic = profile.get("low_priority", [])
    if present:
        return "\n".join(f"- `{n}/`" for n in present) + \
            "\n\n(Plus any deeper folder named: " + ", ".join(f"`{n}`" for n in generic) + ")"
    return "(none at top level; any deeper folder named " + ", ".join(f"`{n}`" for n in generic) + " is deprioritized)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--generator", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--templates", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    templates = Path(args.templates)
    out = Path(args.out)
    (out / "references").mkdir(parents=True, exist_ok=True)
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8-sig"))

    skill_map = {
        "VAULT_PATH": args.vault,
        "GENERATOR_PATH": args.generator,
        "TOP_FOLDERS": ", ".join(profile.get("top_folders", [])) or "(none — flat vault)",
    }
    profile_map = {
        "GENERATED_DATE": datetime.now().astimezone().strftime("%Y-%m-%d"),
        "VAULT_PATH": args.vault,
        "TOTAL_NOTES": profile["total"],
        "ROOT_NOTES": profile.get("root_notes", 0),
        "UNTAGGED_PCT": round(100 * profile["overall"]["untagged"]
                              / max(profile["total"] - profile.get("root_notes", 0), 1)),
        "PROFILE_TABLE": profile_table(profile),
        "STRATEGY_NOTE": strategy_note(profile),
        "SLICE_TABLE": slice_table(profile),
        "LOW_PRIORITY_LIST": low_priority_list(profile),
    }

    skill = render((templates / "SKILL.md.template").read_text(encoding="utf-8"), skill_map)
    check_no_orphans(skill, "SKILL.md")
    (out / "SKILL.md").write_text(skill, encoding="utf-8")

    vp = render((templates / "references" / "vault-profile.md.template").read_text(encoding="utf-8"), profile_map)
    check_no_orphans(vp, "vault-profile.md")
    (out / "references" / "vault-profile.md").write_text(vp, encoding="utf-8")

    shutil.copyfile(templates / "references" / "retrieval-recipes.md",
                    out / "references" / "retrieval-recipes.md")

    print(f"Rendered skill files to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
