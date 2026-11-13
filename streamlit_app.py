"""Student Grade & Report Card Generator — Streamlit version."""
from datetime import date, datetime

import pandas as pd
import streamlit as st

import json
import streamlit.components.v1 as components

import assistant as ai
import auth
import classes_db as cdb
import files_db
import gpa as gpa_lib
import grading
import prefs_db

DEFAULT_SUBJECTS = ["Mathematics", "Science", "English", "Social Studies", "Computer Science"]


# --------------------------------------------------------------------------- page + style
st.set_page_config(page_title="Grade & Report Card Generator", page_icon="🎓", layout="centered")
st.markdown(
    """
    <style>
      /* Works in both light and dark: only translucent colors, text inherits from the theme. */
      footer {visibility: hidden;}
      .stApp {
        background-image:
          radial-gradient(900px 420px at 0% -5%, rgba(124,77,255,.22), transparent 70%),
          radial-gradient(800px 420px at 100% 0%, rgba(255,77,157,.18), transparent 70%);
      }
      .block-container {padding-top: 2.2rem; max-width: 780px;}
      h1 {font-size: 2rem !important; text-align: center; margin-bottom: 0;
          background: linear-gradient(90deg, #7c4dff, #ff4d9d); -webkit-background-clip: text;
          background-clip: text; -webkit-text-fill-color: transparent;}
      .sub {text-align: center; opacity: .75; margin: 0 0 1.4rem;}

      /* Buttons: bold, high-contrast, obviously clickable */
      button[data-testid^="stBaseButton-primary"] {
        background: linear-gradient(90deg, #7c4dff, #ff4d9d) !important;
        color: #fff !important; border: 0 !important; font-weight: 700 !important;
        padding: .65rem 1.2rem !important; box-shadow: 0 4px 14px rgba(124,77,255,.45);
        cursor: pointer; transition: transform .12s ease, box-shadow .12s ease, filter .12s;
      }
      button[data-testid^="stBaseButton-secondary"] {
        border: 2px solid #7c4dff !important; font-weight: 600 !important;
        padding: .55rem 1.1rem !important; cursor: pointer;
        transition: transform .12s ease, background .12s ease, box-shadow .12s ease;
      }
      button[data-testid^="stBaseButton-primary"]:hover {
        transform: translateY(-2px); filter: brightness(1.08);
        box-shadow: 0 8px 20px rgba(124,77,255,.55);
      }
      button[data-testid^="stBaseButton-secondary"]:hover {
        background: rgba(124,77,255,.16) !important; transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(124,77,255,.3);
      }
      button[data-testid^="stBaseButton"]:active {transform: translateY(0) scale(.98);}
      button[data-testid^="stBaseButton"]:focus-visible {outline: 3px solid #ffb300 !important;}

      div[data-testid="stMetric"] {background: rgba(124,77,255,.10); border: 1px solid rgba(124,77,255,.35);
          border-radius: 12px; padding: 12px 14px;}
      div[data-testid="stForm"], div[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 14px;}
      button[role="tab"] {font-weight: 600; font-size: 1.02rem;}
      .chip {display:inline-block; padding:.25rem .7rem; border-radius:999px; font-weight:600;
             background: rgba(124,77,255,.18); border:1px solid rgba(124,77,255,.4); margin:.15rem .2rem 0 0;}
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- login
def _dev_mode():
    """Test mode (code shown on screen) applies only if no real email settings are configured."""
    try:
        if "apps_script" in st.secrets or "smtp" in st.secrets:
            return False
        return bool(st.secrets.get("dev_show_code", False))
    except Exception:
        return False


def _smtp_settings():
    """Returns (settings, error). Prefers [apps_script]; falls back to [smtp]."""
    try:
        sections = list(st.secrets.keys())
    except Exception:
        return None, ("Email sending isn't set up: the app can't read any Secrets. Either none are saved, "
                      "or the text has a formatting mistake (such as curly quotes). Re-save them under "
                      "Settings -> Secrets, then reboot the app.")
    try:
        if "apps_script" in sections:
            return dict(st.secrets["apps_script"]), None
        if "smtp" in sections:
            return dict(st.secrets["smtp"]), None
    except Exception:
        return None, "The email settings in Secrets couldn't be read. Check the formatting."
    found = ", ".join(sections) if sections else "none"
    return None, ("Email sending isn't set up: there is no [apps_script] or [smtp] section in the app's "
                  f"Secrets. Sections found: {found}. Check the spelling of the header.")


def _deliver(send_fn, *args):
    """Run an auth.send_* function with the app's SMTP settings. Returns an error string or None."""
    smtp, err = _smtp_settings()
    if err:
        return err
    try:
        send_fn(smtp, *args)
        return None
    except auth.EmailError as e:
        return str(e)
    except Exception:
        return "Couldn't send the email because of an unexpected error. Check the SMTP settings."


def _send(email, code):
    """Deliver a reset code. Returns an error string or None."""
    if _dev_mode():
        st.session_state["dev_code"] = code
        return None
    return _deliver(auth.send_code_email, email, code)


def _start_pending(pending):
    """Email a fresh code for `pending` (purpose 'signup' or 'reset') and show the code screen."""
    code, err = auth.issue_code(pending["email"])
    err = err or _send(pending["email"], code)
    if err:
        if code:  # the code never reached the user, so don't make them wait to retry
            auth.discard_code(pending["email"])
        st.error(err)
        return
    st.session_state["pending"] = pending
    st.rerun()


def _start_reset(email, username):
    _start_pending({"purpose": "reset", "email": email, "username": username, "verified": False})


def _mask(email):
    name, domain = email.split("@", 1)
    return f"{name[:2]}{'*' * max(len(name) - 2, 1)}@{domain}"


def _clear_pending():
    for k in ("pending", "dev_code"):
        st.session_state.pop(k, None)


def _reset_screen(pending):
    """Forgot password: confirm the emailed code, then choose a new password."""
    st.markdown('<p class="sub">Reset your password</p>', unsafe_allow_html=True)
    if not pending["verified"]:
        st.info(f"We sent a 6-digit code to **{_mask(pending['email'])}**. It expires in 10 minutes.")
        if st.session_state.get("dev_code"):
            st.warning(f"Test mode — your code is **{st.session_state['dev_code']}**")
        with st.form("verify"):
            code = st.text_input("Confirmation code", max_chars=6, placeholder="123456")
            if st.form_submit_button("Verify code", type="primary", width="stretch"):
                ok, msg = auth.verify_code(pending["email"], code)
                if ok:
                    pending["verified"] = True
                    st.rerun()
                else:
                    st.error(msg)
        c1, c2 = st.columns(2)
        if c1.button("Resend code", width="stretch"):
            _start_pending(pending)
        if c2.button("← Back", width="stretch"):
            _clear_pending()
            st.rerun()
    else:
        st.success("Code confirmed. Choose a new password.")
        with st.form("newpw"):
            pw = st.text_input("New password", type="password")
            pw2 = st.text_input("Confirm new password", type="password")
            if st.form_submit_button("Save password & log in", type="primary", width="stretch"):
                err = auth.check_password(pw) or ("Passwords do not match." if pw != pw2 else "")
                if err:
                    st.error(err)
                else:
                    auth.set_password(pending["email"], pw)
                    st.session_state["user"] = pending["username"]
                    _clear_pending()
                    st.rerun()


def _signup_screen(pending):
    """Sign up, step 2: confirm the emailed code, then the account is created and you're logged in."""
    st.markdown('<p class="sub">Confirm your email to finish signing up</p>', unsafe_allow_html=True)
    st.info(f"We emailed a 6-digit code to **{_mask(pending['email'])}**. It expires in 10 minutes.")
    if st.session_state.get("dev_code"):
        st.warning(f"Test mode — your code is **{st.session_state['dev_code']}**")
    with st.form("verify_signup"):
        code = st.text_input("Confirmation code", max_chars=6, placeholder="123456")
        if st.form_submit_button("Verify & create account", type="primary", width="stretch"):
            ok, msg = auth.verify_code(pending["email"], code)
            if not ok:
                st.error(msg)
            else:
                still_ok, msg2, email_n, uname_n = auth.check_signup(pending["email"], pending["username"])
                if not still_ok:  # someone took the name while the code was in the mail
                    _clear_pending()
                    st.session_state["flash_error"] = msg2
                    st.rerun()
                auth.create_member(email_n, uname_n, pending["password"])
                st.session_state["user"] = uname_n
                _clear_pending()
                st.rerun()
    c1, c2 = st.columns(2)
    if c1.button("Resend code", width="stretch"):
        _start_pending(pending)
    if c2.button("← Back", width="stretch"):
        _clear_pending()
        st.rerun()


def login_screen():
    st.title("🎓 Grade & Report Card Generator")
    pending = st.session_state.get("pending")
    if pending:
        (_signup_screen if pending.get("purpose") == "signup" else _reset_screen)(pending)
        return
    if st.session_state.get("flash_error"):
        st.error(st.session_state.pop("flash_error"))

    st.markdown('<p class="sub">Sign up with a code we email you, or log in</p>', unsafe_allow_html=True)
    tab_signup, tab_login = st.tabs(["✨ Sign up", "🔑 Log in"])
    with tab_signup:
        with st.form("signup"):
            email = st.text_input("Email")
            uname = st.text_input("Username", help="Use this for quick log in later.")
            pw = st.text_input("Password", type="password", key="su_pw")
            pw2 = st.text_input("Confirm password", type="password", key="su_pw2")
            if st.form_submit_button("Send me a confirmation code", type="primary", width="stretch"):
                ok, msg, email_n, uname_n = auth.check_signup(email, uname)
                err = msg if not ok else (auth.check_password(pw) or ("Passwords do not match." if pw != pw2 else ""))
                if err:
                    st.error(err)
                else:
                    _start_pending({"purpose": "signup", "email": email_n, "username": uname_n,
                                    "password": pw})
    with tab_login:
        with st.form("login"):
            ident = st.text_input("Username or email")
            pw = st.text_input("Password", type="password", key="li_pw")
            if st.form_submit_button("Log in", type="primary", width="stretch"):
                u, err = auth.authenticate(ident, pw)
                if u:
                    st.session_state["user"] = u
                    st.rerun()
                else:
                    st.error(err)
        with st.expander("Forgot password?"):
            fid = st.text_input("Username or email", key="fp_id")
            if st.button("Email me a reset code", width="stretch"):
                member = auth.find_member(fid) if fid.strip() else None
                if not member:
                    st.error("No account found with that username or email.")
                else:
                    _start_reset(member[1], member[0])


if "user" not in st.session_state:
    login_screen()
    st.stop()

user = st.session_state["user"]

# --------------------------------------------------------------------------- onboarding
if not cdb.is_onboarded(user):
    st.title("🎓 Welcome!")
    st.markdown('<p class="sub">Tell us about your classes. You can change these any time.</p>',
                unsafe_allow_html=True)
    with st.form("onboarding"):
        cur = st.text_area("📘 What classes are you taking right now?",
                           placeholder="One per line or separated by commas", height=120)
        prev = st.text_area("📗 Any previous classes you've already completed? (optional)",
                            placeholder="One per line or separated by commas", height=120)
        go = st.form_submit_button("Save & continue", type="primary", width="stretch")
    skip = st.button("Skip for now", width="stretch")
    if go or skip:
        if go:
            cdb.add_classes(user, cdb.parse_names(cur), "current")
            cdb.add_classes(user, cdb.parse_names(prev), "previous")
        cdb.mark_onboarded(user)
        st.session_state.pop("just_signed_up", None)
        st.rerun()
    st.stop()

# --------------------------------------------------------------------------- main app
head_l, head_r = st.columns([3, 1], vertical_alignment="center")
head_l.markdown(f"**👤 {user}**")
if head_r.button("Log out", width="stretch"):
    for _k in ("user", "last_report", "display_mode", "ai_msgs", "ai_log", "ai_usage", "goto"):
        st.session_state.pop(_k, None)
    st.rerun()

st.title("🎓 Grade & Report Card Generator")
st.markdown('<p class="sub">Enter marks to get the percentage, grade and pass/fail result</p>',
            unsafe_allow_html=True)

IS_ADMIN = auth.is_admin(user)
TAB_NAMES = ["📝 Report card", "🎯 GPA", "⚙️ Grading rules", "📚 My classes", "📁 Files", "🤖 Assistant", "👤 Account"]
if IS_ADMIN:
    TAB_NAMES.append("🛠 Admin")
_tabs = st.tabs(TAB_NAMES)
tab_report, tab_gpa, tab_rules, tab_classes, tab_files, tab_ai, tab_account = _tabs[:7]
if IS_ADMIN:
    tab_admin = _tabs[7]
scale, rules = prefs_db.load(user)
gpa_scale, gpa_levels = prefs_db.load_gpa(user)
my = cdb.list_classes(user)

# ---- Report card tab
def _render_report(student, res, mode):
    df = pd.DataFrame(res["rows"])
    show_pct, show_letter = mode in ("Percentages", "Both"), mode in ("Letter grades", "Both")
    if not show_pct:
        df = df.drop(columns=["%"])
    else:
        df["%"] = df["%"].map(lambda v: f"{v:g}%")
    if not show_letter:
        df = df.drop(columns=["Grade"])
    with st.container(border=True):
        st.markdown("<h3 style='text-align:center;margin:0'>REPORT CARD</h3>"
                    f"<p class='sub' style='margin-bottom:1rem'>{student['exam'] or 'Academic Report'}</p>",
                    unsafe_allow_html=True)
        d1, d2, d3, d4 = st.columns(4)
        d1.caption("Name"); d1.write(f"**{student['name']}**")
        d2.caption("Roll / ID"); d2.write(student["roll"] or "—")
        d3.caption("Class"); d3.write(student["cls"] or "—")
        d4.caption("Date"); d4.write(student["date"])

        st.dataframe(df, width="stretch", hide_index=True)

        metrics = [("Total", f"{res['total']:g} / {res['max_total']:g}")]
        if show_pct:
            metrics.append(("Percentage", f"{res['pct']}%"))
        if show_letter:
            metrics.append(("Grade", res["grade"]))
        metrics.append(("Result", "PASS" if res["passed"] else "FAIL"))
        for col, (label, value) in zip(st.columns(len(metrics)), metrics):
            col.metric(label, value)

        if res["passed"]:
            st.success(f"**Remarks:** {res['remark']}")
        else:
            msg = f"**Remarks:** {res['remark']}"
            if res["failed"]:
                msg += f" — failed in {', '.join(res['failed'])}"
            st.error(msg)
    st.download_button("Download as CSV", df.to_csv(index=False),
                       file_name=f"report_card_{student['name'].strip().replace(' ', '_')}.csv",
                       mime="text/csv", type="primary", width="stretch")


with tab_report:
    _saved_mode = prefs_db.load_display(user)
    if "display_mode" not in st.session_state:  # first visit this session: start from the saved choice
        st.session_state["display_mode"] = _saved_mode
    mode = st.radio("Show grades as", prefs_db.DISPLAY_MODES, horizontal=True, key="display_mode")
    if mode != _saved_mode:
        prefs_db.save_display(user, mode)
    with st.form("student"):
        st.markdown("##### Student details")
        c1, c2 = st.columns(2)
        name = c1.text_input("Student name")
        roll = c2.text_input("Roll / ID number")
        cls = c1.text_input("Class / Grade")
        exam = c2.text_input("Exam")

        st.markdown("##### Subject marks")
        subjects = my["current"] or DEFAULT_SUBJECTS
        if my["current"]:
            st.caption("Pre-filled from your current classes. Add or delete rows as needed.")
        else:
            st.caption("Add or delete rows as needed. Add your classes in the My classes tab to pre-fill these.")
        table = st.data_editor(
            pd.DataFrame({"Subject": subjects, "Marks": [None] * len(subjects),
                          "Max": [100.0] * len(subjects)}),
            num_rows="dynamic", width="stretch", hide_index=True,
            column_config={
                "Marks": st.column_config.NumberColumn(min_value=0.0),
                "Max": st.column_config.NumberColumn(min_value=1.0),
            },
        )
        submitted = st.form_submit_button("Generate report card", type="primary", width="stretch")

    if submitted:
        if not name.strip():
            st.error("Please enter the student's name.")
        else:
            res, err = grading.compute_result(table.to_dict("records"), scale, rules)
            if err:
                st.error(err)
                st.session_state.pop("last_report", None)
            else:
                st.session_state["last_report"] = (
                    {"name": name, "roll": roll, "cls": cls, "exam": exam,
                     "date": f"{date.today():%d %b %Y}"}, res)
    if st.session_state.get("last_report"):  # kept so switching the display mode doesn't lose it
        _render_report(*st.session_state["last_report"], mode)

    _scale_txt = " · ".join(f"{g['grade']} ≥{g['min']:g}" for g in scale) if mode != "Percentages" else ""
    _rule_txt = (f"Pass: at least {rules['pass_subject']:g}% in every subject and {rules['pass_overall']:g}% overall"
                 if rules["require_all"] else f"Pass: at least {rules['pass_overall']:g}% overall")
    st.caption(" · ".join(x for x in (_rule_txt, _scale_txt, "change these in the Grading rules tab") if x))


# ---- My classes tab
def _move(n, status):
    cdb.set_status(user, n, status)


def _delete(n):
    cdb.remove_class(user, n)


def _class_list(title, status, empty_msg):
    other = "previous" if status == "current" else "current"
    move_label = "✅ Completed" if status == "current" else "↩ Current"
    with st.container(border=True):
        st.markdown(f"#### {title} ({len(my[status])})")
        if not my[status]:
            st.caption(empty_msg)
        for n in my[status]:
            a, b, c = st.columns([5, 3, 1], vertical_alignment="center")
            a.markdown(f"<span class='chip'>{n}</span>", unsafe_allow_html=True)
            b.button(move_label, key=f"mv_{status}_{n}", on_click=_move, args=(n, other),
                     width="stretch", help=f"Move to {other} classes")
            c.button("🗑", key=f"rm_{status}_{n}", on_click=_delete, args=(n,),
                     width="stretch", help="Remove")


with tab_classes:
    _class_list("📘 Current classes", "current", "No current classes yet — add some below.")
    _class_list("📗 Previous classes", "previous", "No previous classes yet.")
    with st.form("add_class", clear_on_submit=True):
        st.markdown("##### Add classes")
        names = st.text_input("Class name(s)", placeholder="Separate several with commas")
        where = st.radio("Add to", ["Current", "Previous"], horizontal=True)
        if st.form_submit_button("➕ Add", type="primary", width="stretch"):
            parsed = cdb.parse_names(names)
            if not parsed:
                st.error("Enter at least one class name.")
            else:
                n = cdb.add_classes(user, parsed, where.lower())
                if n == 0:
                    st.warning("Those classes are already in your lists.")
                else:
                    st.rerun()


# ---- Recorded grades (My classes tab)
with tab_classes:
    st.markdown("#### 📈 Recorded grades")
    st.caption("Keep your test and assignment scores here. The AI assistant uses them to find weak spots and "
               "build a study plan.")
    all_classes = my["current"] + my["previous"]
    recorded = cdb.list_grades(user)
    if not all_classes:
        st.info("Add a class above first, then record grades for it.")
    else:
        with st.form("add_grade", clear_on_submit=True):
            g1, g2, g3, g4 = st.columns([3, 2, 2, 3])
            g_class = g1.selectbox("Class", all_classes)
            g_marks = g2.number_input("Marks", min_value=0.0, value=None, step=0.5, placeholder="e.g. 45")
            g_max = g3.number_input("Out of", min_value=1.0, value=100.0, step=1.0)
            g_label = g4.text_input("Label (optional)", placeholder="Unit 3 test")
            if st.form_submit_button("➕ Record grade", type="primary", width="stretch"):
                if g_marks is None:
                    st.error("Enter the marks you got.")
                else:
                    ok, msg = cdb.add_grade(user, g_class, g_marks, g_max, g_label)
                    if ok:
                        st.rerun()
                    st.error(msg)
    if recorded:
        gdf2 = pd.DataFrame([{"Class": g["class"], "Label": g["label"] or "—", "Score": f"{g['marks']:g} / {g['max']:g}",
                              "Percent": f"{g['percent']:g}%", "Date": datetime.fromtimestamp(g["created"]).strftime("%d %b %Y")}
                             for g in recorded])
        st.dataframe(gdf2, width="stretch", hide_index=True)
        d1, d2 = st.columns([4, 1], vertical_alignment="bottom")
        pick = d1.selectbox("Remove a grade", [None] + [g["id"] for g in recorded], index=0,
                            format_func=lambda i: "Choose…" if i is None else next(
                                f"{g['class']} · {g['label'] or 'no label'} · {g['marks']:g}/{g['max']:g}" for g in recorded if g["id"] == i))
        if d2.button("Remove", disabled=pick is None, width="stretch"):
            cdb.delete_grade(user, pick)
            st.rerun()


# ---- Files tab
def _fmt_size(n):
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / (1024 * 1024):.1f} MB"


with tab_files:
    st.markdown("#### 📁 My files")
    n_files, used = files_db.usage(user)
    st.caption(f"{n_files}/{files_db.MAX_FILES} files · {_fmt_size(used)} of {_fmt_size(files_db.MAX_TOTAL_BYTES)} used · "
               f"up to {_fmt_size(files_db.MAX_FILE_BYTES)} per file. Store PDFs, notes, syllabi, report cards - any file type.")
    with st.form("upload_files", clear_on_submit=True):
        uploads = st.file_uploader("Add files", accept_multiple_files=True)
        if st.form_submit_button("Save files", type="primary", width="stretch"):
            if not uploads:
                st.warning("Choose at least one file first.")
            for up in uploads or []:
                ok, res = files_db.add_file(user, up.name, up.getvalue())
                (st.success if ok else st.error)(f'Saved "{files_db.safe_name(up.name)}".' if ok else res)
    my_files = files_db.list_files(user)
    if not my_files:
        st.info("No files yet. Upload one above.")
    else:
        st.dataframe(pd.DataFrame([{"Name": f["name"], "Type": f["mime"], "Size": _fmt_size(f["size"]),
                                    "Added": datetime.fromtimestamp(f["created"]).strftime("%d %b %Y")}
                                   for f in my_files]), width="stretch", hide_index=True)
        chosen = st.selectbox("Open a file", [f["id"] for f in my_files],
                              format_func=lambda i: next(f["name"] for f in my_files if f["id"] == i))
        got = files_db.get_file(user, chosen)
        if got:
            fname, fmime, fdata = got
            b1, b2 = st.columns(2)
            b1.download_button("⬇ Download", fdata, file_name=fname, mime=fmime, type="primary", width="stretch")
            if b2.button("🗑 Delete this file", width="stretch"):
                files_db.delete_file(user, chosen)
                st.rerun()
            if fmime.startswith("image/"):
                st.image(fdata)
            else:
                with st.expander("Preview text"):
                    txt, terr = files_db.extract_text(fname, fdata, limit=4000)
                    st.text(txt) if txt else st.caption(terr)


# ---- Assistant tab
TAB_MAP = {t.split(" ", 1)[1]: t for t in TAB_NAMES if t != "🛠 Admin"}


def _ai_settings():
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY")
        model = st.secrets.get("anthropic_model", ai.DEFAULT_MODEL)
    except Exception:
        return None, ai.DEFAULT_MODEL
    return (str(key).strip() if key else None), (str(model).strip() or ai.DEFAULT_MODEL)


@st.cache_resource
def _ai_client(key):
    return ai.make_client(key)


with tab_ai:
    st.markdown("#### 🤖 AI study assistant")
    api_key, ai_model = _ai_settings()
    if not api_key:
        st.info("The assistant isn't switched on yet. The app owner needs to add an `ANTHROPIC_API_KEY` under "
                "Settings → Secrets (get one at console.anthropic.com), then reboot the app.")
    else:
        st.caption("Ask me to record grades, work out your GPA, review your files, explain how to improve, or build a "
                   "study plan. I can change things in the app for you, and I'll tell you what I did. Your messages, "
                   "grades and any file I read are sent to Anthropic's Claude to answer you. "
                   "I can't change passwords or delete accounts or files.")
        st.session_state.setdefault("ai_msgs", [])
        st.session_state.setdefault("ai_log", [])
        st.session_state.setdefault("ai_usage", [0, 0])
        for m in st.session_state["ai_log"]:
            with st.chat_message(m["role"]):
                for act in m.get("actions", []):
                    st.caption(act)
                st.markdown(m["text"])
        if not st.session_state["ai_log"]:
            st.markdown("**Try:**")
            qa, qb, qc, qd = st.columns(4)
            if qa.button("📅 Make a study plan", width="stretch"):
                st.session_state["ai_pending"] = "Look at my classes and grades and make me a weekly study plan. Save it as a note."
            if qb.button("📈 How can I improve?", width="stretch"):
                st.session_state["ai_pending"] = "Based on my recorded grades, where am I weakest and how can I improve?"
            if qc.button("🎯 My GPA", width="stretch"):
                st.session_state["ai_pending"] = "Calculate my GPA from my recorded grades (use each class's average percent, 1 credit each)."
            if qd.button("📁 Read my files", width="stretch"):
                st.session_state["ai_pending"] = "List my files and summarise what's in them."
        typed = st.chat_input("Message your assistant…", max_chars=ai.MAX_USER_CHARS)
        prompt = typed or st.session_state.pop("ai_pending", None)
        if prompt:
            turns = sum(1 for m in st.session_state["ai_log"] if m["role"] == "user")
            rate_err = ai.check_rate(user) if turns < ai.MAX_TURNS_PER_CHAT else None
            if turns >= ai.MAX_TURNS_PER_CHAT:
                st.warning("This chat is getting long. Press **New chat** to start fresh.")
            elif rate_err:
                st.error(rate_err)
            else:
                with st.spinner("Thinking…"):
                    res = ai.chat_turn(_ai_client(api_key), ai_model, user, st.session_state["ai_msgs"], prompt, TAB_MAP)
                if res["error"]:
                    st.error(res["error"])
                else:
                    st.session_state["ai_log"] += [{"role": "user", "text": prompt},
                                                   {"role": "assistant", "text": res["text"], "actions": res["actions"]}]
                    st.session_state["ai_usage"][0] += res["usage"][0]
                    st.session_state["ai_usage"][1] += res["usage"][1]
                    if res["nav"]:
                        st.session_state["goto"] = res["nav"]
                    st.rerun()
        if st.session_state["ai_log"]:
            u_in, u_out = st.session_state["ai_usage"]
            n1, n2 = st.columns([3, 1], vertical_alignment="center")
            n1.caption(f"Model: {ai_model} · tokens used this chat: {u_in:,} in / {u_out:,} out")
            if n2.button("New chat", width="stretch"):
                for k in ("ai_msgs", "ai_log", "ai_usage"):
                    st.session_state.pop(k, None)
                st.rerun()


# ---- GPA tab
with tab_gpa:
    st.markdown("#### GPA calculator")
    gmode = st.radio("Enter grades as", ["Letter grades", "Percentages"], horizontal=True, key="gpa_mode")
    st.caption("Uses your GPA scale. Weighted GPA adds each course level's bonus (no bonus for a 0-point grade). "
               "Leave a grade empty for courses still in progress. Change the scale, bonuses and "
               "percentage cut-offs in the Grading rules tab."
               + (" Percentages are converted to letters using your cut-offs." if gmode == "Percentages" else ""))
    n = max(len(my["current"]), 4)
    names = (my["current"] + [""] * n)[:n]
    level_names = [l["level"] for l in gpa_levels]
    if gmode == "Letter grades":
        gdf = pd.DataFrame({"Course": names, "Grade": [None] * n, "Credits": [1.0] * n,
                            "Level": [level_names[0]] * n})
        gcfg = {"Grade": st.column_config.SelectboxColumn(options=[g["grade"] for g in gpa_scale])}
    else:
        gdf = pd.DataFrame({"Course": names, "Percent": [None] * n, "Credits": [1.0] * n,
                            "Level": [level_names[0]] * n})
        gcfg = {"Percent": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=0.5)}
    with st.form("gpa"):
        gtable = st.data_editor(
            gdf, num_rows="dynamic", width="stretch", hide_index=True,
            column_config={**gcfg,
                           "Credits": st.column_config.NumberColumn(min_value=0.0, step=0.5),
                           "Level": st.column_config.SelectboxColumn(options=level_names, required=True)},
        )
        calc = st.form_submit_button("Calculate GPA", type="primary", width="stretch")
    if calc:
        g, gerr = gpa_lib.compute_gpa(gtable.to_dict("records"), gpa_scale, gpa_levels)
        if gerr:
            st.error(gerr)
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Unweighted GPA", f"{g['unweighted']:.2f}")
            m2.metric("Weighted GPA", f"{g['weighted']:.2f}")
            m3.metric("Credits counted", f"{g['credits']:g}")
            st.dataframe(pd.DataFrame(g["rows"]), width="stretch", hide_index=True)


# ---- Grading rules tab
with tab_rules:
    st.markdown("#### Your grading rules")
    st.caption("These decide the grade letters and the pass/fail result on your report cards. "
               "Edit the table, add or delete rows, then save.")
    with st.form("rules"):
        edited = st.data_editor(
            pd.DataFrame({"Grade": [g["grade"] for g in scale],
                          "Minimum %": [g["min"] for g in scale],
                          "Remark": [g["remark"] for g in scale]}),
            num_rows="dynamic", width="stretch", hide_index=True,
            column_config={"Minimum %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=0.5)},
        )
        c1, c2 = st.columns(2)
        ps = c1.number_input("Pass mark per subject (%)", 0.0, 100.0, float(rules["pass_subject"]), 0.5)
        po = c2.number_input("Pass mark overall (%)", 0.0, 100.0, float(rules["pass_overall"]), 0.5)
        req = st.checkbox("Must pass every subject to pass overall", value=rules["require_all"])
        save_rules = st.form_submit_button("Save grading rules", type="primary", width="stretch")
    if save_rules:
        new_scale, serr = grading.clean_scale(
            [{"grade": r["Grade"], "min": r["Minimum %"], "remark": r["Remark"]}
             for r in edited.to_dict("records")])
        new_rules, rerr = grading.clean_rules(ps, po, req)
        if serr or rerr:
            st.error(serr or rerr)
        else:
            prefs_db.save(user, new_scale, new_rules)
            st.toast("Grading rules saved.")
            st.rerun()
    if st.button("Reset to defaults", width="stretch"):
        prefs_db.reset(user)
        st.rerun()
    st.caption("The lowest grade must start at 0% so every score gets a grade.")

    st.divider()
    st.markdown("#### GPA scale")
    st.caption("Edit the points for each grade, the lowest percentage that earns it (used when you enter "
               "percentages in the GPA tab; leave empty if it should never come from a percentage), and the "
               "weighted-GPA bonus for each course level. One grade must start at 0%.")
    with st.form("gpa_rules"):
        gs = st.data_editor(
            pd.DataFrame({"Grade": [g["grade"] for g in gpa_scale], "Points": [g["points"] for g in gpa_scale],
                          "Minimum %": [g["min"] for g in gpa_scale]}),
            num_rows="dynamic", width="stretch", hide_index=True, key="gs_editor",
            column_config={"Points": st.column_config.NumberColumn(min_value=0.0, max_value=10.0, step=0.1),
                           "Minimum %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=0.5)},
        )
        st.markdown("**Course levels (weighted bonus)**")
        lv = st.data_editor(
            pd.DataFrame({"Level": [l["level"] for l in gpa_levels], "Bonus": [l["bonus"] for l in gpa_levels]}),
            num_rows="dynamic", width="stretch", hide_index=True, key="lv_editor",
            column_config={"Bonus": st.column_config.NumberColumn(min_value=0.0, max_value=5.0, step=0.1)},
        )
        save_gpa_rules = st.form_submit_button("Save GPA scale", type="primary", width="stretch")
    if save_gpa_rules:
        new_gs, gerr1 = gpa_lib.clean_scale(
            [{"grade": r["Grade"], "points": r["Points"], "min": r["Minimum %"]} for r in gs.to_dict("records")])
        new_lv, gerr2 = gpa_lib.clean_levels(
            [{"level": r["Level"], "bonus": r["Bonus"]} for r in lv.to_dict("records")])
        if gerr1 or gerr2:
            st.error(gerr1 or gerr2)
        else:
            prefs_db.save_gpa(user, new_gs, new_lv)
            st.toast("GPA scale saved.")
            st.rerun()
    if st.button("Reset GPA scale to defaults", width="stretch"):
        prefs_db.reset_gpa(user)
        st.rerun()


# ---- Account tab
with tab_account:
    email_now = auth.get_email(user) or "—"
    st.markdown("#### Your account")
    a1, a2 = st.columns(2)
    a1.caption("Username"); a1.write(f"**{user}**")
    a2.caption("Email"); a2.write(f"**{email_now}**")

    with st.container(border=True):
        st.markdown("##### Change password")
        with st.form("chpw", clear_on_submit=True):
            cur = st.text_input("Current password", type="password")
            new1 = st.text_input("New password", type="password")
            new2 = st.text_input("Confirm new password", type="password")
            if st.form_submit_button("Change password", type="primary", width="stretch"):
                ok, msg = auth.change_password(user, cur, new1, new2)
                (st.success if ok else st.error)(msg)

    with st.container(border=True):
        st.markdown("##### Change email")
        with st.form("chem", clear_on_submit=True):
            new_email = st.text_input("New email")
            pw_e = st.text_input("Your password", type="password", key="chem_pw")
            if st.form_submit_button("Update email", type="primary", width="stretch"):
                ok, msg = auth.change_email(user, pw_e, new_email)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()

    with st.container(border=True):
        st.markdown("##### Check that emails reach you")
        st.caption("Password reset codes are sent by email. Send yourself a test to confirm it works.")
        if st.button("Send a test email to my address", width="stretch"):
            now = datetime.now().timestamp()
            if now - st.session_state.get("last_test_email", 0) < 30:
                st.warning("Please wait a few seconds before sending another test.")
            elif _dev_mode():
                st.info("Test mode is on (dev_show_code), so no real email is sent.")
            else:
                st.session_state["last_test_email"] = now
                err = _deliver(auth.send_test_email, email_now)
                if err:
                    st.error(err)
                else:
                    st.success(f"Test email sent to {email_now}. Check your inbox (and spam folder).")

    with st.expander("Delete my account"):
        st.warning("This permanently deletes your account, classes and grading rules.")
        pw_d = st.text_input("Your password", type="password", key="del_pw")
        sure = st.checkbox("I understand this cannot be undone")
        if st.button("Delete my account permanently", disabled=not (sure and pw_d)):
            u, _ = auth.authenticate(user, pw_d)
            if not u:
                st.error("Your password is incorrect.")
            else:
                auth.delete_member(user)
                del st.session_state["user"]
                st.rerun()


# ---- Admin tab (only on the admin's own device)
if IS_ADMIN:
    with tab_admin:
        members = auth.list_members()
        st.markdown(f"#### Accounts ({len(members)})")
        st.dataframe(pd.DataFrame(members, columns=["Username", "Email"]),
                     width="stretch", hide_index=True)
        others = [u for (u, _e) in members if u != user]
        with st.container(border=True):
            st.markdown("##### Delete one account")
            target = st.selectbox("Account", others, index=None, placeholder="Choose an account")
            if st.button("Delete this account", disabled=target is None):
                auth.delete_member(target)
                st.rerun()
        with st.container(border=True):
            st.markdown("##### Delete ALL other accounts")
            st.caption("Removes every account and its classes except yours. This cannot be undone.")
            confirm = st.text_input("Type DELETE to confirm", key="wipe_confirm")
            if st.button("Delete all other accounts", type="primary",
                         disabled=confirm != "DELETE" or not others):
                n = auth.delete_all_members(keep=user)
                st.session_state.pop("wipe_confirm", None)
                st.toast(f"Deleted {n} account(s).")
                st.rerun()


# ---- Let the assistant switch tabs (best effort: clicks the tab in the page)
_goto = st.session_state.pop("goto", None)
if _goto:
    components.html(
        "<script>setTimeout(function(){var t=[].slice.call(window.parent.document.querySelectorAll('button[role=\"tab\"]'))"
        ".filter(function(b){return b.innerText.trim()===" + json.dumps(_goto) + "})[0];if(t)t.click();},350);</script>",
        height=0)
