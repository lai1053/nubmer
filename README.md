# nubmer

PK10 research and live-operations workbench. This repository now contains the deployable source for the current remote services, plus older research archives for review.

## Services

| Path | Public port | Backend | Purpose |
| --- | ---: | --- | --- |
| `pk10_live_dashboard/` | `5173` | FastAPI `127.0.0.1:18080` + React/Vite static frontend | JSSC/PK10 live dashboard, login, user admin, login logs, bet/broadcast/history APIs |
| `jsft_pk10/` | `5174` | FastAPI `127.0.0.1:18084` | JSFT shadow dashboard and history updater |
| `PK10_ARCHIVE_20260420/` | none | archive | Earlier research code, docs, and database exports |

The current production host inventory is tracked in `REMOTE_PORTS.md`.

## Server Quick Start

Default server layout:

```text
/root/pk10/nubmer                 cloned Git repository
/root/pk10/pk10_live_dashboard    runtime copy for port 5173
/root/jsft_pk10                   runtime copy for port 5174
/var/www/pk10-live                static frontend root for port 5173
```

Clone on a server:

```bash
mkdir -p /root/pk10
cd /root/pk10
git clone git@github.com:lai1053/nubmer.git
cd nubmer
```

Install common runtime tools:

```bash
sudo bash scripts/bootstrap_server.sh
```

Deploy the 5173 live dashboard:

```bash
sudo bash scripts/deploy_5173_pk10_live.sh
```

Deploy the 5174 JSFT shadow service:

```bash
sudo bash scripts/deploy_5174_jsft_shadow.sh
```

Check both services:

```bash
bash scripts/check_services.sh
```

## Configuration

The deploy scripts create example config files only when missing:

- 5173: `/root/pk10/.env`, based on `pk10_live_dashboard/backend/.env.example`
- 5174: `/root/jsft_pk10/.env`, based on `jsft_pk10/.env.example`

Edit those files on the server before relying on the services. They define database connection details, ports, admin bootstrap credentials, strategy IDs, and runtime paths.

## Local Development

5173 backend:

```bash
cd pk10_live_dashboard/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 18080
```

5173 frontend:

```bash
cd pk10_live_dashboard/frontend
npm ci
npm run dev
```

5174 backend:

```bash
cd jsft_pk10
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 18084
```

## Build And Verification

Common checks before committing:

```bash
python3 -m py_compile jsft_pk10/app.py jsft_pk10/update_jsft_history.py
python3 -m compileall -q pk10_live_dashboard/backend/app
npm --prefix pk10_live_dashboard/frontend ci
npm --prefix pk10_live_dashboard/frontend run build
bash -n scripts/*.sh
```

On the server after deployment:

```bash
curl http://127.0.0.1:18080/api/health
curl http://127.0.0.1:18084/api/health
curl -I http://127.0.0.1:5173/
curl -I http://127.0.0.1:5174/
```

## Documentation

- `docs/DEPLOYMENT.md`: server deployment and rollback notes.
- `docs/ARCHITECTURE.md`: service map, runtime layout, and data flow.
- `pk10_live_dashboard/README.md`: 5173 application details and API reference.
- `jsft_pk10/README.md`: 5174 application details.
- `pk10_live_dashboard/PROJECT_MEMORY.md`: handoff notes for future threads.

## Git Workflow

The canonical repository is:

```text
git@github.com:lai1053/nubmer.git
```

Commit source, docs, example config, nginx templates, PM2 ecosystem files, and small review artifacts. Do not commit runtime `.env` files, virtualenvs, `node_modules`, built `dist`, logs, process state, or generated cache files.
