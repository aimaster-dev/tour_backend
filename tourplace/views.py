from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from user.permissions import IsAdmin, IsAdminOrISP
from .models import TourPlace, Venue
from user.models import User
from django.shortcuts import get_object_or_404
from .serializers import TourplaceSerializer, VenueSerializer, ISPSerializer
from rest_framework.response import Response
from rest_framework import status
# Create your views here.


class TourplaceAPIView(APIView):

    permission_classes = [IsAdminOrISP]

    def get(self, request):
        user = request.user
        if user is not None and user.usertype == 2:
            tourplace = user.tourplace
            serializer = TourplaceSerializer(tourplace)
            return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
        elif user.usertype == 1:
            tourplaces = TourPlace.objects.all()
            serializer = TourplaceSerializer(tourplaces, many=True)
            data = serializer.data
            return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
        return Response({'status': False, 'data': {'msg': 'You have to login.'}}, status=status.HTTP_401_UNAUTHORIZED)

    def post(self, request):
        user = request.user
        if user.usertype == 1:
            data = request.data
            serializer = TourplaceSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
            return Response({'status': False, 'data': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': False, 'data': {'msg': 'You do not any permission to create the tourplace.'}})


class TourplaceUpdateAPIView(APIView):

    permission_classes = [IsAdmin]

    def post(self, request):
        id = request.data["id"]
        place = TourPlace.objects.get(id=id)
        data = request.data
        serializer = TourplaceSerializer(place, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
        return Response({'status': False, 'data': {'msg': 'You do not any permission to create the tourplace.'}})

    def get(self, request, pk, format=None):
        tourplace = get_object_or_404(TourPlace, pk=pk)
        serializer = TourplaceSerializer(tourplace)
        return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)


class TourplaceDeleteAPIView(APIView):

    permission_classes = [IsAdmin]

    def post(self, request):
        id = request.data.get('id')
        if not id:
            return Response({"status": False, "data": {"msg": "Tourplace ID is required."}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tourplace = TourPlace.objects.get(id=id)
            tourplace.delete()
            return Response({"status": True, "data": {"msg": "Successfully deleted."}}, status=status.HTTP_200_OK)
        except tourplace.DoesNotExist:
            return Response({"status": False, "data": {"msg": "Tourplace not found."}}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)


class TourplaceGetAllAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        tourplaces = TourPlace.objects.all()
        serializer = TourplaceSerializer(tourplaces, many=True)
        return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)


class TourplaceGetAllForISPAPIView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        tourplaces = TourPlace.objects.filter(isp=0)
        serializer = TourplaceSerializer(tourplaces, many=True)
        return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)


class TourplaceGetAllForCamAPIView(APIView):
    permission_classes = [IsAdminOrISP]

    def get(self, request):
        user = request.user
        tourplaces = []
        if user.usertype == 1:
            tourplaces = TourPlace.objects.all()
        elif user.usertype == 2:
            tourplaces = TourPlace.objects.filter(isp=user.pk)
        serializer = TourplaceSerializer(tourplaces, many=True)
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
