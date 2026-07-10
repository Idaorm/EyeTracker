import asyncio
import json
import logging
import threading
import queue
import time
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from cortex import Cortex

logging.getLogger("websockets").setLevel(logging.CRITICAL)

user = {
    "client_id":     "06YJd0lvRglzw2drwF9IVkYnCKkWBbB62PO7xE2S",
    "client_secret": "3mmP6JXp5ngK4tlKWThH78a0OvJtXIp0AQbQRRRIzc6wBvVJG0mw5LbgrBs3K5C1WReCHxUNqO2wK5x0trnU9WRj5t08ysWRgVdDbfsRkhmBReTlrWXRp5CnXcKmaB8p"
}

data_queue = queue.Queue()
connected_clients = set()


def _epoch_from_cortex(raw):
    """
    Estrae un timestamp epoch Unix (secondi, decimali) affidabile da un
    campione Cortex.
    """
    t = raw.get("time") if isinstance(raw, dict) else None
    if isinstance(t, (int, float)) and t > 1_000_000_000:  # sanity check: epoch plausibile (dopo il 2001)
        return float(t)
    return time.time()


def _readable(epoch):
    return datetime.fromtimestamp(epoch).strftime("%H:%M:%S.%f")[:-3]


class DataCollector:
    def __init__(self, user):
        self.c = Cortex(user["client_id"], user["client_secret"], debug_mode=False)
        self.c.bind(create_session_done=self.on_create_session_done)
        self.c.bind(new_data_labels=self.on_new_data_labels)
        self.c.bind(new_mot_data=self.on_new_mot_data)
        self.c.bind(new_met_data=self.on_new_met_data)
        self.c.bind(new_pow_data=self.on_new_pow_data)
        self.c.bind(inform_error=self.on_inform_error)
        #eventi del ciclo di vita del record e dei marker nativi Cortex.
        self.c.bind(create_record_done=self.on_create_record_done)
        self.c.bind(stop_record_done=self.on_stop_record_done)
        self.c.bind(inject_marker_done=self.on_inject_marker_done)

        self.mot_buffer = []
        self.met_buffer = []
        self.pow_buffer = []
        self.labels = {}
        self.last_mot = None

        
        self.marker_buffer = []
        self.current_marker = None

        # Tracciamento esplicito dell'ultima sessione di registrazione (basato
        # sui marker START_/STOP_)
        self.session_start_epoch = None
        self.session_end_epoch = None
        self.session_label = None

        
        self.record_id = None
        self.record_ready = threading.Event()
        self._pending_markers = []  

    def on_create_session_done(self, *args, **kwargs):
        print("Sessione creata. Avvio acquisizione dati...")
        self.c.sub_request(["mot", "met", "pow"])
        # apre subito un record Cortex, necessario per poter usare
        # injectMarker. Il titolo include un timestamp cosi' resta univoco
        # anche se il server gira a lungo con più sessioni eye-tracker.
        title = f"BrainWave_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.c.create_record(title)

    def on_create_record_done(self, *args, **kwargs):
        data = kwargs.get("data") or {}
        self.record_id = data.get("uuid") or data.get("id")
        print(f"  Record Cortex creato: {self.record_id}")
        self.record_ready.set()
        pending = list(self._pending_markers)
        self._pending_markers.clear()
        for label in pending:
            self._inject_marker_now(label)

    def on_stop_record_done(self, *args, **kwargs):
        print("  Record Cortex fermato.")
        self.record_ready.clear()
        self.record_id = None

    def on_inject_marker_done(self, *args, **kwargs):
        data = kwargs.get("data") or {}
        print(f"  [MARKER CONFERMATO DA CORTEX] {data}")

    def on_new_data_labels(self, *args, **kwargs):
        data = kwargs.get("data")
        self.labels[data["streamName"]] = data["labels"]
        print(f"  Etichette ricevute per: {data['streamName']}")

    def on_new_mot_data(self, *args, **kwargs):
        raw = kwargs.get("data")
        if raw:
            raw["_epoch"] = _epoch_from_cortex(raw)
            self.mot_buffer.append(raw)
            self.last_mot = raw

    def on_new_met_data(self, *args, **kwargs):
        raw = kwargs.get("data")
        if raw:
            raw["_epoch"] = _epoch_from_cortex(raw)
            raw["_marker"] = self.current_marker
            self.met_buffer.append(raw)
            data_queue.put(raw)

    def on_new_pow_data(self, *args, **kwargs):
        raw = kwargs.get("data")
        if raw:
            raw["_epoch"] = _epoch_from_cortex(raw)
            self.pow_buffer.append(raw)

    def on_inform_error(self, *args, **kwargs):
        print("Errore Cortex:", kwargs.get("error_data"))

    def start(self):
        self.c.open()

    def shutdown(self):
        """Chiusura controllata: ferma il record (se attivo) e chiude la connessione Cortex."""
        try:
            if self.record_ready.is_set():
                self.c.stop_record()
                time.sleep(0.3)  
        except Exception as e:
            print(f"Errore durante stop_record in shutdown: {e}")
        try:
            self.c.close() 
        except Exception as e:
            print(f"Errore durante la chiusura della connessione Cortex: {e}")

    def _inject_marker_now(self, label):
        """Invia davvero il marker a Cortex (richiede record_ready)."""
        epoch_ms = int(time.time() * 1000) 
        try:
            self.c.inject_marker_request(time=epoch_ms, value=1, label=label)
        except Exception as e:
            print(f"Errore durante inject_marker_request: {e}")
        return epoch_ms

    def set_marker(self, label):
        """
        Imposta il marker attivo e lo invia a Cortex tramite injectMarker.
        Se inizia una nuova sessione (START_), resetta i buffer dei dati.
        """
        self.current_marker = label if label else None

        if label:
            if self.record_ready.is_set():
                epoch_ms = self._inject_marker_now(label)
            else:
                self._pending_markers.append(label)
                epoch_ms = int(time.time() * 1000)
                print(f"  [MARKER] Record non ancora pronto, '{label}' messo in coda.")
        else:
            epoch_ms = int(time.time() * 1000)

        epoch = epoch_ms / 1000.0

        # Svuota i buffer all'inizio di una nuova sessione ===
        if label and label.startswith("START_"):
            self.mot_buffer.clear()
            self.met_buffer.clear()
            self.pow_buffer.clear()
            self.marker_buffer.clear()
            
            self.session_start_epoch = epoch
            self.session_end_epoch = None
            self.session_label = label[len("START_"):]
            print("\n  [INFO] Buffer svuotati: inizia una nuova sessione pulita.\n")
            
        elif label and label.startswith("STOP_"):
            self.session_end_epoch = epoch
        # =========================================================================

        entry = {
            "epoch": epoch,
            "time": _readable(epoch),
            "label": label or "—",
            "samples_at_set": len(self.met_buffer),
        }
        
        self.marker_buffer.append(entry)
        print(f"  [MARKER] {entry}")

        return entry

    def get_session_window(self):
        """Ritorna (start_epoch, end_epoch, label) dell'ultima sessione marcata."""
        return self.session_start_epoch, self.session_end_epoch, self.session_label

    def save_to_excel(self, filename=None):
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            desktop_path = Path.home() / "Desktop"
            filename = str(desktop_path / f"dati_emotiv_{ts}.xlsx")

        print(f"\nSalvataggio in corso → {filename} ...")
        saved = []

        try:
            snap_mot = list(self.mot_buffer)
            snap_met = list(self.met_buffer)
            snap_pow = list(self.pow_buffer)
            snap_markers = list(self.marker_buffer)

            mot_data = [(r["_epoch"], r["mot"]) for r in snap_mot]
            met_data = [(r["_epoch"], r["met"], r.get("_marker")) for r in snap_met]
            pow_data = [(r["_epoch"], r["pow"]) for r in snap_pow]

            with pd.ExcelWriter(filename, engine="openpyxl") as writer:

                info = pd.DataFrame({
                    "Info": [
                        "Data sessione", "Campioni mot", "Campioni met", "Campioni pow",
                        "Marker inseriti", "Sessione - inizio (epoch)", "Sessione - fine (epoch)",
                        "Sessione - etichetta", "Record Cortex ID",
                    ],
                    "Valore": [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        len(mot_data), len(met_data), len(pow_data), len(snap_markers),
                        self.session_start_epoch, self.session_end_epoch, self.session_label,
                        self.record_id,
                    ]
                })
                info.to_excel(writer, sheet_name="Sessione", index=False)

                if mot_data and "mot" in self.labels:
                    df = pd.DataFrame([item[1] for item in mot_data], columns=self.labels["mot"])
                    df.insert(0, "epoch", [item[0] for item in mot_data])
                    df.insert(1, "time", [_readable(item[0]) for item in mot_data])
                    df.to_excel(writer, sheet_name="Motion", index=False)
                    saved.append(f"Motion ({len(df)} righe)")

                if met_data and "met" in self.labels:
                    df = pd.DataFrame([item[1] for item in met_data], columns=self.labels["met"])
                    df.insert(0, "epoch", [item[0] for item in met_data])
                    df.insert(1, "time", [_readable(item[0]) for item in met_data])
                    df["marker"] = [item[2] if item[2] else "" for item in met_data]
                    df.to_excel(writer, sheet_name="Performance", index=False)
                    saved.append(f"Performance ({len(df)} righe)")

                if pow_data and "pow" in self.labels:
                    df = pd.DataFrame([item[1] for item in pow_data], columns=self.labels["pow"])
                    df.insert(0, "epoch", [item[0] for item in pow_data])
                    df.insert(1, "time", [_readable(item[0]) for item in pow_data])
                    df.to_excel(writer, sheet_name="BandPower", index=False)
                    saved.append(f"BandPower ({len(df)} righe)")

                if snap_markers:
                    df_m = pd.DataFrame(snap_markers, columns=["epoch", "time", "label", "samples_at_set"])
                    df_m.to_excel(writer, sheet_name="Markers", index=False)
                    saved.append(f"Markers ({len(df_m)} eventi)")

            print(f"✅ Salvato con successo in: {filename}")
            for s in saved:
                print(f"   • {s}")
            return filename

        except Exception as e:
            print(f"❌ Errore durante il salvataggio: {e}")
            return None


collector = DataCollector(user)


def run_cortex():
    collector.start()


threading.Thread(target=run_cortex, daemon=True).start()


async def handler(websocket):
    connected_clients.add(websocket)
    addr = websocket.remote_address
    print(f"[+] Browser connesso da {addr}")

    try:
        async for message in websocket:
            try:
                cmd = json.loads(message)
                action = cmd.get("action")

                if action == "save_excel":
                    loop = asyncio.get_running_loop()
                    filename = await loop.run_in_executor(None, collector.save_to_excel)
                    start_epoch, end_epoch, label = collector.get_session_window()
                    resp = {
                        "type": "save_result",
                        "success": filename is not None,
                        "filename": filename or "errore durante il salvataggio",
                        "rows": {
                            "mot": len(collector.mot_buffer),
                            "met": len(collector.met_buffer),
                            "pow": len(collector.pow_buffer),
                        },
                        "session_start_epoch": start_epoch,
                        "session_end_epoch": end_epoch,
                        "session_label": label,
                    }
                    await websocket.send(json.dumps(resp))

                elif action == "set_marker":
                    label = cmd.get("label", "")
                    entry = collector.set_marker(label)
                    resp = {
                        "type": "marker_result",
                        "label": label,
                        "active": bool(label),
                        "epoch": entry["epoch"],
                        "total_markers": len(collector.marker_buffer),
                    }
                    await websocket.send(json.dumps(resp))

                elif action == "get_session_window":
                    start_epoch, end_epoch, label = collector.get_session_window()
                    resp = {
                        "type": "session_window_result",
                        "session_start_epoch": start_epoch,
                        "session_end_epoch": end_epoch,
                        "session_label": label,
                    }
                    await websocket.send(json.dumps(resp))

            except json.JSONDecodeError:
                pass

    except ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[-] Browser disconnesso da {addr}")


async def broadcast_loop():
    global connected_clients
    while True:
        if not data_queue.empty() and connected_clients:
            raw = data_queue.get_nowait()
            if isinstance(raw, dict) and "met" in raw:
                met = raw["met"]
                if len(met) >= 11:
                    payload = {
                        "type": "data",
                        "epoch": raw.get("_epoch", time.time()),
                        "foc": round(max(0.0, min(100.0, float(met[1])  * 100)), 2),
                        "eng": round(max(0.0, min(100.0, float(met[3])  * 100)), 2),
                        "exc": round(max(0.0, min(100.0, float(met[5])  * 100)), 2),
                        "str": round(max(0.0, min(100.0, float(met[8])  * 100)), 2),
                        "rel": round(max(0.0, min(100.0, float(met[10]) * 100)), 2),
                        "session_samples": len(collector.met_buffer),
                        "active_marker": collector.current_marker or "",
                    }

                    if collector.last_mot and "mot" in collector.last_mot:
                        mot = collector.last_mot["mot"]
                        if len(mot) >= 10:
                            payload["mot"] = {
                                "q0":   round(float(mot[0]), 6),
                                "q1":   round(float(mot[1]), 6),
                                "q2":   round(float(mot[2]), 6),
                                "q3":   round(float(mot[3]), 6),
                                "accX": round(float(mot[4]), 4),
                                "accY": round(float(mot[5]), 4),
                                "accZ": round(float(mot[6]), 4),
                                "magX": round(float(mot[7]), 4),
                                "magY": round(float(mot[8]), 4),
                                "magZ": round(float(mot[9]), 4),
                            }

                    msg = json.dumps(payload)
                    dead = set()
                    for ws in connected_clients.copy():
                        try:
                            await ws.send(msg)
                        except Exception:
                            dead.add(ws)
                    connected_clients -= dead

        await asyncio.sleep(0.05)


async def main():
    print("=" * 50)
    print("  BrainWave Server v7 — Marker nativi Cortex + Record")
    print("  WebSocket : ws://localhost:8765")
    print("  Dashboard : http://localhost:8080/charts.html")
    print("=" * 50)

    async with serve(handler, "localhost", 8765):
        await broadcast_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nChiusura server — salvataggio automatico...")
        collector.save_to_excel()
        collector.shutdown()
        print("Arrivederci!")