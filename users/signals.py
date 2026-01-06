from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, BuyerProfile, SellerProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == 'buyer':
            BuyerProfile.objects.create(user=instance)
        elif instance.role == 'seller':
            SellerProfile.objects.create(user=instance)
