import socket


class ESLError(Exception):
    pass


class ESLConnection:

    def __init__(self, host, port, password, timeout=5):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout

        self.sock = None
        self.buf = b""

    def connect(self):

        self.sock = socket.create_connection(
            (self.host, self.port),
            timeout=self.timeout
        )

        self.buf = b""

        headers, _ = self._read_message()

        if headers.get("content-type") != "auth/request":
            raise ESLError("invalid auth request")

        self.send(f"auth {self.password}\n\n")

        headers, _ = self._read_message()

        if "+OK" not in headers.get("reply-text", ""):
            raise ESLError("auth failed")

    def close(self):

        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

    def api(self, command):

        self.send(f"api {command}\n\n")

        _, body = self._read_message()

        return body

    def send(self, data):

        self.sock.sendall(
            data.encode()
        )

    def _read_message(self):

        while b"\n\n" not in self.buf:

            chunk = self.sock.recv(16384)

            if not chunk:
                raise ESLError("connection closed")

            self.buf += chunk

        header_end = self.buf.index(b"\n\n") + 2

        header_bytes = self.buf[:header_end]

        self.buf = self.buf[header_end:]

        headers = {}

        for line in header_bytes.decode().split("\n"):

            if ":" in line:
                k, v = line.split(":", 1)

                headers[k.strip().lower()] = v.strip()

        content_length = int(
            headers.get("content-length", "0")
        )

        while len(self.buf) < content_length:

            chunk = self.sock.recv(16384)

            if not chunk:
                break

            self.buf += chunk

        body = self.buf[:content_length].decode()

        self.buf = self.buf[content_length:]

        return headers, body
