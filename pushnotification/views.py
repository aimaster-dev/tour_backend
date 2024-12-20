from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from user.permissions import IsAdmin, IsAdminOrISP
from user.models import User
import firebase_admin
from firebase_admin import credentials, messaging
from rest_framework.response import Response
from rest_framework import status

cred = credentials.Certificate("D:\projects\Django\\tour_backend\\emmysvideo-fb564-firebase-adminsdk-tk4rs-f56faea058.json")
firebase_admin.initialize_app(cred)
# Create your views here.
class PushNotification(APIView):

    permission_classes = [IsAdmin]

    def post(self, request):
        # Get parameters from the request body
        userlist_id = request.data.get("ids")
        title = request.data.get("title")
        content = request.data.get("content")

        # Check if required fields are provided
        if not userlist_id or not title or not content:
            return Response(
                {"status": False, "message": "Missing required parameters"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Iterate through the user IDs and send the notification
        error_list = []
        for user_id in userlist_id:
            try:
                user = User.objects.get(id=user_id)  # Corrected 'objects' instead of 'object'
                token = user.device_token  # Assuming device_token is a field on the User model

                if not token:  # Handle cases where the user does not have a device token
                    print(f"{user_id}'s token doesn't exist.")
                    error_list.append(user_id)
                    continue

                # Create the message
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=content
                    ),
                    token=token
                )

                # Send the message via Firebase Cloud Messaging
                response = messaging.send(message)
                
                # Optionally log the response for debugging
                print(f"Notification sent to {user_id}: {response}")

            except User.DoesNotExist:
                # Handle case where the user with the given ID does not exist
                print(f"{user_id} doesn't exist.")
                error_list.append(user_id)
                continue  # Skip this ID if the user doesn't exist
            except Exception as e:
                error_list.append(user_id)
                # Catch other exceptions and log them
                print(f"Error sending notification to user {user_id}: {str(e)}")
                continue
        if len(error_list) == 0:
            return Response(
                {"status": True, "data": "Successfully sent the message"},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"status": False, "data": {"errors": error_list}},
                status=status.HTTP_200_OK
            )