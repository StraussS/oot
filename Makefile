run:
	./run.sh

update:
	./update.sh

logs:
	docker compose logs -f

stop:
	docker compose down

restart:
	docker compose down && docker compose up -d --build

check:
	python3 -m py_compile app.py
