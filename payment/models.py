from django.db import models
from django.conf import settings
from price.models import Price


class PaymentLogs(models.Model):
    PAYMENT_STATUS = (
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed')
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    price = models.ForeignKey(
        Price, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.FloatField(default=0.0)
    videoremain = models.IntegerField(default=0)
    snapshotremain = models.IntegerField(default=0)
    record_time = models.IntegerField(default=10)
    status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS, default='PENDING')
    transaction_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invoice_tbl'
        verbose_name_plural = "PaymentLogs"

    def __str__(self):
        return f"{self.user.username} - {self.price.title if self.price else 'No Plan'} - {self.status}"
