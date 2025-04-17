from django.urls import path
from .views import PushNotification, NotificationHistory, LoggingTestAPIView

urlpatterns = [
    path('send/', PushNotification.as_view(), name='send_notification'),
    path('history/', NotificationHistory.as_view(), name='notification_history'),
    path('test-logging/', LoggingTestAPIView.as_view(), name='test_logging'),
]
