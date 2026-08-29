.PHONY: install test lint preflight dashboard deploy stop
install:
	python -m pip install -e '.[dev,ibkr]'
test:
	pytest -q
lint:
	ruff check .
preflight:
	./scripts/preflight.sh
dashboard:
	streamlit run app.py
deploy:
	./scripts/deploy_paper.sh
stop:
	./scripts/stop_production.sh

