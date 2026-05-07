import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import List, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


@dataclass
class MarketplaceOffer:
    platform_name: str
    title: str
    external_id: str
    description: str = ""
    category: str = ""
    brand: str = ""
    image_url: str = ""
    product_url: str = ""
    seller_name: str = ""
    price: Decimal = Decimal("0.00")
    original_price: Decimal | None = None
    shipping_cost: Decimal = Decimal("0.00")
    delivery_time: str = ""
    availability_status: bool = True
    rating: float | None = None
    review_count: int = 0
    request_status: str = "200 OK"


def _read_json(url: str) -> dict:
    request = Request(url=url, method="GET")
    with urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _to_decimal(value) -> Decimal | None:
    if value in (None, "", False):
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        return None


class SerpApiClient:
    def __init__(self, config: dict):
        self.config = config

    def is_enabled(self) -> bool:
        return bool(self.config.get("enabled"))

    def is_configured(self) -> bool:
        return self.is_enabled() and bool(self.config.get("api_key"))

    def _search(self, params: dict) -> dict:
        query = urlencode(params)
        return _read_json(f"https://serpapi.com/search.json?{query}")

    def search_google_shopping(self, query: str, result_count: int = 10) -> List[MarketplaceOffer]:
        if not self.is_configured():
            return []
        response = self._search(
            {
                "engine": "google_shopping",
                "q": query,
                "api_key": self.config["api_key"],
                "google_domain": self.config.get("google_domain", "google.co.in"),
                "location": self.config.get("location", "India"),
                "gl": self.config.get("gl", "in"),
                "hl": self.config.get("hl", "en"),
                "num": min(result_count, 20),
            }
        )
        results = response.get("shopping_results", [])
        offers: List[MarketplaceOffer] = []
        for item in results:
            title = item.get("title", "")
            link = item.get("link") or item.get("product_link") or ""
            source = item.get("source") or item.get("merchant") or "Marketplace"
            price = _to_decimal(item.get("extracted_price") or item.get("price"))
            if not title or not price:
                continue
            offers.append(
                MarketplaceOffer(
                    platform_name=source,
                    title=title,
                    external_id=str(item.get("product_id") or link or title),
                    description=item.get("snippet", ""),
                    image_url=item.get("thumbnail", ""),
                    product_url=link,
                    seller_name=source,
                    price=price,
                    original_price=_to_decimal(item.get("extracted_old_price") or item.get("old_price")),
                    delivery_time=", ".join(item.get("extensions", [])[:2]) if item.get("extensions") else "",
                    availability_status=True,
                    rating=item.get("rating"),
                    review_count=int(item.get("reviews") or item.get("reviews_count") or 0),
                )
            )
        return offers

    def search_amazon(self, query: str, result_count: int = 10) -> List[MarketplaceOffer]:
        if not self.is_configured():
            return []
        response = self._search(
            {
                "engine": "amazon",
                "k": query,
                "api_key": self.config["api_key"],
                "amazon_domain": self.config.get("amazon_domain", "amazon.in"),
            }
        )
        results = response.get("organic_results", [])[:result_count]
        offers: List[MarketplaceOffer] = []
        for item in results:
            price_block = item.get("price") or {}
            price = _to_decimal(price_block.get("value") or price_block.get("raw"))
            if not item.get("title") or not price:
                continue
            offers.append(
                MarketplaceOffer(
                    platform_name="Amazon",
                    title=item.get("title", ""),
                    external_id=item.get("asin", "") or item.get("position", ""),
                    description=item.get("snippet", ""),
                    image_url=item.get("thumbnail", ""),
                    product_url=item.get("link", ""),
                    seller_name="Amazon",
                    price=price,
                    original_price=_to_decimal((item.get("previous_price") or {}).get("value")),
                    delivery_time=item.get("delivery", ""),
                    availability_status=True,
                    rating=item.get("rating"),
                    review_count=int(item.get("reviews") or item.get("reviews_count") or 0),
                )
            )
        return offers


def search_marketplaces(query: str, result_count: int = 10) -> Tuple[List[MarketplaceOffer], List[str]]:
    config = settings.MARKETPLACE_INTEGRATIONS["serpapi"]
    client = SerpApiClient(config)
    offers: List[MarketplaceOffer] = []
    notes: List[str] = []

    if not client.is_enabled():
        return [], ["SerpApi integration is disabled."]
    if not client.is_configured():
        return [], ["SerpApi is enabled but the API key is missing."]

    try:
        google_offers = client.search_google_shopping(query, result_count=result_count)
        offers.extend(google_offers)
        notes.append(f"Google Shopping: {len(google_offers)} offers fetched.")
    except HTTPError as exc:
        notes.append(f"Google Shopping request failed with HTTP {exc.code}.")
    except URLError:
        notes.append("Google Shopping request failed because the network was unavailable.")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Google Shopping request failed: {exc}.")

    try:
        amazon_offers = client.search_amazon(query, result_count=result_count)
        offers.extend(amazon_offers)
        notes.append(f"Amazon Search: {len(amazon_offers)} offers fetched.")
    except HTTPError as exc:
        notes.append(f"Amazon Search request failed with HTTP {exc.code}.")
    except URLError:
        notes.append("Amazon Search request failed because the network was unavailable.")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Amazon Search request failed: {exc}.")

    return offers, notes
