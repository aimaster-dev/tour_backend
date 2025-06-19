from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from .models import PaymentLogs

@receiver(post_save, sender=PaymentLogs)
def reset_video_and_snapshot_limit(sender, instance, created, **kwargs):
    
    if not created and instance.user.usertype != 4:
        # Reset the video and snapshot limit for the user
        if instance.videoremain == 0:
            instance.videoremain = 20
            instance.save()
        if instance.snapshotremain == 0:
            instance.snapshotremain = 20
            instance.save()