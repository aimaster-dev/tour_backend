from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.generics import ListAPIView
from .serializers import ClientListSerializer, UserRegUpdateSerializer, UserListSerializer, UserLoginSerializer, UserDetailSerializer, ISPCreateSerializer, UserLoginWithVenueISPIdSerializer, CustomerByISPSerializer
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from .models import User, Invitation, EmailOTP
from tourplace.models import Venue
from .permissions import IsAdmin, IsAdminOrISP, IsClient
from .tokens import account_activation_token
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from tourplace.models import Venue
from django.utils.crypto import get_random_string
from django.shortcuts import get_object_or_404
from django.db.models import F, Func
from price.models import Price
from payment.models import PaymentLogs
from payment.serializers import PaymentLogsSerializer
import random
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
import logging

# Create your views here.


def is_subset(small, big):
    return all(item in big for item in small)


class UserAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegUpdateSerializer(data=request.data)
        email_addr = request.data.get('email')
        exist_user = User.objects.filter(email=email_addr)

        if len(exist_user) != 0:
            exist_user[0].status = True
            exist_user[0].save()
            return Response({
                "status": True,
                "past_registered": True,
                "data": "User Registered Successfully. You don't need email verification because you already registered to our service."
            }, status=status.HTTP_201_CREATED)

        if serializer.is_valid():
            with transaction.atomic():
                user = serializer.save()
                serializer.is_activate = False
                user.save()

                # If this is a client user (usertype=4) and no ISP is assigned,
                # create a default ISP for the venue
                if user.usertype == 4 and not user.isp:
                    venue_id = user.venue[0] if user.venue else None
                    if venue_id:
                        # Check if any ISP exists for this venue
                        existing_isp = User.objects.filter(
                            usertype=2, 
                            venue__contains=[venue_id], 
                            status=True
                        ).first()
                        
                        if not existing_isp:
                            # Create a default ISP for this venue
                            try:
                                venue_obj = Venue.objects.get(id=venue_id)
                                default_isp = User.objects.create_user(
                                    email=f"default_isp_{venue_id}@example.com",
                                    username=f"Default ISP - {venue_obj.venue_name}",
                                    password="default_isp_password_123",
                                    phone_number="1234567890",
                                    usertype=2,
                                    venue=[venue_id],
                                    status=True,
                                    is_activate=True
                                )
                                user.isp = default_isp
                                user.save()
                            except Venue.DoesNotExist:
                                pass  # Venue doesn't exist, skip ISP creation

                # Check if user already had a free plan before
                existing_free_plan = PaymentLogs.objects.filter(
                    user__email=email_addr,
                    price__isnull=True,
                    transaction_id__startswith='FREE_TRIAL_'
                ).exists()

                # Only create free plan if user never had one
                if not existing_free_plan:
                    PaymentLogs.objects.create(
                        user=user,
                        price=None,
                        amount=0,
                        videoremain=3,
                        snapshotremain=3,
                        record_time=10,
                        status='COMPLETED',
                        transaction_id=f"FREE_TRIAL_{user.id}_{timezone.now().timestamp()}"
                    )

                # Send verification email
                try:
                    token = account_activation_token.make_token(user)
                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    activation_url = f"https://dwareapps.com/email_verify?uid={uid}&token={token}"
                    mail_subject = 'Activate your account'
                    message = render_to_string('acc_active_email.html', {
                        'user': user,
                        'activation_url': activation_url,
                    })
                    email = EmailMessage(mail_subject, message, to=[user.email])
                    email.content_subtype = "html"
                    email.send()
                    
                    return Response({
                        "status": True,
                        "past_registered": False,
                        "data": "User Registered Successfully. Please check your email to activate your account."
                    }, status=status.HTTP_201_CREATED)
                except Exception as e:
                    # If email fails, still create the user but return a different message
                    logging.error(f"Failed to send activation email to {user.email}: {str(e)}")
                    return Response({
                        "status": True,
                        "past_registered": False,
                        "data": "User Registered Successfully. Please contact admin to activate your account."
                    }, status=status.HTTP_201_CREATED)

        return Response({"status": False, "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, pk, format=None):
        try:
            user = User.objects.get(id=pk)
            serializer = UserDetailSerializer(user)
            data = serializer.data
            venue = data['venue']
            del data['venue']
            data['venue'] = []
            for tour in venue:
                tour_data = {
                    'id': tour,
                    'place_name': Venue.objects.get(id=tour).venue_name
                }
                data['venue'].append(tour_data)
            return Response({"status": True, "data": data}, status=status.HTTP_200_OK)
        except user.DoesNotExist:
            Response({"status": False, "data": {"msg": "User not found."}},
                     status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)


class UserDeleteAPIView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, *args, **kwargs):
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"status": False, "data": {"msg": "User ID is required."}}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(id=user_id)
            if user.usertype == 2:
                cameras = user.camera_set.all()
                customers = User.objects.filter(isp=user, usertype__in=[3, 4])
                
                if customers.exists() or cameras.exists():
                    return Response({
                        "status": False,
                        "data": {
                            "msg": "This user has associated cameras or customers. Please remove them first."
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)
            user.delete()
            return Response({"status": True, "data": "The User Successfully deleted."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            Response({"status": False, "data": {"msg": "User not found."}},
                     status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)


class SelfDeleteAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):
        auth_header = request.headers.get('Authorization')
        print(auth_header)
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            print(f"User's Token: {token}")
        user_id = request.user.id
        print(user_id)
        if request.user.usertype != 3:
            return Response({"status": False, "data": {"msg": "Admin or ISP can't be deleted by yourself."}}, status=status.HTTP_400_BAD_REQUEST)
        if not user_id:
            return Response({"status": False, "data": {"msg": "User ID is required."}}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(id=user_id)
            venue = user.venue
            for tour in venue:
                print(tour)
            user.status = False
            user.save()
            return Response({"status": True, "data": "The User Successfully deleted."}, status=status.HTTP_200_OK)
        except user.DoesNotExist:
            Response({"status": False, "data": {"msg": "User not found."}},
                     status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)


class UserLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            venue = request.data.get("venue")
            device_token = request.data.get("device_token")
            login_data = request.data
            # login_data.pop("venue", None)
            login_data.pop("device_token", None)
            serializer = UserLoginSerializer(data=login_data)
            if serializer.is_valid():
                validated_data = serializer.validated_data
                if validated_data['status'] == False and validated_data['usertype'] == 2:
                    return Response({"status": False, "data": {"msg": "Please wait until admin allows you"}}, status=status.HTTP_423_LOCKED)
                else:
                    user = validated_data.pop('user')
                    # Additional checks for venue and activation are now handled in serializer
                    if user.usertype == 3:
                        if venue == 0:
                            return Response({"status": False, "data": {"msg": "Please input venue."}}, status=status.HTTP_403_FORBIDDEN)
                        else:
                            user.venue = [venue]
                            user.device_token = device_token
                            user.save()
                            try:
                                venue_field = Venue.objects.get(
                                    id=venue)
                            except Venue.DoesNotExist:
                                return Response({"status": False, "data": {"msg": "Venue not found."}}, status=status.HTTP_404_NOT_FOUND)
                            userdata = serializer.validated_data
                            userdata["device_token"] = user.device_token
                            try:
                                price = Price.objects.get(
                                    venue=venue_field.pk, price=0)
                            except Price.DoesNotExist:
                                return Response({"status": True, "data": userdata}, status=status.HTTP_200_OK)
                            invoice_info = PaymentLogs.objects.filter(
                                user=user.id, price=price.id)
                            print('here', price.id)
                            if len(invoice_info) == 0:
                                data = {
                                    "user": user.id,
                                    "price": price.id,
                                    "videoremain": price.record_limit,
                                    "snapshotremain": price.snapshot_limit,
                                    "amount": price.price,
                                    "status": "COMPLETED",
                                    "comment": "Free Version",
                                    "message": "Free Version"
                                }
                                payserializer = PaymentLogsSerializer(
                                    data=data)
                                if payserializer.is_valid():
                                    payserializer.save()
                                    return Response({"status": True, "data": userdata}, status=status.HTTP_200_OK)
                                else:
                                    return Response({"status": False, "data": {"msg": payserializer.errors}}, status=status.HTTP_403_FORBIDDEN)
                            else:
                                return Response({"status": True, "data": userdata}, status=status.HTTP_200_OK)
                    else:
                        return Response({"status": True, "data": serializer.validated_data}, status=status.HTTP_200_OK)
            else:
                # Return the specific error message from serializer
                error_msg = serializer.errors.get('non_field_errors', ['Invalid credentials'])[0]
                return Response({"status": False, "data": {"msg": error_msg}}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print(e)
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)


class UserLoginWithVenueISPIdAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            venue = request.data.get("venue_id")
            device_token = request.data.get("device_token")
            login_data = request.data
            login_data.pop("device_token", None)
            serializer = UserLoginWithVenueISPIdSerializer(data=login_data)
            if serializer.is_valid():
                validated_data = serializer.validated_data
                if validated_data['status'] == False and validated_data['usertype'] == 2:
                    return Response({"status": False, "data": {"msg": "Please wait until admin allows you"}}, status=status.HTTP_423_LOCKED)
                else:
                    user = validated_data.pop('user')
                    # Additional checks for venue and activation are now handled in serializer
                    if user.usertype in [3, 4]:  # Assuming 3 is for clients and 4 for app users
                        if venue == 0:
                            return Response({"status": False, "data": {"msg": "Please input venue."}}, status=status.HTTP_403_FORBIDDEN)
                        else:
                            user.venue = [venue]
                            user.device_token = device_token
                            user.save()
                            try:
                                venue_field = Venue.objects.get(
                                    id=venue)
                            except Venue.DoesNotExist:
                                return Response({"status": False, "data": {"msg": "Venue not found."}}, status=status.HTTP_404_NOT_FOUND)
                            userdata = serializer.validated_data
                            userdata["device_token"] = user.device_token
                            try:
                                price = Price.objects.get(
                                    venue=venue_field.pk, price=0)
                            except Price.DoesNotExist:
                                return Response({"status": True, "data": userdata}, status=status.HTTP_200_OK)
                            invoice_info = PaymentLogs.objects.filter(
                                user=user.id, price=price.id)
                            print('here', price.id)
                            if len(invoice_info) == 0:
                                data = {
                                    "user": user.id,
                                    "price": price.id,
                                    "videoremain": price.record_limit,
                                    "snapshotremain": price.snapshot_limit,
                                    "amount": price.price,
                                    "status": "COMPLETED",
                                    "comment": "Free Version",
                                    "message": "Free Version"
                                }
                                payserializer = PaymentLogsSerializer(
                                    data=data)
                                if payserializer.is_valid():
                                    payserializer.save()
                                    return Response({"status": True, "data": userdata}, status=status.HTTP_200_OK)
                                else:
                                    return Response({"status": False, "data": {"msg": payserializer.errors}}, status=status.HTTP_403_FORBIDDEN)
                            else:
                                return Response({"status": True, "data": userdata}, status=status.HTTP_200_OK)
                    else:
                        return Response({"status": True, "data": serializer.validated_data}, status=status.HTTP_200_OK)
            else:
                # Return the specific error message from serializer
                error_msg = serializer.errors.get('non_field_errors', ['Invalid credentials'])[0]
                return Response({"status": False, "data": {"msg": error_msg}}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)


class UserUpdateAPIView(APIView):
    permission_classes = [IsAdmin]

    def put(self, request, *args, **kwargs):
        """
        Update user details by admin.
        This endpoint allows admins to update user information including venue assignments.
        """
        user_id = kwargs.get('pk')

        try:
            user = get_object_or_404(User, id=user_id)

            # Store original venues for comparison
            original_venues = user.venue.copy() if isinstance(user.venue, list) else [
                user.venue] if user.venue else []

            # Validate and update user data
            serializer = UserRegUpdateSerializer(
                user, data=request.data, partial=True)

            if not serializer.is_valid():
                return Response(
                    {"status": False, "data": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Use transaction to ensure data integrity
            with transaction.atomic():
                # First, remove ISP assignment from original venues if user is ISP
                if user.usertype == 2:
                    for venue_id in original_venues:
                        try:
                            place = Venue.objects.get(id=venue_id)
                            if place.isp == user.id:  # Only reset if this user is the assigned ISP
                                place.isp = 0
                                place.save()
                        except Venue.DoesNotExist:
                            # Skip non-existent venues
                            continue

                # Save user data
                updated_user = serializer.save()

                # Process venues if present in the data
                new_venues = updated_user.venue if isinstance(updated_user.venue, list) else [
                    updated_user.venue] if updated_user.venue else []

                # Format response data
                response_data = serializer.data.copy()

                # Replace venue IDs with detailed information
                if 'venue' in response_data:
                    venue_ids = response_data['venue'] if isinstance(
                        response_data['venue'], list) else [response_data['venue']]
                    venue_details = []

                    for venue_id in venue_ids:
                        try:
                            place = Venue.objects.get(id=venue_id)
                            venue_details.append({
                                'id': venue_id,
                                'name': place.venue_name
                            })

                            # If user is ISP, assign them to the venue
                            if updated_user.usertype == 2:
                                place.isp = updated_user.id
                                place.save()
                        except Venue.DoesNotExist:
                            # Include ID but mark as not found
                            venue_details.append({
                                'id': venue_id,
                                'name': 'Not found'
                            })

                    response_data['venue'] = venue_details

                return Response(
                    {"status": True, "data": response_data},
                    status=status.HTTP_200_OK
                )

        except User.DoesNotExist:
            return Response(
                {"status": False, "data": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"status": False, "data": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ISPRangeListAPIView(ListAPIView):
    serializer_class = UserListSerializer
    # Assuming you want this endpoint to be protected
    permission_classes = [IsAdmin]

    def get_queryset(self):
        """
        Optionally restricts the returned users to a given range,
        by filtering against a `start_row_index` and `end_row_index` query parameter in the URL.
        """
        queryset = User.objects.filter(usertype=2)
        start_row_index = self.request.query_params.get(
            'start_row_index', None)
        end_row_index = self.request.query_params.get('end_row_index', None)

        if start_row_index is not None and end_row_index is not None:
            start_row_index = int(start_row_index)
            end_row_index = int(end_row_index)
            return queryset[start_row_index:end_row_index]
        return queryset


class ClientRangeListAPIView(ListAPIView):
    serializer_class = UserListSerializer
    permission_classes = [IsAdminOrISP]

    def get_queryset(self):
        venue_id = self.request.query_params.get('venue', None)
        venue = None
        user = self.request.user
        if venue_id:
            venue = Venue.objects.get(id=venue_id)
        else:
            if user.usertype == 1:
                venue = Venue.objects.all().first()
            else:
                venue = Venue.objects.filter(isp=user.pk).first()
        if venue is None:
            return []
        prices = Price.objects.filter(venue=venue.pk)
        user_id_list = set()
        invoice_list = PaymentLogs.objects.filter(
            price__in=prices, amount__gt=0)
        for invoicelog in invoice_list:
            user_id_list.add(invoicelog.user)
        user_ids = [user.id if isinstance(
            user, User) else user for user in user_id_list]
        queryset = User.objects.filter(id__in=user_ids)
        start_row_index = self.request.query_params.get(
            'start_row_index', None)
        end_row_index = self.request.query_params.get('end_row_index', None)

        if start_row_index is not None and end_row_index is not None:
            start_row_index = int(start_row_index)
            end_row_index = int(end_row_index)
            return queryset[start_row_index:end_row_index]
        return queryset


class ActivateAccount(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        uidb64 = request.data.get("user_id")
        token = request.data.get("token")
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and account_activation_token.check_token(user, token):
            user.is_activate = True
            user.status = True
            user.save()
            mail_subject = 'Activate Successfully'
            message = render_to_string('verification_success_email.html', {
                'user': user,
            })
            email = EmailMessage(mail_subject, message, to=[user.email])
            email.content_subtype = "html"
            email.send()
            return Response({"status": True, "data": "Your account has been successfully activated."}, status=status.HTTP_200_OK)
        else:
            return Response({"status": False, "data": "Activation link is invalid!"}, status=status.HTTP_400_BAD_REQUEST)


class ResendActivationEmail(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
            if not user.is_activate:
                mail_subject = 'Activate your account.'
                token = account_activation_token.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                activation_url = f"https://dwareapps.com/email_verify?uid={uid}&token={token}"
                message = render_to_string('acc_active_email.html', {
                    'user': user,
                    'activation_url': activation_url,
                })
                email = EmailMessage(mail_subject, message, to=[user.email])
                email.content_subtype = "html"
                email.send()
                return Response({"status": True, "data": "A new activation email has been sent."}, status=status.HTTP_200_OK)
            else:
                return Response({"status": False, "data": "This account is already active."}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({"status": False, "data": "No user found with this email address."}, status=status.HTTP_404_NOT_FOUND)


class InviteUserView(APIView):
    def post(self, request):
        email = request.data.get('email')
        venue = request.data.get('venue')
        token = get_random_string(50)
        if request.user.usertype != 1:
            return Response({"status": True, "data": {"msg": "You don't have any permission to create ISP account."}})
        invited_by = request.user
        Invitation.objects.create(
            email=email, venue=venue, token=token, invited_by=invited_by)
        invitation_link = f"https://dwareapps.com/set_password/{token}"
        subject = 'Invitation to Join'
        message = render_to_string('isp_register.html', {
            'invitation_link': invitation_link
        })
        email = EmailMessage(subject, message, to=[email])
        email.content_subtype = "html"
        email.send()
        return Response({"status": True, "data": {"msg": "Invitation Sent."}}, status=status.HTTP_200_OK)


class SetPasswordView(APIView):
    def post(self, request, token):
        invitation = get_object_or_404(Invitation, token=token)
        userdata = request.data
        userdata["venue"] = invitation.venue
        userdata["email"] = invitation.email
        userdata["usertype"] = 2
        serializer = UserRegUpdateSerializer(data=userdata)
        if serializer.is_valid():
            user = serializer.save()
            venues = invitation.venue
            for venue in venues:
                venue_model = Venue.objects.get(pk=venue)
                venue_model.isp = user.pk
                venue_model.save()
            user.is_invited = True
            user.status = True
            user.is_activate = True
            user.save()
            invitation.delete()
            subject = 'Invitation to Join'
            message = render_to_string('isp_register_successfully.html')
            email = EmailMessage(subject, message, to=[userdata["email"]])
            email.content_subtype = "html"
            email.send()
            user_serializer = UserDetailSerializer(user)
            data = user_serializer.data
            del data['venue']
            data['venue'] = []
            for venue in venues:
                tourdata = {
                    'id': venue,
                    'place_name': Venue.objects.get(id=venue).venue_name
                }
                data['venue'].append(tourdata)
            return Response({"status": True, "data": data}, status=status.HTTP_201_CREATED)
        return Response({"status": False, "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class PhoneRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegUpdateSerializer(data=request.data)
        email_addr = request.data.get('email')
        exist_user = User.objects.filter(email=email_addr)

        if len(exist_user) != 0:
            exist_user[0].status = True
            exist_user[0].save()
            return Response({"status": True, "past_registered": True, "data": "User Registered Successfully. You don't need email verification because you already registered to our service."}, status=status.HTTP_201_CREATED)

        if serializer.is_valid():
            with transaction.atomic():
                user = serializer.save(usertype=4) #assigned role "client" to the appusers
                serializer.is_activate = False
                user.save()

                # Check if user already had a free plan before
                existing_free_plan = PaymentLogs.objects.filter(
                    user__email=email_addr,
                    price__isnull=True,
                    transaction_id__startswith='FREE_TRIAL_'
                ).exists()

                # Only create free plan if user never had one
                if not existing_free_plan:
                    PaymentLogs.objects.create(
                        user=user,
                        price=None,
                        amount=0,
                        videoremain=3,
                        snapshotremain=3,
                        record_time=10,
                        status='COMPLETED',
                        transaction_id=f"FREE_TRIAL_{user.id}_{timezone.now().timestamp()}"
                    )

                # Send OTP
                otp = str(random.randint(100000, 999999))
                EmailOTP.objects.create(user=user, otp=otp)
                mail_subject = 'Activate your account'
                message = f"""
                    <html>
                    <body>
                        <p>Your OTP code for <strong>dwareapps.com</strong> is <strong>{otp}</strong></p>
                    </body>
                    </html>
                """
                email = EmailMessage(mail_subject, message, to=[user.email])
                email.content_subtype = "html"
                email.send()

                return Response({
                    "status": True,
                    "past_registered": False,
                    "data": {
                        "msg": "User Registered Successfully. OTP sent to your email.",
                        "user_id": user.id
                    }
                }, status=status.HTTP_201_CREATED)

        return Response({"status": False, "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, otp, format=None):
        try:
            email_otp = EmailOTP.objects.get(otp=otp)
            user = email_otp.user
            user.is_activate = True
            user.status = True
            user.save()
            email_otp.delete()
            return Response({"status": True, "data": "Your account has been successfully activated."}, status=status.HTTP_201_CREATED)
        except EmailOTP.DoesNotExist:
            return Response({"status": False, "data": "OTP code isn't invalid."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "data": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResendActivationCode(APIView):

    permission_classes = [AllowAny]

    def get(self, request, pk, format=None):
        try:
            user = User.objects.get(id=pk)
            code_otp = EmailOTP.objects.get(user=user)
            otp = code_otp.otp
            mail_subject = 'Activate your account'
            message = f"""
                            <html>
                            <body>
                                <p>Your OTP code for <strong>dwareapps.com</strong> is <strong>{otp}</strong></p>
                            </body>
                            </html>
                        """
            email = EmailMessage(mail_subject, message, to=[user.email])
            email.content_subtype = "html"
            email.send()
            return Response({"status": True, "data": {"msg": "User Registered Successfully. OTP sent to your email.", "user_id": user.id}}, status=status.HTTP_201_CREATED)
        except EmailOTP.DoesNotExist:
            return Response({"status": False, "data": "User isn't valid or already activated."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "data": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            serializer = UserDetailSerializer(user)
            data = serializer.data

            # Get venue data
            venue = data['venue']
            del data['venue']
            data['venue'] = []
            for venue_id in venue:
                venue_data = {
                    'id': venue_id,
                    'place_name': Venue.objects.get(id=venue_id).venue_name
                }
                data['venue'].append(venue_data)

            # Get the latest payment log for both paid and free plans
            payment_logs_query = PaymentLogs.objects.filter(user=user.id)
            latest_payment = payment_logs_query.order_by('-created_at').first()

            # Get free plan details
            free_plan = PaymentLogs.objects.filter(
                user=user.id,
                price__isnull=True,
                transaction_id__startswith='FREE_TRIAL_'
            ).first()

            # Calculate total remaining credits
            total_video_remaining = (latest_payment.videoremain if latest_payment else 0) + \
                (free_plan.videoremain if free_plan else 0)
            total_snapshot_remaining = (latest_payment.snapshotremain if latest_payment else 0) + \
                (free_plan.snapshotremain if free_plan else 0)

            # Add permissions and remaining counts to the response data
            data['recording_permissions'] = {
                "is_video_recording_allowed": total_video_remaining > 0,
                "is_snapshot_allowed": total_snapshot_remaining > 0,
                "video_remaining": total_video_remaining,
                "snapshot_remaining": total_snapshot_remaining,
                "record_time": latest_payment.price.record_time if latest_payment and latest_payment.price else 10
            }

            return Response({"status": True, "data": data}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"status": False, "data": {"msg": "User not found."}},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)


class ClientUserListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        clients = User.objects.filter(usertype=4)
        serializer = UserListSerializer(clients, many=True)
        
        return Response(
            {
            'status': True,
            'data': {"clients":serializer.data}
            }
            , status=status.HTTP_200_OK
        )

class ISPManagementView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = ISPCreateSerializer(data=request.data)
        if serializer.is_valid():
            isp = serializer.save()
            return Response({
                'status': True,
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'status': False,
            'data': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        venue_id = request.query_params.get('venue_id')
        queryset = User.objects.filter(usertype=2)

        if venue_id:
            queryset = queryset.filter(venue_id=venue_id)

        serializer = ISPCreateSerializer(queryset, many=True)
        return Response({
            'status': True,
            'data': serializer.data
        })


class VenueISPListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # Get all ISPs with usertype=2 and status=True
        isps = User.objects.filter(usertype=2, status=True)
        data = []

        for isp in isps:
            # Get the venue information for this ISP
            venue_data = []
            if isp.venue:
                # Check if venue is an object or an integer/list
                if isinstance(isp.venue, Venue):
                    # If venue is already a Venue object
                    venue_data = [{
                        'id': isp.venue.id,
                        'name': isp.venue.venue_name
                    }]
                elif isinstance(isp.venue, int):
                    # If venue is an integer ID
                    try:
                        venue_obj = Venue.objects.get(id=isp.venue)
                        venue_data = [{
                            'id': isp.venue,
                            'name': venue_obj.venue_name
                        }]
                    except Venue.DoesNotExist:
                        venue_data = [{'id': isp.venue, 'name': 'Unknown'}]
                elif isinstance(isp.venue, list):
                    # If venue is a list of IDs
                    venue_ids = isp.venue
                    venue_objs = Venue.objects.filter(id__in=venue_ids)
                    venue_data = [
                        {'id': venue.id, 'name': venue.venue_name}
                        for venue in venue_objs
                    ]

            isp_data = {
                'id': isp.id,
                'name': isp.username,
                'email': isp.email,
                'customer_name': isp.customer_name,
                'venue_name': venue_data
            }
            data.append(isp_data)

        return Response({
            'status': True,
            'data': data
        })


class AdminCustomerListAPIView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        try:
            # Get query parameters for filtering
            search_term = request.query_params.get('search')
            status_filter = request.query_params.get('status')

            # Base query - get all customers (usertype=3)
            customers = User.objects.filter(usertype=3).order_by('-created_at')

            # Apply filters
            if search_term:
                customers = customers.filter(
                    Q(username__icontains=search_term) |
                    Q(email__icontains=search_term) |
                    Q(phone_number__icontains=search_term)
                )

            if status_filter:
                customers = customers.filter(
                    status=status_filter.lower() == 'true')

            # Serialize the data
            serializer = UserListSerializer(customers, many=True)

            return Response({
                "status": True,
                "data": {
                    "total_customers": customers.count(),
                    "customers": serializer.data
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": False,
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerManagementView(APIView):
    permission_classes = [IsAdmin]  # Only admin can manage customers

    def post(self, request):
        """Create a new customer"""
        data = request.data.copy()
        data['usertype'] = 3  # Force usertype to be customer

        # Validate venue and ISP
        venue_id = data.get('venue')
        isp_id = data.get('isp_id')

        if not venue_id:
            return Response({
                "status": False,
                "data": "Venue ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = UserRegUpdateSerializer(data=data)

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    user = serializer.save()
                    user.is_activate = True
                    user.status = True
                    user.save()

                    # Create free trial if applicable
                    existing_free_plan = PaymentLogs.objects.filter(
                        user__email=user.email,
                        price__isnull=True,
                        transaction_id__startswith='FREE_TRIAL_'
                    ).exists()

                    if not existing_free_plan:
                        PaymentLogs.objects.create(
                            user=user,
                            price=None,
                            amount=0,
                            videoremain=3,
                            snapshotremain=3,
                            record_time=10,
                            status='COMPLETED',
                            transaction_id=f"FREE_TRIAL_{user.id}_{timezone.now().timestamp()}"
                        )

                return Response({
                    "status": True,
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response({
                    "status": False,
                    "data": str(e)
                }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "status": False,
            "data": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        """Update existing customer"""
        user_id = request.data.get('id')
        if not user_id:
            return Response({
                "status": False,
                "data": "User ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Ensure we're updating a customer (usertype=3)
            user = get_object_or_404(User, id=user_id, usertype=3)

            # Store original data for comparison if needed
            original_data = {
                'venue': user.venue.copy() if user.venue else []
            }

            data = request.data.copy()

            # Prevent changing usertype
            if 'usertype' in data:
                del data['usertype']

            # Handle venue as a list of IDs
            venue_ids = data.pop('venue', None)
            if venue_ids:
                # Check if venue_ids is already a list
                if not isinstance(venue_ids, list):
                    # Convert to list if it's a single ID
                    venue_ids = [venue_ids]

                # Verify all venues exist
                venues_to_assign = []
                for v_id in venue_ids:
                    try:
                        venue = get_object_or_404(Venue, id=v_id)
                        venues_to_assign.append(v_id)
                    except:
                        return Response({
                            "status": False,
                            "data": f"Venue with ID {v_id} not found"
                        }, status=status.HTTP_404_NOT_FOUND)

                # Assign validated venue IDs to user
                user.venue = venues_to_assign

            # Handle ISP assignment if provided
            isp_id = data.pop('isp_id', None)
            if isp_id:
                try:
                    # Verify ISP exists and belongs to at least one of the user's venues
                    # This logic may need adjustment based on your requirements
                    isp = User.objects.get(id=isp_id, usertype=2)

                    # Check if ISP has access to at least one of the user's venues
                    if not any(v_id in isp.venue for v_id in user.venue):
                        return Response({
                            "status": False,
                            "data": f"ISP with ID {isp_id} not associated with any of the customer's venues"
                        }, status=status.HTTP_400_BAD_REQUEST)

                    user.isp_id = isp_id
                except User.DoesNotExist:
                    return Response({
                        "status": False,
                        "data": f"ISP with ID {isp_id} not found"
                    }, status=status.HTTP_404_NOT_FOUND)

            # Use transaction to ensure data integrity
            with transaction.atomic():
                serializer = UserRegUpdateSerializer(
                    user, data=data, partial=True)

                if serializer.is_valid():
                    updated_user = serializer.save()

                    # Format response data
                    response_data = serializer.data.copy()

                    # Add venue information to response
                    if updated_user.venue:
                        # Handle venue as a list
                        venue_details = []
                        for venue_id in updated_user.venue:
                            try:
                                place = Venue.objects.get(id=venue_id)
                                venue_details.append({
                                    'id': venue_id,
                                    'place_name': place.venue_name
                                })
                            except Venue.DoesNotExist:
                                venue_details.append({
                                    'id': venue_id,
                                    'place_name': 'Not found'
                                })

                        response_data['venue'] = venue_details

                    return Response({
                        "status": True,
                        "data": response_data
                    }, status=status.HTTP_200_OK)

                return Response({
                    "status": False,
                    "data": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": "Customer not found"
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerDetailAPIView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, customer_id):
        """Retrieve a single customer by ID"""
        try:
            customer = User.objects.get(id=customer_id, usertype=3)
            serializer = UserListSerializer(customer)

            return Response({
                "status": True,
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": {"msg": "Customer not found."}
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": {"msg": str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerDeleteAPIView(APIView):
    permission_classes = [IsAdmin]

    def delete(self, request, customer_id):
        """Delete a customer by ID"""
        try:
            customer = User.objects.get(id=customer_id, usertype=3)
            customer.delete()
            return Response({
                "status": True,
                "data": {"msg": "Customer successfully deleted."}
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": {"msg": "Customer not found."}
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": {"msg": str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DirectISPCreateView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        if request.user.usertype != 1:
            return Response({
                "status": False,
                "data": {"msg": "You don't have permission to create ISP accounts."}
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = ISPCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.is_activate = True
            user.status = True
            user.save()

            return Response({
                "status": True,
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response({
            "status": False,
            "data": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class VenueSpecificISPListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, venue_id):
        try:
            # First verify the venue exists and is active
            venue = get_object_or_404(Venue, id=venue_id)

            # Modified query: filter users who have this venue_id in their venue list
            # Using contains lookup for JSONField that stores a list of venue IDs
            isps = User.objects.filter(usertype=2, status=True)

            # Filter ISPs that have this venue_id in their venue list
            filtered_isps = []
            for isp in isps:
                # Handle different venue storage formats
                if isinstance(isp.venue, list) and venue_id in isp.venue:
                    filtered_isps.append(isp)
                elif isinstance(isp.venue, int) and isp.venue == venue_id:
                    filtered_isps.append(isp)
                # Skip ISPs whose venue is not properly formatted

            isp_data = [{
                'id': isp.id,
                'name': isp.username,
                'email': isp.email,
                'phone_number': isp.phone_number
            } for isp in filtered_isps]

            response_data = {
                'venue': {
                    'id': venue.id,
                    'name': venue.venue_name
                },
                'isps': isp_data
            }

            return Response({
                'status': True,
                'data': response_data
            }, status=status.HTTP_200_OK)

        except Venue.DoesNotExist:
            return Response({
                'status': False,
                'message': f'Venue with ID {venue_id} not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)


class VenueByISPListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, isp_id):
        try:
            # First verify the ISP exists and is active
            isp = get_object_or_404(User, id=isp_id, usertype=2, status=True)

            # Get all venues associated with this ISP
            venue_ids = isp.venue if isinstance(isp.venue, list) else [
                isp.venue] if isp.venue else []
            venues = Venue.objects.filter(id__in=venue_ids, status=True)

            venue_data = [{
                'id': venue.id,
                'name': venue.venue_name,
                'description': venue.description,
                'status': venue.status
            } for venue in venues]

            response_data = {
                'isp': {
                    'id': isp.id,
                    'name': isp.username,
                    'email': isp.email,
                    'phone_number': isp.phone_number
                },
                'venues': venue_data
            }

            return Response({
                'status': True,
                'data': response_data
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'status': False,
                'message': f'ISP with ID {isp_id} not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)


class CustomersByISPListView(APIView):
    permission_classes = [IsAdminOrISP]

    def get(self, request, isp_id):
        try:
            # First verify the ISP exists and is active
            isp = get_object_or_404(User, id=isp_id, usertype=2, status=True)

            # Get all customers associated with this ISP
            customers = User.objects.filter(
                isp=isp_id, usertype=3, status=True).order_by('-created_at')

            # Get query parameters for filtering
            search_term = request.query_params.get('search')
            status_filter = request.query_params.get('status')

            # Apply filters
            if search_term:
                customers = customers.filter(
                    Q(username__icontains=search_term) |
                    Q(email__icontains=search_term) |
                    Q(phone_number__icontains=search_term)
                )

            # Only override default status=True if explicitly set to false
            if status_filter and status_filter.lower() == 'false':
                customers = customers.filter(status=False)

            # Serialize the data
            serializer = UserListSerializer(customers, many=True)

            return Response({
                "status": True,
                "data": {
                    "total_customers": customers.count(),
                    "customers": serializer.data
                }
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": {"msg": f"ISP with ID {isp_id} not found or inactive"}
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": {"msg": str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ManageUnlimitedAccessView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        user_id = request.data.get('user_id')
        grant_access = request.data.get('grant_access', False)

        if not user_id:
            return Response({"status": False, "data": "User ID is required"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)

            # Admin users can't modify access for other admins or ISPs
            if user.usertype in [1, 2]:
                return Response(
                    {"status": False, "data": "Cannot modify access for Admin or ISP users as they already have unlimited access"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user.has_unlimited_access = grant_access
            user.save()

            action = "granted" if grant_access else "revoked"
            return Response(
                {"status": True, "data": f"Unlimited access {action} for user {user.email}"},
                status=status.HTTP_200_OK
            )

        except User.DoesNotExist:
            return Response(
                {"status": False, "data": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class CustomerByISPCreateView(APIView):
    permission_classes = [IsAdminOrISP]

    def post(self, request, isp_id):
        try:
            # Verify the ISP exists and is active
            isp = get_object_or_404(User, id=isp_id, usertype=2, status=True)

            # Add ISP ID to the request data
            data = request.data.copy()
            data['isp'] = isp_id

            # Serialize and validate the data
            serializer = CustomerByISPSerializer(data=data)
            if serializer.is_valid():
                # Create the customer
                customer = serializer.save()

                # Ensure the customer is properly associated with the ISP
                customer.isp = isp
                customer.save()

                return Response({
                    "status": True,
                    "data": {
                        "message": "Customer created successfully",
                        "customer": CustomerByISPSerializer(customer).data
                    }
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    "status": False,
                    "data": {"errors": serializer.errors}
                }, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": {"msg": f"ISP with ID {isp_id} not found or inactive"}
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": {"msg": str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerByISPUpdateView(APIView):
    permission_classes = [IsAdminOrISP]

    def put(self, request, isp_id, customer_id):
        try:
            # Verify the ISP exists and is active
            isp = get_object_or_404(User, id=isp_id, usertype=2, status=True)

            # Verify the customer exists and belongs to the ISP
            customer = get_object_or_404(
                User, id=customer_id, isp=isp_id, usertype=3)

            # Serialize and validate the data
            serializer = CustomerByISPSerializer(
                customer, data=request.data, partial=True)
            if serializer.is_valid():
                # Update the customer
                updated_customer = serializer.save()

                return Response({
                    "status": True,
                    "data": {
                        "message": "Customer updated successfully",
                        "customer": CustomerByISPSerializer(updated_customer).data
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "status": False,
                    "data": {"errors": serializer.errors}
                }, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": {"msg": f"ISP with ID {isp_id} or Customer with ID {customer_id} not found"}
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": {"msg": str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerByISPDeleteView(APIView):
    permission_classes = [IsAdminOrISP]

    def delete(self, request, isp_id, customer_id):
        try:
            # Verify the ISP exists and is active
            isp = get_object_or_404(User, id=isp_id, usertype=2, status=True)

            # Verify the customer exists and belongs to the ISP
            customer = get_object_or_404(
                User, id=customer_id, isp=isp_id, usertype=3)

            # Delete the customer
            customer.delete()

            return Response({
                "status": True,
                "data": {"message": "Customer deleted successfully"}
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": {"msg": f"ISP with ID {isp_id} or Customer with ID {customer_id} not found"}
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": {"msg": str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerByISPDetailView(APIView):
    permission_classes = [IsAdminOrISP]

    def get(self, request, isp_id, customer_id):
        try:
            # Verify the ISP exists and is active
            isp = get_object_or_404(User, id=isp_id, usertype=2, status=True)

            # Verify the customer exists and belongs to the ISP
            customer = get_object_or_404(
                User, id=customer_id, isp=isp_id, usertype=3)

            # Serialize the customer data
            serializer = CustomerByISPSerializer(customer)

            return Response({
                "status": True,
                "data": {
                    "customer": serializer.data
                }
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": {"msg": f"ISP with ID {isp_id} or Customer with ID {customer_id} not found"}
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": {"msg": str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClientList(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        queryset = User.objects.filter(usertype=4)

        # Serialize the customer data
        serializer = UserListSerializer(queryset)

        return Response({
            "status": True,
            "data": {
                "clients": serializer.data
            }
        }, status=status.HTTP_200_OK)
        

class ClientManagementView(APIView):
    permission_classes = [IsAdminOrISP]
    
    def get(self, request, client_id):
        """Retrieve a single Client by ID"""
        try:
            customer = User.objects.get(id=client_id, usertype=4)
            serializer = UserListSerializer(customer)

            return Response({
                "status": True,
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": {"msg": "Client not found."}
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": {"msg": str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

    def put(self, request, client_id):
        """Update existing Client"""
        
        if not client_id:
            return Response({
                "status": False,
                "data": "User ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Ensure we're updating a client (usertype=4)
            user = get_object_or_404(User, id=client_id, usertype=4)

            # Store original data for comparison if needed
            original_data = {
                'venue': user.venue.copy() if user.venue else []
            }

            data = request.data.copy()

            # Prevent changing usertype
            if 'usertype' in data:
                del data['usertype']

            # Handle venue as a list of IDs
            venue_ids = data.pop('venue', None)
            if venue_ids:
                # Check if venue_ids is already a list
                if not isinstance(venue_ids, list):
                    # Convert to list if it's a single ID
                    venue_ids = [venue_ids]

                # Verify all venues exist
                venues_to_assign = []
                for v_id in venue_ids:
                    try:
                        venue = get_object_or_404(Venue, id=v_id)
                        venues_to_assign.append(v_id)
                    except:
                        return Response({
                            "status": False,
                            "data": f"Venue with ID {v_id} not found"
                        }, status=status.HTTP_404_NOT_FOUND)

                # Assign validated venue IDs to user
                user.venue = venues_to_assign

            # Handle ISP assignment if provided
            isp_id = data.pop('isp_id', None)
            if isp_id:
                try:
                    # Verify ISP exists and belongs to at least one of the user's venues
                    # This logic may need adjustment based on your requirements
                    isp = User.objects.get(id=isp_id, usertype=2)

                    # Check if ISP has access to at least one of the user's venues
                    if not any(v_id in isp.venue for v_id in user.venue):
                        return Response({
                            "status": False,
                            "data": f"ISP with ID {isp_id} not associated with any of the customer's venues"
                        }, status=status.HTTP_400_BAD_REQUEST)

                    user.isp_id = isp_id
                except User.DoesNotExist:
                    return Response({
                        "status": False,
                        "data": f"ISP with ID {isp_id} not found"
                    }, status=status.HTTP_404_NOT_FOUND)

            # Use transaction to ensure data integrity
            with transaction.atomic():
                serializer = UserRegUpdateSerializer(
                    user, data=data, partial=True)

                if serializer.is_valid():
                    updated_user = serializer.save()

                    # Format response data
                    response_data = serializer.data.copy()

                    # Add venue information to response
                    if updated_user.venue:
                        # Handle venue as a list
                        venue_details = []
                        for venue_id in updated_user.venue:
                            try:
                                place = Venue.objects.get(id=venue_id)
                                venue_details.append({
                                    'id': venue_id,
                                    'place_name': place.venue_name
                                })
                            except Venue.DoesNotExist:
                                venue_details.append({
                                    'id': venue_id,
                                    'place_name': 'Not found'
                                })

                        response_data['venue'] = venue_details

                    return Response({
                        "status": True,
                        "data": response_data
                    }, status=status.HTTP_200_OK)

                return Response({
                    "status": False,
                    "data": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": "Client not found"
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    def delete(self, request, client_id):
        """Delete a client by ID"""
        try:
            client = User.objects.get(id=client_id, usertype=4)
            client.delete()
            return Response({
                "status": True,
                "data": {"msg": "Client successfully deleted."}
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": {"msg": "Client not found."}
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": {"msg": str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
class ClientTestUserView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, client_id):
        """Create a new client test user"""
        if not client_id:
            return Response({
                "status": False,
                "data": "User ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)
            

        client = User.objects.get(id=client_id, usertype=4)
        if client.has_unlimited_access:
            # If the client already has unlimited access, return back to no access
            
            client.has_unlimited_access = False
            client.save()
            return Response({
                "status": True,
                "data": "Client's unlimited access has been revoked"
            }, status=status.HTTP_200_OK)
        else:
           client.has_unlimited_access = True
           client.save()    
           return Response({
                "status": True,
                "data": "Client's unlimited access has been granted"
            }, status=status.HTTP_200_OK)
           

class ClientsByISPListView(APIView):
    permission_classes = [IsAdminOrISP]

    def get(self, request, isp_id):
        try:
            # First verify the ISP exists and is active
            isp = get_object_or_404(User, id=isp_id, usertype=2, status=True)

            # Get all customers associated with this ISP
            clients = User.objects.filter(
                isp=isp_id, usertype=4, status=True).order_by('-created_at')

            # Get query parameters for filtering
            search_term = request.query_params.get('search')
            status_filter = request.query_params.get('status')

            # Apply filters
            if search_term:
                clients = clients.filter(
                    Q(username__icontains=search_term) |
                    Q(email__icontains=search_term) |
                    Q(phone_number__icontains=search_term)
                )

            # Only override default status=True if explicitly set to false
            if status_filter and status_filter.lower() == 'false':
                clients = clients.filter(status=False)

            # Serialize the data
            serializer = ClientListSerializer(clients, many=True)

            return Response({
                "status": True,
                "data": {
                    "total_clients": clients.count(),
                    "clients": serializer.data
                }
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": {"msg": f"ISP with ID {isp_id} not found or inactive"}
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": {"msg": str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            

class ClientsByCustomerListView(APIView):
    permission_classes = [IsClient]

    def get(self, request, customer_id):
        try:
            # First verify the customer exists and is active
            customer = get_object_or_404(User, id=customer_id, usertype=3, status=True)

            if customer and customer.isp:
                # Get all customers associated with this ISP
                clients = User.objects.filter(
                    isp= customer.isp, usertype=4, status=True).order_by('-created_at')

                # Get query parameters for filtering
                search_term = request.query_params.get('search')
                status_filter = request.query_params.get('status')

                # Apply filters
                if search_term:
                    clients = clients.filter(
                        Q(username__icontains=search_term) |
                        Q(email__icontains=search_term) |
                        Q(phone_number__icontains=search_term)
                    )

                # Only override default status=True if explicitly set to false
                if status_filter and status_filter.lower() == 'false':
                    clients = clients.filter(status=False)

                # Serialize the data
                serializer = ClientListSerializer(clients, many=True)

                return Response({
                    "status": True,
                    "data": {
                        "total_clients": clients.count(),
                        "clients": serializer.data
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "status": False,
                    "data": {"msg": f"Customer with ID {customer_id} does not have an associated ISP or is inactive"}
                }, status=status.HTTP_404_NOT_FOUND)

        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": {"msg": f"Customer with ID {customer_id} not found or inactive"}
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": {"msg": str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            

class CheckVenueISPsBeforeDeletionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, venue_id):
        try:
            # First verify the venue exists and is active
            venue = get_object_or_404(Venue, id=venue_id)

            # Filter users with usertype=2 (ISP) and active status
            isps = User.objects.filter(usertype=2, status=True)

            # Filter ISPs that have this venue_id in their venue list
            filtered_isps = []
            for isp in isps:
                if isinstance(isp.venue, list) and venue_id in isp.venue:
                    filtered_isps.append(isp)
                elif isinstance(isp.venue, int) and isp.venue == venue_id:
                    filtered_isps.append(isp)

            isp_data = [{
                'id': isp.id,
                'name': isp.username,
                'email': isp.email,
                'phone_number': isp.phone_number
            } for isp in filtered_isps]

            if isp_data:
                return Response({
                    'status': False,
                    'message': "You can't delete this venue as it has associated ISPs",
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'status': True,
                'message': "Venue deleted successfully"
            }, status=status.HTTP_200_OK)

        except Venue.DoesNotExist:
            return Response({
                'status': False,
                'message': f'Venue with ID {venue_id} not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)
            
            
class SafeDeleteISPUserView(APIView):
    """
    API to safely delete an ISP user only if they have no associated customers or cameras.
    """
    def delete(self, request, user_id):
        # Ensure the user is an ISP
        user = get_object_or_404(User, id=user_id, usertype=2)

        # Check if the ISP has any linked cameras or customer accounts
        cameras = user.camera_set.all()
        customers = User.objects.filter(isp=user, usertype__in=[3, 4])

        if customers.exists() or cameras.exists():
            return Response({
                "status": False,
                "data": {
                    "msg": "This ISP user has associated cameras or customers. Please remove them first."
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        user.delete()
        return Response({
            "status": True,
            "message": "ISP user deleted successfully."
        }, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        """Send OTP for forgot password"""
        email = request.data.get('email')
        
        if not email:
            return Response({
                "status": False,
                "data": "Email is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            
            # Check if user is active
            if not user.status:
                return Response({
                    "status": False,
                    "data": "Your account has been deleted. Please contact support."
                }, status=status.HTTP_400_BAD_REQUEST)

            # Delete any existing OTP for this user
            EmailOTP.objects.filter(user=user).delete()
            
            # Generate new OTP
            otp = str(random.randint(100000, 999999))
            EmailOTP.objects.create(user=user, otp=otp)
            
            # Send email
            mail_subject = 'Password Reset OTP'
            message = f"""
                <html>
                <body>
                    <p>Your password reset OTP for <strong>dwareapps.com</strong> is <strong>{otp}</strong></p>
                    <p>This OTP will expire in 10 minutes.</p>
                </body>
                </html>
            """
            email = EmailMessage(mail_subject, message, to=[user.email])
            email.content_subtype = "html"
            email.send()

            return Response({
                "status": True,
                "data": "Password reset OTP sent to your email."
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": "No user found with this email address."
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "status": False,
                "data": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyForgotPasswordOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        """Verify OTP for password reset"""
        email = request.data.get('email')
        otp = request.data.get('otp')
        
        if not email or not otp:
            return Response({
                "status": False,
                "data": "Email and OTP are required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            email_otp = EmailOTP.objects.get(user=user, otp=otp)
            
            # Check if OTP is expired (10 minutes)
            from datetime import timedelta
            if email_otp.created_at + timedelta(minutes=10) < timezone.now():
                email_otp.delete()
                return Response({
                    "status": False,
                    "data": "OTP has expired. Please request a new one."
                }, status=status.HTTP_400_BAD_REQUEST)

            # OTP is valid, return success
            return Response({
                "status": True,
                "data": "OTP verified successfully. You can now reset your password."
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": "No user found with this email address."
            }, status=status.HTTP_404_NOT_FOUND)
        except EmailOTP.DoesNotExist:
            return Response({
                "status": False,
                "data": "Invalid OTP code."
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "status": False,
                "data": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        """Reset password after OTP verification"""
        email = request.data.get('email')
        otp = request.data.get('otp')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        if not all([email, otp, new_password, confirm_password]):
            return Response({
                "status": False,
                "data": "Email, OTP, new password, and confirm password are required"
            }, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({
                "status": False,
                "data": "Passwords do not match"
            }, status=status.HTTP_400_BAD_REQUEST)

        if len(new_password) < 6:
            return Response({
                "status": False,
                "data": "Password must be at least 6 characters long"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            email_otp = EmailOTP.objects.get(user=user, otp=otp)
            
            # Check if OTP is expired (10 minutes)
            from datetime import timedelta
            if email_otp.created_at + timedelta(minutes=10) < timezone.now():
                email_otp.delete()
                return Response({
                    "status": False,
                    "data": "OTP has expired. Please request a new one."
                }, status=status.HTTP_400_BAD_REQUEST)

            # Reset password
            user.set_password(new_password)
            user.save()
            
            # Delete the OTP
            email_otp.delete()
            
            return Response({
                "status": True,
                "data": "Password reset successfully."
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                "status": False,
                "data": "No user found with this email address."
            }, status=status.HTTP_404_NOT_FOUND)
        except EmailOTP.DoesNotExist:
            return Response({
                "status": False,
                "data": "Invalid OTP code."
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "status": False,
                "data": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Change password for authenticated users"""
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        if not all([current_password, new_password, confirm_password]):
            return Response({
                "status": False,
                "data": "Current password, new password, and confirm password are required"
            }, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({
                "status": False,
                "data": "Passwords do not match"
            }, status=status.HTTP_400_BAD_REQUEST)

        if len(new_password) < 6:
            return Response({
                "status": False,
                "data": "Password must be at least 6 characters long"
            }, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        
        # Verify current password
        if not user.check_password(current_password):
            return Response({
                "status": False,
                "data": "Current password is incorrect"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Change password
        user.set_password(new_password)
        user.save()
        
        return Response({
            "status": True,
            "data": "Password changed successfully."
        }, status=status.HTTP_200_OK)