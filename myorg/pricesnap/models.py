import uuid

from django.db import models


class User(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('admin', 'Admin'),
    )
    SUBSCRIPTION_CHOICES = (
        ('Free', 'Free'),
        ('Premium', 'Premium'),
    )

    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password_hash = models.TextField()
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    subscription_type = models.CharField(max_length=10, choices=SUBSCRIPTION_CHOICES, default='Free')
    account_status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.email


class Product(models.Model):
    product_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    model_number = models.CharField(max_length=100, blank=True, null=True)
    rating = models.FloatField(blank=True, null=True)
    review_count = models.IntegerField(default=0)
    image_url = models.TextField(blank=True, null=True)
    launch_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    @property
    def best_offer(self):
        return self.prices.order_by('price').select_related('platform').first()


class Platform(models.Model):
    platform_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    api_endpoint = models.TextField(blank=True, null=True)
    api_key = models.TextField(blank=True, null=True)
    request_limit = models.IntegerField(blank=True, null=True)
    status = models.BooleanField(default=True)
    last_sync = models.DateTimeField(blank=True, null=True)
    platform_type = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ProductPrice(models.Model):
    price_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='prices')
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, related_name='product_prices')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_percentage = models.FloatField(blank=True, null=True)
    availability_status = models.BooleanField(default=True)
    seller_name = models.CharField(max_length=150, blank=True, null=True)
    product_url = models.TextField(blank=True, null=True)
    delivery_time = models.CharField(max_length=100, blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['price']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'platform', 'seller_name'],
                name='unique_product_platform_seller',
            )
        ]

    def __str__(self):
        return f'{self.product.title} - {self.platform.name}'

    @property
    def total_price(self):
        return self.price + self.shipping_cost


class SearchHistory(models.Model):
    search_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='searches', blank=True, null=True)
    query = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True, null=True)
    result_count = models.IntegerField(blank=True, null=True)
    clicked_product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='search_clicks',
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return self.query


class ApiLog(models.Model):
    log_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, related_name='api_logs')
    request_status = models.CharField(max_length=50)
    response_time = models.FloatField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    request_count = models.IntegerField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.platform.name} - {self.request_status}'


class Favorite(models.Model):
    fav_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='favorited_by')
    added_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-added_date']
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name='unique_favorite_per_user')
        ]

    def __str__(self):
        return f'{self.user.email} - {self.product.title}'


class PriceAlert(models.Model):
    FREQUENCY_CHOICES = (
        ('instant', 'Instant'),
        ('daily', 'Daily'),
    )

    alert_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_alerts')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_alerts')
    target_platform = models.ForeignKey(
        Platform,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='price_alerts',
    )
    target_price = models.DecimalField(max_digits=10, decimal_places=2)
    notification_frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='instant')
    notes = models.CharField(max_length=255, blank=True, null=True)
    alert_status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_triggered = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Alert for {self.product.title}'
