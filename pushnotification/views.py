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
import logging
from django.conf import settings
import json

# Configure logging
logger = logging.getLogger(__name__)


def initialize_firebase():
    """Initialize Firebase Admin SDK with proper error handling"""
    try:
        # Check if Firebase is already initialized
        if not firebase_admin._apps:
            cred_path = settings.FIREBASE_CREDENTIALS_PATH

            # Log the credentials being used (excluding sensitive data)
            with open(cred_path, 'r') as f:
                cred_data = json.load(f)
                logger.info(
                    f"Initializing Firebase with project_id: {cred_data.get('project_id')}")

            cred = credentials.Certificate(cred_path)
            default_app = firebase_admin.initialize_app(
                cred, name=settings.FIREBASE_APP_NAME)
            logger.info(
                f"Firebase initialized successfully with project ID: {default_app.project_id}")
        else:
            logger.info("Firebase already initialized")

    except FileNotFoundError:
        logger.error(
            f"Firebase credentials file not found at {settings.FIREBASE_CREDENTIALS_PATH}")
        raise
    except json.JSONDecodeError:
        logger.error("Firebase credentials file is not valid JSON")
        raise
    except Exception as e:
        logger.error(f"Firebase initialization error: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(
            f"Full error details: {e.__dict__ if hasattr(e, '__dict__') else 'No additional details'}")
        raise


# Initialize Firebase when the module loads
initialize_firebase()


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

                try:
                    response = messaging.send(message)
                    success_count += 1
                    logger.info(
                        f"Successfully sent notification to user {user_id} with token {token[:20]}...")
                except firebase_admin.exceptions.FirebaseError as firebase_error:
                    error_detail = {
                        'user_id': user_id,
                        'error': str(firebase_error),
                        'error_code': firebase_error.code if hasattr(firebase_error, 'code') else 'unknown',
                        'error_details': firebase_error.detail if hasattr(firebase_error, 'detail') else 'no details',
                        'token_used': token[:20] + '...' if token else 'No token'
                    }
                    error_list.append(error_detail)
                    logger.error(
                        f"Firebase error for user {user_id}: {error_detail}")
                except Exception as e:
                    error_detail = {
                        'user_id': user_id,
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'token_used': token[:20] + '...' if token else 'No token'
                    }
                    error_list.append(error_detail)
                    logger.error(
                        f"General error for user {user_id}: {error_detail}")

            except User.DoesNotExist:
                error_list.append({
                    'user_id': user_id,
                    'error': 'User not found'
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
        paginator = self.pagination_class()
        result_page = paginator.paginate_queryset(notifications, request)

        if result_page is not None:
            serializer = NotificationSerializer(result_page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = NotificationSerializer(notifications, many=True)
        return Response({
            "status": True,
            "data": serializer.data
        })
