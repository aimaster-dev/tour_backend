from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from user.permissions import IsAdmin, IsISP
from .models import Price
from django.shortcuts import get_object_or_404
from .serializers import PriceSerializer
from rest_framework.response import Response
from rest_framework import status
from tourplace.models import Venue
# Create your views here.


class PriceAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.usertype == 1 or user.usertype == 2:
            venue_id = request.data.get('venue')
            data = request.data.copy()
            data["venue"] = Venue.objects.get(id=venue_id).pk
            serializer = PriceSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
            return Response({'status': False, 'data': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'status': False, 'data': {"msg": "You don't have any permission to creat price."}}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def get(self, request, pk, format=None):
        price = get_object_or_404(Price, pk=pk)
        serializer = PriceSerializer(price)
        return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)


class PriceUpdateAPIView(APIView):

    permission_classes = [IsISP, IsAdmin]

    def post(self, request):
        id = request.data["id"]
        price = Price.objects.get(id=id)
        venue_id = request.data.get("venue")
        data = request.data.copy()
        data["venue"] = Venue.objects.get(id=venue_id).pk
        serializer = PriceSerializer(price, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
        else:
            return Response({'status': False, 'data': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class PriceDeleteAPIView(APIView):

    permission_classes = [IsISP, IsAdmin]

    def post(self, request):
        id = request.data.get('id')
        if not id:
            return Response({"status": False, "data": {"msg": "Price ID is required."}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            price = Price.objects.get(id=id)
            price.delete()
            return Response({"status": True, "data": {"msg": "Successfully Deleted."}}, status=status.HTTP_200_OK)
        except price.DoesNotExist:
            return Response({"status": False, "data": {"msg": "Price not found."}}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)


class PriceGetAllAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        venue_id = request.query_params.get("venue")
        Prices = []
        if venue_id:
            venue = Venue.objects.get(id=venue_id)
            Prices = Price.objects.filter(venue=venue.pk)
        else:
            if user.usertype == 1:
                venue_ids = Venue.objects.all().values_list('id')
                if venue_ids is None:
                    return Response({'status': True, 'data': []}, status=status.HTTP_200_OK)
                else:
                    Prices = Price.objects.filter(venue__in=venue_ids)
            elif user.usertype == 2:
                venue = Venue.objects.filter(isp=user.pk).first()
                Prices = Price.objects.filter(venue=venue.pk)
            elif user.usertype == 3 or user.usertype == 4:
                venue_id = user.venue[0]
                venue = Venue.objects.get(id=venue_id)
                Prices = Price.objects.filter(venue=venue.pk)
        serializer = PriceSerializer(Prices, many=True)
        return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
