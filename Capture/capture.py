from imuThread import captureQuatData
from stereoThread import captureStereoData

imu_stop, imu_thread = captureQuatData(
    "/mnt/camdata/quaternion.csv"
)

stereo_stop, stereo_thread = captureStereoData(
    "/mnt/camdata/stereo.bin"
)

try:
    # Coordinator stays alive while both workers run.
    stereo_thread.join()

except KeyboardInterrupt:
    print("\nStopping recording...", flush=True)

finally:
    imu_stop.set()
    stereo_stop.set()

    imu_thread.join()
    stereo_thread.join()

    print("Everything stopped.", flush=True)