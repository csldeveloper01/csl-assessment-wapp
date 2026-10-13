#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

echo "--- [1/3] Installing backend dependencies ---"
pip install --upgrade pip
pip install -r requirements.txt

echo "--- [2/3] Collecting static files with WhiteNoise ---"
python manage.py collectstatic --noinput

echo "--- [3/3] Running database migrations ---"
python manage.py migrate --noinput

echo "--- Build completed successfully ---"

python manage.py createsuperuser --noinput || true
