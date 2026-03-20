.PHONY: build install

build:
	pyinstaller murmurai.spec -y

install: build
	rm -rf /Applications/murmurai.app
	cp -r dist/murmurai.app /Applications/
