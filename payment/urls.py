from django.urls import path
from .views import PaymentAPIView, ValidStatusAPIView, VideoSnapshotCountAPIView

urlpatterns = [
    path('pay', PaymentAPIView.as_view(), name='process_payment'),
    path('loglist', PaymentAPIView.as_view(), name='payment_list'),
    path('validlist', ValidStatusAPIView.as_view(), name='payment_log_for_client'),
    path('video-snapshot-count', VideoSnapshotCountAPIView.as_view(), name='video_snapshot_count'),
]