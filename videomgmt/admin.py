from django.contrib import admin
from .models import Video, Header, Footer, SnapShot

# Register your models here.
admin.site.register(Video)
admin.site.register(SnapShot)
admin.site.register(Header)
admin.site.register(Footer)
