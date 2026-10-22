# Handoff — cookidoo-mcp — 2026-10-22

## Current state

Repo tree clean, `main` at `f302479` (certifi 2026.10.19 bump).
Fork `origin` (`twilsher/cookidoo-mcp`) 23 commits ahead of
`upstream/main`. No pending code changes in this session.

## Current goal

Two durable open items — both read-only diagnostics, both blocked on a
fresh MCP session (see risks below).

1. **Probe custom-recipe calendar DELETE 400 body**
   (`docs/open-questions.md#7`). The upgraded `cookidoo_http_request`
   (commit `0858dc6`) now surfaces non-2xx bodies; the actual 400 payload
   has still not been captured. Pick a current custom-recipe ULID off
   `cookidoo_get_my_week`, then run the probe (see resume commands).
2. **Map bookmarks endpoint** (`docs/open-questions.md#8`, added this
   session). Meal-planning window 0:12 asked 2026-10-16 for a way to
   list "bookmarked" recipes separate from the 17 custom lists. Static
   research is done (`endpoints.md` already had a `manageBookmark`
   transclude template at `tmde2:organize`); the live JSON probe matrix
   is listed in `open-questions.md#8` and in the resume commands below.

## Risks

- **Stale MCP auth in this window.** The registered MCP server
  authenticated before the 2026-09-22 `.env` password-backslash fix
  (handoff 2026-09-28), and `cookidoo_get_my_week` currently returns
  "Authentication failed". A `/mcp` reload (or a fresh Claude Code
  session) is required before any Cookidoo tool call will work. The
  standalone login smoke-test in resume commands verifies the fix is
  still good at the SDK level.
- **MCP server caches code too.** After edits to `src/`, other windows
  still serve the old code until each `/mcp` reloads.
- **No secrets in this handoff.** Credentials live in `.env` (chmod 600,
  gitignored); never paste the password here or in commits.

## Commands to resume

```bash
# 1. Verify tree + recent commits
cd ~/dev/cookidoo-mcp && git status && git log --oneline -5

# 2. Standalone login smoke test (bypasses MCP, picks up latest .env;
#    confirms the .env password fix still holds)
uv run python -c "
import asyncio
from dotenv import load_dotenv; load_dotenv(override=True)
from cookidoo_mcp.client import CookidooClient
async def m():
    c = CookidooClient.get()
    try: await c.api(); print('login OK')
    finally: await c.close()
asyncio.run(m())
"

# 3. BEFORE running any mcp__cookidoo__* tool call: /mcp reload or
#    start a fresh Claude Code session in this project. Otherwise all
#    calls will fail with 'Authentication failed due to request exception'.
```

### Probe 1 — custom-recipe DELETE 400 body

```python
# Find a live custom-recipe (ULID) on the calendar first
mcp__cookidoo__cookidoo_get_my_week(weeks=4)
# Then (replace <YYYY-MM-DD> and <ULID> with real values):
mcp__cookidoo__cookidoo_http_request(
    method="DELETE",
    path="planning/en/api/my-day/<YYYY-MM-DD>/recipes/<ULID>",
    query={"recipeSource": "CUSTOMER"},
    confirmed=True,
)
# Capture body. If still 400, try omitting query entirely; if 500,
# compare with recipeSource=CUSTOM / customer (both 500 historically).
```

### Probe 2 — bookmarks endpoint matrix

```python
# Try the organize-service JSON namespace first (strongest lead — the
# custom-list endpoint lives at organize/en/api/custom-list).
for path in [
    "organize/en/api/bookmark",
    "organize/en/api/bookmarks",
    "organize/en/api/manage-bookmark",
    "organize/en/api/bookmarked-recipes",
]:
    mcp__cookidoo__cookidoo_http_request(
        method="GET", path=path,
        headers={"Accept": "application/vnd.vorwerk.organize.bookmark.mobile+json"},
    )

# If all 404/405, fetch the transclude HTML directly — it may embed
# the real POST URL as a form action or data attribute:
mcp__cookidoo__cookidoo_http_request(
    method="GET",
    path="organize/en/transclude/manage-bookmark/r292456",
    headers={"Accept": "text/html"},
)

# Last resort: browser-drive HAR capture of a heart-icon click on
# https://cookidoo.international/recipes/recipe/en/r292456 — see
# docs/endpoints.md:273-293 for the planned capture pass.
```

## Modelling assumptions

- Bookmarks are distinct from custom-lists. Based solely on the
  separate `manageBookmark` vs `manageCustomList` page templates. Not
  yet confirmed empirically. If probing shows they share storage,
  update `open-questions.md#8` and the planned `list_bookmarks()` tool
  reduces to a thin alias over `custom-list`.
- `tmde2:organize` service namespace maps to `organize/{lang}/api/...`
  paths. Confirmed for `custom-list`; assumed to hold for `bookmark`.

## Open decisions

None blocking. Both probes are safe read / probe-only; no mutations
required until write MCP tools are specced.
