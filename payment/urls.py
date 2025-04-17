from django.urls import path
from .views import PaymentAPIView, ValidStatusAPIView, VideoSnapshotCountAPIView, PaymentDetailsAPIView, InAppPurchaseAPIView, AdminTransactionListAPIView, UserTransactionsAPIView

urlpatterns = [
    path('pay', PaymentAPIView.as_view(), name='process_payment'),
    path('loglist', PaymentAPIView.as_view(), name='payment_list'),
    path('validlist', ValidStatusAPIView.as_view(),
         name='payment_log_for_client'),
    path('video-snapshot-count', VideoSnapshotCountAPIView.as_view(),
         name='video_snapshot_count'),
    path('transactions', PaymentDetailsAPIView.as_view(),
         name='payment_transactions'),
    path('in-app-purchase', InAppPurchaseAPIView.as_view(), name='in_app_purchase'),
    path('admin/transactions', AdminTransactionListAPIView.as_view(),
         name='admin_transactions'),
    path('user/<int:user_id>/transactions', UserTransactionsAPIView.as_view(),
         name='user_transactions'),
]
