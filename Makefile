run:
	typecheck
	./venv/bin/python main.py

typecheck:
	./venv/bin/mypy --ignore-missing-imports main.py