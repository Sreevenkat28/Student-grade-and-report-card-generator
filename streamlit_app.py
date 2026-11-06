"""Student Grade & Report Card Generator — Streamlit version."""
from datetime import date

import pandas as pd
import streamlit as st

import auth
import classes_db as cdb

PASS_PERCENT = 40
GRADE_SCALE = [
    (90, "A+", "Outstanding"),
    (80, "A", "Excellent"),
    (70, "B+", "Very Good"),
    (60, "B", "Good"),
    (50, "C", "Satisfactory"),
    (40, "D", "Needs Improvement"),
    (0, "F", "Fail"),
]
DEFAULT_SUBJECTS = ["Mathematics", "Science", "English", "Social Studies", "Computer Science"]


def grade_for(pct):
    for low, grade, remark in GRADE_SCALE:
        if pct >= low:
            return grade, remark


def compute_result(rows):
    """rows: list of dicts with Subject, Marks, Max. Returns (result, error)."""
    if not rows:
        return None, "Add at least one subject."
    out = []
    for r in rows:
        name = str(r.get("Subject") or "").strip()
        marks, mx = r.get("Marks"), r.get("Max")
        if not name:
            return None, "Every subject needs a name."
        if mx is None or pd.isna(mx) or mx <= 0:
            return None, f'Maximum marks for "{name}" must be greater than 0.'
        if marks is None or pd.isna(marks):
            return None, f'Enter marks for "{name}".'
        if marks < 0:
            return None, f'Marks for "{name}" cannot be negative.'
        if marks > mx:
            return None, f'Marks for "{name}" ({marks:g}) exceed the maximum ({mx:g}).'
        pct = round(marks / mx * 100, 2)
        out.append({
            "Subject": name, "Marks": marks, "Max": mx, "%": pct,
            "Grade": grade_for(pct)[0],
            "Status": "Pass" if pct >= PASS_PERCENT else "Fail",
        })
    total = round(sum(o["Marks"] for o in out), 2)
    max_total = round(sum(o["Max"] for o in out), 2)
    pct = round(total / max_total * 100, 2)
    failed = [o["Subject"] for o in out if o["Status"] == "Fail"]
    passed = pct >= PASS_PERCENT and not failed
    grade, remark = grade_for(pct)
    if not passed:
        remark = "Not promoted — must reappear in failed subject(s)"
    return {"rows": out, "total": total, "max_total": max_total, "pct": pct,
            "grade": grade, "remark": remark, "passed": passed, "failed": failed}, None


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
def _send(email, code):
    """Deliver the code. Returns an error string or None."""
    try:
        if st.secrets.get("dev_show_code", False):
            st.session_state["dev_code"] = code
            return None
        smtp = dict(st.secrets["smtp"])
    except Exception:
        return "Email sending isn't configured yet (missing SMTP secrets)."
    try:
        auth.send_code_email(smtp, email, code)
        return None
    except Exception:
        return "Couldn't send the email. Check the SMTP settings and try again."


def _start_reset(email, username):
    code, err = auth.issue_code(email)
    err = err or _send(email, code)
    if err:
        st.error(err)
        return
    st.session_state["pending"] = {"email": email, "username": username, "verified": False}
    st.rerun()


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
            _start_reset(pending["email"], pending["username"])
        if c2.button("← Back", width="stretch"):
            _clear_pending()
            st.rerun()
    else:
        st.success("Code confirmed. Choose a new password.")
        with st.form("newpw"):
            pw = st.text_input("New password", type="password", help="At least 6 characters.")
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


def login_screen():
    st.title("🎓 Grade & Report Card Generator")
    pending = st.session_state.get("pending")
    if pending:
        _reset_screen(pending)
        return

    st.markdown('<p class="sub">Create an account in seconds, or log in</p>', unsafe_allow_html=True)
    tab_signup, tab_login = st.tabs(["✨ Sign up", "🔑 Log in"])
    with tab_signup:
        with st.form("signup"):
            email = st.text_input("Email")
            uname = st.text_input("Username", help="Use this for quick log in later.")
            pw = st.text_input("Password", type="password", help="At least 6 characters.", key="su_pw")
            pw2 = st.text_input("Confirm password", type="password", key="su_pw2")
            if st.form_submit_button("Create my account", type="primary", width="stretch"):
                ok, msg, email_n, uname_n = auth.check_signup(email, uname)
                err = msg if not ok else (auth.check_password(pw) or ("Passwords do not match." if pw != pw2 else ""))
                if err:
                    st.error(err)
                else:
                    auth.create_member(email_n, uname_n, pw)  # signed up -> straight in
                    st.session_state["user"] = uname_n
                    st.rerun()
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
    del st.session_state["user"]
    st.rerun()

st.title("🎓 Grade & Report Card Generator")
st.markdown('<p class="sub">Enter marks to get the percentage, grade and pass/fail result</p>',
            unsafe_allow_html=True)

IS_ADMIN = auth.is_admin(user)
if IS_ADMIN:
    tab_report, tab_classes, tab_admin = st.tabs(["📝 Report card", "📚 My classes", "🛠 Admin"])
else:
    tab_report, tab_classes = st.tabs(["📝 Report card", "📚 My classes"])
my = cdb.list_classes(user)

# ---- Report card tab
with tab_report:
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
            res, err = compute_result(table.to_dict("records"))
            if err:
                st.error(err)
            else:
                with st.container(border=True):
                    st.markdown("<h3 style='text-align:center;margin:0'>REPORT CARD</h3>"
                                f"<p class='sub' style='margin-bottom:1rem'>{exam or 'Academic Report'}</p>",
                                unsafe_allow_html=True)
                    d1, d2, d3, d4 = st.columns(4)
                    d1.caption("Name"); d1.write(f"**{name}**")
                    d2.caption("Roll / ID"); d2.write(roll or "—")
                    d3.caption("Class"); d3.write(cls or "—")
                    d4.caption("Date"); d4.write(f"{date.today():%d %b %Y}")

                    df = pd.DataFrame(res["rows"])
                    st.dataframe(df, width="stretch", hide_index=True)

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Total", f"{res['total']:g} / {res['max_total']:g}")
                    m2.metric("Percentage", f"{res['pct']}%")
                    m3.metric("Grade", res["grade"])
                    m4.metric("Result", "PASS" if res["passed"] else "FAIL")

                    if res["passed"]:
                        st.success(f"**Remarks:** {res['remark']}")
                    else:
                        msg = f"**Remarks:** {res['remark']}"
                        if res["failed"]:
                            msg += f" — failed in {', '.join(res['failed'])}"
                        st.error(msg)

                st.download_button("Download as CSV", df.to_csv(index=False),
                                   file_name=f"report_card_{name.strip().replace(' ', '_')}.csv",
                                   mime="text/csv", type="primary", width="stretch")

    st.caption("Pass: at least 40% in every subject and overall · "
               "A+ ≥90 · A ≥80 · B+ ≥70 · B ≥60 · C ≥50 · D ≥40 · F <40")


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
