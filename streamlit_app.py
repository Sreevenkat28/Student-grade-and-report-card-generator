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


st.set_page_config(page_title="Grade & Report Card Generator", page_icon="🎓")
st.title("🎓 Student Grade & Report Card Generator")


def login_screen():
    st.caption("Please log in or create an account to continue.")
    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])
    with tab_login:
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", type="primary"):
                if auth.authenticate(u, p):
                    st.session_state["user"] = u.strip().lower()
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
    with tab_signup:
        with st.form("signup"):
            u = st.text_input("Choose a username")
            p = st.text_input("Choose a password", type="password")
            p2 = st.text_input("Confirm password", type="password")
            if st.form_submit_button("Create account"):
                if p != p2:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = auth.register(u, p)
                    (st.success if ok else st.error)(msg)


if "user" not in st.session_state:
    login_screen()
    st.stop()

top_l, top_r = st.columns([4, 1])
top_l.caption(f"Logged in as **{st.session_state['user']}**")
if top_r.button("Log out"):
    del st.session_state["user"]
    st.rerun()

st.caption("Enter subject marks to get the percentage, grade, pass/fail status and a report card.")

with st.form("student"):
    c1, c2 = st.columns(2)
    name = c1.text_input("Student name")
    roll = c2.text_input("Roll / ID number")
    cls = c1.text_input("Class / Grade")
    exam = c2.text_input("Exam")

    st.subheader("Subject marks")
    st.caption("Add or delete rows in the table as needed.")
    table = st.data_editor(
        pd.DataFrame({"Subject": DEFAULT_SUBJECTS, "Marks": [None] * 5, "Max": [100.0] * 5}),
        num_rows="dynamic", width="stretch", hide_index=True,
        column_config={
            "Marks": st.column_config.NumberColumn(min_value=0.0),
            "Max": st.column_config.NumberColumn(min_value=1.0),
        },
    )
    submitted = st.form_submit_button("Generate report card", type="primary")

if submitted:
    if not name.strip():
        st.error("Please enter the student's name.")
    else:
        res, err = compute_result(table.to_dict("records"))
        if err:
            st.error(err)
        else:
            st.divider()
            st.header("REPORT CARD")
            st.markdown(f"**{exam or 'Academic Report'}**")
            st.write(f"**Name:** {name}  |  **Roll/ID:** {roll or '—'}  |  "
                     f"**Class:** {cls or '—'}  |  **Date:** {date.today():%d %b %Y}")
            df = pd.DataFrame(res["rows"])
            st.dataframe(df, width="stretch", hide_index=True)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total", f"{res['total']:g} / {res['max_total']:g}")
            m2.metric("Percentage", f"{res['pct']}%")
            m3.metric("Grade", res["grade"])
            m4.metric("Result", "PASS" if res["passed"] else "FAIL")

            if res["passed"]:
                st.success(f"Remarks: {res['remark']}")
            else:
                msg = f"Remarks: {res['remark']}"
                if res["failed"]:
                    msg += f" — Failed in: {', '.join(res['failed'])}"
                st.error(msg)

            st.download_button("Download marks as CSV", df.to_csv(index=False),
                               file_name=f"report_card_{name.strip().replace(' ', '_')}.csv",
                               mime="text/csv")

st.caption("Pass rule: at least 40% in every subject and overall. "
           "Grades: A+ ≥90 · A ≥80 · B+ ≥70 · B ≥60 · C ≥50 · D ≥40 · F <40")
