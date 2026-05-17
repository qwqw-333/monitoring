import threading


class State:

    def __init__(self):

        self.lock = threading.Lock()

        self.registrations = {}

    def register(
        self,
        server,
        extension
    ):

        with self.lock:

            self.registrations.setdefault(
                server,
                set()
            ).add(extension)

    def unregister(
        self,
        server,
        extension
    ):

        with self.lock:

            self.registrations.get(
                server,
                set()
            ).discard(extension)
