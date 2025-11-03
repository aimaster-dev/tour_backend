from rest_framework import serializers
from .models import Camera
from tourplace.models import Venue
from tourplace.serializers import VenueSerializer


class CameraSerializer(serializers.ModelSerializer):
    venue_details = VenueSerializer(source='venue', read_only=True)

    class Meta:
        model = Camera
        fields = ['id', 'camera_name', 'stream_url', 'output_url', 'venue',
                  'venue_details', 'created_at', 'updated_at', 'level']
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        stream_url = attrs.get('stream_url')

        if not stream_url or not user:
            return attrs  # let DRF handle missing fields/user errors

        # Create case
        if not self.instance:
            if Camera.objects.filter(stream_url=stream_url, isp=user).exists():
                raise serializers.ValidationError({
                    'stream_url': 'A camera with this Stream URL already exists for your account.'
                })
        # Update case
        else:
            if Camera.objects.filter(
                stream_url=stream_url, isp=user
            ).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError({
                    'stream_url': 'Another camera with this Stream URL already exists for your account.'
                })

        return attrs
    
    def create(self, validated_data):
        # If no venue is provided, fallback to user's venues
        request = self.context.get('request')
        if not validated_data.get('venue') and request:
            user = request.user
            if hasattr(user, 'venue') and user.venue:
                # If user.venue is a single object
                if isinstance(user.venue, int):  # or some other identifier
                    validated_data['venue'] = user.venue
                # If user.venue is a list or queryset
                elif hasattr(user.venue, 'all') or isinstance(user.venue, list):
                    try:
                        venue = Venue.objects.get(id = user.venue[0])# use first venue or handle multiple
                    except:
                        venue = None
                    validated_data['venue'] = venue
        return super().create(validated_data)


class CameraUpdateSerializer(serializers.ModelSerializer):
    venue = serializers.SerializerMethodField()

    class Meta:
        model = Camera
        fields = ['id', 'camera_name', 'stream_url', 'output_url',
                  'venue', 'created_at', 'updated_at', 'level']

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        stream_url = attrs.get('stream_url')

        if not stream_url or not user:
            return attrs  # let DRF handle missing fields/user errors

        # Create case
        if not self.instance:
            if Camera.objects.filter(stream_url=stream_url, isp=user).exists():
                raise serializers.ValidationError({
                    'stream_url': 'A camera with this Stream URL already exists for your account.'
                })
        # Update case
        else:
            if Camera.objects.filter(
                stream_url=stream_url, isp=user
            ).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError({
                    'stream_url': 'Another camera with this Stream URL already exists for your account.'
                })

        return attrs

    def get_venue(self, obj):
        venue = obj.venue
        venues = Venue.objects.filter(id=venue.pk)
        return VenueSerializer(venues, many=True).data

# class CameraSerializer(serializers.ModelSerializer):
#     # tourplace = serializers.SerializerMethodField()

#     class Meta:
#         model = Camera
#         fields = ['id', 'camera_name', 'camera_ip', 'camera_port', 'camera_user_name', 'password', 'output_url', 'created_at', 'updated_at']

#     def validate(self, attrs):
#         if self.instance:
#             return attrs
#         camera_ip = attrs.get('camera_ip')
#         camera_port = attrs.get('camera_port')
#         if Camera.objects.filter(camera_ip=camera_ip, camera_port=camera_port).exists():
#             raise serializers.ValidationError("A camera with this IP address and port already exists.")
#         return super().validate(attrs)

# class CameraUpdateSerializer(serializers.ModelSerializer):
#     tourplace = serializers.SerializerMethodField()

#     class Meta:
#         model = Camera
#         fields = ['id', 'camera_name', 'camera_ip', 'camera_port', 'camera_user_name', 'password', 'output_url', 'tourplace', 'created_at', 'updated_at']

#     def validate(self, attrs):
#         if self.instance:
#             return attrs
#         camera_ip = attrs.get('camera_ip')
#         camera_port = attrs.get('camera_port')
#         if Camera.objects.filter(camera_ip=camera_ip, camera_port=camera_port).exists():
#             raise serializers.ValidationError("A camera with this IP address and port already exists.")
#         return super().validate(attrs)

#     def get_tourplace(self, obj):
#         tourplace = obj.tourplace
#         tourplaces = TourPlace.objects.filter(id=tourplace.pk)
#         return TourplaceSerializer(tourplaces, many=True).data
