import os
import time
import json
import struct
import threading
from pathlib import Path

import lgpio

# ---------------------------------------------------------
# Configure libcamera BEFORE importing Picamera2
# ---------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[0]
OV9281_DIR = PROJECT_ROOT / "ov9281_libcamera"

os.environ["LIBCAMERA_RPI_CONFIG_FILE"] = str(
    OV9281_DIR / "timeout.yaml"
)

from picamera2 import Picamera2


# ---------------------------------------------------------
# Stereo capture
# ---------------------------------------------------------
def captureStereoData(output_file_location):
    """
    Start stereo camera capture in a background thread.

    Each binary frame contains:

        uint64 trigger_timestamp_ns
        uint64 left_timestamp_ns
        uint64 right_timestamp_ns
        left raw frame
        right raw frame

    Returns:
        stop_event, thread

    Call:
        stop_event.set()
        thread.join()

    to stop recording.
    """

    stop_event = threading.Event()

    def capture_loop():

        GPIO = 23

        gpio = None
        left_cam = None
        right_cam = None

        frame_count = 0

        try:
            # -------------------------------------------------
            # GPIO
            # -------------------------------------------------
            gpio = lgpio.gpiochip_open(0)

            lgpio.gpio_claim_output(
                gpio,
                GPIO,
                0,
            )

            def trigger():
                # Very short GPIO pulse.
                lgpio.gpio_write(gpio, GPIO, 1)
                lgpio.gpio_write(gpio, GPIO, 0)

            # -------------------------------------------------
            # Hardware trigger mode
            # -------------------------------------------------
            trigger_bin = OV9281_DIR / "ov9281_trigger"

            os.system(
                f"{trigger_bin} 10 1"
            )

            os.system(
                f"{trigger_bin} 11 1"
            )

            # -------------------------------------------------
            # Cameras
            # -------------------------------------------------
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
                    "FrameDurationLimits": (
                        3333,
                        3333,
                    ),
                },
            )

            left_cam.configure(config)
            right_cam.configure(config)

            # -------------------------------------------------
            # Start cameras
            # -------------------------------------------------
            print(
                "Starting cameras...",
                flush=True,
            )

            left_cam.start()
            right_cam.start()

            time.sleep(1)

            print(
                "Stereo cameras ready",
                flush=True,
            )

            print(
                f"Recording to: {output_file_location}",
                flush=True,
            )

            # -------------------------------------------------
            # Open output file
            # -------------------------------------------------
            with open(
                output_file_location,
                "wb",
                buffering=1024 * 1024,
            ) as f:

                # -------------------------------------------------
                # First frame
                #
                # Used to determine shape/dtype for header.
                # -------------------------------------------------
                trigger()

                trigger_time = time.time_ns()

                left_frame = left_cam.capture_array(
                    "raw"
                )
                left_timestamp = time.time_ns()

                right_frame = right_cam.capture_array(
                    "raw"
                )
                right_timestamp = time.time_ns()

                # -------------------------------------------------
                # Ensure contiguous memory
                # -------------------------------------------------
                if not left_frame.flags["C_CONTIGUOUS"]:
                    left_frame = left_frame.copy()

                if not right_frame.flags["C_CONTIGUOUS"]:
                    right_frame = right_frame.copy()

                # -------------------------------------------------
                # Validate cameras
                # -------------------------------------------------
                if left_frame.shape != right_frame.shape:
                    raise RuntimeError(
                        "Camera shapes differ: "
                        f"left={left_frame.shape}, "
                        f"right={right_frame.shape}"
                    )

                if left_frame.dtype != right_frame.dtype:
                    raise RuntimeError(
                        "Camera dtypes differ: "
                        f"left={left_frame.dtype}, "
                        f"right={right_frame.dtype}"
                    )

                # -------------------------------------------------
                # Header
                # -------------------------------------------------
                header = {
                    "format": "stereo_raw_v1",
                    "shape": left_frame.shape,
                    "dtype": str(left_frame.dtype),
                    "frame_bytes": left_frame.nbytes,
                }

                header_bytes = json.dumps(
                    header
                ).encode("utf-8")

                # 8 bytes: header length
                # N bytes: JSON header
                f.write(
                    struct.pack(
                        "<Q",
                        len(header_bytes),
                    )
                )

                f.write(header_bytes)

                # -------------------------------------------------
                # Frame writer
                # -------------------------------------------------
                def write_frame(
                    trigger_time,
                    left_timestamp,
                    right_timestamp,
                    left_frame,
                    right_frame,
                ):

                    # Three uint64 timestamps
                    f.write(
                        struct.pack(
                            "<QQQ",
                            trigger_time,
                            left_timestamp,
                            right_timestamp,
                        )
                    )

                    # Raw frames
                    f.write(
                        left_frame.data
                    )

                    f.write(
                        right_frame.data
                    )

                # -------------------------------------------------
                # Write first frame
                # -------------------------------------------------
                write_frame(
                    trigger_time,
                    left_timestamp,
                    right_timestamp,
                    left_frame,
                    right_frame,
                )

                frame_count = 1

                start_time = time.perf_counter()

                # -------------------------------------------------
                # Capture loop
                # -------------------------------------------------
                while not stop_event.is_set():

                    # ---------------------------------------------
                    # Trigger both cameras
                    # ---------------------------------------------
                    trigger()

                    trigger_time = time.time_ns()

                    # ---------------------------------------------
                    # Left camera
                    # ---------------------------------------------
                    left_frame = left_cam.capture_array(
                        "raw"
                    )

                    left_timestamp = time.time_ns()

                    # ---------------------------------------------
                    # Right camera
                    # ---------------------------------------------
                    right_frame = right_cam.capture_array(
                        "raw"
                    )

                    right_timestamp = time.time_ns()

                    # ---------------------------------------------
                    # Write
                    # ---------------------------------------------
                    write_frame(
                        trigger_time,
                        left_timestamp,
                        right_timestamp,
                        left_frame,
                        right_frame,
                    )

                    frame_count += 1

                    # ---------------------------------------------
                    # Stats
                    # ---------------------------------------------
                    elapsed = (
                        time.perf_counter()
                        - start_time
                    )

                    fps = frame_count / elapsed

                    sync_error_ns = (
                        right_timestamp
                        - left_timestamp
                    )

                    if frame_count % 10 == 0:
                        print(
                            f"Stereo frame {frame_count} | "
                            f"Delta: "
                            f"{sync_error_ns / 1e6:.3f} ms | "
                            f"FPS: {fps:.2f}",
                            flush=True,
                        )

                # Flush remaining buffered data
                f.flush()

        except Exception as e:
            print(
                f"Stereo capture error: {e}",
                flush=True,
            )

        finally:

            # -----------------------------------------------------
            # Disable hardware trigger
            # -----------------------------------------------------
            try:
                trigger_bin = (
                    OV9281_DIR / "ov9281_trigger"
                )

                os.system(
                    f"{trigger_bin} 10 0"
                )

                os.system(
                    f"{trigger_bin} 11 0"
                )

            except Exception as e:
                print(
                    f"Trigger shutdown error: {e}",
                    flush=True,
                )

            # -----------------------------------------------------
            # Stop cameras
            # -----------------------------------------------------
            print(
                "Stopping stereo cameras...",
                flush=True,
            )

            for cam in (
                left_cam,
                right_cam,
            ):
                if cam is not None:
                    try:
                        cam.stop()
                    except Exception as e:
                        print(
                            f"Camera shutdown error: {e}",
                            flush=True,
                        )

            # -----------------------------------------------------
            # GPIO cleanup
            # -----------------------------------------------------
            if gpio is not None:
                try:
                    lgpio.gpio_free(
                        gpio,
                        GPIO,
                    )

                    lgpio.gpiochip_close(
                        gpio
                    )

                except Exception as e:
                    print(
                        f"GPIO shutdown error: {e}",
                        flush=True,
                    )

            print(
                f"Stereo capture stopped | "
                f"{frame_count} frames",
                flush=True,
            )

    # ---------------------------------------------------------
    # Start worker
    # ---------------------------------------------------------
    thread = threading.Thread(
        target=capture_loop,
        name="StereoCapture",
        daemon=True,
    )

    thread.start()

    return stop_event, thread
