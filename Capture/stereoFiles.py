from picamera2 import Picamera2
import os
import time
from PIL import Image

# Output directories
left_dir = "frames/left"
right_dir = "frames/right"

os.makedirs(left_dir, exist_ok=True)
os.makedirs(right_dir, exist_ok=True)

# Get cameras
leftCam = Picamera2(0)
rightCam = Picamera2(1)

# Get high speed configuration
camMode = leftCam.sensor_modes[0]

# Manually create custom high speed configuration
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

# Configure both cameras
leftCam.configure(config)
rightCam.configure(config)

# Activate both cameras
leftCam.start()
rightCam.start()

# Give cameras time to start
time.sleep(1)

# Framerate tracking variables
frame_count = 0
start_time = time.perf_counter()
last_time = start_time
last_count = 0

try:
    while True:
        leftRaw = leftCam.capture_array("raw")
        rightRaw = rightCam.capture_array("raw")

        # Save frames
        left_path = os.path.join(left_dir, f"{frame_count:08d}.png")
        right_path = os.path.join(right_dir, f"{frame_count:08d}.png")

        Image.fromarray(leftRaw).save(left_path)
        Image.fromarray(rightRaw).save(right_path)

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

except KeyboardInterrupt:
    print("\nStopping...")

finally:
    leftCam.stop()
    rightCam.stop()