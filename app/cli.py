"""Console-script entry point: `nfs-sync`."""
import os


def main():
    host = os.environ.get("NFS_SYNC_HOST", "0.0.0.0")
    port = int(os.environ.get("NFS_SYNC_PORT", "5050"))

    from app import create_app
    application = create_app()

    try:
        import gunicorn.app.base

        class _App(gunicorn.app.base.BaseApplication):
            def load_config(self):
                self.cfg.set("bind", f"{host}:{port}")
                # Must be 1 — APScheduler BackgroundScheduler must not fork.
                self.cfg.set("workers", 1)
                self.cfg.set("timeout", 3600)   # long-running rsync jobs
                self.cfg.set("accesslog", "-")

            def load(self):
                return application

        _App().run()
    except ImportError:
        # Fallback: Flask dev server (fine for local testing).
        application.run(host=host, port=port)
