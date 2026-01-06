import csv
from datetime import timedelta
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from django.db.models import Sum, F, FloatField
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from products.models import Product, Category, Promotion, ProductImage
from orders.models import Order, OrderItem, Coupon, DeliveryOption
from users.models import Profile, Wishlist, Address, Review, ReviewVote, Notification
from payments.models import Payment, PaymentMethod, MobileMoneyProvider, SavedPaymentMethod

User = get_user_model()


# ========================
# MAIN ADMIN SITE (STAFF/SUPERUSER)
# ========================
class StyleBazaarAdminSite(admin.AdminSite):
    site_header = "Style Bazaar - Admin Dashboard"
    site_title = "Style Bazaar Admin"
    index_title = "Welcome to Your Marketplace"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        now = timezone.now()
        twelve_months_ago = now - timedelta(days=365)

        # Stats
        total_users = User.objects.count()
        total_sellers = User.objects.filter(role='seller').count()
        total_products = Product.objects.count()
        pending_products = Product.objects.filter(is_approved=False).count()
        total_orders = Order.objects.count()
        paid_orders = Order.objects.filter(is_paid=True).count()

        # Revenue
        revenue_agg = OrderItem.objects.filter(order__is_paid=True).aggregate(
            total=Sum(F('price') * F('quantity'), output_field=FloatField())
        )
        total_revenue = revenue_agg['total'] or 0

        # Recent Orders
        recent_orders = Order.objects.select_related('buyer').order_by('-created_at')[:10]

        # Monthly Revenue Chart Data
        monthly_revenue = OrderItem.objects.filter(
            order__is_paid=True,
            order__created_at__gte=twelve_months_ago
        ).annotate(
            month=TruncMonth('order__created_at')
        ).values('month').annotate(
            revenue=Sum(F('price') * F('quantity'), output_field=FloatField())
        ).order_by('month')

        monthly_labels = []
        monthly_data = []
        current = twelve_months_ago.replace(day=1)
        for _ in range(12):
            month_str = current.strftime('%b %Y')
            monthly_labels.append(month_str)
            found = next((item for item in monthly_revenue if item['month'].strftime('%b %Y') == month_str), None)
            monthly_data.append(float(found['revenue'] or 0) if found else 0.0)
            current = (current + timedelta(days=32)).replace(day=1)

        extra_context.update({
            'total_users': total_users,
            'total_sellers': total_sellers,
            'total_products': total_products,
            'pending_approval': pending_products,
            'total_orders': total_orders,
            'paid_orders': paid_orders,
            'total_revenue': total_revenue,
            'recent_orders': recent_orders,
            'monthly_labels': monthly_labels,
            'monthly_data': monthly_data,
        })

        return super().index(request, extra_context)


admin_site = StyleBazaarAdminSite(name='main_admin')
admin.site = admin_site  # Replace default site globally (optional, but common)


# ========================
# SELLER-ONLY LIMITED ADMIN
# ========================
class SellerAdminSite(admin.AdminSite):
    site_header = "My Shop Dashboard - Style Bazaar"
    site_title = "Seller Dashboard"
    index_title = ""

    def has_permission(self, request):
        return request.user.is_authenticated and request.user.is_seller

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        seller = request.user

        products_count = Product.objects.filter(seller=seller).count()
        active_products = Product.objects.filter(seller=seller, is_active=True, is_approved=True).count()
        pending_approval = Product.objects.filter(seller=seller, is_approved=False).count()

        revenue_agg = OrderItem.objects.filter(
            product__seller=seller,
            order__is_paid=True
        ).aggregate(total=Sum(F('price') * F('quantity')))
        total_earnings = revenue_agg['total'] or 0

        recent_orders = Order.objects.filter(
            items__product__seller=seller
        ).select_related('buyer').distinct().order_by('-created_at')[:10]

        extra_context.update({
            'products_count': products_count,
            'active_products': active_products,
            'pending_approval': pending_approval,
            'total_earnings': total_earnings,
            'recent_orders': recent_orders,
        })

        return super().index(request, extra_context)


seller_admin_site = SellerAdminSite(name='seller_admin')
seller_admin_site.index_template = 'admin/seller_index.html'


# ========================
# INLINES
# ========================
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('product', 'price', 'quantity', 'get_total')
    readonly_fields = ('get_total',)

    def get_total(self, obj):
        if obj.pk:  # Only if saved
            return mark_safe(f'<strong>K{obj.get_total():.2f}</strong>')
        return 'K0.00'
    get_total.short_description = "Total"


# ========================
# MAIN ADMIN REGISTRATIONS
# ========================
@admin.register(User, site=admin_site)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'phone_number', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff', 'is_verified')
    search_fields = ('username', 'email', 'phone_number')
    readonly_fields = ('date_joined', 'last_login')


@admin.register(Product, site=admin_site)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'seller_link', 'category', 'current_price_display', 'stock', 'approval_status', 'is_active')
    list_filter = ('is_approved', 'is_active', 'category', 'seller')
    search_fields = ('name', 'slug', 'description', 'seller__username')
    inlines = [ProductImageInline]
    readonly_fields = ('created_at', 'updated_at')
    actions = ['approve_products', 'reject_products']

    def seller_link(self, obj):
        if not obj.seller:
            return "-"

        try:
            url = reverse(
                "main_admin:users_user_change",
                args=[obj.seller.pk],
            )
            return format_html('<a href="{}">{}</a>', url, obj.seller.username)
        except Exception:
            # Safety fallback (prevents admin crash)
            return obj.seller.username


    def current_price_display(self, obj):
        price = float(obj.current_price)
        return mark_safe(f'<strong>K{price:.2f} ZMW</strong>')
    current_price_display.short_description = "Current Price"

    def approval_status(self, obj):
        if obj.is_approved:
            return mark_safe('<span class="px-3 py-1 rounded-full bg-green-100 text-green-800 text-xs font-bold">Approved</span>')
        return mark_safe('<span class="px-3 py-1 rounded-full bg-yellow-100 text-yellow-800 text-xs font-bold">Pending</span>')
    approval_status.short_description = "Status"

    def approve_products(self, request, queryset):
        updated = 0
        for product in queryset.filter(is_approved=False):
            product.is_approved = True
            product.is_active = True
            product.save(update_fields=['is_approved', 'is_active'])
            updated += 1

            send_mail(
                subject="🎉 Your product has been approved!",
                message=f"Great news! Your product '{product.name}' is now live.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[product.seller.email],
                fail_silently=False,
            )
        self.message_user(request, f"{updated} product(s) approved and notified.")
    approve_products.short_description = "Approve & notify"

    def reject_products(self, request, queryset):
        updated = queryset.filter(is_approved=False).update(is_approved=False, is_active=False)
        self.message_user(request, f"{updated} product(s) rejected.")
    reject_products.short_description = "Reject products"


# Other main admin registrations (simple registration works with custom site)
admin_site.register(Category)
admin_site.register(Promotion)
admin_site.register(Order)
admin_site.register(Coupon)
admin_site.register(Review)
admin_site.register(Profile)
admin_site.register(Wishlist)
admin_site.register(Address)
admin_site.register(Notification)
admin_site.register(Payment)
admin_site.register(PaymentMethod)
admin_site.register(MobileMoneyProvider)
admin_site.register(SavedPaymentMethod)
admin_site.register(DeliveryOption)


# ========================
# SELLER ADMIN REGISTRATIONS
# ========================
@admin.register(Product, site=seller_admin_site)
class SellerProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'current_price_display', 'stock', 'is_approved', 'is_active')
    list_filter = ('is_approved', 'is_active', 'category')
    search_fields = ('name',)
    inlines = [ProductImageInline]
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(seller=request.user)

    def has_add_permission(self, request): return True
    def has_change_permission(self, request, obj=None): return obj is None or obj.seller == request.user
    def has_delete_permission(self, request, obj=None): return obj is None or obj.seller == request.user

    def current_price_display(self, obj):
        price = float(obj.current_price)
        return mark_safe(f'<strong>K{price:.2f} ZMW</strong>')
    current_price_display.short_description = "Current Price"


@admin.register(Order, site=seller_admin_site)
class SellerOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer_display', 'grand_total_display', 'status_display', 'created_at')
    list_filter = ('status', 'is_paid', 'created_at')
    search_fields = ('id',)
    inlines = [OrderItemInline]
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(items__product__seller=request.user).select_related('buyer').distinct()

    def has_view_permission(self, request, obj=None):
        if obj is not None:
            return obj.items.filter(product__seller=request.user).exists()
        return True

    def buyer_display(self, obj):
        full_name = obj.buyer.get_full_name()
        return full_name or obj.buyer.username
    buyer_display.short_description = "Buyer"
    buyer_display.admin_order_field = 'buyer__username'

    def grand_total_display(self, obj):
        total = obj.get_grand_total()
        return mark_safe(f'<strong class="text-2xl">K{total:.2f}</strong>')
    grand_total_display.short_description = "Total"

    def status_display(self, obj):
        status_text = obj.get_status_display().upper()
        
        if obj.is_paid:
            bg = 'bg-green-100 dark:bg-green-900/50'
            text = 'text-green-800 dark:text-green-300'
        elif obj.status == 'cancelled':
            bg = 'bg-red-100 dark:bg-red-900/50'
            text = 'text-red-800 dark:text-red-300'
        else:
            bg = 'bg-yellow-100 dark:bg-yellow-900/50'
            text = 'text-yellow-800 dark:text-yellow-300'

        return mark_safe(
            f'<span class="inline-flex px-4 py-2 rounded-full text-sm font-bold {bg} {text}">'
            f'{status_text}'
            f'</span>'
        )
    status_display.short_description = "Status"


@admin.register(Promotion, site=seller_admin_site)
class SellerPromotionAdmin(admin.ModelAdmin):
    list_display = ('product', 'discount_type', 'discount_value', 'is_active')
    list_filter = ('is_active',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(product__seller=request.user)