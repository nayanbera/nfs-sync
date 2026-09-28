import os

_data_dir = os.environ.get(
    "NFS_SYNC_DATA_DIR",
    os.path.join(os.path.expanduser("~"), ".nfs-sync"),
)
os.makedirs(_data_dir, exist_ok=True)


class Config:
    SECRET_KEY             = os.environ.get("NFS_SYNC_SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///" + os.environ.get("NFS_SYNC_DB_PATH",
                                       os.path.join(_data_dir, "sync.db"))
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEMPLATES_AUTO_RELOAD          = True
