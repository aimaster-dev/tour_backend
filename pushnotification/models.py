from django.db import models
from user.models import User


class Notification(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='sent_notifications')
    recipients = models.ManyToManyField(
        User, related_name='received_notifications')
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    failed_users = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.created_at} sent by {self.sent_by.username}"
