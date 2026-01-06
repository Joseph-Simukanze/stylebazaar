from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

User = settings.AUTH_USER_MODEL


# -------------------------
# PAYMENT METHODS
# -------------------------
class PaymentMethod(models.Model):
    """Supported payment gateways/methods"""

    MOBILE_MONEY = "mobile_money"
    STRIPE = "stripe"
    CASH_ON_DELIVERY = "cod"

    METHOD_CHOICES = (
        (MOBILE_MONEY, "Mobile Money"),
        (STRIPE, "Credit/Debit Card (Stripe)"),
        (CASH_ON_DELIVERY, "Cash on Delivery"),
    )

    method = models.CharField(
        max_length=20,
        choices=METHOD_CHOICES,
        unique=True
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.get_method_display()


# -------------------------
# MOBILE MONEY PROVIDERS
# -------------------------
class MobileMoneyProvider(models.Model):
    """Zambian mobile money networks"""

    AIRTEL = "airtel"
    MTN = "mtn"
    ZAMTEL = "zamtel"

    PROVIDER_CHOICES = (
        (AIRTEL, "Airtel Money"),
        (MTN, "MTN MoMo"),
        (ZAMTEL, "Zamtel Kwacha"),
    )

    provider = models.CharField(
        max_length=10,
        choices=PROVIDER_CHOICES,
        unique=True
    )

    display_name = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    merchant_id = models.CharField(
        max_length=100,
        blank=True
    )
    api_key = models.CharField(
        max_length=200,
        blank=True
    )

    def __str__(self):
        return self.display_name


# -------------------------
# PAYMENT
# -------------------------
class Payment(models.Model):

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_REFUNDED = "refunded"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REFUNDED, "Refunded"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="payments"
    )

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payment"
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    # ✅ FIX: DEFAULT + PROTECT
    method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name="payments",
        default=1  # MUST exist (see note below)
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    # Mobile Money
    mobile_provider = models.ForeignKey(
        MobileMoneyProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments"
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True
    )

    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True
    )

    # Stripe
    stripe_payment_intent = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-initiated_at"]

    def __str__(self):
        return f"Payment #{self.id} | Order #{self.order.id} | {self.get_status_display()}"

    # -------------------------
    # VALIDATION
    # -------------------------
    def clean(self):
        if self.method.method == PaymentMethod.MOBILE_MONEY:
            if not self.mobile_provider:
                raise ValidationError("Mobile money provider is required.")
            if not self.phone_number:
                raise ValidationError("Phone number is required.")

    # -------------------------
    # STATE HELPERS
    # -------------------------
    def mark_paid(self, transaction_id=None):
        self.status = self.STATUS_PAID
        self.completed_at = timezone.now()

        if transaction_id:
            self.transaction_id = transaction_id

        # sync order
        self.order.is_paid = True
        self.order.paid_at = timezone.now()
        self.order.save(update_fields=["is_paid", "paid_at"])

        self.save(update_fields=["status", "completed_at", "transaction_id"])

    def mark_failed(self):
        self.status = self.STATUS_FAILED
        self.save(update_fields=["status", "updated_at"])
# payments/models.py - Add this at the end

class SavedPaymentMethod(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_payment_methods'
    )
    method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT
    )
    mobile_provider = models.ForeignKey(
        MobileMoneyProvider,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    phone_number = models.CharField(max_length=20, blank=True)

    name = models.CharField(max_length=100, help_text="e.g., My Airtel, Work MTN")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', '-created_at']
        unique_together = ('user', 'mobile_provider', 'phone_number')

    def __str__(self):
        return f"{self.name} ({self.phone_number or 'Card'}) - {self.user}"

    def save(self, *args, **kwargs):
        if self.is_default:
            SavedPaymentMethod.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
