import threading
import time

CACHE = {}
LOCK = threading.Lock()


def set_metrics(instance, metrics):
    with LOCK:
        CACHE[instance] = {
            "updated_at": time.time(),
            "metrics": metrics,
        }


def get_all_metrics():
    with LOCK:
        return dict(CACHE)
