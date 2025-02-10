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
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class VideoProcessingTest(TestCase):
    def setUp(self):
        logging.info("Setting up test environment...")
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
        """Preserve test media directory for inspection"""
        print(f"\n=== Preserving Test Media Directory ===")
        print(f"Test files can be found at: {self.test_media_root}")
        # Comment out the cleanup to preserve files
        # try:
        #     shutil.rmtree(self.test_media_root, ignore_errors=True)
        # except Exception as e:
        #     print(f"Warning: Failed to clean up test media directory: {e}")
        settings.MEDIA_ROOT = self.original_media_root

    def test_video_concatenation(self):
        logging.info("Starting video concatenation test...")
        """Test if videos are correctly concatenated with header"""

        print(f"\n=== Test Media Directory ===")
        print(f"Test media directory: {self.test_media_root}")
        print(f"This folder will be preserved for inspection")

        try:
            # Create directories if they don't exist
            os.makedirs(os.path.join(
                settings.MEDIA_ROOT, 'videos'), exist_ok=True)
            os.makedirs(os.path.join(
                settings.MEDIA_ROOT, 'headers'), exist_ok=True)
            os.makedirs(os.path.join(
                settings.MEDIA_ROOT, 'temp'), exist_ok=True)

            # Copy test files to their expected locations
            header_dest = os.path.join(
                settings.MEDIA_ROOT, str(self.header.video_path))
            sample_dest = os.path.join(
                settings.MEDIA_ROOT, str(self.video.video_path))

            # Ensure parent directories exist
            os.makedirs(os.path.dirname(header_dest), exist_ok=True)
            os.makedirs(os.path.dirname(sample_dest), exist_ok=True)

            # Copy files if they don't exist at destination
            if not os.path.exists(header_dest):
                shutil.copy2(self.header_path, header_dest)
            if not os.path.exists(sample_dest):
                shutil.copy2(self.sample_path, sample_dest)

            print("\n=== Before Processing ===")
            print(f"Video path in database: {self.video.video_path}")
            print(f"Header path in database: {self.header.video_path}")

            print("\nStarting video processing...")
            process_video(
                self.video.id,
                self.user.id,
                'test_output.mp4',
                self.tourplace
            )
            print("Video processing completed")

            # Refresh video object from database
            self.video.refresh_from_db()

            print("\n=== After Processing ===")
            print(f"Updated video path in database: {self.video.video_path}")

            # Get all possible paths where the video might be
            possible_paths = [
                os.path.join(settings.MEDIA_ROOT, str(self.video.video_path)),
                os.path.join(settings.MEDIA_ROOT, 'videos',
                             str(self.video.video_path)),
                os.path.join(settings.MEDIA_ROOT, 'videos',
                             os.path.basename(str(self.video.video_path))),
                str(self.video.video_path)
            ]

            print("\n=== Checking Possible Video Locations ===")
            for path in possible_paths:
                print(f"\nChecking path: {path}")
                print(f"Path exists: {os.path.exists(path)}")
                if os.path.exists(path):
                    print(f"File size: {os.path.getsize(path)} bytes")
                    print(f"Is file: {os.path.isfile(path)}")
                    print(f"Is readable: {os.access(path, os.R_OK)}")

            print("\n=== Directory Structure ===")
            print(f"Media Root: {settings.MEDIA_ROOT}")
            for root, dirs, files in os.walk(settings.MEDIA_ROOT):
                level = root.replace(settings.MEDIA_ROOT, '').count(os.sep)
                indent = ' ' * 4 * level
                print(f"{indent}{os.path.basename(root)}/")
                subindent = ' ' * 4 * (level + 1)
                for f in files:
                    print(f"{subindent}{f}")

            # Try to find the processed video
            processed_video = None
            for root, dirs, files in os.walk(settings.MEDIA_ROOT):
                for file in files:
                    if file.endswith('.mp4') and 'test_output' in file:
                        processed_video = os.path.join(root, file)
                        break
                if processed_video:
                    break

            if processed_video:
                print(f"\n=== Found Processed Video ===")
                print(f"Path: {processed_video}")
                print(f"Size: {os.path.getsize(processed_video)} bytes")
                print(
                    f"Last modified: {datetime.fromtimestamp(os.path.getmtime(processed_video))}")

                # Try to analyze the video
                with VideoFileClip(processed_video) as clip:
                    print(f"Duration: {clip.duration} seconds")
                    print(f"Size: {clip.size}")
                    print(f"FPS: {clip.fps}")
            else:
                print("\nWARNING: Could not find processed video!")

        except Exception as e:
            print(f"\n=== Error Occurred ===")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            import traceback
            traceback.print_exc()
            self.fail(f"Test failed: {str(e)}")
