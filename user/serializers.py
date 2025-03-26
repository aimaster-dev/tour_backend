import datetime
from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Invitation
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils import timezone
from rest_framework import serializers
from tourplace.models import Venue
from tourplace.serializers import VenueSerializer
from django.shortcuts import get_object_or_404


class UserRegUpdateSerializer(serializers.ModelSerializer):
    venue = serializers.IntegerField(write_only=True)
    isp_id = serializers.IntegerField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'phone_number',
                  'venue', 'isp_id', 'usertype', 'status', 'venue',
                  'level', 'is_activate', 'device_token')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        venue_id = validated_data.pop('venue')
        isp_id = validated_data.pop('isp_id', None)

        venue = get_object_or_404(Venue, id=venue_id)
        validated_data['venue'] = venue

        if isp_id:
            isp = get_object_or_404(User, id=isp_id, usertype=2, venue=venue)
            validated_data['isp'] = isp.id

        user = User.objects.create_user(**validated_data)
        return user

    def update(self, instance, validated_data):
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.phone_number = validated_data.get(
            'phone_number', instance.phone_number)
        instance.usertype = validated_data.get('usertype', instance.usertype)
        instance.venue = validated_data.get(
            'venue', instance.venue)
        instance.level = validated_data.get('level', instance.level)
        instance.is_activate = validated_data.get(
            'is_activate', instance.is_activate)
        instance.save()
        return super().update(instance, validated_data)


class UserListSerializer(serializers.ModelSerializer):
    venue = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'usertype',
                  'status', 'venue', 'level', 'is_activate', 'device_token']
        read_only_fields = fields

    def get_venue(self, obj):
        venue_ids = obj.venue
        venues = Venue.objects.filter(id__in=venue_ids)
        return VenueSerializer(venues, many=True).data


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(email=data['email'], password=data['password'])
        if user:
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token
            return {
                'refresh': str(refresh),
                'access': str(access),
                'user_id': user.id,
                'usertype': user.usertype,
                'level': user.level,
                'username': user.username,
                'status': user.status,
                'user': user,
                'venue': user.venue,
                'device_token': user.device_token
            }
        else:
            raise serializers.ValidationError("Invalid email or password")


class UserLoginWithVenueISPIdSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    venue_id = serializers.IntegerField(required=False)
    isp_id = serializers.IntegerField(required=False)

    def validate(self, data):
        user = authenticate(email=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError("Invalid email or password")

        # Handle different user types
        if user.usertype == 1:  # Admin
            # No venue/ISP validation needed
            pass
        elif user.usertype == 2:  # ISP
            # Only validate venue
            if 'venue_id' in data:
                # Check if venue is in user's venues list
                user_venues = user.venue if isinstance(
                    user.venue, list) else [user.venue]
                if data['venue_id'] not in user_venues:
                    raise serializers.ValidationError(
                        "Invalid venue for this ISP")
        elif user.usertype == 3:  # Customer
            # Validate both venue and ISP
            if not user.venue and 'venue_id' not in data:
                raise serializers.ValidationError("Venue selection required")
            if not user.isp_id and 'isp_id' not in data:
                raise serializers.ValidationError("ISP selection required")

            # For existing users without venue/ISP
            if not user.venue and 'venue_id' in data:
                user.venue = [data['venue_id']]
            if not user.isp_id and 'isp_id' in data:
                # Validate ISP belongs to venue
                try:
                    user_venues = user.venue if isinstance(
                        user.venue, list) else [user.venue]
                    isp = User.objects.get(
                        id=data['isp_id'],
                        usertype=2,
                        # Check if ISP's venue list contains user's venue
                        venue__contains=[user_venues[0]],
                        status=True
                    )
                    user.isp_id = isp.id
                    user.save()
                except User.DoesNotExist:
                    raise serializers.ValidationError(
                        "Invalid ISP for selected venue")

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        return {
            'refresh': str(refresh),
            'access': str(access),
            'user_id': user.id,
            'usertype': user.usertype,
            'level': user.level,
            'username': user.username,
            'status': user.status,
            'venue': {
                'id': user.venue.id if hasattr(user.venue, 'id') else user.venue,
                'name': user.venue.venue_name if hasattr(user.venue, 'venue_name') else Venue.objects.get(id=user.venue).venue_name if isinstance(user.venue, int) else None
            } if user.venue else None,
            'isp': {
                'id': user.isp.id,
                'name': user.isp.username
            } if user.isp else None,
            'user': user,
            'device_token': user.device_token
        }


class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ('password',)  # Exclude password from the serialized data


class InvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ['email', 'token', 'invited_by', 'created_at']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'password', 'email']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class ISPCreateSerializer(serializers.ModelSerializer):
    venue_id = serializers.IntegerField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password',
                  'phone_number', 'venue_id', 'status']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def create(self, validated_data):
        venue_id = validated_data.pop('venue_id')
        # Verify venue exists but don't store the object
        get_object_or_404(Venue, id=venue_id)
        validated_data['usertype'] = 2  # ISP type
        validated_data['venue'] = [venue_id]  # Store as a list of venue IDs
        user = User.objects.create_user(**validated_data)
        return user

    def to_representation(self, instance):
        data = super().to_representation(instance)

        if instance.venue:
            # Handle the case where venue is a list of IDs (our expected format)
            if isinstance(instance.venue, list) and instance.venue:
                try:
                    venue_id = instance.venue[0]  # Get the first venue ID
                    venue_obj = Venue.objects.get(id=venue_id)
                    data['venue'] = {
                        'id': venue_id,
                        'name': venue_obj.venue_name
                    }
                except (Venue.DoesNotExist, IndexError):
                    data['venue'] = {
                        'id': venue_id if 'venue_id' in locals() else None, 'name': 'Unknown'}
            # Handle the case where venue is a Venue object
            elif isinstance(instance.venue, Venue):
                data['venue'] = {
                    'id': instance.venue.id,
                    'name': instance.venue.venue_name
                }
            # Handle the case where venue is a single integer
            elif isinstance(instance.venue, int):
                try:
                    venue_obj = Venue.objects.get(id=instance.venue)
                    data['venue'] = {
                        'id': instance.venue,
                        'name': venue_obj.venue_name
                    }
                except Venue.DoesNotExist:
                    data['venue'] = {'id': instance.venue, 'name': 'Unknown'}
            else:
                data['venue'] = None
        else:
            data['venue'] = None

        return data
