# nfs-sync

Web app for one-way NFS folder syncing via rsync, with scheduled jobs and email alerts.

## Requirements

- Python ≥ 3.9
- `rsync` installed on the machine running this app
- Both NFS shares mounted as local paths on that machine

---

## Quick start (local / testing)

```bash
pip install git+https://github.com/nayanbera/nfs-sync.git
nfs-sync
```

Open http://localhost:5050 — default login is `admin` / `admin`.  
**Change the password immediately in Settings.**

---

## Running as a systemd service (Linux)

### 1. Install

```bash
pip install git+https://github.com/nayanbera/nfs-sync.git
```

If you prefer an isolated environment:

```bash
python3 -m venv /opt/nfs-sync-venv
/opt/nfs-sync-venv/bin/pip install git+https://github.com/nayanbera/nfs-sync.git
```

Then set `ExecStart=/opt/nfs-sync-venv/bin/nfs-sync` in the unit file below.

### 2. Install the systemd unit

Download the unit file from the repo and install it as a *template* unit
(the `@username` part tells systemd which user to run the service as — use
the account that has read access to the source NFS paths and write access to
the destination paths):

```bash
# Replace 'myuser' with the actual username
sudo curl -o /etc/systemd/system/nfs-sync@myuser.service \
  https://raw.githubusercontent.com/nayanbera/nfs-sync/main/deploy/nfs-sync.service

# Edit the file to set the correct ExecStart path if you used a venv:
sudo nano /etc/systemd/system/nfs-sync@myuser.service
```

### 3. Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nfs-sync@myuser
```

### 4. Check status and logs

```bash
sudo systemctl status nfs-sync@myuser
sudo journalctl -u nfs-sync@myuser -f
```

---

## Upgrading

All settings and history live in `~/.nfs-sync/` (outside the pip package), so
they survive upgrades automatically. The app also runs schema migrations on
startup, so new columns added in a release are applied to your existing
database without any manual steps.

```bash
pip install --upgrade git+https://github.com/nayanbera/nfs-sync.git
sudo systemctl restart nfs-sync@myuser
```

That's it — no data loss, no manual migration.

---

## Persistent data directory

Everything the app needs to persist lives in one directory:

| Path | Contents |
|---|---|
| `~/.nfs-sync/sync.db` | SQLite database — jobs, run history, SMTP and admin settings |
| `~/.nfs-sync/secret_key` | Auto-generated on first start; keeps login sessions valid across restarts |

To move the data directory (e.g. to `/var/lib/nfs-sync`), set the environment
variable in the systemd unit:

```ini
Environment=NFS_SYNC_DATA_DIR=/var/lib/nfs-sync
```

---

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `NFS_SYNC_HOST` | `0.0.0.0` | Bind address (`127.0.0.1` recommended behind a proxy) |
| `NFS_SYNC_PORT` | `5050` | Bind port |
| `NFS_SYNC_DATA_DIR` | `~/.nfs-sync/` | Directory for the database and secret key |
| `NFS_SYNC_DB_PATH` | `$NFS_SYNC_DATA_DIR/sync.db` | Full path to the SQLite file (overrides `DATA_DIR`) |
| `NFS_SYNC_SECRET_KEY` | *(auto-generated)* | Flask session secret — auto-persisted in `DATA_DIR/secret_key`; set this env var to override |

---

## Architecture notes

- **`workers = 1` (gunicorn)** — APScheduler's `BackgroundScheduler` runs inside
  the app process. Multiple workers would each spawn their own scheduler and
  fire jobs multiple times. The `nfs-sync` command enforces this automatically.
- **One-way sync only** — rsync flags are `-a --verbose --stats [--checksum]`
  with no `--delete`. Files are never removed from the destination.
- **Email alerts** — failure email is sent once per failure streak; a recovery
  email is sent when the job next succeeds. Configure SMTP in Settings.
