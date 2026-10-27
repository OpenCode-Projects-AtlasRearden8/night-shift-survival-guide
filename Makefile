.PHONY: build test clean view

build:
	python3 build.py

test:
	python3 -m unittest discover -s tests -v

clean:
	rm -rf site

view: build
	@echo "Open site/index.html in your browser."
