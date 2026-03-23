# Deployment snippets

Example configs for running Trace with Gunicorn, Celery, and Nginx on Ubuntu.

1. Copy files into `/etc/systemd/system/` and adjust paths (WorkingDirectory, EnvironmentFile, user/group).
2. Enable services:
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now gunicorn.service`
   - `sudo systemctl enable --now celery-worker.service`
   - `sudo systemctl enable --now celery-beat.service`
3. Place `nginx.conf` into `/etc/nginx/sites-available/trace` and symlink to `sites-enabled`, then `sudo nginx -t && sudo systemctl reload nginx`.
4. Environment expectations:
   - `/opt/trace/.env` contains Flask, database, Redis, and Razorpay credentials.
   - Pricing env vars (rupees): `RAZORPAY_MONTHLY_PRICE_INR=499` and `RAZORPAY_ANNUAL_PRICE_INR=4999` (converted to paise automatically).
   - Virtualenv at `/opt/trace/venv` with project dependencies installed.
5. Logs: check `journalctl -u gunicorn.service -f` (similarly for Celery) and `/var/log/nginx/` for proxy logs.
