from django.urls import path
# from .views import CameraAPIView, CameraUpdateAPIView, CameraDeleteAPIView, CameraCheckAPIView, CameraClientAPIView, CameraRestartAPIView, CameraStreamingAPIView
from .views import CameraAPIView, CameraUpdateAPIView, CameraDeleteAPIView, CameraClientAPIView

urlpatterns = [
    path('add', CameraAPIView.as_view(), name = 'camera_add'),
    path('getall', CameraAPIView.as_view(), name = 'get_all_camera_of_current_isp'),
    path('update', CameraUpdateAPIView.as_view(), name = 'update_camera'),
    path('id/<int:pk>', CameraUpdateAPIView.as_view(), name = 'get_camera_by_id'),
    path('tour', CameraClientAPIView.as_view(), name = 'get_camera_by_tourplace'),
    path('delete', CameraDeleteAPIView.as_view(), name = 'delete_camera'),
    # path('restart', CameraRestartAPIView.as_view(), name = 'restart_camera'),
    # path('check', CameraCheckAPIView.as_view(), name = 'check_camera'),
    # path('stream/start/<int:pk>/<int:userid>', CameraStreamingAPIView.as_view(), name = 'start_camera_streaming'),
    # path('stream/stop/<int:pk>/<int:userid>', CameraStreamingAPIView.as_view(), name = 'stop_camera_streaming'),
]