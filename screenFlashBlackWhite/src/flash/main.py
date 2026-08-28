import sys
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout


class FlashTest(QWidget):
    def __init__(self, refresh_rate=144, white_frames=1, black_frames=5):
        super().__init__()

        self.refresh_rate = refresh_rate
        self.white_frames = white_frames
        self.black_frames = black_frames

        self.frame = 0
        self.running = True

        # Fullscreen black window
        self.setWindowTitle("Camera Synchronization Test")
        self.setStyleSheet("background-color: black;")

        # Small status label
        self.label = QLabel()
        self.label.setStyleSheet("""
            QLabel {
                color: #333333;
                background-color: transparent;
                font-size: 18px;
            }
        """)
        self.label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)

        # One monitor refresh
        interval_ms = 1000.0 / self.refresh_rate

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.next_frame)
        self.timer.start(round(interval_ms))

        self.update_display()

    def next_frame(self):
        self.frame += 1
        self.update_display()

    def update_display(self):
        cycle_length = self.white_frames + self.black_frames
        position = self.frame % cycle_length

        if position < self.white_frames:
            self.setStyleSheet("background-color: white;")
        else:
            self.setStyleSheet("background-color: black;")

        # Hide status during the test
        self.label.setText("")

    def keyPressEvent(self, event):
        # ESC quits
        if event.key() == Qt.Key_Escape:
            self.close()

        # SPACE pauses/resumes
        elif event.key() == Qt.Key_Space:
            if self.running:
                self.timer.stop()
                self.running = False
            else:
                self.timer.start(round(1000.0 / self.refresh_rate))
                self.running = True


def main():
    app = QApplication(sys.argv)

    # 144 Hz monitor
    #
    # Pattern:
    #   1 frame WHITE
    #   5 frames BLACK
    #
    # At 144 Hz:
    #   frame = ~6.94 ms
    #   flash interval = ~41.67 ms
    test = FlashTest(
        refresh_rate=144,
        white_frames=1,
        black_frames=1,
    )

    test.showFullScreen()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()