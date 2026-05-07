from rest_framework import serializers

from .models import ApiLog, Favorite, Platform, PriceAlert, Product, ProductPrice, SearchHistory, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'


class PlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = Platform
        fields = '__all__'


class ProductPriceSerializer(serializers.ModelSerializer):
    platform_name = serializers.CharField(source='platform.name', read_only=True)
    product_title = serializers.CharField(source='product.title', read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = ProductPrice
        fields = '__all__'


class ProductSerializer(serializers.ModelSerializer):
    best_offer = ProductPriceSerializer(read_only=True)

    class Meta:
        model = Product
        fields = '__all__'


class SearchHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchHistory
        fields = '__all__'


class ApiLogSerializer(serializers.ModelSerializer):
    platform_name = serializers.CharField(source='platform.name', read_only=True)

    class Meta:
        model = ApiLog
        fields = '__all__'


class FavoriteSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source='product.title', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Favorite
        fields = '__all__'


class PriceAlertSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source='product.title', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    target_platform_name = serializers.CharField(source='target_platform.name', read_only=True)

    class Meta:
        model = PriceAlert
        fields = '__all__'
