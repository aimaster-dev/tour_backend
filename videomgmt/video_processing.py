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

import django
django.setup()
from django.conf import settings
from videomgmt.models import Video, Header, Footer
from user.models import User
from tourplace.models import TourPlace
import logging

logging.basicConfig(level=logging.INFO, filename='video_processing.log', filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')

def generate_unique_filename(original_filename, username):
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    hash_input = f"{original_filename}{username}{current_datetime}".encode('utf-8')
    hash_object = hashlib.sha256(hash_input)
    hash_hex = hash_object.hexdigest()[:16]  # Get the first 16 characters of the hash
    name, _ = os.path.splitext(original_filename)
    return f"{name}_{hash_hex}.mp4"

def convert_webm_to_mp4(input_path, output_path, resolution='1920x1080', frame_rate=30, bitrate='5M'):
    """
    Converts a .webm file to .mp4 with specified resolution, frame rate, and bitrate.
    """
    command = [
        '/usr/local/bin/ffmpeg',
        '-y',  # Overwrite output files without asking
        '-i', input_path,  # Input file
        '-vf', f'scale={resolution}',  # Video filter: scale to desired resolution
        '-r', str(frame_rate),  # Set frame rate
        '-c:v', 'h264_nvenc',  # Use NVIDIA's H.264 encoder
        '-preset', 'medium',  # Encoding preset
        '-b:v', bitrate,  # Video bitrate
        '-c:a', 'aac',  # Audio codec
        '-b:a', '128k',  # Audio bitrate
        '-movflags', 'faststart',  # Enable fast start
        output_path  # Output file
    ]
    
    logging.info(f"Converting {input_path} to {output_path} with resolution {resolution}, frame rate {frame_rate}, and bitrate {bitrate}...")
    
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    if result.returncode != 0:
        # Log the full ffmpeg stderr output for better debugging
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
        '/usr/local/bin/ffmpeg', '-y',  # Overwrite files
        '-i', input_path,  # Input video file
        '-c:v', 'copy',  # Copy video without re-encoding
        '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2',  # Re-encode audio
        output_path  # Output file
    ]
    logging.info(f"Re-encoding audio for {input_path} to {output_path}...")
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        error_message = result.stderr.decode('utf-8')
        logging.error(f"FFmpeg audio re-encoding error: {error_message}")
        raise ValueError(f"Error re-encoding audio: {error_message}")
    logging.info(f"Re-encoding successful: {output_path}")

def concatenate_videos_gpu(output_path, *input_paths):
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    concat_list_filename = f"concat_list_{current_time}.txt"
    with open(concat_list_filename, "w") as f:
        for input_path in input_paths:
            f.write(f"file '{input_path}'\n")
    # output_path_mkv = output_path.replace('.mp4', '.mkv')
    command = [
        '/usr/local/bin/ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list_filename,
        '-c:v', 'h264_nvenc', '-preset', 'medium', '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2',
        '-movflags', 'faststart', output_path
    ]
    logging.info(f"Starting to concatenate video clips using GPU with list {concat_list_filename}...")
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        logging.info(f"Error concatenating videos: {result.stderr.decode('utf-8')}")
        raise ValueError(f"Error concatenating videos: {result.stderr.decode('utf-8')}")
    os.remove(concat_list_filename)
    logging.info(f"Temporary concat list file {concat_list_filename} deleted.")

def process_video(video_id, user_id, original_filename, tourplace):
    video = Video.objects.get(pk=video_id)
    user = User.objects.get(pk=user_id)

    header = Header.objects.filter(tourplace = tourplace.pk).order_by('?').first()
    footer = Footer.objects.filter(tourplace = tourplace.pk).order_by('?').first()

    if not header or not footer:
        logging.info(f"Header and Footer doesn't existed...: {tourplace.pk}")
        video.status = False
        video.save()
        video_url = "https://api.emmysvideos.com/media/" + str(video.video_path)
        send_notification_email(user, video_url, '')
        return
    logging.info("Header and Footer existed")
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_video_path = os.path.join(settings.MEDIA_ROOT, str(video.video_path))
    converted_video_path = os.path.join(settings.MEDIA_ROOT, f'converted_video_{user.username}_{current_time}.mp4')
    convert_webm_to_mp4(temp_video_path, converted_video_path)
    logging.info(f"Finished process for video_id: {video_id}, user_id: {user_id}")
    try:
        logging.info("Preparing to concatenate video clips using GPU...")

        final_video_name = generate_unique_filename(original_filename, user.username)
        final_video_relative_path = os.path.join('videos', final_video_name)
        final_video_absolute_path = os.path.join(settings.MEDIA_ROOT, final_video_relative_path)
        reencode_audio(header.video_path.path, f"{header.video_path.path}_reencoded.mp4")
        reencode_audio(footer.video_path.path, f"{footer.video_path.path}_reencoded.mp4")
        reencode_audio(converted_video_path, f"{converted_video_path}_reencoded.mp4")
        # Use ffmpeg to concatenate the videos with GPU acceleration
        concatenate_videos_gpu(final_video_absolute_path, f"{header.video_path.path}_reencoded.mp4", f"{converted_video_path}_reencoded.mp4", f"{footer.video_path.path}_reencoded.mp4")

        final_video_relative_path = final_video_relative_path.replace('\\', '/')
        logging.info(f"Saving {final_video_relative_path}...")
        video.video_path = final_video_relative_path
        video.status = True
        video.save()
        logging.info(f"Saved {video.video_path}...")
        video_url = "https://api.emmysvideos.com/media/" + final_video_relative_path
        send_notification_email(user, video_url, final_video_name)
        logging.info("Finalizing...")
        
    finally:
        logging.info("Cleaning up temporary files...")
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        if os.path.exists(converted_video_path):
            os.remove(converted_video_path)
        logging.info("Finalizing Cleaning...")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python video_processing.py <video_id> <user_id> <original_filename> <tourplace>")
        sys.exit(1)
    
    video_id = int(sys.argv[1])
    user_id = int(sys.argv[2])
    original_filename = sys.argv[3]
    tourplace_id = int(sys.argv[4])
    tourplace = TourPlace.objects.get(pk = tourplace_id)
    logging.info(f"Starting Video Editing...")
    process_video(video_id, user_id, original_filename, tourplace)
