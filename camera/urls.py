from django.urls import path, include
from rest_framework.routers import DefaultRouter
# from .views import CameraAPIView, CameraUpdateAPIView, CameraDeleteAPIView, CameraCheckAPIView, CameraClientAPIView, CameraRestartAPIView, CameraStreamingAPIView
from .views import CameraViewSet, CameraViewSetForISP, CameraAPIView, CamerasByCustomerAPIView

router = DefaultRouter()
router.register(r'cameras', CameraViewSet, basename='camera')
router.register(r'cameras-isp', CameraViewSetForISP, basename='camera-isp')

urlpatterns = [
    path('', include(router.urls)),

    # path('add', CameraAPIView.as_view(), name = 'camera_add'),
    path('getall', CameraAPIView.as_view(),
         name='get_all_camera_of_current_isp'),
    
     path('get-cameras-by-customer/<int:customer_id>/', CamerasByCustomerAPIView.as_view(),
         name='get_cameras_by_customer'),
    # path('update', CameraUpdateAPIView.as_view(), name = 'update_camera'),
    # path('id/<int:pk>', CameraUpdateAPIView.as_view(), name = 'get_camera_by_id'),
    # path('tour', CameraClientAPIView.as_view(), name = 'get_camera_by_tourplace'),
    # path('delete', CameraDeleteAPIView.as_view(), name = 'delete_camera'),

    # path('restart', CameraRestartAPIView.as_view(), name = 'restart_camera'),
    # path('check', CameraCheckAPIView.as_view(), name = 'check_camera'),
    # path('stream/start/<int:pk>/<int:userid>', CameraStreamingAPIView.as_view(), name = 'start_camera_streaming'),
    # path('stream/stop/<int:pk>/<int:userid>', CameraStreamingAPIView.as_view(), name = 'stop_camera_streaming'),
]
