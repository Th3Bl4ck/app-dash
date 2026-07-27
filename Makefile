SRC := ../app-trading/scripts/dashboards

.PHONY: sync build icons serve

sync:            ## riallinea i generatori dalla fonte di verità (app-trading)
	cp $(SRC)/gen_daily_xau.py $(SRC)/gen_weekly.py generators/
	@echo "generatori risincronizzati da $(SRC)"

build:           ## rigenera public/
	python build.py

icons:           ## rigenera le icone PWA
	python tools/make_icons.py

serve: build     ## anteprima locale (senza gate password)
	python3 -m http.server -d public 8899
