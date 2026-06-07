# Cookidoo Endpoint Inventory — M1

Captured 2026-05-22 from a scripted Playwright walk of the logged-in web app at
`cookidoo.international`. Source HAR: `captures/cookidoo-2026-05-22.har`
(gitignored, contains auth cookies). Parser scripts in `scripts/`.

**Status:** First pass. Page-route templates are comprehensive (extracted
verbatim from the SPA's `__NEXT_DATA__.props.pageProps.actionLinkTemplates`).
The underlying JSON XHR endpoints behind protected pages still need a second
capture pass — see "Gaps" at the bottom.

---

## Architecture Overview

1. **Single origin.** All app routes resolve under `cookidoo.international`.
   Microservices are routed by path prefix (`/planning`, `/organize`,
   `/pantry`, `/foundation`, `/profile`, `/commerce`, `/community/profile`,
   `/customer-devices`, `/created-recipes`, `/collection`, `/recipes`,
   `/shopping`).
2. **Internal service naming**: `tmde2:<service>` (e.g. `tmde2:planning`,
   `tmde2:pantry`). The `tmde2` prefix is the Thermomix Digital Ecosystem
   namespace.
3. **Transclude/partial pattern**: many service actions are exposed as
   server-rendered HTML fragments at
   `/<service>/{lang}/transclude/<action>/<resource>` (or `.../partial/...`).
   The SPA stitches these into the page rather than fetching JSON. This is
   important — naive REST assumptions don't apply everywhere.
4. **Recipe content host**:
   `recipepublic-all.prod.external.eu-tm-prod.vorwerk-digital.com` —
   served stock recipe assets (CSS/JS for the recipe-details widget). Recipe
   *data* itself appears inlined in the page HTML as JSON-LD plus
   server-side templating; not a separate JSON endpoint based on this capture.
5. **Asset CDN**: `assets.tmecosys.com` (images, AVIF/WebP/JPEG).
6. **UI pattern library / static assets**:
   `patternlib-all.prod.external.eu-tm-prod.vorwerk-digital.com` (woff2 fonts,
   CSS, SVG, JS bundles).
7. **Auth (CIAM)**: `eu.login.vorwerk.com/ciam/login` and
   `ciam.prod.cookidoo.vorwerk-digital.com`. OAuth2 entry on the app side is
   `cookidoo.international/oauth2/start`. Login is enforced by 302 redirects
   to the CIAM host.
8. **Search = Algolia**. App ID `3TA8NT85XJ`, env `production`. Public API key
   is exposed in SSR (rotated weekly — current expires `1780055092` = 2026-05-29
   13:04 UTC). Indices and decoded filter scope captured below.

---

## Hosts observed in HAR

| Host | Role | Observed traffic |
|---|---|---|
| `cookidoo.international` | App frontend + transclude services | HTML pages, `oauth2/start` redirect, search SSR |
| `recipepublic-all.prod.external.eu-tm-prod.vorwerk-digital.com` | Recipe widget assets | CSS, JS |
| `patternlib-all.prod.external.eu-tm-prod.vorwerk-digital.com` | UI pattern library | woff2, CSS, JS, SVG |
| `assets.tmecosys.com` | Image CDN | AVIF/WebP/JPEG |
| `ciam.prod.cookidoo.vorwerk-digital.com` | CIAM internal endpoint | `x-unknown` (one hit during auth check) |
| `eu.login.vorwerk.com` | CIAM login UI | HTML + CSS + JS (when redirected) |
| `3ta8nt85xj-dsn.algolia.net` | Algolia search backend | JSON search query |
| `cdn.cookielaw.org`, `geolocation.onetrust.com` | OneTrust cookie consent | telemetry — ignore |

---

## Page-route templates (extracted from `actionLinkTemplates`)

Source: `next-data/search__en.json` →
`props.pageProps.actionLinkTemplates`. These are RFC 6570 URI Templates
(braces denote variables, `{?foo}` denotes a query string parameter).

| Action | Template | Service | Action name |
|---|---|---|---|
| `manageCookToday` | `/planning/{lang}/transclude/manage-cook-today/{recipeId}{?recipeSource}` | `tmde2:planning` | `fint:transclude-manage-cook-today` |
| `manageBookmark` | `/organize/{lang}/transclude/manage-bookmark/{recipeId}` | `tmde2:organize` | `fint:transclude-manage-bookmark` |
| `manageCustomList` | `/organize/{lang}/transclude/manage-custom-list/{recipeId}` | `tmde2:organize` | `fint:transclude-manage-custom-list` |
| `addToMyWeek` | `/planning/{lang}/transclude/manage-add-to-myweek/{recipeId}{?recipeSource}` | `tmde2:planning` | `fint:transclude-manage-add-to-my-week` |
| `addToShoppingList` | `/shopping/{lang}/partial/add-to-shopping-list/{recipeID}{?source}` | `tmde2:pantry` | `fint:add-to-shopping-list` |
| `addToCustomerRecipes` | `/created-recipes/{lang}/partials/add-to-customer-recipes{?recipeUrl}` | `tmde2:customer-recipes` | `fint:add-to-customer-recipes` |
| `recipeDetails` | `/recipes/recipe{/lang}/{id}` | `tmde2:recipe-details` | `fint:details` |
| `collectionDetails` | `/collection/{lang}/p/{code}` | `tmde2:collections` | `fint:collection-details` |
| `login` | `/profile/{lang}/login{?redirectAfterLogin}` | `tmde2:profile` | `fint:login` |
| `register` | `/ciam/register/start` | `tmde2:profile` | `fint:register-page` |
| `userCommunityProfile` | `/community/profile/{lang}` | `tmde2:community-profile` | `fint:user-private-profile` |
| `savedSearches` | `/community/profile/{lang}/saved-searches` | `tmde2:community-profile` | `fint:saved-searches` |
| `exploreWeb` | `/foundation/{lang}/explore` | `tmde2:foundation` | `fint:explore-web` |
| `forYouWeb` | `/foundation/{lang}/for-you` | `tmde2:foundation` | `fint:for-you-web` |
| `myRecipes` | `/organize/{lang}/my-recipes` | `tmde2:organize` | `fint:web-my-recipes` |
| `myWeek` | `/planning/{lang}/my-week{?backButtonLoadsPreviousWidget}` | `tmde2:planning` | `fint:web-my-week` |
| `accountOverview` | `/commerce/{lang}/membership{?paymentUpdated}` | `tmde2:profile` | `fint:account-overview` |
| `help` | `/foundation/{lang}/help` | `tmde2:foundation` | `fint:help` |
| `membership` | `/foundation/{lang}/membership` | `tmde2:foundation` | `fint:membership` |
| `shoppingList` | `/shopping/{lang}{?excludeComponent}` | `tmde2:pantry` | `fint:home` |
| `myAdvisor` | `/foundation/{lang}/my-advisor` | `tmde2:foundation` | `fint:my-advisor` |
| `customerDevices` | `/customer-devices/{lang}/my-devices` | `tmde2:customer-devices` | `fint:my-devices-page-cd2` |
| `customerAccessories` | `/customer-devices/{lang}/my-accessories` | `tmde2:customer-devices` | `fint:my-accessories-page-cd2` |
| `customerDevicesVersions` | `/customer-devices/api/my-devices/versions` | `tmde2:customer-devices` | `fint:thermomix-versions` |
| `footer` | `http://web-foundation-service.production-eu.svc.cluster.local:8030/foundation/{lang}/partials/footer{?page}` | `tmde2:foundation` | `fint:footer` |

### Notes on the templates

1. **`{lang}` is the user-facing language code** — observed values from this account: `en`. Per `marketCode` config it ranges over the locales the market supports.
2. **`{recipeId}` accepts both `r123534`-style stock IDs and `01K...`-style ULIDs** — confirming the two recipe-ID flavours the fork code was guessing at. Custom recipes (user-created on Cookidoo) use ULIDs.
3. **`customerDevicesVersions`** is a real backend `/api/` route (`/customer-devices/api/my-devices/versions`) — only one in the list. Most others are HTML-fragment endpoints.
4. **`footer` template leaks an internal k8s service DNS** (`web-foundation-service.production-eu.svc.cluster.local:8030`). Cluster-internal, not externally callable, but confirms the platform is k8s and gives us a service-name → public-path mapping convention.

---

## Auth (CIAM)

1. SPA entrypoint: `https://cookidoo.international/oauth2/start` — issues 302 chain into CIAM.
2. CIAM login UI: `https://eu.login.vorwerk.com/ciam/login?view_type=login&market=xp&ui_locales=en&requestId=<uuid>`
3. Other CIAM host observed (one hit): `ciam.prod.cookidoo.vorwerk-digital.com` — response mime `x-unknown`, likely an internal authz call (not exhaustively captured in this run; revisit).
4. **localStorage is NOT used for auth** — dumped 0 keys from a logged-in persistent profile. Auth state is entirely cookie-based.
5. The `storageState({path})` JSON dump from a logged-in persistent profile is **insufficient by itself** to authenticate a fresh Playwright context — protected pages (e.g. `/shopping/list`, `/my-week` after Next reroute) redirect to CIAM login. Either an httpOnly cookie isn't being captured, or there's a session-fingerprint check (User-Agent, IP, Sec-CH-UA) that breaks across contexts. To be investigated in M2.
6. PR #203 in upstream `cookidoo-api` is the reference for the new browser-OAuth2 flow (per `CLAUDE.md`).

### CIAM URL fragments observed

- `view_type=login`
- `market=xp` (market code "xp" — international/export market, per `marketCode` config)
- `ui_locales=en`
- `requestId=<uuid>` — CIAM-side flow identifier

### Market config for Thomas's account

```
name:              international
marketCode:        xp
operator:          VI (Export)
mainDomain:        cookidoo.international
awsRegion:         EU
userBucket:        Switzerland
mainCurrency:      USD
defaultUILanguage: en
```

This is the "international export" market, not a national one (NO/DE/etc.). Locale handling needs to default to `en` for this account.

---

## Search — Algolia

1. **App ID**: `3TA8NT85XJ`
2. **Environment**: `production`
3. **DSN host**: `3ta8nt85xj-dsn.algolia.net`
4. **Public API key** (rotates ~weekly, current `validUntil` = 1780055092 = 2026-05-29 13:04 UTC):
   - The base64 key embeds the following constraints (decoded):
     - `attributesToRetrieve`: `id,title,image,rating,numberOfRatings,totalTime,category,publishedAt,description,url`
     - `filters`: `allowedRoles:public OR recipes-production.facets.exact_matches.allowedRoles.value:public`
     - `restrictIndices`: limited to the indices listed below
5. **Important**: the public key filters to `allowedRoles:public` — it returns ONLY public stock recipes. Custom user recipes (`01K...` ULIDs) won't be searchable through this key. They're accessed by direct ID via `/organize/...` or `/created-recipes/...`.
6. The key sits in `__NEXT_DATA__.props.pageProps.algoliaApiKeyData.apiKey` on `/search/en`. Refresh strategy for our client: re-scrape this from the page each session (or each rotation).

### Indices

```
recipes:
  relevance_empty: recipes-production-by-emptySearchScore
  relevance:       recipes-production
  publishedAt:     recipes-production-by-publishedAt-desc
  title:           recipes-production-by-title-asc
  rating:          recipes-production-by-rating-desc
  totalTime:       recipes-production-by-totalTime-asc
  preparationTime: recipes-production-by-preparationTime-asc
collections:
  relevance:       collections-production
  publishedAt:     collections-production-by-publishedAt-desc
  title:           collections-production-by-title-asc
category-suggestions: category-suggestions-production
suggestions-recipes:  suggestions-recipes-production
editorial:
  default: editorial-production
  title:   editorial-production-by-title-asc
```

---

## Recipe data shape (from inline JSON-LD)

Stock recipe page (`/recipes/recipe/en/r123534`, "Lentil Moussaka") embeds a
`<script type="application/ld+json">` block following **schema.org/Recipe**
spec. This is a stable, well-documented data shape (not vendor-custom):

```
@context, @type, name, image, ...
recipeIngredient: [string]
recipeInstructions: [{"@type":"HowToStep", text, ...}]
nutrition: {...}, totalTime, prepTime, recipeYield, ...
```

Implication: for stock recipes, **we may not need a dedicated JSON API at all
in the read path** — fetching the page HTML and extracting the JSON-LD blob
gives us schema-validated recipe data for free. The forks' bespoke recipe DTOs
become redundant. (Custom recipes — `01K...` — likely follow the same pattern
but need confirmation; their full HTML wasn't captured in this run because the
fresh context was unauthenticated for that page.)

Custom recipe ULIDs observed in My Week / scheduled: `01KS7SC3BNGA3FTF0ZNDZNZQR9` (Halloumi pita, Wed 5/27).

---

## Mobile-app deep link scheme

`com.vorwerk.cookidoo://` — for app-handoff deep links. Not relevant to a
Python client but worth knowing if we ever expose share/handoff.

---

## Gaps (require a second capture pass)

This first capture used a **fresh ephemeral context** that proved
under-authenticated for protected pages — `/shopping/list`, `/my-week` (deep
data), and the custom-recipe `/edit` view all redirected to CIAM login or
returned 8KB error/login shells. As a result the inventory is currently strong
on:

1. App architecture and routing
2. Auth flow surface (entry points, not the token exchange itself)
3. Search backend (Algolia, complete)
4. Stock recipe data shape (JSON-LD, complete)

…and weak on the actual JSON XHR endpoints that the SPA hits behind the
transclude/partial paths once a user is logged in. Specifically still unknown:

1. **My Week**: the GET endpoint that returns the week's scheduled recipes
   (assignments per day, slot, recipe ID, custom flag).
2. **My Week add/remove**: POST/DELETE shape for the
   `/planning/{lang}/transclude/manage-add-to-myweek/{recipeId}` endpoint.
3. **Shopping list**: GET (`/shopping/{lang}`), and the add/remove/clear write endpoints.
4. **Custom recipe full data**: the GET shape for `01K...` ULIDs when
   authenticated. Probably JSON-LD like stock recipes, but confirm.
5. **Custom recipe CRUD**: **CONFIRMED WORKING 2026-06-06** (window 14, reverse-engineered from alexandrepa-mcp-cookidoo).
   - **Step 1** — POST `{base_url}/created-recipes/{locale}` with `{"recipeName": "<name>"}` → returns blank recipe with ULID.
   - **Step 2** — PATCH `{base_url}/created-recipes/{locale}/{recipe_id}` with full detail body:
     - `name`: string
     - `ingredients`: `[{type: "ingredient", text: "..."}]` — flat text lines, NOT a name/description split
     - `instructions`: `[{type: "instruction", text: "..."}]`
     - `yield`: object (servings)
     - times in **seconds** (alexandrepa-mcp-cookidoo converts at API boundary)
   - Confirmed live: ULID `01KTECKZHEN6EE20HF7WH8E9RC` (Pan-Seared Cod with Lemon Butter) created 2026-06-06.
   - Auth note: Bearer token in their source; in our session, cookies-based auth via the existing MCP passthrough works.
   - **Gap closed for M4**. Still capture in M1 pass 2 to confirm full request/response shapes.
6. **Token exchange**: full CIAM OAuth2 flow including the
   `ciam.prod.cookidoo.vorwerk-digital.com` `x-unknown` call. Need full HAR
   through the login redirect chain.
7. **Favorite / bookmark a recipe**: no known endpoint. The
   `manageBookmark` page template
   (`/organize/{lang}/transclude/manage-bookmark/{recipeId}`) is the likely
   surface, but the underlying POST/DELETE shape is unmapped. Gap surfaced by
   meal-planning 2026-05-27 — Thomas asked to favorite `r292456` (Beetroot
   Quinoa Salad) and current cookidoo-mcp has no support. Failed probes via
   `cookidoo_http_request`: `GET community/en/api/favourites` (auth error),
   `GET favourites/en` (404), `POST community/en/api/recipes/r292456/bookmark`
   (405), `GET community/en/bookmarks` (404). Capture both fav + unfav to map
   the DELETE side too. Once mapped, expose as
   `favorite_recipe(recipe_id)` / `unfavorite_recipe(recipe_id)` in the
   write client (M4) and a `list_favorites()` reader in M3.

### Next capture-pass plan

1. Drive the **persistent profile** directly (not a fresh context) so auth
   actually works. Since Playwright's `recordHar` is silently ignored on
   `launchPersistentContext`, do manual HAR construction via `page.on(
   'request' | 'response' )` listeners and serialise to disk on exit. Or
   switch to capturing via Chrome DevTools Protocol (CDP) sessions over the
   persistent context — that supports network events.
2. Walk the same flows but slower (8–10s per step) and trigger the actions
   that matter for write endpoints:
   - Open My Week → wait for hydration XHRs to settle
   - Add a stock recipe to My Week → capture the request
   - Remove it → capture the request
   - Open shopping list → capture hydration
   - Add a recipe to shopping list from a recipe page → capture
   - Open custom recipe → capture authenticated GET
   - Edit custom recipe → fill one field → save → capture PATCH (NB: actually save this time so we get the real payload; revert afterward)
   - Click heart/bookmark icon on a stock recipe page (e.g. `r292456`) → capture POST
   - Navigate "My Recipes" → "Favorites" tab → capture list GET (URL also unknown)
   - Un-favorite the same recipe → capture DELETE
3. Capture the full login redirect chain on a logged-out persistent profile in a separate run, to fully document the CIAM exchange for M2.

---

## API Response Quirks (confirmed 2026-06-06)

These are gotchas where the immediate response body is misleading — the side-effect succeeds but the response doesn't reflect it. Always verify with `cookidoo_get_my_week` (NOT `get_calendar_week`) rather than trusting the write-call response.

1. **Custom recipe → My Week add**: `add_custom_recipes_to_calendar` returns a response with an empty `recipes` array even on success. The recipe IS scheduled — verify with `cookidoo_get_my_week`.
2. **Calendar remove**: `remove_from_calendar` response body still shows the removed recipe in the day's block — looks like a no-op. Actually worked — verify with `cookidoo_get_my_week`.
3. **Pattern**: trust the side-effect, not the response body. Use `cookidoo_get_my_week` (merged endpoint that surfaces both stock + custom) as the canonical read-back for any calendar mutation.

---

## Shopping List Notes (confirmed 2026-06-06)

- `add_to_shopping_list(recipe_ids=[...])` is **recipe-scoped only** — it adds all ingredients for a given recipe. No freehand item add through this surface.
- The list response appends ingredients with auto-generated ULIDs per line.
- **Gap (M3/M4)**: the web app's shopping list UI allows freeform item entry — there is likely a separate per-item add endpoint. Still unmapped; add to M1 pass 2 capture plan.

---

## Auth — One-Shot Interactive Bootstrap (confirmed 2026-06-06)

Window 14 confirmed: importing `cookidoo_service.py`'s login flow into a standalone script fails outside the MCP server's existing browser-OAuth2 session. The CIAM flow requires an interactive browser for the initial login; it cannot re-login from a script using only a stored cookie jar.

**M2 design implication**: treat OAuth2 login as a **one-shot interactive bootstrap**. Subsequent calls run against a persisted cookie jar. Do NOT design for "fresh login on every script start" — that assumption is wrong and will fail the way the forks failed.
