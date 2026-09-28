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
                # workers=1 — APScheduler must not be forked across processes.
                # gthread worker allows multiple concurrent requests (e.g. SSE
                # streaming + normal page loads) within the single process.
                self.cfg.set("workers", 1)
                self.cfg.set("worker_class", "gthread")
                self.cfg.set("threads", 4)
                self.cfg.set("timeout", 3600)   # long-running rsync jobs
                self.cfg.set("accesslog", "-")

            def load(self):
                return application

        _App().run()
    except ImportError:
        # Fallback: Flask dev server (fine for local testing).
        application.run(host=host, port=port)
