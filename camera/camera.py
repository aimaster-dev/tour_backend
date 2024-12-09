import cv2
import os
import urllib.request
import numpy as np
from django.conf import settings

# Load the face detection model
face_detection_videocam = cv2.CascadeClassifier(os.path.join(
			settings.BASE_DIR, 'opencv_haarcascade_data/haarcascade_frontalface_default.xml'))
face_detection_webcam = cv2.CascadeClassifier(os.path.join(
			settings.BASE_DIR, 'opencv_haarcascade_data/haarcascade_frontalface_default.xml'))

class VideoCamera(object):
	def __init__(self):
		self.video = cv2.VideoCapture(0)

	def __del__(self):
		self.video.release()

	def get_frame(self):
		success, image = self.video.read()
		
		# Using CUDA for grayscale conversion
		gpu_frame = cv2.cuda_GpuMat()  # Initialize GpuMat for CUDA operations
		gpu_frame.upload(image)  # Upload frame to GPU
		gray_gpu = cv2.cuda.cvtColor(gpu_frame, cv2.COLOR_BGR2GRAY)  # Convert to grayscale using CUDA

		# Download back the processed frame to CPU memory for face detection
		gray = gray_gpu.download()

		faces_detected = face_detection_videocam.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)
		for (x, y, w, h) in faces_detected:
			cv2.rectangle(image, pt1=(x, y), pt2=(x + w, y + h), color=(255, 0, 0), thickness=2)
		
		# Use CUDA for flipping the frame
		gpu_frame.upload(image)  # Re-upload the frame with rectangles
		flipped_gpu = cv2.cuda.flip(gpu_frame, 1)  # Flip using CUDA
		flipped_image = flipped_gpu.download()  # Download flipped image back to CPU

		ret, jpeg = cv2.imencode('.jpg', flipped_image)
		return jpeg.tobytes()


class IPWebCam(object):
	def __init__(self):
		self.url = "http://192.168.43.1:8080/shot.jpg"

	def __del__(self):
		cv2.destroyAllWindows()

	def get_frame(self):
		imgResp = urllib.request.urlopen(self.url)
		imgNp = np.array(bytearray(imgResp.read()), dtype=np.uint8)
		img = cv2.imdecode(imgNp, -1)
		
		# Using CUDA for grayscale conversion
		gpu_frame = cv2.cuda_GpuMat()
		gpu_frame.upload(img)
		gray_gpu = cv2.cuda.cvtColor(gpu_frame, cv2.COLOR_BGR2GRAY)
		gray = gray_gpu.download()

		faces_detected = face_detection_webcam.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)
		for (x, y, w, h) in faces_detected:
			cv2.rectangle(img, pt1=(x, y), pt2=(x + w, y + h), color=(255, 0, 0), thickness=2)
		
		# Resize and flip using CUDA
		gpu_frame.upload(img)
		resized_gpu = cv2.cuda.resize(gpu_frame, (640, 480))
		flipped_gpu = cv2.cuda.flip(resized_gpu, 1)
		flipped_image = flipped_gpu.download()

		ret, jpeg = cv2.imencode('.jpg', flipped_image)
		return jpeg.tobytes()


class LiveWebCam(object):
	def __init__(self, rtsp_url):
		self.url = cv2.VideoCapture(rtsp_url)

	def __del__(self):
		cv2.destroyAllWindows()

	def get_frame(self):
		success, imgNp = self.url.read()

		if imgNp is None or imgNp.size == 0:
			print("Error: Frame is empty!")
		ret, jpeg = cv2.imencode('.jpg', imgNp)

		# Return the encoded image
		return jpeg.tobytes()

		# success, imgNp = self.url.read()

		# # Use CUDA for resizing
		# gpu_frame = cv2.cuda_GpuMat()
		# gpu_frame.upload(imgNp)
		# resized_gpu = cv2.cuda.resize(gpu_frame, (1280, 960))
		# resized_image = resized_gpu.download()

		# ret, jpeg = cv2.imencode('.jpg', resized_image)
		# return jpeg.tobytes()