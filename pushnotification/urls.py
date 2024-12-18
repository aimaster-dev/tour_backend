from django.urls import path
from .views import PushNotification

urlpatterns = [
    path('push', PushNotification.as_view(), name = 'push_notification'),
]