import os
import csv
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from scipy.ndimage import gaussian_filter

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QSlider, QComboBox, QMessageBox, QFileDialog, QProgressDialog
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap

from config import (C_TEXT, C_GREEN, C_ACCENT, C_SURFACE, C_BORDER, C_BG, 
                    C_MUTED, C_RED, DESKTOP, styled_btn)

class ResultScreen(QWidget):
    def __init__(self, image_path, session_name, points, on_restart, emotiv_file=None,
                 session_start_epoch=None, session_end_epoch=None):
        super().__init__()
        self.image_path = image_path
        self.session_name = session_name
        self.points = points  
        self.on_restart = on_restart
        self.emotiv_file = emotiv_file  # percorso dell'Excel generato dal server Emotiv
        self.session_start_epoch = session_start_epoch
        self.session_end_epoch = session_end_epoch
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        if len(self.points) == 1:
            title_text = f"  {self.session_name}  —  {len(self.points[0]):,} punti registrati"
        else:
            total_pts = sum(len(s) for s in self.points)
            title_text = f"👥  {self.session_name}  —  {total_pts:,} punti globali combinati"

        title = QLabel(title_text)
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {C_TEXT};")
        header.addWidget(title)
        header.addStretch()

        btn_save = styled_btn("  Salva report", C_GREEN)
        btn_save.clicked.connect(self._save_result_image)
        header.addWidget(btn_save)

        btn_new = styled_btn("↩  Schermata Home", C_ACCENT)
        btn_new.clicked.connect(self._stop_and_restart)
        header.addWidget(btn_new)

        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"QTabWidget::pane {{ background: {C_SURFACE}; }}")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs, stretch=1)

        self.tabs.addTab(self._make_gazepath(), "  Gaze Path")
        self.tabs.addTab(self._make_heatmap(),  "  Heatmap globale")
        
        if len(self.points) == 1:
            self.tabs.addTab(self._make_timeseries(), "  Time Series")
            self.tabs.addTab(self._make_playback(), "▶  Replay Sguardo")
            
        
        if self.emotiv_file and os.path.exists(self.emotiv_file):
            self.tabs.addTab(self._make_emotiv_charts(), "Metriche Mentali (EEG)")
            self.tabs.addTab(self._make_motion_charts(), "Movimento (Headset)")
            self.tabs.addTab(self._make_band_power_chart(), "Bande di Frequenza")

    def _plot_defaults(self, ax):
        ax.set_facecolor("#0f1117")
        ax.figure.patch.set_facecolor("#1a1d27")
        for spine in ax.spines.values():
            spine.set_edgecolor("#2a2d3a")
        ax.tick_params(colors="#6b7280")
        ax.xaxis.label.set_color("#6b7280")
        ax.yaxis.label.set_color("#6b7280")
        ax.title.set_color("#e8e6e0")

    def _make_gazepath(self):
        fig = Figure(figsize=(8, 5))
        fig.patch.set_facecolor(C_SURFACE)
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        self._plot_defaults(ax)

        img = plt.imread(self.image_path)
        ax.imshow(img, extent=[0, 1, 1, 0], aspect='auto')

        if self.points and any(self.points):
            if len(self.points) == 1:
                pts = self.points[0]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                ts = [p[2] for p in pts]
                dts = np.diff(ts, prepend=ts[0])
                rng = dts.max() - dts.min()
                sizes = ((dts - dts.min()) / rng * 600 + 40) if rng > 0 else np.full(len(ts), 80)

                ax.plot(xs, ys, color='#4f8ef7', alpha=0.5, linewidth=1.2, zorder=1)
                ax.scatter(xs, ys, s=sizes, c='#4f8ef7', alpha=0.55, edgecolors='white', linewidths=0.3, zorder=2)
                ax.scatter(xs[0],  ys[0],  s=150, c='#2ecc71', edgecolors='white', linewidths=1.2, zorder=4, label='Inizio')
                ax.scatter(xs[-1], ys[-1], s=150, c='#e74c3c', edgecolors='white', linewidths=1.2, zorder=4, label='Fine')
                ax.legend(loc='best', fontsize=9, facecolor=C_SURFACE, labelcolor=C_TEXT, edgecolor=C_BORDER)
            else:
                cmap = plt.get_cmap('tab10')
                for idx, pts in enumerate(self.points):
                    if not pts: continue
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    color = cmap(idx % 10)

                    ax.plot(xs, ys, color=color, alpha=0.4, linewidth=1.0, zorder=1)
                    ax.scatter(xs, ys, s=25, color=color, alpha=0.35, edgecolors='none', zorder=2)
                    ax.scatter(xs[0],  ys[0],  s=50, c='#2ecc71', edgecolors='white', linewidths=0.5, zorder=3)
                    ax.scatter(xs[-1], ys[-1], s=50, c='#e74c3c', edgecolors='white', linewidths=0.5, zorder=3)

                legend_elements = [
                    Line2D([0], [0], marker='o', color='w', label='Punti di Inizio (Soggetti)', markerfacecolor='#2ecc71', markeredgecolor='white', markersize=8),
                    Line2D([0], [0], marker='o', color='w', label='Punti di Fine (Soggetti)', markerfacecolor='#e74c3c', markeredgecolor='white', markersize=8)
                ]
                ax.legend(handles=legend_elements, loc='best', fontsize=9, facecolor=C_SURFACE, labelcolor=C_TEXT, edgecolor=C_BORDER)

        ax.set_xlim(0, 1); ax.set_ylim(1, 0)
        ax.set_title("Percorsi visivi sovrapposti", pad=10)
        ax.axis('off')
        fig.tight_layout()
        return canvas

    def _make_heatmap(self):
        fig = Figure(figsize=(8, 5))
        fig.patch.set_facecolor(C_SURFACE)
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        self._plot_defaults(ax)

        img = plt.imread(self.image_path)
        ax.imshow(img, extent=[0, 1, 1, 0], aspect='auto', zorder=0)

        if self.points:
            all_xs = []
            all_ys = []
            for pts in self.points:
                all_xs.extend([p[0] for p in pts])
                all_ys.extend([p[1] for p in pts])

            if all_xs:
                xs = np.array(all_xs)
                ys = np.array(all_ys)
                h, _, _ = np.histogram2d(xs, ys, bins=80, range=[[0,1],[0,1]])
                h_smooth = gaussian_filter(h.T, sigma=3)
                ax.imshow(h_smooth, extent=[0,1,1,0], origin='upper',
                          cmap='hot', alpha=0.6, aspect='auto', zorder=1)

        ax.set_xlim(0, 1); ax.set_ylim(1, 0)
        ax.set_title("Heatmap globale cumulativa", pad=10)
        ax.axis('off')
        fig.tight_layout()
        return canvas

    def _make_timeseries(self):
        fig = Figure(figsize=(8, 4))
        fig.patch.set_facecolor(C_SURFACE)
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        self._plot_defaults(ax)

        if self.points and self.points[0]:
            pts = self.points[0]
            ts = np.array([p[2] for p in pts])
            xs = np.array([p[0] for p in pts])
            ys = np.array([p[1] for p in pts])
            t_norm = (ts - ts[0]) / 1000
            ax.plot(t_norm, xs, label="X", color='#4f8ef7', linewidth=1.2)
            ax.plot(t_norm, ys, label="Y", color='#e74c3c', linewidth=1.2)
            ax.invert_yaxis()
            ax.set_xlabel("Tempo (s)")
            ax.set_ylabel("Coordinata")
            ax.set_title("Coordinate nel tempo", pad=10)
            ax.legend(facecolor=C_SURFACE, labelcolor=C_TEXT, edgecolor=C_BORDER)
            ax.grid(True, color=C_BORDER, linewidth=0.5)

        fig.tight_layout()
        return canvas

    def _make_playback(self):
        self.pb_widget = QWidget()
        vbox = QVBoxLayout(self.pb_widget)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(12)

        self.pb_fig = Figure(figsize=(8, 5))
        self.pb_fig.patch.set_facecolor(C_SURFACE)
        self.pb_canvas = FigureCanvas(self.pb_fig)
        self.pb_ax = self.pb_fig.add_subplot(111)
        self._plot_defaults(self.pb_ax)

        img = plt.imread(self.image_path)
        self.pb_ax.imshow(img, extent=[0, 1, 1, 0], aspect='auto')
        self.pb_ax.set_xlim(0, 1)
        self.pb_ax.set_ylim(1, 0)
        self.pb_ax.axis('off')

        self.pb_dot, = self.pb_ax.plot([], [], 'ro', markersize=14, markeredgecolor='white', markeredgewidth=1.5, zorder=5)

        vbox.addWidget(self.pb_canvas, stretch=1)

        controls = QHBoxLayout()
        controls.setSpacing(15)

        self.btn_play = styled_btn("Play", C_ACCENT)
        self.btn_play.setFixedWidth(100)
        self.btn_play.clicked.connect(self._toggle_playback)
        controls.addWidget(self.btn_play)

        pts_len = len(self.points[0]) if (self.points and self.points[0]) else 0
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, max(0, pts_len - 1))
        self.slider.sliderMoved.connect(self._on_slider_moved)
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ height: 6px; background: {C_BG}; border-radius: 3px; }}
            QSlider::sub-page:horizontal {{ background: {C_ACCENT}; border-radius: 3px; }}
            QSlider::handle:horizontal {{ background: {C_TEXT}; width: 14px; margin-top: -4px; margin-bottom: -4px; border-radius: 7px; }}
        """)
        controls.addWidget(self.slider)

        lbl_speed = QLabel("Velocità:")
        lbl_speed.setStyleSheet("border: none; color: #6b7280; font-weight: 600;")
        controls.addWidget(lbl_speed)

        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["1x", "2x", "5x", "10x"])
        self.combo_speed.setFixedWidth(80)
        controls.addWidget(self.combo_speed)

        vbox.addLayout(controls)

        self.pb_timer = QTimer(self)
        self.pb_timer.setInterval(30)
        self.pb_timer.timeout.connect(self._advance_playback_frame)
        self.pb_index = 0
        self.pb_playing = False

        if self.points and self.points[0]:
            self._update_playback_dot(0)

        return self.pb_widget
    
    def _make_emotiv_charts(self):
        """
        Genera il grafico delle metriche cognitive caricate dall'Excel.
        I marker vengono presi dal foglio 'Markers' con posizionamento millimetrico,
        etichette orizzontali e l'inizio delle linee attaccato perfettamente al primo marker.
        I marker di STOP vengono automaticamente ignorati e nascosti.
        """
        import matplotlib.ticker as mtick

        fig = Figure(figsize=(9, 5.5))  # Alzata leggermente la figura per dare spazio alle etichette
        fig.patch.set_facecolor(C_SURFACE)
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        self._plot_defaults(ax)

        try:
            # 1. Carichiamo i dati delle metriche
            df = pd.read_excel(self.emotiv_file, sheet_name="Performance")
            
            # 2. Carichiamo la lista ESATTA dei marker dal foglio dedicato
            try:
                df_markers = pd.read_excel(self.emotiv_file, sheet_name="Markers")
            except Exception:
                df_markers = pd.DataFrame()

            if df.empty:
                ax.text(0.5, 0.5, "Nessun dato EEG disponibile per questa sessione",
                        color=C_MUTED, ha="center", va="center")
                fig.tight_layout()
                return canvas

            
            if "epoch" in df.columns and self.session_start_epoch is not None:
                start = self.session_start_epoch
                end = self.session_end_epoch if self.session_end_epoch is not None else df["epoch"].max()
                df = df[(df["epoch"] >= start) & (df["epoch"] <= end)].reset_index(drop=True)
                
                
                if not df_markers.empty:
                    df_markers = df_markers[(df_markers["epoch"] >= start) & (df_markers["epoch"] <= end)].reset_index(drop=True)

            if df.empty:
                ax.text(0.5, 0.5,
                        "Nessun campione EEG ricevuto tra START e STOP.",
                        color=C_RED, ha="center", va="center", fontsize=10)
                fig.tight_layout()
                return canvas

            
            if "epoch" in df.columns and len(df) > 0:
                t0 = self.session_start_epoch if self.session_start_epoch is not None else df["epoch"].iloc[0]
                
                # Se il primo dato arriva DOPO il marker (causa ritardo di 10s di Emotiv),
                # duplica la prima riga di dati e la porta indietro
                if df["epoch"].iloc[0] > t0:
                    first_row = df.iloc[[0]].copy()
                    first_row["epoch"] = t0
                    df = pd.concat([first_row, df]).reset_index(drop=True)

                x_axis = df["epoch"] - t0
                ax.set_xlabel("Tempo dall'inizio della registrazione (secondi)", fontweight="bold", labelpad=10)
            else:
                t0 = df["epoch"].iloc[0] if "epoch" in df.columns and len(df) > 0 else 0
                x_axis = np.arange(len(df))
                ax.set_xlabel("Campioni acquisiti", fontweight="bold", labelpad=10)

            cols_to_plot = [
                c for c in df.columns
                if c not in ("epoch", "time", "marker") and not c.endswith(".isActive") and c != "lex"
            ]

            color_map = {
                "attention": "#3b82f6", "foc": "#3b82f6",
                "str": "#ef4444", "eng": "#8b5cf6",
                "rel": "#10b981", "exc": "#f59e0b", "int": "#ec4899",
            }

            for col in cols_to_plot:
                col_lower = col.lower()
                color = next((v for k, v in color_map.items() if k in col_lower), "#a8a29e")
                
                data_in_percent = df[col] * 100
                smoothed_data = data_in_percent.rolling(window=4, min_periods=1).mean()
                
                ax.plot(x_axis, smoothed_data, label=col.capitalize(), linewidth=2.5, color=color)
                ax.fill_between(x_axis, smoothed_data, alpha=0.06, color=color)

            # === GESTIONE DEI MARKER ===
            if not df_markers.empty and "epoch" in df_markers.columns and "label" in df_markers.columns:
                last_m = None
                
                for idx, row in df_markers.iterrows():
                    curr_m = row["label"]
                    m_epoch = row["epoch"]
                    
                    if pd.notna(curr_m) and curr_m != "" and str(curr_m).strip() != "—" and curr_m != last_m:
                        display_name = str(curr_m)
                        
                        if display_name.startswith("STOP_"):
                            continue  
                        
                        pos_x = m_epoch - t0
                        
                        if display_name.startswith("START_"):
                            display_name = display_name[6:]
                        ax.axvline(x=pos_x, color="#475569", linestyle="--", linewidth=1.8, alpha=0.85)
                        ax.text(pos_x, 108, display_name,
                                color="#ffffff", fontsize=10, rotation=0, fontweight="bold",
                                ha="center", va="center",
                                bbox=dict(facecolor="#1e293b", alpha=0.9, edgecolor='#64748b', boxstyle='round,pad=0.4'))
                        last_m = curr_m

            ax.set_title("Stato Emotivo e Cognitivo durante la Sessione", pad=25, fontsize=14, fontweight="bold")
            ax.set_ylabel("Intensità (%)", fontweight="bold")
            
            ax.set_ylim(-5, 125)
            ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100))

            leg = ax.legend(facecolor=C_SURFACE, labelcolor=C_TEXT, edgecolor=C_BORDER,
                            loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=9,
                            title="Metriche", title_fontproperties={'weight': 'bold'})
            leg.get_title().set_color("#ffffff") 
            
            ax.grid(True, color=C_BORDER, linestyle="--", alpha=0.6)

            if cols_to_plot:
                medie = "    ".join(f"{c.upper()}: {(df[c].mean()*100):.1f}%" for c in cols_to_plot)
                fig.text(0.5, 0.02, f"VALORI MEDI GLOBALI:   {medie}",
                         color="#94a3b8", ha="center", fontsize=9, fontweight="bold",
                         bbox=dict(facecolor=C_BORDER, alpha=0.4, edgecolor='none', boxstyle='round,pad=0.6'))

        except Exception as e:
            ax.text(0.5, 0.5, f"Errore nel rendering dei dati EEG:\n{e}", color=C_RED, ha="center", va="center")

        fig.tight_layout(rect=[0, 0.05, 0.82, 0.95])
        return canvas

    def _make_motion_charts(self):
        """
        Genera i grafici dei dati di movimento (accelerometro + orientamento)
        dell'headset Emotiv, caricati dal foglio "Motion" dell'Excel
        """
        fig = Figure(figsize=(8, 6))
        fig.patch.set_facecolor(C_SURFACE)
        canvas = FigureCanvas(fig)
        ax_orient = fig.add_subplot(211)
        ax_accel = fig.add_subplot(212)
        self._plot_defaults(ax_orient)
        self._plot_defaults(ax_accel)

        try:
            df = pd.read_excel(self.emotiv_file, sheet_name="Motion")

            if df.empty:
                ax_orient.text(0.5, 0.5, "Nessun dato di movimento disponibile per questa sessione",
                                color=C_MUTED, ha="center", va="center", transform=ax_orient.transAxes)
                fig.tight_layout()
                return canvas

            if "epoch" in df.columns and self.session_start_epoch is not None:
                start = self.session_start_epoch
                end = self.session_end_epoch if self.session_end_epoch is not None else df["epoch"].max()
                df = df[(df["epoch"] >= start) & (df["epoch"] <= end)].reset_index(drop=True)

            if df.empty:
                ax_orient.text(0.5, 0.5,
                                "Nessun campione di movimento ricevuto tra START e STOP.",
                                color=C_RED, ha="center", va="center", fontsize=10, transform=ax_orient.transAxes)
                fig.tight_layout()
                return canvas

            if "epoch" in df.columns and len(df) > 1:
                t0 = self.session_start_epoch if self.session_start_epoch is not None else df["epoch"].iloc[0]
                x_axis = df["epoch"] - t0
            else:
                x_axis = np.arange(len(df))
            cols_lower = {c.lower(): c for c in df.columns}

            def find_col(*names):
                for n in names:
                    if n.lower() in cols_lower:
                        return cols_lower[n.lower()]
                return None

            quat_cols = [find_col(n) for n in ("Q0", "Q1", "Q2", "Q3")]
            quat_cols = [c for c in quat_cols if c is not None]
            gyro_cols = [find_col(n) for n in ("GYROX", "GYROY", "GYROZ")]
            gyro_cols = [c for c in gyro_cols if c is not None]
            accel_cols = [find_col(n) for n in ("ACCX", "ACCY", "ACCZ")]
            accel_cols = [c for c in accel_cols if c is not None]
            mag_cols = [find_col(n) for n in ("MAGX", "MAGY", "MAGZ")]
            mag_cols = [c for c in mag_cols if c is not None]

            orient_cols = quat_cols if quat_cols else gyro_cols
            orient_label = "Orientamento (quaternioni Q0-Q3)" if quat_cols else "Velocità angolare (giroscopio)"

            if orient_cols:
                for col in orient_cols:
                    ax_orient.plot(x_axis, df[col], label=col, linewidth=1.3)
                ax_orient.set_title(orient_label, fontsize=11, fontweight="bold", color=C_TEXT)
                ax_orient.legend(facecolor=C_SURFACE, labelcolor=C_TEXT, edgecolor=C_BORDER,
                                  loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=8)
            else:
                ax_orient.text(0.5, 0.5, "Dati di orientamento non disponibili",
                                color=C_MUTED, ha="center", va="center", transform=ax_orient.transAxes)
            ax_orient.grid(True, color=C_BORDER, linestyle=":", alpha=0.5)

            if accel_cols:
                for col in accel_cols:
                    ax_accel.plot(x_axis, df[col], label=col, linewidth=1.3)
            if mag_cols:
                for col in mag_cols:
                    ax_accel.plot(x_axis, df[col], label=col, linewidth=1.0, linestyle="--", alpha=0.7)

            if accel_cols or mag_cols:
                ax_accel.set_title("Accelerometro / Magnetometro", fontsize=11, fontweight="bold", color=C_TEXT)
                ax_accel.legend(facecolor=C_SURFACE, labelcolor=C_TEXT, edgecolor=C_BORDER,
                                 loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=8)
            else:
                ax_accel.text(0.5, 0.5, "Dati di accelerometro/magnetometro non disponibili",
                               color=C_MUTED, ha="center", va="center", transform=ax_accel.transAxes)
            ax_accel.grid(True, color=C_BORDER, linestyle=":", alpha=0.5)
            ax_accel.set_xlabel("Tempo dall'inizio della registrazione (secondi)")

            if "epoch" in df.columns:
                marker_epochs = []
                for ax in (ax_orient, ax_accel):
                    ax.axvline(x=0, color=C_MUTED, linestyle="--", alpha=0.6)

        except Exception as e:
            ax_orient.text(0.5, 0.5, f"Errore nel rendering dei dati di movimento:\n{e}",
                            color=C_RED, ha="center", va="center", transform=ax_orient.transAxes)

        fig.tight_layout(rect=[0, 0.03, 0.78, 1])
        return canvas

    def _make_band_power_chart(self):
        """
        Genera il grafico delle Bande di Frequenza (Band Power) filtrate per sessione.
        Raggruppa dinamicamente i canali presenti nell'Excel per evitare KeyError.
        """
        fig = Figure(figsize=(9, 5))
        fig.patch.set_facecolor(C_SURFACE)
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        self._plot_defaults(ax)

        try:
            # 1. Carichiamo il foglio BandPower
            df_pow = pd.read_excel(self.emotiv_file, sheet_name="BandPower")
            if df_pow.empty:
                ax.text(0.5, 0.5, "Nessun dato di Band Power disponibile.", color=C_MUTED, ha="center", va="center")
                fig.tight_layout()
                return canvas

            # 2. Ritaglio temporale sulla sessione corrente
            if "epoch" in df_pow.columns and self.session_start_epoch is not None:
                start = self.session_start_epoch
                end = self.session_end_epoch if self.session_end_epoch is not None else df_pow["epoch"].max()
                df_pow = df_pow[(df_pow["epoch"] >= start) & (df_pow["epoch"] <= end)].reset_index(drop=True)

            if df_pow.empty:
                ax.text(0.5, 0.5, "Nessun dato Band Power nel range di questa sessione.", color=C_MUTED, ha="center", va="center")
                fig.tight_layout()
                return canvas

            # Asse X basato sul tempo relativo
            t0 = self.session_start_epoch if self.session_start_epoch is not None else df_pow["epoch"].iloc[0]
            x_axis = df_pow["epoch"] - t0

            # Definizione delle bande che vogliamo estrarre
            bands = ["theta", "alpha", "betaL", "betaH", "gamma"]
            band_data = {b: [] for b in bands}

            # 3. RAGGRUPPAMENTO DINAMICO: Scorriamo le colonne reali del file Excel
            # Evita i KeyError se mancano canali come O1 o AF3
            valid_columns_count = 0
            for col in df_pow.columns:
                if "/" in col:  # Formato classico Emotiv "Canale/Banda" (es: "AF3/alpha")
                    parts = col.split("/")
                    band_name = parts[1] # prende la parte dopo la barra
                    
                    if band_name in band_data:
                        band_data[band_name].append(df_pow[col])
                        valid_columns_count += 1

            if valid_columns_count == 0:
                ax.text(0.5, 0.5, "Formato colonne BandPower non riconosciuto.", color=C_RED, ha="center", va="center")
                fig.tight_layout()
                return canvas

            # Palette colori coerente per le onde cerebrali
            band_colors = {
                "theta": "#2ecc71",  # Verde
                "alpha": "#3498db",  # Blu
                "betaL": "#f1c40f",  # Giallo
                "betaH": "#e67e22",  # Arancione
                "gamma": "#9b59b6"   # Viola
            }

            # 4. Calcoliamo la media globale delle bande e le disegnamo
            for band in bands:
                lists_for_band = band_data[band]
                if len(lists_for_band) > 0:
                    # Fa la media di tutti i canali disponibili per questa specifica banda
                    avg_series = pd.concat(lists_for_band, axis=1).mean(axis=1)
                    
                    # Applichiamo un leggero smoothing per rendere il grafico morbido e leggibile
                    smoothed = avg_series.rolling(window=5, min_periods=1).mean()
                    
                    color = band_colors.get(band, "#ffffff")
                    ax.plot(x_axis, smoothed, label=band.upper(), color=color, linewidth=2)

            # Abbellimenti grafici coerenti con la UI
            ax.set_title("Potenza delle Bande di Frequenza (Media Canali)", pad=15, fontsize=12, fontweight="bold")
            ax.set_xlabel("Tempo dall'inizio (secondi)", fontweight="bold")
            ax.set_ylabel("Potenza (µV²)", fontweight="bold")
            ax.grid(True, color=C_BORDER, linestyle="--", alpha=0.5)
            
            # Legenda con titolo stilizzato
            leg = ax.legend(facecolor=C_SURFACE, labelcolor=C_TEXT, edgecolor=C_BORDER, loc="upper right")
            if leg:
                leg.set_title("Onde Cerebrali")
                leg.get_title().set_color(C_TEXT)
                leg.get_title().set_fontweight("bold")

        except Exception as e:
            ax.text(0.5, 0.5, f"Errore BandPower:\n{e}", color=C_RED, ha="center", va="center")

        fig.tight_layout()
        return canvas

    def _toggle_playback(self):
        if not self.points or not self.points[0]:
            return
        if self.pb_playing:
            self.pb_timer.stop()
            self.pb_playing = False
            self.btn_play.setText("Play")
            self.btn_play.setStyleSheet(f"background: {C_ACCENT}; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-size: 13px; font-weight: 600;")
        else:
            if self.pb_index >= len(self.points[0]) - 1:
                self.pb_index = 0
            self.pb_timer.start()
            self.pb_playing = True
            self.btn_play.setText("Pausa")
            self.btn_play.setStyleSheet(f"background: {C_RED}; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-size: 13px; font-weight: 600;")

    def _advance_playback_frame(self):
        speed_multiplier = int(self.combo_speed.currentText().replace("x", ""))
        self.pb_index += speed_multiplier

        if self.pb_index >= len(self.points[0]):
            self.pb_index = len(self.points[0]) - 1
            self.pb_timer.stop()
            self.pb_playing = False
            self.btn_play.setText("Play")
            self.btn_play.setStyleSheet(f"background: {C_ACCENT}; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-size: 13px; font-weight: 600;")

        self._update_playback_dot(self.pb_index)

    def _on_slider_moved(self, val):
        self.pb_index = val
        self._update_playback_dot(self.pb_index)

    def _update_playback_dot(self, index):
        if self.points and self.points[0] and 0 <= index < len(self.points[0]):
            p = self.points[0][index]
            self.pb_dot.set_data([p[0]], [p[1]])
            self.slider.blockSignals(True)
            self.slider.setValue(index)
            self.slider.blockSignals(False)
            self.pb_canvas.draw_idle()

    def _on_tab_changed(self, index):
        if hasattr(self, 'pb_playing') and self.pb_playing:
            if index != self.tabs.indexOf(self.pb_widget):
                self._toggle_playback()

    def _stop_and_restart(self):
        if hasattr(self, 'pb_timer') and self.pb_timer.isActive():
            self.pb_timer.stop()
        self.on_restart()

    def _save_result_image(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Salva immagine",
            str(DESKTOP / f"{self.session_name}_risultati.png"),
            "PNG (*.png);;JPEG (*.jpg)"
        )
        if not path:
            return

        fig = Figure(figsize=(18, 8), dpi=150)
        fig.patch.set_facecolor(C_BG)
        canvas = FigureCanvasAgg(fig)
        img = plt.imread(self.image_path)

        # 1. Gaze Path (Export)
        ax1 = fig.add_subplot(1, 2, 1)
        ax1.set_facecolor(C_BG)
        ax1.imshow(img, extent=[0, 1, 1, 0], aspect='auto')
        if self.points and any(self.points):
            if len(self.points) == 1:
                pts = self.points[0]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                ts = [p[2] for p in pts]
                dts = np.diff(ts, prepend=ts[0])
                rng = dts.max() - dts.min()
                sizes = ((dts - dts.min()) / rng * 600 + 40) if rng > 0 else np.full(len(ts), 80)
                ax1.plot(xs, ys, color='#4f8ef7', alpha=0.5, linewidth=1.5)
                ax1.scatter(xs, ys, s=sizes, c='#4f8ef7', alpha=0.55, edgecolors='white', linewidths=0.3)
                ax1.scatter(xs[0],  ys[0],  s=180, c='#2ecc71', edgecolors='white', linewidths=1.5, zorder=5)
                ax1.scatter(xs[-1], ys[-1], s=180, c='#e74c3c', edgecolors='white', linewidths=1.5, zorder=5)
            else:
                cmap = plt.get_cmap('tab10')
                for idx, pts in enumerate(self.points):
                    if not pts: continue
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    color = cmap(idx % 10)
                    ax1.plot(xs, ys, color=color, alpha=0.4, linewidth=1.2)
                    ax1.scatter(xs, ys, s=30, color=color, alpha=0.3)
                    ax1.scatter(xs[0],  ys[0],  s=60, c='#2ecc71', edgecolors='white', linewidths=0.6, zorder=5)
                    ax1.scatter(xs[-1], ys[-1], s=60, c='#e74c3c', edgecolors='white', linewidths=0.6, zorder=5)
        ax1.set_xlim(0, 1); ax1.set_ylim(1, 0)
        ax1.set_title("Gaze Path", color=C_TEXT, fontsize=15, pad=12)
        ax1.axis('off')

        # 2. Heatmap (Export)
        ax2 = fig.add_subplot(1, 2, 2)
        ax2.set_facecolor(C_BG)
        ax2.imshow(img, extent=[0, 1, 1, 0], aspect='auto', zorder=0)
        if self.points:
            all_xs = []
            all_ys = []
            for pts in self.points:
                all_xs.extend([p[0] for p in pts])
                all_ys.extend([p[1] for p in pts])
            if all_xs:
                xs = np.array(all_xs)
                ys = np.array(all_ys)
                h, _, _ = np.histogram2d(xs, ys, bins=80, range=[[[0,1],[0,1]]][0])
                h_smooth = gaussian_filter(h.T, sigma=3)
                ax2.imshow(h_smooth, extent=[0,1,1,0], origin='upper',
                           cmap='hot', alpha=0.6, aspect='auto', zorder=1)
        ax2.set_xlim(0, 1); ax2.set_ylim(1, 0)
        ax2.set_title("Heatmap", color=C_TEXT, fontsize=15, pad=12)
        ax2.axis('off')

        fig.suptitle(self.session_name, color=C_TEXT, fontsize=13, y=0.02)
        fig.tight_layout(pad=2)
        canvas.draw()
        fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=C_BG)
        QMessageBox.information(self, "Salvato", f"Immagine report aggregata salvata:\n{path}")
