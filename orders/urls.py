from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = "orders"

urlpatterns = [
    # Buyer flows
    path("checkout/", views.checkout, name="checkout"),
    path("my-orders/", views.order_list, name="order_list"),
    path("order/<int:order_id>/", views.order_detail, name="order_detail"),  # ← ADDED: Buyer order detail
    path("success/<int:order_id>/", views.order_success, name="order_success"),
    path("tracking/", views.tracking, name="tracking"),

    # Legacy redirect (optional – keeps old URLs working)
    path("success/", views.order_success, name="order_success_legacy"),  # if you still need a non-param version

    # Seller flows
    path("seller/orders/", views.seller_orders, name="seller_orders"),
    path("seller/<int:order_id>/", views.seller_order_detail, name="seller_order_detail"),

    # Redirect old create path to checkout
    path("create/", RedirectView.as_view(url="/orders/checkout/", permanent=True), name="create_order"),
    path("initiate-payment/<int:order_id>/", views.initiate_payment, name="initiate_payment"),
   path("track/<int:order_id>/", views.buyer_order_tracking, name="buyer_order_tracking"),
   path("seller/notifications/", views.seller_notifications, name="seller_notifications"),
   # urls.py
path('order/<int:order_id>/ship/', views.mark_order_shipped, name='mark_order_shipped'),
   
]