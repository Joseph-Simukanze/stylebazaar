from django.urls import path
from . import views

app_name = "products"

urlpatterns = [
    # Seller
    path("seller/", views.seller_product_list, name="seller_product_list"),
    path("seller/add/", views.product_create, name="product_create"),
    path("seller/<int:pk>/edit/", views.product_update, name="product_update"),
    path("seller/<int:pk>/delete/", views.product_delete, name="product_delete"),
    path("inventory/", views.inventory, name="inventory"),
    path("reports/", views.seller_reports, name="seller_reports"),
    path("seller/promotions/", views.seller_promotions, name="seller_promotions"),

    # Categories
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_update, name="category_update"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("categories/<slug:slug>/", views.category_detail, name="category_detail"),

    # Promotions
    path("promotions/", views.promotions_list, name="promotions_list"),
    path("promotions/add/<int:product_id>/", views.add_promotion, name="add_promotion"),
    path("promotions/remove/<int:product_id>/", views.remove_promotion, name="remove_promotion"),

    # Public
    path("", views.product_list, name="product_list"),

    # Product detail (LAST)
    path("<slug:slug>/", views.product_detail, name="product_detail"),
]
