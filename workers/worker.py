"""Standalone worker process — polls the durable job queue and runs pipeline
jobs. The API also runs an in-process worker thread, so this process is only
needed when you want to scale processing independently (docker-compose runs
one)."""

import logging
import time

from app.db import init_db
from app.services.jobs import work_once

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("worker")


def main() -> None:
    init_db()
    log.info("worker started")
    while True:
        try:
            if not work_once():
                time.sleep(1.0)
        except KeyboardInterrupt:
            break
        except Exception:
            log.exception("worker loop error")
            time.sleep(2.0)


if __name__ == "__main__":
    main()
