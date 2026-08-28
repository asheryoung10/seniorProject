from picamera2 import Picamera2
from PIL import Image
import os
import time

# get cameras
leftCam = Picamera2(0)
rightCam = Picamera2(1)

# get high speed configuration
camMode = leftCam.sensor_modes[0]

# manually create custom high speed configuration
config = leftCam.create_video_configuration(
    raw={
        "format": camMode["format"],
        "size": camMode["size"],
    },
    sensor={
        "output_size": camMode["size"],
        "bit_depth": camMode["bit_depth"],
    },
    buffer_count=6,
    queue=False,
    controls={
        "FrameDurationLimits": (3333, 3333),
    },
)

# configure both cameras
leftCam.configure(config)
rightCam.configure(config)

# activate both cameras
leftCam.start()
rightCam.start()

# framerate tracking variables
frame_count = 0
start_time = time.perf_counter()
last_time = start_time
last_count = 0

while True:
    leftRaw = leftCam.capture_array("raw")
    rightRaw = rightCam.capture_array("raw")

    frame_count += 1

    # Report rolling FPS every 100 frames
    if frame_count % 100 == 0:
        now = time.perf_counter()
        interval = now - last_time
        total = now - start_time
        rolling_fps = (frame_count - last_count) / interval
        overall_fps = frame_count / total

        print(
            f"{frame_count} frames | "
            f"FPS: {rolling_fps:.2f} | "
            f"avg FPS: {overall_fps:.2f}",
            flush=True,
        )

        last_time = now
        last_count = frame_count