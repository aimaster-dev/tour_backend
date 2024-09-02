from django.db import models

# Create your models here.
class PaymentLogs(models.Model):
    user = models.IntegerField(default=0)
    price = models.IntegerField(default=0)
    amount = models.FloatField(default=0.0)
    remain = models.IntegerField(default=0)
    status = models.CharField(max_length=255)
    message = models.CharField(max_length=1000)
    comment = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invoice_tbl'