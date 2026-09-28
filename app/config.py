import os
import secrets

_data_dir = os.environ.get(
    "NFS_SYNC_DATA_DIR",
    os.path.join(os.path.expanduser("~"), ".nfs-sync"),
)
os.makedirs(_data_dir, exist_ok=True)


def _load_secret_key():
    """Return a persistent secret key, generating one on first run."""
    env_key = os.environ.get("NFS_SYNC_SECRET_KEY")
    if env_key:
        return env_key
    key_path = os.path.join(_data_dir, "secret_key")
    if os.path.exists(key_path):
        return open(key_path).read().strip()
    key = secrets.token_hex(32)
    with open(key_path, "w") as f:
        f.write(key)
    os.chmod(key_path, 0o600)
    return key


class Config:
    SECRET_KEY              = _load_secret_key()
    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///" + os.environ.get("NFS_SYNC_DB_PATH",
                                       os.path.join(_data_dir, "sync.db"))
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEMPLATES_AUTO_RELOAD          = True
