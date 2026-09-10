.PHONY: dev test build install

dev:
	uv venv
	uv pip install -e ".[test,build]"

test:
	uv run --no-sync python -m pytest

build:
	uv run --no-sync pyinstaller murmurai.spec -y

install: build
	rm -rf /Applications/murmurai.app
	cp -r dist/murmurai.app /Applications/
