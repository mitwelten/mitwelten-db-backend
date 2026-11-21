# Mitwelten Data API

## Setup

Requires Python 3.13.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Add credentials in `../credentials.py` (copy from [`../../credentials_example.py`](../../credentials_example.py))

## Running

```bash
source .venv/bin/activate
cd ..
api/.venv/bin/uvicorn api.main:app --reload
```

## Dependency Upgrade Procedure

The image only contains Python and the dependencies; the code in this directory
and `credentials.py` are mounted into the container at runtime (see
`docker/docker-compose.yaml`). Image and code therefore have to be updated together.

- [`requirements.in`](requirements.in): direct dependencies, edit this file when installing new packages
- [`requirements.txt`](requirements.txt): fully pinned lock file, generated from `requirements.in` (needs `uv`, see below)

1. Re-resolve all dependencies to their latest versions (for the Python version and platform of the image):

    ```bash
    uv pip compile requirements.in -o requirements.txt --python-version 3.13 --python-platform x86_64-manylinux_2_28 --upgrade
    ```

    To bump the Python version, change `FROM python:3.13-slim` in the [`Dockerfile`](Dockerfile) and `--python-version` above.

2. Test locally:

    ```bash
    python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
    cd .. && api/.venv/bin/uvicorn api.main:app --reload
    ```
