"""FastMCP server with all Cookidoo tools."""

from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

from dotenv import load_dotenv
from mcp.types import ToolAnnotations
from mcp.server.fastmcp import FastMCP

from cookidoo_mcp.client import CookidooClient

load_dotenv()

mcp = FastMCP("cookidoo", dependencies=["cookidoo-api", "python-dotenv", "aiohttp"])

_client = CookidooClient.get()

READ_ONLY_TOOL_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
)
MUTATION_TOOL_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
)


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PATCH = "PATCH"
    DELETE = "DELETE"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize(value: str) -> str:
    """Strip control characters to prevent prompt injection via untrusted recipe data."""
    return re.sub(r"[\x00-\x1f\x7f]", "", value)


def _search_locale(language: str) -> str:
    """Extract the bare language code used in the search path (e.g. 'en-US' → 'en')."""
    return language.split("-")[0].lower()


def _pick_image(assets: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Extract (thumbnail, image) from descriptiveAssets list."""
    for asset in assets:
        url = asset.get("square") or asset.get("landscape") or asset.get("portrait")
        if url:
            return url, url
    return None, None


_STANDARD_RECIPE_ID_RE = re.compile(r"^r\d+$")


def _is_custom_recipe_id(recipe_id: str) -> bool:
    """Cookidoo has two recipe-ID shapes routed to different calendar endpoints.

    Standard catalog recipes use `r` + digits (e.g. `r150903`); custom (user-created)
    recipes use a 26-char ULID (e.g. `01KRRK46H63Z0BSN5ZP2Y99P2W`). The two require
    different API methods to add/remove from the meal calendar.
    """
    return not _STANDARD_RECIPE_ID_RE.match(recipe_id)


def _parse_date(date_str: str | None) -> date:
    if not date_str:
        return date.today()
    return datetime.fromisoformat(date_str).date()


def _require_confirmed(confirmed: bool) -> None:
    if confirmed is not True:
        raise RuntimeError(
            "This Cookidoo mutation tool requires confirmed=true after explicit user approval."
        )


def _format_recipe_summary(recipe: Any) -> dict[str, Any]:
    return {
        "id": recipe.id,
        "name": _sanitize(recipe.name),
        "url": recipe.url,
        "total_time_seconds": recipe.total_time,
        "thumbnail": recipe.thumbnail,
    }


def _format_calendar_day(
    day: Any, extra_recipes: list[Any] | None = None
) -> dict[str, Any]:
    recipes = [_format_recipe_summary(recipe) for recipe in day.recipes]
    if extra_recipes:
        recipes.extend(_format_recipe_summary(r) for r in extra_recipes)
    return {
        "id": day.id,
        "title": _sanitize(day.title),
        "recipes": recipes,
    }


async def _fetch_custom_recipe_ids_for_week(target: date) -> dict[str, list[str]]:
    """Read the raw my-week response and return {dayKey: [custom_ulid, ...]}.

    The cookidoo-api library's CookidooCalendarDay dataclass drops the
    customerRecipeIds field, so to surface custom recipes in the meal plan we
    have to hit the raw endpoint ourselves.
    """
    api = await _client.api()
    language = api._cfg.localization.language
    path = f"planning/{language}/api/my-week/{target.isoformat()}"
    response = await _client.raw_request("GET", path)
    body = response.get("body") or {}
    days = body.get("myDays", []) if isinstance(body, dict) else []
    out: dict[str, list[str]] = {}
    for day in days:
        if not isinstance(day, dict):
            continue
        day_key = day.get("dayKey")
        custom_ids = day.get("customerRecipeIds") or []
        if day_key and custom_ids:
            out[day_key] = list(custom_ids)
    return out


async def _fetch_custom_recipes(custom_ids: set[str]) -> dict[str, Any]:
    """Fetch each custom recipe by ID and return {id: CookidooCustomRecipe}.

    Skips any IDs the lookup can't resolve (deleted recipe, transient error).
    """
    if not custom_ids:
        return {}
    api = await _client.api()
    results = await asyncio.gather(
        *(api.get_custom_recipe(rid) for rid in custom_ids),
        return_exceptions=True,
    )
    out: dict[str, Any] = {}
    for rid, result in zip(custom_ids, results):
        if not isinstance(result, BaseException):
            out[rid] = result
    return out


def _format_ingredient(ingredient: Any) -> dict[str, Any]:
    return {
        "id": ingredient.id,
        "name": _sanitize(ingredient.name),
        "description": _sanitize(ingredient.description),
    }


def _format_shopping_item(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": _sanitize(item.name),
        "description": _sanitize(item.description),
        "is_owned": item.is_owned,
    }


def _recipe_path(language: str, recipe_id: str) -> str:
    return f"recipes/recipe/{language}/{recipe_id}"


async def _get_raw_recipe(recipe_id: str) -> dict[str, Any]:
    api = await _client.api()
    raw = await _client.raw_request(
        "GET",
        _recipe_path(api.localization.language, recipe_id),
    )
    body = raw["body"]
    if not isinstance(body, dict):
        raise RuntimeError("Cookidoo recipe details response was not JSON.")
    return body


def _format_steps(raw_recipe: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for group_index, group in enumerate(raw_recipe.get("recipeStepGroups", []), start=1):
        group_title = _sanitize(str(group.get("title") or ""))
        for step_index, step in enumerate(group.get("recipeSteps", []), start=1):
            steps.append(
                {
                    "group_index": group_index,
                    "group_title": group_title,
                    "step_index": step_index,
                    "title": _sanitize(str(step.get("title") or "")),
                    "text": _sanitize(str(step.get("formattedText") or "")),
                }
            )
    return steps


async def _get_recipe_payload(recipe_id: str) -> dict[str, Any]:
    api = await _client.api()
    details = await api.get_recipe_details(recipe_id)
    raw_recipe = await _get_raw_recipe(recipe_id)
    return {
        "id": details.id,
        "name": _sanitize(details.name),
        "url": details.url,
        "difficulty": details.difficulty,
        "active_time_seconds": details.active_time,
        "total_time_seconds": details.total_time,
        "serving_size": details.serving_size,
        "thumbnail": details.thumbnail,
        "notes": [_sanitize(n) for n in details.notes],
        "utensils": [_sanitize(u) for u in details.utensils],
        "categories": [
            {"id": c.id, "name": _sanitize(c.name), "notes": _sanitize(c.notes)}
            for c in details.categories
        ],
        "collections": [
            {"id": c.id, "name": _sanitize(c.name), "total_recipes": c.total_recipes}
            for c in details.collections
        ],
        "ingredients": [_format_ingredient(i) for i in details.ingredients],
        "nutrition_groups": [
            {
                "name": _sanitize(ng.name),
                "entries": [
                    {
                        "quantity": rn.quantity,
                        "unit": _sanitize(rn.unit_notation),
                        "nutritions": [
                            {
                                "type": _sanitize(n.type),
                                "number": n.number,
                                "unit": _sanitize(n.unittype),
                            }
                            for n in rn.nutritions
                        ],
                    }
                    for rn in ng.recipe_nutritions
                ],
            }
            for ng in details.nutrition_groups
        ],
        "steps": _format_steps(raw_recipe),
    }


# ---------------------------------------------------------------------------
# Priority tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=READ_ONLY_TOOL_ANNOTATIONS)
async def cookidoo_search_recipes(
    query: str, max_results: int = 10
) -> list[dict[str, Any]]:
    """Search Cookidoo recipes by name, ingredient, or cuisine.

    Args:
        query: Free-text search term (e.g. "pasta tomato", "chicken curry", "gluten free cake").
        max_results: Maximum number of results to return (default 10). The
            server returns at most 20 results per call regardless of this value.
    """
    api = await _client.api()

    lang = _search_locale(api.localization.language)
    # The mobile API host (api.api_endpoint) exposes /search/<lang>, but it
    # returns matches from an unfiltered global pool — empty results for many
    # queries and cross-language noise (e.g. Czech soups for "korean pork").
    # The public web host serves the same path with the locale filter applied,
    # matching what users see at cookidoo.international/search/<lang>.
    base_url = api.localization.url.rsplit("/foundation/", 1)[0]
    url = f"{base_url}/search/{lang}"

    headers = dict(api._api_headers)
    if api._auth_data:
        headers["Cookie"] = f"v-token={api._auth_data.access_token}"

    # The endpoint is 0-indexed; page=1 returns a fallback "popular recipes"
    # pool from a different locale. pageSize is ignored — 20 results per page,
    # always — so we trim client-side instead.
    params = {"query": query, "page": "0"}

    async with api._session.get(url, headers=headers, params=params) as r:
        r.raise_for_status()
        data = await r.json()

    raw_recipes = data.get("data") or data.get("recipes") or []

    results = []
    for item in raw_recipes[:max_results]:
        recipe_id = item.get("id", "")
        name = _sanitize(item.get("title") or item.get("name") or "")
        assets = item.get("descriptiveAssets") or []
        thumbnail, _image = _pick_image(assets)
        total_time = item.get("totalTime") or item.get("total_time")
        recipe_url = f"{base_url}/recipes/recipe/{lang}/{recipe_id}"
        results.append({
            "id": recipe_id,
            "name": name,
            "url": recipe_url,
            "total_time_seconds": total_time,
            "thumbnail": thumbnail,
        })

    return results


@mcp.tool(annotations=READ_ONLY_TOOL_ANNOTATIONS)
async def cookidoo_get_recipe(recipe_id: str) -> dict[str, Any]:
    """Get a Cookidoo recipe by ID, including ingredients and preparation steps.

    Args:
        recipe_id: The Cookidoo recipe ID (e.g. "r907001").
    """
    return await _get_recipe_payload(recipe_id)


@mcp.tool(annotations=READ_ONLY_TOOL_ANNOTATIONS)
async def cookidoo_get_shopping_list() -> list[dict[str, Any]]:
    """Get the current Cookidoo shopping list items."""
    api = await _client.api()
    items = await api.get_ingredient_items()
    return [_format_shopping_item(item) for item in items]


@mcp.tool(annotations=READ_ONLY_TOOL_ANNOTATIONS)
async def cookidoo_get_my_week(
    weeks: int = 2, start_date: str = ""
) -> list[dict[str, Any]]:
    """Get planned Cookidoo recipes for upcoming calendar weeks.

    Args:
        weeks: Number of upcoming weeks to return, including the current week (default 2, max 8).
        start_date: Optional ISO date to start from. Defaults to today.
    """
    api = await _client.api()
    start = _parse_date(start_date or None)
    week_count = min(max(1, weeks), 8)

    planned_weeks = []
    for offset in range(week_count):
        target = start + timedelta(weeks=offset)
        week_start = target - timedelta(days=target.weekday())
        days, custom_ids_by_day = await asyncio.gather(
            api.get_recipes_in_calendar_week(target),
            _fetch_custom_recipe_ids_for_week(target),
        )
        all_custom_ids = {rid for ids in custom_ids_by_day.values() for rid in ids}
        custom_recipes = await _fetch_custom_recipes(all_custom_ids)
        planned_weeks.append(
            {
                "week_start": week_start.isoformat(),
                "week_end": (week_start + timedelta(days=6)).isoformat(),
                "days": [
                    _format_calendar_day(
                        day,
                        extra_recipes=[
                            custom_recipes[rid]
                            for rid in custom_ids_by_day.get(day.id, [])
                            if rid in custom_recipes
                        ],
                    )
                    for day in days
                ],
            }
        )

    return planned_weeks


@mcp.tool(annotations=MUTATION_TOOL_ANNOTATIONS)
async def cookidoo_http_request(
    method: HttpMethod,
    path: str,
    body: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    confirmed: bool = False,
) -> dict[str, Any]:
    """Execute a raw Cookidoo API request with the stored session.

    Non-GET requests require confirmed=true after explicit user approval.
    Use relative API paths, e.g. "shopping/en-US" or "planning/en-US/api/my-week/2026-05-16".
    """
    if method != HttpMethod.GET:
        _require_confirmed(confirmed)

    return await _client.raw_request(
        method.value,
        path,
        body=body,
        query=query,
    )


# ---------------------------------------------------------------------------
# Backwards-compatible tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=READ_ONLY_TOOL_ANNOTATIONS)
async def search_recipes(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Search Cookidoo recipes by name, ingredient, or cuisine.

    Args:
        query: Free-text search term (e.g. "pasta tomato", "chicken curry", "gluten free cake").
        max_results: Maximum number of results to return (default 10). The
            server returns at most 20 results per call regardless of this value.
    """
    return await cookidoo_search_recipes(query, max_results)


# ---------------------------------------------------------------------------
# Priority 2 — Recipe Details & Shopping List
# ---------------------------------------------------------------------------

@mcp.tool(annotations=READ_ONLY_TOOL_ANNOTATIONS)
async def get_recipe_details(recipe_id: str) -> dict[str, Any]:
    """Get full details for a recipe: ingredients, timing, nutrition, categories, difficulty.

    Args:
        recipe_id: The Cookidoo recipe ID (e.g. "r907001").
    """
    return await _get_recipe_payload(recipe_id)


@mcp.tool(annotations=READ_ONLY_TOOL_ANNOTATIONS)
async def get_shopping_list() -> list[dict[str, Any]]:
    """Get the current shopping list — all ingredient items with quantities and ownership status."""
    return await cookidoo_get_shopping_list()


@mcp.tool(annotations=MUTATION_TOOL_ANNOTATIONS)
async def add_to_shopping_list(
    recipe_ids: list[str], confirmed: bool = False
) -> list[dict[str, Any]]:
    """Add recipe ingredients to the shopping list.

    Args:
        recipe_ids: List of Cookidoo recipe IDs whose ingredients to add.
        confirmed: Must be true after explicit user approval.
    """
    _require_confirmed(confirmed)
    api = await _client.api()
    items = await api.add_ingredient_items_for_recipes(recipe_ids)
    return [_format_shopping_item(item) for item in items]


@mcp.tool(annotations=MUTATION_TOOL_ANNOTATIONS)
async def remove_from_shopping_list(
    recipe_ids: list[str], confirmed: bool = False
) -> list[dict[str, Any]]:
    """Remove recipe ingredients from the shopping list.

    Args:
        recipe_ids: List of Cookidoo recipe IDs whose ingredients to remove.
        confirmed: Must be true after explicit user approval.
    """
    _require_confirmed(confirmed)
    api = await _client.api()
    await api.remove_ingredient_items_for_recipes(recipe_ids)
    items = await api.get_ingredient_items()
    return [_format_shopping_item(item) for item in items]


@mcp.tool(annotations=MUTATION_TOOL_ANNOTATIONS)
async def clear_shopping_list(confirmed: bool = False) -> dict[str, str]:
    """Wipe the entire shopping list (removes all ingredient items)."""
    _require_confirmed(confirmed)
    api = await _client.api()
    await api.clear_shopping_list()
    return {"status": "ok", "message": "Shopping list cleared."}


# ---------------------------------------------------------------------------
# Priority 3 — Meal Calendar
# ---------------------------------------------------------------------------

@mcp.tool(annotations=READ_ONLY_TOOL_ANNOTATIONS)
async def get_calendar_week(date: str = "") -> list[dict[str, Any]]:
    """View the meal plan for the week containing the given date.

    Args:
        date: ISO date string (e.g. "2025-03-15"). Defaults to today.
    """
    api = await _client.api()
    target = _parse_date(date or None)
    days, custom_ids_by_day = await asyncio.gather(
        api.get_recipes_in_calendar_week(target),
        _fetch_custom_recipe_ids_for_week(target),
    )
    all_custom_ids = {rid for ids in custom_ids_by_day.values() for rid in ids}
    custom_recipes = await _fetch_custom_recipes(all_custom_ids)
    return [
        _format_calendar_day(
            day,
            extra_recipes=[
                custom_recipes[rid]
                for rid in custom_ids_by_day.get(day.id, [])
                if rid in custom_recipes
            ],
        )
        for day in days
    ]


@mcp.tool(annotations=MUTATION_TOOL_ANNOTATIONS)
async def add_to_calendar(
    recipe_ids: list[str], date: str, confirmed: bool = False
) -> dict[str, Any]:
    """Schedule recipes for a specific day in the meal calendar.

    Args:
        recipe_ids: List of Cookidoo recipe IDs to add.
        date: ISO date string for the target day (e.g. "2025-03-15").
        confirmed: Must be true after explicit user approval.
    """
    _require_confirmed(confirmed)
    api = await _client.api()
    target = _parse_date(date)

    standard_ids = [rid for rid in recipe_ids if not _is_custom_recipe_id(rid)]
    custom_ids = [rid for rid in recipe_ids if _is_custom_recipe_id(rid)]

    day = None
    if standard_ids:
        day = await api.add_recipes_to_calendar(target, standard_ids)
    if custom_ids:
        day = await api.add_custom_recipes_to_calendar(target, custom_ids)
    return _format_calendar_day(day)


@mcp.tool(annotations=MUTATION_TOOL_ANNOTATIONS)
async def remove_from_calendar(
    recipe_id: str, date: str, confirmed: bool = False
) -> dict[str, Any]:
    """Remove a recipe from a specific day in the meal calendar.

    Args:
        recipe_id: The Cookidoo recipe ID to remove.
        date: ISO date string for the target day (e.g. "2025-03-15").
        confirmed: Must be true after explicit user approval.
    """
    _require_confirmed(confirmed)
    api = await _client.api()
    target = _parse_date(date)
    if _is_custom_recipe_id(recipe_id):
        day = await api.remove_custom_recipe_from_calendar(target, recipe_id)
    else:
        day = await api.remove_recipe_from_calendar(target, recipe_id)
    return _format_calendar_day(day)
