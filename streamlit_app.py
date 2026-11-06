"""Student Grade & Report Card Generator — Streamlit version."""
from datetime import date

import pandas as pd
import streamlit as st

import auth

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


st.set_page_config(page_title="Grade & Report Card Generator", page_icon="🎓", layout="centered")
st.markdown(
    """
    <style>
      #MainMenu, footer, header [data-testid="stToolbar"] {visibility: hidden;}
      .stApp {background: linear-gradient(180deg, #eef2ff 0%, #f5f7fb 40%);}
      .block-container {padding-top: 2.5rem; max-width: 760px;}
      h1 {font-size: 1.9rem !important; text-align: center; margin-bottom: 0;}
      .sub {text-align: center; color: #64708a; margin: 0 0 1.5rem;}
      div[data-testid="stMetric"] {background: #ffffff; border: 1px solid #dfe5f5;
          border-radius: 10px; padding: 12px 14px;}
      div[data-testid="stForm"] {border-radius: 12px;}
      .stButton > button, .stFormSubmitButton > button {border-radius: 8px; width: 100%;}
    </style>
    """,
    unsafe_allow_html=True,
)


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


def _start(mode, email, username):
    """Issue + send a code, then move to the code-entry step."""
    code, err = auth.issue_code(email)
    err = err or _send(email, code)
    if err:
        st.error(err)
        return
    st.session_state["pending"] = {"mode": mode, "email": email, "username": username}
    st.rerun()


def _mask(email):
    name, domain = email.split("@", 1)
    return f"{name[:2]}{'*' * max(len(name) - 2, 1)}@{domain}"


def login_screen():
    st.title("🎓 Grade & Report Card Generator")
    st.markdown('<p class="sub">Sign in with a one-time code sent to your email</p>',
                unsafe_allow_html=True)
    pending = st.session_state.get("pending")

    if pending:  # step 2: enter the code
        st.info(f"We sent a 6-digit code to **{_mask(pending['email'])}**. It expires in 10 minutes.")
        if st.session_state.get("dev_code"):
            st.warning(f"Test mode — your code is **{st.session_state['dev_code']}**")
        with st.form("verify"):
            code = st.text_input("Confirmation code", max_chars=6, placeholder="123456")
            if st.form_submit_button("Verify & continue", type="primary"):
                ok, msg = auth.verify_code(pending["email"], code)
                if not ok:
                    st.error(msg)
                else:
                    if pending["mode"] == "signup":
                        try:
                            auth.create_member(pending["email"], pending["username"])
                        except Exception:
                            st.error("That username or email was just taken. Please start again.")
                            st.session_state.pop("pending")
                            st.stop()
                    st.session_state["user"] = pending["username"]
                    for k in ("pending", "dev_code"):
                        st.session_state.pop(k, None)
                    st.rerun()
        c1, c2 = st.columns(2)
        if c1.button("Resend code"):
            _start(pending["mode"], pending["email"], pending["username"])
        if c2.button("← Back"):
            for k in ("pending", "dev_code"):
                st.session_state.pop(k, None)
            st.rerun()
        return

    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])
    with tab_login:
        with st.form("login"):
            ident = st.text_input("Username or email")
            if st.form_submit_button("Send me a code", type="primary"):
                member = auth.find_member(ident) if ident.strip() else None
                if not member:
                    st.error("No account found. Check the spelling or sign up first.")
                else:
                    _start("login", member[1], member[0])
    with tab_signup:
        with st.form("signup"):
            email = st.text_input("Email")
            uname = st.text_input("Username", help="Use this for quick log in later.")
            if st.form_submit_button("Send me a code", type="primary"):
                ok, msg, email_n, uname_n = auth.check_signup(email, uname)
                if not ok:
                    st.error(msg)
                else:
                    _start("signup", email_n, uname_n)


if "user" not in st.session_state:
    login_screen()
    st.stop()

# ---- Logged-in app ----
head_l, head_r = st.columns([3, 1], vertical_alignment="center")
head_l.markdown(f"**👤 {st.session_state['user']}**")
if head_r.button("Log out"):
    del st.session_state["user"]
    st.rerun()

st.title("🎓 Grade & Report Card Generator")
st.markdown('<p class="sub">Enter marks to get the percentage, grade and pass/fail result</p>',
            unsafe_allow_html=True)

with st.form("student"):
    st.markdown("##### Student details")
    c1, c2 = st.columns(2)
    name = c1.text_input("Student name")
    roll = c2.text_input("Roll / ID number")
    cls = c1.text_input("Class / Grade")
    exam = c2.text_input("Exam")

    st.markdown("##### Subject marks")
    table = st.data_editor(
        pd.DataFrame({"Subject": DEFAULT_SUBJECTS, "Marks": [None] * 5, "Max": [100.0] * 5}),
        num_rows="dynamic", width="stretch", hide_index=True,
        column_config={
            "Marks": st.column_config.NumberColumn(min_value=0.0),
            "Max": st.column_config.NumberColumn(min_value=1.0),
        },
    )
    st.caption("Add or delete rows in the table as needed.")
    submitted = st.form_submit_button("Generate report card", type="primary")

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
                               mime="text/csv")

st.caption("Pass: at least 40% in every subject and overall · "
           "A+ ≥90 · A ≥80 · B+ ≥70 · B ≥60 · C ≥50 · D ≥40 · F <40")
