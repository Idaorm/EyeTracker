import threading
import time
import json
import websocket

def _run_with_hard_timeout(func, timeout_seconds, fallback_value):
    result_box = {"value": fallback_value, "done": False}

    def target():
        try:
            result_box["value"] = func()
        except Exception as e:
            print(f"[hard_timeout] Eccezione nella funzione eseguita: {e}")
        finally:
            result_box["done"] = True

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout=timeout_seconds)
    return result_box["value"]

def sync_emotiv(label_name):
    sent_epoch = time.time()
    def _do_send():
        ws = websocket.create_connection("ws://localhost:8765", timeout=2)
        ws.send(json.dumps({"action": "set_marker", "label": label_name}))
        raw_resp = ws.recv()
        ws.close()
        resp = json.loads(raw_resp)
        server_epoch = resp.get("epoch")
        return server_epoch if server_epoch is not None else sent_epoch

    result = _run_with_hard_timeout(_do_send, timeout_seconds=5, fallback_value=None)
    return result if result is not None else sent_epoch

def save_emotiv_data():
    fallback = {"filename": None, "session_start_epoch": None, "session_end_epoch": None}
    def _do_save():
        ws = websocket.create_connection("ws://localhost:8765", timeout=20)
        ws.send(json.dumps({"action": "save_excel"}))
        result = ws.recv()
        ws.close()
        resp = json.loads(result)
        if resp.get("type") == "save_result" and resp.get("success"):
            return {
                "filename": resp.get("filename"),
                "session_start_epoch": resp.get("session_start_epoch"),
                "session_end_epoch": resp.get("session_end_epoch"),
            }
        return fallback

    return _run_with_hard_timeout(_do_save, timeout_seconds=25, fallback_value=fallback)