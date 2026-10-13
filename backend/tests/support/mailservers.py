"""A tiny local SMTP server, so the real mail transport runs against a real socket and keeps what it is sent."""

import socketserver
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


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
