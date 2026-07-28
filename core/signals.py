
from django.core.cache import cache

from django.db.models.signals import (
    pre_save,
    post_save,
    post_delete
)
from django.dispatch import receiver
from . import models
#invalidate the document report when an update is detected.



@receiver(post_save, sender=models.LoanApplication)
def application_review_updated(sender, instance: models.LoanApplication, created, **kwargs):

    if created:
        return 
    
    #but if an update is detected.
    cache_key =f'application_detail_{instance.id}'
    cache.delete(cache_key)
    
    return

@receiver(post_delete, sender=models.LoanApplication)
def application_delete(sender, instance, **kwargs):

    return