# ML Backend API

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi "uvicorn[standard]"
```

Add credentials in `../credentials.py` (copy from [`../credentials_example.py`](../credentials_example.py))

## Running

```bash
source .venv/bin/activate
./.venv/bin/uvicorn main:app --reload
```
