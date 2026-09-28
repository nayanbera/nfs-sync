# nfs-sync

Web app for one-way NFS folder syncing via rsync, with scheduled jobs and email alerts.

## Install from GitHub

```bash
pip install git+https://github.com/nayanbera/nfs-sync.git
```

## Run

```bash
nfs-sync
```

Then open http://localhost:5050 — default login is `admin` / `admin`.  
**Change the password immediately in Settings.**

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `NFS_SYNC_DATA_DIR` | `~/.nfs-sync/` | Directory for the SQLite database |
| `NFS_SYNC_DB_PATH` | `$NFS_SYNC_DATA_DIR/sync.db` | Full path to the database file |
| `NFS_SYNC_SECRET_KEY` | `change-me-in-production` | Flask session secret — **set this in production** |
| `NFS_SYNC_HOST` | `0.0.0.0` | Bind address |
| `NFS_SYNC_PORT` | `5050` | Bind port |

## Production (gunicorn)

```bash
pip install gunicorn
NFS_SYNC_SECRET_KEY=<random> gunicorn "app:create_app()" -c gunicorn.conf.py
```

> `workers = 1` is required (APScheduler runs inside the app process).

## Requirements

- Python ≥ 3.9
- `rsync` installed on the machine running this app
- Both NFS shares mounted as local paths on that machine
