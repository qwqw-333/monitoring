import logging
import time
import yaml

from prometheus_client import start_http_server

from workers import FreeSwitchWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

with open("config.yml") as f:
    CONFIG = yaml.safe_load(f)


def main():

    start_http_server(9180)

    workers = []

    for fs in CONFIG["freeswitches"]:

        worker = FreeSwitchWorker(
            fs,
            CONFIG["scrape_interval"]
        )

        worker.start()

        workers.append(worker)

    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
