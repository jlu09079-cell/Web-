from decimal import Decimal
import re

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.conf import settings
from django.db.models import Avg, F, Max, Min, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework import viewsets

from .forms import LoginForm, SignupForm
from .sync import sync_marketplace_query
from .models import ApiLog, Favorite, Platform, PriceAlert, Product, ProductPrice, SearchHistory, User
from .serializers import (
    ApiLogSerializer,
    FavoriteSerializer,
    PlatformSerializer,
    PriceAlertSerializer,
    ProductPriceSerializer,
    ProductSerializer,
    SearchHistorySerializer,
    UserSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer


class PlatformViewSet(viewsets.ModelViewSet):
    queryset = Platform.objects.all()
    serializer_class = PlatformSerializer


class ProductPriceViewSet(viewsets.ModelViewSet):
    queryset = ProductPrice.objects.select_related('product', 'platform').all()
    serializer_class = ProductPriceSerializer


class SearchHistoryViewSet(viewsets.ModelViewSet):
    queryset = SearchHistory.objects.select_related('user', 'clicked_product').all()
    serializer_class = SearchHistorySerializer


class ApiLogViewSet(viewsets.ModelViewSet):
    queryset = ApiLog.objects.select_related('platform').all()
    serializer_class = ApiLogSerializer


class FavoriteViewSet(viewsets.ModelViewSet):
    queryset = Favorite.objects.select_related('user', 'product').all()
    serializer_class = FavoriteSerializer


class PriceAlertViewSet(viewsets.ModelViewSet):
    queryset = PriceAlert.objects.select_related('user', 'product', 'target_platform').all()
    serializer_class = PriceAlertSerializer


SAMPLE_PRODUCTS = [
    {
        'title': 'Sony WH-1000XM5',
        'description': 'Wireless noise-cancelling headphones with adaptive sound control.',
        'category': 'Audio',
        'brand': 'Sony',
        'model_number': 'WH-1000XM5',
        'rating': 4.8,
        'review_count': 2481,
        'image_url': 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=80',
    },
    {
        'title': 'Apple Watch Series 9',
        'description': 'Health-focused smartwatch with bright display and all-day battery.',
        'category': 'Wearables',
        'brand': 'Apple',
        'model_number': 'S9-45MM',
        'rating': 4.7,
        'review_count': 1830,
        'image_url': 'https://images.unsplash.com/photo-1434494878577-86c23bcb06b9?auto=format&fit=crop&w=900&q=80',
    },
    {
        'title': 'MacBook Pro 16 M3 Pro',
        'description': 'High-performance laptop for creators and developers.',
        'category': 'Computers',
        'brand': 'Apple',
        'model_number': 'MBP16M3P',
        'rating': 4.9,
        'review_count': 963,
        'image_url': 'https://images.unsplash.com/photo-1517336714739-489689fd1ca8?auto=format&fit=crop&w=900&q=80',
    },
]

SAMPLE_PRICES = {
    'Sony WH-1000XM5': [
        ('Amazon', Decimal('24999.00'), Decimal('0.00'), Decimal('32999.00'), 'Free next day', 'https://www.amazon.in/'),
        ('Best Buy', Decimal('26499.00'), Decimal('0.00'), Decimal('32999.00'), 'Pickup today', 'https://www.bestbuy.com/'),
        ('Flipkart', Decimal('25999.00'), Decimal('199.00'), Decimal('32999.00'), '2 day shipping', 'https://www.flipkart.com/'),
    ],
    'Apple Watch Series 9': [
        ('Amazon', Decimal('32999.00'), Decimal('0.00'), Decimal('38999.00'), 'Free next day', 'https://www.amazon.in/'),
        ('Best Buy', Decimal('33999.00'), Decimal('0.00'), Decimal('38999.00'), 'Free shipping', 'https://www.bestbuy.com/'),
        ('Flipkart', Decimal('33499.00'), Decimal('149.00'), Decimal('38999.00'), '3 day shipping', 'https://www.flipkart.com/'),
    ],
    'MacBook Pro 16 M3 Pro': [
        ('Amazon', Decimal('189999.00'), Decimal('0.00'), Decimal('209999.00'), 'Free next day', 'https://www.amazon.in/'),
        ('Best Buy', Decimal('193999.00'), Decimal('0.00'), Decimal('209999.00'), 'Store pickup', 'https://www.bestbuy.com/'),
        ('Flipkart', Decimal('191499.00'), Decimal('499.00'), Decimal('209999.00'), '4 day shipping', 'https://www.flipkart.com/'),
    ],
}


def ensure_sample_data():
    user, _ = User.objects.get_or_create(
        email='alex@example.com',
        defaults={
            'name': 'Alex Curator',
            'password_hash': make_password('demo-password'),
            'role': 'admin',
            'location': 'Bengaluru',
            'subscription_type': 'Premium',
        },
    )
    if not user.password_hash.startswith('pbkdf2_'):
        user.password_hash = make_password(user.password_hash)
        user.save(update_fields=['password_hash'])

    platform_map = {}
    for name, platform_type in [('Amazon', 'Marketplace'), ('Best Buy', 'Retail'), ('Flipkart', 'Marketplace')]:
        platform_map[name], _ = Platform.objects.get_or_create(
            name=name,
            defaults={'platform_type': platform_type, 'request_limit': 1000, 'status': True},
        )

    product_map = {}
    for product_data in SAMPLE_PRODUCTS:
        product, _ = Product.objects.get_or_create(
            title=product_data['title'],
            defaults=product_data,
        )
        product_map[product.title] = product

    for product_title, price_rows in SAMPLE_PRICES.items():
        product = product_map[product_title]
        for platform_name, price, shipping_cost, original_price, delivery_time, product_url in price_rows:
            discount_percentage = float(round(((original_price - price) / original_price) * 100, 2)) if original_price else None
            ProductPrice.objects.update_or_create(
                product=product,
                platform=platform_map[platform_name],
                seller_name=platform_name,
                defaults={
                    'price': price,
                    'shipping_cost': shipping_cost,
                    'original_price': original_price,
                    'discount_percentage': discount_percentage,
                    'availability_status': True,
                    'delivery_time': delivery_time,
                    'product_url': product_url,
                },
            )

    sony = product_map['Sony WH-1000XM5']
    watch = product_map['Apple Watch Series 9']
    macbook = product_map['MacBook Pro 16 M3 Pro']

    Favorite.objects.get_or_create(user=user, product=sony)
    Favorite.objects.get_or_create(user=user, product=watch)

    PriceAlert.objects.update_or_create(
        user=user,
        product=sony,
        target_platform=platform_map['Amazon'],
        defaults={
            'target_price': Decimal('22999.00'),
            'notification_frequency': 'instant',
            'notes': 'Notify on any new low.',
        },
    )
    PriceAlert.objects.update_or_create(
        user=user,
        product=macbook,
        target_platform=platform_map['Best Buy'],
        defaults={
            'target_price': Decimal('185000.00'),
            'notification_frequency': 'daily',
            'notes': 'Track workstation deals.',
        },
    )

    if not SearchHistory.objects.exists():
        SearchHistory.objects.create(user=user, query='Sony WH-1000XM5', category='Audio', result_count=3, clicked_product=sony)
        SearchHistory.objects.create(user=user, query='MacBook Pro 16 M3 Pro', category='Computers', result_count=3, clicked_product=macbook)
        SearchHistory.objects.create(user=user, query='Apple Watch Series 9', category='Wearables', result_count=3, clicked_product=watch)

    if not ApiLog.objects.exists():
        ApiLog.objects.create(platform=platform_map['Amazon'], request_status='200 OK', response_time=118.0, request_count=412)
        ApiLog.objects.create(platform=platform_map['Best Buy'], request_status='200 OK', response_time=146.0, request_count=287)
        ApiLog.objects.create(platform=platform_map['Flipkart'], request_status='429 Retry', response_time=34.0, request_count=92, error_message='Rate limit reached')

    return user


def decorate_products(products):
    items = list(products)
    for product in items:
        offers = list(product.prices.select_related('platform').order_by('price'))
        product.offer_count = len(offers)
        product.best_offer_cached = offers[0] if offers else None
    return items


def _comparison_keywords(product):
    source = " ".join(
        filter(
            None,
            [
                product.brand or "",
                product.model_number or "",
                product.title or "",
            ],
        )
    ).lower()
    words = re.findall(r"[a-z0-9]+", source)
    ignored = {"green", "blue", "black", "white", "storage", "gb", "general"}
    return [word for word in words if word not in ignored][:4]


def get_comparison_offers(product):
    offers_qs = ProductPrice.objects.select_related("product", "platform")
    keywords = _comparison_keywords(product)
    related_prices = offers_qs.none()

    if product.brand and product.model_number:
        related_prices = offers_qs.filter(
            product__brand__iexact=product.brand,
            product__model_number__iexact=product.model_number,
        )

    if not related_prices.exists() and keywords:
        title_filter = Q()
        for keyword in keywords:
            title_filter &= Q(product__title__icontains=keyword)
        related_prices = offers_qs.filter(title_filter)

    if not related_prices.exists():
        related_prices = offers_qs.filter(product=product)

    deduped = []
    seen = set()
    for offer in related_prices.order_by("price", "platform__name", "product__title"):
        key = (offer.platform_id, offer.seller_name or offer.platform.name, offer.product_url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(offer)
    return deduped


def common_context(active_page='dashboard'):
    demo_user = ensure_sample_data()
    return {
        'active_page': active_page,
        'demo_user': demo_user,
        'platform_count': Platform.objects.count(),
        'product_count': Product.objects.count(),
        'alert_count': PriceAlert.objects.filter(user=demo_user).count(),
    }


def get_current_user(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    return User.objects.filter(user_id=user_id, account_status=True).first()


def base_context(request, active_page='dashboard'):
    context = common_context(active_page=active_page)
    current_user = get_current_user(request)
    context['current_user'] = current_user
    context['is_authenticated'] = current_user is not None
    if current_user:
        context['alert_count'] = PriceAlert.objects.filter(user=current_user).count()
    return context


def login_required_custom(view_func):
    def wrapped(request, *args, **kwargs):
        if not get_current_user(request):
            messages.info(request, 'Please login to continue.')
            return redirect('login')
        return view_func(request, *args, **kwargs)

    return wrapped


def home_page(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.prefetch_related('prices__platform').all()
    if query:
        products = products.filter(
            Q(title__icontains=query) |
            Q(category__icontains=query) |
            Q(brand__icontains=query)
        )
        current_user = get_current_user(request)
        if current_user:
            SearchHistory.objects.create(user=current_user, query=query, result_count=products.count())
    featured_products = decorate_products(products[:6])
    context = {
        **base_context(request, active_page='home'),
        'page_title': 'Price Snap Home',
        'featured_products': featured_products,
        'search_query': query,
    }
    return render(request, 'index.html', context)


def product_list_page(request):
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    sync_notes = []
    synced_count = 0
    current_user = get_current_user(request)
    if query:
        synced_count, sync_notes = sync_marketplace_query(query, result_count=10)
        if current_user:
            SearchHistory.objects.create(user=current_user, query=query, category=category or None)
    products = Product.objects.prefetch_related('prices__platform').all()
    if query:
        products = products.filter(Q(title__icontains=query) | Q(brand__icontains=query))
    if category:
        products = products.filter(category__iexact=category)
    context = {
        **base_context(request, active_page='products'),
        'page_title': 'All Products',
        'products': decorate_products(products),
        'selected_category': category,
        'search_query': query,
        'categories': Product.objects.exclude(category__isnull=True).exclude(category='').values_list('category', flat=True).distinct(),
        'sync_notes': sync_notes,
        'synced_count': synced_count,
        'marketplace_ready': synced_count > 0,
        'show_marketplace_setup_notice': bool(query) and synced_count == 0,
    }
    return render(request, 'productli.html', context)


def product_detail_page(request, product_id):
    product = get_object_or_404(Product.objects.prefetch_related('prices__platform'), pk=product_id)
    current_user = get_current_user(request)
    offers = list(product.prices.select_related('platform').order_by('price'))
    best_offer = offers[0] if offers else None
    if current_user:
        SearchHistory.objects.create(
            user=current_user,
            query=product.title,
            category=product.category,
            result_count=len(offers),
            clicked_product=product,
        )
    related_products = decorate_products(
        Product.objects.exclude(pk=product.pk).filter(category=product.category).prefetch_related('prices__platform')[:3]
    )
    context = {
        **base_context(request, active_page='products'),
        'page_title': product.title,
        'product': product,
        'offers': offers,
        'best_offer': best_offer,
        'related_products': related_products,
        'average_price': offers and sum(offer.total_price for offer in offers) / len(offers) or None,
        'is_favorite': current_user and Favorite.objects.filter(user=current_user, product=product).exists(),
        'existing_alert': current_user and PriceAlert.objects.filter(user=current_user, product=product, alert_status=True).first(),
    }
    return render(request, 'productdetail.html', context)


def product_compare_page(request, product_id):
    product = get_object_or_404(Product.objects.prefetch_related('prices__platform'), pk=product_id)
    sync_marketplace_query(product.title, result_count=12)
    product.refresh_from_db()
    offers = get_comparison_offers(product)
    best_offer = offers[0] if offers else None
    context = {
        **base_context(request, active_page='products'),
        'page_title': f'Compare {product.title}',
        'product': product,
        'offers': offers,
        'best_offer': best_offer,
        'comparison_count': len(offers),
    }
    return render(request, 'pricecomparision.html', context)


@login_required_custom
def dashboard_page(request):
    current_user = get_current_user(request)
    favorite_products = [favorite.product for favorite in Favorite.objects.filter(user=current_user).select_related('product')]
    recent_searches = SearchHistory.objects.filter(user=current_user).select_related('clicked_product')[:5]
    best_price = ProductPrice.objects.aggregate(best=Min('price'))['best']
    highest_discount = ProductPrice.objects.aggregate(best=Max('discount_percentage'))['best']
    context = {
        **base_context(request, active_page='dashboard'),
        'page_title': 'Dashboard',
        'favorite_products': decorate_products(favorite_products),
        'recent_searches': recent_searches,
        'tracked_items': Product.objects.count(),
        'total_savings': ProductPrice.objects.aggregate(saved=Sum(F('original_price') - F('price')))['saved'] or Decimal('0.00'),
        'best_price': best_price,
        'highest_discount': highest_discount,
    }
    return render(request, 'dash.html', context)


@login_required_custom
def favorites_page(request):
    current_user = get_current_user(request)
    favorites = list(Favorite.objects.filter(user=current_user).select_related('product'))
    for favorite in favorites:
        favorite.best_offer = favorite.product.best_offer
    context = {
        **base_context(request, active_page='favorites'),
        'page_title': 'Favorites',
        'favorites': favorites,
    }
    return render(request, 'favpage.html', context)


@login_required_custom
def price_alerts_page(request):
    current_user = get_current_user(request)
    alerts = list(PriceAlert.objects.filter(user=current_user).select_related('product', 'target_platform'))
    for alert in alerts:
        alert.current_offer = alert.product.best_offer
        if alert.current_offer:
            alert.is_reached = alert.current_offer.price <= alert.target_price
    context = {
        **base_context(request, active_page='alerts'),
        'page_title': 'Price Alerts',
        'alerts': alerts,
    }
    return render(request, 'pricealert.html', context)


@login_required_custom
def history_page(request):
    current_user = get_current_user(request)
    history = SearchHistory.objects.filter(user=current_user).select_related('clicked_product')
    context = {
        **base_context(request, active_page='history'),
        'page_title': 'Search History',
        'history_items': history,
        'search_count': history.count(),
    }
    return render(request, 'searchhistory.html', context)


@login_required_custom
def settings_page(request):
    api_logs = ApiLog.objects.select_related('platform')[:6]
    serpapi_config = settings.MARKETPLACE_INTEGRATIONS.get('serpapi', {})
    summary = {
        'monthly_revenue': 'Rs. 42,89,000',
        'active_users': User.objects.filter(account_status=True).count(),
        'searches': SearchHistory.objects.count(),
        'avg_response': round(ApiLog.objects.aggregate(avg=Avg('response_time'))['avg'] or 0, 1),
    }
    context = {
        **base_context(request, active_page='settings'),
        'page_title': 'Settings',
        'api_logs': api_logs,
        'summary': summary,
        'serpapi_status': {
            'env_file_exists': (settings.BASE_DIR / '.env').exists(),
            'enabled': bool(serpapi_config.get('enabled')),
            'key_present': bool(serpapi_config.get('api_key')),
            'google_domain': serpapi_config.get('google_domain', ''),
            'location': serpapi_config.get('location', ''),
            'gl': serpapi_config.get('gl', ''),
            'hl': serpapi_config.get('hl', ''),
            'amazon_domain': serpapi_config.get('amazon_domain', ''),
        },
    }
    return render(request, 'admin.html', context)


def login_page(request):
    if get_current_user(request):
        return redirect('dashboard')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        user = User.objects.filter(email=email, account_status=True).first()
        if user and check_password(password, user.password_hash):
            request.session['user_id'] = str(user.user_id)
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            messages.success(request, 'Welcome back.')
            return redirect('dashboard')
        messages.error(request, 'Invalid email or password.')

    context = {
        **base_context(request, active_page='login'),
        'page_title': 'Login',
        'form': form,
    }
    return render(request, 'login.html', context)


def signup_page(request):
    if get_current_user(request):
        return redirect('dashboard')

    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            form.add_error('email', 'An account with this email already exists.')
        else:
            user = User.objects.create(
                name=form.cleaned_data['name'],
                email=email,
                password_hash=make_password(form.cleaned_data['password']),
                location=form.cleaned_data.get('location') or None,
                role='user',
                subscription_type='Free',
                account_status=True,
            )
            request.session['user_id'] = str(user.user_id)
            messages.success(request, 'Account created successfully.')
            return redirect('dashboard')

    context = {
        **base_context(request, active_page='signup'),
        'page_title': 'Sign Up',
        'form': form,
    }
    return render(request, 'signup.html', context)


def logout_page(request):
    request.session.pop('user_id', None)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


@login_required_custom
def add_favorite_page(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    current_user = get_current_user(request)
    Favorite.objects.get_or_create(user=current_user, product=product)
    messages.success(request, f'{product.title} was added to your favorites.')
    return redirect('product_detail', product_id=product.product_id)


@login_required_custom
def create_alert_page(request, product_id):
    product = get_object_or_404(Product.objects.prefetch_related('prices__platform'), pk=product_id)
    current_user = get_current_user(request)
    best_offer = product.best_offer
    if not best_offer:
        messages.error(request, 'No live offer is available yet for this product.')
        return redirect('product_detail', product_id=product.product_id)

    target_price = request.POST.get('target_price')
    try:
        target_price_value = Decimal(target_price) if target_price else max(best_offer.price - Decimal('1000.00'), Decimal('1.00'))
    except Exception:  # noqa: BLE001
        target_price_value = max(best_offer.price - Decimal('1000.00'), Decimal('1.00'))

    PriceAlert.objects.update_or_create(
        user=current_user,
        product=product,
        defaults={
            'target_platform': best_offer.platform,
            'target_price': target_price_value,
            'notification_frequency': 'instant',
            'notes': f'Created from product details for {product.title}.',
            'alert_status': True,
        },
    )
    messages.success(request, f'Price alert created for {product.title}.')
    return redirect('alerts')
