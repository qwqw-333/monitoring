import logging
import threading
import time
import urllib.parse

from esl import ESLConnection
from state import State

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)

FS = [
    ("kyiv-1", "172.30.0.201", 8021, "ClueCon"),
    ("lviv-1", "172.30.2.201", 8021, "ClueCon"),
]

state = State()


def parse_event(body):

    result = {}

    for line in body.split("\n"):

        if ":" in line:

            k, v = line.split(":", 1)

            result[k.strip()] = urllib.parse.unquote(
                v.strip()
            )

    return result


def worker(name, host, port, password):

    while True:

        try:

            conn = ESLConnection(
                host,
                port,
                password
            )

            conn.connect()

            conn.send(
                "event plain CUSTOM "
                "sofia::register "
                "sofia::unregister\n\n"
            )

            logging.info(
                "%s connected",
                name
            )

            while True:

                headers, body = conn._read_message()

                if headers.get(
                    "content-type"
                ) != "text/event-plain":
                    continue

                event = parse_event(body)

                subclass = event.get(
                    "Event-Subclass",
                    ""
                )

                extension = event.get(
                    "from-user",
                    ""
                )

                if not extension:
                    continue

                if subclass == "sofia::register":

                    state.register(
                        name,
                        extension
                    )

                    logging.info(
                        "%s REGISTER %s",
                        name,
                        extension
                    )

                elif subclass == "sofia::unregister":

                    state.unregister(
                        name,
                        extension
                    )

                    logging.info(
                        "%s UNREGISTER %s",
                        name,
                        extension
                    )

        except Exception as e:

            logging.exception(
                "%s failed: %s",
                name,
                e
            )

            time.sleep(5)


def main():

    threads = []

    for item in FS:

        t = threading.Thread(
            target=worker,
            args=item,
            daemon=True
        )

        t.start()

        threads.append(t)

    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
