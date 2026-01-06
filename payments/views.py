import stripe
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from orders.models import Order
from .models import SavedPaymentMethod, MobileMoneyProvider, PaymentMethod  # Assuming PaymentMethod is your model with choices

stripe.api_key = settings.STRIPE_SECRET_KEY


def payment(request, order_id):
    """
    View to initiate Stripe card payment for an order.
    Creates a PaymentIntent and renders the payment page.
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)  # Add user check for security

    # Optional: Prevent recreating intent if already exists
    if not order.stripe_payment_intent_id:
        intent = stripe.PaymentIntent.create(
            amount=int(order.get_total_price() * 100),  # Amount in cents
            currency="usd",  # Change to your currency, e.g., "zmw" if supported
            metadata={
                "order_id": str(order.id),
                "user_id": str(request.user.id),
            },
            # automatic_payment_methods={"enabled": True},  # Recommended for modern integrations
        )
        order.stripe_payment_intent_id = intent.id
        order.save(update_fields=["stripe_payment_intent_id"])

    else:
        # Retrieve existing intent if needed (optional)
        intent = stripe.PaymentIntent.retrieve(order.stripe_payment_intent_id)

    return render(
        request,
        "payments/payment.html",
        {
            "order": order,
            "client_secret": intent.client_secret,
            "stripe_public_key": settings.STRIPE_PUBLIC_KEY,
        },
    )


@login_required
def payment_methods_view(request):
    """
    View to manage saved payment methods (Mobile Money only for now).
    Supports adding, deleting, and setting default mobile money methods.
    """
    saved_methods = request.user.saved_payment_methods.all().order_by('-is_default', 'id')
    mobile_providers = MobileMoneyProvider.objects.filter(is_active=True)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_mobile":
            provider_id = request.POST.get("provider")
            phone = request.POST.get("phone")
            name = request.POST.get("name")

            if not provider_id or not phone:
                messages.error(request, "Provider and phone number are required.")
                return redirect("payments:payment_methods")

            try:
                provider = MobileMoneyProvider.objects.get(id=provider_id, is_active=True)
            except MobileMoneyProvider.DoesNotExist:
                messages.error(request, "Invalid provider selected.")
                return redirect("payments:payment_methods")

            if not name:
                name = f"My {provider.display_name} ({phone[-4:]})"

            # Get the singleton Mobile Money method (adjust if you have multiple types)
            mobile_method = PaymentMethod.objects.get(method=PaymentMethod.MOBILE_MONEY)

            new_method = SavedPaymentMethod.objects.create(
                user=request.user,
                method=mobile_method,
                mobile_provider=provider,  # Use ForeignKey field name
                phone_number=phone,
                name=name,
            )

            # Set as default only if user has no other methods
            if not saved_methods.exists():
                new_method.is_default = True
                new_method.save(update_fields=["is_default"])

            messages.success(request, f"{name} has been added successfully!")
            return redirect("payments:payment_methods")

        elif action == "delete":
            method_id = request.POST.get("method_id")
            method = get_object_or_404(SavedPaymentMethod, id=method_id, user=request.user)
            method.delete()
            messages.success(request, "Payment method removed successfully.")
            return redirect("payments:payment_methods")

        elif action == "set_default":
            method_id = request.POST.get("method_id")
            new_default = get_object_or_404(SavedPaymentMethod, id=method_id, user=request.user)

            # Unset previous default
            SavedPaymentMethod.objects.filter(user=request.user, is_default=True).update(is_default=False)

            new_default.is_default = True
            new_default.save(update_fields=["is_default"])

            messages.success(request, "Default payment method updated.")
            return redirect("payments:payment_methods")

    context = {
        "saved_methods": saved_methods,
        "mobile_providers": mobile_providers,
    }
    return render(request, "payments/payment_methods.html", context)
# your_app/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import HttpResponseBadRequest
from orders.models import Order  # make sure you have an Order model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required  # Optional: if only logged-in users
from django.urls import reverse



@require_POST
# @login_required  # Uncomment if only authenticated users can place orders
def confirm_payment(request):
    transaction_ref = request.POST.get('transaction_ref')
    order_id = request.POST.get('order_id')

    # Basic input validation
    if not transaction_ref or not order_id:
        messages.error(request, "Invalid request. Transaction reference and order ID are required.")
        return redirect('checkout')  # or your checkout page name

    transaction_ref = transaction_ref.strip()

    if len(transaction_ref) < 3:  # Basic length check
        messages.error(request, "Transaction reference seems too short. Please check and try again.")
        return redirect('order_success', order_id=order_id)  # back to order page

    try:
        # Fetch order securely
        order_query = {'id': order_id}

        # If user is authenticated, ensure the order belongs to them (security)
        if request.user.is_authenticated:
            order_query['customer'] = request.user

        order = get_object_or_404(Order, **order_query)

        # Prevent re-submission or processing paid/verified orders
        if order.status in ['paid', 'awaiting_verification', 'processing', 'shipped', 'delivered']:
            messages.info(request, "This order has already been processed or is under verification.")
            return redirect('orders:order_detail', order_id=order.id)

        if order.status != 'pending_payment':
            messages.error(request, "This order is not awaiting payment.")
            return redirect('orders:order_detail', order_id=order.id)

        # Save transaction reference and update status
        order.payment_transaction_id = transaction_ref
        order.status = 'awaiting_verification'
        order.save()

        # Success message
        messages.success(
            request,
            f"Success! Your payment reference <strong>{transaction_ref}</strong> has been recorded. "
            "We are verifying your payment and will confirm shortly via SMS/email."
        )

        # Render dedicated confirmation page with full order context
        return render(request, 'payments/confirm_payment.html', {
            'order': order,
        })

    except Order.DoesNotExist:
        messages.error(request, "Order not found or you don't have permission to access it.")
        return redirect('home')  # or checkout

    except Exception as e:
        # Log the error in production (e.g., using logging module)
        print(f"Error in confirm_payment: {e}")  # Replace with proper logging
        messages.error(request, "An unexpected error occurred. Please try again or contact support.")
        return redirect('orders:checkout')
    # payments/views.py
@require_POST
@login_required
def simulate_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    if order.status not in ['pending_payment', 'awaiting_verification']:
        return JsonResponse({"success": False, "error": "Order already processed."})

    order.status = 'paid'
    order.payment_transaction_id = 'SIMULATED-TEST-PAYMENT'
    order.save()

    return JsonResponse({
        "success": True,
        "redirect_url": reverse('orders:order_success', kwargs={'order_id': order.id})
    })