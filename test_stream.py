import cv2
import sys

url = "http://10.85.118.54:8080/video"
print(f"Testing stream: {url}")
cap = cv2.VideoCapture(url)

if not cap.isOpened():
    print("Failed to open stream")
    sys.exit(1)

ret, frame = cap.read()
if ret:
    print(f"Successfully read frame! Shape: {frame.shape}")
else:
    print("Failed to read frame")

cap.release()
