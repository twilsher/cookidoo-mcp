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

6. **Shopping list — per-item freeform add** — RESOLVED 2026-08-11.
   Endpoint: `POST shopping/{language}/additional-items/add` with body
   `{"itemsValue": ["item1", "item2", ...]}`. SDK exposes it as
   `cookidoo.add_additional_items(names: list[str])`. Confirmed working
   via `cookidoo_http_request` (used to add "makrut lime leaves").
   TODO: expose as first-class MCP tool `add_additional_shopping_items(items)`.
