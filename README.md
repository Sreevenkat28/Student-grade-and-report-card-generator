# Grade Generator

Student Grade & Report Card Generator. Enter subject marks and get the percentage, grade, pass/fail status and a report card.

- **Streamlit app:** `streamlit_app.py` (run with `pip install -r requirements.txt && streamlit run streamlit_app.py`)
- The Streamlit app: sign up with email + username + password, then enter the 6-digit code emailed to you to confirm your email (the account is created and you're logged in once it's confirmed), then log in with your username or email and password. "Forgot password?" emails a 6-digit code (valid 10 min) to reset it.
- After sign-up it asks for your current and previous classes. Tabs: **✏️ My grades** (type one grade per class, a letter like B+ or a percentage like 87%; the Report card, GPA, My classes, summary bar, assistant and profile all update from it at once), **Report card** (show grades as letters, percentages or both; your choice is remembered), **GPA** (unweighted + weighted on the standard 4.0 scale; enter grades as letters or percentages), **Grading rules** (edit report-card grade cut-offs and pass marks, plus the whole GPA scale: points per grade, percentage cut-offs and weighted bonuses per course level), **My classes** (plus recorded test grades), **Files** (upload and keep any file type), **Assistant** (Claude-powered study helper), **Settings** window (click your name, then ⚙️ Settings): appearance (light/dark/auto and effects), preferences (how grades are shown, reset rules), account (change password or email, test email, delete account) and your data (download as JSON, clear grades).
- Codes are emailed from your own Gmail through a Google Apps Script (`apps_script/Code.gs`, setup steps are in its header) or via SMTP. Put the settings in Streamlit Cloud -> App settings -> Secrets (see `.streamlit/secrets.toml.example`). Addresses are checked before sending: format, disposable-mail domains, common typos (gmial.com) and DNS (the domain must accept mail). For testing only, `dev_show_code = true` shows the code on screen instead of emailing it.
- Accounts are stored in a local SQLite file (`users.db`), which is NOT persistent on Streamlit Community Cloud: accounts reset when the app restarts.
- **Static web version (no login):** open `index.html` in a browser (uses `grading.js`, `app.js`, `style.css`)

Pass rule: at least 40% in every subject and overall.
Grades: A+ ≥90 · A ≥80 · B+ ≥70 · B ≥60 · C ≥50 · D ≥40 · F <40

## Roles
Everyone uses the same login screen; the account decides the role.

| Role | How you get it | What it can do |
|---|---|---|
| **Student** | choose *Student* at sign-up | All the grade, report card, GPA, file and assistant tools, plus **Classrooms**: join with a teacher's code, see your scores, announcements and materials. |
| **Teacher** | choose *Teacher* at sign-up | Everything a student has, plus **Teaching**: create classrooms with join codes, gradebook, class statistics, student reports, announcements, shared materials, pass mark, close or delete a classroom, remove students. |
| **Admin** | the owner: the account with the owner's email (or, on their own computer, the `.admin_device` file) | Preview the Teacher or Student view, open the app as any account, change roles, delete accounts and classrooms. |

**Online admin (the deployed app):** the account registered with the owner's email is admin automatically. Creating it needs the code sent to that inbox, and nobody else can switch their account to that address. Use a strong password: it is the only other protection. (To use a different owner, set `admin_email` in Secrets.)

A teacher only sees students who join with their code. Grades a teacher enters flow into the student's tabs and the student can't change them. To restrict who can register as a teacher, set `teacher_code` in Secrets.

**Using admin:** on your Mac, double-click `run_admin.command` (or `bash run_admin.command`). The first run installs what's needed and creates your admin account; the app then opens at http://localhost:8501. It only listens on your computer. Its accounts are separate from the online app's.

## Study assistant
The Assistant tab is a chat-style command assistant that works for everyone with no API key and no cost. It does what you ask in plain words and tells you what it changed. It can:
- set or clear any class's grade (`my math grade is B+`, `set physics to 87%`), credits and level (`make physics honors`, `make all classes regular`), rename or move or remove classes, record test scores;
- build report cards (`make a report card for Sam Lee, roll 12, exam Finals: math 80/100, science 45/50`), work out GPA, make study plans, give advice, save notes;
- change every grading setting (pass marks, grade cut-offs, add or remove grades, remarks, GPA points and cut-offs, course levels and their bonuses), show grades as letters or percentages, switch dark mode and each animation;
- open any tab or the right section of Settings, list or show or delete files, show your settings and profile.

It also: handles **several requests in one message** (`my math grade is B+ and turn on dark mode`), forgives small **typos**, asks for a **yes** before deleting anything, and has an **undo** (say `undo`, or press the button) that reverses the whole last message, including confirmed deletions. It never changes passwords or emails or deletes your account; it opens Settings instead. Type `help` for the full list.

It uses pattern matching, not a language model, so it works best with short, direct commands; if it can't tell what you mean it suggests commands to try. Optional: if the app owner adds `ANTHROPIC_API_KEY` to Secrets (see `.streamlit/secrets.toml.example`), a switch appears to use Claude for free-form requests instead. That mode is billed to the key's owner, sends messages and grades to Anthropic, and is limited to 30 messages per hour per user.

## Built-in help
Most labels have a small **?** icon, and the table column headings explain themselves when you hover them, so every setting and number is described where you use it.

## Dark mode
Switch with the 🌙 / ☀️ button next to your name, or choose Light / Dark / Auto (follows your device) in Settings → Appearance, or tell the assistant `dark mode`. The choice is saved to your account.

## Tests
`python tests/test_roles.py` checks role permissions and screens, `python tests/test_tabs.py` checks that every tab renders, and `python tests/test_assistant.py` checks the assistant's commands, multi-request messages, confirmations and undo (both use a throwaway database).

## Look and animations
The interface uses an Apple-style design: SF system font, large rounded corners, frosted-glass panels and macOS-style segmented tabs.

## Animations
Click your name at the top left to open your **profile menu**: your details (email, class/grade/file counts), Settings and Log out. The switches are: all animations, tab transitions, click/press effects, hover lift, the typing effect in the assistant, and fade-in cards. Choices are saved per account, and the assistant can change them too (`turn click effects off`). Animations are disabled automatically for visitors whose device asks for reduced motion.
