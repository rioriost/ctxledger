test:
	pytest tests

test-cov:
	pytest --cov=src/ctxledger --cov-report=term-missing tests
