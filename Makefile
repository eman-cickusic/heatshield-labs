.PHONY: setup api ui fmt lint test

setup:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

api:
	uvicorn src.api.main:app --reload --port 8000

ui:
	streamlit run app/streamlit_app.py

fmt:
	python -m pip install ruff black && ruff check --fix . && black .

