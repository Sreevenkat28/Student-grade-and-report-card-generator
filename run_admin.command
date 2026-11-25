#!/bin/bash
# Double-click (Mac) to run the app on THIS computer, with you as admin. Nothing here is deployed.
cd "$(dirname "$0")" || exit 1
[ -d .venv ] || python3 -m venv .venv || exit 1
echo "Checking requirements (the first run takes a few minutes)..."
.venv/bin/pip install -q -r requirements.txt || exit 1
mkdir -p .streamlit
# local testing only (git-ignored): show sign-up codes on screen so you can create test accounts without email
[ -f .streamlit/secrets.toml ] || printf "dev_show_code = true\n" > .streamlit/secrets.toml
[ -f .admin_device ] || .venv/bin/python make_admin.py || exit 1
exec .venv/bin/streamlit run streamlit_app.py --server.address localhost
