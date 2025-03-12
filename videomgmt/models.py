from django.db import models
from django.core.files.base import ContentFile
from user.models import User
from tourplace.models import Venue
from moviepy.editor import VideoFileClip
import io
from PIL import Image


class Header(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video_path = models.FileField(upload_to='headers/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    thumbnail = models.ImageField(
        upload_to='headers/thumbnail/', null=True, blank=True)
    venue = models.ForeignKey(
        Venue, null=True, blank=True, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.thumbnail:
            self.generate_thumbnail()

    def generate_thumbnail(self):
        clip = VideoFileClip(self.video_path.path)
        temp_thumb = io.BytesIO()
        frame = clip.get_frame(t=1)
        image = Image.fromarray(frame)
        image.save(temp_thumb, format='JPEG')
        temp_thumb.seek(0)
        self.thumbnail.save(f"{self.pk}_thumbnail.jpg",
                            ContentFile(temp_thumb.read()), save=False)
        temp_thumb.close()
        clip.close()
        self.save()

    class Meta:
        db_table = 'header_tbl'

    def __str__(self):
        return f"{self.user.email} - {self.venue.venue_name if self.venue else 'No Venue'}"


class Footer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video_path = models.FileField(upload_to='footers/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    thumbnail = models.ImageField(
        upload_to='footers/thumbnail/', null=True, blank=True)
    venue = models.ForeignKey(
        Venue, null=True, blank=True, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.thumbnail:
            self.generate_thumbnail()

    def generate_thumbnail(self):
        clip = VideoFileClip(self.video_path.path)
        temp_thumb = io.BytesIO()
        frame = clip.get_frame(t=1)
        image = Image.fromarray(frame)
        image.save(temp_thumb, format='JPEG')
        temp_thumb.seek(0)
        self.thumbnail.save(f"{self.pk}_thumbnail.jpg",
                            ContentFile(temp_thumb.read()), save=False)
        temp_thumb.close()
        clip.close()
        self.save()

    class Meta:
        db_table = 'footer_tbl'

    def __str__(self):
        return f"{self.user.email} - {self.venue.venue_name if self.venue else 'No Venue'}"


class Video(models.Model):
    client = models.ForeignKey(User, on_delete=models.CASCADE)
    venue = models.ForeignKey(
        Venue, null=True, blank=True, on_delete=models.CASCADE)
    video_path = models.FileField(upload_to='videos/')
    status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    thumbnail = models.ImageField(
        upload_to='videos/thumbnail/', null=True, blank=True)

    class Meta:
        db_table = 'video_tbl'

    def __str__(self):
        return f"{self.client.email} - {self.venue.venue_name if self.venue else 'No Venue'}"


class SnapShot(models.Model):
    client = models.ForeignKey(User, on_delete=models.CASCADE)
    venue = models.ForeignKey(
        Venue, null=True, blank=True, on_delete=models.CASCADE)
    image_path = models.ImageField(upload_to='images/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'snapshot_tbl'

    def __str__(self):
        return f"{self.client.email} - {self.venue.venue_name if self.venue else 'No Venue'}"
