#!/usr/bin/env python3
"""Spec Hunter USB — local web UI

Serves a dark, mobile-first page on http://127.0.0.1:8080 on the tested laptop:

  1. Shows the auto-collected hardware specs (from the device, not guessed)
  2. Takes the customer name
  3. Lists the manual tests the operator runs physically on this laptop:
        keyboard, display, sound, microphone, touchpad, ports
     each with Pass/Fail + a free-text failure point (e.g. "spacebar
     unresponsive", "dead pixel lower-left")
  4. On submit: uploads the full payload ({...specs, customer_name,
     test_results}) to the configured API, then powers the laptop off.
  5. Abort button: powers off WITHOUT uploading. Payload is written to
     /tmp/last_upload.json so nothing is lost.
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http import HTTPStatus
from pathlib import Path

logger = logging.getLogger("spec-hunter.ui")

HOST = "127.0.0.1"
PORT = 8080
UI_DIR = Path(__file__).parent
INDEX = (UI_DIR / "index.html").read_text()
RESULT_FILE = "/tmp/last_upload.json"


class Uploader:
    """Holds the payload + config; ties browser submit/abort to a blocking
    wait that main() can await."""

    def __init__(self, payload: dict, config, upload_fn):
        self.payload = payload
        self.config = config
        self.upload = upload_fn
        self.done = threading.Event()
        self.ok = False
        self.laptop_id = None

    def submit(self, customer_name: str, test_results: dict) -> dict:
        self.payload["customer_name"] = customer_name
        self.payload["test_results"] = test_results or {}
        result = self.upload(self.payload, self.config)
        self.laptop_id = result.get("laptopId")
        self.ok = True
        self.done.set()
        return result

    def abort(self) -> None:
        self.ok = False
        self.done.set()


def serve_ui(payload: dict, config, upload_fn, idle_timeout_s=300) -> Uploader:
    """Run the local UI (blocking) until submit or abort, then return.

    Idle timeout is a backstop so the machine still powers off if the
    operator walks away mid-session.
    """
    upl = Uploader(payload, config, upload_fn)

    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                body = INDEX.encode()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/state":
                self._send_json(HTTPStatus.OK, {"payload": upl.payload})
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def do_POST(self):
            if self.path != "/api/submit":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                return
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except json.JSONDecodeError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON"})
                return
            customer_name = data.get("customer_name", "")
            test_results = data.get("test_results", {})
            try:
                result = upl.submit(customer_name, test_results)
                self._send_json(HTTPStatus.OK, result)
            except Exception as exc:  # noqa: BLE001 — surface any upload error on-screen
                logger.error(f"Upload failed: {exc}")
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})

        def log_message(self, fmt, *args):
            logger.info(f"[ui] {fmt % args}")

    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    logger.info(f"=== UI ready: http://{HOST}:{PORT} ===")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    try:
        upl.done.wait(timeout=idle_timeout_s)
    finally:
        httpd.shutdown()
        httpd.server_close()

    if not upl.ok:
        # Operator aborted, upload failed, or idle timeout — keep the data.
        with open(RESULT_FILE, "w") as f:
            json.dump(upl.payload, f, indent=2)
        logger.warning(f"No upload — payload saved to {RESULT_FILE}")
    return upl