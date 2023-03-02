# Mitwelten Data API

## Setup

```bash
python -m venv .venv
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
