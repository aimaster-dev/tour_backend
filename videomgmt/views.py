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
from tourplace.models import Venue
from django.http import Http404, FileResponse
from datetime import datetime
from user.models import User
from payment.models import PaymentLogs
from django.db import transaction
import logging
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from asgiref.sync import async_to_sync
from .video_processing import process_video
import sys


class HeaderAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        return Header.objects.all()

    def get(self, request):
        venue_id = request.query_params.get('venue')
        if venue_id == None:
            headers = self.get_queryset()
            if headers.exists():
                serializer = HeaderSerializer(headers, many=True)
                return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)
        else:
            venue = Venue.objects.get(id=venue_id)
            headers = Header.objects.filter(venue=venue.pk)
            if headers.exists():
                serializer = HeaderSerializer(headers, many=True)
                return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)

    def post(self, request):
        venue_id = request.data.get('venue')
        data = request.data
        data['venue'] = Venue.objects.get(id=venue_id).pk
        serializer = HeaderSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"status": True, "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response({"status": False, "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

# Backup
# class HeaderAPIView(APIView):
#     permission_classes = [IsAdmin]
#     parser_classes = (MultiPartParser, FormParser)

#     def get_queryset(self):
#         if self.request.user.usertype == 1:
#             venue = Venue.objects.first()
#             if venue:
#                 return Header.objects.filter(venue=venue.pk)
#             else:
#                 return Header.objects.none()
#         return Header.objects.filter(user=self.request.user)

#     def get(self, request):
#         venue_id = request.query_params.get('venue')
#         if venue_id == None:
#             headers = self.get_queryset()
#             if headers.exists():
#                 serializer = HeaderSerializer(headers, many=True)
#                 return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
#             else:
#                 return Response({"status": True, "data": []}, status=status.HTTP_200_OK)
#         else:
#             venue = Venue.objects.get(id=venue_id)
#             headers = Header.objects.filter(venue=venue.pk)
#             if headers.exists():
#                 serializer = HeaderSerializer(headers, many=True)
#                 return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
#             else:
#                 return Response({"status": True, "data": []}, status=status.HTTP_200_OK)

#     def post(self, request):
#         venue_id = request.data.get('venue')
#         data = request.data
#         data['venue'] = Venue.objects.get(id=venue_id).pk
#         serializer = HeaderSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save(user=request.user)
#             return Response({"status": True, "data": serializer.data}, status=status.HTTP_201_CREATED)
#         return Response({"status": False, "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


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
                header_existence = Header.objects.get(pk=header_id)
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
            venue = Venue.objects.first()
            if venue:
                return Header.objects.filter(venue=venue.pk)
            else:
                return Footer.objects.none()
        return Footer.objects.filter(user=self.request.user)

    def get(self, request):
        venue_id = request.query_params.get('venue')
        if venue_id == None:
            footers = self.get_queryset()
            if footers.exists():
                serializer = FooterSerializer(footers, many=True)
                return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)
        else:
            venue = Venue.objects.get(id=venue_id)
            footers = Footer.objects.filter(venue=venue.pk)
            if footers.exists():
                serializer = FooterSerializer(footers, many=True)
                return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)

    def post(self, request):
        venue_id = request.data.get('venue')
        data = request.data
        data['venue'] = Venue.objects.get(id=venue_id).pk
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
                footer_existence = Footer.objects.get(pk=footer_id)
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
                footer_existence = Video.objects.get(pk=video_id)
                return Response({"status": False, "data": {"msg": "You don't have permission to delete this data."}}, status=status.HTTP_403_FORBIDDEN)
            except Footer.DoesNotExist:
                return Response({"status": False, "data": {"msg": "Video not found."}}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)


class VideoAddAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        venue_id = request.data.get('venue_id')
        pricing_id = request.data.get('pricing_id')

        # Add logging for request details
        logging.info(
            f"Starting video upload process for user {request.user.username} (ID: {request.user.id})")
        logging.info(f"Venue ID: {venue_id}, Pricing ID: {pricing_id}")

        # Check if video file is present in request
        if 'video_path' not in request.FILES:
            logging.warning(
                f"Video file missing in request from user {request.user.username}")
            return Response({
                "status": False,
                "data": {"video_path": ["Video file is required."]}
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            venue = Venue.objects.get(id=venue_id)
            logging.info(
                f"Found venue: {venue.venue_name} (ID: {venue.id})")
        except Venue.DoesNotExist:
            logging.error(f"Venue not found with ID: {venue_id}")
            return Response({"status": False, "data": {"msg": "Venue not found."}}, status=status.HTTP_404_NOT_FOUND)

        # Create necessary directories
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'videos'), exist_ok=True)
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'temp'), exist_ok=True)
        logging.info("Created necessary directories")

        # Create a new dict with the data we need
        data = {
            'video_path': request.FILES['video_path'],
            'venue': venue.pk
        }

        # Add any other fields from request.data that we need
        for key in request.data:
            if key not in ['video_path', 'venue_id']:
                data[key] = request.data[key]

        serializer = VideoSerializer(data=data)

        if serializer.is_valid():
            try:
                video = serializer.save(client=request.user, status=False)
                original_filename = os.path.basename(video.video_path.name)
                logging.info(
                    f"Created video record with ID: {video.id}, filename: {original_filename}")

                # If user is type 3, handle subscription and payment logic
                if request.user.usertype in [3, 4]:
                    logging.info(
                        f"Processing payment for type 3 user: {request.user.username}")

                    # Check if user has unlimited access
                    if request.user.has_free_recording_access() or venue.is_test:
                        logging.info(
                            f"User {request.user.username} has unlimited access - no decrement needed")
                    else:
                        try:
                            with transaction.atomic():
                                # Log payment search criteria
                                if pricing_id and pricing_id not in ["", "null", "undefined", None]:
                                    logging.info(
                                        f"Searching for payment log with pricing ID: {pricing_id}")
                                    payment_log = PaymentLogs.objects.filter(
                                        user=request.user.id,
                                        price=pricing_id,
                                        videoremain__gt=0
                                    ).first()
                                    if payment_log:
                                        logging.info(
                                            f"Found payment log - ID: {payment_log.id}, Remaining videos: {payment_log.videoremain}")
                                    else:
                                        logging.warning(
                                            f"No payment log found with pricing ID: {pricing_id}")
                                else:
                                    logging.info(
                                        "Searching for free trial payment log")
                                    payment_log = PaymentLogs.objects.filter(
                                        user=request.user.id,
                                        price__isnull=True,
                                        transaction_id__startswith='FREE_TRIAL_',
                                        videoremain__gt=0
                                    ).first()
                                    if payment_log:
                                        logging.info(
                                            f"Found free trial payment log - ID: {payment_log.id}, Remaining videos: {payment_log.videoremain}")
                                    else:
                                        logging.warning(
                                            "No free trial payment log found")

                                if not payment_log:
                                    logging.warning(
                                        f"No remaining video credits for user {request.user.username}")
                                    # Store video ID before deletion for logging
                                    video_id = getattr(video, 'id', None)
                                    video_path = getattr(
                                        video, 'video_path', None)

                                    # Delete file if it exists
                                    if video_path and default_storage.exists(video_path.name):
                                        default_storage.delete(video_path.name)
                                        logging.info(
                                            f"Deleted video file: {video_path.name}")

                                    # Only attempt to delete if we have a valid ID
                                    if video_id is not None:
                                        video.delete()
                                        logging.info(
                                            f"Deleted video record with ID: {video_id}")
                                    else:
                                        logging.warning(
                                            "Video record not deleted - no valid ID")

                                    return Response({
                                        'status': False,
                                        "data": "You don't have any remaining video credits."
                                    }, status=status.HTTP_400_BAD_REQUEST)

                                # Log payment log state before update
                                logging.info(
                                    f"Current video remain count: {payment_log.videoremain}")
                                payment_log.videoremain -= 1
                                payment_log.save()
                                logging.info(
                                    f"Updated payment log, new remaining videos: {payment_log.videoremain}")

                        except Exception as e:
                            logging.error(
                                f"Payment processing error: {str(e)}")
                            logging.error(
                                f"Payment error type: {type(e).__name__}")
                            logging.error(
                                "Payment error details:", exc_info=True)

                            # Store video ID before deletion for logging
                            video_id = getattr(video, 'id', None)
                            video_path = getattr(video, 'video_path', None)

                            # Delete file if it exists
                            if video_path and default_storage.exists(video_path.name):
                                default_storage.delete(video_path.name)
                                logging.info(
                                    f"Cleaned up video file after payment error: {video_path.name}")

                            # Only attempt to delete if we have a valid ID
                            if video_id is not None:
                                video.delete()
                                logging.info(
                                    f"Cleaned up video record after payment error: {video_id}")
                            else:
                                logging.warning(
                                    "Video record not deleted - no valid ID")

                            return Response({
                                'status': False,
                                "data": "Error processing payment. Please try again."
                            }, status=status.HTTP_400_BAD_REQUEST)

                # Process video
                try:
                    logging.info(
                        f"Starting video processing for video ID: {video.id}")
                    process_video(
                        video.id,
                        request.user.id,
                        original_filename,
                        venue
                    )
                    logging.info(
                        f"Successfully processed video ID: {video.id}")
                except ValueError as e:
                    logging.error(
                        f"Video processing failed with ValueError: {str(e)}")
                    if video.video_path and default_storage.exists(video.video_path.name):
                        default_storage.delete(video.video_path.name)
                    video.delete()

                    error_msg = str(e)
                    if "codec" in error_msg.lower():
                        error_msg = "Server configuration error: Video codec not available. Please contact support."

                    return Response({
                        'status': False,
                        "data": f"Video processing failed: {error_msg}"
                    }, status=status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    logging.error(
                        f"Video processing failed with unexpected error: {str(e)}")
                    if video.video_path and default_storage.exists(video.video_path.name):
                        default_storage.delete(video.video_path.name)
                    video.delete()
                    return Response({
                        'status': False,
                        "data": f"Video processing failed: An unexpected error occurred"
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                logging.info(
                    f"Video upload and processing completed successfully for video ID: {video.id}")
                return Response(
                    {"status": True, "data": serializer.data},
                    status=status.HTTP_201_CREATED
                )

            except Exception as e:
                logging.error(f"Error in video creation process: {str(e)}")
                if video.video_path and default_storage.exists(video.video_path.name):
                    default_storage.delete(video.video_path.name)
                if hasattr(video, 'id'):
                    video.delete()
                return Response({
                    'status': False,
                    "data": str(e)
                }, status=status.HTTP_400_BAD_REQUEST)

        logging.error(
            f"Video serializer validation failed: {serializer.errors}")
        return Response(
            {"status": False, "data": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    def get(self, request):
        user = request.user
        venue_id = request.query_params.get("venue")
        videos = []
        if user.usertype == 1:
            if venue_id:
                venue = Venue.objects.get(id=venue_id)
                videos = Video.objects.filter(venue=venue.pk)
            else:
                venue = Venue.objects.all().first()
                videos = Video.objects.filter(venue=venue.pk)
            serializer = VideoSerializer(videos, many=True)
            data = serializer.data
            num_cli = len(data)
            for i in range(num_cli):
                client = User.objects.get(id=data[i]["client"])
                data[i]["client"] = client.username
                data[i]["venue"] = venue.venue_name
            return Response({"status": True, "data": data}, status=status.HTTP_200_OK)
        elif user.usertype == 2:
            if venue_id:
                venue = Venue.objects.get(id=venue_id)
                if venue.isp == user.pk:
                    videos = Video.objects.filter(venue=venue.pk)
                else:
                    Response(
                        {"status": False, "data": "You don't have any permission for this venue."}, status=status.HTTP_200_OK)
            else:
                venue = Venue.objects.filter(isp=user.pk).first()
                videos = Video.objects.filter(venue=venue.pk)
            serializer = VideoSerializer(videos, many=True)
            data = serializer.data
            num_cli = len(data)
            for i in range(num_cli):
                client = User.objects.get(id=data[i]["client"])
                data[i]["client"] = client.username
                data[i]["venue"] = venue.venue_name
            return Response({"status": True, "data": data}, status=status.HTTP_200_OK)
        elif user.usertype in [3,4]:
            venue = Venue.objects.get(id=user.venue[0])
            videos = Video.objects.filter(
                client=user.pk, venue=venue.pk)
            serializer = VideoSerializer(videos, many=True)
            # data = serializer.data
            # num_cli = len(data)
            # for i in range(num_cli):
            #     client = User.objects.get(id = data[i]["client"])
            #     data[i]["client"] = client.username
            #     data[i]["venue"] = venue.venue_name
            return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)


class getHeaderandFooterAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        venues = request.user.venue
        if len(venues) == 0:
            return Response({"status": False, "data": "Admin or ISP can't use this api."}, status=status.HTTP_404_NOT_FOUND)
        venue_id = request.user.venue[0]
        venue = Venue.objects.get(id=venue_id)
        header = Header.objects.filter(
            venue=venue.pk).order_by('?').first()
        footer = Footer.objects.filter(
            venue=venue.pk).order_by('?').first()
        if not header or not footer:
            return Response({"status": False, "data": "Header or Footer of this venue aren't existed now."}, status=status.HTTP_404_NOT_FOUND)
        header_path = header.video_path.path
        footer_path = footer.video_path.path
        base_url = "https://api.dwareapps.com/"
        header_path = header_path.replace(
            "/var/www/htdocs/Video_Backend/", base_url)
        footer_path = footer_path.replace(
            "/var/www/htdocs/Video_Backend/", base_url)
        return Response({"status": True, "data": {"header": header_path, "footer": footer_path}}, status=status.HTTP_200_OK)


def download_video(request):
    video_url = request.GET.get('video_url')
    if not video_url:
        raise Http404("Video URL not provided")
    video_path = os.path.join(settings.MEDIA_ROOT, video_url.replace(
        'https://api.dwareapps.com/media/', '').replace('/', os.sep))
    print(video_path)
    if not os.path.exists(video_path):
        raise Http404(f"Video not found: {video_path}")
    response = FileResponse(open(
        video_path, 'rb'), as_attachment=True, filename=os.path.basename(video_path))
    return response


class SnapShotAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        client = request.user
        if client.usertype not in [3,4]:
            return Response({"status": False, "data": "Admin or ISP can't upload the snapshots."}, status=status.HTTP_400_BAD_REQUEST)

        venue_id = client.venue[0]
        images = SnapShot.objects.filter(
            venue_id=venue_id, client=client)
        serializer = SnatShotSerializer(images, many=True)
        return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)


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


class SnapShotAddAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def send_snapshot_email(self, user, snapshots, remaining_snapshots):
        try:
            logging.info(
                f"Starting email sending process for user {user.email}")
            subject = 'Your Snapshot Have Been Created'

            # Prepare snapshot URLs
            snapshot_data = []
            for snapshot in snapshots:
                snapshot_data.append({
                    'image_url': f"https://api.dwareapps.com/media/{snapshot.image_path}"
                })
            logging.info(
                f"Prepared {len(snapshot_data)} snapshot URLs for email")

            message = render_to_string('snapshot_success_email.html', {
                'user': user,
                'snapshots': snapshot_data,
                'remaining_snapshots': remaining_snapshots
            })
            logging.info("Email template rendered successfully")

            email = EmailMessage(subject, message, to=[user.email])
            email.content_subtype = "html"
            email.send()
            logging.info(f"Successfully sent email to {user.email}")
        except Exception as e:
            logging.error(
                f"Failed to send snapshot email to {user.email}: {str(e)}")
            logging.error(
                f"Email error details: {type(e).__name__}", exc_info=True)
            # Continue with the snapshot upload process

    def post(self, request):
        try:
            logging.info(
                f"Starting snapshot upload process for user {request.user.username}")
            client = request.user
            if client.usertype not in [3,4]:
                logging.warning(
                    f"Unauthorized access attempt by user {client.username} (type {client.usertype})")
                return Response({"status": False, "data": "Admin or ISP can't upload the snapshots."},
                                status=status.HTTP_400_BAD_REQUEST)

            venue_id = client.venue[0]
            logging.info(f"Processing snapshots for venue ID: {venue_id}")
            
            try:
                venue = Venue.objects.get(id=venue_id)
                logging.info(
                    f"Found venue: {venue.venue_name} (ID: {venue.id})")
            except Venue.DoesNotExist:
                logging.error(f"Venue not found with ID: {venue_id}")
                venue = None
                
            images = request.FILES.getlist('image_path')
            if not images:
                logging.warning(
                    f"No images provided by user {client.username}")
                return Response({"status": False, "data": "Venue and images are required."},
                                status=status.HTTP_400_BAD_REQUEST)
            logging.info(f"Received {len(images)} images for processing")

            # Check if user has unlimited access
            if not client.has_free_recording_access() and (not venue or not venue.is_test):
                logging.info(
                    f"Checking snapshot limits for user {client.username}")
                # Check the user's remaining snapshot count
                payment_log = PaymentLogs.objects.filter(
                    user=client.id).order_by('-created_at').first()
                if not payment_log or payment_log.snapshotremain <= 0:
                    logging.warning(
                        f"User {client.username} has no remaining snapshots")
                    return Response({"status": False, "data": "You don't have any remaining snapshots."},
                                    status=status.HTTP_400_BAD_REQUEST)
                logging.info(
                    f"User {client.username} has {payment_log.snapshotremain} snapshots remaining")

            snapshots = []
            for image in images:
                logging.info(f"Processing image: {image.name}")
                snapshot = SnapShot(
                    client=client, venue_id=venue_id, image_path=image)
                snapshots.append(snapshot)

            logging.info(f"Creating {len(snapshots)} snapshot records")
            SnapShot.objects.bulk_create(snapshots)
            logging.info("Snapshot records created successfully")

            # Decrement the snapshot count only if user doesn't have unlimited access
            if not client.has_free_recording_access() and (not venue or not venue.is_test):
                payment_log.snapshotremain -= len(images)
                payment_log.save()
                remaining_snapshots = payment_log.snapshotremain
                logging.info(
                    f"Updated remaining snapshots count to {remaining_snapshots}")
            else:
                remaining_snapshots = "Unlimited"
                logging.info("User has unlimited snapshot access")

            # Send email with snapshots
            self.send_snapshot_email(client, snapshots, remaining_snapshots)

            serializer = SnatShotSerializer(snapshots, many=True)
            logging.info(
                f"Successfully completed snapshot upload for user {client.username}")
            return Response({"status": True, "data": serializer.data}, status=status.HTTP_201_CREATED)

        except Exception as e:
            logging.error(f"Error in SnapShotAddAPIView: {str(e)}")
            logging.error(f"Error type: {type(e).__name__}", exc_info=True)
            return Response({"status": False, "data": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
