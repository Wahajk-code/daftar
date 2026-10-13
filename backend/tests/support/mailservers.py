"""Tiny local servers so the real mail transports run against real sockets: an SMTP server that keeps what it is
sent, and an HTTP server that stands in for Resend."""

import json
import socketserver
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


@dataclass
class SmtpInbox:
    port: int
    messages: list[str] = field(default_factory=list)
    envelopes: list[tuple[str, list[str]]] = field(default_factory=list)


class _SmtpHandler(socketserver.StreamRequestHandler):
    inbox: SmtpInbox

    def reply(self, line: str) -> None:
        self.wfile.write(line.encode() + b"\r\n")

    def handle(self) -> None:
        self.reply("220 test ESMTP")
        sender = ""
        recipients: list[str] = []
        while line := self.rfile.readline():
            command = line.decode().strip()
            verb = command.upper()
            if verb.startswith(("EHLO", "HELO")):
                self.reply("250 test")
            elif verb.startswith("MAIL FROM"):
                sender, recipients = command.split(":", 1)[1].strip(), []
                self.reply("250 ok")
            elif verb.startswith("RCPT TO"):
                recipients.append(command.split(":", 1)[1].strip())
                self.reply("250 ok")
            elif verb == "DATA":
                self.reply("354 go ahead")
                body: list[str] = []
                while (data := self.rfile.readline().decode()) != ".\r\n":
                    body.append(data)
                self.inbox.messages.append("".join(body))
                self.inbox.envelopes.append((sender, recipients))
                self.reply("250 queued")
            elif verb == "QUIT":
                self.reply("221 bye")
                return
            else:
                self.reply("250 ok")


@contextmanager
def smtp_server() -> Iterator[SmtpInbox]:
    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    server = Server(("127.0.0.1", 0), _SmtpHandler)
    inbox = SmtpInbox(port=server.server_address[1])
    _SmtpHandler.inbox = inbox
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield inbox
    finally:
        server.shutdown()
        server.server_close()


@dataclass
class ResendCalls:
    url: str
    status: int = 200
    requests: list[dict[str, Any]] = field(default_factory=list)


@contextmanager
def resend_server(status: int = 200) -> Iterator[ResendCalls]:
    calls = ResendCalls(url="", status=status)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            calls.requests.append(
                {
                    "path": self.path,
                    "headers": {key.lower(): value for key, value in self.headers.items()},
                    "json": json.loads(self.rfile.read(length) or b"{}"),
                }
            )
            ok = {"id": "49a3999c-0ce1-4ea6-ab68-afcd6dc2e794"}
            body = json.dumps(ok if calls.status < 300 else {"message": "refused"})
            self.send_response(calls.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    calls.url = f"http://127.0.0.1:{server.server_address[1]}/emails"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield calls
    finally:
        server.shutdown()
        server.server_close()
