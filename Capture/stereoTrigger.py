import os
import time
from pathlib import Path

import lgpio

# Configure libcamera before importing Picamera2
PROJECT_ROOT = Path(__file__).resolve().parents[0]
OV9281_DIR = PROJECT_ROOT / "ov9281_libcamera"

os.environ["LIBCAMERA_RPI_CONFIG_FILE"] = str(
    OV9281_DIR / "timeout.yaml"
)

from picamera2 import Picamera2


# ---------------------------------------------------------
# GPIO trigger
# ---------------------------------------------------------
GPIO = 23

gpio = lgpio.gpiochip_open(0)

# Output starts low
lgpio.gpio_claim_output(gpio, GPIO, 0)


def trigger():
    # Rising edge
    lgpio.gpio_write(gpio, GPIO, 1)

    # Falling edge
    lgpio.gpio_write(gpio, GPIO, 0)


# ---------------------------------------------------------
# Hardware trigger mode
# ---------------------------------------------------------
def enable_trigger():
    trigger_bin = OV9281_DIR / "ov9281_trigger"

    # Enable trigger on both cameras
    os.system(f"{trigger_bin} 10 1")
    os.system(f"{trigger_bin} 11 1")


def disable_trigger():
    trigger_bin = OV9281_DIR / "ov9281_trigger"

    os.system(f"{trigger_bin} 10 0")
    os.system(f"{trigger_bin} 11 0")


# ---------------------------------------------------------
# Cameras
# ---------------------------------------------------------
left_cam = Picamera2(1)
right_cam = Picamera2(0)

mode = left_cam.sensor_modes[0]

config = left_cam.create_video_configuration(
    raw={
        "format": mode["format"],
        "size": mode["size"],
    },
    sensor={
        "output_size": mode["size"],
        "bit_depth": mode["bit_depth"],
    },
    buffer_count=2,
    queue=True,
    controls={
        "FrameDurationLimits": (3333, 3333),
    },
)

left_cam.configure(config)
right_cam.configure(config)


# ---------------------------------------------------------
# Start
# ---------------------------------------------------------
print("Starting cameras...")

left_cam.start()
right_cam.start()

time.sleep(1)

print("Enabling external trigger mode...")

enable_trigger()

print("Waiting for trigger pulses...")
print("Press Ctrl+C to stop")


# ---------------------------------------------------------
# Capture
# ---------------------------------------------------------
frame_count = 0
start_time = time.perf_counter()

try:
    while True:

        #print("Waiting for trigger", flush=True)
        trigger()
        trigger_time = time.perf_counter()

        # Wait for externally triggered frame
        left_frame = left_cam.capture_array("raw")
        left_timestamp = time.time_ns()

        #print("Captured left image", flush=True)

        # Wait for externally triggered frame
        right_frame = right_cam.capture_array("raw")
        right_timestamp = time.time_ns()

        #print("Captured right image", flush=True)

        # Difference between Raspberry Pi timestamps
        sync_error_ns = right_timestamp - left_timestamp

        frame_count += 1

        elapsed = time.perf_counter() - start_time
        fps = frame_count / elapsed

        print(
            f"Frame {frame_count} | "
            f"Left: {left_timestamp} ns | "
            f"Right: {right_timestamp} ns | "
            f"Delta: {sync_error_ns / 1e6:.3f} ms | "
            f"FPS: {fps:.2f}\n",
            flush=False,
        )

except KeyboardInterrupt:
    print("\nStopping...", flush=True)


finally:
    print("Disabling trigger mode...")
    disable_trigger()

    print("Stopping cameras...")

    for cam in (left_cam, right_cam):
        try:
            cam.stop()
        except Exception as e:
            print(e)

    lgpio.gpio_free(gpio, GPIO)
    lgpio.gpiochip_close(gpio)

    print("Shutdown complete.")