# Cookidoo API — patterns & gotchas

Quick-reference for non-obvious behavior of the Cookidoo HTTP surface, written
for the next session that needs to add a tool. Companion to `endpoints.md`
(which is the full inventory) — this file is the "what would have saved you
two hours" notes.

---

## 1. Create custom recipe → two-step POST+PATCH

Single POST with a full body returns **400 Bad Request**. The endpoint
strictly accepts a name-only create, then a PATCH for the rest.

```
POST   created-recipes/{lang}                     {"recipeName": "..."}
       → 200, returns the new ULID
PATCH  created-recipes/{lang}/{ULID}              <full body>
       → 200, returns the populated recipe
```

Required PATCH body fields (omit one and you get 400):
- `name`, `image` (nullable), `isImageOwnedByUser`, `tools` (`[]` is fine)
- `yield: {value, unitText}` — `unitText: "portion"` is what the UI emits
- `prepTime`, `cookTime`, `totalTime` — **in seconds**, not minutes
- `ingredients: [{"type": "INGREDIENT", "text": "..."}]`
- `instructions: [{"type": "STEP", "text": "..."}]`
- `hints: ""` (single string; `"\n"`-join multiple)
- `workStatus: "PRIVATE"`
- `recipeMetadata: {"requiresAnnotationsCheck": false}`

The PATCH echoes back the recipe with extra fields (`annotations`,
`missedUsages`, `descriptiveAssets`) populated by the server — those are
read-only.

Reference implementation: `alexandrepa-mcp-cookidoo/cookidoo_service.py`
`create_custom_recipe` method (only fork with a working from-scratch path).
Our `cookidoo-api` pin (miaucl new-auth branch) has `add_custom_recipe_from`
which copies from an existing recipe URL — that's NOT what you want for fresh
creation.

First confirmed-working call: `01KTECKZHEN6EE20HF7WH8E9RC` (Pan-Seared Cod),
2026-06-06.

---

## 2. Calendar mutation responses are misleading — mitigated at the tool layer

Two specific cases where the underlying `cookidoo-api` library responses don't
reflect the side effect:

- `add_custom_recipes_to_calendar(date, [ulid])` returns a day object with
  `recipes: []`. The recipe IS scheduled — the library's `CookidooCalendarDay`
  dataclass simply doesn't surface `customerRecipeIds`.
- `remove_*_from_calendar(date, recipe_id)` response body can still show the
  removed recipe in the day's block.

**Mitigation (server-side, since 2026-06-08):** `add_to_calendar` and
`remove_from_calendar` MCP tools no longer return the raw write-call response.
They internally call `_read_back_day(target)` after the mutation — which uses
the same merged `get_recipes_in_calendar_week` + `_fetch_custom_recipe_ids_for_week`
path as `get_calendar_week` — and return an envelope:

```json
{
  "success": true,
  "action": "added" | "removed",
  "recipe_ids": [...] | "recipe_id": "...",
  "date": "YYYY-MM-DD",
  "missing_after_readback": [...]      // for add
  "still_present_after_readback": bool // for remove
  "day": { ...actual post-call day state... }
}
```

Consumers can trust `success` at face value; the `day` field is the verified
post-call state, not the misleading library response.

If you're writing a NEW calendar mutation tool, route the read-back through
`_read_back_day(target)` rather than returning the library response directly.
The library response will lie to you.

---

## 3. Auth is a one-shot interactive bootstrap — scripts can't re-login fresh

The browser OAuth2 flow (miaucl/new-auth) requires an interactive browser
session for the initial login. Once cookies are in the session jar, subsequent
calls work fine; but spinning up a fresh Python script and calling
`api.login()` fails with:

```
CookidooAuthException: Login failed: authentication cookies were not set.
```

This means:

1. **Don't write standalone scripts that authenticate from scratch.** Always
   route HTTP calls through the running MCP server's session (either via
   `cookidoo_http_request` or by adding a proper tool to `server.py`).
2. The 401 auto-retry in `client.py` (commit `da9067f`) works because it
   re-uses whatever cookie path the original login took — but if the
   underlying browser session has fully expired (not just the session cookie
   refresh), `/mcp reconnect cookidoo` is still needed to redo the bootstrap.
3. M2 of the rewrite should treat OAuth2 login as a **one-shot interactive
   bootstrap** with a persisted cookie jar, not as a "fresh on every call"
   flow. The forks that assumed the latter all broke when Cookidoo deprecated
   `grant_type=password`.

---

## 4. Search needs the public web host, not the mobile API host

- `xp.tmmobile.vorwerk-digital.com/search/{lang}` — global unfiltered pool;
  returns cross-language noise and empty results for many queries.
- `cookidoo.international/search/{lang}` — locale-filtered, matches the web
  UI. **Use this.**
- Pagination is **0-indexed**. `page=0` is real first page; `page=1` is a
  fallback "popular" pool from a different locale.
- `pageSize` is **ignored** — always 20 results. Trim client-side.

Per `endpoints.md`, there's also an Algolia surface
(`3ta8nt85xj-dsn.algolia.net`) used by the SPA directly. We haven't migrated
to it yet; the locale-filtered `/search/{lang}` HTTP endpoint is sufficient
for our current tools.

---

## 5. Where to put the recipe content — per-step ingredient embedding

Cookidoo's custom-recipe schema is flat: ingredients and instructions are two
independent arrays. There's no per-step ingredient linking field.

For Thomas's preferred display style ("per-step weights in the leading text,
much preferred over consolidated header"), embed the relevant ingredient+
quantity into each step's text:

```
"Stek halloumi — 400 g halloumi, 2 ss olivenolje: Skjær halloumien i ..."
```

Still populate `ingredients[]` with the full canonical list — that's what
`add_to_shopping_list` reads from. The per-step text is purely for the cooking
view. See `~/.claude/skills/cookidoo-custom-recipe/SKILL.md` for the full
convention.

---

## 6. Recipe ID shapes determine which tool to call

| Shape | Example | Class |
|-------|---------|-------|
| `r\d+` | `r150903` | Stock catalog recipe |
| 26-char ULID, starts `01K` | `01KTECKZHEN6EE20HF7WH8E9RC` | Custom (user-created) |

`_is_custom_recipe_id(rid)` in `server.py` dispatches based on the `r\d+`
regex. Any new endpoint that accepts a recipe ID should use this helper rather
than guessing.

---

## Adding a new tool — flow

When meal-planning asks for a tool we don't have:

1. Check if `cookidoo-api` (current pin, `miaucl new-auth @ ad9fb13`) already
   has the method — `grep "def " .venv/.../cookidoo_api/cookidoo.py`. If yes,
   wrap it in `server.py` using `_client.call(lambda api: ...)` for the
   401-retry behavior.
2. If not, check the Mariosd23 or alexandrepa forks for an implementation we
   can crib (both at `~/dev/{thermomix-mcp,alexandrepa-mcp-cookidoo}/`).
3. If still nothing, use `cookidoo_http_request` with the raw endpoint. Once
   confirmed working, fold the call into a proper named tool in `server.py`
   rather than leaving meal-planning to compose raw requests. Update
   `endpoints.md` and this file with what you learned.

What NOT to do: write a one-off scratch script that bypasses the MCP server.
Auth doesn't survive that, and the discovery doesn't get captured for the
next session.
