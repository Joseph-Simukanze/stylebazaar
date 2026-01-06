from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver

from orders.models import Order
from products.models import Product


# ========================
# CUSTOM USER MODEL
# ========================
class User(AbstractUser):
    BUYER = "buyer"
    SELLER = "seller"

    ROLE_CHOICES = (
        (BUYER, "Buyer"),
        (SELLER, "Seller"),
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default=BUYER,
    )

    phone_number = models.CharField(
        max_length=15,
        unique=True,
        blank=True,
        null=True,
        help_text="Required for mobile money payments"
    )

    is_verified = models.BooleanField(default=False)

    def is_buyer(self):
        return self.role == self.BUYER

    def is_seller(self):
        return self.role == self.SELLER

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


# ========================
# GENERAL PROFILE (shared)
# ========================
class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    avatar = models.ImageField(
        upload_to="avatars/",
        blank=True,
        null=True
    )
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username} Profile"


# ========================
# BUYER PROFILE
# ========================
class BuyerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="buyer_profile"
    )
    shipping_address = models.TextField(blank=True)

    def __str__(self):
        return f"Buyer Profile - {self.user.username}"


# ========================
# SELLER PROFILE
# ========================
class SellerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_profile"
    )
    shop_name = models.CharField(max_length=255)
    shop_description = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Seller: {self.shop_name} ({self.user.username})"


# ========================
# AUTO-CREATE PROFILE ON USER CREATION
# ========================
@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
        if instance.is_buyer():
            BuyerProfile.objects.create(user=instance)
        elif instance.is_seller():
            SellerProfile.objects.create(user=instance)


# ========================
# WISHLIST
# ========================
class Wishlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist_items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-added_at']
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'

    def __str__(self):
        return f"{self.user.username} ❤️ {self.product.name}"


# ========================
# ADDRESS
# ========================
class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="Zambia")
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-updated_at']
        verbose_name_plural = "Addresses"

    def __str__(self):
        return f"{self.full_name} - {self.city}, {self.state}"

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


# ========================
# REVIEW & VOTE
# ========================
class Review(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reviews"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "user"],
                name="unique_review_per_user_per_product"
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.rating}⭐ by {self.user}"


class ReviewVote(models.Model):
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="votes"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    is_helpful = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["review", "user"],
                name="unique_review_vote_per_user"
            )
        ]

# users/models.py (or wherever your Notification model lives)

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.timesince import timesince

from orders.models import Order  # Adjust import path as needed


# ========================
# NOTIFICATIONS
# ========================
class Notification(models.Model):
    TYPE_CHOICES = [
        ('order', 'Order Update'),          # e.g., confirmed, shipped, delivered
        ('message', 'Direct Message'),      # User-to-user or system message
        ('promotion', 'Promotion'),         # Sales, flash deals, new arrivals
        ('review', 'Review & Rating'),      # Someone reviewed your product/order
        ('system', 'System Alert'),         # Important account/admin notices
        ('product', 'Product Update'),      # Product approved, stock low, etc.
    ]

    # Recipient of the notification
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Recipient"
    )

    # Optional: Who triggered/sent this notification (e.g., seller, admin, system)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_notifications',
        verbose_name="Sender"
    )

    title = models.CharField(max_length=200, help_text="Short title for the notification")
    message = models.TextField(help_text="Full message body")

    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='system',
        db_index=True,  # Improves filtering performance
        verbose_name="Type"
    )

    # Optional link to related order (for order-related notifications)
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name="Related Order"
    )

    # Optional generic link (e.g., to a product, review, or message thread)
    link = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Optional URL to redirect when notification is clicked"
    )

    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_read', '-created_at']),
        ]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.get_notification_type_display()} — {self.title} ({self.user})"

    def get_time(self):
        """Human-readable time since creation (e.g., '2 hours ago')"""
        return timesince(self.created_at) + " ago"

    def mark_as_read(self):
        """Mark notification as read with timestamp"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def get_icon(self):
        """Return a suitable emoji/icon based on type"""
        icons = {
            'order': "📦",
            'message': "💬",
            'promotion': "🎉",
            'review': "⭐",
            'system': "⚙️",
            'product': "🛍️",
        }
        return icons.get(self.notification_type, "🔔")