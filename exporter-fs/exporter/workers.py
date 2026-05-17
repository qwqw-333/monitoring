import json
import logging
import threading
import time
import xml.etree.ElementTree as ET

from cache import set_metrics
from esl import ESLConnection
from metrics import *

log = logging.getLogger(__name__)


class FreeSwitchWorker(threading.Thread):

    def __init__(self, config, interval):

        super().__init__(daemon=True)

        self.config = config
        self.interval = interval

        self.name = config["name"]
        self.host = config["host"]
        self.port = config["port"]
        self.password = config["password"]

        self.conn = None

    def run(self):

        while True:

            try:

                self.collect()

            except Exception as e:

                log.exception(
                    "%s collect failed: %s",
                    self.name,
                    e
                )

                freeswitch_up.labels(
                    instance=self.name
                ).set(0)

            time.sleep(self.interval)

    def connect(self):

        if self.conn:
            return

        self.conn = ESLConnection(
            self.host,
            self.port,
            self.password
        )

        self.conn.connect()

    def collect(self):

        self.connect()

        freeswitch_up.labels(
            instance=self.name
        ).set(1)

        exporter_target_up.labels(
            instance=self.name
        ).set(1)

        self.collect_counts()
        self.collect_gateways()

        exporter_last_update.labels(
            instance=self.name
        ).set(time.time())

    def collect_counts(self):

        calls = self.json_count(
            "show calls count as json"
        )

        channels = self.json_count(
            "show channels count as json"
        )

        registrations = self.json_count(
            "show registrations count as json"
        )

        freeswitch_calls_active.labels(
            instance=self.name
        ).set(calls)

        freeswitch_channels_active.labels(
            instance=self.name
        ).set(channels)

        freeswitch_registrations_active.labels(
            instance=self.name
        ).set(registrations)

    def json_count(self, command):

        raw = self.conn.api(command)

        data = json.loads(raw)

        return int(
            data.get("row_count", 0)
        )

    def collect_gateways(self):

        raw = self.conn.api(
            "sofia xmlstatus gateway"
        )

        root = ET.fromstring(raw)

        for gw in root.findall(".//gateway"):

            name = gw.findtext("name", "")

            status = gw.findtext("status", "")

            up = 1 if status in (
                "UP",
                "REGED"
            ) else 0

            freeswitch_gateway_up.labels(
                instance=self.name,
                gateway=name
            ).set(up)
