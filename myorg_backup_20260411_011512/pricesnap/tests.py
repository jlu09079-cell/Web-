from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from .marketplaces import MarketplaceOffer
from .models import Product, ProductPrice, User
from .sync import upsert_marketplace_offer


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

    @patch("pricesnap.views.sync_marketplace_query", return_value=(0, ["Amazon is disabled.", "Flipkart is disabled."]))
    def test_product_search_shows_sync_notes(self, mocked_sync):
        response = self.client.get(reverse("product_list"), {"q": "laptop"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Marketplace sync")
        self.assertContains(response, "Amazon is disabled.")
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
