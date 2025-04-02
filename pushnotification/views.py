from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from user.permissions import IsAdmin, IsAdminOrISP
from user.models import User
import firebase_admin
from firebase_admin import credentials, messaging
from rest_framework.response import Response
from rest_framework import status
from .models import Notification
from .serializers import NotificationSerializer, SendNotificationSerializer
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

# Initialize Firebase Admin SDK
try:
    cred = credentials.Certificate(
        "/var/www/htdocs/Video_Backend/emmysvideo-fb564-firebase-adminsdk-tk4rs-f56faea058.json")
    firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"Firebase initialization error: {str(e)}")


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class PushNotification(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SendNotificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"status": False, "message": "Invalid data",
                    "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_ids = serializer.validated_data['user_ids']
        title = serializer.validated_data['title']
        content = serializer.validated_data['content']

        # Create notification record
        notification = Notification.objects.create(
            title=title,
            content=content,
            sent_by=request.user
        )
        notification.recipients.set(user_ids)

        error_list = []
        success_count = 0

        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                token = user.device_token

                if not token:
                    error_list.append({
                        'user_id': user_id,
                        'error': 'Device token not found'
                    })
                    continue

                message = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=content
                    ),
                    token=token
                )

                response = messaging.send(message)
                success_count += 1
                print(f"Notification sent to {user_id}: {response}")

            except User.DoesNotExist:
                error_list.append({
                    'user_id': user_id,
                    'error': 'User not found'
                })
            except Exception as e:
                error_list.append({
                    'user_id': user_id,
                    'error': str(e)
                })

        # Update notification record with results
        notification.success_count = success_count
        notification.failure_count = len(error_list)
        notification.failed_users = error_list
        notification.save()

        response_data = {
            "status": True,
            "message": "Notification processing completed",
            "data": {
                "success_count": success_count,
                "failure_count": len(error_list),
                "failed_users": error_list
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)


class NotificationHistory(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        notifications = Notification.objects.all()
        page = self.pagination_class().paginate_queryset(notifications, request)

        if page is not None:
            serializer = NotificationSerializer(page, many=True)
            return self.pagination_class().get_paginated_response(serializer.data)

        serializer = NotificationSerializer(notifications, many=True)
        return Response({
            "status": True,
            "data": serializer.data
        })
