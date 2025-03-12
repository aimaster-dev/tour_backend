from django.urls import path
from .views import (VenueAPIView, VenueDetailAPIView,
                    PublicVenueListAPIView, PublicVenueDetailAPIView, PublicISPDetailAPIView,
                    VenueGetAllAPIView, VenueUpdateAPIView, VenueDeleteAPIView,
                    VenueGetAllForISPAPIView, VenueGetAllForCamAPIView)

urlpatterns = [
    path('add', VenueAPIView.as_view(), name='venue_add'),
    path('get', VenueAPIView.as_view(), name='venue_get'),
    path('getall', VenueGetAllAPIView.as_view(),
         name='get_all_venue_type'),
    path('update', VenueUpdateAPIView.as_view(), name='update_venue'),
    path('delete', VenueDeleteAPIView.as_view(), name='delete_venue'),
    path('id/<int:pk>', VenueUpdateAPIView.as_view(),
         name='get-venue-by-id'),
    path('getispall', VenueGetAllForISPAPIView.as_view(),
         name='get-venue-for-isp'),
    path('getvenuebyisp', VenueGetAllForISPAPIView.as_view(),
         name='get-venue-for-isp'),
    path('venue/', VenueAPIView.as_view(), name='venue-list-create'),
    path('venue/<int:pk>/', VenueDetailAPIView.as_view(), name='venue-detail'),
    path('venues/public/', PublicVenueListAPIView.as_view(),
         name='public-venue-list'),
    path('venues/public/<int:venue_id>/',
         PublicVenueDetailAPIView.as_view(), name='public-venue-detail'),
    path('isps/public/<int:isp_id>/',
         PublicISPDetailAPIView.as_view(), name='public-isp-detail'),
]
