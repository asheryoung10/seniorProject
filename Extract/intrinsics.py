
import sys
import re
from pathlib import Path

import cv2
import numpy as np

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QListWidget, QTabWidget, QTextEdit,
    QMessageBox, QSplitter
)
from PySide6.QtGui import QPixmap, QImage, QFont
from PySide6.QtCore import Qt


# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(".")

LEFT_DIR = ROOT / "left"
RIGHT_DIR = ROOT / "right"

# 5 x 5 physical squares = 4 x 4 internal corners
CHECKERBOARD = (4, 4)

# 3.95 cm, converted to meters
SQUARE_SIZE = 0.0395

# Expected physical baseline, used only as a sanity check
EXPECTED_BASELINE = 0.10

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}


# ============================================================
# CHECKERBOARD DETECTION
# ============================================================

def detect_checkerboard(image):

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    found = False
    corners = None
    method = "None"

    # Try the more robust SB detector first
    if hasattr(cv2, "findChessboardCornersSB"):

        found, corners = cv2.findChessboardCornersSB(
            gray,
            CHECKERBOARD,
            flags=cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        if found:
            method = "SB"

    # Fallback to classic detector
    if not found:

        found, corners = cv2.findChessboardCorners(
            gray,
            CHECKERBOARD,
            flags=(
                cv2.CALIB_CB_ADAPTIVE_THRESH
                + cv2.CALIB_CB_NORMALIZE_IMAGE
            )
        )

        if found:

            criteria = (
                cv2.TERM_CRITERIA_EPS
                + cv2.TERM_CRITERIA_MAX_ITER,
                30,
                0.001
            )

            corners = cv2.cornerSubPix(
                gray,
                corners,
                (5, 5),
                (-1, -1),
                criteria
            )

            method = "Classic"

    display = image.copy()

    if found:

        cv2.drawChessboardCorners(
            display,
            CHECKERBOARD,
            corners,
            found
        )

        # Number the corners
        for i, corner in enumerate(corners):

            x, y = corner.ravel().astype(int)

            cv2.putText(
                display,
                str(i),
                (x + 5, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                1
            )

    return found, corners, display, method


# ============================================================
# FILE DISCOVERY
# ============================================================

def get_image_files(folder):

    files = {}

    if not folder.exists():
        return files

    for path in folder.iterdir():

        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        match = re.search(r"\d+", path.stem)

        if match:
            files[int(match.group())] = path

    return files


# ============================================================
# IMAGE DISPLAY
# ============================================================

def make_pixmap(image, label):

    if image is None:
        label.setText("No image")
        label.setPixmap(QPixmap())
        return

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    h, w, c = rgb.shape

    qimage = QImage(
        rgb.data,
        w,
        h,
        c * w,
        QImage.Format.Format_RGB888
    ).copy()

    pixmap = QPixmap.fromImage(qimage)

    label.setPixmap(
        pixmap.scaled(
            label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
    )


def make_image_panel(title):

    frame = QFrame()
    frame.setFrameShape(QFrame.Shape.StyledPanel)

    layout = QVBoxLayout(frame)

    heading = QLabel(title)
    heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
    heading.setFont(QFont("Arial", 12, QFont.Weight.Bold))

    status = QLabel("Waiting")
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)

    image = QLabel("No image")
    image.setAlignment(Qt.AlignmentFlag.AlignCenter)
    image.setMinimumSize(350, 260)
    image.setStyleSheet(
        "background-color: #222; color: white;"
    )

    layout.addWidget(heading)
    layout.addWidget(status)
    layout.addWidget(image, stretch=1)

    return {
        "widget": frame,
        "status": status,
        "image": image
    }


# ============================================================
# MAIN APPLICATION
# ============================================================

class StereoWorkbench(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Stereo Calibration Workbench")
        self.resize(1600, 1000)

        self.left_files = {}
        self.right_files = {}

        self.image_numbers = []
        self.index = 0

        # Pairs selected by the user
        self.kept_pairs = set()

        # Cached detections
        self.detections = {}

        # Calibration results
        self.calibration = None

        self.current_source_images = {}
        self.current_rectified_images = {}

        self.build_ui()
        self.reload_files()

    # ========================================================
    # UI
    # ========================================================

    def build_ui(self):

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        title = QLabel("Stereo Calibration Workbench")
        title.setFont(QFont("Arial", 19, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        description = QLabel(
            "5 x 5 squares | 4 x 4 internal corners | "
            "Square size: 0.0395 m | Baseline: 0.10 m"
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(title)
        main_layout.addWidget(description)

        self.tabs = QTabWidget()

        self.review_tab = QWidget()
        self.calibration_tab = QWidget()

        self.tabs.addTab(self.review_tab, "1. Review Images")
        self.tabs.addTab(self.calibration_tab, "2. Calibration Preview")

        main_layout.addWidget(self.tabs)

        self.build_review_tab()
        self.build_calibration_tab()

    # ========================================================
    # REVIEW TAB
    # ========================================================

    def build_review_tab(self):

        layout = QVBoxLayout(self.review_tab)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Image viewer
        viewer = QWidget()
        viewer_layout = QVBoxLayout(viewer)

        panels = QHBoxLayout()

        self.left_panel = make_image_panel("LEFT CAMERA")
        self.right_panel = make_image_panel("RIGHT CAMERA")

        panels.addWidget(self.left_panel["widget"])
        panels.addWidget(self.right_panel["widget"])

        viewer_layout.addLayout(panels, stretch=1)

        self.pair_info = QLabel("Image pair")
        self.pair_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        viewer_layout.addWidget(self.pair_info)

        # Navigation
        navigation = QHBoxLayout()

        self.previous_btn = QPushButton("< Previous")
        self.next_btn = QPushButton("Next >")

        self.previous_btn.clicked.connect(self.previous_image)
        self.next_btn.clicked.connect(self.next_image)

        navigation.addWidget(self.previous_btn)
        navigation.addWidget(self.next_btn)

        viewer_layout.addLayout(navigation)

        # Keep button
        self.keep_btn = QPushButton("Keep pair")
        self.keep_btn.setMinimumHeight(45)
        self.keep_btn.setStyleSheet(
            "background-color: #267a40; color: white; "
            "font-weight: bold; font-size: 15px;"
        )

        self.keep_btn.clicked.connect(self.keep_current_pair)

        viewer_layout.addWidget(self.keep_btn)

        # Selection panel
        selection = QWidget()
        selection_layout = QVBoxLayout(selection)

        selection_title = QLabel("Selected calibration pairs")
        selection_title.setFont(
            QFont("Arial", 13, QFont.Weight.Bold)
        )

        self.kept_counter = QLabel("0 pairs selected")

        self.kept_list = QListWidget()
        self.kept_list.currentRowChanged.connect(
            self.select_kept_pair
        )

        self.remove_btn = QPushButton("Remove selected pair")
        self.remove_btn.clicked.connect(self.remove_kept_pair)

        selection_layout.addWidget(selection_title)
        selection_layout.addWidget(self.kept_counter)
        selection_layout.addWidget(self.kept_list, stretch=1)
        selection_layout.addWidget(self.remove_btn)

        splitter.addWidget(viewer)
        splitter.addWidget(selection)

        splitter.setSizes([1100, 350])

        layout.addWidget(splitter, stretch=1)

        # Calibration button
        self.calibrate_btn = QPushButton(
            "CALIBRATE & RECTIFY SELECTED PAIRS"
        )

        self.calibrate_btn.setMinimumHeight(55)
        self.calibrate_btn.setStyleSheet(
            "background-color: #245b91; color: white; "
            "font-weight: bold; font-size: 16px;"
        )

        self.calibrate_btn.clicked.connect(self.calibrate)

        layout.addWidget(self.calibrate_btn)

    # ========================================================
    # CALIBRATION TAB
    # ========================================================

    def build_calibration_tab(self):

        layout = QVBoxLayout(self.calibration_tab)

        self.calibration_status = QLabel(
            "No calibration performed yet."
        )

        self.calibration_status.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.calibration_status.setFont(
            QFont("Arial", 13, QFont.Weight.Bold)
        )

        layout.addWidget(self.calibration_status)

        # Rectified image panels
        panels = QHBoxLayout()

        self.rect_left_panel = make_image_panel(
            "RECTIFIED LEFT CAMERA"
        )

        self.rect_right_panel = make_image_panel(
            "RECTIFIED RIGHT CAMERA"
        )

        panels.addWidget(self.rect_left_panel["widget"])
        panels.addWidget(self.rect_right_panel["widget"])

        layout.addLayout(panels, stretch=2)

        # Numerical calibration results
        result_title = QLabel("Calibration parameters")

        result_title.setFont(
            QFont("Arial", 13, QFont.Weight.Bold)
        )

        layout.addWidget(result_title)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setFont(
            QFont("Courier New", 10)
        )

        layout.addWidget(self.results_text, stretch=1)

        self.rectify_current_btn = QPushButton(
            "Rectify currently displayed pair"
        )

        self.rectify_current_btn.clicked.connect(
            self.rectify_current_pair
        )

        layout.addWidget(self.rectify_current_btn)

    # ========================================================
    # LOAD IMAGES
    # ========================================================

    def reload_files(self):

        self.left_files = get_image_files(LEFT_DIR)
        self.right_files = get_image_files(RIGHT_DIR)

        self.image_numbers = sorted(
            set(self.left_files) | set(self.right_files)
        )

        self.detections.clear()
        self.kept_pairs.clear()
        self.calibration = None

        self.kept_list.clear()

        self.update_kept_counter()

        if not self.image_numbers:

            QMessageBox.warning(
                self,
                "No images",
                "No numbered images found in left/ and right/."
            )

            return

        self.index = 0
        self.show_current()

    # ========================================================
    # DETECTION CACHE
    # ========================================================

    def get_pair_detection(self, number):

        if number in self.detections:
            return self.detections[number]

        result = {}

        for side, files in [
            ("left", self.left_files),
            ("right", self.right_files)
        ]:

            path = files.get(number)

            if path is None:

                result[side] = {
                    "found": False,
                    "corners": None,
                    "display": None,
                    "original": None,
                    "method": "Missing"
                }

                continue

            image = cv2.imread(str(path))

            if image is None:

                result[side] = {
                    "found": False,
                    "corners": None,
                    "display": None,
                    "original": None,
                    "method": "Read error"
                }

                continue

            found, corners, display, method = (
                detect_checkerboard(image)
            )

            result[side] = {
                "found": found,
                "corners": corners,
                "display": display,
                "original": image,
                "method": method
            }

        self.detections[number] = result

        return result

    # ========================================================
    # DISPLAY CURRENT PAIR
    # ========================================================

    def show_current(self):

        if not self.image_numbers:
            return

        number = self.image_numbers[self.index]

        result = self.get_pair_detection(number)

        self.pair_info.setText(
            f"Pair {number}  |  "
            f"{self.index + 1} of {len(self.image_numbers)}"
        )

        self.show_detection(
            self.left_panel,
            result["left"],
            "LEFT"
        )

        self.show_detection(
            self.right_panel,
            result["right"],
            "RIGHT"
        )

        valid = (
            result["left"]["found"]
            and result["right"]["found"]
        )

        self.keep_btn.setEnabled(
            valid and number not in self.kept_pairs
        )

        if number in self.kept_pairs:
            self.keep_btn.setText("Already kept")
        else:
            self.keep_btn.setText("Keep pair")

        self.previous_btn.setEnabled(self.index > 0)

        self.next_btn.setEnabled(
            self.index < len(self.image_numbers) - 1
        )

        # Update rectified preview if calibration exists
        if self.calibration is not None:
            self.rectify_current_pair()

    def show_detection(self, panel, data, side):

        if not data["found"]:

            panel["status"].setText(
                f"{side}: CHECKERBOARD NOT FOUND"
            )

            panel["status"].setStyleSheet("color: red;")

            panel["image"].setText("No valid detection")
            panel["image"].setPixmap(QPixmap())

            return

        count = CHECKERBOARD[0] * CHECKERBOARD[1]

        panel["status"].setText(
            f"FOUND {count} CORNERS | {data['method']}"
        )

        panel["status"].setStyleSheet(
            "color: green; font-weight: bold;"
        )

        make_pixmap(data["display"], panel["image"])

    # ========================================================
    # NAVIGATION
    # ========================================================

    def next_image(self):

        if self.index < len(self.image_numbers) - 1:

            self.index += 1
            self.show_current()

    def previous_image(self):

        if self.index > 0:

            self.index -= 1
            self.show_current()

    # ========================================================
    # KEEP / REMOVE PAIRS
    # ========================================================

    def keep_current_pair(self):

        number = self.image_numbers[self.index]

        result = self.get_pair_detection(number)

        if not (
            result["left"]["found"]
            and result["right"]["found"]
        ):

            return

        self.kept_pairs.add(number)

        item_text = f"Pair {number}  |  Both cameras OK"

        self.kept_list.addItem(item_text)

        self.update_kept_counter()

        self.keep_btn.setText("Already kept")
        self.keep_btn.setEnabled(False)

    def select_kept_pair(self, row):

        if row < 0:
            return

        number = sorted(self.kept_pairs)[row]

        if number in self.image_numbers:

            self.index = self.image_numbers.index(number)
            self.show_current()

    def remove_kept_pair(self):

        row = self.kept_list.currentRow()

        if row < 0:
            return

        number = sorted(self.kept_pairs)[row]

        self.kept_pairs.remove(number)

        self.kept_list.takeItem(row)

        self.update_kept_counter()
        self.show_current()

    def update_kept_counter(self):

        self.kept_counter.setText(
            f"{len(self.kept_pairs)} pairs selected"
        )

    # ========================================================
    # CALIBRATION
    # ========================================================

    def calibrate(self):

        selected = sorted(self.kept_pairs)

        if len(selected) < 3:

            QMessageBox.warning(
                self,
                "Not enough images",
                "Select at least 3 valid stereo pairs.\n"
                "For a reliable calibration, aim for 15-30 "
                "or more varied pairs."
            )

            return

        object_points = []
        image_points_left = []
        image_points_right = []

        image_size_left = None
        image_size_right = None

        # 3D checkerboard coordinates
        objp = np.zeros(
            (
                CHECKERBOARD[0] * CHECKERBOARD[1],
                3
            ),
            np.float32
        )

        objp[:, :2] = np.mgrid[
            0:CHECKERBOARD[0],
            0:CHECKERBOARD[1]
        ].T.reshape(-1, 2)

        objp *= SQUARE_SIZE

        for number in selected:

            data = self.get_pair_detection(number)

            left = data["left"]
            right = data["right"]

            if not (left["found"] and right["found"]):
                continue

            sizeL = (
                left["original"].shape[1],
                left["original"].shape[0]
            )

            sizeR = (
                right["original"].shape[1],
                right["original"].shape[0]
            )

            if image_size_left is None:
                image_size_left = sizeL
                image_size_right = sizeR

            if sizeL != image_size_left:
                QMessageBox.warning(
                    self,
                    "Resolution mismatch",
                    f"Left camera image sizes differ at pair {number}."
                )
                return

            if sizeR != image_size_right:
                QMessageBox.warning(
                    self,
                    "Resolution mismatch",
                    f"Right camera image sizes differ at pair {number}."
                )
                return

            if sizeL != sizeR:
                QMessageBox.warning(
                    self,
                    "Resolution mismatch",
                    "Left and right cameras must have the same "
                    "image dimensions for this calibration workflow."
                )
                return

            object_points.append(objp.copy())

            image_points_left.append(left["corners"])
            image_points_right.append(right["corners"])

        if len(object_points) < 3:
            return

        try:

            # --------------------------------------------
            # Individual camera intrinsics
            # --------------------------------------------

            rmsL, K1, D1, _, _ = cv2.calibrateCamera(
                object_points,
                image_points_left,
                image_size_left,
                None,
                None
            )

            rmsR, K2, D2, _, _ = cv2.calibrateCamera(
                object_points,
                image_points_right,
                image_size_right,
                None,
                None
            )

            # --------------------------------------------
            # Stereo calibration
            # --------------------------------------------

            criteria = (
                cv2.TERM_CRITERIA_EPS
                + cv2.TERM_CRITERIA_MAX_ITER,
                100,
                1e-6
            )

            rmsS, K1, D1, K2, D2, R, T, E, F = (
                cv2.stereoCalibrate(
                    object_points,
                    image_points_left,
                    image_points_right,
                    K1, D1,
                    K2, D2,
                    image_size_left,
                    criteria=criteria,
                    flags=cv2.CALIB_FIX_INTRINSIC
                )
            )

            # --------------------------------------------
            # Stereo rectification
            # --------------------------------------------

            R1, R2, P1, P2, Q, roi1, roi2 = (
                cv2.stereoRectify(
                    K1, D1,
                    K2, D2,
                    image_size_left,
                    R, T,
                    flags=cv2.CALIB_ZERO_DISPARITY,
                    alpha=0
                )
            )

            # Store everything in memory
            self.calibration = {
                "K1": K1,
                "D1": D1,
                "K2": K2,
                "D2": D2,
                "R": R,
                "T": T,
                "E": E,
                "F": F,
                "R1": R1,
                "R2": R2,
                "P1": P1,
                "P2": P2,
                "Q": Q,
                "roi1": roi1,
                "roi2": roi2,
                "image_size": image_size_left,
                "rmsL": rmsL,
                "rmsR": rmsR,
                "rmsS": rmsS
            }

            baseline = np.linalg.norm(T)

            self.show_calibration_results()

            self.rectify_current_pair()

            self.tabs.setCurrentWidget(self.calibration_tab)

            QMessageBox.information(
                self,
                "Calibration complete",
                f"Calibration completed using {len(object_points)} pairs.\n\n"
                f"Estimated baseline: {baseline:.5f} m\n"
                f"Expected baseline: {EXPECTED_BASELINE:.5f} m"
            )

        except cv2.error as error:

            QMessageBox.critical(
                self,
                "Calibration error",
                str(error)
            )

    # ========================================================
    # SHOW CALIBRATION PARAMETERS
    # ========================================================

    def show_calibration_results(self):

        c = self.calibration

        baseline = np.linalg.norm(c["T"])

        output = f"""
STEREO CALIBRATION RESULTS
==========================

Selected pairs: {len(self.kept_pairs)}

Image resolution: {c['image_size']}

Checkerboard:
  Internal corners: {CHECKERBOARD}
  Square size: {SQUARE_SIZE} meters

LEFT CAMERA
-----------

Camera matrix K1:
{c['K1']}

Distortion D1:
{c['D1']}

Calibration RMS:
{c['rmsL']:.6f}


RIGHT CAMERA
------------

Camera matrix K2:
{c['K2']}

Distortion D2:
{c['D2']}

Calibration RMS:
{c['rmsR']:.6f}


STEREO EXTRINSICS
-----------------

Rotation R:
{c['R']}

Translation T (meters):
{c['T']}

Estimated baseline:
{baseline:.6f} meters

Expected baseline:
{EXPECTED_BASELINE:.6f} meters

Difference:
{abs(baseline - EXPECTED_BASELINE):.6f} meters

Stereo RMS:
{c['rmsS']:.6f}


RECTIFICATION
-------------

R1:
{c['R1']}

R2:
{c['R2']}

P1:
{c['P1']}

P2:
{c['P2']}

Q:
{c['Q']}

ROI left: {c['roi1']}
ROI right: {c['roi2']}


IMPORTANT:
RMS values are reprojection errors in pixels.

The stereo baseline is estimated from calibration.
It is not forced to equal the mechanical baseline.
"""

        self.results_text.setPlainText(output)

        self.calibration_status.setText(
            f"Calibration complete | "
            f"Baseline: {baseline:.5f} m | "
            f"Stereo RMS: {c['rmsS']:.4f} px"
        )

    # ========================================================
    # RECTIFICATION PREVIEW
    # ========================================================

    def rectify_current_pair(self):

        if self.calibration is None:
            return

        if not self.image_numbers:
            return

        number = self.image_numbers[self.index]

        data = self.get_pair_detection(number)

        left = data["left"]["original"]
        right = data["right"]["original"]

        if left is None or right is None:
            return

        c = self.calibration

        # Generate rectification maps
        mapL1, mapL2 = cv2.initUndistortRectifyMap(
            c["K1"],
            c["D1"],
            c["R1"],
            c["P1"],
            c["image_size"],
            cv2.CV_32FC1
        )

        mapR1, mapR2 = cv2.initUndistortRectifyMap(
            c["K2"],
            c["D2"],
            c["R2"],
            c["P2"],
            c["image_size"],
            cv2.CV_32FC1
        )

        rectL = cv2.remap(
            left,
            mapL1,
            mapL2,
            cv2.INTER_LINEAR
        )

        rectR = cv2.remap(
            right,
            mapR1,
            mapR2,
            cv2.INTER_LINEAR
        )

        self.current_rectified_images = {
            "left": rectL,
            "right": rectR
        }

        make_pixmap(
            rectL,
            self.rect_left_panel["image"]
        )

        make_pixmap(
            rectR,
            self.rect_right_panel["image"]
        )

        self.rect_left_panel["status"].setText(
            f"Rectified pair {number}"
        )

        self.rect_right_panel["status"].setText(
            f"Rectified pair {number}"
        )

    # ========================================================
    # RESIZE
    # ========================================================

    def resizeEvent(self, event):

        super().resizeEvent(event)

        if self.image_numbers:
            self.show_current()

    # ========================================================
    # KEYBOARD
    # ========================================================

    def keyPressEvent(self, event):

        key = event.key()

        if key == Qt.Key.Key_Right:
            self.next_image()

        elif key == Qt.Key.Key_Left:
            self.previous_image()

        elif key == Qt.Key.Key_Space:
            self.keep_current_pair()

        else:
            super().keyPressEvent(event)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = StereoWorkbench()
    window.show()

    sys.exit(app.exec())

