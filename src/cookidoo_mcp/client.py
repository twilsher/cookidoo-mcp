"""Singleton wrapper managing the cookidoo-api session."""

from __future__ import annotations

import os
from typing import Any

import aiohttp
from cookidoo_api import Cookidoo
from cookidoo_api.types import CookidooConfig, CookidooLocalizationConfig

# Supported locales — extend as needed
LOCALE_MAP: dict[str, CookidooLocalizationConfig] = {
    "en-US": CookidooLocalizationConfig(
        country_code="us",
        language="en-US",
        url="https://cookidoo.thermomix.com/foundation/en-US",
    ),
    "en-GB": CookidooLocalizationConfig(
        country_code="gb",
        language="en-GB",
        url="https://cookidoo.co.uk/foundation/en-GB",
    ),
    "pl": CookidooLocalizationConfig(
        country_code="pl",
        language="pl",
        url="https://cookidoo.pl/foundation/pl",
    ),
    "de-DE": CookidooLocalizationConfig(
        country_code="de",
        language="de-DE",
        url="https://cookidoo.de/foundation/de-DE",
    ),
    "fr-FR": CookidooLocalizationConfig(
        country_code="fr",
        language="fr-FR",
        url="https://cookidoo.fr/foundation/fr-FR",
    ),
    "es-ES": CookidooLocalizationConfig(
        country_code="es",
        language="es-ES",
        url="https://cookidoo.es/foundation/es-ES",
    ),
    "it-IT": CookidooLocalizationConfig(
        country_code="it",
        language="it-IT",
        url="https://cookidoo.it/foundation/it-IT",
    ),
    "nl-NL": CookidooLocalizationConfig(
        country_code="nl",
        language="nl-NL",
        url="https://cookidoo.nl/foundation/nl-NL",
    ),
    "pt-PT": CookidooLocalizationConfig(
        country_code="pt",
        language="pt-PT",
        url="https://cookidoo.pt/foundation/pt-PT",
    ),
    "ru-RU": CookidooLocalizationConfig(
        country_code="ru",
        language="ru-RU",
        url="https://cookidoo.ru/foundation/ru-RU",
    ),
    "no": CookidooLocalizationConfig(
        country_code="no",
        language="en",
        url="https://cookidoo.international/foundation/en",
    ),
    "se": CookidooLocalizationConfig(
        country_code="se",
        language="en",
        url="https://cookidoo.international/foundation/en",
    ),
    "dk": CookidooLocalizationConfig(
        country_code="dk",
        language="en",
        url="https://cookidoo.international/foundation/en",
    ),
}


class CookidooClient:
    """Singleton managing a cookidoo-api session with lazy login and token refresh."""

    _instance: CookidooClient | None = None

    def __init__(self) -> None:
        self._api: Cookidoo | None = None
        self._session: aiohttp.ClientSession | None = None

    @classmethod
    def get(cls) -> "CookidooClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _ensure_authenticated(self) -> Cookidoo:
        """Return an authenticated Cookidoo instance, logging in on first use."""
        if self._api is not None:
            return self._api

        email = os.environ.get("COOKIDOO_EMAIL", "")
        password = os.environ.get("COOKIDOO_PASSWORD", "")
        locale_key = os.environ.get("COOKIDOO_LOCALE", "en-US")

        if not email or not password:
            raise RuntimeError(
                "COOKIDOO_EMAIL and COOKIDOO_PASSWORD must be set in .env"
            )

        localization = LOCALE_MAP.get(locale_key, LOCALE_MAP["en-US"])
        cfg = CookidooConfig(localization=localization, email=email, password=password)

        # The browser OAuth2 flow follows redirects across cookidoo.<tld>,
        # the CIAM authorization server, and login-srv; aiohttp's default
        # CookieJar rejects cross-domain cookies, so we need unsafe=True.
        self._session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
        self._api = Cookidoo(self._session, cfg)
        try:
            await self._api.login()
        except Exception:
            await self.close()
            self._api = None
            self._session = None
            raise

        return self._api

    async def api(self) -> Cookidoo:
        """Get an authenticated Cookidoo API instance."""
        return await self._ensure_authenticated()

    async def _relogin(self) -> Cookidoo:
        """Drop the current session and re-authenticate from scratch."""
        await self.close()
        self._api = None
        self._session = None
        return await self._ensure_authenticated()

    async def call(self, coro_fn):
        """Call an async function that takes a Cookidoo instance, retrying once on 401."""
        api = await self.api()
        try:
            return await coro_fn(api)
        except aiohttp.ClientResponseError as exc:
            if exc.status != 401:
                raise
            api = await self._relogin()
            return await coro_fn(api)

    async def _do_raw_request(
        self,
        api: "Cookidoo",
        method: str,
        path: str,
        body: dict[str, Any] | None,
        query: dict[str, Any] | None,
        headers: dict[str, str] | None,
    ) -> dict[str, Any]:
        relative_path = path.lstrip("/")
        url = api.api_endpoint / relative_path
        merged_headers = {**api._api_headers, **(headers or {})}
        async with api._session.request(
            method.upper(),
            url,
            headers=merged_headers,
            json=body,
            params=query,
        ) as response:
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                data: Any = await response.json()
            else:
                data = await response.text()
            if response.status == 401:
                response.raise_for_status()
            return {"status": response.status, "url": str(response.url), "body": data}

    async def raw_request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute an authenticated request against the localized Cookidoo API, retrying once on 401.

        Non-2xx responses (except 401, which triggers a relogin retry) are
        returned intact — the caller inspects ``status`` and ``body`` to
        diagnose 4xx/5xx. This is intentional for the raw escape hatch, where
        the response body of a 400 is often the whole diagnostic signal.
        """
        api = await self.api()
        try:
            return await self._do_raw_request(api, method, path, body, query, headers)
        except aiohttp.ClientResponseError as exc:
            if exc.status != 401:
                raise
            api = await self._relogin()
            return await self._do_raw_request(api, method, path, body, query, headers)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
