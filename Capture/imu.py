import time

from mpu6050 import MPU6050


# ---------------------------------------------------------
# IMU
# ---------------------------------------------------------
# I2C bus 1
# MPU-6050 address 0x68
#
# freq_divider=4 gives the 200 Hz DMP configuration
# used by this implementation.
#
imu = MPU6050(
    a_bus=1,
    a_address=0x68,
    freq_divider=4,
)


# ---------------------------------------------------------
# Initialize DMP
# ---------------------------------------------------------
print("Initializing DMP...", flush=True)

result = imu.dmp_initialize()

if result != 0:
    raise RuntimeError(f"DMP initialization failed: {result}")

imu.set_DMP_enabled(True)

packet_size = imu.DMP_get_FIFO_packet_size()

print(
    f"DMP ready | packet size: {packet_size} bytes",
    flush=True,
)


# ---------------------------------------------------------
# Quaternion loop
# ---------------------------------------------------------
frame_count = 0
start_time = time.perf_counter()

try:
    while True:

        # Wait for a complete DMP packet.
        #
        # This checks the FIFO until the DMP has produced
        # a complete quaternion packet.
        while True:

            fifo_count = imu.get_FIFO_count()
            int_status = imu.get_int_status()

            # FIFO overflow
            if fifo_count >= 1024 or (int_status & 0x10):
                imu.reset_FIFO()
                continue

            # DMP packet available
            if int_status & 0x02 and fifo_count >= packet_size:
                break

        # Raspberry Pi timestamp immediately before
        # pulling the packet from the FIFO.
        timestamp = time.time_ns()

        # Read exactly one DMP packet.
        fifo = imu.get_FIFO_bytes(packet_size)

        # Extract quaternion.
        #
        # This returns the raw fixed-point quaternion:
        # w, x, y, z
        #
        q = imu.DMP_get_quaternion(fifo)

        frame_count += 1

        elapsed = time.perf_counter() - start_time
        fps = frame_count / elapsed

        print(
            f"{timestamp}, "
            f"{q.w:.6f}, "
            f"{q.x:.6f}, "
            f"{q.y:.6f}, "
            f"{q.z:.6f}, "
            f"{fps:.1f} Hz",
            flush=True,
        )

except KeyboardInterrupt:
    print("\nStopping...", flush=True)

finally:
    imu.set_DMP_enabled(False)
