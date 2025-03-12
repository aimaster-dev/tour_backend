import logging
from django.utils import timezone
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from user.permissions import IsAdmin, IsAdminOrISP
from .models import Venue
from user.models import User
from django.shortcuts import get_object_or_404
from .serializers import VenueSerializer, ISPSerializer, PublicVenueSerializer, PublicISPSerializer
from rest_framework.response import Response
from rest_framework import status
from tourvideoproject.utils import LoggerHelper

# Configure logger for this module
logger = LoggerHelper.get_logger('tourplace')


class TourplaceAPIView(APIView):

    permission_classes = [IsAdminOrISP]

    def get(self, request):
        user = request.user
        if user is not None and user.usertype == 2:
            venue = user.venue
            serializer = VenueSerializer(venue)
            return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
        elif user.usertype == 1:
            venues = Venue.objects.all()
            serializer = VenueSerializer(venues, many=True)
            data = serializer.data
            return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
        return Response({'status': False, 'data': {'msg': 'You have to login.'}}, status=status.HTTP_401_UNAUTHORIZED)

    def post(self, request):
        user = request.user
        if user.usertype == 1:
            data = request.data
            serializer = VenueSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
            return Response({'status': False, 'data': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': False, 'data': {'msg': 'You do not any have permission to create the venue.'}})


class VenueUpdateAPIView(APIView):

    permission_classes = [IsAdmin]

    def post(self, request):
        id = request.data["id"]
        venue = Venue.objects.get(id=id)
        data = request.data
        serializer = VenueSerializer(venue, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
        return Response({'status': False, 'data': {'msg': 'You do not any permission to create the venue.'}})

    def get(self, request, pk, format=None):
        venue = get_object_or_404(Venue, pk=pk)
        serializer = VenueSerializer(venue)
        return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)


class VenueDeleteAPIView(APIView):

    permission_classes = [IsAdmin]

    def post(self, request):
        id = request.data.get('id')
        if not id:
            return Response({"status": False, "data": {"msg": "Venue ID is required."}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            venue = Venue.objects.get(id=id)
            venue.delete()
            return Response({"status": True, "data": {"msg": "Successfully deleted."}}, status=status.HTTP_200_OK)
        except venue.DoesNotExist:
            return Response({"status": False, "data": {"msg": "Venue not found."}}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)


class VenueGetAllAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # Log the request with user info if authenticated
            user_info = f"User: {request.user.email}" if request.user.is_authenticated else "Anonymous user"
            LoggerHelper.log_api_request(
                logger, request, "Venues request received")

            venues = Venue.objects.all()
            serializer = VenueSerializer(venues, many=True)

            # Log successful response
            LoggerHelper.log_api_response(
                logger,
                request,
                status.HTTP_200_OK,
                f"Successfully retrieved {len(serializer.data)} tour places"
            )

            return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            # Log the error with detailed information
            error_message = f"{timezone.now().strftime('%Y-%m-%d %H:%M:%S')} - {user_info} - Error retrieving tour places: {str(e)}"
            LoggerHelper.log_exception(
                logger, request, e, error_message)
            return Response({"error": "Failed to retrieve tour places"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VenueGetAllForISPAPIView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        venues = Venue.objects.filter(isp=0)
        serializer = VenueSerializer(venues, many=True)
        return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)


class VenueGetAllForCamAPIView(APIView):
    permission_classes = [IsAdminOrISP]

    def get(self, request):
        user = request.user
        venues = []
        if user.usertype == 1:
            venues = Venue.objects.all()
        elif user.usertype == 2:
            venues = Venue.objects.filter(isp=user.pk)
        serializer = VenueSerializer(venues, many=True)
        return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)


class VenueAPIView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        venues = Venue.objects.all()
        serializer = VenueSerializer(venues, many=True)
        return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = VenueSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': True, 'data': serializer.data}, status=status.HTTP_201_CREATED)
        return Response({'status': False, 'data': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class VenueDetailAPIView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        venue = get_object_or_404(Venue, pk=pk)
        serializer = VenueSerializer(venue)
        return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)

    def put(self, request, pk):
        venue = get_object_or_404(Venue, pk=pk)
        serializer = VenueSerializer(venue, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
        return Response({'status': False, 'data': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        venue = get_object_or_404(Venue, pk=pk)
        venue.delete()
        return Response({'status': True, 'message': 'Venue deleted successfully'}, status=status.HTTP_200_OK)


class VenueISPListAPIView(APIView):
    def get(self, request, venue_id):
        isps = User.objects.filter(
            usertype=2,
            tourplaces__venue_id=venue_id
        ).distinct()
        serializer = ISPSerializer(isps, many=True)
        return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)


class PublicVenueListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        venues = Venue.objects.filter()
        # venues = Venue.objects.filter(status=True)
        serializer = VenueSerializer(venues, many=True)
        return Response({
            'status': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class PublicVenueDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, venue_id):
        try:
            venue = get_object_or_404(Venue, id=venue_id)
            serializer = PublicVenueSerializer(venue)
            return Response({
                'status': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        except Venue.DoesNotExist:
            return Response({
                'status': False,
                'error': 'Venue not found'
            }, status=status.HTTP_404_NOT_FOUND)


class PublicISPDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, isp_id):
        try:
            # usertype=2 ensures it's an ISP
            isp = get_object_or_404(User, id=isp_id, usertype=2)
            serializer = PublicISPSerializer(isp)
            return Response({
                'status': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'status': False,
                'error': 'ISP not found'
            }, status=status.HTTP_404_NOT_FOUND)
