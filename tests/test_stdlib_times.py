"""Tests for the date/time and web standard-library rites
(godcode/stdlib_times.py): DATE_TODAY, TIME_NOW, FORMAT_DATE, HTTP_GET.

Every rite is exercised through the real interpreter, exactly as a
creation would call it. HTTP_GET is tested against a local server, so no
test depends on the public internet.
"""

import socket
import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from godcode import stdlib_times
from godcode.errors import GodRuntimeError, SandboxViolation
from godcode.interpreter import Interpreter
from godcode.sandbox import SandboxPolicy, apply_policy

BODY = "peace upon the web"


def run_creation(*lines):
    """Run God Code lines through a real interpreter; return REVEAL output."""
    source = "BEGIN CREATION\n" + "\n".join(lines) + "\nEND CREATION\n"
    interp = Interpreter(log_path=None)
    stdlib_times.register(interp)
    interp.run_source(source)
    return interp.output


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = BODY.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep test output quiet
        pass


@pytest.fixture()
def local_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        thread.join()


def _closed_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_date_today_matches_python():
    out = run_creation("REVEAL(DATE_TODAY())")
    assert out == [date.today().isoformat()]


def test_date_today_takes_no_arguments():
    with pytest.raises(GodRuntimeError):
        run_creation('REVEAL(DATE_TODAY("extra"))')


def test_time_now_parses_as_datetime():
    out = run_creation("REVEAL(TIME_NOW())")
    stamp = datetime.fromisoformat(out[0])
    assert abs((datetime.now().astimezone() - stamp).total_seconds()) < 60


def test_format_date_weekday():
    out = run_creation('REVEAL(FORMAT_DATE("2026-09-24", "%A"))')
    assert out == ["Thursday"]


def test_format_date_full_pattern():
    out = run_creation('REVEAL(FORMAT_DATE("2026-09-24", "%Y/%m/%d"))')
    assert out == ["2026/09/24"]


def test_format_date_bad_date_raises():
    with pytest.raises(GodRuntimeError) as exc:
        run_creation('REVEAL(FORMAT_DATE("not-a-date", "%A"))')
    assert "FORMAT_DATE" in str(exc.value)


def test_format_date_non_word_date_raises():
    with pytest.raises(GodRuntimeError):
        run_creation('REVEAL(FORMAT_DATE(42, "%A"))')


def test_http_get_local_server(local_server):
    out = run_creation(f'REVEAL(HTTP_GET("{local_server}/hello"))')
    assert out == [BODY]


def test_http_get_unroutable_raises_cleanly_and_quickly():
    port = _closed_port()  # refused at once: never hangs
    with pytest.raises(GodRuntimeError) as exc:
        run_creation(f'REVEAL(HTTP_GET("http://127.0.0.1:{port}/"))')
    assert "HTTP_GET" in str(exc.value)


def test_http_get_non_word_url_raises():
    with pytest.raises(GodRuntimeError):
        run_creation("REVEAL(HTTP_GET(42))")


def test_http_get_denied_under_strict_sandbox():
    interp = Interpreter(log_path=None)
    stdlib_times.register(interp)
    apply_policy(interp, SandboxPolicy.strict())
    with pytest.raises(SandboxViolation) as exc:
        interp.run_source(
            "BEGIN CREATION\n"
            'REVEAL(HTTP_GET("http://127.0.0.1:1/"))\n'
            "END CREATION\n"
        )
    assert "HTTP_GET" in str(exc.value)


def test_http_get_allowed_when_network_granted(local_server):
    interp = Interpreter(log_path=None)
    stdlib_times.register(interp)
    policy = SandboxPolicy.strict()
    policy.allow_network = True
    apply_policy(interp, policy)
    interp.run_source(
        "BEGIN CREATION\n"
        f'REVEAL(HTTP_GET("{local_server}/hello"))\n'
        "END CREATION\n"
    )
    assert interp.output == [BODY]
