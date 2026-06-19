.PHONY: clean build

VERSION := $(shell python -c "import ast; tree=ast.parse(open('src/main.py','r',encoding='utf-8').read()); print([n.value.s for n in ast.walk(tree) if isinstance(n,ast.Assign) and hasattr(n.targets[0],'id') and n.targets[0].id=='__version__'][0])")

build:
	pyinstaller --onefile --windowed --name finance-$(VERSION) \
		src/main.py

clean:
	rm -rf dist/* build *.spec && echo Done.
