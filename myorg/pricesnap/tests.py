from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from .marketplaces import MarketplaceOffer
from .models import Favorite, Platform, PriceAlert, Product, ProductPrice, SearchHistory, User
from .sync import upsert_marketplace_offer
from .views import get_comparison_offers


class SmokeTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_product_list_loads(self):
        response = self.client.get(reverse("product_list"))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_loads(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("login"))

    def test_signup_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("signup"),
            {
                "name": "Test User",
                "email": "test@example.com",
                "location": "Chennai",
                "password": "strongpass123",
                "confirm_password": "strongpass123",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email="test@example.com").exists())
        self.assertContains(response, "Today's snapshot")

    def test_login_works_for_existing_user(self):
        User.objects.create(
            name="Existing User",
            email="existing@example.com",
            password_hash=make_password("strongpass123"),
            subscription_type="Free",
        )
        response = self.client.post(
            reverse("login"),
            {
                "email": "existing@example.com",
                "password": "strongpass123",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Today's snapshot")

    @patch("pricesnap.views.sync_marketplace_query", return_value=(0, ["SerpApi integration is disabled."]))
    def test_product_search_shows_sync_notes(self, mocked_sync):
        response = self.client.get(reverse("product_list"), {"q": "laptop"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connect SerpApi")
        self.assertContains(response, "Live products are available after you add your SerpApi key")
        mocked_sync.assert_called_once_with("laptop", result_count=10)

    def test_upsert_marketplace_offer_creates_records(self):
        offer = MarketplaceOffer(
            platform_name="Flipkart",
            title="Test Laptop",
            external_id="flipkart-123",
            description="Gaming laptop",
            category="Computers",
            brand="BrandX",
            image_url="https://example.com/laptop.jpg",
            product_url="https://example.com/laptop",
            seller_name="Flipkart",
            price=Decimal("999.00"),
            original_price=Decimal("1299.00"),
            shipping_cost=Decimal("0.00"),
            delivery_time="2 days",
            availability_status=True,
        )
        upsert_marketplace_offer(offer)
        self.assertTrue(Product.objects.filter(title="Test Laptop").exists())
        self.assertTrue(ProductPrice.objects.filter(product__title="Test Laptop", platform__name="Flipkart").exists())

    def test_add_favorite_and_alert_and_history_from_product_detail(self):
        user = User.objects.create(
            name="Action User",
            email="action@example.com",
            password_hash=make_password("strongpass123"),
            subscription_type="Free",
        )
        product = Product.objects.create(
            title="Action Phone 17",
            brand="Action",
            category="Smartphones",
            description="Phone for action tests",
        )
        offer = MarketplaceOffer(
            platform_name="Amazon",
            title="Action Phone 17",
            external_id="action-17",
            seller_name="Amazon",
            price=Decimal("99999.00"),
            original_price=Decimal("109999.00"),
            shipping_cost=Decimal("0.00"),
            product_url="https://example.com/action17",
        )
        upsert_marketplace_offer(offer)
        session = self.client.session
        session["user_id"] = str(user.user_id)
        session.save()

        detail_response = self.client.get(reverse("product_detail", args=[product.product_id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertTrue(SearchHistory.objects.filter(user=user, clicked_product=product).exists())

        favorite_response = self.client.post(reverse("add_favorite", args=[product.product_id]), follow=True)
        self.assertEqual(favorite_response.status_code, 200)
        self.assertTrue(Favorite.objects.filter(user=user, product=product).exists())

        alert_response = self.client.post(reverse("create_alert", args=[product.product_id]), follow=True)
        self.assertEqual(alert_response.status_code, 200)
        self.assertTrue(PriceAlert.objects.filter(user=user, product=product).exists())

    def test_compare_groups_matching_brand_and_model(self):
        primary = Product.objects.create(
            title="Apple iPhone 17 512GB",
            brand="Apple",
            model_number="17",
            category="Smartphones",
        )
        related = Product.objects.create(
            title="Apple iPhone 17 Green 512GB",
            brand="Apple",
            model_number="17",
            category="Smartphones",
        )
        amazon = Platform.objects.create(name="Amazon Compare")
        flipkart = Platform.objects.create(name="Flipkart Compare")
        ProductPrice.objects.create(product=primary, platform=amazon, seller_name="Amazon Compare", price=Decimal("99999.00"))
        ProductPrice.objects.create(product=related, platform=flipkart, seller_name="Flipkart Compare", price=Decimal("97999.00"))

        offers = get_comparison_offers(primary)
        self.assertEqual(len(offers), 2)
