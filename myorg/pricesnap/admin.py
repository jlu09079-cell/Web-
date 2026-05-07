from django.contrib import admin

from .models import ApiLog, Favorite, Platform, PriceAlert, Product, ProductPrice, SearchHistory, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'role', 'subscription_type', 'account_status', 'created_at')
    search_fields = ('name', 'email')
    list_filter = ('role', 'subscription_type', 'account_status')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'brand', 'category', 'rating', 'review_count', 'created_at')
    search_fields = ('title', 'brand', 'category')
    list_filter = ('category', 'brand')


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ('name', 'platform_type', 'status', 'request_limit', 'last_sync')
    list_filter = ('status', 'platform_type')
    search_fields = ('name',)


@admin.register(ProductPrice)
class ProductPriceAdmin(admin.ModelAdmin):
    list_display = ('product', 'platform', 'price', 'shipping_cost', 'availability_status', 'last_updated')
    list_filter = ('availability_status', 'platform')
    search_fields = ('product__title', 'platform__name', 'seller_name')


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ('query', 'user', 'result_count', 'clicked_product', 'timestamp')
    search_fields = ('query', 'user__email')


@admin.register(ApiLog)
class ApiLogAdmin(admin.ModelAdmin):
    list_display = ('platform', 'request_status', 'response_time', 'request_count', 'timestamp')
    list_filter = ('request_status', 'platform')


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'added_date')
    search_fields = ('user__email', 'product__title')


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'target_platform', 'target_price', 'notification_frequency', 'alert_status')
    list_filter = ('alert_status', 'notification_frequency')
    search_fields = ('user__email', 'product__title')
