# Grade Generator

Student Grade & Report Card Generator. Enter subject marks and get the percentage, grade, pass/fail status and a report card.

- **Streamlit app:** `streamlit_app.py` (run with `pip install -r requirements.txt && streamlit run streamlit_app.py`)
- The Streamlit app: sign up with email + username + password (you're logged in right away), then log in with your username or email and password. "Forgot password?" emails a 6-digit code (valid 10 min) to reset it. After 5 wrong passwords an account is locked for 10 minutes.
- After sign-up it asks for your current and previous classes; the app has a Report card tab and a My classes tab.
- The reset email needs SMTP credentials in Streamlit Cloud -> App settings -> Secrets (see `.streamlit/secrets.toml.example`). For testing only, `dev_show_code = true` shows the code on screen instead of emailing it.
- Accounts are stored in a local SQLite file (`users.db`), which is NOT persistent on Streamlit Community Cloud: accounts reset when the app restarts.
- **Static web version (no login):** open `index.html` in a browser (uses `grading.js`, `app.js`, `style.css`)

Pass rule: at least 40% in every subject and overall.
Grades: A+ ≥90 · A ≥80 · B+ ≥70 · B ≥60 · C ≥50 · D ≥40 · F <40
