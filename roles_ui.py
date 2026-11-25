"""Screens that depend on the account's role: Teaching (teachers), Classrooms (students) and Admin."""
from datetime import datetime

import pandas as pd
import streamlit as st

import auth
import classes_db as cdb
import grading
import prefs_db
import rooms_db


def _date(ts):
    return datetime.fromtimestamp(ts).strftime("%d %b %Y")


def _safe_cell(text):
    """Stop spreadsheet programs from running a downloaded value as a formula."""
    text = str(text)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def _files(user, room_id, key_prefix, can_delete=False):
    items = rooms_db.materials(user, room_id)
    if not items:
        st.caption("No files shared yet.")
        return
    chosen = st.selectbox("Shared file", [m["id"] for m in items], key=f"{key_prefix}_mat_{room_id}",
                          format_func=lambda i: next(m["name"] for m in items if m["id"] == i))
    got = rooms_db.get_material(user, room_id, chosen)
    if got:
        c1, c2 = st.columns(2)
        c1.download_button("⬇ Download", got[2], file_name=got[0], mime=got[1], width="stretch",
                           key=f"{key_prefix}_dl_{room_id}")
        if can_delete and c2.button("🗑 Remove file", width="stretch", key=f"{key_prefix}_rm_{room_id}"):
            rooms_db.delete_material(user, room_id, chosen)
            st.rerun()


# ------------------------------------------------------------------ teacher
def teaching_tab(user):
    st.markdown("#### 🏫 Teaching")
    st.caption("Create a classroom and give students its join code. You only see students who join with your code. "
               "Grades you enter here appear in their app and they can't change them.")
    with st.form("new_room", clear_on_submit=True):
        name = st.text_input("New classroom name", help="Students see this as the class name, for example Math 10-B.")
        if st.form_submit_button("➕ Create classroom", type="primary", width="stretch"):
            ok, res = rooms_db.create_room(user, name)
            if ok:
                st.session_state["room_pick"] = res
                st.rerun()
            st.error(res)

    rooms = rooms_db.rooms_of_teacher(user)
    if not rooms:
        st.info("You have no classrooms yet.")
        return
    ids = [r["id"] for r in rooms]
    if st.session_state.get("room_pick") not in ids:
        st.session_state["room_pick"] = ids[0]
    rid = st.selectbox("Classroom", ids, key="room_pick", format_func=lambda i: next(r["name"] for r in rooms if r["id"] == i))
    room = next(r for r in rooms if r["id"] == rid)
    st.info(f"Join code for **{room['name']}**: **{room['code']}**" + ("" if room["open"] else "  (closed to new students)"))

    t_book, t_stats, t_report, t_news, t_files, t_manage = st.tabs(
        ["📒 Gradebook", "📈 Class statistics", "🧾 Student report", "📣 Announcements", "📎 Materials", "🛠 Manage"])
    book = rooms_db.gradebook(user, rid)
    percents = rooms_db.percents(user, rid)

    with t_book:
        with st.form(f"new_assignment_{rid}", clear_on_submit=True):
            c1, c2 = st.columns([3, 1])
            title = c1.text_input("Assignment or test", help="For example Unit 1 test.")
            mx = c2.number_input("Out of", min_value=1.0, value=100.0, step=1.0, help="Maximum marks.")
            if st.form_submit_button("Add assignment", width="stretch"):
                ok, msg = rooms_db.add_assignment(user, rid, title, mx)
                if ok:
                    st.rerun()
                st.error(msg)
        if not book["students"]:
            st.info("No students yet. Share the join code above.")
        elif not book["assignments"]:
            st.info("Add an assignment, then type the scores.")
        else:
            data = {"Student": book["students"]}
            config = {}
            for a in book["assignments"]:
                col = f"a{a['id']}"
                data[col] = pd.Series([book["scores"].get((a["id"], s)) for s in book["students"]], dtype="float")
                config[col] = st.column_config.NumberColumn(f"{a['title']} / {a['max']:g}", min_value=0.0,
                                                            max_value=float(a["max"]), help="Leave empty if not marked.")
            data["Total %"] = [None if percents[s] is None else f"{percents[s]:g}%" for s in book["students"]]
            frame = pd.DataFrame(data)
            with st.form(f"gradebook_{rid}"):
                edited = st.data_editor(frame, hide_index=True, width="stretch", num_rows="fixed",
                                        disabled=["Student", "Total %"], column_config=config)
                if st.form_submit_button("Save scores", type="primary", width="stretch"):
                    changes = []
                    for rec in edited.to_dict("records"):
                        for a in book["assignments"]:
                            new = rec[f"a{a['id']}"]
                            new = None if new is None or new != new else float(new)
                            if new != book["scores"].get((a["id"], rec["Student"])):
                                changes.append((a["id"], rec["Student"], new))
                    try:
                        rooms_db.set_scores(user, rid, changes)
                        st.toast(f"Saved {len(changes)} score(s). Students see them now.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            export = frame.rename(columns={f"a{a['id']}": _safe_cell(f"{a['title']} / {a['max']:g}") for a in book["assignments"]})
            st.download_button("⬇ Export gradebook (CSV)", export.to_csv(index=False), file_name="gradebook.csv",
                               mime="text/csv", width="stretch", key=f"csv_{rid}")
        if book["assignments"]:
            with st.expander("Delete an assignment"):
                aid = st.selectbox("Assignment", [a["id"] for a in book["assignments"]], key=f"del_a_{rid}",
                                   format_func=lambda i: next(a["title"] for a in book["assignments"] if a["id"] == i))
                if st.button("Delete it and its scores", key=f"del_a_btn_{rid}"):
                    rooms_db.delete_assignment(user, rid, aid)
                    st.rerun()

    with t_stats:
        values = [v for v in percents.values() if v is not None]
        if not values:
            st.info("Statistics appear once you have entered some scores.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Class average", f"{sum(values) / len(values):.1f}%")
            m2.metric("Highest", f"{max(values):g}%")
            m3.metric("Lowest", f"{min(values):g}%")
            m4.metric("Pass rate", f"{100 * sum(v >= room['pass_mark'] for v in values) / len(values):.0f}%",
                      help=f"Share of marked students at or above the pass mark of {room['pass_mark']:g}%.")
            scale = prefs_db.load(user)[0]
            letters = [grading.grade_for(scale, v)[0] for v in values]
            st.markdown("**Grade distribution** (your grade scale)")
            st.bar_chart(pd.DataFrame({"Grade": [g["grade"] for g in scale], "Students": [letters.count(g["grade"]) for g in scale]}),
                         x="Grade", y="Students")
            behind = [s for s, v in percents.items() if v is not None and v < room["pass_mark"]]
            if behind:
                st.warning("Below the pass mark: " + ", ".join(behind))

    with t_report:
        if not book["students"]:
            st.info("No students yet.")
        else:
            who = st.selectbox("Student", book["students"], key=f"rep_{rid}")
            marked = [{"Subject": a["title"], "Marks": book["scores"][(a["id"], who)], "Max": a["max"]}
                      for a in book["assignments"] if (a["id"], who) in book["scores"]]
            if not marked:
                st.caption("No scores for this student yet.")
            else:
                res, err = grading.compute_result(marked, prefs_db.load(user)[0],
                                                  {"pass_subject": room["pass_mark"], "pass_overall": room["pass_mark"], "require_all": False})
                if err:
                    st.error(err)
                else:
                    df = pd.DataFrame(res["rows"]).rename(columns={"Subject": "Assignment"})
                    st.dataframe(df, width="stretch", hide_index=True)
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Percentage", f"{res['pct']}%")
                    m2.metric("Grade", res["grade"])
                    m3.metric("Result", "PASS" if res["passed"] else "FAIL")
                    df["Assignment"] = df["Assignment"].map(_safe_cell)
                    st.download_button("⬇ Download report (CSV)", df.to_csv(index=False), file_name=f"report_{who}.csv",
                                       mime="text/csv", width="stretch", key=f"repcsv_{rid}")

    with t_news:
        with st.form(f"news_{rid}", clear_on_submit=True):
            text = st.text_area("Message to this class", help="Every student in this classroom sees it.")
            if st.form_submit_button("Post announcement", type="primary", width="stretch"):
                ok, msg = rooms_db.add_announcement(user, rid, text)
                if ok:
                    st.rerun()
                st.error(msg)
        for a in rooms_db.announcements(user, rid):
            c1, c2 = st.columns([6, 1])
            c1.caption(_date(a["created"]))
            c1.text(a["text"])
            if c2.button("🗑", key=f"del_news_{a['id']}", help="Delete this announcement"):
                rooms_db.delete_announcement(user, rid, a["id"])
                st.rerun()

    with t_files:
        with st.form(f"share_{rid}", clear_on_submit=True):
            ups = st.file_uploader("Share files with this class", accept_multiple_files=True,
                                   help="Worksheets, notes, a syllabus. Up to 10 MB each.")
            if st.form_submit_button("Share", type="primary", width="stretch"):
                for up in ups or []:
                    ok, msg = rooms_db.add_material(user, rid, up.name, up.getvalue())
                    (st.success if ok else st.error)(msg)
        _files(user, rid, "t", can_delete=True)

    with t_manage:
        st.markdown("**Classroom controls**")
        with st.form(f"controls_{rid}"):
            pass_mark = st.number_input("Pass mark for this class (%)", 0.0, 100.0, float(room["pass_mark"]), 0.5)
            show_avg = st.checkbox("Students can see the class average", value=room["show_average"])
            is_open = st.checkbox("Accept new students", value=room["open"], help="Turn off to stop the join code working.")
            if st.form_submit_button("Save controls", type="primary", width="stretch"):
                rooms_db.update_room(user, rid, pass_mark, show_avg, is_open)
                st.rerun()
        if st.button("Make a new join code", key=f"newcode_{rid}", help="The old code stops working.", width="stretch"):
            rooms_db.new_code(user, rid)
            st.rerun()
        st.markdown("**Students**")
        students = rooms_db.roster(user, rid)
        if students:
            st.dataframe(pd.DataFrame({"Student": students,
                                       "Grade": ["—" if percents.get(s) is None else f"{percents[s]:g}%" for s in students]}),
                         hide_index=True, width="stretch")
            who = st.selectbox("Remove a student", students, index=None, placeholder="Choose a student", key=f"rmwho_{rid}")
            if st.button("Remove from classroom", disabled=who is None, key=f"rmbtn_{rid}"):
                rooms_db.remove_student(user, rid, who)
                st.rerun()
        else:
            st.caption("No students yet.")
        with st.expander("Delete this classroom"):
            sure = st.checkbox("Delete the classroom, its scores, announcements and files", key=f"sure_{rid}")
            if st.button("Delete classroom", disabled=not sure, key=f"delroom_{rid}"):
                rooms_db.delete_room(user, rid)
                st.session_state.pop("room_pick", None)
                st.rerun()


# ------------------------------------------------------------------ student
def classrooms_tab(user):
    st.markdown("#### 🏫 Classrooms")
    st.caption("Join your teacher's classroom with the code they give you. Your teacher can then see your username and give "
               "you grades, which update your report card and GPA.")
    with st.form("join_room", clear_on_submit=True):
        code = st.text_input("Join code", help="The 8-character code from your teacher.")
        if st.form_submit_button("Join classroom", type="primary", width="stretch"):
            ok, msg = rooms_db.join(user, code)
            if ok:
                cdb.add_classes(user, [msg], "current")
                st.toast(f"You joined {msg}.")
                st.rerun()
            st.error(msg)
    rooms = rooms_db.rooms_of_student(user)
    if not rooms:
        st.info("You haven't joined any classrooms.")
    for room in rooms:
        rid = room["id"]
        with st.expander(f"{room['name']}  ·  teacher: {room['teacher']}", expanded=len(rooms) == 1):
            mine, avg = rooms_db.my_percent(user, rid), rooms_db.class_average(user, rid)
            m1, m2 = st.columns(2)
            m1.metric("Your grade", "—" if mine is None else f"{mine:g}%",
                      help="Marks you earned out of the marks possible on the work your teacher has graded.")
            m2.metric("Class average", "hidden" if not room["show_average"] else ("—" if avg is None else f"{avg:g}%"))
            scores = rooms_db.my_scores(user, rid)
            if scores:
                st.dataframe(pd.DataFrame([{"Assignment": s["title"],
                                            "Your marks": "not marked" if s["marks"] is None else f"{s['marks']:g}",
                                            "Out of": f"{s['max']:g}"} for s in scores]), hide_index=True, width="stretch")
            st.markdown("**📣 Announcements**")
            news = rooms_db.announcements(user, rid)
            if not news:
                st.caption("None yet.")
            for a in news[:10]:
                st.caption(_date(a["created"]))
                st.text(a["text"])
            st.markdown("**📎 Materials**")
            _files(user, rid, "s")
            sure = st.checkbox("I want to leave this classroom (your scores there are removed)", key=f"leave_sure_{rid}")
            if st.button("Leave classroom", disabled=not sure, key=f"leave_{rid}"):
                rooms_db.leave(user, rid)
                st.rerun()


# ------------------------------------------------------------------ admin (owner's device only)
def admin_tab(admin_user, viewing_user, view_as):
    """`admin_user` is the device owner. `view_as(username)` switches the app to look at another account."""
    if not auth.is_admin(admin_user):
        return
    st.markdown("#### 🛠 Admin")
    st.caption("Only on this device. You can see every account and classroom here, change roles, and open the app as anyone.")
    accounts = auth.list_accounts()
    st.dataframe(pd.DataFrame([{"Username": a["username"], "Email": a["email"],
                                "Role": "admin (you)" if a["username"] == admin_user else a["role"]} for a in accounts]),
                 width="stretch", hide_index=True)
    others = [a["username"] for a in accounts if a["username"] != admin_user]
    with st.container(border=True, key="card_admin_account"):
        st.markdown("##### Manage an account")
        target = st.selectbox("Account", others, index=None, placeholder="Choose an account", key="adm_target")
        if target:
            current = auth.get_role(target)
            new_role = st.radio("Role", list(auth.ROLES), index=list(auth.ROLES).index(current), horizontal=True,
                                key=f"adm_role_{target}", help="Changing a teacher to student deletes their classrooms.")
            c1, c2, c3 = st.columns(3)
            if c1.button("Save role", disabled=new_role == current, width="stretch"):
                auth.set_role(admin_user, target, new_role)
                st.rerun()
            if c2.button("👀 View as them", type="primary", width="stretch", help="See the app exactly as this account does."):
                view_as(target)
            if c3.button("🗑 Delete", width="stretch"):
                auth.delete_member(target)
                st.session_state.pop("adm_target", None)
                st.rerun()
        elif not others:
            st.caption("No other accounts yet. Sign up a test student and a test teacher to try the roles.")
    with st.container(border=True, key="card_admin_rooms"):
        st.markdown("##### All classrooms")
        rooms = rooms_db.all_rooms()
        if rooms:
            st.dataframe(pd.DataFrame([{"Teacher": r["teacher"], "Classroom": r["name"], "Code": r["code"],
                                        "Students": r["students"]} for r in rooms]), width="stretch", hide_index=True)
            rid = st.selectbox("Delete a classroom", [r["id"] for r in rooms], index=None, placeholder="Choose a classroom",
                               format_func=lambda i: next(f"{r['teacher']} · {r['name']}" for r in rooms if r["id"] == i))
            if st.button("Delete classroom", disabled=rid is None, key="adm_del_room"):
                rooms_db.admin_delete_room(admin_user, rid)
                st.rerun()
        else:
            st.caption("No classrooms yet.")
    with st.container(border=True, key="card_admin_wipe"):
        st.markdown("##### Delete ALL other accounts")
        st.caption("Removes every account and its data except yours. This cannot be undone.")
        confirm = st.text_input("Type DELETE to confirm", key="wipe_confirm")
        if st.button("Delete all other accounts", type="primary", disabled=confirm != "DELETE" or not others):
            n = auth.delete_all_members(keep=admin_user)
            st.session_state.pop("wipe_confirm", None)
            st.toast(f"Deleted {n} account(s).")
            st.rerun()
