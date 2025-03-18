from rest_framework import serializers
from .models import Venue
from user.models import User


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ['id', 'venue_name', 'status', 'created_at', 'updated_at']


class ISPSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'usertype']


class VenueSerializer(serializers.ModelSerializer):

    class Meta:
        model = Venue
        fields = ["id", "venue_name", "status",
                  "isp", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        instance.venue_name = validated_data.get(
            'venue_name', instance.venue_name)
        instance.status = validated_data.get('status', instance.status)
        instance.isp = validated_data.get('isp', instance.isp)
        instance.save()
        return instance


class PublicVenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ['id', 'venue_name', 'description', 'status', 'created_at']


class PublicISPSerializer(serializers.ModelSerializer):
    venue = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email',
                  'phone_number', 'venue', 'status']

    def get_venue(self, obj):
        venues = Venue.objects.filter(id=obj.venue)

        if venues.exists():
            return [
                {
                    'id': venue.id,
                    'name': venue.venue_name
                } for venue in venues
            ]
        return []
