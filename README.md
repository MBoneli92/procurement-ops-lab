# procurement-ops-lab

Mini servico de procurement em Python (FastAPI) para estudar SAP BTP DevOps.

## Rodar local
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload    # http://127.0.0.1:8000/docs
pytest --cov=app
ruff check . && ruff format --check .
```
