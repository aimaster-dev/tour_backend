from django.db import models
from django.conf import settings
from tourplace.models import Venue
from user.models import User


class Camera(models.Model):
    camera_name = models.CharField(max_length=255, blank=True, default='')
    isp = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stream_url = models.CharField(max_length=255)
    output_url = models.CharField(max_length=255)
    venue = models.ForeignKey(
        Venue, null=True, blank=True, on_delete=models.CASCADE)
    level = models.IntegerField() 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'camera_tbl'
        constraints = [
            models.UniqueConstraint(
                fields=['stream_url', 'isp'], name='unique_stream_url_per_isp'
            )
        ]

    def __str__(self):
        return self.camera_name

# class Camera(models.Model):
#     camera_name = models.CharField(max_length=255, blank=True, default='')
#     isp = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
#     camera_ip = models.CharField(max_length=255)
#     camera_port = models.CharField(max_length=255)
#     camera_user_name = models.CharField(max_length=255)
#     password = models.CharField(max_length=255)
#     output_url = models.CharField(max_length=255)
#     tourplace = models.ForeignKey(TourPlace, on_delete=models.CASCADE)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'camera_tbl'
#         constraints = [
#             models.UniqueConstraint(fields=['camera_ip', 'camera_port'], name='unique_camera_ip_port')
#         ]

# class Stream(models.Model):
#     stream_url = models.CharField(max_length=255)
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     is_active = models.BooleanField(default=True)

#     class Meta:
#         db_table = 'stream_tbl'
#         constraints = [
#             models.UniqueConstraint(fields=['stream_url', 'user'], name='unique_stream_url_user')
#         ]
