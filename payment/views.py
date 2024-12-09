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
        prices = Price.objects.filter(id = price_id)
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
        logs = PaymentLogs.objects.filter(user=user.pk, price=price.pk).filter(Q(videoremain__gt=0) | Q(snapshotremain__gt=0))
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
                serializer = PaymentLogsSerializer(data = data)
                if serializer.is_valid():
                    serializer.save()
                    data = serializer.data
                    print(data["amount"])
                    tourplace = TourPlace.objects.get(id = price.tourplace.pk)
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
        paylogs = PaymentLogs.objects.filter(status = 'PENDING')
        for paylog in paylogs:
            comment = json.loads(paylog.comment)
            payment_id = comment.get("payment", {}).get("id")
            if payment_id:
                _status_, comment, message = check_payment_status(payment_id)
                paylog.status = _status_
                paylog.comment = comment
                paylog.message = message
        PaymentLogs.objects.bulk_update(paylogs, ['status', 'comment', 'message'])
        if user.usertype == 1:
            tourplace = TourPlace.objects.first()
            if tourplace is None:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)
            tourplace_id = request.query_params.get("tourplace", tourplace.id)
            if tourplace_id is None:
                Response({"status": True, "data": []}, status=status.HTTP_200_OK)
            else:
                tourplace = TourPlace.objects.get(id = tourplace_id)
        elif user.usertype == 2:
            tourplace_id = request.query_params.get("tourplace", user.tourplace[0])
            tourplace = TourPlace.objects.get(id = tourplace_id)
        else:
            tourplace_id = user.tourplace[0]
            tourplace = TourPlace.objects.get(id = tourplace_id)
        prices = Price.objects.filter(tourplace_id=tourplace, price__gt = 0)
        price_ids = []
        for price in prices:
            price_ids.append(price.id)
        logs = []
        if user.usertype == 3:
            logs = PaymentLogs.objects.filter(user=user.id, price__in=price_ids)
        else:
            logs = PaymentLogs.objects.filter(price__in=price_ids)
        from_date_str = request.query_params.get('from')
        to_date_str = request.query_params.get('to')
        try:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d') if from_date_str else datetime.today().replace(day=1)
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d')  + timedelta(days=1) if to_date_str else None
        except ValueError:
            return Response({"status": False, "message": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        if from_date:
            logs = logs.filter(created_at__gte=from_date)
        if to_date:
            logs = logs.filter(created_at__lte=to_date)

        output_data = []
        for log in logs:
            user_id = log.user
            client = User.objects.get(id = user_id)
            price_id = log.price
            price = Price.objects.get(id = price_id)
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
        paylogs = PaymentLogs.objects.filter(status = 'PENDING')
        for paylog in paylogs:
            comment = json.loads(paylog.comment)
            payment_id = comment.get("payment", {}).get("id")
            if payment_id:
                _status_, comment, message = check_payment_status(payment_id)
                paylog.status = _status_
                paylog.comment = comment
                paylog.message = message
        PaymentLogs.objects.bulk_update(paylogs, ['status', 'comment', 'message'])
        if user.usertype == 1:
            tourplace = TourPlace.objects.first()
            if tourplace is None:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)
            tourplace_id = request.query_params.get("tourplace", tourplace.id)
            if tourplace_id is None:
                return Response({"status": True, "data": []}, status=status.HTTP_200_OK)
            else:
                tourplace = TourPlace.objects.get(id = tourplace_id)
        elif user.usertype == 2:
            tourplace_id = request.query_params.get("tourplace", user.tourplace[0])
            tourplace = TourPlace.objects.get(id = tourplace_id)
        else:
            tourplace_id = user.tourplace[0]
            tourplace = TourPlace.objects.get(id = tourplace_id)

        prices = Price.objects.filter(tourplace_id=tourplace)

        logs = []
        if user.usertype == 3:
            logs = PaymentLogs.objects.filter(user=user.pk, price__in=prices).filter(Q(videoremain__gt=0) | Q(snapshotremain__gt=0))
        else:
            logs = PaymentLogs.objects.filter(price__in=prices).filter(Q(videoremain__gt=0) | Q(snapshotremain__gt=0))

        output_data = []
        for log in logs:
            user_id = log.user
            client = User.objects.get(id = user_id)
            price_id = log.price
            price = Price.objects.get(id = price_id)
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