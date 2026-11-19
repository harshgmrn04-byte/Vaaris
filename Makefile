.PHONY: setup verify test index eval bench-report demo
setup:
	uv sync --extra dev
verify:
	uv run --extra dev ruff check .
	uv run --extra dev mypy src
	uv run --extra dev pytest -q
test:
	uv run --extra dev pytest -q
index:
	uv run heirs index
eval:
	uv run heirs eval --split $(or $(SPLIT),dev)
bench-report:
	uv run heirs report
demo:
	uv run streamlit run src/heirs_navigator/app/main.py

