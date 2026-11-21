# Open Questions — Cookidoo API

Migrated from thermomix-integration initiative 2026-06-07. Unresolved items to
track down as the client matures.

---

1. **Web vs mobile surface** — The web app at `cookidoo.international` is now
   well-mapped (see `endpoints.md`). The mobile backend
   (`ch.tmmobile.vorwerk-digital.com`) is what the old forks targeted — it may
   have lighter-weight JSON endpoints for some operations. Current bet: stick
   with the web surface (freshest, live auth flow). Revisit if we hit something
   the web surface handles awkwardly.

2. **Locale handling** — Thomas's market is `xp` (international export, default
   lang `en`). Stock recipe IDs use `r<digits>`, custom recipes use ULIDs.
   No `nb`/`no` in the language list for this market — `en` is what we use.
   Watch for multi-locale accounts when generalising.

3. **TM6 vs TM7 device tag** — not surfaced in any capture yet. Should appear
   in `/customer-devices/api/my-devices/versions`. Needed if we ever gate
   features on device generation.

4. **Rate limits** — observe rather than guess. Start conservative at 1 req/sec.
   Update here once we have data from real usage patterns.

5. **Algolia public key rotation cadence** — key appears in
   `__NEXT_DATA__.props.pageProps.algoliaApiKeyData.apiKey` on `/search/en`.
   Observed rotation: roughly weekly (`validUntil` epoch in the base64-decoded
   key). Refresh strategy: re-scrape from the page each session. Confirm exact
   cadence by observing across multiple rotations.

6. **Shopping list — per-item freeform add** — RESOLVED 2026-09-19.
   Endpoint: `POST shopping/{language}/additional-items/add` with body
   `{"itemsValue": ["item1", "item2", ...]}`. SDK exposes it as
   `cookidoo.add_additional_items(names: list[str])`. Wrapped as
   first-class MCP tool in commit `899ce7e`.

7. **Custom-recipe calendar DELETE** — RESOLVED 2026-11-21. The HTTP
   endpoint works: `DELETE planning/{lang}/api/my-day/{day}/recipes/{ulid}?recipeSource=CUSTOMER`
   returns 200 with body `{"message":"Recipe was removed","content":null,"code":null}`.
   Matrix (re-probed 2026-11-21 against a throwaway ULID on 2026-11-28):
   - `recipeSource=CUSTOMER` → 200, recipe removed.
   - omit param → 400, body `{"code":"E003","message":"Recipe has already been deleted for this day"}`.
   - `recipeSource=CUSTOM` → 500, generic "Something went wrong".
   The 2026-08-06 "CUSTOMER → 400" finding was stale (likely Cookidoo-side fix
   between then and now). The remaining failure mode was an SDK bug: the SDK's
   `remove_custom_recipe_from_calendar` parses `(await r.json())["content"]`
   but the body has `content: null`, raising `'NoneType' object is not
   subscriptable` even though the server-side delete succeeded. Fix: our MCP
   `remove_from_calendar` tool bypasses the SDK for custom-recipe IDs and
   hits the endpoint via `raw_request` (commit hash: see repo log after this
   doc update). Upstream SDK bug still present in miaucl's cookidoo-api
   new-auth branch — worth filing.

8. **Bookmarks endpoint discovery** — meal-planning (window 0:12) asked
   2026-10-16 for a programmatic way to list "bookmarked" recipes
   (distinct from the 17 custom lists at `organize/{language}/api/custom-list`).
   A page-route template `/organize/{lang}/transclude/manage-bookmark/{recipeId}`
   exists in `actionLinkTemplates` (service `tmde2:organize`), which strongly
   implies a distinct bookmark concept, but the underlying JSON endpoint is
   unmapped. Prior failed probes (from `endpoints.md` §7): `GET
   community/en/api/favourites` (auth error), `GET favourites/en` (404),
   `POST community/en/api/recipes/{id}/bookmark` (405), `GET
   community/en/bookmarks` (404). Next probe matrix (needs live MCP auth):
   `organize/en/api/bookmark[s]`, `organize/en/api/manage-bookmark`,
   `organize/en/api/bookmarked-recipes`, each with Accept
   `application/vnd.vorwerk.organize.<name>.mobile+json`; also fetch the
   transclude HTML at `organize/en/transclude/manage-bookmark/r292456` and
   inspect for the real POST URL. If all JSON probes fail, browser-drive HAR
   capture of a heart-icon click is the fallback (planned step in
   `endpoints.md:273-293`). Once mapped, expose `list_bookmarks()`,
   `bookmark_recipe()`, `unbookmark_recipe()` MCP tools.
