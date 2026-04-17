#!/usr/bin/env python3
"""FreeSWITCH Prometheus Exporter with multi-target support.

Connects to FreeSWITCH via ESL (mod_event_socket) and exposes metrics
in Prometheus text format. Supports the multi-target pattern via /probe endpoint,
similar to snmp_exporter or blackbox_exporter.

Usage:
    GET /probe?target=172.30.0.201:8021  - scrape a specific FreeSWITCH instance
    GET /health                          - exporter health check
"""

import json
import logging
import os
import re
import socket
import sys
import time
import xml.etree.ElementTree as ET
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "9724"))
ESL_PASSWORD = os.environ.get("FREESWITCH_ESL_PASSWORD", "ClueCon")
ESL_TIMEOUT = int(os.environ.get("ESL_TIMEOUT", "5"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("freeswitch_exporter")


# ---------------------------------------------------------------------------
# ESL client
# ---------------------------------------------------------------------------

class ESLError(Exception):
    pass


class ESLClient:
    """Minimal FreeSWITCH Event Socket Layer client."""

    def __init__(self, host: str, port: int, password: str, timeout: int = ESL_TIMEOUT):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._buf = b""

    # --- context manager ---
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()

    # --- connection ---
    def connect(self):
        self._sock = socket.create_connection(
            (self.host, self.port), timeout=self.timeout
        )
        self._buf = b""

        headers, _ = self._read_message()
        if headers.get("content-type") != "auth/request":
            raise ESLError(f"Expected auth/request, got: {headers}")

        self._send(f"auth {self.password}\n\n")

        headers, _ = self._read_message()
        reply = headers.get("reply-text", "")
        if "+OK" not in reply:
            raise ESLError(f"Auth failed: {reply}")

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    # --- commands ---
    def command(self, cmd: str) -> str:
        self._send(f"{cmd}\n\n")
        _, body = self._read_message()
        return body

    # --- low-level I/O ---
    def _send(self, data: str):
        self._sock.sendall(data.encode("utf-8"))

    def _read_message(self) -> tuple[dict, str]:
        while b"\n\n" not in self._buf:
            chunk = self._sock.recv(16384)
            if not chunk:
                raise ESLError("Connection closed")
            self._buf += chunk

        header_end = self._buf.index(b"\n\n") + 2
        header_bytes = self._buf[:header_end]
        self._buf = self._buf[header_end:]

        headers = {}
        for line in header_bytes.decode("utf-8", errors="replace").strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        content_length = int(headers.get("content-length", "0"))
        while len(self._buf) < content_length:
            chunk = self._sock.recv(16384)
            if not chunk:
                break
            self._buf += chunk

        body = self._buf[:content_length].decode("utf-8", errors="replace")
        self._buf = self._buf[content_length:]
        return headers, body


# ---------------------------------------------------------------------------
# Prometheus text format builder
# ---------------------------------------------------------------------------

class MetricsBuilder:
    """Builds Prometheus exposition format text, deduplicating HELP/TYPE."""

    def __init__(self):
        self._metrics: dict[str, dict] = {}

    def gauge(self, name: str, help_text: str, value, labels: dict | None = None):
        self._add(name, "gauge", help_text, value, labels)

    def counter(self, name: str, help_text: str, value, labels: dict | None = None):
        self._add(name, "counter", help_text, value, labels)

    def _add(self, name, mtype, help_text, value, labels):
        if name not in self._metrics:
            self._metrics[name] = {"help": help_text, "type": mtype, "samples": []}
        self._metrics[name]["samples"].append((labels or {}, value))

    def build(self) -> str:
        lines = []
        for name, info in self._metrics.items():
            lines.append(f"# HELP {name} {info['help']}")
            lines.append(f"# TYPE {name} {info['type']}")
            for labels, value in info["samples"]:
                if labels:
                    lbl = ",".join(f'{k}="{v}"' for k, v in labels.items())
                    lines.append(f"{name}{{{lbl}}} {value}")
                else:
                    lines.append(f"{name} {value}")
        lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Metric collectors
# ---------------------------------------------------------------------------

_STATUS_RE = re.compile(
    r"(\d+) session\(s\) since startup\s+"
    r"(\d+) session\(s\) - peak (\d+), last 5min (\d+)\s+"
    r"(\d+) session\(s\) per Sec out of max (\d+), peak (\d+), last 5min (\d+)\s+"
    r"(\d+) session\(s\) max\s+"
    r"min idle cpu ([\d.]+)/([\d.]+)"
)


def collect_status(esl: ESLClient, m: MetricsBuilder):
    raw = esl.command("api status")

    match = _STATUS_RE.search(raw)
    if match:
        m.counter("freeswitch_sessions_total", "Total sessions since startup", int(match.group(1)))
        m.gauge("freeswitch_sessions_active", "Active sessions", int(match.group(2)))
        m.gauge("freeswitch_sessions_peak", "Peak sessions since startup", int(match.group(3)))
        m.gauge("freeswitch_sessions_peak_5min", "Peak sessions last 5 minutes", int(match.group(4)))
        m.gauge("freeswitch_sps_current", "Current sessions per second", int(match.group(5)))
        m.gauge("freeswitch_sps_max", "Max sessions per second", int(match.group(6)))
        m.gauge("freeswitch_sps_peak", "Peak sessions per second", int(match.group(7)))
        m.gauge("freeswitch_sps_peak_5min", "Peak SPS last 5 minutes", int(match.group(8)))
        m.gauge("freeswitch_sessions_max", "Max sessions allowed", int(match.group(9)))
        m.gauge("freeswitch_cpu_idle_min", "Minimum CPU idle percentage", float(match.group(10)))
        m.gauge("freeswitch_cpu_idle", "Current CPU idle percentage", float(match.group(11)))


def collect_uptime(esl: ESLClient, m: MetricsBuilder):
    raw = esl.command("api uptime s").strip()
    try:
        m.gauge("freeswitch_uptime_seconds", "Uptime in seconds", int(raw))
    except ValueError:
        pass


def collect_json_count(esl: ESLClient, m: MetricsBuilder, command: str, metric_name: str, help_text: str):
    raw = esl.command(command).strip()
    try:
        data = json.loads(raw)
        m.gauge(metric_name, help_text, data.get("row_count", 0))
    except (json.JSONDecodeError, AttributeError):
        m.gauge(metric_name, help_text, 0)


def collect_sofia_profiles(esl: ESLClient, m: MetricsBuilder):
    raw = esl.command("api sofia xmlstatus")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return

    for profile in root.findall(".//profile"):
        name = profile.findtext("name", "")
        ptype = profile.findtext("type", "")
        state = profile.findtext("state", "")

        if ptype != "profile":
            continue

        running = 1 if "RUNNING" in state else 0
        m.gauge(
            "freeswitch_sofia_profile_up",
            "Sofia SIP profile status (1=RUNNING, 0=DOWN)",
            running,
            {"name": name},
        )


def collect_gateways(esl: ESLClient, m: MetricsBuilder):
    raw = esl.command("api sofia xmlstatus gateway")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return

    for gw in root.findall(".//gateway"):
        name = gw.findtext("name", "")
        profile = gw.findtext("profile", "")
        proxy = gw.findtext("proxy", "")
        status = gw.findtext("status", "")
        up = 1 if status in ("UP", "REGED") else 0

        labels = {"name": name, "profile": profile, "proxy": proxy}

        m.gauge("freeswitch_gateway_up", "Gateway status (1=UP, 0=DOWN)", up, labels)

        for field, metric, help_t in (
            ("calls-in", "freeswitch_gateway_calls_in_total", "Gateway inbound calls"),
            ("calls-out", "freeswitch_gateway_calls_out_total", "Gateway outbound calls"),
            ("failed-calls-in", "freeswitch_gateway_failed_calls_in_total", "Gateway failed inbound calls"),
            ("failed-calls-out", "freeswitch_gateway_failed_calls_out_total", "Gateway failed outbound calls"),
        ):
            try:
                m.counter(metric, help_t, int(gw.findtext(field, "0")), labels)
            except ValueError:
                pass

        try:
            ping_ms = float(gw.findtext("pingtime", "0"))
            m.gauge(
                "freeswitch_gateway_ping_seconds",
                "Gateway ping time in seconds",
                round(ping_ms / 1000, 4),
                labels,
            )
        except (ValueError, TypeError):
            pass


def collect_registrations_detail(esl: ESLClient, m: MetricsBuilder):
    raw = esl.command("api show registrations as json").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return
    for row in data.get("rows", []):
        reg_user = row.get("reg_user", "")
        realm = row.get("realm", "")
        network_ip = row.get("network_ip", "")
        if reg_user:
            m.gauge(
                "freeswitch_registration_active",
                "Extension registration presence (1=registered)",
                1,
                {"reg_user": reg_user, "realm": realm, "network_ip": network_ip},
            )


def collect_all(host: str, port: int, password: str) -> str:
    m = MetricsBuilder()
    start = time.monotonic()

    try:
        with ESLClient(host, port, password, timeout=ESL_TIMEOUT) as esl:
            collect_status(esl, m)
            collect_uptime(esl, m)
            collect_json_count(
                esl, m, "api show registrations count as json",
                "freeswitch_registrations_active", "Number of active registrations",
            )
            collect_registrations_detail(esl, m)
            collect_json_count(
                esl, m, "api show channels count as json",
                "freeswitch_channels_active", "Number of active channels",
            )
            collect_json_count(
                esl, m, "api show calls count as json",
                "freeswitch_calls_active", "Number of active calls",
            )
            collect_json_count(
                esl, m, "api show bridged_calls count as json",
                "freeswitch_bridged_calls", "Number of bridged calls",
            )
            collect_sofia_profiles(esl, m)
            collect_gateways(esl, m)
            m.gauge("freeswitch_up", "Whether FreeSWITCH is reachable (1=yes, 0=no)", 1)

    except Exception as e:
        log.error("Scrape failed for %s:%d — %s", host, port, e)
        m.gauge("freeswitch_up", "Whether FreeSWITCH is reachable (1=yes, 0=no)", 0)

    duration = time.monotonic() - start
    m.gauge("freeswitch_scrape_duration_seconds", "Scrape duration", round(duration, 4))
    return m.build()


# ---------------------------------------------------------------------------
# HTTP handler (multi-target pattern)
# ---------------------------------------------------------------------------

class ProbeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/probe":
            self._handle_probe(parsed)
        elif parsed.path == "/health":
            self._respond(200, "ok\n")
        else:
            self._respond(404, "Use /probe?target=host:port or /health\n")

    def _handle_probe(self, parsed):
        params = parse_qs(parsed.query)
        target = params.get("target", [None])[0]

        if not target:
            self._respond(400, "Missing 'target' parameter\n")
            return

        if ":" in target:
            host, port_str = target.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 8021
        else:
            host = target
            port = 8021

        password = params.get("password", [ESL_PASSWORD])[0]

        body = collect_all(host, port, password)
        self._respond(200, body, content_type="text/plain; version=0.0.4; charset=utf-8")

    def _respond(self, code: int, body: str, content_type: str = "text/plain"):
        encoded = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, fmt, *args):
        log.info(fmt, *args)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    server = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), ProbeHandler)
    log.info("FreeSWITCH exporter listening on :%d", LISTEN_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    main()
