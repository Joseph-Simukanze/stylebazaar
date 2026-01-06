from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

# app_name = "users"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),

    path("buyer/dashboard/", views.buyer_dashboard, name="buyer_dashboard"),
    path("seller/dashboard/", views.seller_dashboard, name="seller_dashboard"),
    path("profile/", views.profile, name="profile"),
    path("change-password/", views.change_password, name="password_change"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    # users/urls.py

    path('addresses/', views.addresses_view, name='addresses'),
    path('addresses/add/', views.add_address, name='add_address'),
    path('addresses/edit/<int:address_id>/', views.edit_address, name='edit_address'),
    path('addresses/delete/<int:address_id>/', views.delete_address, name='delete_address'),
    path('addresses/default/<int:address_id>/', views.set_default_address, name='set_default_address'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('support/', views.support_view, name='support'),
    path("seller/payouts/", views.seller_payouts, name="seller_payouts"),
    

path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt'
    ), name='password_reset'),

    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html'
    ), name='password_reset_confirm'),

    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
]
