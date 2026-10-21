import json
import logging
import os
import signal
import time
from uuid import uuid4

from app.database import SessionLocal
from app.jobs import process_due_jobs_once

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("taskflow.worker")
stopping = False


def _request_stop(_signum, _frame):
    global stopping
    stopping = True


def run() -> None:
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)
    worker_id = f"{os.environ.get('HOSTNAME', 'worker')}-{uuid4().hex[:8]}"
    logger.info(json.dumps({"event": "worker_started", "worker_id": worker_id}))
    while not stopping:
        did_work = process_due_jobs_once(SessionLocal, worker_id=worker_id)
        if not did_work:
            time.sleep(1)
    logger.info(json.dumps({"event": "worker_stopped", "worker_id": worker_id}))


if __name__ == "__main__":
    run()
