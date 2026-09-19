import sys
import math
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
    QGroupBox,
    QGridLayout,
)

import pyqtgraph as pg


class ImageViewer(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "KITTI Stereo Image + Pose Viewer"
        )

        self.resize(1700, 1000)

        self.left_files = []
        self.right_files = []

        # Each pose is:
        #
        # [r11, r12, r13, tx,
        #  r21, r22, r23, ty,
        #  r31, r32, r33, tz]
        #
        self.poses = []

        self.current_index = 0

        self.setup_ui()

    # =========================================================
    # UI
    # =========================================================

    def setup_ui(self):

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        # -----------------------------------------------------
        # Top
        # -----------------------------------------------------

        top_layout = QHBoxLayout()

        self.open_button = QPushButton(
            "Open Sequence Folder"
        )

        self.open_button.clicked.connect(
            self.open_folder
        )

        top_layout.addWidget(
            self.open_button
        )

        self.path_label = QLabel(
            "No folder selected"
        )

        top_layout.addWidget(
            self.path_label,
            1
        )

        main_layout.addLayout(
            top_layout
        )

        # -----------------------------------------------------
        # Images
        # -----------------------------------------------------

        images_layout = QHBoxLayout()

        self.left_label = QLabel(
            "Left Image"
        )

        self.right_label = QLabel(
            "Right Image"
        )

        for label in (
            self.left_label,
            self.right_label
        ):

            label.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            label.setMinimumSize(
                450,
                400
            )

            label.setStyleSheet("""
                QLabel {
                    background-color: #202020;
                    color: white;
                    border: 1px solid #555555;
                }
            """)

        images_layout.addWidget(
            self.left_label,
            1
        )

        images_layout.addWidget(
            self.right_label,
            1
        )

        main_layout.addLayout(
            images_layout,
            1
        )

        # -----------------------------------------------------
        # Image names
        # -----------------------------------------------------

        filename_layout = QHBoxLayout()

        self.left_filename = QLabel("")
        self.right_filename = QLabel("")

        self.left_filename.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.right_filename.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        filename_layout.addWidget(
            self.left_filename
        )

        filename_layout.addWidget(
            self.right_filename
        )

        main_layout.addLayout(
            filename_layout
        )

        # -----------------------------------------------------
        # Bottom information area
        #
        # Left:
        #   position + rotation
        #
        # Right:
        #   XY trajectory
        # -----------------------------------------------------

        bottom_layout = QHBoxLayout()

        # =====================================================
        # Pose information
        # =====================================================

        pose_widget = QWidget()

        pose_layout = QVBoxLayout(
            pose_widget
        )

        # -----------------------------------------------------
        # Position
        # -----------------------------------------------------

        position_box = QGroupBox(
            "Position / Translation"
        )

        position_grid = QGridLayout()

        self.x_label = QLabel(
            "X: -"
        )

        self.y_label = QLabel(
            "Y: -"
        )

        self.z_label = QLabel(
            "Z: -"
        )

        position_grid.addWidget(
            self.x_label,
            0,
            0
        )

        position_grid.addWidget(
            self.y_label,
            1,
            0
        )

        position_grid.addWidget(
            self.z_label,
            2,
            0
        )

        position_box.setLayout(
            position_grid
        )

        pose_layout.addWidget(
            position_box
        )

        # -----------------------------------------------------
        # Rotation
        # -----------------------------------------------------

        rotation_box = QGroupBox(
            "Rotation"
        )

        rotation_grid = QGridLayout()

        self.roll_label = QLabel(
            "Roll: -"
        )

        self.pitch_label = QLabel(
            "Pitch: -"
        )

        self.yaw_label = QLabel(
            "Yaw: -"
        )

        rotation_grid.addWidget(
            self.roll_label,
            0,
            0
        )

        rotation_grid.addWidget(
            self.pitch_label,
            1,
            0
        )

        rotation_grid.addWidget(
            self.yaw_label,
            2,
            0
        )

        rotation_box.setLayout(
            rotation_grid
        )

        pose_layout.addWidget(
            rotation_box
        )

        # -----------------------------------------------------
        # Rotation matrix
        # -----------------------------------------------------

        matrix_box = QGroupBox(
            "Rotation Matrix"
        )

        matrix_layout = QVBoxLayout()

        self.rotation_matrix_label = QLabel(
            "-"
        )

        self.rotation_matrix_label.setStyleSheet(
            "font-family: monospace;"
        )

        matrix_layout.addWidget(
            self.rotation_matrix_label
        )

        matrix_box.setLayout(
            matrix_layout
        )

        pose_layout.addWidget(
            matrix_box
        )

        # -----------------------------------------------------
        # Transformation matrix
        # -----------------------------------------------------

        transform_box = QGroupBox(
            "Transformation Matrix"
        )

        transform_layout = QVBoxLayout()

        self.transform_label = QLabel(
            "-"
        )

        self.transform_label.setStyleSheet(
            "font-family: monospace;"
        )

        transform_layout.addWidget(
            self.transform_label
        )

        transform_box.setLayout(
            transform_layout
        )

        pose_layout.addWidget(
            transform_box
        )

        # =====================================================
        # Trajectory graph
        # =====================================================

        graph_box = QGroupBox(
            "XY Trajectory"
        )

        graph_layout = QVBoxLayout(
            graph_box
        )

        self.graph = pg.PlotWidget()

        self.graph.setBackground(
            "#202020"
        )

        self.graph.showGrid(
            x=True,
            y=True,
            alpha=0.3
        )

        self.graph.setLabel(
            "left",
            "Y",
            units="m"
        )

        self.graph.setLabel(
            "bottom",
            "X",
            units="m"
        )

        self.graph.setTitle(
            "Trajectory up to current frame"
        )

        # Keep X/Y at the same visual scale.
        self.graph.getViewBox().setAspectLocked(
            True
        )

        # Trajectory line.
        self.trajectory_curve = self.graph.plot(
            [],
            [],
            pen=pg.mkPen(
                "#4dabf7",
                width=2
            )
        )

        # Current position marker.
        self.current_position = self.graph.plot(
            [],
            [],
            pen=None,
            symbol="o",
            symbolSize=10,
            symbolBrush="#ff5555",
            symbolPen=None
        )

        graph_layout.addWidget(
            self.graph
        )

        # -----------------------------------------------------
        # Add pose + graph to bottom
        # -----------------------------------------------------

        bottom_layout.addWidget(
            pose_widget,
            1
        )

        bottom_layout.addWidget(
            graph_box,
            1
        )

        main_layout.addLayout(
            bottom_layout,
            1
        )

        # -----------------------------------------------------
        # Slider
        # -----------------------------------------------------

        self.slider = QSlider(
            Qt.Orientation.Horizontal
        )

        self.slider.setEnabled(
            False
        )

        self.slider.valueChanged.connect(
            self.slider_changed
        )

        main_layout.addWidget(
            self.slider
        )

        # -----------------------------------------------------
        # Frame
        # -----------------------------------------------------

        self.frame_label = QLabel(
            "Frame: -"
        )

        self.frame_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.frame_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
            }
        """)

        main_layout.addWidget(
            self.frame_label
        )

        # -----------------------------------------------------
        # Navigation
        # -----------------------------------------------------

        button_layout = QHBoxLayout()

        self.prev_button = QPushButton(
            "Previous"
        )

        self.next_button = QPushButton(
            "Next"
        )

        self.prev_button.clicked.connect(
            self.previous_frame
        )

        self.next_button.clicked.connect(
            self.next_frame
        )

        self.prev_button.setEnabled(
            False
        )

        self.next_button.setEnabled(
            False
        )

        button_layout.addWidget(
            self.prev_button
        )

        button_layout.addWidget(
            self.next_button
        )

        main_layout.addLayout(
            button_layout
        )

    # =========================================================
    # Open folder
    # =========================================================

    def open_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select KITTI sequence folder"
        )

        if not folder:
            return

        sequence_folder = Path(
            folder
        )

        image0 = sequence_folder / "image_0"
        image1 = sequence_folder / "image_1"

        # Look for:
        #
        # sequences/00/00.txt
        #
        pose_file = (
            sequence_folder
            / (sequence_folder.name + ".txt")
        )

        # Also support standard KITTI:
        #
        # dataset/
        #   sequences/
        #       00/
        #
        #   poses/
        #       00.txt
        #

        if not pose_file.exists():

            possible_pose = (
                sequence_folder.parent.parent
                / "poses"
                / (sequence_folder.name + ".txt")
            )

            if possible_pose.exists():
                pose_file = possible_pose

        if not image0.exists():

            self.path_label.setText(
                "ERROR: image_0 does not exist"
            )

            return

        if not image1.exists():

            self.path_label.setText(
                "ERROR: image_1 does not exist"
            )

            return

        self.load_images(
            sequence_folder,
            image0,
            image1,
            pose_file
        )

    # =========================================================
    # Load images + poses
    # =========================================================

    def load_images(
        self,
        sequence_folder,
        left_folder,
        right_folder,
        pose_file
    ):

        left_folder = Path(
            left_folder
        )

        right_folder = Path(
            right_folder
        )

        # -----------------------------------------------------
        # Images
        # -----------------------------------------------------

        extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp",
            ".webp"
        }

        left_files = [
            Path(x)
            for x in left_folder.iterdir()
            if Path(x).is_file()
            and Path(x).suffix.lower()
            in extensions
        ]

        right_files = [
            Path(x)
            for x in right_folder.iterdir()
            if Path(x).is_file()
            and Path(x).suffix.lower()
            in extensions
        ]

        left_dict = {
            x.name: x
            for x in left_files
        }

        right_dict = {
            x.name: x
            for x in right_files
        }

        common_names = (
            set(left_dict.keys())
            &
            set(right_dict.keys())
        )

        def numeric_filename(filename):

            try:
                return int(
                    Path(filename).stem
                )

            except ValueError:

                return str(filename)

        common_names = sorted(
            common_names,
            key=numeric_filename
        )

        self.left_files = [
            left_dict[name]
            for name in common_names
        ]

        self.right_files = [
            right_dict[name]
            for name in common_names
        ]

        if not self.left_files:

            self.path_label.setText(
                "No matching image pairs found."
            )

            return

        # -----------------------------------------------------
        # Poses
        # -----------------------------------------------------

        self.poses = []

        if pose_file.exists():

            try:

                with open(
                    pose_file,
                    "r"
                ) as f:

                    for line in f:

                        line = line.strip()

                        if not line:
                            continue

                        values = [
                            float(x)
                            for x in line.split()
                        ]

                        # Standard KITTI:
                        #
                        # 12 values
                        #
                        if len(values) == 12:

                            self.poses.append(
                                values
                            )

                        # Support:
                        #
                        # frame_number + 12 values
                        #
                        elif len(values) == 13:

                            self.poses.append(
                                values[1:]
                            )

            except Exception as e:

                print(
                    "Could not load pose file:",
                    e
                )

        else:

            print(
                "Pose file not found:",
                pose_file
            )

        # -----------------------------------------------------
        # Setup slider
        # -----------------------------------------------------

        self.current_index = 0

        self.slider.setEnabled(
            True
        )

        self.slider.setMinimum(
            0
        )

        self.slider.setMaximum(
            len(self.left_files) - 1
        )

        self.prev_button.setEnabled(
            True
        )

        self.next_button.setEnabled(
            True
        )

        pose_status = ""

        if self.poses:

            pose_status = (
                f" | Poses: {len(self.poses)}"
            )

        else:

            pose_status = (
                " | Poses: not found"
            )

        self.path_label.setText(
            str(sequence_folder)
            + pose_status
        )

        self.show_frame(
            0
        )

    # =========================================================
    # Show frame
    # =========================================================

    def show_frame(self, index):

        if not self.left_files:
            return

        index = max(
            0,
            min(
                index,
                len(self.left_files) - 1
            )
        )

        self.current_index = index

        left_path = Path(
            self.left_files[index]
        )

        right_path = Path(
            self.right_files[index]
        )

        # -----------------------------------------------------
        # Left image
        # -----------------------------------------------------

        left_pixmap = QPixmap(
            str(left_path)
        )

        if not left_pixmap.isNull():

            self.left_label.setPixmap(
                left_pixmap.scaled(
                    self.left_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )

        else:

            self.left_label.setText(
                "Could not load:\n"
                + str(left_path)
            )

        # -----------------------------------------------------
        # Right image
        # -----------------------------------------------------

        right_pixmap = QPixmap(
            str(right_path)
        )

        if not right_pixmap.isNull():

            self.right_label.setPixmap(
                right_pixmap.scaled(
                    self.right_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )

        else:

            self.right_label.setText(
                "Could not load:\n"
                + str(right_path)
            )

        # -----------------------------------------------------
        # Filename
        # -----------------------------------------------------

        self.left_filename.setText(
            "Left: " + left_path.name
        )

        self.right_filename.setText(
            "Right: " + right_path.name
        )

        self.frame_label.setText(
            f"Frame {index + 1} / "
            f"{len(self.left_files)}    "
            f"{left_path.name}"
        )

        # -----------------------------------------------------
        # Pose
        # -----------------------------------------------------

        self.show_pose(
            index
        )

        # -----------------------------------------------------
        # Trajectory
        # -----------------------------------------------------

        self.update_trajectory(
            index
        )

        # -----------------------------------------------------
        # Slider
        # -----------------------------------------------------

        self.slider.blockSignals(
            True
        )

        self.slider.setValue(
            index
        )

        self.slider.blockSignals(
            False
        )

    # =========================================================
    # Pose
    # =========================================================

    def show_pose(self, index):

        if index >= len(self.poses):

            self.x_label.setText(
                "X: unavailable"
            )

            self.y_label.setText(
                "Y: unavailable"
            )

            self.z_label.setText(
                "Z: unavailable"
            )

            self.roll_label.setText(
                "Roll: unavailable"
            )

            self.pitch_label.setText(
                "Pitch: unavailable"
            )

            self.yaw_label.setText(
                "Yaw: unavailable"
            )

            self.rotation_matrix_label.setText(
                "No pose available"
            )

            self.transform_label.setText(
                "No transformation available"
            )

            return

        p = self.poses[index]

        # -----------------------------------------------------
        # KITTI 3x4 matrix
        #
        # r11 r12 r13 tx
        # r21 r22 r23 ty
        # r31 r32 r33 tz
        # -----------------------------------------------------

        r11, r12, r13, tx = p[0:4]
        r21, r22, r23, ty = p[4:8]
        r31, r32, r33, tz = p[8:12]

        # -----------------------------------------------------
        # Position
        # -----------------------------------------------------

        self.x_label.setText(
            f"X: {tx:.6f} m"
        )

        self.y_label.setText(
            f"Y: {ty:.6f} m"
        )

        self.z_label.setText(
            f"Z: {tz:.6f} m"
        )

        # -----------------------------------------------------
        # Rotation matrix
        # -----------------------------------------------------

        self.rotation_matrix_label.setText(
            f"""
[
 {r11: .6f}  {r12: .6f}  {r13: .6f}
 {r21: .6f}  {r22: .6f}  {r23: .6f}
 {r31: .6f}  {r32: .6f}  {r33: .6f}
]
""".strip()
        )

        # -----------------------------------------------------
        # Euler angles
        # -----------------------------------------------------

        r31_clamped = max(
            -1.0,
            min(
                1.0,
                r31
            )
        )

        pitch = math.asin(
            -r31_clamped
        )

        roll = math.atan2(
            r32,
            r33
        )

        yaw = math.atan2(
            r21,
            r11
        )

        roll_deg = math.degrees(
            roll
        )

        pitch_deg = math.degrees(
            pitch
        )

        yaw_deg = math.degrees(
            yaw
        )

        self.roll_label.setText(
            f"Roll:  {roll_deg:.4f}°"
        )

        self.pitch_label.setText(
            f"Pitch: {pitch_deg:.4f}°"
        )

        self.yaw_label.setText(
            f"Yaw:   {yaw_deg:.4f}°"
        )

        # -----------------------------------------------------
        # Full transformation matrix
        # -----------------------------------------------------

        self.transform_label.setText(
            f"[ {r11: .6f}  {r12: .6f}  "
            f"{r13: .6f}  {tx: .6f} ]\n"
            f"[ {r21: .6f}  {r22: .6f}  "
            f"{r23: .6f}  {ty: .6f} ]\n"
            f"[ {r31: .6f}  {r32: .6f}  "
            f"{r33: .6f}  {tz: .6f} ]\n"
            f"[  0.000000   0.000000   "
            f"0.000000   1.000000 ]"
        )

    # =========================================================
    # Update trajectory
    # =========================================================

    def update_trajectory(self, current_index):
        if not self.poses:
            self.trajectory_curve.setData([], [])
            self.current_position.setData([], [])
            return

        poses = self.poses[:current_index + 1]

        # KITTI: X = left/right, Y = up/down, Z = forward/back
        xs = [pose[3] for pose in poses]
        zs = [pose[11] for pose in poses]

        # Draw trajectory from frame 0 to current frame
        self.trajectory_curve.setData(xs, zs)

        # Current vehicle position
        if xs and zs:
            self.current_position.setData([xs[-1]], [zs[-1]])

        self.graph.setLabel("bottom", "X", units="m")
        self.graph.setLabel("left", "Z", units="m")
        self.graph.setTitle("XZ Trajectory")
        self.graph.enableAutoRange()

    # =========================================================
    # Slider
    # =========================================================

    def slider_changed(self, value):

        self.show_frame(
            value
        )

    # =========================================================
    # Previous
    # =========================================================

    def previous_frame(self):

        if not self.left_files:
            return

        self.show_frame(
            self.current_index - 1
        )

    # =========================================================
    # Next
    # =========================================================

    def next_frame(self):

        if not self.left_files:
            return

        self.show_frame(
            self.current_index + 1
        )

    # =========================================================
    # Resize
    # =========================================================

    def resizeEvent(self, event):

        super().resizeEvent(
            event
        )

        if self.left_files:

            self.show_frame(
                self.current_index
            )

    # =========================================================
    # Keyboard
    # =========================================================

    def keyPressEvent(self, event):

        if event.key() == Qt.Key.Key_Left:

            self.previous_frame()

        elif event.key() == Qt.Key.Key_Right:

            self.next_frame()

        elif event.key() == Qt.Key.Key_Home:

            if self.left_files:
                self.show_frame(0)

        elif event.key() == Qt.Key.Key_End:

            if self.left_files:

                self.show_frame(
                    len(self.left_files) - 1
                )

        else:

            super().keyPressEvent(
                event
            )


# =============================================================
# MAIN
# =============================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    window = ImageViewer()

    window.show()

    sys.exit(
        app.exec()
    )

