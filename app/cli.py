"""Console-script entry point: `nfs-sync`."""
import os


def main():
    host = os.environ.get("NFS_SYNC_HOST", "0.0.0.0")
    port = int(os.environ.get("NFS_SYNC_PORT", "5050"))

    from app import create_app
    application = create_app()
    application.run(host=host, port=port)
