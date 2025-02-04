import logging
from tourplace.models import TourPlace
from user.models import User
from videomgmt.models import Video, Header, Footer
from django.conf import settings
import django
import os
import sys
import subprocess
import hashlib
from datetime import datetime
from moviepy.editor import VideoFileClip, concatenate_videoclips
from django.core.wsgi import get_wsgi_application
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tourvideoproject.settings")
application = get_wsgi_application()

django.setup()

logging.basicConfig(level=logging.INFO, filename='video_processing.log', filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')


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
        'ffmpeg',  # Changed from '/usr/local/bin/ffmpeg' to just 'ffmpeg'
        '-y',  # Overwrite output files without asking
        '-i', input_path,  # Input file
        '-vf', f'scale={resolution}',
        '-r', str(frame_rate),  # Set frame rate
        '-c:v', 'libx264',  # Changed from h264_nvenc to libx264 for better compatibility
        '-preset', 'medium',  # Encoding preset
        '-b:v', bitrate,  # Video bitrate
        '-c:a', 'aac',  # Audio codec
        '-b:a', '128k',  # Audio bitrate
        '-movflags', 'faststart',  # Enable fast start
        output_path  # Output file
    ]

    logging.info(f"Converting {input_path} to {output_path}...")

    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            error_message = result.stderr.decode('utf-8')
            logging.error(f"FFmpeg conversion error: {error_message}")
            raise ValueError(f"Error converting video: {error_message}")
    except FileNotFoundError:
        logging.error(
            "FFmpeg not found. Please ensure FFmpeg is installed and in your system PATH")
        raise

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
        'ffmpeg', '-y',  # Changed from '/usr/local/bin/ffmpeg' to just 'ffmpeg'
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
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    concat_list_filename = f"concat_list_{current_time}.txt"

    try:
        with open(concat_list_filename, "w") as f:
            for input_path in input_paths:
                f.write(f"file '{input_path}'\n")

        command = [
            'ffmpeg',  # Changed from '/usr/local/bin/ffmpeg' to just 'ffmpeg'
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_list_filename,
            '-c:v', 'libx264',  # Changed from h264_nvenc to libx264
            '-preset', 'medium',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '48000',
            '-ac', '2',
            '-movflags', 'faststart',
            output_path
        ]

        logging.info(f"Starting to concatenate video clips...")
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            error_message = result.stderr.decode('utf-8')
            logging.error(f"Error concatenating videos: {error_message}")
            raise ValueError(f"Error concatenating videos: {error_message}")

    finally:
        if os.path.exists(concat_list_filename):
            os.remove(concat_list_filename)
            logging.info(
                f"Temporary concat list file {concat_list_filename} deleted.")


async def handle_video_processing(video, user, original_filename, tourplace):
    logging.info(f"Starting video processing for user: {user.username}")

    # Get header
    header = Header.objects.filter(
        tourplace=tourplace.pk).order_by('?').first()
    if not header:
        logging.info(f"Header doesn't exist for tourplace: {tourplace.pk}")
        video.status = False
        video.save()
        video_url = "https://api.emmysvideos.com/media/" + \
            str(video.video_path)
        send_notification_email(user, video_url, '')
        return False

    try:
        # Convert the uploaded video
        current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_video_path = os.path.join(
            settings.MEDIA_ROOT, str(video.video_path))
        converted_video_path = os.path.join(
            settings.MEDIA_ROOT,
            f'converted_video_{user.username}_{current_time}.mp4'
        )

        # Convert video to MP4
        convert_webm_to_mp4(temp_video_path, converted_video_path)

        # Generate final video name and paths
        final_video_name = generate_unique_filename(
            original_filename, user.username)
        final_video_relative_path = os.path.join('videos', final_video_name)
        final_video_absolute_path = os.path.join(
            settings.MEDIA_ROOT, final_video_relative_path
        )

        # Re-encode audio for both videos
        reencode_audio(header.video_path.path,
                       f"{header.video_path.path}_reencoded.mp4")
        reencode_audio(converted_video_path,
                       f"{converted_video_path}_reencoded.mp4")

        # Concatenate videos
        concatenate_videos_gpu(
            final_video_absolute_path,
            f"{header.video_path.path}_reencoded.mp4",
            f"{converted_video_path}_reencoded.mp4"
        )

        # Update video path and status
        final_video_relative_path = final_video_relative_path.replace(
            '\\', '/')
        video.video_path = final_video_relative_path
        video.status = True
        video.save()

        # Send email notification
        video_url = "https://api.emmysvideos.com/media/" + final_video_relative_path
        send_notification_email(user, video_url, final_video_name)

        return True

    except Exception as e:
        logging.error(f"Error processing video: {str(e)}")
        return False

    finally:
        # Clean up temporary files
        cleanup_paths = [
            temp_video_path,
            converted_video_path,
            f"{header.video_path.path}_reencoded.mp4",
            f"{converted_video_path}_reencoded.mp4"
        ]
        for path in cleanup_paths:
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 5:
            logging.error(
                f"Incorrect number of arguments. Received {len(sys.argv)} arguments")
            print(
                "Usage: python video_processing.py <video_id> <user_id> <original_filename> <tourplace>")
            sys.exit(1)

        video_id = sys.argv[1]
        user_id = sys.argv[2]
        original_filename = sys.argv[3]
        tourplace_id = sys.argv[4]

        logging.info(
            f"Received arguments - video_id: {video_id}, user_id: {user_id}, tourplace_id: {tourplace_id}")

        # Validate tourplace_id
        if not tourplace_id or tourplace_id == '""':
            logging.error("Empty tourplace_id received")
            sys.exit(1)

        # Convert to integer and get tourplace object
        tourplace_id = int(tourplace_id)
        tourplace = TourPlace.objects.get(pk=tourplace_id)

        logging.info(
            f"Starting Video Editing for tourplace_id: {tourplace_id}")
        process_video(video_id, user_id, original_filename, tourplace)

    except Exception as e:
        logging.error(f"Error in video processing: {str(e)}")
        sys.exit(1)
