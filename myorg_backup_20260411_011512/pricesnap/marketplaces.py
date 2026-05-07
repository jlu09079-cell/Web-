import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
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
    request_status: str = "200 OK"


def _read_json(request: Request) -> dict:
    with urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _to_decimal(value) -> Decimal | None:
    if value in (None, "", False):
        return None
    if isinstance(value, dict):
        value = value.get("amount") or value.get("Amount") or value.get("value")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


class BaseMarketplaceClient:
    platform_name = ""

    def __init__(self, config: dict):
        self.config = config

    def is_enabled(self) -> bool:
        return bool(self.config.get("enabled"))

    def is_configured(self) -> bool:
        raise NotImplementedError

    def search_products(self, query: str, result_count: int = 10) -> List[MarketplaceOffer]:
        raise NotImplementedError


class AmazonMarketplaceClient(BaseMarketplaceClient):
    platform_name = "Amazon"

    def is_configured(self) -> bool:
        required = ("access_key", "secret_key", "partner_tag", "host", "region", "marketplace")
        return self.is_enabled() and all(self.config.get(field) for field in required)

    def _sign(self, payload: str, amz_date: str, date_stamp: str) -> dict:
        host = self.config["host"]
        region = self.config["region"]
        access_key = self.config["access_key"]
        secret_key = self.config["secret_key"]

        canonical_headers = (
            f"content-encoding:amz-1.0\n"
            f"content-type:application/json; charset=utf-8\n"
            f"host:{host}\n"
            f"x-amz-date:{amz_date}\n"
            f"x-amz-target:com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems\n"
        )
        signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = "\n".join(
            [
                "POST",
                "/paapi5/searchitems",
                "",
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{region}/ProductAdvertisingAPI/aws4_request"
        string_to_sign = "\n".join(
            [
                algorithm,
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )

        def sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        k_date = sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
        k_region = sign(k_date, region)
        k_service = sign(k_region, "ProductAdvertisingAPI")
        k_signing = sign(k_service, "aws4_request")
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (
            f"{algorithm} Credential={access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return {
            "Content-Encoding": "amz-1.0",
            "Content-Type": "application/json; charset=utf-8",
            "Host": host,
            "X-Amz-Date": amz_date,
            "X-Amz-Target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems",
            "Authorization": authorization,
        }

    def search_products(self, query: str, result_count: int = 10) -> List[MarketplaceOffer]:
        if not self.is_configured():
            return []

        body = {
            "Keywords": query,
            "ItemCount": min(result_count, 10),
            "PartnerTag": self.config["partner_tag"],
            "PartnerType": self.config.get("partner_type", "Associates"),
            "Marketplace": self.config["marketplace"],
            "SearchIndex": self.config.get("search_index", "All"),
            "Resources": [
                "Images.Primary.Medium",
                "ItemInfo.ByLineInfo",
                "ItemInfo.Features",
                "ItemInfo.Title",
                "Offers.Listings.Availability.Message",
                "Offers.Listings.Price",
            ],
        }
        payload = json.dumps(body)
        now = datetime.utcnow()
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        headers = self._sign(payload, amz_date, date_stamp)

        request = Request(
            url=f"https://{self.config['host']}/paapi5/searchitems",
            data=payload.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        response = _read_json(request)
        items = response.get("SearchResult", {}).get("Items", [])
        offers: List[MarketplaceOffer] = []
        for item in items:
            offer_block = ((item.get("Offers") or {}).get("Listings") or [{}])[0]
            price_block = offer_block.get("Price", {})
            amount = _to_decimal(price_block.get("Amount"))
            savings_basis = _to_decimal(((price_block.get("Savings") or {}).get("Basis")))
            if not amount:
                continue
            feature_values = ((item.get("ItemInfo") or {}).get("Features") or {}).get("DisplayValues") or []
            availability_message = (((offer_block.get("Availability") or {}).get("Message")) or "Available")
            offers.append(
                MarketplaceOffer(
                    platform_name=self.platform_name,
                    title=((item.get("ItemInfo") or {}).get("Title") or {}).get("DisplayValue", ""),
                    external_id=item.get("ASIN", ""),
                    description=feature_values[0] if feature_values else "",
                    brand=(((item.get("ItemInfo") or {}).get("ByLineInfo") or {}).get("Brand") or {}).get("DisplayValue", ""),
                    image_url=((((item.get("Images") or {}).get("Primary") or {}).get("Medium") or {}).get("URL", "")),
                    product_url=item.get("DetailPageURL", ""),
                    seller_name=self.platform_name,
                    price=amount,
                    original_price=savings_basis,
                    shipping_cost=Decimal("0.00"),
                    delivery_time=availability_message,
                    availability_status="out" not in availability_message.lower(),
                )
            )
        return offers


class FlipkartMarketplaceClient(BaseMarketplaceClient):
    platform_name = "Flipkart"

    def is_configured(self) -> bool:
        required = ("affiliate_id", "affiliate_token", "api_base")
        return self.is_enabled() and all(self.config.get(field) for field in required)

    def search_products(self, query: str, result_count: int = 10) -> List[MarketplaceOffer]:
        if not self.is_configured():
            return []

        params = urlencode({"query": query, "resultCount": min(result_count, 10)})
        url = f"{self.config['api_base']}/search.json?{params}"
        request = Request(
            url=url,
            headers={
                "Fk-Affiliate-Id": self.config["affiliate_id"],
                "Fk-Affiliate-Token": self.config["affiliate_token"],
            },
            method="GET",
        )
        response = _read_json(request)
        products = response.get("productInfoList", [])
        offers: List[MarketplaceOffer] = []
        for item in products:
            base_info = item.get("productBaseInfoV1") or item
            current_price = _to_decimal(
                base_info.get("flipkartSpecialPrice")
                or base_info.get("flipkartSellingPrice")
                or base_info.get("sellingPrice")
            )
            if not current_price:
                continue
            image_urls = base_info.get("imageUrls") or {}
            image_url = ""
            if isinstance(image_urls, dict):
                image_url = image_urls.get("400x400") or image_urls.get("200x200") or next(iter(image_urls.values()), "")
            offers.append(
                MarketplaceOffer(
                    platform_name=self.platform_name,
                    title=base_info.get("title", ""),
                    external_id=str(base_info.get("productId", "")),
                    description=base_info.get("productDescription", ""),
                    category=base_info.get("categoryPath", ""),
                    brand=base_info.get("productBrand", ""),
                    image_url=image_url or base_info.get("imageUrl", ""),
                    product_url=base_info.get("productUrl", ""),
                    seller_name=self.platform_name,
                    price=current_price,
                    original_price=_to_decimal(base_info.get("maximumRetailPrice") or base_info.get("mrp")),
                    shipping_cost=Decimal("0.00"),
                    delivery_time="Flipkart affiliate listing",
                    availability_status=bool(base_info.get("inStock", True)),
                )
            )
        return offers


def get_marketplace_clients() -> List[BaseMarketplaceClient]:
    config = settings.MARKETPLACE_INTEGRATIONS
    return [
        AmazonMarketplaceClient(config["amazon"]),
        FlipkartMarketplaceClient(config["flipkart"]),
    ]


def search_marketplaces(query: str, result_count: int = 10) -> Tuple[List[MarketplaceOffer], List[str]]:
    offers: List[MarketplaceOffer] = []
    notes: List[str] = []
    for client in get_marketplace_clients():
        if not client.is_enabled():
            notes.append(f"{client.platform_name} is disabled.")
            continue
        if not client.is_configured():
            notes.append(f"{client.platform_name} is enabled but missing API credentials.")
            continue
        try:
            client_offers = client.search_products(query, result_count=result_count)
            offers.extend(client_offers)
            notes.append(f"{client.platform_name}: {len(client_offers)} offers fetched.")
        except HTTPError as exc:
            notes.append(f"{client.platform_name} request failed with HTTP {exc.code}.")
        except URLError:
            notes.append(f"{client.platform_name} request failed because the network was unavailable.")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{client.platform_name} request failed: {exc}.")
    return offers, notes
