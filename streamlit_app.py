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
      .block-container {padding-top: 2.5rem; max-width: 760px;}
      h1 {font-size: 1.9rem !important; text-align: center; margin-bottom: 0;}
      .sub {text-align: center; color: #64708a; margin: 0 0 1.5rem;}
      div[data-testid="stMetric"] {background: #f6f8fc; border: 1px solid #e3e8f2;
          border-radius: 10px; padding: 12px 14px;}
      div[data-testid="stForm"] {border-radius: 12px;}
      .stButton > button, .stFormSubmitButton > button {border-radius: 8px; width: 100%;}
    </style>
    """,
    unsafe_allow_html=True,
)


def login_screen():
    st.title("🎓 Grade & Report Card Generator")
    st.markdown('<p class="sub">Log in or create an account to continue</p>', unsafe_allow_html=True)
    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])
    with tab_login:
        with st.form("login"):
            ident = st.text_input("Username or email")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", type="primary"):
                user = auth.authenticate(ident, pw)
                if user:
                    st.session_state["user"] = user
                    st.rerun()
                else:
                    st.error("Invalid username/email or password.")
    with tab_signup:
        with st.form("signup"):
            email = st.text_input("Email")
            uname = st.text_input("Username", help="Use this for quick log in later.")
            pw = st.text_input("Password", type="password", help="At least 6 characters.")
            pw2 = st.text_input("Confirm password", type="password")
            if st.form_submit_button("Create account", type="primary"):
                if pw != pw2:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = auth.register(email, uname, pw)
                    (st.success if ok else st.error)(msg)


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
