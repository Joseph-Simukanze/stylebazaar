from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib import messages
from django.db.models import Sum, F
from django.utils import timezone

from .forms import UserRegistrationForm, ProfileForm, AddressForm
from .models import Profile, Address, Wishlist
from .decorators import buyer_required, seller_required
from orders.models import Order, OrderItem
from products.models import Product
from users.models import Review  # Import moved here to avoid potential circular import issues
from django.db.models import Avg
from django.db.models import Sum, Avg, Count, F, Q
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Avg, Sum, F
from django.contrib.auth import get_user_model

from products.models import Product
from orders.models import Order, OrderItem
from users.models import Review
from users.decorators import seller_required

User = get_user_model()


# ====================
# AUTHENTICATION VIEWS
# ====================
from django.contrib.auth import login
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters

from .forms import UserRegistrationForm
from .models import SellerProfile  # if you have a SellerProfile model


@sensitive_post_parameters('password1', 'password2')  # Hide passwords in debug traceback
@never_cache  # Prevent browser back-button issues after login
def register_view(request):
    """
    Handle user registration.
    Creates a regular user by default.
    Optionally creates a SellerProfile if the user chooses to be a seller.
    """
    if request.user.is_authenticated:
        # If already logged in, redirect appropriately
        if hasattr(request.user, 'seller_profile'):
            return redirect('seller_dashboard')
        return redirect('home')  # or buyer dashboard

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            # Save user but don't commit yet (in case we need to modify)
            user = form.save(commit=False)

            # Set password properly (hashed)
            user.set_password(form.cleaned_data["password1"])
            user.save()

            # Optional: Create SellerProfile if user selected "I want to sell"
            # Assuming your form has a field like `wants_to_sell` (boolean)
            wants_to_sell = form.cleaned_data.get('wants_to_sell', False)
            if wants_to_sell:
                SellerProfile.objects.get_or_create(user=user)
                messages.success(
                    request,
                    "Welcome, seller! Your account is created. You can now add products."
                )
            else:
                messages.success(
                    request,
                    "Registration successful! Welcome to Style Bazaar. Enjoy shopping!"
                )

            # Log the user in immediately
            login(request, user)

            # Redirect based on role
            if hasattr(user, 'seller_profile') or wants_to_sell:
                return redirect('seller_dashboard')
            return redirect('home')  # or buyer landing page

    else:
        form = UserRegistrationForm()

    return render(request, "users/register.html", {"form": form})

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, f"Welcome back, {form.get_user().username}!")
            return redirect("home")
    else:
        form = AuthenticationForm()

    return render(request, "users/login.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("login")


# ====================
# PROFILE & SETTINGS
# ====================
@login_required
def profile(request):
    return render(request, "users/profile.html")


@login_required
def change_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password was updated successfully.")
            return redirect("profile")
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, "users/change_password.html", {"form": form})


@login_required
def profile_edit(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile)

    return render(request, "users/profile_edit.html", {"form": form})


# ====================
# BUYER DASHBOARD
# ====================
@login_required
@buyer_required
def buyer_dashboard(request):
    user = request.user
    now = timezone.now()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    active_orders_count = user.orders.filter(
        is_paid=True
    ).exclude(
        status__in=['delivered', 'cancelled']
    ).count()

    delivered_this_month = user.orders.filter(
        is_paid=True,
        status='delivered',
        paid_at__gte=this_month_start
    ).count()

    wishlist_count = Wishlist.objects.filter(user=user).count()

    items_total = OrderItem.objects.filter(
        order__buyer=user,
        order__is_paid=True
    ).aggregate(total=Sum(F('price') * F('quantity')))['total'] or 0

    delivery_total = user.orders.filter(is_paid=True).aggregate(
        total=Sum('delivery_price')
    )['total'] or 0

    total_spent_zmw = items_total + delivery_total

    context = {
        'active_orders_count': active_orders_count,
        'delivered_this_month': delivered_this_month,
        'wishlist_count': wishlist_count,
        'total_spent_zmw': total_spent_zmw,
    }

    return render(request, "users/buyer_dashboard.html", context)


# ====================
# SELLER DASHBOARD
# ====================
# ====================
# SELLER DASHBOARD
# ====================
from django.db.models import Sum, Avg, Count, F
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Avg, Count, F
from django.utils import timezone
from django.shortcuts import render

from products.models import Product
from orders.models import Order, OrderItem
from .models import Review
from users.models import User
from users.decorators import seller_required


@login_required
@seller_required
def seller_dashboard(request):
    seller = request.user
    now = timezone.now()
    
    # Start of current month (timezone-aware)
    current_month_start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    # ─────────────────────────────────────────────────────────────
    # PRODUCT STATISTICS
    # ─────────────────────────────────────────────────────────────
    active_products = Product.objects.filter(
        seller=seller,
        is_active=True,
        is_approved=True
    ).count()

    total_products = Product.objects.filter(seller=seller).count()

    # ─────────────────────────────────────────────────────────────
    # ORDER & REVENUE STATISTICS
    # ─────────────────────────────────────────────────────────────
    # Pending / Action-required orders
    pending_orders = Order.objects.filter(
        items__product__seller=seller,
        is_paid=True,
        status__in=['confirmed', 'processing', 'shipped']
    ).distinct().count()

    # Total orders (all time)
    total_orders = Order.objects.filter(
        items__product__seller=seller
    ).distinct().count()

    # Monthly revenue (current month)
    monthly_revenue = OrderItem.objects.filter(
        product__seller=seller,
        order__is_paid=True,
        order__created_at__gte=current_month_start
    ).aggregate(
        total=Sum(F('price') * F('quantity'))
    )['total'] or 0

    # Lifetime total earnings
    lifetime_earnings = OrderItem.objects.filter(
        product__seller=seller,
        order__is_paid=True
    ).aggregate(
        total=Sum(F('price') * F('quantity'))
    )['total'] or 0

    # ─────────────────────────────────────────────────────────────
    # RATINGS & REVIEWS
    # ─────────────────────────────────────────────────────────────
    rating_data = Review.objects.filter(
        product__seller=seller
    ).aggregate(
        avg_rating=Avg('rating'),
        review_count=Count('id')
    )

    avg_rating = (
        round(rating_data['avg_rating'], 1)
        if rating_data['avg_rating'] is not None
        else "N/A"
    )
    review_count = rating_data['review_count'] or 0

    # ─────────────────────────────────────────────────────────────
    # BUYERS (for notifications or messaging)
    # ─────────────────────────────────────────────────────────────
    buyers = User.objects.filter(
        orders__items__product__seller=seller
    ).annotate(
        order_count=Count('orders', distinct=True)
    ).distinct().order_by('username')

    # ─────────────────────────────────────────────────────────────
    # RECENT ORDERS (for quick view / dropdown)
    # ─────────────────────────────────────────────────────────────
    recent_orders = Order.objects.filter(
        items__product__seller=seller
    ).select_related(
        'buyer'
    ).prefetch_related(
        'items__product'
    ).distinct().order_by('-created_at')[:10]  # Reduced to 10 for performance

    # ─────────────────────────────────────────────────────────────
    # CONTEXT FOR TEMPLATE
    # ─────────────────────────────────────────────────────────────
    context = {
        # Products
        'active_products': active_products,
        'total_products': total_products,
        
        # Orders
        'pending_orders': pending_orders,
        'total_orders': total_orders,
        
        # Revenue
        'total_sales_this_month': monthly_revenue,
        'lifetime_earnings': lifetime_earnings,
        
        # Reviews
        'avg_rating': avg_rating,
        'review_count': review_count,
        
        # Additional data
        'buyers': buyers,
        'recent_orders': recent_orders,
        
        # Current date/time (useful for display)
        'current_month': now.strftime('%B %Y'),
    }

    return render(request, "users/seller_dashboard.html", context)
# ====================
# WISHLIST
# ====================
@login_required
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related(
        'product__seller', 'product__category'
    ).prefetch_related('product__images').order_by('-added_at')
    return render(request, 'users/wishlist.html', {'wishlist_items': wishlist_items})


@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    obj, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if created:
        messages.success(request, f'"{product.name}" added to your wishlist! ❤️')
    else:
        messages.info(request, f'"{product.name}" is already in your wishlist.')
    return redirect('wishlist')  # or redirect to product detail if preferred


@login_required
def remove_from_wishlist(request, product_id):
    if request.method == "POST":
        item = get_object_or_404(Wishlist, user=request.user, product__id=product_id)
        product_name = item.product.name
        item.delete()
        messages.success(request, f'"{product_name}" removed from wishlist.')
    return redirect('wishlist')


# ====================
# ADDRESSES
# ====================
@login_required
def addresses_view(request):
    addresses = request.user.addresses.all()
    return render(request, 'users/addresses.html', {'addresses': addresses})


@login_required
def add_address(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, 'New address added successfully!')
            return redirect('addresses')
    else:
        form = AddressForm()
    return render(request, 'users/address_form.html', {'form': form, 'title': 'Add New Address'})


@login_required
def edit_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address updated successfully!')
            return redirect('addresses')
    else:
        form = AddressForm(instance=address)
    return render(request, 'users/address_form.html', {'form': form, 'title': 'Edit Address'})


@login_required
def delete_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    if request.method == 'POST':
        address.delete()
        messages.success(request, 'Address deleted successfully.')
    return redirect('addresses')


@login_required
def set_default_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    Address.objects.filter(user=request.user).update(is_default=False)
    address.is_default = True
    address.save()
    messages.success(request, 'Default address updated.')
    return redirect('addresses')


# ====================
# NOTIFICATIONS & SUPPORT
# ====================
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction

from .models import Notification  # Make sure this import is correct


@login_required
def notifications_view(request):
    user = request.user

    # Fetch all notifications for the current user, newest first
    notifications_qs = Notification.objects.filter(user=user).select_related('sender', 'order')

    # Count unread notifications (for potential badge or highlight)
    unread_count = notifications_qs.filter(is_read=False).count()

    # Mark all as read when the user views the page
    if unread_count > 0:
        with transaction.atomic():
            notifications_qs.filter(is_read=False).update(is_read=True, read_at=timezone.now())

    # Convert queryset to list of dicts for easy template use
    notifications = [
        {
            "id": n.id,
            "type": n.notification_type,
            "title": n.title,
            "message": n.message,
            "time": n.get_time(),  # Uses your model's method: "2 hours ago"
            "icon": n.get_icon(),  # Uses your improved model's method
            "is_read": n.is_read,
            "link": n.link,  # Optional clickable link
            "order_id": n.order.id if n.order else None,
            "sender_username": n.sender.username if n.sender else None,
        }
        for n in notifications_qs
    ]

    context = {
        'notifications': notifications,
        'unread_count': 0,  # Now 0 because we just marked them read
        'total_notifications': len(notifications),
        'has_notifications': len(notifications) > 0,
    }

    return render(request, 'users/notifications.html', context)

@login_required
def support_view(request):
    return render(request, 'users/support.html')


# ====================
# SELLER PAYOUTS
# ====================
@login_required
@seller_required
def seller_payouts(request):
    payouts = OrderItem.objects.filter(
        product__seller=request.user,
        order__is_paid=True
    ).values(
        "order__id",
        "order__created_at",
        "order__status",
        "order__buyer__username"
    ).annotate(
        total_amount=Sum(F("price") * F("quantity"))
    ).order_by("-order__created_at")

    total_earned = payouts.aggregate(total=Sum('total_amount'))['total'] or 0

    return render(request, "users/seller_payouts.html", {
        "payouts": payouts,
        "total_earned": total_earned,
    })