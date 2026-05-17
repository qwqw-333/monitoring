#!/usr/bin/env python3
"""FusionPBX Prometheus Exporter — multi-target REST API scraper.

Connects to each FusionPBX server via HTTPS REST API and exposes the list
of provisioned extensions as Prometheus metrics. Supports multi-target pattern.

Usage:
    GET /probe?target=172.30.0.195  - scrape a specific FusionPBX instance
    GET /health                     - exporter health check
"""

import base64
import json
import logging
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "9725"))
FUSIONPBX_USER = os.environ.get("FUSIONPBX_USER", "admin")
FUSIONPBX_PASSWORD = os.environ.get("FUSIONPBX_PASSWORD", "")
FUSIONPBX_API_TOKEN = os.environ.get("FUSIONPBX_API_TOKEN", "")
API_TIMEOUT = int(os.environ.get("API_TIMEOUT", "15"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("fusionpbx_exporter")

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


# ---------------------------------------------------------------------------
# Prometheus text format builder (same pattern as freeswitch-exporter)
# ---------------------------------------------------------------------------

class MetricsBuilder:
    def __init__(self):
        self._metrics: dict[str, dict] = {}

    def gauge(self, name: str, help_text: str, value, labels: dict | None = None):
        if name not in self._metrics:
            self._metrics[name] = {"help": help_text, "type": "gauge", "samples": []}
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
# FusionPBX API client
# ---------------------------------------------------------------------------

def _auth_header() -> str:
    if FUSIONPBX_API_TOKEN:
        return f"Bearer {FUSIONPBX_API_TOKEN}"
    creds = base64.b64encode(f"{FUSIONPBX_USER}:{FUSIONPBX_PASSWORD}".encode()).decode()
    return f"Basic {creds}"


def _fetch_extensions(host: str) -> list[dict]:
    url = f"https://{host}/api/v2/extensions"
    req = urllib.request.Request(url, headers={"Authorization": _auth_header()})
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=API_TIMEOUT) as resp:
        data = json.loads(resp.read())

    if isinstance(data, list):
        return data
    # Handle wrapped responses: {"extensions": [...]} or {"data": [...]}
    for key in ("extensions", "data", "items", "results"):
        if key in data and isinstance(data[key], list):
            return data[key]

    raise ValueError(f"Unexpected API response shape: {type(data).__name__}")


# ---------------------------------------------------------------------------
# Metric collection
# ---------------------------------------------------------------------------

def collect_all(host: str) -> str:
    m = MetricsBuilder()
    start = time.monotonic()

    try:
        extensions = _fetch_extensions(host)
        count = 0
        for ext in extensions:
            ext_num = str(ext.get("extension", "") or "").strip()
            enabled = ext.get("enabled", "true")
            if not ext_num:
                continue
            if str(enabled).lower() not in ("true", "1", "yes", "enabled"):
                continue
            m.gauge(
                "fusionpbx_extension",
                "Extension provisioned in FusionPBX database (1=exists)",
                1,
                {"extension": ext_num},
            )
            count += 1

        m.gauge("fusionpbx_extensions_total", "Total enabled extensions in FusionPBX", count)
        m.gauge("fusionpbx_up", "FusionPBX API reachable (1=yes, 0=no)", 1)
        log.info("Scraped %s: %d extensions", host, count)

    except urllib.error.HTTPError as exc:
        log.error("HTTP %d from %s: %s", exc.code, host, exc.reason)
        m.gauge("fusionpbx_up", "FusionPBX API reachable (1=yes, 0=no)", 0)
    except Exception as exc:
        log.error("Scrape failed for %s: %s", host, exc)
        m.gauge("fusionpbx_up", "FusionPBX API reachable (1=yes, 0=no)", 0)

    m.gauge(
        "fusionpbx_scrape_duration_seconds",
        "Duration of FusionPBX API scrape in seconds",
        round(time.monotonic() - start, 4),
    )
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
            self._respond(404, "Use /probe?target=<host> or /health\n")

    def _handle_probe(self, parsed):
        params = parse_qs(parsed.query)
        target = params.get("target", [None])[0]
        if not target:
            self._respond(400, "Missing 'target' parameter\n")
            return
        # Strip port if present — we always use HTTPS/443
        host = target.split(":")[0] if ":" in target else target
        body = collect_all(host)
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
    log.info("FusionPBX API exporter listening on :%d", LISTEN_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    main()
