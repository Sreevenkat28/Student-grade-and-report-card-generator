"""Create the online-admin lines for Streamlit Secrets, on your own computer.

    python3 make_owner_key.py you@example.com

Writes .streamlit/owner_secrets.txt (git-ignored, readable only by you). An existing key is kept.
The key is never printed; open the file and paste its two lines into Streamlit -> Settings -> Secrets.
"""
import os
import secrets
import sys

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "owner_secrets.txt")

if os.path.exists(PATH):
    print("The key already exists in", PATH)
    sys.exit(0)
if len(sys.argv) != 2 or "@" not in sys.argv[1]:
    sys.exit("Usage: python3 make_owner_key.py you@example.com")
os.makedirs(os.path.dirname(PATH), exist_ok=True)
fd = os.open(PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as f:
    f.write(f'admin_email = "{sys.argv[1].strip().lower()}"\nadmin_key = "{secrets.token_urlsafe(32)}"\n')
print("Saved to", PATH)
