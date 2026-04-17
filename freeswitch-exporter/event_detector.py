#!/usr/bin/env python3
"""UMZ Registration Event Detector.

Tracks extension registrations on all UMZ servers. Detects OFFLINE, MIGRATE,
and REGISTER events. Pushes structured JSON events to stdout and Loki.
"""

import json
import logging
import os
import socket
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

ALL_UMZ = [
    ("172.30.0.195", 8021, "Kv UMZ"),
    ("172.30.2.195", 8021, "Lv UMZ"),
    ("172.30.4.195", 8021, "Dn UMZ"),
    ("172.30.8.195", 8021, "Od UMZ"),
]
ESL_PASSWORD = os.environ.get("FREESWITCH_ESL_PASSWORD", "ClueCon")
LOKI_URL = os.environ.get("LOKI_URL", "http://loki:3100/loki/api/v1/push")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "30"))
ESL_TIMEOUT = int(os.environ.get("ESL_TIMEOUT", "10"))


# ---------------------------------------------------------------------------
# logfmt logging
# ---------------------------------------------------------------------------

def logfmt_encode(fields: dict) -> str:
    """Encode dict to logfmt (key=value, quote values with spaces/special chars)."""
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
# ESL client
# ---------------------------------------------------------------------------

class ESLError(Exception):
    pass


def esl_get_registrations(host: str, port: int, password: str) -> dict[str, dict]:
    """Returns {reg_user: {network_ip, realm}} for all registered extensions."""
    s = socket.create_connection((host, port), timeout=ESL_TIMEOUT)
    buf = b""

    def read_msg():
        nonlocal buf
        while b"\n\n" not in buf:
            chunk = s.recv(16384)
            if not chunk:
                raise ESLError("Connection closed")
            buf += chunk
        end = buf.index(b"\n\n") + 2
        hdrs_raw = buf[:end]
        buf = buf[end:]
        hdrs = {}
        for line in hdrs_raw.decode("utf-8", errors="replace").strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                hdrs[k.strip().lower()] = v.strip()
        clen = int(hdrs.get("content-length", 0))
        while len(buf) < clen:
            chunk = s.recv(16384)
            if not chunk:
                break
            buf += chunk
        body = buf[:clen].decode("utf-8", errors="replace")
        buf = buf[clen:]
        return hdrs, body

    try:
        read_msg()  # auth/request
        s.sendall(f"auth {password}\n\n".encode())
        hdrs, _ = read_msg()
        if "+OK" not in hdrs.get("reply-text", ""):
            raise ESLError(f"Auth failed: {hdrs}")

        s.sendall(b"api show registrations as json\n\n")
        _, body = read_msg()

        data = json.loads(body.strip())
        result = {}
        for row in data.get("rows", []):
            user = row.get("reg_user", "")
            if user:
                result[user] = {
                    "network_ip": row.get("network_ip", ""),
                    "realm": row.get("realm", ""),
                }
        return result
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Loki push
# ---------------------------------------------------------------------------

def push_to_loki(level: str, event_type: str, server: str, message: str, fields: dict):
    ns = str(time.time_ns())
    # Exclude fields already present as stream labels to avoid duplication in Loki
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
# Event detection loop
# ---------------------------------------------------------------------------

def poll_all_servers() -> dict[str, dict[str, dict]]:
    """Returns {server_name: {reg_user: {network_ip, realm}}} for all UMZ servers."""
    result = {}
    for host, port, name in ALL_UMZ:
        try:
            result[name] = esl_get_registrations(host, port, ESL_PASSWORD)
        except Exception as e:
            log_event(logging.ERROR, f"Cannot reach {name}: {e}",
                      {"server": name, "error": str(e)})
            result[name] = None  # None = unreachable, skip diff for this server
    return result


def run():
    log_event(logging.INFO,
              f"Starting UMZ event detector — monitoring {len(ALL_UMZ)} servers, polling every {POLL_INTERVAL}s")

    prev_state: dict[str, dict | None] = {name: None for _, _, name in ALL_UMZ}
    initialized: set[str] = set()

    while True:
        curr_state = poll_all_servers()

        for _, _, server_name in ALL_UMZ:
            curr = curr_state.get(server_name)

            if curr is None:
                continue  # server unreachable, skip

            if server_name not in initialized:
                log_event(logging.INFO,
                          f"Initial state: {len(curr)} extensions on {server_name}",
                          {"server": server_name, "count": len(curr)})
                prev_state[server_name] = curr
                initialized.add(server_name)
                continue

            prev = prev_state[server_name]
            if prev is None:
                prev_state[server_name] = curr
                continue

            disappeared = {u: v for u, v in prev.items() if u not in curr}
            appeared = {u: v for u, v in curr.items() if u not in prev}

            # Build global view of where each user is NOW (across all reachable servers)
            all_regs_now: dict[str, str] = {}
            for other_name, other_regs in curr_state.items():
                if other_name != server_name and other_regs is not None:
                    for user in other_regs:
                        if user not in all_regs_now:
                            all_regs_now[user] = other_name

            # Build global view of where each user WAS (previous poll, across all servers)
            prev_global: dict[str, str] = {}
            for other_name, other_regs in prev_state.items():
                if other_regs is not None:
                    for user in other_regs:
                        if user not in prev_global:
                            prev_global[user] = other_name

            for user, info in disappeared.items():
                ip = info["network_ip"]
                if user in all_regs_now:
                    dest = all_regs_now[user]
                    msg = f"extension {user} migrated from {server_name} to {dest}"
                    log_event(logging.INFO, msg, {
                        "event": "migrated", "extension": user,
                        "from": server_name, "to": dest, "ip": ip,
                    })
                    push_to_loki("INFO", "migrate", server_name, msg, {
                        "extension": user, "from": server_name, "to": dest, "ip": ip,
                    })
                else:
                    msg = f"extension {user} unregistered from {server_name}"
                    log_event(logging.WARNING, msg, {
                        "event": "unregistered", "extension": user,
                        "server": server_name, "ip": ip,
                    })
                    push_to_loki("WARN", "offline", server_name, msg, {
                        "extension": user, "ip": ip,
                    })

            for user, info in appeared.items():
                ip = info["network_ip"]
                # Skip REGISTER if phone was on another UMZ last cycle — already covered by MIGRATE
                if prev_global.get(user, server_name) != server_name:
                    continue
                msg = f"extension {user} registered on {server_name}"
                log_event(logging.INFO, msg, {
                    "event": "registered", "extension": user,
                    "server": server_name, "ip": ip,
                })
                push_to_loki("INFO", "register", server_name, msg, {
                    "extension": user, "ip": ip,
                })

            prev_state[server_name] = curr

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
