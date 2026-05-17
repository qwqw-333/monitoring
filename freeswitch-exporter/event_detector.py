#!/usr/bin/env python3
"""UMZ Registration Event Detector — real-time ESL event subscription.

Maintains persistent connections to all UMZ servers. Detects REGISTER,
OFFLINE, and MIGRATE events via sofia::register / sofia::unregister /
sofia::expire events. Pushes structured logfmt events to stdout and Loki.
"""

import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

ALL_UMZ = [
    ("172.30.0.195", 8021, "Kv UMZ"),
    ("172.30.2.195", 8021, "Lv UMZ"),
    ("172.30.4.195", 8021, "Dn UMZ"),
    ("172.30.8.195", 8021, "Od UMZ"),
]
ESL_PASSWORD            = os.environ.get("FREESWITCH_ESL_PASSWORD", "ClueCon")
LOKI_URL                = os.environ.get("LOKI_URL", "http://loki:3100/loki/api/v1/push")
ESL_TIMEOUT             = int(os.environ.get("ESL_TIMEOUT", "10"))
MIGRATE_BUFFER_SECONDS   = float(os.environ.get("MIGRATE_BUFFER_SECONDS", "3"))
MIGRATE_CONFIRM_SECONDS  = int(os.environ.get("MIGRATE_CONFIRM_SECONDS", "300"))
RECONNECT_DELAY          = int(os.environ.get("RECONNECT_DELAY", "5"))
RECONNECT_MAX_DELAY      = int(os.environ.get("RECONNECT_MAX_DELAY", "60"))


# ---------------------------------------------------------------------------
# logfmt logging — unchanged from original
# ---------------------------------------------------------------------------

def logfmt_encode(fields: dict) -> str:
    parts = []
    for k, v in fields.items():
        if v is None:
            continue
        s = str(v)
        if s == "" or any(c in s for c in ' "=\n\t'):
            s = '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
        parts.append(f"{k}={s}")
    return " ".join(parts)


class LogfmtFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname.replace("WARNING", "WARN")
        fields = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": level,
        }
        extra = getattr(record, "extra", {})
        fields.update(extra)
        fields["msg"] = record.getMessage()
        return logfmt_encode(fields)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(LogfmtFormatter())
log = logging.getLogger("umz_event_detector")
log.setLevel(logging.DEBUG)
log.addHandler(handler)
log.propagate = False


def log_event(level: int, message: str, extra: dict | None = None):
    record = log.makeRecord(log.name, level, "(detector)", 0, message, (), None)
    if extra:
        record.extra = extra
    log.handle(record)


# ---------------------------------------------------------------------------
# Loki push — unchanged from original
# ---------------------------------------------------------------------------

def push_to_loki(level: str, event_type: str, server: str, message: str, fields: dict):
    ns = str(time.time_ns())
    stream_keys = {"event_type", "level", "server", "job"}
    clean_fields = {k: v for k, v in fields.items() if k not in stream_keys}
    line = logfmt_encode({**clean_fields, "msg": message})
    stream = {"job": "umz-events", "event_type": event_type, "level": level, "server": server}
    payload = json.dumps({
        "streams": [{"stream": stream, "values": [[ns, line]]}]
    }).encode("utf-8")
    req = urllib.request.Request(
        LOKI_URL, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except urllib.error.URLError as e:
        log_event(logging.ERROR, f"Failed to push to Loki: {e}")


# ---------------------------------------------------------------------------
# Shared cross-thread state
# ---------------------------------------------------------------------------

class SharedState:
    """Thread-safe state: registrations + two deferred-event buffers.

    pending_offline : expire fired, phone not seen elsewhere → OFFLINE after MIGRATE_BUFFER_SECONDS
    pending_migrate : expire fired, phone already on other server → MIGRATE after MIGRATE_CONFIRM_SECONDS
                      (bounce is detected when the "to" server also fires expire before confirmation)

    Lock is never held across I/O. Each public method is one critical section.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # server_name → set of reg_user strings currently registered
        self.registrations: dict[str, set[str]] = {}
        # reg_user → (from_server, monotonic_timestamp, network_ip)
        self.pending_offline: dict[str, tuple[str, float, str]] = {}
        # reg_user → (from_server, to_server, monotonic_timestamp, network_ip)
        self.pending_migrate: dict[str, tuple[str, str, float, str]] = {}

    def set_snapshot(self, server: str, users: set[str]) -> None:
        """Replace registrations for server with a fresh snapshot.

        Prunes stale pending entries that originated from this server
        and are now confirmed as registered (events missed during reconnect gap).
        """
        with self._lock:
            self.registrations[server] = set(users)
            for d in (self.pending_offline, self.pending_migrate):
                stale = [u for u, entry in d.items() if entry[0] == server and u in users]
                for u in stale:
                    del d[u]

    def on_register(self, server: str, user: str, ip: str) -> tuple[str, str | None]:
        """Handle sofia::register. Returns (action, from_server).

        Actions:
          "migration_resolved" — expire already happened (pending_offline path)
          "new_register"       — phone not seen anywhere before
          "double_register"    — phone already on another server; wait for expire
          "reregister"         — same-server refresh; silent
        """
        with self._lock:
            # Expire-before-register path: pending_offline → confirmed migrate
            if user in self.pending_offline:
                from_server, _ts, _ip = self.pending_offline.pop(user)
                self.registrations.setdefault(server, set()).add(user)
                return "migration_resolved", from_server

            already_here = user in self.registrations.get(server, set())
            already_elsewhere = not already_here and any(
                user in regs
                for srv, regs in self.registrations.items()
                if srv != server
            )
            self.registrations.setdefault(server, set()).add(user)

            if already_here:
                return "reregister", None
            if already_elsewhere:
                # Double-registration: phone is on two servers simultaneously.
                # Suppress REGISTER — expire on old server will trigger MIGRATE
                # after MIGRATE_CONFIRM_SECONDS if phone stays on new server.
                return "double_register", None
            return "new_register", None

    def on_unregister(self, server: str, user: str, ip: str) -> None:
        """Handle sofia::unregister or sofia::expire.

        Routes to pending_migrate or pending_offline depending on whether
        the phone is already registered elsewhere. Detects bounces by
        checking if expire fires on the pending_migrate "to" server.
        """
        with self._lock:
            self.registrations.get(server, set()).discard(user)

            # Bounce detection: expire fired on the server we were migrating TO.
            # The phone left before MIGRATE_CONFIRM_SECONDS — it was a bounce.
            if user in self.pending_migrate and self.pending_migrate[user][1] == server:
                del self.pending_migrate[user]
                # Phone may now be on yet another server (re-registered elsewhere
                # during the bounce); if not, it goes to pending_offline below.
                if any(user in regs for regs in self.registrations.values()):
                    return  # still registered somewhere, no action needed
                self.pending_offline[user] = (server, time.monotonic(), ip)
                return

            # Check if phone is currently registered on another server
            other = next(
                (srv for srv, regs in self.registrations.items()
                 if srv != server and user in regs),
                None,
            )
            if other:
                # Phone already on another server: candidate for migration.
                # Wait for MIGRATE_CONFIRM_SECONDS before emitting MIGRATE.
                self.pending_migrate[user] = (server, other, time.monotonic(), ip)
            else:
                self.pending_offline[user] = (server, time.monotonic(), ip)

    def drain_expired_pending(self, cutoff: float) -> list[tuple[str, str, str]]:
        """Return and remove pending_offline entries older than cutoff.

        Skips users that are now registered anywhere (register-before-expire race).
        """
        result = []
        with self._lock:
            all_registered: set[str] = set()
            for users in self.registrations.values():
                all_registered.update(users)

            expired = [u for u, (_s, ts, _ip) in self.pending_offline.items()
                       if ts < cutoff]
            for u in expired:
                srv, _ts, ip = self.pending_offline.pop(u)
                if u not in all_registered:
                    result.append((u, srv, ip))
        return result

    def drain_confirmed_migrates(self, cutoff: float) -> list[tuple[str, str, str, str]]:
        """Return and remove pending_migrate entries older than cutoff.

        Only returns entries where the phone is still on the "to" server,
        confirming it was a real migration and not a bounce.
        Returns list of (user, from_server, to_server, ip).
        """
        result = []
        with self._lock:
            confirmed = [u for u, (_f, _t, ts, _ip) in self.pending_migrate.items()
                         if ts < cutoff]
            for u in confirmed:
                from_srv, to_srv, _ts, ip = self.pending_migrate.pop(u)
                if u in self.registrations.get(to_srv, set()):
                    result.append((u, from_srv, to_srv, ip))
        return result


# ---------------------------------------------------------------------------
# ESL client — persistent connection
# ---------------------------------------------------------------------------

class ESLError(Exception):
    pass


class ESLConnection:
    """Persistent FreeSWITCH ESL connection for event subscription."""

    def __init__(self, host: str, port: int, name: str, password: str, timeout: int):
        self.host = host
        self.port = port
        self.name = name
        self.password = password
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._buf = b""

    def connect(self) -> None:
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._sock.settimeout(None)  # switch to blocking after connect
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "TCP_KEEPIDLE"):
            self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        self._buf = b""

        hdrs, _ = self._read_message()
        if hdrs.get("content-type") != "auth/request":
            raise ESLError(f"Expected auth/request, got: {hdrs}")
        self._send(f"auth {self.password}\n\n")
        hdrs, _ = self._read_message()
        if "+OK" not in hdrs.get("reply-text", ""):
            raise ESLError(f"Auth failed: {hdrs}")

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def get_snapshot(self) -> dict[str, str]:
        """Return {reg_user: network_ip} for all currently registered extensions."""
        self._send("api show registrations as json\n\n")
        _, body = self._read_message()
        try:
            data = json.loads(body.strip())
        except json.JSONDecodeError:
            return {}
        result = {}
        for row in data.get("rows", []):
            user = row.get("reg_user", "")
            if user:
                result[user] = row.get("network_ip", "")
        return result

    def subscribe(self) -> None:
        self._send(
            "event plain CUSTOM sofia::register sofia::unregister sofia::expire\n\n"
        )
        hdrs, _ = self._read_message()
        if "+OK" not in hdrs.get("reply-text", ""):
            raise ESLError(f"Subscribe failed: {hdrs}")

    def read_event(self) -> dict[str, str] | None:
        """Block until one ESL message arrives. Returns parsed event dict or None."""
        hdrs, body = self._read_message()
        if hdrs.get("content-type") == "text/event-plain":
            return _parse_esl_event(body)
        return None  # command/reply, api/response, etc. — ignore

    def _send(self, data: str) -> None:
        self._sock.sendall(data.encode("utf-8"))

    def _read_message(self) -> tuple[dict[str, str], str]:
        """Read one ESL message: parse headers, then read Content-Length body."""
        while b"\n\n" not in self._buf:
            chunk = self._sock.recv(16384)
            if not chunk:
                raise ESLError("Connection closed by remote")
            self._buf += chunk

        header_end = self._buf.index(b"\n\n") + 2
        header_bytes = self._buf[:header_end]
        self._buf = self._buf[header_end:]

        hdrs: dict[str, str] = {}
        for line in header_bytes.decode("utf-8", errors="replace").strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                hdrs[k.strip().lower()] = v.strip()

        clen = int(hdrs.get("content-length", "0"))
        while len(self._buf) < clen:
            chunk = self._sock.recv(16384)
            if not chunk:
                break
            self._buf += chunk

        body = self._buf[:clen].decode("utf-8", errors="replace")
        self._buf = self._buf[clen:]
        return hdrs, body


def _parse_esl_event(body: str) -> dict[str, str]:
    """Parse URL-encoded key-value event body into a plain dict."""
    fields: dict[str, str] = {}
    for line in body.split("\n"):
        line = line.rstrip("\r")
        if not line:
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = urllib.parse.unquote(v.strip())
    return fields


# ---------------------------------------------------------------------------
# Event routing
# ---------------------------------------------------------------------------

def handle_event(state: SharedState, server_name: str, fields: dict[str, str]) -> None:
    subclass = fields.get("Event-Subclass", "")
    user = fields.get("from-user", "").strip()
    ip = fields.get("network-ip", fields.get("network-addr", "")).strip()

    if not user:
        return

    if subclass == "sofia::register":
        action, from_server = state.on_register(server_name, user, ip)
        if action == "migration_resolved":
            msg = f"extension {user} migrated from {from_server} to {server_name}"
            log_event(logging.INFO, msg, {
                "event": "migrated", "extension": user,
                "from": from_server, "to": server_name, "ip": ip,
            })
            push_to_loki("INFO", "migrate", server_name, msg, {
                "extension": user, "from": from_server, "to": server_name, "ip": ip,
            })
        elif action == "new_register":
            msg = f"extension {user} registered on {server_name}"
            log_event(logging.INFO, msg, {
                "event": "registered", "extension": user,
                "server": server_name, "ip": ip,
            })
            push_to_loki("INFO", "register", server_name, msg, {
                "extension": user, "ip": ip,
            })
        # "reregister" → routine re-registration of known user, suppress

    elif subclass in ("sofia::unregister", "sofia::expire"):
        state.on_unregister(server_name, user, ip)
        # OFFLINE is deferred to sweeper_thread to allow migration correlation


# ---------------------------------------------------------------------------
# Sweeper — emits OFFLINE and MIGRATE from deferred buffers
# ---------------------------------------------------------------------------

def sweeper_thread(state: SharedState) -> None:
    sleep_interval = max(0.5, MIGRATE_BUFFER_SECONDS / 2)
    while True:
        time.sleep(sleep_interval)
        now = time.monotonic()

        for user, server, ip in state.drain_expired_pending(now - MIGRATE_BUFFER_SECONDS):
            msg = f"extension {user} unregistered from {server}"
            log_event(logging.WARNING, msg, {
                "event": "unregistered", "extension": user,
                "server": server, "ip": ip,
            })
            push_to_loki("WARN", "offline", server, msg, {
                "extension": user, "ip": ip,
            })

        for user, from_srv, to_srv, ip in state.drain_confirmed_migrates(now - MIGRATE_CONFIRM_SECONDS):
            msg = f"extension {user} migrated from {from_srv} to {to_srv}"
            log_event(logging.INFO, msg, {
                "event": "migrated", "extension": user,
                "from": from_srv, "to": to_srv, "ip": ip,
            })
            push_to_loki("INFO", "migrate", to_srv, msg, {
                "extension": user, "from": from_srv, "to": to_srv, "ip": ip,
            })


# ---------------------------------------------------------------------------
# Per-server worker with reconnect
# ---------------------------------------------------------------------------

def server_worker(host: str, port: int, name: str, state: SharedState) -> None:
    delay = RECONNECT_DELAY
    while True:
        conn = ESLConnection(host, port, name, ESL_PASSWORD, ESL_TIMEOUT)
        try:
            conn.connect()
            log_event(logging.INFO, f"Connected to {name}", {"server": name})

            snapshot = conn.get_snapshot()
            state.set_snapshot(name, set(snapshot.keys()))
            log_event(logging.INFO,
                      f"Snapshot: {len(snapshot)} registrations on {name}",
                      {"server": name, "count": len(snapshot)})

            conn.subscribe()
            delay = RECONNECT_DELAY  # reset backoff on successful session

            while True:
                event = conn.read_event()
                if event:
                    handle_event(state, name, event)

        except (ESLError, OSError) as e:
            log_event(logging.ERROR,
                      f"Connection lost to {name}: {e} — reconnecting in {delay}s",
                      {"server": name, "error": str(e)})
        finally:
            conn.close()

        time.sleep(delay)
        delay = min(delay * 2, RECONNECT_MAX_DELAY)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    log_event(logging.INFO,
              f"Starting UMZ event detector — {len(ALL_UMZ)} servers, "
              f"migrate_buffer={MIGRATE_BUFFER_SECONDS}s, "
              f"migrate_confirm={MIGRATE_CONFIRM_SECONDS}s, "
              f"reconnect={RECONNECT_DELAY}-{RECONNECT_MAX_DELAY}s")

    state = SharedState()

    threads: list[threading.Thread] = []

    sweeper = threading.Thread(target=sweeper_thread, args=(state,), daemon=True, name="sweeper")
    threads.append(sweeper)

    for host, port, name in ALL_UMZ:
        t = threading.Thread(
            target=server_worker,
            args=(host, port, name, state),
            daemon=True,
            name=f"worker-{name}",
        )
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
