#!/usr/bin/env python3
"""One-command local web interface for LoomQ Agent."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

try:
    from .l2_agent.factory import create_agent
    from .run_l2 import (
        DEFAULT_ENV_FILE,
        load_environment,
        reexec_with_bundled_venv_if_needed,
        validate_ready,
    )
except ImportError:
    from l2_agent.factory import create_agent
    from run_l2 import (
        DEFAULT_ENV_FILE,
        load_environment,
        reexec_with_bundled_venv_if_needed,
        validate_ready,
    )


WEB_ROOT = Path(__file__).resolve().with_name("web")
MAX_REQUEST_BYTES = 64 * 1024


class WebApplication:
    """Application boundary kept separate from HTTP for straightforward tests."""

    def handle_chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        if len(prompt) > 12000:
            raise ValueError("prompt is too long")

        result = create_agent().execute(prompt.strip())
        response = asdict(result)
        response["display_text"] = self._display_text(response)
        return response

    @staticmethod
    def _display_text(result: Dict[str, Any]) -> str:
        english = result.get("response_language") == "en"
        if not result.get("ok"):
            return result.get("message") or (
                "The task could not be completed."
                if english
                else "暂时无法完成这个任务。"
            )
        if result.get("backend_id"):
            return result.get("explanation") or (
                "This backend satisfies the stated constraints."
                if english
                else "该后端满足你提出的条件。"
            )
        return result.get("explanation") or (
            "The circuit was generated and run successfully."
            if english
            else "电路已生成并成功运行。"
        )


class LoomQRequestHandler(BaseHTTPRequestHandler):
    app = WebApplication()

    def log_message(self, format_string, *args):
        # Keep the terminal useful without ever logging request bodies or keys.
        sys.stderr.write("[LoomQ Web] %s\n" % (format_string % args))

    def do_GET(self):
        path = urlparse(self.path).path
        relative = "index.html" if path == "/" else path.lstrip("/")
        if relative not in {"index.html", "styles.css", "app.js"}:
            self._json_error(HTTPStatus.NOT_FOUND, "not found")
            return
        file_path = WEB_ROOT / relative
        try:
            body = file_path.read_bytes()
        except OSError:
            self._json_error(HTTPStatus.NOT_FOUND, "not found")
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if urlparse(self.path).path != "/api/chat":
            self._json_error(HTTPStatus.NOT_FOUND, "not found")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json_error(HTTPStatus.BAD_REQUEST, "invalid content length")
            return
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._json_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "invalid request size")
            return
        try:
            payload = json.loads(self.rfile.read(length))
            response = self.app.handle_chat(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            self._json_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except Exception as exc:
            self._json_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "%s: %s" % (type(exc).__name__, exc),
            )
            return
        self._json_response(HTTPStatus.OK, response)

    def _json_error(self, status: HTTPStatus, message: str) -> None:
        self._json_response(status, {"ok": False, "error": message})

    def _json_response(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the LoomQ Agent web interface")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    configuration = load_environment(args.env_file)
    validate_ready(configuration)
    server = ThreadingHTTPServer((args.host, args.port), LoomQRequestHandler)
    url = "http://%s:%d" % (args.host, server.server_port)
    print("LoomQ Agent 网页已启动：%s" % url)
    print("按 Ctrl+C 停止。")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLoomQ Agent 网页已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    reexec_with_bundled_venv_if_needed()
    sys.exit(main())
