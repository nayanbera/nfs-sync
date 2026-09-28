# APScheduler must run in a single process — do not increase workers.
workers = 1
bind = "0.0.0.0:5050"
timeout = 120
accesslog = "-"
errorlog = "-"
