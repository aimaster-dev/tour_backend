from django.urls import path
from .views import PushNotification, NotificationHistory

urlpatterns = [
    path('send', PushNotification.as_view(), name='send_notification'),
    path('history', NotificationHistory.as_view(), name='notification_history'),
]
