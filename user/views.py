from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.generics import ListAPIView
from .serializers import UserRegUpdateSerializer, UserListSerializer, UserLoginSerializer, UserDetailSerializer, ISPCreateSerializer, UserLoginWithVenueISPIdSerializer
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from .models import User, Invitation, EmailOTP
from tourplace.models import Venue
from .permissions import IsAdmin, IsAdminOrISP
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
                token = account_activation_token.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                activation_url = f"https://emmysvideos.com/email_verify?uid={uid}&token={token}"
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
            user.delete()
            return Response({"status": True, "data": "The User Successfully deleted."}, status=status.HTTP_200_OK)
        except user.DoesNotExist:
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
            login_data.pop("venue", None)
            login_data.pop("device_token", None)
            serializer = UserLoginSerializer(data=login_data)
            if serializer.is_valid():
                validated_data = serializer.validated_data
                if validated_data['status'] == False and validated_data['usertype'] == 2:
                    return Response({"status": False, "data": {"msg": "Please wait until admin allows you"}}, status=status.HTTP_423_LOCKED)
                else:
                    user = validated_data.pop('user')
                    if user.status == False:
                        return Response({"status": False, "data": {"msg": "Your account is deleted."}}, status=status.HTTP_403_FORBIDDEN)
                    if user.usertype == 3:
                        if user.is_activate == False:
                            return Response({"status": False, "data": {"msg": "Please activate your account first.", "user_id": user.id}}, status=status.HTTP_406_NOT_ACCEPTABLE)
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
            return Response({"status": False, "data": {"msg": "Invalid email or password"}}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            print(e)
            return Response({"status": False, "data": {"msg": str(e)}}, status=status.HTTP_400_BAD_REQUEST)


class UserLoginWithVenueISPIdAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            venue = request.data.get("venue")
            device_token = request.data.get("device_token")
            login_data = request.data
            login_data.pop("venue", None)
            login_data.pop("device_token", None)
            serializer = UserLoginWithVenueISPIdSerializer(data=login_data)
            if serializer.is_valid():
                validated_data = serializer.validated_data
                if validated_data['status'] == False and validated_data['usertype'] == 2:
                    return Response({"status": False, "data": {"msg": "Please wait until admin allows you"}}, status=status.HTTP_423_LOCKED)
                else:
                    user = validated_data.pop('user')
                    if user.status == False:
                        return Response({"status": False, "data": {"msg": "Your account is deleted."}}, status=status.HTTP_403_FORBIDDEN)
                    if user.usertype == 3:
                        if user.is_activate == False:
                            return Response({"status": False, "data": {"msg": "Please activate your account first.", "user_id": user.id}}, status=status.HTTP_406_NOT_ACCEPTABLE)
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
            return Response({"status": False, "data": {"msg": "Invalid email or password"}}, status=status.HTTP_404_NOT_FOUND)
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
                activation_url = f"https://emmysvideos.com/email_verify?uid={uid}&token={token}"
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
        invitation_link = f"https://emmysvideos.com/set_password/{token}"
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
                user = serializer.save()
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
                        <p>Your OTP code for <strong>emmysvideos.com</strong> is <strong>{otp}</strong></p>
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
                                <p>Your OTP code for <strong>emmysvideos.com</strong> is <strong>{otp}</strong></p>
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
        venue_id = data.get('venue_id')
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
        user_id = request.data.get('user_id')
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

            # Handle venue_id if provided
            venue_id = data.pop('venue_id', None)
            if venue_id:
                try:
                    venue = get_object_or_404(Venue, id=venue_id)
                    user.venue = venue
                except Venue.DoesNotExist:
                    return Response({
                        "status": False,
                        "data": f"Venue with ID {venue_id} not found"
                    }, status=status.HTTP_404_NOT_FOUND)

            # Handle ISP assignment if provided
            isp_id = data.pop('isp_id', None)
            if isp_id:
                try:
                    # Verify ISP exists and belongs to the same venue
                    isp = get_object_or_404(
                        User,
                        id=isp_id,
                        usertype=2,
                        venue=user.venue
                    )
                except User.DoesNotExist:
                    return Response({
                        "status": False,
                        "data": f"ISP with ID {isp_id} not found or not associated with the customer's venue"
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
                        response_data['venue'] = {
                            'id': updated_user.venue.id,
                            'name': updated_user.venue.venue_name
                        }

                    # Replace venue IDs with detailed information if present
                    if 'venue' in response_data and response_data['venue']:
                        venue_ids = response_data['venue']
                        venue_details = []

                        for venue_id in venue_ids:
                            try:
                                place = Venue.objects.get(id=venue_id)
                                venue_details.append({
                                    'id': venue_id,
                                    'place_name': place.venue_name
                                })
                            except Venue.DoesNotExist:
                                # Include ID but mark as not found
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
            venue = get_object_or_404(Venue, id=venue_id, status=True)

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
