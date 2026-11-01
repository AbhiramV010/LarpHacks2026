"""UDP link to the Uno Q: commands out on 5005, events in on 5006, PING/PONG health."""
import logging
import queue
import socket
import threading
import time
import config

log = logging.getLogger("link")


class Link:
    def __init__(self):
        self.events = queue.Queue()
        self.up = False
        self._missed = 0
        self._addr = None
        self._warned = False
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("0.0.0.0", config.LAPTOP_EVENT_PORT))
        self._sock.settimeout(0.5)
        self._resolve()
        threading.Thread(target=self._recv_loop, daemon=True).start()
        threading.Thread(target=self._ping_loop, daemon=True).start()

    def _resolve(self):
        try:
            self._addr = (socket.gethostbyname(config.UNOQ_HOST), config.UNOQ_PORT)
            log.info("Uno Q at %s:%d", *self._addr)
        except socket.gaierror:
            if not self._warned:
                log.error("Cannot resolve %s. Set UNOQ_HOST to the board's IP in config.py.", config.UNOQ_HOST)
                self._warned = True

    def send(self, cmd):
        if not self._addr:
            return
        try:
            self._sock.sendto(cmd.encode("utf-8"), self._addr)
        except OSError as e:
            log.debug("send failed: %s", e)

    def _recv_loop(self):
        while True:
            try:
                data, _ = self._sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                continue
            text = data.decode("utf-8", "replace").strip()
            if text == "PONG":
                self._missed = 0
                if not self.up:
                    log.info("Uno Q is up")
                self.up = True
            else:
                self.events.put(text)

    def _ping_loop(self):
        while True:
            if not self._addr:
                self._resolve()
            self._missed += 1
            if self._missed > 3 and self.up:
                log.warning("Uno Q is down")
                self.up = False
            self.send("PING")
            time.sleep(5)
