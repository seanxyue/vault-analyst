# vault-analyst

A Claude Code skill that lets Claude **analyze across your entire Obsidian vault** — review SOPs spread over many notes, compare documents, answer "what do I know about X" — without sending a single note to any external service.

It works in three layers:

1. **Router index** — a generated `_vault-index.md` at your vault root maps every folder with note counts, so Claude navigates instead of guessing.
2. **Analysis skill** — a `vault-analyst` skill teaches Claude to route through the index, filter by the frontmatter fields *your* vault actually uses, fan out parallel read-only subagents for big questions, and cite a vault path for every claim.
3. **Freshness automation** — an optional daily cron regenerates the index; without it, the skill regenerates whenever the index is older than 7 days.

The installer **measures your vault** (which frontmatter fields exist, how reliably, which folders are big) and generates a `vault-profile.md` so the skill adapts to how your notes are actually organized — fully tagged, completely untagged, or anywhere in between.

## Requirements

- macOS
- [Claude Code](https://claude.com/claude-code)
- Python 3.9+ (`python3 --version` — comes with Xcode Command Line Tools)
- An Obsidian vault (any size — designed and tested around ~2,500 notes)

## Install

```bash
git clone https://github.com/seanxyue/vault-analyst.git
cd vault-analyst
./install.sh
```

The guided setup asks:

| Question | Why |
|---|---|
| Where is your vault? | Everything is keyed off this path (stored locally in a config file) |
| Folders to exclude? | Skip folders that aren't knowledge (e.g. attachments dumps, code projects) |
| Install a daily cron? | Keeps the index fresh at 04:45; decline and the skill self-refreshes when stale |

Then ask Claude Code, from anywhere:

> "What do I have in my vault about project planning?"

## What lands where

| Repo file | Installed to |
|---|---|
| `skill/SKILL.md.template` (rendered) | `~/.claude/skills/vault-analyst/SKILL.md` |
| `skill/references/retrieval-recipes.md` | `~/.claude/skills/vault-analyst/references/` |
| `skill/references/vault-profile.md.template` (rendered from your vault's measurements) | `~/.claude/skills/vault-analyst/references/vault-profile.md` |
| `scripts/generate_vault_index.py` | `~/.claude/skills/vault-analyst/scripts/` |
| — | `~/.claude/skills/vault-analyst/config.json` (your vault path + choices) |
| — | `<your vault>/_vault-index.md` (the generated router index) |

Nothing else is touched. The cloned repo can be deleted after install if you don't want updates (everything needed at runtime is copied out).

## Updating

```bash
cd vault-analyst
git pull
./install.sh
```

Re-running is safe: your previous answers are offered as defaults, and if you've hand-edited any installed file (e.g. added quirks to `vault-profile.md`), the installer detects it and asks before overwriting.

## Uninstalling

```bash
rm -rf ~/.claude/skills/vault-analyst
crontab -e   # delete the line containing generate_vault_index.py, if you installed the cron
```

Then delete `_vault-index.md` from your vault root.

## FAQ

**Does this send my notes anywhere?**
No. Everything runs locally: the index generator is a stdlib-only Python script, and the skill is instructions for Claude Code, which reads your vault from disk in your own session. Note that anything Claude reads during a conversation is part of that conversation — same as opening any file with Claude Code.

**My vault is under git (Obsidian Git plugin) — anything to know?**
The generated `_vault-index.md` lists your folder structure and note counts. If you push your vault anywhere public or shared, consider adding `_vault-index.md` to the vault's `.gitignore`.

**I skipped the cron. Will the index go stale?**
The skill checks the index's age before using it and regenerates anything older than 7 days, so you'll never be more than a week stale — at the cost of a few seconds at the start of an analysis.

**The cron doesn't seem to run.**
On recent macOS, `cron` may need Full Disk Access to read vaults under `~/Documents` or iCloud (System Settings → Privacy & Security → Full Disk Access → add `cron`). Or just rely on the skill's self-refresh.

**My vault has no frontmatter/tags at all. Is this useless?**
No — the installer detects that and the generated profile tells the skill to skip frontmatter filtering and use body-text search plus whole-folder reads instead. The router index and fan-out still do their job.

**Something's off / I have an idea.**
Open an issue: https://github.com/seanxyue/vault-analyst/issues

## How it works (for the curious)

- `scripts/generate_vault_index.py` — walks the vault (skipping `.obsidian`, `node_modules`, etc.), counts notes per branch, pulls one-line descriptions from any `_index.md` files you keep, flags big unindexed folders, and writes a two-tier router under 200 lines. `--profile` mode emits per-folder frontmatter coverage as JSON.
- `scripts/render_templates.py` — substitutes your vault path and measurements into the skill templates. All rendering happens in Python, so paths with spaces, slashes, `&`, or unicode are safe.
- `install.sh` — the guided wrapper around the two scripts: prompts, overwrite protection (file hashes), null-safe crontab editing with automatic backup.
- `tests/make_fixture.py` — builds a procedurally-generated fixture vault for testing; no real vault data is in this repo.

## License

MIT
