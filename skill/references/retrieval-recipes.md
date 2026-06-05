# Retrieval Recipes — vault-analyst reference

Generic search patterns. Which frontmatter fields exist in this vault — and their measured coverage — is in `vault-profile.md`; read that first and substitute real field names into the patterns below.

## Grep recipes

Use `files_with_matches` mode first (get the candidate set), then content search within the narrowed set.

```text
# By frontmatter field (substitute a high-coverage field from vault-profile.md):
pattern: "^tags:.*project-x"
pattern: "^category: (alpha|beta)"

# By date range (if a date field exists):
pattern: "^date: 2026-0[1-3]"

# Candidate set by field, then body text within those files only:
1) files_with_matches: "^tags:.*topic"
2) content search within the matched files

# Wikilink backlinks to a note (who references X):
pattern: "\[\[.*Note Title.*\]\]"

# Body-text fallback (when frontmatter coverage is low):
2-3 phrasing variants before concluding absence — vocabulary drifts
("meme-coin" vs "memecoin", "set up" vs "setup").
```

Caveats:
- Frontmatter search only finds tagged notes. Untagged notes are invisible to it — vault-profile.md reports the untagged share per folder. When completeness matters, pair field search with a body-text pass or whole-slice reads.
- If a search returns suspiciously few hits, try variants before concluding the vault has nothing — phrasing drift is the most common cause of false absence.

## Fan-out prompt template

```
You are a read-only research subagent. Question: <QUESTION>

Your slice (read ONLY within): <vault>/<branch>/ — roughly <N> notes.
Identify relevant notes (frontmatter fields if coverage is high — see note below — else body-text search), then read them.
If the slice is under ~150 notes, read all of it.

Return (raw data, no prose intro):
- ≤25 bullets, each: finding + exact vault-relative path
- Contradictions between notes: flag explicitly with both paths
- Gaps: what the question needs that this slice does NOT contain (1-3 bullets)
- Do NOT dump note contents — extract.
```

Spawn 3–5 in parallel. Synthesize only after all return; keep each subagent's citations in the merged output.

## Escalation path (when retrieval misses)

1. Re-route: re-read `_vault-index.md` — was a branch skipped?
2. Body-text search across the full vault (expensive, last lexical resort).
3. If conceptual queries keep missing (no shared vocabulary between question and notes), consider adding a search backend: [nightisyang/obsidian-cli](https://github.com/nightisyang/obsidian-cli) (headless lexical + wikilink graph) or [tobi/qmd](https://github.com/tobi/qmd) (BM25 + optional semantic search).
