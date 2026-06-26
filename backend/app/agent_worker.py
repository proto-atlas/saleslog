import time

from app.agent.worker_queue import run_pending_agent_work_once

POLL_INTERVAL_SECONDS = 2


def main() -> None:
    while True:
        run_pending_agent_work_once()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
