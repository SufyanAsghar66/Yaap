"""
Signal handlers for the accounts app.
- Update display_name default after creation
- Log user creation events
"""

import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def set_default_display_name(sender, instance, created, **kwargs):
    """If display_name is blank on creation, set it to the first part of full_name."""
    if created and not instance.display_name:
        instance.display_name = instance.full_name.split()[0] if instance.full_name else instance.email.split("@")[0]
        User.objects.filter(pk=instance.pk).update(display_name=instance.display_name)
        logger.info("Set default display_name for new user %s", instance.id)


@receiver(post_save, sender=User)
def log_user_creation(sender, instance, created, **kwargs):
    if created:
        logger.info(
            "New user created: id=%s email=%s provider=%s",
            instance.id,
            instance.email,
            instance.auth_provider,
        )
