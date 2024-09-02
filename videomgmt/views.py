from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Header, Footer, Video
from .serializers import HeaderSerializer, FooterSerializer, VideoSerializer
from user.permissions import IsAdmin
from django.core.files.storage import default_storage
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
import subprocess
from django.conf import settings
import os
from tourplace.models import TourPlace
from django.http import Http404, FileResponse
from datetime import datetime
from user.models import User
from payment.models import PaymentLogs
from django.db import transaction

class HeaderAPIView(APIView):
    permission_classes = [IsAdmin]
    parser_classes = (MultiPartParser, FormParser)
    
    def get_queryset(self):
        if self.request.user.usertype == 1:
            tourplace = TourPlace.objects.first()
            if tourplace:
                return Header.objects.filter(tourplace = tourplace.pk)
            else:
                return Header.objects.none()
        return Header.objects.filter(user=self.request.user)
    
    def get(self, request):
        tourplace_id = request.query_params.get('tourplace')
        if tourplace_id == None:
            headers = self.get_queryset()
            if headers.exists():
                serializer = HeaderSerializer(headers, many=True)
                return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)
        else:
            tourplace = TourPlace.objects.get(id = tourplace_id)
            headers = Header.objects.filter(tourplace = tourplace.pk)
            if headers.exists():
                    serializer = HeaderSerializer(headers, many=True)
                    return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)
    
    def post(self, request):
        tourplace_id = request.data.get('tourplace')
        data = request.data
        data['tourplace'] = TourPlace.objects.get(id = tourplace_id).pk
        serializer = HeaderSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response({"status": True, "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response({"status": False, "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
class HeaderDeleteAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAdmin]
    def post(self, request, *args, **kwargs):
        header_id = request.data.get('header_id')
        if not header_id:
            return Response({"status": False, "data": {"msg": "Header ID is required."}}, status=status.HTTP_400_BAD_REQUEST)
        try:
            header = Header.objects.get(pk=header_id, user=request.user)
            if header.video_path:
                if default_storage.exists(header.video_path.name):
                    default_storage.delete(header.video_path.name)
            if header.thumbnail:
                if default_storage.exists(header.thumbnail.name):
                    default_storage.delete(header.thumbnail.name)
            header.delete()
            return Response({"status": True}, status=status.HTTP_200_OK)
        except Header.DoesNotExist:
            try:
                header_existence = Header.objects.get(pk = header_id)
                return Response({"status": False, "data": {"msg": "You don't have permission to delete this data."}}, status=status.HTTP_403_FORBIDDEN)
            except Header.DoesNotExist:
                return Response({"status": False, "data": {"msg": "Header not found."}}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)

class FooterAPIView(APIView):
    permission_classes = [IsAdmin]
    parser_classes = (MultiPartParser, FormParser)
    
    def get_queryset(self):
        if self.request.user.usertype == 1:
            tourplace = TourPlace.objects.first()
            if tourplace:
                return Header.objects.filter(tourplace = tourplace.pk)
            else:
                return Footer.objects.none()
        return Footer.objects.filter(user=self.request.user)
    
    def get(self, request):
        tourplace_id = request.query_params.get('tourplace')
        if tourplace_id == None:
            footers = self.get_queryset()
            if footers.exists():
                serializer = FooterSerializer(footers, many=True)
                return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)
        else:
            tourplace = TourPlace.objects.get(id = tourplace_id)
            footers = Footer.objects.filter(tourplace = tourplace.pk)
            if footers.exists():
                serializer = FooterSerializer(footers, many=True)
                return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)
    
    def post(self, request):
        tourplace_id = request.data.get('tourplace')
        data = request.data
        data['tourplace'] = TourPlace.objects.get(id = tourplace_id).pk
        serializer = FooterSerializer(data=data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response({"status": True, "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response({"status": False, "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
class FooterDeleteAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAdmin]
    def post(self, request, *args, **kwargs):
        footer_id = request.data.get('footer_id')
        if not footer_id:
            return Response({"status": False, "data": {"msg": "Footer ID is required."}}, status=status.HTTP_400_BAD_REQUEST)
        try:
            footer = Footer.objects.get(pk=footer_id, user=request.user)
            if footer.video_path:
                if default_storage.exists(footer.video_path.name):
                    default_storage.delete(footer.video_path.name)
            if footer.thumbnail:
                if default_storage.exists(footer.thumbnail.name):
                    default_storage.delete(footer.thumbnail.name)
            footer.delete()
            return Response({"status": True}, status=status.HTTP_200_OK)
        except Footer.DoesNotExist:
            try:
                footer_existence = Footer.objects.get(pk = footer_id)
                return Response({"status": False, "data": {"msg": "You don't have permission to delete this data."}}, status=status.HTTP_403_FORBIDDEN)
            except Footer.DoesNotExist:
                return Response({"status": False, "data": {"msg": "Footer not found."}}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)

class VideoAddAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        tourplace_id = request.data.get('tourplace_id')
        pricing_id = request.data.get('pricing_id')
        if not tourplace_id:
            return Response({'error': 'Tourplace ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            tourplace = TourPlace.objects.get(pk=tourplace_id)
        except TourPlace.DoesNotExist:
            return Response({'error': 'Invalid Tourplace ID'}, status=status.HTTP_400_BAD_REQUEST)
        if 'video_path' not in request.FILES:
            return Response({'error': 'Video file is required'}, status=status.HTTP_400_BAD_REQUEST)
        data = request.data
        data['client'] = request.user.pk
        data['tourplace'] = tourplace_id
        serializer = VideoSerializer(data=data)
        if serializer.is_valid():
            uploaded_video = request.FILES['video_path']
            original_filename = uploaded_video.name
            current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
            temp_video_path = os.path.join(settings.MEDIA_ROOT, f'temp_uploaded_video_{request.user.username}_{current_time}.webm')
            with open(temp_video_path, 'wb+') as temp_file:
                for chunk in uploaded_video.chunks():
                    temp_file.write(chunk)
            try:
                print(request.user.usertype)
                if request.user.usertype == 3:
                    with transaction.atomic():
                        video = serializer.save(client=request.user, tourplace=tourplace, status=False)
                        payment_log = PaymentLogs.objects.select_for_update().get(
                            user=request.user.id, price=pricing_id, remain__gt=0
                        )
                        payment_log.remain -= 1
                        payment_log.save()
                        subprocess.Popen(
                            ['/var/www/htdocs/Video_Backend/otisenv/bin/python', '/var/www/htdocs/Video_Backend/videomgmt/video_processing.py', str(video.id), str(request.user.id), original_filename, str(tourplace_id)]
                        )
                else:
                    video = serializer.save(client=request.user, tourplace=tourplace, status=False)
                    subprocess.Popen(
                        ['/var/www/htdocs/Video_Backend/otisenv/bin/python', '/var/www/htdocs/Video_Backend/videomgmt/video_processing.py', str(video.id), str(request.user.id), original_filename, str(tourplace_id)]
                    )
            except PaymentLogs.DoesNotExist:
                video_file_path = video.video_path.path
                video.delete()
                if os.path.exists(video_file_path):
                    os.remove(video_file_path)
                if os.path.exists(temp_video_path):
                    os.remove(temp_video_path)
                return Response({'status': False, "data": "You don't have any remaining case for this subscription."}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"status": True, "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response({"status": False, "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        user = request.user
        tourplace_id = request.query_params.get("tourplace")
        videos = []
        if user.usertype == 1:
            if tourplace_id:
                tourplace = TourPlace.objects.get(id = tourplace_id)
                videos = Video.objects.filter(tourplace = tourplace.pk)
            else:
                tourplace = TourPlace.objects.all().first()
                videos = Video.objects.filter(tourplace = tourplace.pk)
            serializer = VideoSerializer(videos, many = True)
            data = serializer.data
            num_cli = len(data)
            for i in range(num_cli):
                client = User.objects.get(id = data[i]["client"])
                data[i]["client"] = client.username
                data[i]["tourplace"] = tourplace.place_name
            return Response({"status": True, "data": data}, status=status.HTTP_200_OK)
        elif user.usertype == 2:
            if tourplace_id:
                tourplace = TourPlace.objects.get(id = tourplace_id)
                if tourplace.isp == user.pk:
                    videos = Video.objects.filter(tourplace = tourplace.pk)
                else:
                   Response({"status": False, "data": "You don't have any permission for this tourplace."}, status=status.HTTP_200_OK)
            else:
                tourplace = TourPlace.objects.filter(isp = user.pk).first()
                videos = Video.objects.filter(tourplace = tourplace.pk)
            serializer = VideoSerializer(videos, many = True)
            data = serializer.data
            num_cli = len(data)
            for i in range(num_cli):
                client = User.objects.get(id = data[i]["client"])
                data[i]["client"] = client.username
                data[i]["tourplace"] = tourplace.place_name
            return Response({"status": True, "data": data}, status=status.HTTP_200_OK)
        elif user.usertype == 3:
            tourplace = TourPlace.objects.get(id = user.tourplace[0])
            videos = Video.objects.filter(client = user.pk, tourplace = tourplace.pk)
            serializer = VideoSerializer(videos, many = True)
            data = serializer.data
            num_cli = len(data)
            for i in range(num_cli):
                client = User.objects.get(id = data[i]["client"])
                data[i]["client"] = client.username
                data[i]["tourplace"] = tourplace.place_name
            return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
        
def download_video(request):
    video_url = request.GET.get('video_url')
    if not video_url:
        raise Http404("Video URL not provided")
    video_path = os.path.join(settings.MEDIA_ROOT, video_url.replace('https://api.emmysvideos.com/media/', '').replace('/', os.sep))
    if not os.path.exists(video_path):
        raise Http404("Video not found")
    response = FileResponse(open(video_path, 'rb'), as_attachment=True, filename=os.path.basename(video_path))
    return response