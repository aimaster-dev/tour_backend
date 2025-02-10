import logging
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from moviepy.editor import VideoFileClip
from datetime import datetime
import hashlib
import subprocess
from django.conf import settings
from videomgmt.models import Video, Header, Footer
from user.models import User
from tourplace.models import TourPlace
import os
import sys
import django

# Set up Django environment FIRST before any other imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tourvideoproject.settings")
django.setup()

# Now we can import Django models

logging.basicConfig(level=logging.INFO, filename='video_processing.log', filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Define ffmpeg path based on environment
FFMPEG_PATH = (
    '/usr/local/bin/ffmpeg' if os.path.exists('/usr/local/bin/ffmpeg')
    else '/usr/bin/ffmpeg' if os.path.exists('/usr/bin/ffmpeg')
    else 'ffmpeg'
)


def generate_unique_filename(original_filename, username):
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    hash_input = f"{original_filename}{username}{current_datetime}".encode(
        'utf-8')
    hash_object = hashlib.sha256(hash_input)
    # Get the first 16 characters of the hash
    hash_hex = hash_object.hexdigest()[:16]
    name, _ = os.path.splitext(original_filename)
    return f"{name}_{hash_hex}.mp4"


def convert_webm_to_mp4(input_path, output_path, resolution='1920x1080', frame_rate=30, bitrate='5M'):
    """
    Converts a .webm file to .mp4 with specified resolution, frame rate, and bitrate.
    """
    command = [
        FFMPEG_PATH,  # Use environment-specific path
        '-y',  # Overwrite output files without asking
        '-i', input_path,  # Input file
        # Video filter: scale to desired resolution
        '-vf', f'scale={resolution}',
        '-r', str(frame_rate),  # Set frame rate
        '-c:v', 'h264',  # Use H.264 encoder instead of NVIDIA
        '-preset', 'medium',  # Encoding preset
        '-b:v', bitrate,  # Video bitrate
        '-c:a', 'aac',  # Audio codec
        '-b:a', '128k',  # Audio bitrate
        '-movflags', 'faststart',  # Enable fast start
        output_path  # Output file
    ]

    logging.info(
        f"Converting {input_path} to {output_path} with resolution {resolution}, frame rate {frame_rate}, and bitrate {bitrate}...")

    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        error_message = result.stderr.decode('utf-8')
        logging.error(f"FFmpeg conversion error: {error_message}")
        raise ValueError(f"Error converting webm to mp4: {error_message}")

    logging.info(f"Conversion successful: {output_path}")


def send_notification_email(user, video_url, final_video_name):
    subject = 'Your Video Has Been Processed'
    message = render_to_string('video_success_email.html', {
        'user': user,
        'video_url': video_url,
        'video_name': final_video_name
    })
    email = EmailMessage(subject, message, to=[user.email])
    email.content_subtype = "html"
    email.send()


def reencode_audio(input_path, output_path):
    """
    Re-encodes the audio of the given input video to ensure uniformity.
    """
    command = [
        FFMPEG_PATH,  # Use environment-specific path
        '-y',  # Overwrite files
        '-i', input_path,  # Input video file
        '-c:v', 'copy',  # Copy video without re-encoding
        '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2',  # Re-encode audio
        output_path  # Output file
    ]
    logging.info(f"Re-encoding audio for {input_path} to {output_path}...")
    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        error_message = result.stderr.decode('utf-8')
        logging.error(f"FFmpeg audio re-encoding error: {error_message}")
        raise ValueError(f"Error re-encoding audio: {error_message}")
    logging.info(f"Re-encoding successful: {output_path}")


def concatenate_videos_gpu(output_path, *input_paths):
    """
    Concatenates multiple videos using FFmpeg with GPU acceleration if available,
    falls back to CPU if GPU encoding is not available.
    """
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    concat_list_filename = f"concat_list_{current_time}.txt"

    try:
        # Create concat list file with absolute paths
        with open(concat_list_filename, "w") as f:
            for input_path in input_paths:
                normalized_path = input_path.replace('\\', '/')
                f.write(f"file '{normalized_path}'\n")

        # Try GPU encoding first
        gpu_command = [
            FFMPEG_PATH,  # Use environment-specific path
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_list_filename,
            '-c:v', 'h264_nvenc',  # NVIDIA GPU encoder
            '-preset', 'medium',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '48000',
            '-ac', '2',
            '-movflags', 'faststart',
            output_path
        ]

        # Try GPU encoding first
        try:
            logging.info("Attempting GPU acceleration...")
            result = subprocess.run(
                gpu_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            logging.info("GPU acceleration successful")
            return
        except subprocess.CalledProcessError:
            logging.info("GPU encoding failed, falling back to CPU...")

        # Fallback to CPU encoding
        cpu_command = [
            FFMPEG_PATH,  # Use environment-specific path
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_list_filename,
            '-c:v', 'libx264',  # CPU encoder
            '-preset', 'medium',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '48000',
            '-ac', '2',
            '-movflags', 'faststart',
            output_path
        ]

        logging.info("Starting video concatenation with CPU...")
        result = subprocess.run(
            cpu_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        logging.info("CPU encoding successful")

    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode('utf-8')
        logging.error(f"FFmpeg concatenation error: {error_message}")
        raise ValueError(f"Error concatenating videos: {error_message}")
    except Exception as e:
        logging.error(f"Unexpected error during concatenation: {str(e)}")
        raise
    finally:
        # Clean up the temporary concat list file
        if os.path.exists(concat_list_filename):
            os.remove(concat_list_filename)
            logging.info(
                f"Temporary concat list file {concat_list_filename} deleted")


def process_video(video_id, user_id, original_filename, tourplace):
    video = Video.objects.get(pk=video_id)
    user = User.objects.get(pk=user_id)

    header = Header.objects.filter(
        tourplace=tourplace.pk).order_by('?').first()

    if not header:
        logging.info(f"Header doesn't exist for tourplace: {tourplace.pk}")
        video.status = False
        video.save()
        video_url = "https://api.emmysvideos.com/media/" + \
            str(video.video_path)
        send_notification_email(user, video_url, '')
        return

    logging.info("Header existed")

    # Get absolute paths for all files
    temp_video_path = os.path.abspath(os.path.join(
        settings.MEDIA_ROOT, str(video.video_path)))
    header_path = os.path.abspath(os.path.join(
        settings.MEDIA_ROOT, str(header.video_path)))

    # Log file existence and permissions
    logging.info(f"Checking file paths:")
    logging.info(
        f"Video path: {temp_video_path} (exists: {os.path.exists(temp_video_path)})")
    logging.info(
        f"Header path: {header_path} (exists: {os.path.exists(header_path)})")

    # Generate paths for temporary and final files
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    converted_video_path = os.path.join(
        settings.MEDIA_ROOT,
        'temp',
        f'converted_video_{user.username}_{current_time}.mp4'
    )

    # Ensure temp directory exists
    os.makedirs(os.path.dirname(converted_video_path), exist_ok=True)

    # Convert the video
    try:
        convert_webm_to_mp4(temp_video_path, converted_video_path)
        logging.info(f"Finished converting video for video_id: {video_id}")

        # Generate final paths
        final_video_name = generate_unique_filename(
            original_filename, user.username)
        final_video_relative_path = os.path.join('videos', final_video_name)
        final_video_absolute_path = os.path.join(
            settings.MEDIA_ROOT, final_video_relative_path)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(final_video_absolute_path), exist_ok=True)

        # Create temporary files for reencoded videos
        header_reencoded = os.path.join(
            settings.MEDIA_ROOT,
            'temp',
            f'header_reencoded_{current_time}.mp4'
        )
        video_reencoded = os.path.join(
            settings.MEDIA_ROOT,
            'temp',
            f'video_reencoded_{current_time}.mp4'
        )

        # Reencode audio for both videos
        reencode_audio(header_path, header_reencoded)
        reencode_audio(converted_video_path, video_reencoded)

        # Concatenate videos
        logging.info("Starting video concatenation...")
        concatenate_videos_gpu(
            final_video_absolute_path,
            header_reencoded,
            video_reencoded
        )

        # Update video object
        final_video_relative_path = final_video_relative_path.replace(
            '\\', '/')
        video.video_path = final_video_relative_path
        video.status = True
        video.save()

        # Send notification
        video_url = "https://api.emmysvideos.com/media/" + final_video_relative_path
        send_notification_email(user, video_url, final_video_name)
        logging.info("Video processing completed successfully")

    except Exception as e:
        logging.error(f"Error processing video: {str(e)}")
        video.status = False
        video.save()
        raise
    finally:
        # Clean up all temporary files
        temp_files = [
            converted_video_path,
            header_reencoded if 'header_reencoded' in locals() else None,
            video_reencoded if 'video_reencoded' in locals() else None
        ]

        for temp_file in temp_files:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    logging.info(f"Cleaned up temporary file: {temp_file}")
                except Exception as e:
                    logging.warning(
                        f"Failed to clean up {temp_file}: {str(e)}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python video_processing.py <video_id> <user_id> <original_filename> <tourplace>")
        sys.exit(1)

    video_id = int(sys.argv[1])
    user_id = int(sys.argv[2])
    original_filename = sys.argv[3]
    tourplace_id = int(sys.argv[4])
    tourplace = TourPlace.objects.get(pk=tourplace_id)
    logging.info(f"Starting Video Editing...")
    process_video(video_id, user_id, original_filename, tourplace)
