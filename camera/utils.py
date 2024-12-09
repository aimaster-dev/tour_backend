import subprocess
import os
import hashlib

processes = {}

def hash_string(rtsp_url):
    return hashlib.sha256(rtsp_url.encode()).hexdigest()

def get_output_dir(rtsp_url):
    hashed_name = hash_string(rtsp_url)
    return f'media/hls/{hashed_name}'

def convert_rtsp_to_hls(rtsp_url, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    command = [
        '/usr/local/bin/ffmpeg', '-rtsp_transport', 'udp', '-analyzeduration', '100000', '-probesize', '100000',
        '-i', rtsp_url,
        '-c:v', 'h264_nvenc', '-preset', 'ultrafast', '-tune', 'zerolatency', '-cq:v', '28',
        '-c:a', 'aac', '-ar', '44100', '-b:a', '128k',
        '-f', 'hls', '-hls_time', '1', '-hls_list_size', '2',
        '-hls_flags', 'delete_segments+single_file', '-hls_start_number_source', 'epoch',
        '-hls_delete_threshold', '1',
        f'{output_dir}/index.m3u8'
    ]

    process = subprocess.Popen(command)
    processes[output_dir] = process

def stop_stream(output_dir):
    process = processes.get(output_dir)
    if process:
        process.terminate()
        process.wait()
        del processes[output_dir]
    if os.path.exists(output_dir):
        for root, dirs, files in os.walk(output_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(output_dir)
