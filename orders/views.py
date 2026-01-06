from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404
from django.views.decorators.http import require_POST
from django.db.models import Prefetch
from decimal import Decimal
from users.decorators import buyer_required, seller_required
from cart.cart import Cart
from products.models import Product
from .models import Order, OrderItem, Coupon, DeliveryOption
from .forms import CheckoutForm
from django.utils import timezone
from django.db.models import Count
from django.contrib.auth import get_user_model
User = get_user_model()

# ========================
# BUYER CHECKOUT & ORDERS
# ========================

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.http import JsonResponse
from .forms import CheckoutForm
from .models import DeliveryOption, Order, OrderItem
from cart.cart import Cart  # adjust import path if needed
from orders.models import Coupon  # if Coupon is in orders app
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.http import JsonResponse

from cart.cart import Cart  # adjust path if needed
from .forms import CheckoutForm
from .models import DeliveryOption, Order, OrderItem, Coupon


from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from cart.cart import Cart
from .forms import CheckoutForm
from .models import DeliveryOption, Order, OrderItem, Coupon
from users.decorators import buyer_required  # adjust if path is different

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from orders.forms import CheckoutForm
from orders.models import OrderItem
from cart.cart import Cart
from users.decorators import buyer_required
from .models import Coupon
from orders.models import DeliveryOption


@login_required
@buyer_required
@require_http_methods(["GET", "POST"])
def checkout(request):
    cart = Cart(request)

    if len(cart) == 0:
        messages.info(request, "Your cart is empty.")
        return redirect("products:buyer_product_list")

    # Retrieve applied coupon from session
    coupon = None
    coupon_id = request.session.get("coupon_id")
    if coupon_id:
        try:
            coupon = Coupon.objects.get(id=coupon_id, active=True)
            if not coupon.is_valid():
                messages.warning(request, "The applied coupon is no longer valid.")
                request.session.pop("coupon_id", None)
                coupon = None
        except Coupon.DoesNotExist:
            request.session.pop("coupon_id", None)

    # ✅ FIXED: correct field name
    delivery_options = (
        DeliveryOption.objects
        .filter(is_active=True)
        .order_by("display_order", "price")
    )

    if request.method == "POST":
        form = CheckoutForm(request.POST)

        if form.is_valid():
            try:
                order = form.save(commit=False)
                order.buyer = request.user

                # Delivery option
                selected_delivery = form.cleaned_data["delivery_option"]
                order.delivery_option = selected_delivery
                order.delivery_price = selected_delivery.price

                # Coupon handling
                subtotal = cart.get_subtotal()
                if coupon and coupon.is_valid():
                    order.coupon = coupon
                    order.discount_amount = coupon.calculate_discount(subtotal)
                    coupon.increment_usage()

                order.save()

                # Create order items + reduce stock
                for item in cart:
                    OrderItem.objects.create(
                        order=order,
                        product=item["product"],
                        price=item["price"],
                        quantity=item["quantity"],
                    )
                    item["product"].reduce_stock(item["quantity"])

                # Cleanup
                cart.clear()
                request.session.pop("coupon_id", None)

                success_message = f"Order #{order.id} created successfully! Please complete payment."

                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({
                        "success": True,
                        "message": success_message,
                        "order_id": order.id,
                        "order_ref": f"ORDER-{order.id}",
                        "total_amount": float(order.get_grand_total()),
                    })

                messages.success(request, success_message)
                return redirect("orders:order_success", order_id=order.id)

            except Exception as e:
                error_msg = "An error occurred while placing your order. Please try again."
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {"success": False, "error": str(e) or error_msg},
                        status=500
                    )
                messages.error(request, error_msg)

        else:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                errors = {f: errs[0] for f, errs in form.errors.items()}
                return JsonResponse({
                    "success": False,
                    "error": "Please correct the highlighted errors.",
                    "errors": errors,
                }, status=400)

            messages.error(request, "Please correct the highlighted errors.")

    else:
        initial_data = {
            "full_name": request.user.get_full_name() or request.user.username,
            "email": request.user.email,
        }

        default_delivery = delivery_options.first()
        if default_delivery:
            initial_data["delivery_option"] = default_delivery.id

        form = CheckoutForm(initial=initial_data)

    # Totals
    subtotal = cart.get_subtotal()
    discount_amount = (
        coupon.calculate_discount(subtotal)
        if coupon and coupon.is_valid()
        else Decimal("0.00")
    )

    default_delivery_price = (
        delivery_options.first().price
        if delivery_options.exists()
        else Decimal("0.00")
    )

    context = {
        "form": form,
        "cart": cart,
        "coupon": coupon,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "delivery_price": default_delivery_price,
        "final_total": subtotal - discount_amount + default_delivery_price,
    }

    return render(request, "orders/checkout.html", context)

@login_required
@buyer_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    return render(request, "orders/order_success.html", {"order": order})


@login_required
@buyer_required
def order_list(request):
    orders = Order.objects.filter(buyer=request.user).order_by("-created_at").prefetch_related(
        Prefetch("items", queryset=OrderItem.objects.select_related("product"))
    )
    return render(request, "orders/order_list.html", {"orders": orders})


@login_required
@buyer_required
def tracking(request):
    """Buyer order tracking page - shows all orders with status"""
    orders = Order.objects.filter(buyer=request.user).order_by("-created_at").prefetch_related(
        "items__product"
    )
    return render(request, "orders/tracking.html", {"orders": orders})


@require_POST
@login_required
@buyer_required
def apply_coupon(request):
    code = request.POST.get("code", "").strip().upper()
    if not code:
        messages.error(request, "Please enter a coupon code.")
        return redirect("cart:cart_detail")

    try:
        coupon = Coupon.objects.get(code__iexact=code, active=True)
        if coupon.is_valid():
            request.session["coupon_id"] = coupon.id
            messages.success(request, f"Coupon '{coupon.code}' applied! {coupon.discount_percent}% off.")
        else:
            messages.error(request, "This coupon is no longer valid.")
            request.session.pop("coupon_id", None)
    except Coupon.DoesNotExist:
        messages.error(request, "Invalid coupon code.")
        request.session.pop("coupon_id", None)

    return redirect("cart:cart_detail")


# ========================
# SELLER ORDER VIEWS
# ========================

@login_required
@seller_required
def seller_orders(request):
    orders = (
        Order.objects.filter(items__product__seller=request.user)
        .distinct()
        .select_related("buyer", "delivery_option")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )
    return render(request, "orders/seller_orders.html", {"orders": orders})


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404
from .models import Order
from users.decorators import buyer_required, seller_required  # adjust if needed


# -----------------------------
# BUYER ORDER DETAIL
# -----------------------------
@login_required
@buyer_required
def order_detail(request, order_id):
    """
    Detail view for buyers to see their own order.
    """
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    
    context = {
        "order": order,
    }
    return render(request, "orders/order_detail.html", context)


# -----------------------------
# SELLER ORDER DETAIL (already had, but updated version)
# ------------from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404

from orders.models import Order
from users.decorators import seller_required  # assuming you have this


@login_required
@seller_required
def seller_order_detail(request, order_id):
    """
    Detail view for sellers to see an order that includes their products.
    Only shows items sold by the current seller.
    """
    order = get_object_or_404(Order, id=order_id)

    # Security: Seller can only view orders containing their products
    seller_items = order.items.filter(product__seller=request.user)
    if not seller_items.exists():
        raise Http404("You do not have permission to view this order.")

    # Calculate seller's subtotal from their items only
    seller_subtotal = sum(item.get_total() for item in seller_items)

    context = {
        "order": order,
        "seller_items": seller_items,
        "seller_subtotal": seller_subtotal,
        "seller_item_count": seller_items.count(),
        
        # Pass the full buyer User object — this fixes the template error
        "buyer": order.buyer,
        
        # Keep these for convenience (your template may use them)
        "buyer_name": order.full_name or order.buyer.get_full_name() or order.buyer.username,
        "buyer_phone": order.phone or getattr(order.buyer, 'phone_number', 'Not provided'),
        "buyer_address": order.address,
        "buyer_gps": order.gps_location,
        
        # Delivery info
        "delivery_option": order.delivery_option,
        "delivery_price": order.delivery_price,
        "tracking_number": order.tracking_number or "Not assigned yet",
    }
    
    return render(request, "orders/seller_order_detail.html", context)
from django.views.decorators.http import require_POST

@require_POST
@login_required
@buyer_required
def initiate_payment(request, order_id):
    # Temporarily remove buyer and is_paid checks for testing
    order = get_object_or_404(Order, id=order_id)  # ← Only check ID

    # Optional: Re-add security check but show better message
    if order.buyer != request.user:
        messages.error(request, "You can only pay for your own orders.")
        return redirect("orders:order_list")
    
    if order.is_paid:
        messages.info(request, "This order has already been paid.")
        return redirect("orders:order_detail", order_id=order.id)

    method = request.POST.get("method")
    valid_methods = ["airtelmoney", "mtn", "zamtel"]
    if method not in valid_methods:
        messages.error(request, "Please select a valid payment method.")
        return redirect("orders:order_success", order_id=order.id)

    # Simulate payment
    from django.utils import timezone
    order.is_paid = True
    order.paid_at = timezone.now()
    order.payment_method = method
    order.status = "confirmed"
    order.save()

    messages.success(request, f"Payment successful via {order.get_payment_method_display()}!")
    return redirect("orders:order_detail", order_id=order.id)
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from users.decorators import buyer_required  # if you have it, or remove if not needed
from orders.models import Order, OrderItem


@login_required
def buyer_order_tracking(request, order_id):
    try:
        order = Order.objects.get(id=order_id, buyer=request.user)
    except Order.DoesNotExist:
        messages.error(request, "Order not found or you don't have permission to view it.")
        return redirect("orders:order_list")

    context = {"order": order}
    return render(request, "orders/buyer_order_tracking.html", context)
@login_required
@seller_required
@require_http_methods(["GET", "POST"])
def seller_notifications(request):
    """
    Seller dashboard notifications:
    - Single buyer (optional order link)
    - Bulk broadcast to all buyers
    """
    seller = request.user

    # --------------------
    # BUYERS WHO PURCHASED
    # --------------------
    buyers_qs = (
        User.objects
        .filter(
            orders__items__product__seller=seller,
            orders__is_paid=True
        )
        .distinct()
        .annotate(order_count=Count('orders', distinct=True))
        .order_by('-order_count', 'username')
    )

    buyer_count = buyers_qs.count()

    # --------------------
    # RECENT PAID ORDERS
    # --------------------
    recent_orders = (
        Order.objects
        .filter(
            items__product__seller=seller,
            is_paid=True
        )
        .select_related('buyer')
        .distinct()
        .order_by('-created_at')[:20]
    )

    # --------------------
    # HANDLE POST
    # --------------------
    if request.method == "POST":
        send_mode = request.POST.get("send_mode", "single").lower()
        title = request.POST.get("title", "").strip()
        message = request.POST.get("message", "").strip()

        # Validation
        if not title:
            messages.error(request, "Message title is required.")
            return redirect("orders:seller_notifications")

        if not message:
            messages.error(request, "Message body is required.")
            return redirect("orders:seller_notifications")

        if len(title) > 200:
            messages.error(request, "Title must be 200 characters or less.")
            return redirect("orders:seller_notifications")

        # --------------------
        # BULK MODE
        # --------------------
        if send_mode == "bulk":
            if buyer_count == 0:
                messages.warning(request, "You have no buyers to notify yet.")
                return redirect("orders:seller_notifications")

            notifications = [
                Notification(
                    user=buyer,
                    sender=seller,
                    title=title,
                    message=message,
                    notification_type="promotion",
                    created_at=timezone.now()
                )
                for buyer in buyers_qs
            ]

            Notification.objects.bulk_create(notifications)

            messages.success(
                request,
                f"Broadcast sent to {len(notifications)} buyer{'s' if len(notifications) != 1 else ''}!"
            )

            return redirect("orders:seller_notifications")

        # --------------------
        # SINGLE BUYER MODE
        # --------------------
        buyer_id = request.POST.get("buyer")
        order_id = request.POST.get("order_id") or None

        if not buyer_id:
            messages.error(request, "Please select a buyer.")
            return redirect("orders:seller_notifications")

        try:
            buyer = buyers_qs.get(id=buyer_id)
        except User.DoesNotExist:
            messages.error(request, "Invalid buyer selected.")
            return redirect("orders:seller_notifications")

        order = None
        notification_type = "message"

        if order_id:
            try:
                order = Order.objects.get(
                    id=order_id,
                    items__product__seller=seller,
                    is_paid=True
                )
                notification_type = "order"
            except Order.DoesNotExist:
                messages.error(request, "Selected order is invalid.")
                return redirect("orders:seller_notifications")

        Notification.objects.create(
            user=buyer,
            sender=seller,
            title=title,
            message=message,
            notification_type=notification_type,
            order=order,
            link=order.get_tracking_url() if order else None,
            created_at=timezone.now()
        )

        messages.success(
            request,
            f"Notification sent to {buyer.get_full_name() or buyer.username}!"
        )

        return redirect("orders:seller_notifications")

    # --------------------
    # GET REQUEST
    # --------------------
    context = {
        "buyers": buyers_qs,
        "recent_orders": recent_orders,
        "buyer_count": buyer_count,
        "has_buyers": buyer_count > 0,
    }

    return render(request, "orders/seller_notifications.html", context)

# views.py
@login_required
@seller_required
def mark_order_shipped(request, order_id):
    order = get_object_or_404(Order, id=order_id, seller_items__product__seller=request.user)
    if request.method == 'POST' and order.status == 'pending' and order.is_paid:
        order.status = 'shipped'
        order.shipped_at = timezone.now()
        order.save()

        # Send email to buyer
        send_mail(
            subject=f"Your order #{order.id} has been shipped!",
            message=f"Hi {order.buyer.get_full_name()},\n\nGreat news! Your order from Style Bazaar has been shipped...\n\nTracking: Coming soon!",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.buyer.email],
        )

        messages.success(request, "Order marked as shipped and buyer notified!")
        return redirect('orders:seller_order_detail', order_id=order.id)

    return redirect('orders:seller_order_detail', order_id=order.id)