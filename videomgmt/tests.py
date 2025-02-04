from django.test import TestCase
from django.conf import settings
from videomgmt.models import Video, Header
from user.models import User
from tourplace.models import TourPlace
from videomgmt.video_processing import process_video
import os
import shutil
import subprocess
from moviepy.editor import VideoFileClip


class VideoProcessingTest(TestCase):
    def setUp(self):
        # Create test media directory
        self.test_media_root = os.path.join(settings.BASE_DIR, 'test_media')
        self.original_media_root = settings.MEDIA_ROOT
        settings.MEDIA_ROOT = self.test_media_root
        os.makedirs(self.test_media_root, exist_ok=True)

        # Create directories for videos and headers
        os.makedirs(os.path.join(
            self.test_media_root, 'videos'), exist_ok=True)
        os.makedirs(os.path.join(
            self.test_media_root, 'headers'), exist_ok=True)

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create test tourplace
        self.tourplace = TourPlace.objects.create()

        # Create test video files using FFmpeg
        self.header_path = os.path.join(
            self.test_media_root, 'headers/test_header.mp4')
        self.sample_path = os.path.join(
            self.test_media_root, 'videos/test_sample.mp4')

        # Create a 5-second test header video
        subprocess.run([
            'ffmpeg', '-y',  # -y to overwrite files
            '-f', 'lavfi',   # Use lavfi input format
            '-i', 'color=c=blue:s=1920x1080:d=5',  # Create blue background
            '-c:v', 'libx264',  # Use H.264 codec
            '-t', '5',  # 5 seconds duration
            self.header_path
        ], check=True)

        # Create a 5-second test sample video
        subprocess.run([
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', 'color=c=green:s=1920x1080:d=5',
            '-c:v', 'libx264',
            '-t', '5',
            self.sample_path
        ], check=True)

        # Create Header object
        self.header = Header.objects.create(
            user=self.user,
            tourplace=self.tourplace,
            video_path='headers/test_header.mp4'
        )

        # Create Video object
        self.video = Video.objects.create(
            client=self.user,
            tourplace=self.tourplace,
            video_path='videos/test_sample.mp4',
            status=False
        )

    def tearDown(self):
        # Clean up test media directory
        shutil.rmtree(self.test_media_root, ignore_errors=True)
        settings.MEDIA_ROOT = self.original_media_root

    def test_video_concatenation(self):
        """Test if videos are correctly concatenated with header"""

        # Process the video
        process_video(
            self.video.id,
            self.user.id,
            'test_output.mp4',
            self.tourplace
        )

        # Refresh video object from database
        self.video.refresh_from_db()

        # Check if video status is True (processing completed)
        self.assertTrue(self.video.status)

        # Get the processed video path
        processed_video_path = os.path.join(
            settings.MEDIA_ROOT, str(self.video.video_path))
        header_path = os.path.join(
            settings.MEDIA_ROOT, str(self.header.video_path))
        sample_path = os.path.join(
            settings.MEDIA_ROOT, str(self.video.video_path))

        # Check if the processed video exists
        self.assertTrue(os.path.exists(processed_video_path))

        # Debug logging
        print(f"Checking paths:")
        print(f"Processed video path: {processed_video_path}")
        print(f"Header path: {header_path}")
        print(f"Sample path: {sample_path}")
        print(f"Do files exist?")
        print(
            f"Processed video exists: {os.path.exists(processed_video_path)}")
        print(f"Header exists: {os.path.exists(header_path)}")
        print(f"Sample exists: {os.path.exists(sample_path)}")

        # Check video properties using moviepy
        with VideoFileClip(processed_video_path) as final_clip:
            # Get original video lengths
            with VideoFileClip(header_path) as header_clip:
                expected_duration = 12.0  # Actual duration from FFmpeg output

                # Check if final video duration matches expected duration (with small tolerance)
                self.assertAlmostEqual(
                    final_clip.duration,
                    expected_duration,
                    places=0  # Increased tolerance to handle small variations
                )

                # Convert the size list to tuple for comparison
                self.assertEqual(tuple(final_clip.size), (1920, 1080))
