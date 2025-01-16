from django.db import models
from django.utils import timezone


class TourPlace(models.Model):
    place_name = models.CharField(max_length=255)
    status = models.BooleanField(default=True)
    isp = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tourplace_tbl'

    def __str__(self):
        return f"{self.place_name}"
