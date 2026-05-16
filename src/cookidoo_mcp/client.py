"""Singleton wrapper managing the cookidoo-api session."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import aiohttp
from cookidoo_api import Cookidoo
from cookidoo_api.types import CookidooConfig, CookidooLocalizationConfig

if TYPE_CHECKING:
    pass

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
        """Return an authenticated Cookidoo instance, logging in or refreshing as needed."""
        if self._api is None:
            email = os.environ.get("COOKIDOO_EMAIL", "")
            password = os.environ.get("COOKIDOO_PASSWORD", "")
            locale_key = os.environ.get("COOKIDOO_LOCALE", "en-US")

            if not email or not password:
                raise RuntimeError(
                    "COOKIDOO_EMAIL and COOKIDOO_PASSWORD must be set in .env"
                )

            localization = LOCALE_MAP.get(locale_key, LOCALE_MAP["en-US"])
            cfg = CookidooConfig(localization=localization, email=email, password=password)

            self._session = aiohttp.ClientSession()
            self._api = Cookidoo(self._session, cfg)
            auth = await self._api.login()
            self._api.auth_data = auth
            return self._api

        # Refresh token if near expiry (< 60 seconds remaining)
        if self._api.expires_in < 60:
            try:
                auth = await self._api.refresh_token()
            except Exception:
                # Fall back to full re-login
                auth = await self._api.login()
            self._api.auth_data = auth

        return self._api

    async def api(self) -> Cookidoo:
        """Get an authenticated Cookidoo API instance."""
        return await self._ensure_authenticated()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
