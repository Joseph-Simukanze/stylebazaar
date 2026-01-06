from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from admin_panel.admin import admin_site, seller_admin_site

urlpatterns = [
    # Default Django admin
    path('admin/', admin.site.urls),

    # Custom admin panels
    path('custom-admin/', admin_site.urls),       # Renamed to avoid conflict with 'admin/'
    path('seller-admin/', seller_admin_site.urls),

    # Home page / core app
    path('', include('core.urls')),

    # Users
    path('users/', include('users.urls')),

    # Products
    path('products/', include('products.urls', namespace='products')),

    # Cart
    path('cart/', include('cart.urls')),

    # Orders
    path('orders/', include('orders.urls', namespace='orders')),

    # Payments
    path('payments/', include('payments.urls', namespace='payments')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
