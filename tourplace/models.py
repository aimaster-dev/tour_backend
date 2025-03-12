from django.db import models
from django.utils import timezone


class TourPlace(models.Model):
    '''
    IMPORTANT: This model is deprecated. It is replaced by Venue model.
    '''
    place_name = models.CharField(max_length=255)
    status = models.BooleanField(default=True)
    isp = models.IntegerField(default=0)
    venue = models.ForeignKey(
        "Venue", on_delete=models.CASCADE, null=True, related_name='tourplaces', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tourplace_tbl'

    def __str__(self):
        return f"{self.place_name} - {'Active' if self.status else 'Inactive'}"


class Venue(models.Model):
    venue_name = models.CharField(max_length=255)
    status = models.BooleanField(default=True)
    isp = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'venue_tbl'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.venue_name} - {'Active' if self.status else 'Inactive'}"
