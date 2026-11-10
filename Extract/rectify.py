
from pathlib import Path
import cv2
import numpy as np

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

LEFT_DIR = Path("left")
RIGHT_DIR = Path("right")

LEFT_OUTPUT_DIR = Path("leftRectified")
RIGHT_OUTPUT_DIR = Path("rightRectified")

IMAGE_SIZE = (640, 400)  # width, height

# --------------------------------------------------
# CAMERA INTRINSICS
# --------------------------------------------------

K1 = np.array([
    [535.36938072, 0.0, 355.40622091],
    [0.0, 536.53025111, 205.86207886],
    [0.0, 0.0, 1.0]
], dtype=np.float64)

D1 = np.array([
    [-0.34711682, 0.15329214, -0.00367549,
     -0.01073926, -0.18104952]
], dtype=np.float64)

K2 = np.array([
    [530.3184002, 0.0, 331.80636407],
    [0.0, 530.36520213, 212.15825565],
    [0.0, 0.0, 1.0]
], dtype=np.float64)

D2 = np.array([
    [-0.349255, 0.30565206, -0.00532387,
     -0.01521311, -0.38702665]
], dtype=np.float64)

# --------------------------------------------------
# STEREO EXTRINSICS
# --------------------------------------------------

R = np.array([
    [ 9.99999171e-01, -3.36427001e-04,  1.24317011e-03],
    [ 3.33715671e-04,  9.99997567e-01,  2.18054515e-03],
    [-1.24390068e-03, -2.18012848e-03,  9.99996850e-01]
], dtype=np.float64)

T = np.array([
    [ 0.10518957],
    [-0.00275078],
    [-0.00770235]
], dtype=np.float64)

# --------------------------------------------------
# RECTIFICATION MATRICES
# --------------------------------------------------

R1 = np.array([
    [9.97072148e-01, -2.62481647e-02, -7.18203639e-02],
    [2.63274655e-02,  9.99653360e-01,  1.57567545e-04],
    [7.17913322e-02, -2.04795436e-03,  9.97417571e-01]
], dtype=np.float64)

R2 = np.array([
    [9.96990867e-01, -2.60719698e-02, -7.30031720e-02],
    [2.59913291e-02,  9.99660057e-01, -2.05455446e-03],
    [7.30319214e-02,  1.50922562e-04,  9.97329592e-01]
], dtype=np.float64)

P1 = np.array([
    [666.58263832, 0.0, 450.79271507, 0.0],
    [0.0, 666.58263832, 164.87558746, 0.0],
    [0.0, 0.0, 1.0, 0.0]
], dtype=np.float64)

P2 = np.array([
    [666.58263832, 0.0, 450.79271507, 70.32916798],
    [0.0, 666.58263832, 164.87558746, 0.0],
    [0.0, 0.0, 1.0, 0.0]
], dtype=np.float64)

# --------------------------------------------------
# CREATE RECTIFICATION MAPS
# --------------------------------------------------

map1x, map1y = cv2.initUndistortRectifyMap(
    K1, D1, R1, P1,
    IMAGE_SIZE,
    cv2.CV_32FC1
)

map2x, map2y = cv2.initUndistortRectifyMap(
    K2, D2, R2, P2,
    IMAGE_SIZE,
    cv2.CV_32FC1
)

# --------------------------------------------------
# RECTIFY ALL MATCHING PAIRS
# --------------------------------------------------

def main():

    LEFT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RIGHT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

    left_files = {
        p.name: p for p in LEFT_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    }

    right_files = {
        p.name: p for p in RIGHT_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    }

    common_names = sorted(set(left_files) & set(right_files))

    if not common_names:
        print("No matching image filenames found.")
        return

    print(f"Found {len(common_names)} matching image pairs.")

    processed = 0
    skipped = 0

    for filename in common_names:

        left = cv2.imread(str(left_files[filename]))
        right = cv2.imread(str(right_files[filename]))

        if left is None or right is None:
            print(f"[SKIP] Could not read {filename}")
            skipped += 1
            continue

        if (left.shape[1], left.shape[0]) != IMAGE_SIZE:
            print(f"[SKIP] Left image has unexpected size: {filename}")
            skipped += 1
            continue

        if (right.shape[1], right.shape[0]) != IMAGE_SIZE:
            print(f"[SKIP] Right image has unexpected size: {filename}")
            skipped += 1
            continue

        left_rectified = cv2.remap(
            left, map1x, map1y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT
        )

        right_rectified = cv2.remap(
            right, map2x, map2y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT
        )

        left_path = LEFT_OUTPUT_DIR / filename
        right_path = RIGHT_OUTPUT_DIR / filename

        if not cv2.imwrite(str(left_path), left_rectified):
            print(f"[ERROR] Could not save {left_path}")
            skipped += 1
            continue

        if not cv2.imwrite(str(right_path), right_rectified):
            print(f"[ERROR] Could not save {right_path}")
            skipped += 1
            continue

        processed += 1

        print(f"[OK] {filename}")

    print("\n------------------------------")
    print("RECTIFICATION COMPLETE")
    print("------------------------------")
    print(f"Processed: {processed}")
    print(f"Skipped:   {skipped}")
    print(f"Left output:  {LEFT_OUTPUT_DIR.resolve()}")
    print(f"Right output: {RIGHT_OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()

