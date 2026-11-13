# Grade Generator

Student Grade & Report Card Generator. Enter subject marks and get the percentage, grade, pass/fail status and a report card.

- **Streamlit app:** `streamlit_app.py` (run with `pip install -r requirements.txt && streamlit run streamlit_app.py`)
- The Streamlit app: sign up with email + username + password, then enter the 6-digit code emailed to you to confirm your email (the account is created and you're logged in once it's confirmed), then log in with your username or email and password. "Forgot password?" emails a 6-digit code (valid 10 min) to reset it.
- After sign-up it asks for your current and previous classes. Tabs: **Report card** (show grades as letters, percentages or both; your choice is remembered), **GPA** (unweighted + weighted on the standard 4.0 scale; enter grades as letters or percentages), **Grading rules** (edit report-card grade cut-offs and pass marks, plus the whole GPA scale: points per grade, percentage cut-offs and weighted bonuses per course level), **My classes**, **Account** (change password / email, send a test email, delete account).
- Codes are emailed from your own Gmail through a Google Apps Script (`apps_script/Code.gs`, setup steps are in its header) or via SMTP. Put the settings in Streamlit Cloud -> App settings -> Secrets (see `.streamlit/secrets.toml.example`). Addresses are checked before sending: format, disposable-mail domains, common typos (gmial.com) and DNS (the domain must accept mail). For testing only, `dev_show_code = true` shows the code on screen instead of emailing it.
- Accounts are stored in a local SQLite file (`users.db`), which is NOT persistent on Streamlit Community Cloud: accounts reset when the app restarts.
- **Static web version (no login):** open `index.html` in a browser (uses `grading.js`, `app.js`, `style.css`)

Pass rule: at least 40% in every subject and overall.
Grades: A+ ≥90 · A ≥80 · B+ ≥70 · B ≥60 · C ≥50 · D ≥40 · F <40

## Admin (this device only)
Run `python3 make_admin.py` on your own computer to make an account the admin. It writes a git-ignored `.admin_device` file; with `streamlit run streamlit_app.py` that account then gets an **Admin** tab (list accounts, delete one, delete all others). The deployed app never has this file, so nobody online can be an admin.
