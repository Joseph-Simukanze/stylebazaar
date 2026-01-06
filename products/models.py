# products/models.py

from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal


User = settings.AUTH_USER_MODEL


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_approved"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Approved" if self.is_approved else "Pending"
        return f"{self.name} ({status})"


from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

class Product(models.Model):
    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="products"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        limit_choices_to={"is_approved": True}
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=12, decimal_places=2)

    # Manual discounted price – highest priority
    discounted_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Manual override price — takes priority over any promotion"
    )

    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_promoted = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)

    sold_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Product"
        verbose_name_plural = "Products"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active", "is_approved"]),
            models.Index(fields=["seller"]),
            models.Index(fields=["category"]),
            models.Index(fields=["is_promoted"]),
        ]

    # -----------------------------
    # SAVE
    # -----------------------------
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    # -----------------------------
    # STOCK
    # -----------------------------
    def is_in_stock(self):
        return self.stock > 0

    def reduce_stock(self, quantity: int):
        if quantity > self.stock:
            raise ValueError("Not enough stock available")
        self.stock -= quantity
        self.sold_count += quantity
        self.save(update_fields=["stock", "sold_count"])

    # -----------------------------
    # PROMOTION (CRASH-PROOF)
    # -----------------------------
    @property
    def active_promotion(self):
        """
        Returns the currently valid promotion or None.
        NEVER raises RelatedObjectDoesNotExist.
        """
        promo = getattr(self, "promotion", None)
        if not promo:
            return None

        today = timezone.now().date()

        if not promo.is_active:
            return None
        if promo.start_date > today:
            return None
        if promo.end_date and promo.end_date < today:
            return None

        return promo

    # -----------------------------
    # PRICING (BUSINESS LOGIC)
    # -----------------------------
    @property
    def current_price(self):
        """Final price customer pays"""
        # 1. Manual override (highest priority)
        if self.discounted_price is not None:
            return self.discounted_price

        # 2. Active promotion
        promo = self.active_promotion
        if promo:
            return promo.get_discounted_price(self.price)

        # 3. Regular price
        return self.price

    @property
    def has_active_promotion(self):
        return self.active_promotion is not None

    @property
    def savings_amount(self):
        if self.current_price < self.price:
            return self.price - self.current_price
        return Decimal("0.00")

    @property
    def has_savings(self):
        return self.savings_amount > Decimal("0.00")

    # -----------------------------
    # MEDIA
    # -----------------------------
    @property
    def main_image(self):
        return self.images.first()

    def __str__(self):
        seller_name = self.seller.get_full_name() or self.seller.username
        return f"{self.name} (by {seller_name})"


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images"
    )
    image = models.ImageField(upload_to="products/%Y/%m/")
    alt_text = models.CharField(max_length=255, blank=True, help_text="Optional SEO alt text")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "Product Image"
        verbose_name_plural = "Product Images"

    def __str__(self):
        return f"Image #{self.pk} for {self.product.name}"


class DeliveryOption(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    estimated_days = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Estimated delivery time in days"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price"]

    def __str__(self):
        days = f" ({self.estimated_days} days)" if self.estimated_days else ""
        return f"{self.name}{days} - K{self.price}"

from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

class Promotion(models.Model):
    DISCOUNT_CHOICES = [
        ("percentage", "Percentage Off"),
        ("fixed", "Fixed Amount Off"),
    ]

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="promotion",
        help_text="Product this promotion applies to"
    )

    title = models.CharField(
        max_length=150,
        blank=True,
        help_text="e.g., 'New Year Flash Sale' or 'Weekend Special'"
    )

    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_CHOICES,
        default="percentage"
    )

    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Percentage (e.g., 30) or fixed amount"
    )

    start_date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True, db_index=True)

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Promotion"
        verbose_name_plural = "Promotions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.title or 'Promotion'} – {self.get_discount_type_display()}"

    def clean(self):
        super().clean()

        if self.discount_value <= 0:
            raise ValidationError("Discount value must be greater than 0.")

        if self.discount_type == "percentage" and self.discount_value > 100:
            raise ValidationError("Percentage discount cannot exceed 100%.")

        if self.end_date and self.start_date > self.end_date:
            raise ValidationError("End date cannot be earlier than start date.")

    @property
    def is_valid(self):
        """Check if promotion is currently valid"""
        today = timezone.now().date()
        if not self.is_active:
            return False
        if self.start_date > today:
            return False
        if self.end_date and self.end_date < today:
            return False
        return True

    def get_discounted_price(self, original_price=None):
        """Safely apply discount"""
        if not self.is_valid:
            return original_price

        price = original_price or self.product.price

        if self.discount_type == "percentage":
            discount = price * (self.discount_value / Decimal("100"))
        else:
            discount = self.discount_value

        return max(price - discount, Decimal("0"))
