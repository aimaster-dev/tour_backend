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
from tourplace.models import TourPlace, Venue
from tourplace.serializers import TourplaceSerializer
from django.shortcuts import get_object_or_404


class UserRegUpdateSerializer(serializers.ModelSerializer):
    venue_id = serializers.IntegerField(write_only=True)
    isp_id = serializers.IntegerField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'phone_number',
                  'venue_id', 'isp_id', 'usertype', 'status', 'tourplace',
                  'level', 'is_activate', 'device_token')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        venue_id = validated_data.pop('venue_id')
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
        instance.tourplace = validated_data.get(
            'tourplace', instance.tourplace)
        instance.level = validated_data.get('level', instance.level)
        instance.is_activate = validated_data.get(
            'is_activate', instance.is_activate)
        instance.save()
        return super().update(instance, validated_data)


class UserListSerializer(serializers.ModelSerializer):
    tourplace = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'usertype',
                  'status', 'tourplace', 'level', 'is_activate', 'device_token']
        read_only_fields = fields

    def get_tourplace(self, obj):
        tourplace_ids = obj.tourplace
        tourplaces = TourPlace.objects.filter(id__in=tourplace_ids)
        return TourplaceSerializer(tourplaces, many=True).data


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
                'tourplace': user.tourplace,
                'user': user,
                'device_token': user.device_token
            }
        else:
            raise serializers.ValidationError("Invalid email or password")


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
        venue = get_object_or_404(Venue, id=venue_id)
        validated_data['usertype'] = 2  # ISP type
        validated_data['venue'] = venue
        user = User.objects.create_user(**validated_data)
        return user

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['venue'] = {
            'id': instance.venue.id,
            'name': instance.venue.venue_name
        } if instance.venue else None
        return data
