from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def buyer_required(view_func):
    """
    Decorator to restrict views to authenticated buyers only.
    - Redirects unauthenticated users to login
    - Redirects sellers to seller dashboard
    - Allows buyers to proceed
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        user = request.user

        # Check if user is a seller
        if getattr(user, "is_seller", lambda: False)():
            messages.info(request, "You're logged in as a seller. Redirecting to your dashboard.")
            return redirect("seller_dashboard")

        # If not a seller and authenticated, assume buyer (or default user)
        # You can tighten this if you have an explicit is_buyer flag
        return view_func(request, *args, **kwargs)

    return wrapper


def seller_required(view_func):
    """
    Decorator to restrict views to authenticated sellers only.
    - Redirects unauthenticated users to login
    - Redirects buyers to buyer dashboard
    - Allows sellers to proceed
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        user = request.user

        if not getattr(user, "is_seller", lambda: False)():
            messages.warning(request, "This page is only available to registered sellers.")
            return redirect("buyer_dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


def seller_required_strict(view_func):
    """
    Strict version for sensitive actions (e.g., API endpoints).
    Raises 403 PermissionDenied instead of redirecting.
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not getattr(request.user, "is_seller", lambda: False)():
            raise PermissionDenied("You do not have permission to perform this action.")

        return view_func(request, *args, **kwargs)

    return wrapper


# Optional: Combined role check for advanced use
def role_required(allowed_roles=["buyer", "seller"]):
    """
    Flexible decorator to allow multiple roles.
    Example usage:
        @role_required(["buyer", "seller"])
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            user = request.user
            is_buyer = not getattr(user, "is_seller", lambda: False)()
            is_seller = getattr(user, "is_seller", lambda: False)()

            user_role = "seller" if is_seller else "buyer"

            if user_role not in allowed_roles:
                messages.warning(request, f"This page is restricted to {', '.join(allowed_roles)}.")
                redirect_url = "seller_dashboard" if is_seller else "buyer_dashboard"
                return redirect(redirect_url)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator