SRC_NAME := TFG_GII_IS911_2020
BUILD_DIR := build
LC := latexmk -synctex=1 -latexoption=-interaction=nonstopmode -file-line-error -latexoption=-shell-escape -xelatex --outdir=$(BUILD_DIR) $(SRC_NAME).tex

all: build

build: check
	$(LC)
	mv $(BUILD_DIR)/$(SRC_NAME).pdf .

view: check
	$(LC) --pvc

clean: check
	$(LC) -C

check: abstract.tex appendix.tex body.tex citations.tex cover.tex preamble.tex TFG_GII_IS911_2020.tex
