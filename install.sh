#!/bin/bash
# vault-analyst guided installer (macOS)
#
# Sets up the vault-analyst Claude Code skill for your Obsidian vault:
#   1. asks where your vault is
#   2. measures how your notes are tagged (everything stays on your machine)
#   3. installs the skill into ~/.claude/skills/vault-analyst/
#   4. generates the vault router index
#   5. optionally installs a daily refresh cron
#
# Safe to re-run any time — re-running is also how you update after `git pull`.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.claude/skills/vault-analyst"
CONFIG="$INSTALL_DIR/config.json"
PY="${VAULT_ANALYST_PYTHON:-python3}"

say()  { printf '%s\n' "$*"; }
ask()  { local prompt="$1" default="$2" reply; read -r -p "$prompt${default:+ [$default]}: " reply; printf '%s' "${reply:-$default}"; }

# ---------- preflight ----------
if ! "$PY" -c 'import sys' >/dev/null 2>&1; then
  say "ERROR: python3 not found or not runnable. On macOS run:  xcode-select --install"
  exit 1
fi
if [ ! -d "$HOME/.claude" ]; then
  say "NOTE: ~/.claude not found — Claude Code may not be installed yet."
  say "      Installing anyway; the skill will be picked up once Claude Code runs."
fi

# ---------- vault path ----------
prev_vault="$("$PY" "$REPO_DIR/scripts/install_helpers.py" get "$CONFIG" vault_path 2>/dev/null || true)"
default_vault="$prev_vault"
if [ -z "$default_vault" ]; then
  for guess in \
    "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents"/* \
    "$HOME/Documents/Obsidian"/* \
    "$HOME/Obsidian"/*; do
    [ -d "$guess" ] && default_vault="$guess" && break
  done
fi

vault=""
while [ -z "$vault" ]; do
  candidate="$(ask "Path to your Obsidian vault" "$default_vault")"
  candidate="${candidate/#\~/$HOME}"
  if [ ! -d "$candidate" ]; then
    say "  That directory doesn't exist — try again (drag the vault folder into the terminal to paste its path)."
    continue
  fi
  if [ ! -d "$candidate/.obsidian" ]; then
    say "  WARNING: no .obsidian/ folder there — is this really a vault?"
    keep="$(ask "  Use it anyway? (y/N)" "n")"
    case "$keep" in y|Y) ;; *) continue ;; esac
  fi
  vault="$candidate"
done

# ---------- folder exclusions ----------
say ""
say "Top-level folders found in your vault:"
"$PY" "$REPO_DIR/scripts/install_helpers.py" top-folders "$CONFIG" "$vault" | sed 's/^/  - /' || true
prev_excludes="$("$PY" "$REPO_DIR/scripts/install_helpers.py" get "$CONFIG" exclude_folders 2>/dev/null || true)"
say ""
excludes="$(ask "Folders to EXCLUDE from analysis (comma-separated, empty for none)" "$prev_excludes")"

# ---------- overwrite guard ----------
if [ -f "$INSTALL_DIR/SKILL.md" ] && [ ! -f "$CONFIG" ]; then
  say ""
  say "WARNING: $INSTALL_DIR already contains skill files not installed by this script."
  cont="$(ask "Overwrite them? (y/N)" "n")"
  case "$cont" in y|Y) ;; *) say "Aborted — nothing changed."; exit 0 ;; esac
fi
if [ -f "$INSTALL_DIR/SKILL.md" ] && [ -f "$CONFIG" ]; then
  if modified="$("$PY" "$REPO_DIR/scripts/install_helpers.py" check-hashes "$CONFIG" "$INSTALL_DIR")"; then
    : # clean install or unmodified — safe to overwrite
  else
    say ""
    say "WARNING: you have manually edited the installed skill file: $modified"
    say "Re-installing will OVERWRITE your edits (copy them out first — e.g. the Quirks section of vault-profile.md)."
    cont="$(ask "Overwrite anyway? (y/N)" "n")"
    case "$cont" in y|Y) ;; *) say "Aborted — nothing changed."; exit 0 ;; esac
  fi
fi

# ---------- install ----------
say ""
say "Installing..."
mkdir -p "$INSTALL_DIR/scripts" "$INSTALL_DIR/references"

"$PY" "$REPO_DIR/scripts/install_helpers.py" write-config "$CONFIG" "$vault" "$excludes"

cp "$REPO_DIR/scripts/generate_vault_index.py" "$INSTALL_DIR/scripts/"
cp "$REPO_DIR/scripts/install_helpers.py"      "$INSTALL_DIR/scripts/"

profile_json="$(mktemp)"
"$PY" "$INSTALL_DIR/scripts/generate_vault_index.py" --config "$CONFIG" --profile > "$profile_json"

"$PY" "$REPO_DIR/scripts/render_templates.py" \
  --vault "$vault" \
  --generator "$INSTALL_DIR/scripts/generate_vault_index.py" \
  --profile "$profile_json" \
  --templates "$REPO_DIR/skill" \
  --out "$INSTALL_DIR"
rm -f "$profile_json"

"$PY" "$REPO_DIR/scripts/install_helpers.py" record-hashes "$CONFIG" "$INSTALL_DIR" \
  "SKILL.md" "references/retrieval-recipes.md" "references/vault-profile.md"

# ---------- first index ----------
say ""
"$PY" "$INSTALL_DIR/scripts/generate_vault_index.py" --config "$CONFIG"

# ---------- cron (optional) ----------
say ""
cron_installed=no
if command -v crontab >/dev/null 2>&1; then
  want_cron="$(ask "Install a daily 04:45 cron to keep the index fresh? (Y/n)" "y")"
  case "$want_cron" in
    n|N) say "  Skipped — the skill regenerates the index itself when it's older than 7 days." ;;
    *)
      cron_line="45 4 * * * /usr/bin/env python3 \"$INSTALL_DIR/scripts/generate_vault_index.py\" --config \"$CONFIG\" >> \"$INSTALL_DIR/cron.log\" 2>&1"
      existing="$(crontab -l 2>/dev/null || true)"
      backup="$INSTALL_DIR/crontab.backup.$(date +%Y%m%d%H%M%S)"
      if [ -n "$existing" ]; then printf '%s\n' "$existing" > "$backup"; else : > "$backup"; fi
      # filter out any previous vault-analyst entry; grep exits 1 when nothing survives, which is fine
      filtered="$(printf '%s\n' "$existing" | grep -vF "generate_vault_index.py" || true)"
      if { [ -n "$filtered" ] && printf '%s\n' "$filtered"; printf '%s\n' "$cron_line"; } | crontab -; then
        cron_installed=yes
        say "  Cron installed (backup of your previous crontab: $backup)"
      else
        say "  WARNING: failed to write crontab — restoring backup."
        if [ -s "$backup" ]; then
          crontab "$backup" || say "  Restore failed too; your previous crontab is saved at $backup"
        fi
      fi
      ;;
  esac
else
  say "NOTE: crontab not available on this system — skipping cron. The skill self-heals stale indexes."
fi

# ---------- summary ----------
say ""
say "=========================================================="
say "vault-analyst installed."
say ""
say "  Skill:      $INSTALL_DIR/SKILL.md"
say "  Profile:    $INSTALL_DIR/references/vault-profile.md  (your vault's measured shape)"
say "  Generator:  $INSTALL_DIR/scripts/generate_vault_index.py"
say "  Config:     $CONFIG  (vault path stored in plain text here)"
say "  Index:      $vault/_vault-index.md"
say "  Cron:       $cron_installed"
say ""
say "Try it: open Claude Code anywhere and ask"
say '  "what do I have in my vault about <topic>?"'
say ""
say "If your vault is under git (e.g. Obsidian Git plugin), consider adding"
say "  _vault-index.md"
say "to the vault's .gitignore — it reveals your folder structure if pushed."
say ""
say "Update later:  cd $(printf '%q' "$REPO_DIR") && git pull && ./install.sh"
say "Uninstall:     rm -rf \"$INSTALL_DIR\"; crontab -e  (remove the generate_vault_index.py line); delete _vault-index.md from the vault"
say "=========================================================="
