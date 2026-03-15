# OOT

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg)](#tech-stack)
[![Docker Ready](https://img.shields.io/badge/Docker-ready-2496ED.svg)](#docker)
[![CI](https://img.shields.io/github/actions/workflow/status/StraussS/oot/ci.yml?branch=main)](https://github.com/StraussS/oot/actions/workflows/ci.yml)

> **Order of Things** — a Streamlit app for managing items, assets, invoices, and wishes.

OOT helps you answer a few simple questions clearly:

- What do I own?
- How much did it cost?
- What is still in use?
- What has been retired or sold?
- Where are the images and invoices?

It is designed for people who want a clean, local-first system to track digital devices, household equipment, subscriptions, collections, and wishlists.

---

## Highlights

- **Asset + wishlist management** in one place
- **Overview dashboard** with total value, daily cost, counts, and status breakdowns
- **Categories and tags** for flexible organization
- **Lifecycle status tracking**: active / retired / sold
- **Local image and invoice uploads** with replacement cleanup
- **Statistics and CSV export**
- **SQLite by default** — simple and local-first
- **Docker-ready** for easier deployment

## Screens and structure

- **Home** — overview, search, filters, item list
- **Wishlist** — lightweight wish tracking
- **Stats** — value and status analysis
- **Settings** — categories, tags, export
- **Sidebar create form** — quick entry for assets and wishes

## Tech stack

- Python 3.13
- Streamlit
- SQLite
- Docker / Docker Compose

## Project structure

```text
oot/
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── run.sh
├── update.sh
├── Makefile
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── docs/
│   ├── DEPLOYMENT.md
│   └── DEVELOPMENT.md
└── uploads/
```

## Quick start

### Local run

```bash
cd oot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.headless true --browser.gatherUsageStats false --server.address 0.0.0.0 --server.port 8502
```

Open: <http://localhost:8502>

### Docker

```bash
cd oot
docker compose up -d --build
```

Open: <http://localhost:8502>

### One-command start

```bash
cd oot
./run.sh
```

## Docker

### Direct run

```bash
cd oot
docker build -t oot .
docker run -d \
  --name oot-app \
  -p 8502:8502 \
  -v $(pwd)/data:/data \
  --restart unless-stopped \
  oot
```

### Persistent data

Mount these paths to keep your data:

- `./data` → `/data`

That preserves:
- uploaded images and invoices
- SQLite data between container rebuilds

Inside the container, OOT now uses:
- database: `/data/oot.db`
- uploads: `/data/uploads`


## Password protection

OOT supports a simple password gate for the whole app.

### Docker Compose

Set an environment variable before starting:

```bash
export OOT_PASSWORD='your-password'
docker compose up -d --build
```

### Docker run

```bash
docker run -d \
  --name oot-app \
  -p 8502:8502 \
  -e OOT_PASSWORD='your-password' \
  -v $(pwd)/data:/data \
  oot
```

If `OOT_PASSWORD` is empty, password protection is disabled.

## Common commands

### Start

```bash
./run.sh
```

### Update and rebuild

```bash
./update.sh
```

### Make targets

```bash
make run
make update
make logs
make stop
make restart
make check
```

## Data model

### Asset fields

- name
- price
- purchase date
- category
- tags
- status
- target cost
- note
- image
- invoice
- include in total assets
- include in daily cost
- expiry date / reminder
- sold price / sold date

### Wishlist fields

Kept intentionally lightweight:

- name
- price
- image
- note

## Export

OOT supports CSV export from the Settings page for:

- backup
- migration
- analysis

## Documentation

- [Deployment guide](docs/DEPLOYMENT.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Contributing guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Roadmap ideas

Potential future directions:

- theme switching
- richer statistics and charts
- import support
- stronger warranty / expiry reminders
- multi-user separation
- more complete invoice preview support

## License

MIT
