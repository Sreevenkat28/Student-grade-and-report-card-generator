# Grade Generator

Student Grade & Report Card Generator. Enter subject marks and get the percentage, grade, pass/fail status and a report card.

- **Streamlit app:** `streamlit_app.py` (run with `pip install -r requirements.txt && streamlit run streamlit_app.py`)
- The Streamlit app: sign up with email + username + password, then enter the 6-digit code emailed to you to confirm your email (the account is created and you're logged in once it's confirmed), then log in with your username or email and password. "Forgot password?" emails a 6-digit code (valid 10 min) to reset it.
- After sign-up it asks for your current and previous classes. Tabs: **✏️ My grades** (type one grade per class, a letter like B+ or a percentage like 87%; the Report card, GPA, My classes, summary bar, assistant and profile all update from it at once), **Report card** (show grades as letters, percentages or both; your choice is remembered), **GPA** (unweighted + weighted on the standard 4.0 scale; enter grades as letters or percentages), **Grading rules** (edit report-card grade cut-offs and pass marks, plus the whole GPA scale: points per grade, percentage cut-offs and weighted bonuses per course level), **My classes** (plus recorded test grades), **Files** (upload and keep any file type), **Assistant** (Claude-powered study helper), **Account** (change password / email, send a test email, delete account).
- Codes are emailed from your own Gmail through a Google Apps Script (`apps_script/Code.gs`, setup steps are in its header) or via SMTP. Put the settings in Streamlit Cloud -> App settings -> Secrets (see `.streamlit/secrets.toml.example`). Addresses are checked before sending: format, disposable-mail domains, common typos (gmial.com) and DNS (the domain must accept mail). For testing only, `dev_show_code = true` shows the code on screen instead of emailing it.
- Accounts are stored in a local SQLite file (`users.db`), which is NOT persistent on Streamlit Community Cloud: accounts reset when the app restarts.
- **Static web version (no login):** open `index.html` in a browser (uses `grading.js`, `app.js`, `style.css`)

Pass rule: at least 40% in every subject and overall.
Grades: A+ ≥90 · A ≥80 · B+ ≥70 · B ≥60 · C ≥50 · D ≥40 · F <40

## Admin (this device only)
Run `python3 make_admin.py` on your own computer to make an account the admin. It writes a git-ignored `.admin_device` file; with `streamlit run streamlit_app.py` that account then gets an **Admin** tab (list accounts, delete one, delete all others). The deployed app never has this file, so nobody online can be an admin.

## Study assistant
The Assistant tab is a chat-style command assistant that works for everyone with no API key. It understands plain requests and acts on your own data: record or undo grades, add/move/remove classes, make report cards, work out GPA, build and save study plans, change pass marks, grade cut-offs, GPA points and weights, switch how grades are shown, turn animations on or off, read or delete your files, and open any tab (type `help` for examples). Removing a class or file, or deleting all grades, asks for a "yes" first. It never changes passwords or emails or deletes your account; it sends you to the Account tab for that.

It uses pattern matching, not a language model, so it works best with short commands. Optional: if the app owner adds `ANTHROPIC_API_KEY` to Secrets (see `.streamlit/secrets.toml.example`), a switch appears to use Claude instead. That mode is billed to the key's owner, sends messages and grades to Anthropic, and is limited to 30 messages per hour per user.

## Built-in help
Most labels have a small **?** icon, and the table column headings explain themselves when you hover them, so every setting and number is described where you use it.

## Dark mode
Switch with the 🌙 / ☀️ button next to your name, or choose Light / Dark / Auto (follows your device) in the profile menu, or tell the assistant `dark mode`. The choice is saved to your account.

## Tests
`python tests/test_tabs.py` checks that every tab renders (uses a throwaway database).

## Look and animations
The interface uses an Apple-style design: SF system font, large rounded corners, frosted-glass panels and macOS-style segmented tabs.

## Animations
Click your name at the top left to open your **profile menu**: your details (email, class/grade/file counts), the **✨ Effects** switches, Account settings and Log out. The switches are: all animations, tab transitions, click/press effects, hover lift, the typing effect in the assistant, and fade-in cards. Choices are saved per account, and the assistant can change them too (`turn click effects off`). Animations are disabled automatically for visitors whose device asks for reduced motion.
