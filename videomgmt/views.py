from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Header, Footer, Video, SnapShot
from .serializers import HeaderSerializer, FooterSerializer, VideoSerializer, SnatShotSerializer
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
import logging

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

class VideoDeleteAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        video_id = request.data.get('video_id')
        if not video_id:
            return Response({"status": False, "data": {"msg": "Video ID is required."}}, status=status.HTTP_400_BAD_REQUEST)
        try:
            video = Video.objects.get(pk=video_id, client=request.user)
            if video.video_path:
                if default_storage.exists(video.video_path.name):
                    default_storage.delete(video.video_path.name)
            if video.thumbnail:
                if default_storage.exists(video.thumbnail.name):
                    default_storage.delete(video.thumbnail.name)
            video.delete()
            return Response({"status": True, "data": {"msg": "Successfully Deleted."}}, status=status.HTTP_200_OK)
        except Video.DoesNotExist:
            try:
                footer_existence = Video.objects.get(pk = video_id)
                return Response({"status": False, "data": {"msg": "You don't have permission to delete this data."}}, status=status.HTTP_403_FORBIDDEN)
            except Footer.DoesNotExist:
                return Response({"status": False, "data": {"msg": "Video not found."}}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)

class VideoAddAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        tourplace_id = request.data.get('tourplace_id')
        pricing_id = request.data.get('pricing_id')
        data = request.data
        data['tourplace'] = TourPlace.objects.get(id = tourplace_id).pk
        serializer = VideoSerializer(data=data)
        if serializer.is_valid():
            try:
                video = serializer.save(client=request.user, status=False)
                original_filename = os.path.basename(video.video_path.path)
                # If user is type 3, handle subscription and payment logic
                if request.user.usertype == 3:
                    with transaction.atomic():
                        payment_log = PaymentLogs.objects.select_for_update().get(
                            user=request.user.id, price=pricing_id, videoremain__gt=0
                        )
                        payment_log.videoremain -= 1
                        payment_log.save()

                        # Call the external video processing script
                        subprocess.Popen(
                            ['/var/www/htdocs/Video_Backend/otisenv/bin/python', '/var/www/htdocs/Video_Backend/videomgmt/video_processing.py', str(video.id), str(request.user.id), original_filename, str(tourplace_id)]
                        )
                else:
                    # Regular user, just process video and save
                    subprocess.Popen(
                        ['/var/www/htdocs/Video_Backend/otisenv/bin/python', '/var/www/htdocs/Video_Backend/videomgmt/video_processing.py', str(video.id), str(request.user.id), original_filename, str(tourplace_id)]
                    )

                # Return success response
                return Response({"status": True, "data": serializer.data}, status=status.HTTP_201_CREATED)

            except PaymentLogs.DoesNotExist:
                # In case of no valid payment log, clean up and return error
                video_file_path = video.video_path.path
                video.delete()
                if os.path.exists(video_file_path):
                    os.remove(video_file_path)

                return Response({'status': False, "data": "You don't have any remaining case for this subscription."}, status=status.HTTP_400_BAD_REQUEST)

        # If the serializer is not valid, return validation errors
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
            # data = serializer.data
            # num_cli = len(data)
            # for i in range(num_cli):
            #     client = User.objects.get(id = data[i]["client"])
            #     data[i]["client"] = client.username
            #     data[i]["tourplace"] = tourplace.place_name
            return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)

class getHeaderandFooterAPIView(APIView):

    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        tourplaces = request.user.tourplace
        if len(tourplaces) == 0:
            return Response({"status": False, "data": "Admin or ISP can't use this api."}, status=status.HTTP_404_NOT_FOUND)
        tourplace_id = request.user.tourplace[0]
        tourplace = TourPlace.objects.get(id = tourplace_id)
        header = Header.objects.filter(tourplace = tourplace.pk).order_by('?').first()
        footer = Footer.objects.filter(tourplace = tourplace.pk).order_by('?').first()
        if not header or not footer:
            return Response({"status": False, "data": "Header or Footer of this tourplace aren't existed now."}, status=status.HTTP_404_NOT_FOUND)
        header_path = header.video_path.path
        footer_path = footer.video_path.path
        base_url = "https://api.emmysvideos.com/"
        header_path = header_path.replace("/var/www/htdocs/Video_Backend/", base_url)
        footer_path = footer_path.replace("/var/www/htdocs/Video_Backend/", base_url)
        return Response({"status": True, "data": {"header": header_path, "footer": footer_path}}, status=status.HTTP_200_OK)

def download_video(request):
    video_url = request.GET.get('video_url')
    if not video_url:
        raise Http404("Video URL not provided")
    video_path = os.path.join(settings.MEDIA_ROOT, video_url.replace('https://api.emmysvideos.com/media/', '').replace('/', os.sep))
    print(video_path)
    if not os.path.exists(video_path):
        raise Http404(f"Video not found: {video_path}")
    response = FileResponse(open(video_path, 'rb'), as_attachment=True, filename=os.path.basename(video_path))
    return response

class SnapShotAPIView(APIView):

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        client = request.user
        if client.usertype != 3:
            return Response({"status": False, "data": "Admin or ISP can't upload the snapshots."}, status = status.HTTP_400_BAD_REQUEST)
        tourplace_id = client.tourplace[0]
        images = SnapShot.objects.filter(tourplace_id = tourplace_id, client = client)
        serializer = SnatShotSerializer(images, many = True)
        return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        client = request.user
        if client.usertype != 3:
            return Response({"status": False, "data": "Admin or ISP can't upload the snapshots."}, status = status.HTTP_400_BAD_REQUEST)
        tourplace_id = client.tourplace[0]
        images = request.FILES.getlist('image_path')
        if not images:
            return Response({"status": False, "data": "Tourplace and images are required."}, status = status.HTTP_400_BAD_REQUEST)
        snapshots = []
        for image in images:
            snapshot = SnapShot(client = client, tourplace_id = tourplace_id, image_path = image)
            snapshots.append(snapshot)
        SnapShot.objects.bulk_create(snapshots)
        serializer = SnatShotSerializer(snapshots, many = True)
        return Response({"status": True, "data": serializer.data}, status=status.HTTP_201_CREATED)

class SnapShotDeleteAPIView(APIView):

    permission_classes = [IsAuthenticated]
    # parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        client = request.user
        image_ids = request.data.get('image_ids')
        if not image_ids or not isinstance(image_ids, list):
            return Response({"status": False, "data": "Invalid input. 'image_ids' should be a list."}, status=status.HTTP_400_BAD_REQUEST)
        snapshots_to_delete = SnapShot.objects.filter(id__in=image_ids)
        if not snapshots_to_delete.exists():
            return Response({"status": False, "data": "No corresponding images found."}, status=status.HTTP_404_NOT_FOUND)
        unauthorized_images = snapshots_to_delete.filter(client=client)
        if unauthorized_images.count() != snapshots_to_delete.count():
            return Response({"status": False, "data": "You do not have permission to delete some of the images."}, status=status.HTTP_403_FORBIDDEN)
        for snapshot in snapshots_to_delete:
            if snapshot.image_path and os.path.isfile(snapshot.image_path.path):
                os.remove(snapshot.image_path.path)
        snapshots_to_delete.delete()
        return Response({"status": True, "data": f"{len(image_ids)} images successfully deleted."}, status=status.HTTP_200_OK)