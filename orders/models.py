from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

from products.models import Product

User = settings.AUTH_USER_MODEL


# -------------------------
# DELIVERY OPTIONS
# -------------------------
from django.db import models
from django.core.validators import MinValueValidator
from django.utils.text import slugify


class DeliveryOption(models.Model):
    """
    Represents a delivery method with price and estimated time.
    Used during checkout to let buyers choose how they want their order delivered.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="e.g., Standard Delivery, Express Delivery, Instant Pickup"
    )
    slug = models.SlugField(
    max_length=120,
    unique=True,
    blank=True
    )

    is_active = models.BooleanField(default=True)



    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Delivery fee in Zambian Kwacha (ZMW)"
    )

    estimated_days = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Estimated number of days for delivery"
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Uncheck to temporarily disable this option without deleting it"
    )

    display_order = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
        help_text="Lower numbers appear first in the checkout options"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "price", "name"]
        verbose_name = "Delivery Option"
        verbose_name_plural = "Delivery Options"
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["display_order"]),
        ]

    def save(self, *args, **kwargs):
        """
        Auto-generate a UNIQUE slug from name if not provided.
        Safe for SQLite and PostgreSQL.
        """
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1

            while DeliveryOption.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        status = "" if self.is_active else " (Inactive)"
        days_word = "day" if self.estimated_days == 1 else "days"
        return f"{self.name} — K{self.price} ZMW ({self.estimated_days} {days_word}){status}"

    @property
    def formatted_price(self):
        """Returns price as formatted string for templates"""
        return f"K{self.price} ZMW"

    @property
    def estimated_delivery_text(self):
        """Returns nice text for estimated delivery"""
        days_word = "day" if self.estimated_days == 1 else "days"
        return f"{self.estimated_days} {days_word}"


# -------------------------
# COUPONS
# -------------------------
class Coupon(models.Model):
    code = models.CharField(
        max_length=30,
        unique=True,
        help_text="Unique coupon code (case-insensitive)"
    )
    discount_percent = models.PositiveIntegerField(
        help_text="Percentage discount (e.g., 10 for 10% off)",
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of uses (leave blank for unlimited)"
    )
    used_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-valid_from"]
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"

    def __str__(self):
        return f"{self.code.upper()} - {self.discount_percent}% off"

    def is_valid(self):
        """Check if coupon is currently valid"""
        now = timezone.now()
        if not self.active:
            return False
        if self.valid_from > now:
            return False
        if self.valid_to and self.valid_to < now:
            return False
        if self.max_uses and self.used_count >= self.max_uses:
            return False
        return True

    def increment_usage(self):
        """Increase used count (call when coupon is applied to an order)"""
        if self.max_uses:
            self.used_count += 1
            self.save(update_fields=['used_count'])


# Helper function for default delivery option
def get_default_delivery_option_id():
    """Return the ID of the cheapest delivery option. Create a default one if none exist."""
    option = DeliveryOption.objects.order_by('price').first()
    if not option:
        option = DeliveryOption.objects.create(
            name="Standard Delivery",
            price=50.00,          # Adjust price as needed
            estimated_days=3
        )
    return option.id


# -------------------------
# ORDER
# -------------------------
class Order(models.Model):
    ORDER_STATUS = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_METHODS = [
        ("airtelmoney", "Airtel Money"),
        ("mtn", "MTN Mobile Money"),
        ("zamtel", "Zamtel Kwacha"),
        ("cash", "Cash on Delivery"),
        ]
    buyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="orders"
    )
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, help_text="Contact phone number")
    address = models.TextField(help_text="Full delivery address")
    gps_location = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="GPS coordinates for precise delivery (e.g., -15.3875, 28.3228)"
    )
    delivery_option = models.ForeignKey(
        DeliveryOption,
        on_delete=models.PROTECT,
        related_name="orders",
        default=get_default_delivery_option_id  # ← Safe & robust default
    )
    delivery_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default="mpesa")
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default="pending")
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        return f"Order #{self.id} - {self.buyer.get_full_name() or self.buyer.username} ({self.get_status_display()})"

    def get_items_total(self):
        """Total price of all items before delivery & discount"""
        return sum(item.get_total() for item in self.items.all())

    def get_discount_amount(self):
        """Calculate discount based on applied coupon"""
        if not self.coupon or not self.coupon.is_valid():
            return 0
        items_total = self.get_items_total()
        return (items_total * self.coupon.discount_percent) / 100

    def get_grand_total(self):
        """Final total after discount and delivery"""
        items_total = self.get_items_total()
        discount = self.get_discount_amount()
        return max(items_total - discount + self.delivery_price, 0)

    def save(self, *args, **kwargs):
        # Auto-calculate discount on save if coupon is applied
        if self.coupon:
            self.discount_amount = self.get_discount_amount()
        else:
            self.discount_amount = 0
        super().save(*args, **kwargs)


# -------------------------
# ORDER ITEM
# -------------------------
class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        related_name="items",
        on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price at the time of purchase (with discount applied if any)"
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def __str__(self):
        return f"{self.quantity} × {self.product.name}"

    def get_total(self):
        return self.price * self.quantity