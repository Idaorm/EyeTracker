from PyQt6.QtWidgets import QWidget, QVBoxLayout, QWidget, QHBoxLayout, QLabel, QPushButton, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from config import C_RED, C_BORDER, C_BG

class RecordingScreen(QWidget):
    def __init__(self, image_path, on_stop):
        super().__init__()
        self.on_stop = on_stop
        self.image_path = image_path
        self._elapsed = 0
        self._build()

        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet(f"background: {C_RED};")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(20, 0, 20, 0)

        dot = QLabel("")
        dot.setStyleSheet("color: white; font-size: 10px; border: none;")
        bar_layout.addWidget(dot)

        self.rec_label = QLabel("REC  00:00")
        self.rec_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold; letter-spacing: 1px; border: none;")
        bar_layout.addWidget(self.rec_label)
        bar_layout.addStretch()

        self.btn_stop = QPushButton("  Termina Registrazione")
        self.btn_stop.setStyleSheet("background: white; color: #c0392b; font-weight: bold; padding: 8px 20px; border-radius: 6px; border: none;")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.clicked.connect(self._stop)
        bar_layout.addWidget(self.btn_stop)

        layout.addWidget(bar)

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setStyleSheet("background: black;")
        layout.addWidget(self.img_label, stretch=1)
        self._refresh_image()

    def _tick(self):
        self._elapsed += 1
        m, s = divmod(self._elapsed, 60)
        self.rec_label.setText(f"REC  {m:02d}:{s:02d}")

    def _stop(self):
        self.btn_stop.setEnabled(False)
        self.btn_stop.setText("Salvataggio in corso...")
        self._timer.stop()
        self.on_stop()

    def _refresh_image(self):
        pix = QPixmap(self.image_path)
        screen = QApplication.primaryScreen().size()
        pix = pix.scaled(screen.width(), screen.height() - 52,
                         Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
        self.img_label.setPixmap(pix)

    def resizeEvent(self, event):
        self._refresh_image()
        super().resizeEvent(event)
