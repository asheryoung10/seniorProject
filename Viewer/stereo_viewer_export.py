"""Viewer/exporter for stereo_raw_v1 recordings.

The export button writes <recording>_export/timestamps.csv plus left/ and
right/ numbered PNG folders.  CSV rows have no header: columns are trigger
timestamp, left image path, and right image path.
"""

import csv
import json
import os
import struct
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)


class StereoRecording:
    def __init__(self, filename):
        self.filename = Path(filename)
        self.file = self.filename.open("rb", buffering=1024 * 1024)
        length_data = self.file.read(8)
        if len(length_data) != 8:
            raise RuntimeError("Invalid recording file: missing header length")
        header_length = struct.unpack("<Q", length_data)[0]
        header_data = self.file.read(header_length)
        if len(header_data) != header_length:
            raise RuntimeError("Incomplete recording header")
        self.header = json.loads(header_data.decode("utf-8"))
        if self.header.get("format") != "stereo_raw_v1":
            raise RuntimeError(f"Unsupported recording format: {self.header.get('format')}")

        self.shape = tuple(self.header["shape"])
        self.dtype = np.dtype(self.header["dtype"])
        self.frame_bytes = int(self.header["frame_bytes"])
        if len(self.shape) != 2 or self.dtype != np.uint8:
            raise RuntimeError("This viewer requires 2D uint8 images")
        self.stored_height, self.stored_width = self.shape
        if self.stored_width % 2:
            raise RuntimeError("Stored image width must be even")
        expected_bytes = self.stored_height * self.stored_width
        if self.frame_bytes != expected_bytes:
            raise RuntimeError("frame_bytes does not match image shape")

        self.data_offset = 8 + header_length
        self.record_size = 24 + 2 * self.frame_bytes
        self.file.seek(0, os.SEEK_END)
        data_size = self.file.tell() - self.data_offset
        if data_size < 0:
            raise RuntimeError("Invalid recording file")
        self.frame_count = data_size // self.record_size
        if data_size % self.record_size:
            print("Warning: ignoring incomplete final record", file=sys.stderr)

    def frame_offset(self, index):
        if not 0 <= index < self.frame_count:
            raise IndexError(f"Frame index out of range: {index}")
        return self.data_offset + index * self.record_size

    def read_trigger_timestamp(self, index):
        self.file.seek(self.frame_offset(index))
        timestamp = self.file.read(8)
        if len(timestamp) != 8:
            raise RuntimeError(f"Could not read trigger timestamp for frame {index}")
        return struct.unpack("<Q", timestamp)[0]

    def read_image(self, index, left):
        offset = self.frame_offset(index) + 24
        if not left:
            offset += self.frame_bytes
        self.file.seek(offset)
        raw = self.file.read(self.frame_bytes)
        if len(raw) != self.frame_bytes:
            raise RuntimeError(f"Could not read complete {'left' if left else 'right'} image")
        stored = np.frombuffer(raw, dtype=self.dtype).reshape(self.shape)
        # Retains the supplied reader's convention: usable pixels are columns
        # 1, 3, 5, ... and the alternating columns are padding.
        return np.ascontiguousarray(stored[:, 1::2])

    def close(self):
        if self.file is not None:
            self.file.close()
            self.file = None


def pair_count(recording, left_offset):
    """Matched pair count after dropping unmatched beginning/end frames."""
    return max(0, recording.frame_count - abs(left_offset))


def pair_sources(pair_index, left_offset):
    """Return (left source index, right source index) for a displayed pair.

    Positive offset advances left: offset +1 pairs left frame 2 with right
    frame 1. Negative offset advances right instead.
    """
    right_index = pair_index + max(0, -left_offset)
    return right_index + left_offset, right_index


def qimage(image):
    image = np.ascontiguousarray(image, dtype=np.uint8)
    height, width = image.shape
    return QImage(image.data, width, height, width, QImage.Format_Grayscale8).copy()


def save_png(image, filename):
    if not qimage(image).save(str(filename), "PNG"):
        raise RuntimeError(f"Could not write PNG: {filename}")


def export_recording(recording, output_dir, left_offset=0, progress=None):
    """Export only the valid pairs, renumbered from one.

    Each CSV row is: trigger_timestamp,left/N.png,right/N.png.  The timestamp
    is from the right/source record anchoring the pair; camera timestamps are
    deliberately never read or exported.
    """
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Export folder already exists: {output_dir}")
    left_dir, right_dir = output_dir / "left", output_dir / "right"
    left_dir.mkdir(parents=True)
    right_dir.mkdir()
    total = pair_count(recording, left_offset)
    with (output_dir / "timestamps.csv").open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        for pair_index in range(total):
            left_index, right_index = pair_sources(pair_index, left_offset)
            number = pair_index + 1
            left_name, right_name = f"left/{number}.png", f"right/{number}.png"
            save_png(recording.read_image(left_index, True), output_dir / left_name)
            save_png(recording.read_image(right_index, False), output_dir / right_name)
            writer.writerow((recording.read_trigger_timestamp(right_index), left_name, right_name))
            if progress:
                progress(number, total)


class ImageDisplay(QLabel):
    def __init__(self, title):
        super().__init__(title)
        self.original = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background:#111; color:#999; border:1px solid #333;")

    def set_image(self, image):
        self.original = QPixmap.fromImage(qimage(image))
        self.scale_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scale_image()

    def scale_image(self):
        if self.original is not None and self.width() and self.height():
            self.setPixmap(self.original.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


class StereoViewer(QMainWindow):
    def __init__(self, filename=None):
        super().__init__()
        self.recording, self.current_pair = None, -1
        self.setWindowTitle("Stereo Recording Viewer")
        self.resize(1400, 850)
        self.setup_ui()
        if filename:
            self.open_recording(filename)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        toolbar = QHBoxLayout()
        self.open_button = QPushButton("Open Recording")
        self.open_button.clicked.connect(self.choose_recording)
        self.export_button = QPushButton("Export CSV + PNGs")
        self.export_button.clicked.connect(self.export_current)
        self.previous_button = QPushButton("◀ Previous")
        self.previous_button.clicked.connect(lambda: self.show_pair(self.current_pair - 1))
        self.next_button = QPushButton("Next ▶")
        self.next_button.clicked.connect(lambda: self.show_pair(self.current_pair + 1))
        self.offset_box = QSpinBox()
        self.offset_box.setPrefix("Left offset: ")
        self.offset_box.setToolTip("Positive = advance left relative to right; negative = delay left.")
        self.offset_box.valueChanged.connect(self.offset_changed)
        self.frame_label = QLabel("No recording loaded")
        self.frame_label.setAlignment(Qt.AlignCenter)
        for widget in (self.open_button, self.export_button, self.previous_button,
                       self.next_button, self.offset_box):
            toolbar.addWidget(widget)
        toolbar.addWidget(self.frame_label, 1)
        layout.addLayout(toolbar)
        image_layout = QHBoxLayout()
        self.left_display, self.right_display = ImageDisplay("Left"), ImageDisplay("Right")
        image_layout.addWidget(self.left_display)
        image_layout.addWidget(self.right_display)
        layout.addLayout(image_layout, 1)
        self.set_controls(False)

    def set_controls(self, loaded):
        self.export_button.setEnabled(loaded)
        self.previous_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.offset_box.setEnabled(loaded)

    def choose_recording(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open stereo recording", "", "Binary files (*.bin);;All files (*)")
        if filename:
            self.open_recording(filename)

    def open_recording(self, filename):
        try:
            new_recording = StereoRecording(filename)
        except Exception as error:
            QMessageBox.critical(self, "Could not open recording", str(error))
            return
        if self.recording:
            self.recording.close()
        self.recording = new_recording
        self.offset_box.blockSignals(True)
        limit = max(0, self.recording.frame_count - 1)
        self.offset_box.setRange(-limit, limit)
        self.offset_box.setValue(0)
        self.offset_box.blockSignals(False)
        self.set_controls(self.recording.frame_count > 0)
        if self.recording.frame_count:
            self.show_pair(0)
        else:
            self.frame_label.setText("Recording contains no complete frames")

    def offset_changed(self):
        if self.recording and pair_count(self.recording, self.offset_box.value()):
            self.show_pair(0)

    def show_pair(self, pair_index):
        if not self.recording:
            return
        offset = self.offset_box.value()
        total = pair_count(self.recording, offset)
        if not 0 <= pair_index < total:
            return
        left_index, right_index = pair_sources(pair_index, offset)
        try:
            left = self.recording.read_image(left_index, True)
            right = self.recording.read_image(right_index, False)
            timestamp = self.recording.read_trigger_timestamp(right_index)
        except Exception as error:
            QMessageBox.critical(self, "Could not read frame", str(error))
            return
        self.current_pair = pair_index
        self.left_display.set_image(left)
        self.right_display.set_image(right)
        self.frame_label.setText(
            f"Matched pair {pair_index + 1} / {total}    Trigger timestamp: {timestamp}    "
            f"(source: left {left_index + 1}, right {right_index + 1})"
        )
        self.previous_button.setEnabled(pair_index > 0)
        self.next_button.setEnabled(pair_index + 1 < total)

    def export_current(self):
        if not self.recording:
            return
        parent = QFileDialog.getExistingDirectory(self, "Choose parent folder for export", str(self.recording.filename.parent))
        if not parent:
            return
        export_dir = Path(parent) / f"{self.recording.filename.stem}_export"
        if export_dir.exists():
            QMessageBox.warning(self, "Export folder exists", f"Choose another parent or rename/remove:\n{export_dir}")
            return
        self.open_button.setEnabled(False)
        self.set_controls(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            offset = self.offset_box.value()
            total = pair_count(self.recording, offset)
            def update(done, count):
                self.frame_label.setText(f"Exporting matched pair {done} / {count}")
                QApplication.processEvents()
            export_recording(self.recording, export_dir, offset, update)
        except Exception as error:
            QMessageBox.critical(self, "Export failed", f"{error}\n\nPartial output, if any: {export_dir}")
        else:
            QMessageBox.information(self, "Export complete", f"Wrote {total} matched pairs to:\n{export_dir}")
        finally:
            QApplication.restoreOverrideCursor()
            self.open_button.setEnabled(True)
            self.set_controls(self.recording.frame_count > 0)
            self.show_pair(min(self.current_pair, pair_count(self.recording, self.offset_box.value()) - 1))

    def closeEvent(self, event):
        if self.recording:
            self.recording.close()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StereoViewer(sys.argv[1] if len(sys.argv) > 1 else None)
    window.show()
    sys.exit(app.exec())
