import csv
import threading
import time

from mpu6050 import MPU6050


def captureQuatData(outputfilelocation):
    """
    Capture MPU-6050 DMP quaternion data on a background thread.

    CSV:
        timestamp_ns,w,x,y,z

    Returns:
        stop_event, thread
    """

    stop_event = threading.Event()

    def capture_loop():

        imu = None
        frame_count = 0
        start_time = time.perf_counter()

        try:
            # -------------------------------------------------
            # IMU
            # -------------------------------------------------
            imu = MPU6050(
                a_bus=1,
                a_address=0x68,
                freq_divider=4,
            )

            print(
                "Initializing IMU DMP...",
                flush=True,
            )

            result = imu.dmp_initialize()

            if result != 0:
                raise RuntimeError(
                    f"DMP initialization failed: {result}"
                )

            imu.set_DMP_enabled(True)

            packet_size = (
                imu.DMP_get_FIFO_packet_size()
            )

            print(
                f"IMU ready | "
                f"DMP packet: {packet_size} bytes",
                flush=True,
            )

            # -------------------------------------------------
            # CSV
            # -------------------------------------------------
            with open(
                outputfilelocation,
                "w",
                newline="",
                buffering=1024 * 1024,
            ) as f:

                writer = csv.writer(f)

                writer.writerow([
                    "timestamp_ns",
                    "w",
                    "x",
                    "y",
                    "z",
                ])

                f.flush()

                # -------------------------------------------------
                # Capture
                # -------------------------------------------------
                while not stop_event.is_set():

                    # ---------------------------------------------
                    # Wait for a complete DMP packet.
                    #
                    # We intentionally do NOT poll INT_STATUS here.
                    # FIFO count is sufficient and avoids clearing
                    # the interrupt state while polling.
                    # ---------------------------------------------
                    while not stop_event.is_set():

                        fifo_count = (
                            imu.get_FIFO_count()
                        )

                        # FIFO overflow
                        if fifo_count >= 1024:
                            print(
                                "IMU FIFO overflow - resetting",
                                flush=True,
                            )

                            imu.reset_FIFO()
                            continue

                        if fifo_count >= packet_size:
                            break

                        # Give the CPU a tiny break while polling.
                        time.sleep(0.0001)

                    if stop_event.is_set():
                        break

                    # ---------------------------------------------
                    # Timestamp using Raspberry Pi system clock
                    # ---------------------------------------------
                    timestamp = time.time_ns()

                    # ---------------------------------------------
                    # Read exactly one DMP packet
                    # ---------------------------------------------
                    fifo = imu.get_FIFO_bytes(
                        packet_size
                    )

                    # ---------------------------------------------
                    # Extract quaternion
                    # ---------------------------------------------
                    q = imu.DMP_get_quaternion(
                        fifo
                    )

                    # ---------------------------------------------
                    # Write
                    # ---------------------------------------------
                    writer.writerow([
                        timestamp,
                        f"{q.w:.6f}",
                        f"{q.x:.6f}",
                        f"{q.y:.6f}",
                        f"{q.z:.6f}",
                    ])

                    frame_count += 1

                    # Flush frequently enough that data is visible
                    # during recording, without flushing every sample.
                    if frame_count % 10 == 0:
                        f.flush()

                        elapsed = (
                            time.perf_counter()
                            - start_time
                        )

                        fps = (
                            frame_count / elapsed
                        )

                        print(
                            f"IMU {frame_count} | "
                            f"{fps:.1f} Hz",
                            flush=True,
                        )

                # Make sure everything reaches the drive.
                f.flush()

        except Exception as e:
            print(
                f"IMU capture error: {e}",
                flush=True,
            )

        finally:
            if imu is not None:
                try:
                    imu.set_DMP_enabled(False)
                except Exception:
                    pass

            print(
                f"IMU stopped | "
                f"{frame_count} samples",
                flush=True,
            )

    # ---------------------------------------------------------
    # Start thread
    # ---------------------------------------------------------
    thread = threading.Thread(
        target=capture_loop,
        name="IMUCapture",
        daemon=True,
    )

    thread.start()

    return stop_event, thread
