import sys
import os
import json
import struct
from pathlib import Path

import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QFont
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QScrollArea,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QSizePolicy,
    QFrame,
)


# =========================================================
# Stereo Recording
# =========================================================

class StereoRecording:

    def __init__(self, filename):

        self.filename = filename

        self.file = open(
            filename,
            "rb",
            buffering=1024 * 1024,
        )

        # -------------------------------------------------
        # Read header length
        # -------------------------------------------------

        header_length_data = self.file.read(8)

        if len(header_length_data) != 8:
            raise RuntimeError(
                "Invalid recording file"
            )

        header_length = struct.unpack(
            "<Q",
            header_length_data,
        )[0]

        # -------------------------------------------------
        # Read JSON header
        # -------------------------------------------------

        header_data = self.file.read(
            header_length
        )

        if len(header_data) != header_length:
            raise RuntimeError(
                "Incomplete recording header"
            )

        self.header = json.loads(
            header_data.decode("utf-8")
        )

        if self.header.get("format") != "stereo_raw_v1":

            raise RuntimeError(
                "Unsupported recording format: "
                f"{self.header.get('format')}"
            )

        # -------------------------------------------------
        # Camera information
        # -------------------------------------------------

        self.shape = tuple(
            self.header["shape"]
        )

        self.dtype = np.dtype(
            self.header["dtype"]
        )

        self.frame_bytes = int(
            self.header["frame_bytes"]
        )

        if len(self.shape) != 2:

            raise RuntimeError(
                f"Expected 2D image, "
                f"got {self.shape}"
            )

        # Stored dimensions
        self.stored_height = self.shape[0]
        self.stored_width = self.shape[1]

        # -------------------------------------------------
        # IMPORTANT:
        #
        # The stored image is uint8.
        #
        # Every real column is followed by a padding
        # column.
        #
        # Example:
        #
        #  P0  0  P1  0  P2  0  P3  0
        #
        # Therefore the actual image width is half
        # the stored width.
        # -------------------------------------------------

        if self.stored_width % 2 != 0:

            raise RuntimeError(
                "Stored image width must be even"
            )

        self.height = self.stored_height
        self.width = self.stored_width // 2

        self.display_shape = (
            self.height,
            self.width,
        )

        # -------------------------------------------------
        # Validate dtype
        # -------------------------------------------------

        if self.dtype != np.uint8:

            raise RuntimeError(
                "This viewer expects the stored image "
                f"to be uint8, got {self.dtype}"
            )

        # -------------------------------------------------
        # Record layout
        #
        # uint64 trigger timestamp    8 bytes
        # uint64 left timestamp       8 bytes
        # uint64 right timestamp      8 bytes
        #
        # left image                 frame_bytes
        # right image                frame_bytes
        # -------------------------------------------------

        self.record_size = (
            24 +
            self.frame_bytes * 2
        )

        # First frame starts after:
        #
        # 8 bytes header length
        # JSON header
        #

        self.data_offset = (
            8 +
            header_length
        )

        # -------------------------------------------------
        # Determine number of frames
        # -------------------------------------------------

        self.file.seek(
            0,
            os.SEEK_END,
        )

        file_size = self.file.tell()

        data_size = (
            file_size -
            self.data_offset
        )

        if data_size < 0:

            raise RuntimeError(
                "Invalid recording file"
            )

        if data_size % self.record_size != 0:

            print(
                "WARNING: recording file has "
                "an incomplete record",
                flush=True,
            )

        self.frame_count = (
            data_size //
            self.record_size
        )

        # -------------------------------------------------
        # Print information
        # -------------------------------------------------

        print(
            f"Recording: {filename}"
        )

        print(
            f"Frames: {self.frame_count}"
        )

        print(
            f"Stored shape: {self.shape}"
        )

        print(
            f"Display shape: {self.display_shape}"
        )

        print(
            f"Dtype: {self.dtype}"
        )

        print(
            f"Frame bytes: {self.frame_bytes}"
        )

        print(
            f"Record size: {self.record_size}"
        )

    # =====================================================
    # Frame offset
    # =====================================================

    def frame_offset(self, index):

        if index < 0 or index >= self.frame_count:

            raise IndexError(
                f"Frame index out of range: {index}"
            )

        return (
            self.data_offset +
            index * self.record_size
        )

    # =====================================================
    # Read timestamps
    # =====================================================

    def read_timestamps(self, index):

        offset = self.frame_offset(
            index
        )

        self.file.seek(
            offset
        )

        data = self.file.read(
            24
        )

        if len(data) != 24:

            raise RuntimeError(
                f"Could not read timestamps "
                f"for frame {index}"
            )

        return struct.unpack(
            "<QQQ",
            data,
        )

    # =====================================================
    # Read raw image
    # =====================================================

    def read_raw_frame(
        self,
        index,
        left=True,
    ):

        offset = self.frame_offset(
            index
        )

        # Skip the three timestamps.

        image_offset = (
            offset +
            24
        )

        # Right image comes after left image.

        if not left:

            image_offset += (
                self.frame_bytes
            )

        self.file.seek(
            image_offset
        )

        raw = self.file.read(
            self.frame_bytes
        )

        if len(raw) != self.frame_bytes:

            raise RuntimeError(
                f"Could not read complete "
                f"{'left' if left else 'right'} "
                f"image for frame {index}"
            )

        array = np.frombuffer(
            raw,
            dtype=self.dtype,
        )

        expected_elements = (
            self.stored_height *
            self.stored_width
        )

        if array.size != expected_elements:

            raise RuntimeError(
                "Image size does not match header\n"
                f"Expected elements: "
                f"{expected_elements}\n"
                f"Actual elements: "
                f"{array.size}\n"
                f"Shape: {self.shape}\n"
                f"Dtype: {self.dtype}"
            )

        return array.reshape(
            self.shape
        )

    # =====================================================
    # Decode image
    # =====================================================

    @staticmethod
    def decode_image(image):
        """
        Remove the padded columns.

        Stored:

            P0  0  P1  0  P2  0  P3  0

        Display:

            P0  P1  P2  P3

        Therefore:

            image[:, ::2]
        """

        if image.ndim != 2:

            raise RuntimeError(
                f"Expected 2D image, "
                f"got {image.shape}"
            )

        if image.dtype != np.uint8:

            raise RuntimeError(
                f"Expected uint8 image, "
                f"got {image.dtype}"
            )

        if image.shape[1] % 2 != 0:

            raise RuntimeError(
                "Image width must be even"
            )

        # -------------------------------------------------
        # THIS IS THE IMPORTANT PART
        # -------------------------------------------------
        #
        # Keep columns:
        #
        # 0, 2, 4, 6, ...
        #
        # Discard:
        #
        # 1, 3, 5, 7, ...
        #

        decoded = image[:, 1::2]

        return np.ascontiguousarray(
            decoded
        )

    # =====================================================
    # Read complete frame
    # =====================================================

    def read_frame(self, index):

        # -------------------------------------------------
        # Timestamps
        # -------------------------------------------------

        (
            trigger_timestamp,
            left_timestamp,
            right_timestamp,
        ) = self.read_timestamps(
            index
        )

        # -------------------------------------------------
        # Raw images
        # -------------------------------------------------

        left_raw = self.read_raw_frame(
            index,
            left=True,
        )

        right_raw = self.read_raw_frame(
            index,
            left=False,
        )

        # -------------------------------------------------
        # Remove padding columns
        # -------------------------------------------------

        left = self.decode_image(
            left_raw
        )

        right = self.decode_image(
            right_raw
        )

        return (
            left,
            right,
            trigger_timestamp,
            left_timestamp,
            right_timestamp,
        )

    # =====================================================
    # Close
    # =====================================================

    def close(self):

        if self.file is not None:

            self.file.close()

            self.file = None

    def __del__(self):

        try:
            self.close()
        except Exception:
            pass


# =========================================================
# NumPy image -> QPixmap
# =========================================================

def numpy_to_pixmap(image):

    if image.dtype != np.uint8:

        image = image.astype(
            np.uint8
        )

    image = np.ascontiguousarray(
        image
    )

    height, width = image.shape

    qimage = QImage(
        image.data,
        width,
        height,
        width,
        QImage.Format_Grayscale8,
    )

    # Make an independent copy so Qt does not depend
    # on the NumPy array's memory.

    qimage = qimage.copy()

    return QPixmap.fromImage(
        qimage
    )


# =========================================================
# Image display widget
# =========================================================

class ImageDisplay(QLabel):

    def __init__(
        self,
        title="",
    ):

        super().__init__()

        self.title = title
        self.original_pixmap = None

        self.setAlignment(
            Qt.AlignCenter
        )

        self.setMinimumSize(
            200,
            200,
        )

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        self.setStyleSheet(
            """
            QLabel {
                background-color: #111111;
                color: #888888;
                border: 1px solid #333333;
            }
            """
        )

        self.setText(
            title
        )

    # -----------------------------------------------------
    # Set image
    # -----------------------------------------------------

    def set_image(
        self,
        pixmap,
    ):

        self.original_pixmap = pixmap

        self.update_scaled_pixmap()

    # -----------------------------------------------------
    # Resize
    # -----------------------------------------------------

    def resizeEvent(
        self,
        event,
    ):

        super().resizeEvent(
            event
        )

        self.update_scaled_pixmap()

    # -----------------------------------------------------
    # Scale image
    # -----------------------------------------------------

    def update_scaled_pixmap(self):

        if self.original_pixmap is None:
            return

        if self.width() <= 0:
            return

        if self.height() <= 0:
            return

        scaled = self.original_pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        self.setPixmap(
            scaled
        )


# =========================================================
# Main Viewer
# =========================================================

class StereoViewer(QMainWindow):

    def __init__(
        self,
        filename=None,
    ):

        super().__init__()

        self.recording = None
        self.current_frame = -1

        self.setWindowTitle(
            "Stereo Recording Viewer"
        )

        self.resize(
            1400,
            850,
        )

        self.setup_ui()

        if filename:

            self.open_recording(
                filename
            )

    # =====================================================
    # Setup UI
    # =====================================================

    def setup_ui(self):

        central = QWidget()

        self.setCentralWidget(
            central
        )

        main_layout = QVBoxLayout(
            central
        )

        main_layout.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        main_layout.setSpacing(
            6
        )

        # =================================================
        # Top toolbar
        # =================================================

        toolbar = QHBoxLayout()

        # -------------------------------------------------
        # Open
        # -------------------------------------------------

        self.open_button = QPushButton(
            "Open Recording"
        )

        self.open_button.clicked.connect(
            self.choose_recording
        )

        toolbar.addWidget(
            self.open_button
        )

        # -------------------------------------------------
        # Previous
        # -------------------------------------------------

        self.previous_button = QPushButton(
            "◀ Previous"
        )

        self.previous_button.clicked.connect(
            self.previous_frame
        )

        self.previous_button.setEnabled(
            False
        )

        toolbar.addWidget(
            self.previous_button
        )

        # -------------------------------------------------
        # Next
        # -------------------------------------------------

        self.next_button = QPushButton(
            "Next ▶"
        )

        self.next_button.clicked.connect(
            self.next_frame
        )

        self.next_button.setEnabled(
            False
        )

        toolbar.addWidget(
            self.next_button
        )

        # -------------------------------------------------
        # Current frame
        # -------------------------------------------------

        self.frame_label = QLabel(
            "No recording loaded"
        )

        self.frame_label.setAlignment(
            Qt.AlignCenter
        )

        toolbar.addWidget(
            self.frame_label,
            1,
        )

        main_layout.addLayout(
            toolbar
        )

        # =================================================
        # Main splitter
        # =================================================

        splitter = QSplitter(
            Qt.Horizontal
        )

        main_layout.addWidget(
            splitter,
            1,
        )

        # =================================================
        # LEFT PANEL
        # =================================================

        left_panel = QWidget()

        left_layout = QVBoxLayout(
            left_panel
        )

        left_layout.setContentsMargins(
            4,
            4,
            4,
            4,
        )

        # -------------------------------------------------
        # Title
        # -------------------------------------------------

        title = QLabel(
            "Frames"
        )

        font = QFont()

        font.setBold(
            True
        )

        font.setPointSize(
            12
        )

        title.setFont(
            font
        )

        left_layout.addWidget(
            title
        )

        # -------------------------------------------------
        # Scroll area
        # -------------------------------------------------

        self.frame_scroll = QScrollArea()

        self.frame_scroll.setWidgetResizable(
            True
        )

        self.frame_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.frame_container = QWidget()

        self.frame_button_layout = QVBoxLayout(
            self.frame_container
        )

        self.frame_button_layout.setContentsMargins(
            4,
            4,
            4,
            4,
        )

        self.frame_button_layout.setSpacing(
            3
        )

        self.frame_scroll.setWidget(
            self.frame_container
        )

        left_layout.addWidget(
            self.frame_scroll
        )

        left_panel.setMinimumWidth(
            180
        )

        left_panel.setMaximumWidth(
            350
        )

        splitter.addWidget(
            left_panel
        )

        # =================================================
        # RIGHT PANEL
        # =================================================

        right_panel = QWidget()

        right_layout = QVBoxLayout(
            right_panel
        )

        right_layout.setContentsMargins(
            4,
            4,
            4,
            4,
        )

        # =================================================
        # Timestamp panel
        # =================================================

        info_frame = QFrame()

        info_frame.setFrameShape(
            QFrame.StyledPanel
        )

        info_layout = QVBoxLayout(
            info_frame
        )

        self.timestamp_label = QLabel(
            "No frame selected"
        )

        self.timestamp_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        self.timestamp_label.setStyleSheet(
            """
            QLabel {
                padding: 8px;
                font-family: monospace;
            }
            """
        )

        info_layout.addWidget(
            self.timestamp_label
        )

        right_layout.addWidget(
            info_frame
        )

        # =================================================
        # Stereo image splitter
        # =================================================

        image_splitter = QSplitter(
            Qt.Horizontal
        )

        self.left_image = ImageDisplay(
            "Left Camera"
        )

        self.right_image = ImageDisplay(
            "Right Camera"
        )

        image_splitter.addWidget(
            self.left_image
        )

        image_splitter.addWidget(
            self.right_image
        )

        image_splitter.setStretchFactor(
            0,
            1
        )

        image_splitter.setStretchFactor(
            1,
            1
        )

        right_layout.addWidget(
            image_splitter,
            1
        )

        splitter.addWidget(
            right_panel
        )

        splitter.setStretchFactor(
            0,
            0
        )

        splitter.setStretchFactor(
            1,
            1
        )

        splitter.setSizes(
            [
                220,
                1100,
            ]
        )

        # =================================================
        # Status bar
        # =================================================

        self.statusBar().showMessage(
            "Open a stereo recording"
        )

    # =====================================================
    # Open recording dialog
    # =====================================================

    def choose_recording(self):

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Stereo Recording",
            "",
            "Stereo recordings (*.bin *.raw *.dat);;All files (*)",
        )

        if not filename:
            return

        self.open_recording(
            filename
        )

    # =====================================================
    # Open recording
    # =====================================================

    def open_recording(
        self,
        filename,
    ):

        try:

            if self.recording is not None:

                self.recording.close()

            self.recording = StereoRecording(
                filename
            )

        except Exception as e:

            self.recording = None

            QMessageBox.critical(
                self,
                "Could not open recording",
                str(e),
            )

            return

        self.setWindowTitle(
            "Stereo Recording Viewer - "
            f"{Path(filename).name}"
        )

        self.populate_frame_list()

        self.current_frame = -1

        if self.recording.frame_count > 0:

            self.select_frame(
                0
            )

        else:

            self.frame_label.setText(
                "Recording contains no frames"
            )

        self.statusBar().showMessage(
            f"Loaded {Path(filename).name} | "
            f"{self.recording.frame_count} frames | "
            f"Image: "
            f"{self.recording.width} × "
            f"{self.recording.height}"
        )

    # =====================================================
    # Clear frame buttons
    # =====================================================

    def clear_frame_buttons(self):

        while (
            self.frame_button_layout.count()
        ):

            item = (
                self.frame_button_layout.takeAt(
                    0
                )
            )

            widget = item.widget()

            if widget is not None:

                widget.deleteLater()

    # =====================================================
    # Populate frame buttons
    # =====================================================

    def populate_frame_list(self):

        self.clear_frame_buttons()

        if self.recording is None:
            return

        for index in range(
            self.recording.frame_count
        ):

            button = QPushButton(
                f"Frame {index + 1}"
            )

            button.setMinimumHeight(
                30
            )

            button.setCheckable(
                True
            )

            button.clicked.connect(
                lambda checked=False,
                       i=index:
                    self.select_frame(i)
            )

            self.frame_button_layout.addWidget(
                button
            )

        # Add empty space after buttons.
        self.frame_button_layout.addStretch()

    # =====================================================
    # Get frame button
    # =====================================================

    def get_frame_button(
        self,
        index,
    ):

        item = (
            self.frame_button_layout.itemAt(
                index
            )
        )

        if item is None:
            return None

        return item.widget()

    # =====================================================
    # Select frame
    # =====================================================

    def select_frame(
        self,
        index,
    ):

        if self.recording is None:
            return

        if (
            index < 0
            or
            index >= self.recording.frame_count
        ):

            return

        try:

            (
                left,
                right,
                trigger_timestamp,
                left_timestamp,
                right_timestamp,
            ) = self.recording.read_frame(
                index
            )

            # -------------------------------------------------
            # Verify decoded dimensions
            # -------------------------------------------------

            expected_shape = (
                self.recording.height,
                self.recording.width,
            )

            if left.shape != expected_shape:

                raise RuntimeError(
                    "Decoded left image has incorrect "
                    f"shape {left.shape}; "
                    f"expected {expected_shape}"
                )

            if right.shape != expected_shape:

                raise RuntimeError(
                    "Decoded right image has incorrect "
                    f"shape {right.shape}; "
                    f"expected {expected_shape}"
                )

            # -------------------------------------------------
            # Display images
            # -------------------------------------------------

            self.left_image.set_image(
                numpy_to_pixmap(
                    left
                )
            )

            self.right_image.set_image(
                numpy_to_pixmap(
                    right
                )
            )

            # -------------------------------------------------
            # Timestamp information
            # -------------------------------------------------

            self.update_timestamp_display(
                index,
                trigger_timestamp,
                left_timestamp,
                right_timestamp,
            )

            # -------------------------------------------------
            # Selection
            # -------------------------------------------------

            self.set_selected_button(
                index
            )

            self.current_frame = index

            # -------------------------------------------------
            # Navigation
            # -------------------------------------------------

            self.previous_button.setEnabled(
                index > 0
            )

            self.next_button.setEnabled(
                index <
                self.recording.frame_count - 1
            )

            self.frame_label.setText(
                f"Frame {index + 1} / "
                f"{self.recording.frame_count}"
            )

            self.statusBar().showMessage(
                f"Frame {index + 1} | "
                f"Image: "
                f"{self.recording.width} × "
                f"{self.recording.height}"
            )

        except Exception as e:

            QMessageBox.critical(
                self,
                "Could not read frame",
                str(e),
            )

    # =====================================================
    # Select button
    # =====================================================

    def set_selected_button(
        self,
        index,
    ):

        if self.recording is None:
            return

        for i in range(
            self.recording.frame_count
        ):

            button = self.get_frame_button(
                i
            )

            if button is None:
                continue

            if i == index:

                button.setChecked(
                    True
                )

                button.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #2878c8;
                        color: white;
                        font-weight: bold;
                    }
                    """
                )

            else:

                button.setChecked(
                    False
                )

                button.setStyleSheet(
                    ""
                )

        # Scroll selected frame into view.

        button = self.get_frame_button(
            index
        )

        if button is not None:

            self.frame_scroll.ensureWidgetVisible(
                button
            )

    # =====================================================
    # Format timestamp
    # =====================================================

    @staticmethod
    def format_timestamp_ns(
        timestamp_ns,
    ):

        seconds = (
            timestamp_ns /
            1_000_000_000.0
        )

        return (
            f"{timestamp_ns:,} ns "
            f"({seconds:.9f} s)"
        )

    # =====================================================
    # Timestamp display
    # =====================================================

    def update_timestamp_display(
        self,
        index,
        trigger_timestamp,
        left_timestamp,
        right_timestamp,
    ):

        # Difference between software timestamps.

        stereo_delta_ns = (
            right_timestamp -
            left_timestamp
        )

        trigger_to_left_ns = (
            left_timestamp -
            trigger_timestamp
        )

        trigger_to_right_ns = (
            right_timestamp -
            trigger_timestamp
        )

        text = (
            f"<b>Frame {index + 1}</b><br><br>"

            f"<b>Trigger:</b><br>"
            f"{self.format_timestamp_ns(trigger_timestamp)}"
            f"<br><br>"

            f"<b>Left:</b><br>"
            f"{self.format_timestamp_ns(left_timestamp)}"
            f"<br>"
            f"Trigger → Left: "
            f"{trigger_to_left_ns / 1e6:.3f} ms"
            f"<br><br>"

            f"<b>Right:</b><br>"
            f"{self.format_timestamp_ns(right_timestamp)}"
            f"<br>"
            f"Trigger → Right: "
            f"{trigger_to_right_ns / 1e6:.3f} ms"
            f"<br><br>"

            f"<b>Left/Right difference:</b> "
            f"{stereo_delta_ns / 1e6:.3f} ms"
            f"<br><br>"

            f"<b>Image size:</b> "
            f"{self.recording.width} × "
            f"{self.recording.height}"
        )

        self.timestamp_label.setText(
            text
        )

    # =====================================================
    # Previous frame
    # =====================================================

    def previous_frame(self):

        if self.current_frame > 0:

            self.select_frame(
                self.current_frame - 1
            )

    # =====================================================
    # Next frame
    # =====================================================

    def next_frame(self):

        if (
            self.recording is not None
            and
            self.current_frame <
            self.recording.frame_count - 1
        ):

            self.select_frame(
                self.current_frame + 1
            )

    # =====================================================
    # Keyboard controls
    # =====================================================

    def keyPressEvent(
        self,
        event,
    ):

        if event.key() == Qt.Key_Left:

            self.previous_frame()

            event.accept()

            return

        if event.key() == Qt.Key_Right:

            self.next_frame()

            event.accept()

            return

        if event.key() == Qt.Key_Home:

            if self.recording is not None:

                self.select_frame(
                    0
                )

            event.accept()

            return

        if event.key() == Qt.Key_End:

            if self.recording is not None:

                self.select_frame(
                    self.recording.frame_count - 1
                )

            event.accept()

            return

        super().keyPressEvent(
            event
        )

    # =====================================================
    # Close
    # =====================================================

    def closeEvent(
        self,
        event,
    ):

        if self.recording is not None:

            self.recording.close()

        event.accept()


# =========================================================
# Main
# =========================================================

def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "Stereo Recording Viewer"
    )

    # -----------------------------------------------------
    # Optional filename from command line
    # -----------------------------------------------------

    filename = None

    if len(sys.argv) > 1:

        filename = sys.argv[1]

        if not os.path.isfile(
            filename
        ):

            QMessageBox.critical(
                None,
                "File not found",
                f"Recording does not exist:\n"
                f"{filename}",
            )

            return 1

    # -----------------------------------------------------
    # Create viewer
    # -----------------------------------------------------

    viewer = StereoViewer(
        filename
    )

    viewer.show()

    return app.exec()


# =========================================================
# Entry point
# =========================================================

if __name__ == "__main__":

    sys.exit(
        main()
    )

