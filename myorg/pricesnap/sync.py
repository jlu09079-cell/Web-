from decimal import Decimal

from django.utils import timezone

from .marketplaces import MarketplaceOffer, search_marketplaces
from .models import ApiLog, Platform, Product, ProductPrice


def _safe_price(value):
    return value if value is not None else Decimal("0.00")


def _infer_brand(title: str, brand: str) -> str:
    if brand:
        return brand
    if not title:
        return ""
    first_word = title.split()[0]
    return first_word.title()


def _infer_category(title: str, category: str) -> str:
    if category:
        return category
    lowered = title.lower()
    if "iphone" in lowered or "phone" in lowered or "smartphone" in lowered:
        return "Smartphones"
    if "headphone" in lowered or "earbud" in lowered:
        return "Audio"
    if "watch" in lowered:
        return "Wearables"
    if "macbook" in lowered or "laptop" in lowered:
        return "Computers"
    return "General"


def _infer_model_number(title: str) -> str:
    if not title:
        return ""
    tokens = [token.strip("(),") for token in title.split()]
    for token in tokens:
        upper = token.upper()
        if any(ch.isdigit() for ch in upper) and len(upper) <= 20:
            return upper
    return ""


def upsert_marketplace_offer(offer: MarketplaceOffer):
    platform, _ = Platform.objects.get_or_create(
        name=offer.platform_name,
        defaults={
            "platform_type": "Marketplace API",
            "status": True,
            "api_endpoint": offer.product_url or "",
        },
    )
    if offer.product_url and not platform.api_endpoint:
        platform.api_endpoint = offer.product_url
        platform.save(update_fields=["api_endpoint"])

    product, _ = Product.objects.get_or_create(
        title=offer.title,
        defaults={
            "description": offer.description or offer.title,
            "category": _infer_category(offer.title, offer.category),
            "brand": _infer_brand(offer.title, offer.brand),
            "model_number": _infer_model_number(offer.title),
            "rating": offer.rating,
            "review_count": offer.review_count or 0,
            "image_url": offer.image_url or "",
        },
    )

    updated_fields = []
    for field, value in (
        ("description", offer.description or offer.title),
        ("category", _infer_category(offer.title, offer.category)),
        ("brand", _infer_brand(offer.title, offer.brand)),
        ("model_number", _infer_model_number(offer.title)),
        ("rating", offer.rating),
        ("review_count", offer.review_count or 0),
        ("image_url", offer.image_url),
    ):
        if value and not getattr(product, field):
            setattr(product, field, value)
            updated_fields.append(field)
    if updated_fields:
        product.save(update_fields=updated_fields)

    ProductPrice.objects.update_or_create(
        product=product,
        platform=platform,
        seller_name=offer.seller_name or offer.platform_name,
        defaults={
            "price": _safe_price(offer.price),
            "original_price": offer.original_price,
            "shipping_cost": _safe_price(offer.shipping_cost),
            "availability_status": offer.availability_status,
            "product_url": offer.product_url,
            "delivery_time": offer.delivery_time,
            "discount_percentage": _discount_percentage(offer.original_price, offer.price),
        },
    )


def _discount_percentage(original_price, current_price):
    if not original_price or not current_price or original_price == 0:
        return None
    return float(round(((original_price - current_price) / original_price) * 100, 2))


def sync_marketplace_query(query: str, result_count: int = 10):
    offers, notes = search_marketplaces(query, result_count=result_count)
    synced = 0
    for offer in offers:
        upsert_marketplace_offer(offer)
        platform = Platform.objects.get(name=offer.platform_name)
        ApiLog.objects.create(
            platform=platform,
            request_status=offer.request_status,
            response_time=None,
            request_count=1,
            timestamp=timezone.now(),
        )
        synced += 1
    return synced, notes
