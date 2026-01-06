from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Category, Product, ProductImage


# -------------------------
# INLINE PRODUCT IMAGES
# -------------------------
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    max_num = 3


# -------------------------
# PRODUCT ADMIN
# -------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "seller_link",      # Custom clickable link instead of plain "seller"
        "category",
        "price",
        "stock",
        "is_active",
        "is_approved",
        "is_promoted",
        "created_at",
    )

    list_filter = (
        "category",
        "is_active",
        "is_approved",
        "is_promoted",
        "created_at",
    )

    search_fields = (
        "name",
        "description",
        "seller__username",
        "seller__email",    # Optional: also search by email if useful
    )

    list_editable = (
        "is_active",
        "is_approved",
        "is_promoted",
    )

    ordering = ("-created_at",)

    inlines = [ProductImageInline]

    actions = ["approve_products", "reject_products"]

    fieldsets = (
        ("Basic Info", {
            "fields": (
                "seller",
                "category",
                "name",
                "description",
            )
        }),
        ("Pricing & Stock", {
            "fields": (
                "price",
                "discounted_price",
                "stock",
            )
        }),
        ("Status & Visibility", {
            "fields": (
                "is_active",
                "is_approved",
                "is_promoted",
            )
        }),
    )

    # Custom display method for clickable seller link
    def seller_link(self, obj):
        if obj.seller:
            url = reverse("admin:auth_user_change", args=[obj.seller.id])
            return format_html('<a href="{}">{}</a>', url, obj.seller.get_username() or obj.seller.email)
        return "-"
    seller_link.short_description = "Seller"
    seller_link.admin_order_field = "seller__username"  # Allows sorting by username

    # ---------- ADMIN ACTIONS ----------
    @admin.action(description="✅ Approve selected products")
    def approve_products(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description="❌ Reject selected products")
    def reject_products(self, request, queryset):
        queryset.update(is_approved=False)


# -------------------------
# CATEGORY ADMIN
# -------------------------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_approved", "created_at")
    list_filter = ("is_approved",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}