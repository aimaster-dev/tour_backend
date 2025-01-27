from user.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from user.permissions import IsClient
from django.core.files.storage import default_storage
from rest_framework.parsers import MultiPartParser, FormParser
from square.client import Client
import os
from price.models import Price
from .serializers import PaymentLogsSerializer
import uuid
import json
from rest_framework.permissions import IsAuthenticated
from price.serializers import PriceSerializer
from .models import PaymentLogs
from tourplace.models import TourPlace
from datetime import datetime, timedelta
from django.db.models import Q
# Create your views here.


def check_payment_status(payment_id):
    try:
        client = Client(
            access_token="EAAAl7xof62WZ9eKwaJNvCRTvGt9l2knAO0o2oKSkOj9MwWWsNtiSWVWx-7bvKBz",
            environment='sandbox'
        )

        response = client.payments.retrieve_payment(payment_id)

        if response.is_success():
            payment_status = response.body['payment']['status']
            _status_ = payment_status
            comment = json.dumps(response.body)
            message = ""
            if payment_status == 'PENDING':
                message = "The payment was successfully processed and completed."
            elif payment_status == 'COMPLETED':
                message = "The payment is not yet finalized and is awaiting further action, such as 3D Secure verification or manual review."
            elif payment_status == 'APPROVED':
                message = "The payment has been approved but has not yet been captured."
            elif payment_status == 'CANCELED':
                message = " The payment was canceled before it was completed."
            elif payment_status == 'VOIDED':
                message = "The payment was voided. This can happen if an authorized payment is canceled before it is captured."
            elif payment_status == 'REFUNDED':
                message = "The payment was refunded after it was completed."
            elif payment_status == 'DECLINED':
                message = "The payment was declined by the card issuer or the Square payment gateway."
            elif payment_status == 'FAILED':
                failure_reason = response.body['payment']['failure_reason']
                _status_ = failure_reason
                if failure_reason == 'INSUFFICIENT_FUNDS':
                    message = "The card has insufficient funds."
                elif failure_reason == 'CARD_EXPIRED':
                    message = "The card has expired."
                elif failure_reason == 'CARD_DECLINED':
                    message = "The card was declined by the issuer."
                elif failure_reason == 'INVALID_CARD':
                    message = "The card information provided is invalid."
                elif failure_reason == 'FRAUD_DETECTED':
                    message = "Fraud was detected."
                else:
                    message = "Other reasons not categorized specifically."
            else:
                _status_ = "unknown"
                message = "Unknown reasons not categorized specifically."
            return _status_, comment, message
        elif response.is_error():
            _status_ = "error"
            comment = json.dumps(response.errors)
            message = "error"
            return _status_, comment, message
    except Exception as e:
        return "error", "error", str(e)


class PaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        token = request.data["token"]
        price_id = request.data["price_id"]
        prices = Price.objects.filter(id=price_id)
        if len(prices) == 0:
            return Response({"status": False, "data": "Please input correct price id."}, status=status.HTTP_400_BAD_REQUEST)
        price = prices[0]
        print(price.price)
        data = {
            "user": user.pk,
            "price": price_id,
            "snapshotremain": price.snapshot_limit,
            "videoremain": price.record_limit,
            "amount": price.price,
            "status": 0,
            "comment": "",
            "message": ""
        }
        logs = PaymentLogs.objects.filter(user=user.pk, price=price.pk).filter(
            Q(videoremain__gt=0) | Q(snapshotremain__gt=0))
        if len(logs) != 0:
            return Response({"status": False, "data": "You already paid for this premium."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            client = Client(
                access_token="EAAAl7xof62WZ9eKwaJNvCRTvGt9l2knAO0o2oKSkOj9MwWWsNtiSWVWx-7bvKBz",
                environment="sandbox"
            )
            idempotency_key = str(uuid.uuid4())
            response = client.payments.create_payment({
                "source_id": token,
                "idempotency_key": idempotency_key,
                "amount_money": {
                    "amount": data["amount"],
                    "currency": "USD"
                }
            })
            print(response)
            serializer = {}
            if response.is_success():
                payment_status = response.body['payment']['status']
                data["status"] = payment_status
                data["comment"] = json.dumps(response.body)
                if payment_status == 'PENDING':
                    data["message"] = "The payment is not yet finalized and is awaiting further action, such as 3D Secure verification or manual review."
                elif payment_status == 'COMPLETED':
                    data["message"] = "The payment was successfully processed and completed."
                    data["remain"] = price.record_limit
                elif payment_status == 'APPROVED':
                    data["message"] = "The payment has been approved but has not yet been captured."
                elif payment_status == 'CANCELED':
                    data["message"] = " The payment was canceled before it was completed."
                elif payment_status == 'VOIDED':
                    data["message"] = "The payment was voided. This can happen if an authorized payment is canceled before it is captured."
                elif payment_status == 'REFUNDED':
                    data["message"] = "The payment was refunded after it was completed."
                elif payment_status == 'DECLINED':
                    data["message"] = "The payment was declined by the card issuer or the Square payment gateway."
                elif payment_status == 'FAILED':
                    failure_reason = response.body['payment']['failure_reason']
                    data["status"] = failure_reason
                    if failure_reason == 'INSUFFICIENT_FUNDS':
                        data["message"] = "The card has insufficient funds."
                    elif failure_reason == 'CARD_EXPIRED':
                        data["message"] = "The card has expired."
                    elif failure_reason == 'CARD_DECLINED':
                        data["message"] = "The card was declined by the issuer."
                    elif failure_reason == 'INVALID_CARD':
                        data["message"] = "The card information provided is invalid."
                    elif failure_reason == 'FRAUD_DETECTED':
                        data["message"] = "Fraud was detected."
                    else:
                        data["message"] = "Other reasons not categorized specifically."
                else:
                    data["status"] = "unknown"
                    data["message"] = "Unknown reasons not categorized specifically."
                serializer = PaymentLogsSerializer(data=data)
                if serializer.is_valid():
                    serializer.save()
                    data = serializer.data
                    print(data["amount"])
                    tourplace = TourPlace.objects.get(id=price.tourplace.pk)
                    output_data = {
                        "price_id": price.pk,
                        "username": user.username,
                        "email": user.email,
                        "phonenumber": user.phone_number,
                        "tourplace": tourplace.place_name,
                        "amount": price.price,
                        "date": data["updated_at"],
                        "status": data["status"],
                        "comment": data["message"],
                        "videoremain": data["videoremain"],
                        "snapshotremain": data["snapshotremain"]
                    }
                    return Response({"status": True, "data": output_data}, status=status.HTTP_201_CREATED)
                else:
                    return Response({"status": False, "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            elif response.is_error():
                return Response({"status": False, "data": response.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"status": False, "data": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        user = request.user
        paylogs = PaymentLogs.objects.filter(status='PENDING')
        for paylog in paylogs:
            comment = json.loads(paylog.comment)
            payment_id = comment.get("payment", {}).get("id")
            if payment_id:
                _status_, comment, message = check_payment_status(payment_id)
                paylog.status = _status_
                paylog.comment = comment
                paylog.message = message
        PaymentLogs.objects.bulk_update(
            paylogs, ['status', 'comment', 'message'])
        if user.usertype == 1:
            tourplace = TourPlace.objects.first()
            if tourplace is None:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)
            tourplace_id = request.query_params.get("tourplace", tourplace.id)
            if tourplace_id is None:
                Response({"status": True, "data": []},
                         status=status.HTTP_200_OK)
            else:
                tourplace = TourPlace.objects.get(id=tourplace_id)
        elif user.usertype == 2:
            tourplace_id = request.query_params.get(
                "tourplace", user.tourplace[0])
            tourplace = TourPlace.objects.get(id=tourplace_id)
        else:
            tourplace_id = user.tourplace[0]
            tourplace = TourPlace.objects.get(id=tourplace_id)
        prices = Price.objects.filter(tourplace_id=tourplace, price__gt=0)
        price_ids = []
        for price in prices:
            price_ids.append(price.id)
        logs = []
        if user.usertype == 3:
            logs = PaymentLogs.objects.filter(
                user=user.id, price__in=price_ids)
        else:
            logs = PaymentLogs.objects.filter(price__in=price_ids)
        from_date_str = request.query_params.get('from')
        to_date_str = request.query_params.get('to')
        try:
            from_date = datetime.strptime(
                from_date_str, '%Y-%m-%d') if from_date_str else datetime.today().replace(day=1)
            to_date = datetime.strptime(
                to_date_str, '%Y-%m-%d') + timedelta(days=1) if to_date_str else None
        except ValueError:
            return Response({"status": False, "message": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        if from_date:
            logs = logs.filter(created_at__gte=from_date)
        if to_date:
            logs = logs.filter(created_at__lte=to_date)

        output_data = []
        for log in logs:
            user_id = log.user
            client = User.objects.get(id=user_id)
            price_id = log.price
            price = Price.objects.get(id=price_id)
            output_element = {
                "price_id": price.pk,
                "username": client.username,
                "email": client.email,
                "phonenumber": client.phone_number,
                "tourplace": tourplace.place_name,
                "amount": price.price,
                "videoremain": log.videoremain,
                "snapshotremain": log.snapshotremain,
                "date": log.updated_at,
                "status": log.status,
                "comment": log.message
            }
            output_data.append(output_element)
        return Response({"status": True, "data": output_data}, status=status.HTTP_200_OK)


class ValidStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        paylogs = PaymentLogs.objects.filter(status='PENDING')
        for paylog in paylogs:
            comment = json.loads(paylog.comment)
            payment_id = comment.get("payment", {}).get("id")
            if payment_id:
                _status_, comment, message = check_payment_status(payment_id)
                paylog.status = _status_
                paylog.comment = comment
                paylog.message = message
        PaymentLogs.objects.bulk_update(
            paylogs, ['status', 'comment', 'message'])
        if user.usertype == 1:
            tourplace = TourPlace.objects.first()
            if tourplace is None:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)
            tourplace_id = request.query_params.get("tourplace", tourplace.id)
            if tourplace_id is None:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)
            else:
                tourplace = TourPlace.objects.get(id=tourplace_id)
        elif user.usertype == 2:
            tourplace_id = request.query_params.get(
                "tourplace", user.tourplace[0])
            tourplace = TourPlace.objects.get(id=tourplace_id)
        else:
            tourplace_id = user.tourplace[0]
            tourplace = TourPlace.objects.get(id=tourplace_id)

        prices = Price.objects.filter(tourplace_id=tourplace)

        logs = []
        if user.usertype == 3:
            logs = PaymentLogs.objects.filter(user=user.pk, price__in=prices).filter(
                Q(videoremain__gt=0) | Q(snapshotremain__gt=0))
        else:
            logs = PaymentLogs.objects.filter(price__in=prices).filter(
                Q(videoremain__gt=0) | Q(snapshotremain__gt=0))

        output_data = []
        for log in logs:
            user_id = log.user
            client = User.objects.get(id=user_id)
            price_id = log.price
            price = Price.objects.get(id=price_id)
            output_element = {
                "price_id": price.pk,
                "username": client.username,
                "email": client.email,
                "phonenumber": client.phone_number,
                "tourplace": tourplace.place_name,
                "amount": price.price,
                "videoremain": log.videoremain,
                "snapshotremain": log.snapshotremain,
                "date": log.updated_at,
                "status": log.status,
                "comment": log.message
            }
            output_data.append(output_element)
        return Response({"status": True, "data": output_data}, status=status.HTTP_200_OK)


class VideoSnapshotCountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
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

            # Return the remaining video and snapshot counts
            response_data = {
                "status": True,
                "data": {
                    "price_id": latest_payment.price.id if latest_payment and latest_payment.price else None,
                    "video_remaining": total_video_remaining,
                    "snapshot_remaining": total_snapshot_remaining,
                    "is_free_plan": latest_payment.price is None if latest_payment else True,
                    "record_time": latest_payment.price.record_time if latest_payment and latest_payment.price else 10
                }
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": False,
                "data": {"msg": str(e)}
            }, status=status.HTTP_400_BAD_REQUEST)


class PaymentDetailsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get query parameters for filtering
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        status_filter = request.query_params.get('status')

        # Base query for user's transactions
        transactions = PaymentLogs.objects.filter(
            user=user.pk).order_by('-created_at')

        # Apply date filters if provided
        if from_date:
            try:
                from_date = datetime.strptime(from_date, '%Y-%m-%d')
                transactions = transactions.filter(created_at__gte=from_date)
            except ValueError:
                return Response({
                    "status": False,
                    "message": "Invalid from_date format. Use YYYY-MM-DD"
                }, status=status.HTTP_400_BAD_REQUEST)

        if to_date:
            try:
                to_date = datetime.strptime(to_date, '%Y-%m-%d')
                to_date = to_date + timedelta(days=1)  # Include the entire day
                transactions = transactions.filter(created_at__lte=to_date)
            except ValueError:
                return Response({
                    "status": False,
                    "message": "Invalid to_date format. Use YYYY-MM-DD"
                }, status=status.HTTP_400_BAD_REQUEST)

        # Filter by status if provided
        if status_filter:
            transactions = transactions.filter(status=status_filter.upper())

        output_data = []
        for transaction in transactions:
            try:
                price = Price.objects.get(id=transaction.price.id)
                tourplace = TourPlace.objects.get(id=price.tourplace.pk)

                transaction_data = {
                    "id": transaction.id,
                    "transaction_id": transaction.transaction_id,
                    "amount": transaction.amount,
                    "status": transaction.status,
                    "created_at": transaction.created_at,
                    "updated_at": transaction.updated_at,
                    "tourplace": tourplace.place_name,
                    "plan_name": price.title,
                    "video_remaining": transaction.videoremain,
                    "snapshot_remaining": transaction.snapshotremain,
                }
                output_data.append(transaction_data)
            except (Price.DoesNotExist, TourPlace.DoesNotExist):
                # Skip transactions with missing related data
                continue

        return Response({
            "status": True,
            "data": {
                "total_transactions": len(output_data),
                "transactions": output_data
            }
        }, status=status.HTTP_200_OK)


class InAppPurchaseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            purchase_data = request.data[0]  # Get first purchase object
            product_id = purchase_data.get('productId')
            transaction_id = purchase_data.get('transactionId')

            # Validate required fields
            if not all([product_id, transaction_id]):
                return Response({
                    "status": False,
                    "data": "Missing required purchase information"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check for duplicate transaction
            if PaymentLogs.objects.filter(transaction_id=transaction_id).exists():
                return Response({
                    "status": False,
                    "data": "Transaction already processed"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Find matching price plan
            try:
                price = Price.objects.get(product_id=product_id)
            except Price.DoesNotExist:
                return Response({
                    "status": False,
                    "data": "Invalid product ID"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create payment record
            payment_data = {
                "user": user.pk,
                "price": price.pk,
                "amount": price.price,
                "videoremain": price.record_limit,
                "snapshotremain": price.snapshot_limit,
                "status": "COMPLETED",
                "transaction_id": transaction_id
            }

            serializer = PaymentLogsSerializer(data=payment_data)
            if serializer.is_valid():
                payment = serializer.save()

                return Response({
                    "status": True,
                    "data": {
                        "payment_id": payment.id,
                        "plan_name": price.title,
                        "amount": price.price,
                        "video_limit": price.record_limit,
                        "snapshot_limit": price.snapshot_limit,
                        "transaction_id": transaction_id,
                        "purchase_date": payment.created_at
                    }
                }, status=status.HTTP_201_CREATED)

            return Response({
                "status": False,
                "data": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "status": False,
                "data": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
