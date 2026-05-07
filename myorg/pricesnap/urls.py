from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ApiLogViewSet,
    FavoriteViewSet,
    PriceAlertViewSet,
    PlatformViewSet,
    ProductPriceViewSet,
    ProductViewSet,
    SearchHistoryViewSet,
    UserViewSet,
    add_favorite_page,
    dashboard_page,
    favorites_page,
    history_page,
    home_page,
    login_page,
    create_alert_page,
    logout_page,
    price_alerts_page,
    product_compare_page,
    product_detail_page,
    product_list_page,
    settings_page,
    signup_page,
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'products', ProductViewSet)
router.register(r'platforms', PlatformViewSet)
router.register(r'product-prices', ProductPriceViewSet)
router.register(r'search-history', SearchHistoryViewSet)
router.register(r'api-logs', ApiLogViewSet)
router.register(r'favorites', FavoriteViewSet)
router.register(r'price-alerts', PriceAlertViewSet)

urlpatterns = [
    path('', home_page, name='home'),
    path('products/', product_list_page, name='product_list'),
    path('products/<uuid:product_id>/', product_detail_page, name='product_detail'),
    path('products/<uuid:product_id>/compare/', product_compare_page, name='product_compare'),
    path('products/<uuid:product_id>/favorite/', add_favorite_page, name='add_favorite'),
    path('products/<uuid:product_id>/alert/', create_alert_page, name='create_alert'),
    path('dashboard/', dashboard_page, name='dashboard'),
    path('favorites/', favorites_page, name='favorites'),
    path('alerts/', price_alerts_page, name='alerts'),
    path('history/', history_page, name='history'),
    path('settings/', settings_page, name='settings_page'),
    path('login/', login_page, name='login'),
    path('signup/', signup_page, name='signup'),
    path('logout/', logout_page, name='logout'),
    path('api/', include(router.urls)),
]
