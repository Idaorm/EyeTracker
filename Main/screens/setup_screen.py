import csv
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QLineEdit, QFileDialog, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

# Prendiamo stili e colori dal nostro file di configurazione
from config import C_SURFACE, C_BORDER, C_TEXT, C_MUTED, C_BG, C_GREEN, C_ACCENT, DESKTOP, styled_btn



class SetupScreen(QWidget):
    def __init__(self, on_start, on_aggregate):
        super().__init__()
        self.on_start = on_start
        self.on_aggregate = on_aggregate
        self.image_path = None
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QWidget()
        card.setFixedWidth(520)
        card.setStyleSheet(f"background: {C_SURFACE}; border-radius: 16px; border: 1px solid {C_BORDER};")
        layout = QVBoxLayout(card)
        layout.setSpacing(16)
        layout.setContentsMargins(40, 30, 40, 30)

        title = QLabel("  Eye Tracker")
        title.setStyleSheet(f"font-size: 26px; font-weight: 700; color: {C_TEXT}; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("Carica l'immagine stimolo per registrare o aggregare dati passati")
        sub.setStyleSheet(f"color: {C_MUTED}; font-size: 12px; border: none;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        layout.addWidget(sub)

        self.preview = QLabel("Clicca per selezionare un'immagine")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedHeight(200)
        self.preview.setStyleSheet(f"border: 2px dashed {C_BORDER}; border-radius: 10px; background: {C_BG}; color: {C_MUTED};")
        self.preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview.mousePressEvent = lambda e: self._load_image()
        layout.addWidget(self.preview)

        row = QHBoxLayout()
        lbl = QLabel("Sessione:")
        lbl.setStyleSheet("border: none;")
        lbl.setFixedWidth(70)
        self.session_name = QLineEdit()
        self.session_name.setPlaceholderText("es. Paziente_01 (solo per registrazione)")
        row.addWidget(lbl)
        row.addWidget(self.session_name)
        layout.addLayout(row)

        btn_load = styled_btn("  Scegli immagine", C_BORDER, C_TEXT)
        btn_load.clicked.connect(self._load_image)
        layout.addWidget(btn_load)

        self.btn_start = styled_btn("▶  Avvia Registrazione", C_GREEN, "white", "#1a3a2a")
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._start)
        layout.addWidget(self.btn_start)

        # Pulsante per l'aggregazione Multi-Soggetto
        self.btn_aggregate = styled_btn("  Analisi Multi-Soggetto (Aggrega CSV)", C_ACCENT, "white", "#1e293b")
        self.btn_aggregate.setEnabled(False)
        self.btn_aggregate.clicked.connect(self._aggregate_files)
        layout.addWidget(self.btn_aggregate)

        outer.addWidget(card)

    def _load_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Scegli immagine", str(Path.home()), "Immagini (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.image_path = path
            pix = QPixmap(path).scaled(440, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.preview.setPixmap(pix)
            self.preview.setStyleSheet(f"border: 2px solid {C_ACCENT}; border-radius: 10px; background: {C_BG};")
            self.btn_start.setEnabled(True)
            self.btn_aggregate.setEnabled(True)

    def _start(self):
        if self.image_path:
            self.on_start(self.image_path, self.session_name.text().strip() or "sessione")

    def _aggregate_files(self):
        if not self.image_path:
            return

        files, _ = QFileDialog.getOpenFileNames(
            self, "Seleziona i file CSV dei soggetti da aggregare",
            str(DESKTOP), "File CSV (*.csv)"
        )
        
        if not files:
            return
            
        if len(files) < 2:
            QMessageBox.warning(self, "Seleziona più file", "Seleziona almeno 2 file CSV per eseguire un'analisi aggregata collettiva.")
            return

        all_subjects_points = []
        for file_path in files:
            pts = []
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    next(reader, None)  # Salta l'intestazione
                    for row in reader:
                        if len(row) >= 3:
                            try:
                                x = float(row[0].replace(",", "."))
                                y = float(row[1].replace(",", "."))
                                t = int(float(row[2]))
                                if 0 <= x <= 1 and 0 <= y <= 1:
                                    pts.append((x, y, t))
                            except ValueError:
                                continue
            except Exception as e:
                print(f"Errore caricamento {file_path}: {e}")
            
            if pts:
                all_subjects_points.append(pts)

        if not all_subjects_points:
            QMessageBox.critical(self, "Errore", "Nessun dato valido estratto dai file CSV selezionati.")
            return

        session_summary = f"Aggregazione Multi-Soggetto ({len(all_subjects_points)} soggetti)"
        self.on_aggregate(self.image_path, session_summary, all_subjects_points)