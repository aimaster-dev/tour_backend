from datetime import timezone
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
# from .models import Camera, Stream
from .models import Camera
from .serializers import CameraSerializer, CameraUpdateSerializer
from user.permissions import IsAdmin, IsISP, IsClient
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from .utils import convert_rtsp_to_hls, get_output_dir, stop_stream
import requests
import json
from user.models import User
from tourplace.models import Venue
from .camera import LiveWebCam
from django.http.response import StreamingHttpResponse
from tourvideoproject.utils import LoggerHelper
import traceback
from rest_framework import viewsets, filters
from rest_framework.pagination import PageNumberPagination

# Configure logger for this module
logger = LoggerHelper.get_logger('camera')


def gen(camera, stream_id):
    while len(Stream.objects.filter(id=stream_id)) != 0:
        stream_record = Stream.objects.get(id=stream_id)
        print(stream_id)
        if not stream_record.is_active:
            break
        frame = camera.get_frame()
        if frame is None:
            print("Error: Frame is None, skipping...")
            # Optionally, you can break the loop or continue based on your needs
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')


class CameraClientAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def get(self, request):
        try:
            # Log the incoming request
            LoggerHelper.log_api_request(
                logger, request, "Client camera list request received")

            venue = request.data.get("venue")
            user = request.user

            logger.info(
                f"Request parameters: venue={venue}, user_type={user.usertype}")

            if venue is None and user.usertype == 2:
                logger.info(
                    f"ISP user without specified venue, fetching first venue for ISP: {user.pk}")
                try:
                    venue = Venue.objects.filter(isp=user.pk).first()
                    if not venue:
                        logger.warning(
                            f"No venue found for ISP with ID: {user.pk}")
                        return Response({'status': False, 'error': 'No venue found for this ISP'}, status=status.HTTP_404_NOT_FOUND)

                    logger.info(
                        f"Found venue: {venue.venue_name} (ID: {venue.pk})")
                    cameras = Camera.objects.filter(venue=venue.pk)
                except Exception as tp_error:
                    logger.error(
                        f"Error finding venue for ISP: {str(tp_error)}")
                    return Response({'status': False, 'error': f'Error finding venue: {str(tp_error)}'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                logger.info(
                    f"Fetching cameras for specified venue: {venue}")
                try:
                    cameras = Camera.objects.filter(venue=venue)
                except Exception as cam_error:
                    logger.error(f"Error filtering cameras: {str(cam_error)}")
                    return Response({'status': False, 'error': f'Error filtering cameras: {str(cam_error)}'}, status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"Found {len(cameras)} cameras")

            if len(cameras) != 0:
                serializer = CameraUpdateSerializer(cameras, many=True)

                # Log successful response
                LoggerHelper.log_api_response(
                    logger,
                    request,
                    status.HTTP_200_OK,
                    f"Successfully retrieved {len(cameras)} cameras for client"
                )

                return Response({'status': True, 'data': serializer.data})
            else:
                logger.warning("No cameras found for the specified venue")
                return Response({'status': False, 'error': 'There is no cameras now.'}, status=400)

        except Exception as e:
            # Log the exception with full traceback
            LoggerHelper.log_exception(
                logger, request, e, f"Error retrieving cameras for client: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return Response({'status': False, 'error': str(e)}, status=400)


class CameraAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def get(self, request):
        try:
            # Log the incoming request
            LoggerHelper.log_api_request(
                logger, request, "Camera list request received")

            user = request.user
            venue_id = request.query_params.get("venue")
            cameras = []

            # Log request parameters
            logger.info(
                f"Request parameters: venue_id={venue_id}, user_type={user.usertype}")

            if user.usertype == 1:  # Admin
                logger.info("Admin user: fetching all cameras")
                if venue_id:
                    venue = Venue.objects.get(id=venue_id)
                    cameras = Camera.objects.filter(venue=venue)
                else:
                    cameras = Camera.objects.all()
            elif user.usertype == 2:  # ISP
                logger.info(f"ISP user: fetching cameras for ISP: {user.pk}")
                if venue_id:
                    venue = Venue.objects.get(id=venue_id, isp=user)
                    cameras = Camera.objects.filter(venue=venue, isp=user)
                else:
                    cameras = Camera.objects.filter(isp=user)
            elif user.usertype == 3 or user.usertype == 4:  # Customer or client
                logger.info(
                    f"Customer user: fetching cameras for customer: {user.pk}")
                if venue_id:
                    # Check if the venue belongs to the customer
                    if venue_id not in user.venue:
                        return Response({'status': False, 'error': 'You do not have access to this venue'},
                                        status=status.HTTP_403_FORBIDDEN)
                    venue = Venue.objects.get(id=venue_id)
                    cameras = Camera.objects.filter(venue=venue)
                else:
                    # Get all cameras from customer's venues
                    venue_ids = user.venue
                    isp = user.isp
                    cameras = Camera.objects.filter(
                                Q(venue__id__in=venue_ids) | Q(isp=isp)
                            )
            else:
                logger.warning(f"Invalid user type: {user.usertype}")
                return Response({'status': False, 'error': 'Invalid user type'},
                                status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"Found {len(cameras)} cameras")
            serializer = CameraUpdateSerializer(cameras, many=True)

            # Log successful response
            LoggerHelper.log_api_response(
                logger,
                request,
                status.HTTP_200_OK,
                f"Successfully retrieved {len(cameras)} cameras"
            )

            return Response({'status': True, 'data': serializer.data})

        except Venue.DoesNotExist:
            logger.error(f"Venue not found: {venue_id}")
            return Response({'status': False, 'error': 'Venue not found'},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            # Log the exception with full traceback
            LoggerHelper.log_exception(
                logger, request, e, f"Error retrieving cameras: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return Response({'status': False, 'error': str(e)}, status=400)

    def post(self, request):
        try:
            # Log the incoming request
            LoggerHelper.log_api_request(
                logger, request, "Camera creation request received")

            data = request.data
            user = request.user

            logger.info(f"Request data: {data}")
            logger.info(f"User type: {user.usertype}")

            if user.usertype != 2:  # Only ISP can create cameras
                logger.warning(
                    f"User type {user.usertype} attempted to create a camera")
                return Response({'status': False, 'error': 'Only ISP users can create cameras'},
                                status=status.HTTP_403_FORBIDDEN)

            rtsp_url = data.get("rtsp_url")
            if not rtsp_url:
                logger.error("Missing required field: rtsp_url")
                return Response({'status': False, 'error': 'RTSP URL is required'},
                                status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"Processing RTSP URL: {rtsp_url}")
            output_dir = get_output_dir(rtsp_url)
            logger.info(f"Generated output directory: {output_dir}")

            camdata = {
                "rtsp_url": rtsp_url,
                "camera_name": data.get("camera_name"),
                "output_url": output_dir
            }

            venue_id = data.get('venue')
            if not venue_id:
                logger.error("Missing required field: venue")
                return Response({'status': False, 'error': 'Venue ID is required'},
                                status=status.HTTP_400_BAD_REQUEST)

            try:
                # Verify that the venue belongs to the ISP
                venue = Venue.objects.get(id=venue_id, isp=user)
                logger.info(
                    f"Found venue: {venue.venue_name} (ID: {venue.pk})")
            except Venue.DoesNotExist:
                logger.error(
                    f"Venue with ID {venue_id} not found or not owned by ISP")
                return Response({'status': False, 'error': 'Venue not found or not owned by you'},
                                status=status.HTTP_404_NOT_FOUND)

            serializer = CameraSerializer(data=camdata)
            if serializer.is_valid():
                logger.info("Camera data validated successfully")
                serializer.save(isp=user, venue=venue)
                logger.info(
                    f"Camera saved with ID: {serializer.data.get('id', 'unknown')}")

                output = serializer.data
                output['venue'] = [{
                    'id': venue.pk,
                    'venue_name': venue.venue_name
                }]

                # Log successful response
                LoggerHelper.log_api_response(
                    logger,
                    request,
                    status.HTTP_201_CREATED,
                    f"Successfully created camera: {output.get('camera_name')}"
                )

                return Response({"status": True, "data": output}, status=status.HTTP_201_CREATED)
            else:
                logger.error(f"Validation errors: {serializer.errors}")
                return Response({"status": False, "data": {"msg": serializer.errors}},
                                status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            # Log the exception with full traceback
            LoggerHelper.log_exception(
                logger, request, e, f"Error creating camera: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return Response({'status': False, 'error': str(e)}, status=400)


class CameraUpdateAPIView(APIView):
    permission_classes = [IsISP]
    parser_classes = (MultiPartParser, FormParser)

    def get(self, request, pk, format=None):
        try:
            # Log the incoming request
            LoggerHelper.log_api_request(
                logger, request, f"Camera detail request received for ID: {pk}")

            isp = request.user
            camera_id = pk

            logger.info(
                f"Fetching camera with ID: {camera_id} for ISP: {isp.id}")

            if isp is not None:
                try:
                    camera = Camera.objects.get(isp=isp, id=camera_id)
                    logger.info(f"Found camera: {camera.camera_name}")
                    serializer = CameraUpdateSerializer(camera)

                    # Log successful response
                    LoggerHelper.log_api_response(
                        logger,
                        request,
                        status.HTTP_200_OK,
                        f"Successfully retrieved camera details for ID: {pk}"
                    )

                    return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)
                except Camera.DoesNotExist:
                    logger.warning(
                        f"Camera with ID {camera_id} not found for ISP {isp.id}")
                    return Response({'status': False, 'error': 'Camera not found'}, status=status.HTTP_404_NOT_FOUND)
            else:
                logger.warning("Unauthenticated request")
                return Response({'status': False, 'error': 'You have to login in this site.'}, status=400)

        except Exception as e:
            # Log the exception with full traceback
            LoggerHelper.log_exception(
                logger, request, e, f"Error retrieving camera details: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return Response({'status': False, 'error': str(e)}, status=400)

    def post(self, request):
        try:
            # Log the incoming request
            LoggerHelper.log_api_request(
                logger, request, "Camera update request received")

            camera_id = request.data.get('id')
            logger.info(f"Updating camera with ID: {camera_id}")

            if not camera_id:
                logger.error("Missing required field: id")
                return Response({'status': False, 'error': 'Camera ID is required'}, status=status.HTTP_400_BAD_REQUEST)

            venue_id = request.data.get('venue')
            if not venue_id:
                logger.error("Missing required field: venue")
                return Response({'status': False, 'error': 'Venue ID is required'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                venue = Venue.objects.get(id=venue_id)
                logger.info(
                    f"Found venue: {venue.venue_name} (ID: {venue.pk})")
            except Venue.DoesNotExist:
                logger.error(f"Venue with ID {venue_id} not found")
                return Response({'status': False, 'error': f'Venue with ID {venue_id} not found'}, status=status.HTTP_404_NOT_FOUND)

            try:
                camera = Camera.objects.get(id=camera_id, isp=request.user)
                logger.info(f"Found camera: {camera.camera_name}")
            except Camera.DoesNotExist:
                logger.error(
                    f"Camera with ID {camera_id} not found for this ISP")
                return Response({'status': False, 'error': 'Camera not found or you do not have permission'}, status=status.HTTP_404_NOT_FOUND)

            origin_dir = camera.output_url
            if not origin_dir:
                logger.error("Origin directory is not set for this camera")
                return Response({'status': False, 'error': 'Origin Dir is not existed now.'}, status=400)

            origin_dir = origin_dir.lstrip('/')
            logger.info(f"Original output directory: {origin_dir}")

            # stop_stream(origin_dir)
            data = request.data
            rtsp_url = data.get("rtsp_url")
            if not rtsp_url:
                logger.error("Missing required field: rtsp_url")
                return Response({'status': False, 'error': 'RTSP URL is required'}, status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"New RTSP URL: {rtsp_url}")
            output_dir = get_output_dir(rtsp_url)
            logger.info(f"New output directory: {output_dir}")

            camdata = {
                "rtsp_url": rtsp_url,
                "output_url": output_dir,
                "camera_name": data.get("camera_name"),
            }

            serializer = CameraUpdateSerializer(
                camera, data=camdata, partial=True)
            if serializer.is_valid():
                logger.info("Camera data validated successfully")
                serializer.save(venue=venue)
                logger.info(f"Camera updated successfully")

                # Log successful response
                LoggerHelper.log_api_response(
                    logger,
                    request,
                    status.HTTP_200_OK,
                    f"Successfully updated camera: {camera.camera_name}"
                )

                return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
            else:
                logger.error(f"Validation errors: {serializer.errors}")
                return Response({"status": False, "data": {"msg": serializer.errors}})

        except Camera.DoesNotExist:
            try:
                camera_existence = Camera.objects.get(id=camera_id)
                logger.warning(
                    f"Permission denied: Camera exists but belongs to another ISP")
                return Response({"status": False, "data": {"msg": "You don't have permission to update this camera."}}, status=status.HTTP_403_FORBIDDEN)
            except Camera.DoesNotExist:
                logger.error(f"Camera with ID {camera_id} not found")
                return Response({"status": False, "data": {"msg": "Camera not found."}}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            # Log the exception with full traceback
            LoggerHelper.log_exception(
                logger, request, e, f"Error updating camera: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)


class CameraDeleteAPIView(APIView):
    permission_classes = [IsISP]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        try:
            # Log the incoming request
            LoggerHelper.log_api_request(
                logger, request, "Camera deletion request received")

            camera_id = request.data.get('id')
            logger.info(f"Deleting camera with ID: {camera_id}")

            if not camera_id:
                logger.error("Missing required field: id")
                return Response({"status": False, "data": {"msg": "Camera ID is required."}}, status=status.HTTP_400_BAD_REQUEST)

            try:
                camera = Camera.objects.get(id=camera_id, isp=request.user)
                logger.info(f"Found camera: {camera.camera_name}")
            except Camera.DoesNotExist:
                try:
                    camera_existence = Camera.objects.get(id=camera_id)
                    logger.warning(
                        f"Permission denied: Camera exists but belongs to another ISP")
                    return Response({"status": False, "data": {"msg": "You don't have permission to delete this camera."}}, status=status.HTTP_403_FORBIDDEN)
                except Camera.DoesNotExist:
                    logger.error(f"Camera with ID {camera_id} not found")
                    return Response({"status": False, "data": {"msg": "Camera not found."}}, status=status.HTTP_404_NOT_FOUND)

            output_url = camera.output_url
            if not output_url:
                logger.error("Output URL is not set for this camera")
                return Response({'status': False, 'error': 'Origin Dir is not existed now.'}, status=400)

            output_url = output_url.lstrip('/')
            logger.info(f"Stopping stream for output URL: {output_url}")

            try:
                stop_stream(output_url)
                logger.info("Stream stopped successfully")
            except Exception as stream_error:
                logger.warning(f"Error stopping stream: {str(stream_error)}")
                # Continue with deletion even if stream stopping fails

            camera.delete()
            logger.info(f"Camera deleted successfully")

            # Log successful response
            LoggerHelper.log_api_response(
                logger,
                request,
                status.HTTP_200_OK,
                f"Successfully deleted camera with ID: {camera_id}"
            )

            return Response({"status": True, "data": {"msg": "Successfully Deleted."}}, status=status.HTTP_200_OK)

        except Exception as e:
            # Log the exception with full traceback
            LoggerHelper.log_exception(
                logger, request, e, f"Error deleting camera: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)

# class CameraRestartAPIView(APIView):
#     permission_classes = [IsISP]
#     parser_classes = (MultiPartParser, FormParser)

#     def post(self, request):
#         camera_id = request.data.get('id')
#         if not camera_id:
#             return Response({"status": False, "data": {"msg": "Header ID is required."}}, status=status.HTTP_400_BAD_REQUEST)
#         try:
#             camera = Camera.objects.get(id=camera_id, isp=request.user)
#             output_url = camera.output_url
#             stop_stream(output_url)
#             data = {
#                 "camera_name": camera.camera_name,
#                 "camera_ip": camera.camera_ip,
#                 "camera_port": camera.camera_port,
#                 "camera_user_name": camera.camera_user_name,
#                 "password": camera.password,
#                 "output_url": camera.output_url
#             }
#             rtsp_url = "rtsp://" + data["camera_user_name"] + ":" + data["password"] + "@" + data["camera_ip"] + ":" + data["camera_port"] + "/"
#             # convert_rtsp_to_hls(rtsp_url, data["output_url"])
#             return Response({"status": True, "data": {"msg": "Successfully Restarted."}}, status=status.HTTP_200_OK)
#         except Camera.DoesNotExist:
#             try:
#                 camera_existence = Camera.objects.get(id = camera_id)
#                 return Response({"status": False, "data": {"msg": "You don't have permission to delete this camera."}}, status=status.HTTP_403_FORBIDDEN)
#             except Camera.DoesNotExist:
#                 return Response({"status": False, "data": {"msg": "Camera not found."}}, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)

# class CameraCheckAPIView(APIView):
#     def post(self, request):
#         userdata = request.data
#         ip_addr = userdata["camera_ip"]
#         userName = userdata["userName"]
#         password = userdata["password"]

#         url = f'https://{ip_addr}/api.cgi?cmd=Login'
#         headers = {
#             'Content-Type': 'application/json'
#         }
#         data = [
#             {
#                 "cmd": "Login",
#                 "param": {
#                     "User": {
#                         "Version": "0",
#                         "userName": userName,
#                         "password": password
#                     }
#                 }
#             }
#         ]
#         try:
#             response = requests.get(url, headers=headers, data=json.dumps(data), verify=False)
#             response.raise_for_status()

#             # Parse the JSON response
#             data = json.loads(response.text)
#             return Response({"status": True, "data": "Connected"}, status=status.HTTP_200_OK)

#         except requests.exceptions.HTTPError as http_err:
#             return Response({"status": False, "data": f'HTTP error occurred: {http_err}', 'content': response.content.decode()}, status=status.HTTP_400_BAD_REQUEST)
#         except requests.exceptions.ConnectionError as conn_err:
#             return Response({"status": False, "data": f'Connection error occurred: {conn_err}'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
#         except requests.exceptions.Timeout as timeout_err:
#             return Response({"status": False, "data": f'Timeout error occurred: {timeout_err}'}, status=status.HTTP_504_GATEWAY_TIMEOUT)
#         except requests.exceptions.RequestException as req_err:
#             return Response({"status": False, "data": f'Request error occurred: {req_err}'}, status=status.HTTP_400_BAD_REQUEST)
#         except json.JSONDecodeError as json_err:
#             return Response({"status": False, "data": f'JSON decode error: {json_err}', 'content': response.text}, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as err:
#             return Response({"status": False, "data": str(err)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# class CameraStreamingAPIView(APIView):

#     def get(self, request, pk, userid, format=None):
#         camera_id = pk
#         print(pk)
#         if not camera_id:
#             return Response({"status": False, "data": {"msg": "Camera ID is required."}}, status=status.HTTP_400_BAD_REQUEST)
#         try:
#             print(userid)
#             user = User.objects.filter(id = userid).first()
#             if not user:
#                 Response({"status": False, "data": {"msg": "You don't have any permission to access this camera."}}, status=status.HTTP_403_FORBIDDEN)
#             camera = Camera.objects.get(id=camera_id)
#             print(camera_id)
#             username = camera.camera_user_name
#             password = camera.password
#             ip_addr = camera.camera_ip
#             port = camera.camera_port
#             stream_url = f"rtsp://{username}:{password}@{ip_addr}:{port}/"
#             print(stream_url)
#             stream_record, created = Stream.objects.get_or_create(
#                 stream_url=stream_url,
#                 user=user,

#                 defaults={'is_active': True}
#             )
#             if not created:
#                 stream_record.is_active = True
#                 stream_record.save()
#             print(created)
#             return StreamingHttpResponse(gen(LiveWebCam(stream_url), stream_record.id), content_type = 'multipart/x-mixed-replace; boundary=frame')
#         except Camera.DoesNotExist:
#             try:
#                 camera_existence = Camera.objects.get(id = camera_id)
#                 return Response({"status": False, "data": {"msg": "You don't have permission to delete this camera."}}, status=status.HTTP_403_FORBIDDEN)
#             except Camera.DoesNotExist:
#                 return Response({"status": False, "data": {"msg": "Camera not found."}}, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)

#     def post(self, request, pk, userid, format=None):
#         camera_id = pk
#         if not camera_id:
#             return Response({"status": False, "data": {"msg": "Camera ID is required."}}, status=status.HTTP_400_BAD_REQUEST)
#         try:
#             user = User.objects.filter(id = userid).first()
#             if not user:
#                 Response({"status": False, "data": {"msg": "You don't have any permission to access this camera."}}, status=status.HTTP_403_FORBIDDEN)
#             camera = Camera.objects.get(id=camera_id)
#             username = camera.camera_user_name
#             password = camera.password
#             ip_addr = camera.camera_ip
#             port = camera.camera_port
#             stream_url = f"rtsp://{username}:{password}@{ip_addr}:{port}/"
#             stream_record = Stream.objects.filter(stream_url=stream_url, user=user).first()
#             if stream_record:
#                 stream_record.is_active = False
#                 stream_record.save()
#                 stream_record.delete()
#                 return Response({"status": True, "data": {"msg": "Stream stopped"}}, status=status.HTTP_200_OK)
#             else:
#                 return Response({"status": False, "data": {"msg": "Stream not found"}}, status=status.HTTP_404_NOT_FOUND)
#         except Camera.DoesNotExist:
#             try:
#                 camera_existence = Camera.objects.get(id = camera_id)
#                 return Response({"status": False, "data": {"msg": "You don't have permission to delete this camera."}}, status=status.HTTP_403_FORBIDDEN)
#             except Camera.DoesNotExist:
#                 return Response({"status": False, "data": {"msg": "Camera not found."}}, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)


class CameraPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class CameraViewSet(viewsets.ModelViewSet):
    serializer_class = CameraSerializer
    permission_classes = [IsAdmin]
    pagination_class = CameraPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['venue']
    search_fields = ['camera_name', 'rtsp_url']
    ordering_fields = ['created_at', 'camera_name']

    def get_queryset(self):
        # ISP can only see their own cameras
        return Camera.objects.all()

    def perform_create(self, serializer):
        serializer.save(isp=self.request.user)


class CameraViewSetForISP(viewsets.ModelViewSet):
    serializer_class = CameraSerializer
    permission_classes = [IsISP]
    pagination_class = CameraPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['venue']
    search_fields = ['camera_name', 'rtsp_url']
    ordering_fields = ['created_at', 'camera_name']

    def get_queryset(self):
        # ISP can only see their own cameras
        return Camera.objects.filter(isp=self.request.user)

    def perform_create(self, serializer):
        serializer.save(isp=self.request.user)


class CamerasByCustomerAPIView(APIView):
    def get(self, request, customer_id):
        venue_id = request.query_params.get('venue_id')

        try:
            user = User.objects.get(pk=customer_id)
        except User.DoesNotExist:
            logger.warning(f"User with ID {customer_id} does not exist")
            return Response({'status': False, 'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        if user.usertype != 3:  # Ensure user is a customer
            logger.warning(f"User ID {customer_id} is not a customer")
            return Response({'status': False, 'error': 'Not a customer user'}, status=status.HTTP_403_FORBIDDEN)

        logger.info(f"Customer user: fetching cameras for customer ID: {user.pk}")

        if venue_id:
            logger.info(f"Checking access to venue ID: {venue_id}")
            try:
                venue_id = int(venue_id)
            except ValueError:
                return Response({'status': False, 'error': 'Invalid venue_id'}, status=status.HTTP_400_BAD_REQUEST)

            if venue_id not in user.venue:
                logger.warning(f"User ID {user.pk} attempted access to unauthorized venue {venue_id}")
                return Response({'status': False, 'error': 'You do not have access to this venue'}, status=status.HTTP_403_FORBIDDEN)

            venue = Venue.objects.filter(id=venue_id).first()
            if not venue:
                return Response({'status': False, 'error': 'Venue not found'}, status=status.HTTP_404_NOT_FOUND)

            cameras = Camera.objects.filter(venue=venue)
        else:
            venue_ids = user.venue
            cameras = Camera.objects.filter(venue__id__in=venue_ids)

        serializer = CameraSerializer(cameras, many=True)
        logger.info(f"Found {len(serializer.data)} cameras for customer ID: {user.pk}")
        return Response({'status': True, 'data': serializer.data}, status=status.HTTP_200_OK)