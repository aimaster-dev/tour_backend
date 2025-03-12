from django.db import models
from tourplace.models import Venue


class Price(models.Model):
    level = models.IntegerField()
    price = models.FloatField(default=0.0)
    product_id = models.CharField(max_length=255, null=True, blank=True)
    title = models.CharField(max_length=255)
    record_time = models.IntegerField(default=0)
    record_limit = models.IntegerField(default=0)
    snapshot_limit = models.IntegerField(default=0)
    features = models.JSONField(default=list, blank=True)
    venue = models.ForeignKey(
        Venue, null=True, blank=True, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pricing_tbl'

    def __str__(self):
        return f"{self.title} - {self.price}"
