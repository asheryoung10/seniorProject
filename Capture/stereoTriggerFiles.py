import os
import time
import json
import struct
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
# Output
# ---------------------------------------------------------
OUTPUT_FILE = "/mnt/camdata/recording.bin"


# ---------------------------------------------------------
# GPIO trigger
# ---------------------------------------------------------
GPIO = 23

gpio = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(gpio, GPIO, 0)


def trigger():
    lgpio.gpio_write(gpio, GPIO, 1)
    lgpio.gpio_write(gpio, GPIO, 0)


# ---------------------------------------------------------
# Hardware trigger mode
# ---------------------------------------------------------
def enable_trigger():
    trigger_bin = OV9281_DIR / "ov9281_trigger"

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
# Start cameras
# ---------------------------------------------------------
print("Starting cameras...", flush=True)

left_cam.start()
right_cam.start()

time.sleep(1)

print("Enabling external trigger mode...", flush=True)

enable_trigger()
time.sleep(1)

print(f"Recording to: {OUTPUT_FILE}", flush=True)
print("Waiting for trigger pulses...", flush=True)
print("Press Ctrl+C to stop", flush=True)


# ---------------------------------------------------------
# Capture
# ---------------------------------------------------------
frame_count = 0
start_time = time.perf_counter()

with open(OUTPUT_FILE, "wb", buffering=1024 * 1024) as f:

    # Capture one frame first so we know the exact
    # dimensions and dtype for the binary file header.
    trigger()
    trigger_time = time.time_ns()

    left_frame = left_cam.capture_array("raw")
    left_timestamp = trigger_time

    right_frame = right_cam.capture_array("raw")
    right_timestamp = trigger_time

    # Make sure frames are contiguous in memory.
    left_frame = left_frame if left_frame.flags["C_CONTIGUOUS"] else left_frame.copy()
    right_frame = right_frame if right_frame.flags["C_CONTIGUOUS"] else right_frame.copy()

    # Both cameras should have the same format/shape.
    if left_frame.shape != right_frame.shape:
        raise RuntimeError(
            f"Camera shapes differ: "
            f"left={left_frame.shape}, right={right_frame.shape}"
        )

    if left_frame.dtype != right_frame.dtype:
        raise RuntimeError(
            f"Camera dtypes differ: "
            f"left={left_frame.dtype}, right={right_frame.dtype}"
        )

    # -----------------------------------------------------
    # Binary file header
    # -----------------------------------------------------
    header = {
        "format": "stereo_raw_v1",
        "shape": left_frame.shape,
        "dtype": str(left_frame.dtype),
        "frame_bytes": left_frame.nbytes,
    }

    header_bytes = json.dumps(header).encode("utf-8")

    # Header:
    #   8 bytes = header length
    #   N bytes = JSON header
    f.write(struct.pack("<Q", len(header_bytes)))
    f.write(header_bytes)

    # -----------------------------------------------------
    # Frame writer
    # -----------------------------------------------------
    def write_frame(
        trigger_time,
        left_timestamp,
        right_timestamp,
        left_frame,
        right_frame,
    ):
        # Three uint64 timestamps:
        # trigger, left receive time, right receive time
        f.write(
            struct.pack(
                "<QQQ",
                trigger_time,
                left_timestamp,
                right_timestamp,
            )
        )

        # Raw image data
        f.write(left_frame.data)
        f.write(right_frame.data)

    # Write first frame
    write_frame(
        trigger_time,
        left_timestamp,
        right_timestamp,
        left_frame,
        right_frame,
    )

    frame_count += 1

    try:
        while True:

            # -------------------------------------------------
            # Trigger
            # -------------------------------------------------
            trigger()
            trigger_time = time.time_ns()

            # -------------------------------------------------
            # Capture left
            # -------------------------------------------------
            left_frame = left_cam.capture_array("raw")
            print("Captured", flush=True)
            left_timestamp = trigger_time

            # -------------------------------------------------
            # Capture right
            # -------------------------------------------------
            right_frame = right_cam.capture_array("raw")
            print("Captured", flush=True)
            right_timestamp = trigger_time

            # -------------------------------------------------
            # Write binary record
            # -------------------------------------------------
            write_frame(
                trigger_time,
                left_timestamp,
                right_timestamp,
                left_frame,
                right_frame,
            )

            frame_count += 1

            # -------------------------------------------------
            # FPS
            # -------------------------------------------------
            elapsed = time.perf_counter() - start_time
            fps = frame_count / elapsed

            sync_error_ns = right_timestamp - left_timestamp

            print(
                f"Frame {frame_count} | "
                f"Delta: {sync_error_ns / 1e6:.3f} ms | "
                f"FPS: {fps:.2f}",
                flush=True,
            )

    except KeyboardInterrupt:
        print("\nStopping...", flush=True)


# ---------------------------------------------------------
# Shutdown
# ---------------------------------------------------------
print("Disabling trigger mode...", flush=True)
disable_trigger()

print("Stopping cameras...", flush=True)

for cam in (left_cam, right_cam):
    try:
        cam.stop()
    except Exception as e:
        print(e)

lgpio.gpio_free(gpio, GPIO)
lgpio.gpiochip_close(gpio)

print(f"Saved {frame_count} frames", flush=True)
print(f"File: {OUTPUT_FILE}", flush=True)
print("Shutdown complete.", flush=True)
