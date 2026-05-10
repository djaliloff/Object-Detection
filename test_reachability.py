import requests
import sys

url = "http://10.85.118.54:8080/video"
print(f"Testing reachability with requests: {url}")
try:
    response = requests.get(url, timeout=5, stream=True)
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        print("Successfully reached the stream!")
        # Read a bit of the stream
        count = 0
        for chunk in response.iter_content(chunk_size=1024):
            count += 1
            if count > 10: break
        print("Successfully read some data from the stream.")
    else:
        print(f"Failed to reach the stream. Status: {response.status_code}")
except Exception as e:
    print(f"Error reaching stream: {e}")
