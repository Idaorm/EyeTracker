import threading
from pathlib import Path
from PyQt6.QtWidgets import QMainWindow, QApplication, QProgressDialog
from PyQt6.QtCore import pyqtSignal, QObject, Qt

# Importiamo le nostre risorse personalizzate dai nuovi file
from config import STYLE_BASE, DESKTOP
from services import sync_emotiv, save_emotiv_data
from screens.setup_screen import SetupScreen
from screens.recording_screen import RecordingScreen
from screens.result_screen import ResultScreen

from recorder import GazeRecorder

# Manteniamo la struttura degli epoch di sessione
_session_epochs = {"start": None, "stop": None}

class GazeSignal(QObject):
    point = pyqtSignal(float, float)


class MainWindow(QMainWindow):
    # Usiamo il segnale Qt per comunicare la fine della registrazione dal thread in background
    stop_finished = pyqtSignal(object, list, object, object, object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Eye Tracker & Emotiv Integration")
        self.setStyleSheet(STYLE_BASE)
        
        self.recorder = None
        self.gaze_sig = GazeSignal()
        self.image_path = None
        self.session_name = "sessione"
        
        self.stop_finished.connect(self._finish_stop)
        self._show_setup()

    def _show_setup(self):
        self.setCentralWidget(SetupScreen(on_start=self._on_start, on_aggregate=self._on_aggregate))
        self.showNormal()

    def _on_start(self, image_path, session_name):
        self.image_path = image_path
        self.session_name = session_name
        
        # Sincronizzazione ed avvio
        _session_epochs["start"] = sync_emotiv(f"START_{session_name}")
        
        try:
            self.recorder = GazeRecorder()
            self.recorder.start()
        except Exception as e:
            print(f"[Errore Tobii] Impossibile avviare il tracker: {e}")
            self.recorder = None
            
        self.setCentralWidget(RecordingScreen(self.image_path, on_stop=self._on_stop))
        self.showFullScreen()

    def _on_stop(self):
        _session_epochs["stop"] = sync_emotiv("STOP_TOBII")
        
        progress = QProgressDialog("Salvataggio dati e download metriche EEG...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setWindowFlags(progress.windowFlags() | Qt.WindowType.CustomizeWindowHint)
        progress.show()

        def worker():
            session_start_epoch = _session_epochs["start"]
            session_end_epoch = _session_epochs["stop"]
            
            emotiv_res = save_emotiv_data()
            emotiv_excel_path = emotiv_res.get("filename")
            
            if emotiv_res.get("session_start_epoch") is not None:
                session_start_epoch = emotiv_res["session_start_epoch"]
                session_end_epoch = emotiv_res["session_end_epoch"]

            if self.recorder:
                self.recorder.stop()
                if self.recorder._thread:
                    self.recorder._thread.join(timeout=2)
                points = list(self.recorder.points)
                print(f"[ui] Punti Tobii registrati: {len(points)}")
                self.recorder.save_csv(str(DESKTOP / f"{self.session_name}.csv"))
            else:
                points = []

            self.stop_finished.emit(
                emotiv_excel_path,
                points,
                progress,
                session_start_epoch,
                session_end_epoch,
            )

        threading.Thread(target=worker, daemon=True).start()

    def _finish_stop(self, emotiv_excel_path, points, progress_dialog, session_start_epoch, session_end_epoch):
        progress_dialog.close()
        self.showNormal()
        self.setCentralWidget(ResultScreen(
            self.image_path, 
            self.session_name, 
            [points], 
            on_restart=self._show_setup, 
            emotiv_file=emotiv_excel_path,
            session_start_epoch=session_start_epoch,
            session_end_epoch=session_end_epoch,
        )) 

    def _on_aggregate(self, image_path, session_summary, all_points):
        self.image_path = image_path
        self.session_name = session_summary
        self.showNormal()
        self.setCentralWidget(ResultScreen(
            self.image_path, 
            self.session_name, 
            all_points, 
            on_restart=self._show_setup
        ))