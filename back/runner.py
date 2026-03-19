import subprocess
import sys

import uvicorn


def dev() -> None:
    uvicorn.run("back.main:app", host="127.0.0.1", port=8000, reload=True)


def start() -> None:
    uvicorn.run("back.main:app", host="0.0.0.0", port=8000)


def celery_worker() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "back.celery_app:celery_app",
            "worker",
            "--loglevel=info",
            "--pool=solo",
        ],
        check=True,
    )


def celery_beat() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "back.celery_app:celery_app",
            "beat",
            "--loglevel=info",
        ],
        check=True,
    )
