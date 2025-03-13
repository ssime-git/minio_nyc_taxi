# clean __pycache__ files
clean:
	find . -name "__pycache__" -type d -exec rm -rf {} +
