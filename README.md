# Grade Generator

Student Grade & Report Card Generator. Enter subject marks and get the percentage, grade, pass/fail status and a report card.

- **Streamlit app:** `streamlit_app.py` (run with `pip install -r requirements.txt && streamlit run streamlit_app.py`)
- The Streamlit app uses passwordless login: sign up with email + username, then log in with a 6-digit code emailed to you (valid 10 min, 5 attempts, 30s resend limit).
- Set the email credentials in Streamlit Cloud -> App settings -> Secrets (see `.streamlit/secrets.toml.example`). For testing only, `dev_show_code = true` shows the code on screen instead of emailing it.
- Accounts are stored in a local SQLite file (`users.db`), which is NOT persistent on Streamlit Community Cloud: accounts reset when the app restarts.
- **Static web version (no login):** open `index.html` in a browser (uses `grading.js`, `app.js`, `style.css`)

Pass rule: at least 40% in every subject and overall.
Grades: A+ ≥90 · A ≥80 · B+ ≥70 · B ≥60 · C ≥50 · D ≥40 · F <40
