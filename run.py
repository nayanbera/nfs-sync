"""Development entry point. For production use gunicorn (see gunicorn.conf.py)."""
from app.cli import main

if __name__ == "__main__":
    main()
