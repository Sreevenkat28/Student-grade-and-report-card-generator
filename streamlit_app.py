"""Student Grade & Report Card Generator — Streamlit version."""
from datetime import date, datetime

import pandas as pd
import streamlit as st

import html
import json
import re
import time
import streamlit.components.v1 as components

import assistant as ai
import auth
import classes_db as cdb
import files_db
import helper
import overview
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
      [data-testid="stMainMenu"], [data-testid="stAppDeployButton"] {display: none !important;}
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
      div[data-testid="stForm"] {border-radius: 14px;}
      button[role="tab"] {font-weight: 600; font-size: 1.02rem;}
      .chip {display:inline-block; padding:.25rem .7rem; border-radius:999px; font-weight:600;
             background: rgba(124,77,255,.18); border:1px solid rgba(124,77,255,.4); margin:.15rem .2rem 0 0;}

      /* Assistant: modern chat look */
      .ai-hero {display:flex; gap:.9rem; align-items:center; padding:1rem 1.2rem; border-radius:18px; margin:.2rem 0 1rem;
                color:#fff; background: linear-gradient(120deg,#7c4dff,#ff4d9d,#7c4dff); background-size: 220% 220%;
                box-shadow: 0 8px 24px rgba(124,77,255,.35);}
      .ai-hero .orb {font-size:1.8rem; width:2.8rem; height:2.8rem; border-radius:50%; display:flex; align-items:center;
                     justify-content:center; background:rgba(255,255,255,.22); flex:none;}
      .ai-hero b {font-size:1.15rem;} .ai-hero span {opacity:.92; font-size:.92rem;}
      [data-testid="stChatMessage"] {border-radius:18px; padding:.85rem 1.05rem; margin-bottom:.65rem;
          border:1px solid rgba(124,77,255,.28); background: rgba(124,77,255,.07);}
      [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
          background: rgba(255,77,157,.08); border-color: rgba(255,77,157,.32);}
      [data-testid="stChatMessage"] table {font-size:.92rem;}
      [data-testid="stChatInput"] {border-radius:16px;}
      .act {display:inline-block; font-size:.8rem; padding:.12rem .6rem; border-radius:999px; margin:0 .3rem .35rem 0;
            background: rgba(46,160,67,.14); border:1px solid rgba(46,160,67,.4);}

      /* ===== macOS look: SF font stack, big rounded corners, frosted glass, segmented tabs ===== */
      .stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp p,.stApp li,.stApp label,.stApp input,.stApp textarea,
      .stApp [data-testid="stMarkdownContainer"],.stApp [data-testid="stMarkdownContainer"] *,.stApp button p,
      .stApp [data-baseweb="tab"],.stApp [data-testid="stCaptionContainer"],.stApp [data-testid="stMetricValue"],
      .stApp [data-testid="stMetricLabel"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", "Segoe UI", system-ui, sans-serif !important;
        letter-spacing: -0.005em;}
      .stApp h1 {letter-spacing:-0.02em;}
      /* frosted-glass panels */
      [class*="st-key-card"], div[data-testid="stForm"], div[data-testid="stExpander"],
      div[data-testid="stMetric"], div[data-testid="stAlert"] {
        border-radius: 20px !important; border: 1px solid rgba(127,127,127,.22) !important;
        background-color: rgba(127,127,127,.07);
        -webkit-backdrop-filter: blur(18px) saturate(170%); backdrop-filter: blur(18px) saturate(170%);
        box-shadow: 0 1px 2px rgba(0,0,0,.05), 0 10px 28px rgba(0,0,0,.07);}
      div[data-testid="stMetric"] {border-radius: 18px !important;}
      div[data-testid="stExpander"] details, div[data-testid="stExpander"] summary {border-radius: 20px !important;}
      /* inputs */
      div[data-baseweb="input"], div[data-baseweb="base-input"], div[data-baseweb="select"] > div, textarea,
      div[data-testid="stNumberInputContainer"], div[data-testid="stFileUploaderDropzone"] {border-radius: 13px !important;}
      div[data-testid="stFileUploaderDropzone"] {border-radius: 18px !important;}
      div[data-testid="stChatInput"], div[data-testid="stChatInput"] > div {border-radius: 24px !important;}
      div[data-testid="stDataFrame"], div[data-testid="stImage"] img, pre, code {border-radius: 14px !important;}
      div[data-testid="stDataFrame"] {overflow: hidden;}
      div[data-baseweb="popover"] > div {border-radius: 20px !important; overflow: hidden;
        box-shadow: 0 18px 50px rgba(0,0,0,.28) !important;}
      div[data-testid="stPopoverBody"] {border-radius: 20px !important; border: 1px solid rgba(127,127,127,.25);
        -webkit-backdrop-filter: blur(24px) saturate(180%); backdrop-filter: blur(24px) saturate(180%);}
      div[data-baseweb="tooltip"] > div, div[data-testid="stToast"] {border-radius: 16px !important;}
      /* buttons */
      button[data-testid^="stBaseButton"] {border-radius: 13px !important;}
      /* tabs as a macOS segmented control */
      div[data-baseweb="tab-list"] {background: rgba(120,120,128,.16); border-radius: 15px; padding: 4px; gap: 2px;
        overflow-x: auto; scrollbar-width: none;}
      div[data-baseweb="tab-list"]::-webkit-scrollbar {display:none;}
      div[data-baseweb="tab-border"] {display:none;}
      button[role="tab"] {border-radius: 11px !important; padding: .45rem .8rem !important; position: relative; z-index: 1;}
      div[data-baseweb="tab-highlight"] {height: calc(100% - 8px) !important; top: 4px !important; border-radius: 11px;
        background: rgba(124,77,255,.26) !important; border: 1px solid rgba(124,77,255,.45); z-index: 0;
        box-shadow: 0 2px 8px rgba(124,77,255,.25);}
      button[role="tab"][aria-selected="true"] {font-weight: 700;}
      /* profile menu */
      .prof {display:flex; gap:.8rem; align-items:center; margin-bottom:.4rem;}
      .prof .avatar {width:3rem; height:3rem; border-radius:50%; display:flex; align-items:center; justify-content:center; flex:none;
        font-weight:800; font-size:1.25rem; color:#fff; background:linear-gradient(135deg,#7c4dff,#ff4d9d);
        box-shadow:0 4px 14px rgba(124,77,255,.45);}
      .prof span {opacity:.75; font-size:.88rem; word-break:break-all;}
      .stats {display:grid; grid-template-columns:repeat(3,1fr); gap:.5rem; margin:.5rem 0 .2rem;}
      .stats div {text-align:center; padding:.5rem .2rem; border-radius:14px; background:rgba(124,77,255,.1);
        border:1px solid rgba(124,77,255,.25); font-size:.78rem; opacity:.95;}
      .stats b {display:block; font-size:1.2rem;}
      .sumbar {display:flex; flex-wrap:wrap; justify-content:center; gap:.5rem; margin:-.4rem 0 1rem;}
      .sumbar span {padding:.3rem .8rem; border-radius:999px; font-size:.9rem; background:rgba(124,77,255,.12);
        border:1px solid rgba(124,77,255,.3);} .sumbar.hint span {background:rgba(255,179,0,.14); border-color:rgba(255,179,0,.4);}
      .badge {display:inline-block; font-size:.7rem; font-weight:700; padding:.05rem .5rem; border-radius:999px; margin-left:.4rem;
        background:#ffb300; color:#3b2a00; vertical-align:middle;}
    </style>
    """,
    unsafe_allow_html=True,
)

UI_KEYS = prefs_db.UI_KEYS
UI_HELP = {
    "animations": "Master switch: turns every animation on or off at once.",
    "transitions": "Tabs, menus and the page fade and slide in smoothly.",
    "click_fx": "Buttons shrink and ripple when pressed, and boxes glow when you click into them.",
    "hover_fx": "Cards and result boxes lift slightly when you point at them.",
    "typing_fx": "The assistant's replies appear as if they were being typed.",
    "cards_fx": "Forms, tables and results fade in when they appear.",
}
RESULT_HELP = {
    "Total": "All the marks scored, out of all the marks possible.",
    "Percentage": "Total marks as a percentage of the total possible.",
    "Grade": "The letter for that percentage, from your grade scale in the Grading rules tab.",
    "Result": "PASS needs the overall percentage (and, if switched on, every subject) to reach your pass marks.",
}


def _motion_css(ui):
    """Animation CSS built from the user's toggles. Empty when animations are off."""
    reduced = "@media (prefers-reduced-motion: reduce){*{animation:none !important;transition:none !important;}}"
    if not ui.get("animations", True):
        return reduced
    css = ["@keyframes aiShift{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}"
           ".ai-hero{animation: aiShift 9s ease infinite;} .ai-hero .orb{animation: orbPulse 2.6s ease-in-out infinite;}"
           "@keyframes orbPulse{0%,100%{transform:scale(1)}50%{transform:scale(1.09)}}"]
    if ui.get("transitions", True):
        css.append("div[data-baseweb='tab-panel']{animation: tabIn .38s cubic-bezier(.2,.8,.2,1) both;}"
                   "@keyframes tabIn{from{opacity:0;transform:translateY(12px) scale(.995)}to{opacity:1;transform:none}}"
                   "button[role='tab']{transition: color .25s ease, background-color .25s ease, transform .18s ease;}"
                   "button[role='tab']:hover{transform:translateY(-1px)} button[role='tab']:active{transform:scale(.95)}")
    if ui.get("cards_fx", True):
        css.append("div[data-testid='stMetric'],div[data-testid='stAlert'],div[data-testid='stDataFrame'],"
                   "[data-testid='stChatMessage'],.ai-hero{animation-name: popIn; animation-duration:.45s;"
                   "animation-timing-function:cubic-bezier(.2,.9,.3,1.2); animation-fill-mode:both;}"
                   ".ai-hero{animation: popIn .45s cubic-bezier(.2,.9,.3,1.2) both, aiShift 9s ease .45s infinite;}"
                   "@keyframes popIn{from{opacity:0;transform:translateY(14px) scale(.97)}to{opacity:1;transform:none}}")
    if ui.get("transitions", True):
        css.append("div[data-testid='stPopoverBody'],div[data-baseweb='popover'] > div{animation: menuIn .22s cubic-bezier(.2,.9,.3,1.15) both;"
                   "transform-origin: top left;}@keyframes menuIn{from{opacity:0;transform:scale(.92) translateY(-6px)}to{opacity:1;transform:none}}"
                   "div[data-testid='stExpander'] details[open] > div{animation: expandIn .3s ease both;}"
                   "@keyframes expandIn{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}"
                   "div[data-testid='stToast']{animation: menuIn .3s cubic-bezier(.2,.9,.3,1.15) both;}"
                   "section.main .block-container,div.block-container{animation: pageIn .55s ease both;}"
                   "@keyframes pageIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}")
    if ui.get("cards_fx", True):
        css.append("div[data-testid='stForm'],div[data-testid='stExpander'],[class*='st-key-card'],"
                   "div[data-testid='stDataFrame'],div[data-testid='stFileUploader'],div[data-testid='stImage']"
                   "{animation: popIn .5s cubic-bezier(.2,.9,.3,1.1) both;}"
                   "h1{animation: popIn .6s cubic-bezier(.2,.9,.3,1.1) both;}"
                   ".stats div{animation: popIn .5s cubic-bezier(.2,.9,.3,1.1) both;} .stats div:nth-child(2){animation-delay:.07s}"
                   ".stats div:nth-child(3){animation-delay:.14s}")
    if ui.get("click_fx", True):
        css.append("input:focus,textarea:focus,div[data-baseweb='select'] > div:focus-within,div[data-baseweb='input']:focus-within"
                   "{box-shadow:0 0 0 4px rgba(124,77,255,.25) !important;transition:box-shadow .2s ease;}"
                   "input,textarea,div[data-baseweb='select'] > div,div[data-baseweb='input']{transition: box-shadow .2s ease, border-color .2s ease;}"
                   "summary:active,div[data-baseweb='select']:active{transform:scale(.99);}")
        css.append("button[data-testid^='stBaseButton']{position:relative;overflow:hidden;}"
                   "button[data-testid^='stBaseButton']::after{content:'';position:absolute;inset:0;pointer-events:none;"
                   "background:radial-gradient(circle,rgba(255,255,255,.7) 12%,transparent 13%) 50% 50%/1100% 1100% no-repeat;"
                   "opacity:0;transition:background-size .6s ease,opacity 1s ease;}"
                   "button[data-testid^='stBaseButton']:active::after{background-size:0 0;opacity:1;transition:0s;}"
                   "button[data-testid^='stBaseButton']:active{transform:scale(.95) !important;}"
                   "label[data-baseweb='checkbox']:active,label[data-baseweb='radio']:active{transform:scale(.96);}")
    if ui.get("hover_fx", True):
        css.append("div[data-testid='stMetric'],[data-testid='stChatMessage'],[class*='st-key-card']"
                   "{transition: transform .22s ease, box-shadow .22s ease;}"
                   "div[data-testid='stMetric']:hover,[data-testid='stChatMessage']:hover{transform:translateY(-3px);"
                   "box-shadow:0 10px 24px rgba(124,77,255,.22);}")
    return "".join(css) + reduced


_COUNTER = ("img,video,.ai-hero,.prof .avatar,.badge,h1,button[data-testid='stBaseButton-primary'],"
            "button[data-testid='stBaseButton-primaryFormSubmit'],.st-key-theme_quick button p{filter:invert(1) hue-rotate(180deg);}")


def _theme_css(theme, animate):
    """Dark mode by inverting the page (keeps charts/tables readable) and restoring images and the colourful bits."""
    dark = "html{filter:invert(1) hue-rotate(180deg);background:#fff;}" + _COUNTER
    base = "html{transition: filter .45s ease;}" if animate else ""
    if theme == "Dark":
        return base + dark
    if theme == "Auto":
        return base + "@media (prefers-color-scheme: dark){" + dark + "}"
    return base


def _inject_theme(theme, animate):
    st.markdown(f"<style>{_theme_css(theme, animate)}</style>", unsafe_allow_html=True)


def _save_theme():
    u = st.session_state.get("user")
    if u:
        prefs_db.save_theme(u, st.session_state.get("theme_mode", "Light"))


def _toggle_theme():
    cur = st.session_state.get("theme_mode", "Light")
    st.session_state["theme_mode"] = "Light" if cur == "Dark" else "Dark"
    _save_theme()


def _inject_motion(ui):
    st.markdown(f"<style>{_motion_css(ui)}</style>", unsafe_allow_html=True)


def _clear_user_state():
    """Forget everything tied to the signed-in user (called on log out / account deletion)."""
    for k in list(st.session_state.keys()):
        if k in ("user", "last_report", "display_mode", "ai_msgs", "ai_log", "ai_usage", "ai_mode", "ai_state",
                 "ai_stream", "ai_pending", "goto", "_pending_state", "theme_mode", "open_settings", "settings_tab", "settings_flash") or k.startswith("ui_"):
            st.session_state.pop(k, None)


def _save_ui():
    u = st.session_state.get("user")
    if u:
        prefs_db.save_ui(u, {k: st.session_state.get(f"ui_{k}", True) for k in UI_KEYS})


def _typewriter(text):
    """Yield the reply a few characters at a time (about 1.4 s in total at most)."""
    toks = re.findall(r"\S+\s*", text) or [text]
    delay = min(0.03, 1.4 / len(toks))
    for tok in toks:
        yield tok
        time.sleep(delay)


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
            code = st.text_input("Confirmation code", max_chars=6, placeholder="123456",
                                 help="The 6-digit code we just emailed you. It expires in 10 minutes.")
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
            pw = st.text_input("New password", type="password", help="Any length, any characters. Keep it private.")
            pw2 = st.text_input("Confirm new password", type="password", help="Type the same new password again.")
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
        code = st.text_input("Confirmation code", max_chars=6, placeholder="123456",
                                 help="The 6-digit code we just emailed you. It expires in 10 minutes.")
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
    _inject_motion(prefs_db.UI_DEFAULTS)
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
            email = st.text_input("Email", help="We send your confirmation code here, so use a real address you can open.")
            uname = st.text_input("Username", help="A short nickname: 3-30 letters, numbers, _ . or -. You can log in with it instead of your email.")
            pw = st.text_input("Password", type="password", key="su_pw", help="Any length, any characters. Keep it private.")
            pw2 = st.text_input("Confirm password", type="password", key="su_pw2", help="Type the same password again to avoid typos.")
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
            ident = st.text_input("Username or email", help="Either one works.")
            pw = st.text_input("Password", type="password", key="li_pw")
            if st.form_submit_button("Log in", type="primary", width="stretch"):
                u, err = auth.authenticate(ident, pw)
                if u:
                    st.session_state["user"] = u
                    st.rerun()
                else:
                    st.error(err)
        with st.expander("Forgot password?"):
            fid = st.text_input("Username or email", key="fp_id", help="We email a code to the address on this account so you can set a new password.")
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

# Changes the assistant asked for (display mode, effect toggles): applied here, before those widgets exist.
for _k, _v in st.session_state.pop("_pending_state", {}).items():
    st.session_state[_k] = _v
_saved_ui = prefs_db.load_ui(user)

# --------------------------------------------------------------------------- onboarding
if not cdb.is_onboarded(user):
    _inject_motion(_saved_ui)
    _inject_theme(prefs_db.load_theme(user), _saved_ui["animations"] and _saved_ui["transitions"])
    st.title("🎓 Welcome!")
    st.markdown('<p class="sub">Tell us about your classes. You can change these any time.</p>',
                unsafe_allow_html=True)
    with st.form("onboarding"):
        cur = st.text_area("📘 What classes are you taking right now?",
                           help="Your current classes. They pre-fill the report card and GPA tables. You can change them later in My classes.",
                           placeholder="One per line or separated by commas", height=120)
        prev = st.text_area("📗 Any previous classes you've already completed? (optional)",
                            help="Classes you finished in the past. Kept for your records and shown separately.",
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
# These keys must be created in the same run as the profile-menu widgets that use them; creating them
# earlier (e.g. during onboarding) makes the browser show the switches as off.
for _k in UI_KEYS:
    st.session_state.setdefault(f"ui_{_k}", _saved_ui[_k])
UI = {k: st.session_state[f"ui_{k}"] for k in UI_KEYS}
_inject_motion(UI)
st.session_state.setdefault("theme_mode", prefs_db.load_theme(user))
_inject_theme(st.session_state["theme_mode"], UI["animations"] and UI["transitions"])
head_l, _head_gap, head_theme = st.columns([2, 3, 1], vertical_alignment="center")
with head_l.popover(f"👤 {user}", width="stretch"):
    _email = auth.get_email(user) or "—"
    _cls, _sum, (_nfiles, _used) = cdb.list_classes(user), overview.summary(user), files_db.usage(user)
    _badge = '<span class="badge">ADMIN</span>' if auth.is_admin(user) else ""
    _gpa_txt = "—" if _sum["gpa"] is None else "%.2f" % _sum["gpa"]
    st.markdown(f'<div class="prof"><div class="avatar">{html.escape(user[:1].upper())}</div>'
                f'<div><b>{html.escape(user)}</b>{_badge}<br><span>{html.escape(_email)}</span></div></div>'
                f'<div class="stats"><div title="Classes you are taking now"><b>{len(_cls["current"])}</b>current classes</div>'
                f'<div title="Unweighted GPA from your My grades tab"><b>{_gpa_txt}</b>GPA</div>'
                f'<div title="Files stored in your Files tab"><b>{_nfiles}</b>files</div></div>',
                unsafe_allow_html=True)
    if _cls["previous"]:
        st.caption(f"{len(_cls['previous'])} previous class(es)")
    st.divider()
    if st.button("⚙️ Settings", width="stretch", key="prof_settings",
                 help="Light/dark mode, effects, preferences, password, your data and more."):
        st.session_state["open_settings"] = True
        st.rerun()
    if st.button("Log out", width="stretch", key="prof_logout"):
        _clear_user_state()
        st.rerun()
_is_dark = st.session_state.get("theme_mode") == "Dark"
head_theme.button("☀️" if _is_dark else "🌙", key="theme_quick", on_click=_toggle_theme, width="stretch",
                  help="Switch to light mode" if _is_dark else "Switch to dark mode")

st.title("🎓 Grade & Report Card Generator")
st.markdown('<p class="sub">Enter marks to get the percentage, grade and pass/fail result</p>',
            unsafe_allow_html=True)

CT = overview.class_table(user)
SUM = overview.summary(user)
CLS_BY = {r["name"].lower(): r for r in CT}
if SUM["graded"]:
    _bits = [f'<span title="Average of your class percentages">📊 Average <b>{SUM["avg_percent"]:g}%</b></span>'] if SUM["avg_percent"] is not None else []
    if SUM["gpa"] is not None:
        _bits.append(f'<span title="Unweighted GPA on your GPA scale">🎯 GPA <b>{SUM["gpa"]:.2f}</b></span>')
    _bits.append(f'<span title="Classes that have a grade">✅ <b>{SUM["graded"]}/{SUM["total"]}</b> classes graded</span>')
    st.markdown('<div class="sumbar">' + "".join(_bits) + '</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="sumbar hint"><span>👋 Start in <b>✏️ My grades</b>: enter a grade for each class and the whole app fills in.</span></div>',
                unsafe_allow_html=True)

# --------------------------------------------------------------------------- Settings window
_ST_TABS = ["🎨 Appearance", "🎛 Preferences", "👤 Account", "🗂 Your data"]


def _reopen_settings(tab=None):
    """Re-run the whole app (so theme/effect changes apply) and open this window again, on the same tab."""
    st.session_state["open_settings"] = True
    if tab:
        st.session_state["settings_tab"] = tab
    st.rerun(scope="app")


def _export_my_data(u):
    scale_, rules_ = prefs_db.load(u)
    gs_, lv_ = prefs_db.load_gpa(u)
    return {
        "username": u, "email": auth.get_email(u), "exported": datetime.now().isoformat(timespec="seconds"),
        "classes": cdb.list_classes(u),
        "class_grades": [{k: r[k] for k in ("name", "status", "entered_text", "percent", "gpa_letter", "credits", "level")}
                         for r in overview.class_table(u)],
        "recorded_scores": [{k: g[k] for k in ("class", "label", "marks", "max", "percent")} for g in cdb.list_grades(u)],
        "grading_rules": {"scale": scale_, **rules_},
        "gpa_scale": gs_, "course_levels": lv_,
        "preferences": {"theme": prefs_db.load_theme(u), "grades_shown_as": prefs_db.load_display(u), "effects": prefs_db.load_ui(u)},
        "files": [{"name": f["name"], "size_bytes": f["size"]} for f in files_db.list_files(u)],
    }


@st.dialog("⚙️ Settings", width="large")
def settings_dialog():
    u = st.session_state["user"]
    email_now = auth.get_email(u) or "—"
    flash = st.session_state.pop("settings_flash", None)
    if flash:
        st.success(flash)
    t_look, t_prefs, t_acct, t_data = st.tabs(_ST_TABS, default=st.session_state.pop("settings_tab", None))

    with t_look:
        st.markdown("**🌓 Theme**")
        cur_theme = st.session_state.get("theme_mode", "Light")
        new_theme = st.radio("Theme", prefs_db.THEMES, index=prefs_db.THEMES.index(cur_theme), horizontal=True, key="s_theme",
                             label_visibility="collapsed",
                             help="Light or dark look. Auto follows your device's own light/dark setting. The 🌙 button at the top also switches it.")
        if new_theme != cur_theme:
            st.session_state["theme_mode"] = new_theme
            prefs_db.save_theme(u, new_theme)
            _reopen_settings(_ST_TABS[0])
        st.divider()
        st.markdown("**✨ Effects**")
        st.caption("Turn animations on or off. Saved to your account.")
        for k in UI_KEYS:
            cur = st.session_state.get(f"ui_{k}", True)
            v = st.toggle(prefs_db.UI_LABELS[k], value=cur, key=f"s_ui_{k}", help=UI_HELP[k])
            if v != cur:
                st.session_state[f"ui_{k}"] = v
                prefs_db.save_ui(u, {kk: (v if kk == k else st.session_state.get(f"ui_{kk}", True)) for kk in UI_KEYS})
                _reopen_settings(_ST_TABS[0])

    with t_prefs:
        st.markdown("**📊 How grades are shown**")
        modes = prefs_db.DISPLAY_MODES
        cur_mode = prefs_db.load_display(u)
        new_mode = st.radio("Show grades as", modes, index=modes.index(cur_mode), horizontal=True, key="s_display",
                            help="Report cards can show letter grades (A, B+), percentages (85%), or both.")
        if new_mode != cur_mode:
            prefs_db.save_display(u, new_mode)
            st.session_state["_pending_state"] = {**st.session_state.get("_pending_state", {}), "display_mode": new_mode}
            st.session_state["settings_flash"] = f"Grades now show as {new_mode.lower()}."
            _reopen_settings(_ST_TABS[1])
        st.divider()
        st.markdown("**↩ Reset to defaults**")
        st.caption("Go back to the standard grade letters, pass marks and GPA scale. Your grades and classes are not touched.")
        sure_reset = st.checkbox("Yes, reset my grading rules and GPA scale", key="s_sure_reset")
        r1, r2 = st.columns(2)
        if r1.button("Reset grading rules", disabled=not sure_reset, width="stretch",
                     help="Restores the default report-card grade letters and the 40% pass marks."):
            prefs_db.reset(u)
            st.session_state["settings_flash"] = "Grading rules reset to the defaults."
            _reopen_settings(_ST_TABS[1])
        if r2.button("Reset GPA scale", disabled=not sure_reset, width="stretch",
                     help="Restores the standard 4.0 scale and the Honors / AP bonuses."):
            prefs_db.reset_gpa(u)
            st.session_state["settings_flash"] = "GPA scale reset to the defaults."
            _reopen_settings(_ST_TABS[1])

    with t_acct:
        st.markdown("**Your account**")
        a1, a2 = st.columns(2)
        a1.caption("Username"); a1.write(f"**{u}**")
        a2.caption("Email"); a2.write(f"**{email_now}**")
        with st.expander("🔑 Change password"):
            with st.form("chpw", clear_on_submit=True):
                cur = st.text_input("Current password", type="password", help="Needed to confirm it is really you.")
                new1 = st.text_input("New password", type="password", help="Any length, any characters.")
                new2 = st.text_input("Confirm new password", type="password", help="Type the new password again.")
                if st.form_submit_button("Change password", type="primary", width="stretch"):
                    ok, msg = auth.change_password(u, cur, new1, new2)
                    (st.success if ok else st.error)(msg)
        with st.expander("✉️ Change email"):
            with st.form("chem", clear_on_submit=True):
                new_email = st.text_input("New email", help="Used for confirmation codes and password resets, so it must be an address you can open.")
                pw_e = st.text_input("Your password", type="password", key="chem_pw", help="Needed to confirm it is really you.")
                if st.form_submit_button("Update email", type="primary", width="stretch"):
                    ok, msg = auth.change_email(u, pw_e, new_email)
                    (st.success if ok else st.error)(msg)
        with st.expander("📬 Check that emails reach you"):
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
                    st.error(err) if err else st.success(f"Test email sent to {email_now}. Check your inbox (and spam folder).")
        with st.expander("🗑 Delete my account"):
            st.warning("This permanently deletes your account, classes, grades and files.")
            pw_d = st.text_input("Your password", type="password", key="del_pw", help="Needed to confirm it is really you.")
            sure = st.checkbox("I understand this cannot be undone", key="del_sure")
            if st.button("Delete my account permanently", disabled=not (sure and pw_d)):
                who, _ = auth.authenticate(u, pw_d)
                if not who:
                    st.error("Your password is incorrect.")
                else:
                    auth.delete_member(u)
                    _clear_user_state()
                    st.rerun(scope="app")
        if st.button("Log out", width="stretch", key="s_logout"):
            _clear_user_state()
            st.rerun(scope="app")

    with t_data:
        st.markdown("**⬇ Download your data**")
        st.caption("Your classes, grades, scores, grading rules and preferences as a JSON file (file names only, not file contents).")
        st.download_button("⬇ Download my data (JSON)", json.dumps(_export_my_data(u), indent=2), file_name=f"{u}_grades_data.json",
                           mime="application/json", type="primary", width="stretch")
        st.divider()
        st.markdown("**🧹 Clear grades**")
        st.caption("Removes the grade you typed for every class and all recorded test scores. Your classes stay.")
        sure_g = st.checkbox("Yes, clear all my grades", key="s_sure_grades")
        if st.button("Clear all my grades", disabled=not sure_g, width="stretch"):
            for r in overview.class_table(u):
                cdb.delete_final(u, r["name"])
            for g in cdb.list_grades(u):
                cdb.delete_grade(u, g["id"])
            st.session_state["settings_flash"] = "All grades cleared."
            _reopen_settings(_ST_TABS[3])


IS_ADMIN = auth.is_admin(user)
TAB_NAMES = ["✏️ My grades", "📝 Report card", "🎯 GPA", "⚙️ Grading rules", "📚 My classes", "📁 Files", "🤖 Assistant"]
if IS_ADMIN:
    TAB_NAMES.append("🛠 Admin")
_tabs = st.tabs(TAB_NAMES)
tab_grades, tab_report, tab_gpa, tab_rules, tab_classes, tab_files, tab_ai = _tabs[:7]
if IS_ADMIN:
    tab_admin = _tabs[7]
scale, rules = prefs_db.load(user)
gpa_scale, gpa_levels = prefs_db.load_gpa(user)
my = cdb.list_classes(user)

# ---- My grades tab (the one place you type grades; every other tab reads from it)
with tab_grades:
    st.markdown("#### ✏️ My grades")
    st.caption("Type your grade for each class: a **letter** (A, B+) or a **percentage** (87 or 87%). Your Report card, "
               "GPA, summary bar, My classes, assistant and profile all update from this, all at once.")
    if not CT:
        st.info("You have no classes yet. Add them in the **📚 My classes** tab first, then come back and enter a grade for each.")
    else:
        _lvl_names = [l["level"] for l in gpa_levels]
        with st.form("my_grades"):
            _edited = st.data_editor(
                pd.DataFrame({"Class": [r["name"] for r in CT], "Status": [r["status"].title() for r in CT],
                              "Grade": [r["entered_text"] for r in CT], "Credits": [r["credits"] for r in CT],
                              "Level": [r["level"] for r in CT]}),
                num_rows="fixed", hide_index=True, width="stretch", disabled=["Class", "Status"],
                column_config={
                    "Class": st.column_config.TextColumn(help="Add or remove classes in the My classes tab."),
                    "Status": st.column_config.TextColumn(help="Current = taking now. Previous = finished."),
                    "Grade": st.column_config.TextColumn(help="Your grade for this class: a letter from your GPA scale (A, B+...) "
                                                              "or a percentage (87 or 87%). Leave empty if you have no grade yet."),
                    "Credits": st.column_config.NumberColumn(min_value=0.5, max_value=20.0, step=0.5,
                                                             help="How much the class counts in your GPA. A full-year class is usually 1, a semester 0.5."),
                    "Level": st.column_config.SelectboxColumn(options=_lvl_names, required=True,
                                                              help="Regular, Honors, AP / IB... harder levels add bonus points to the weighted GPA."),
                })
            _save_g = st.form_submit_button("Save grades", type="primary", width="stretch",
                                            help="Updates every tab at once.")
        if _save_g:
            _errs, _plan = [], []
            for rec in _edited.to_dict("records"):
                _p, _l, _e = overview.parse_grade(rec["Grade"], gpa_scale)
                if _e:
                    _errs.append(f"**{rec['Class']}**: {_e}")
                else:
                    _plan.append((rec, _p, _l))
            if _errs:
                st.error("  \n".join(_errs))
            else:
                for rec, _p, _l in _plan:
                    if _p is None and not _l:
                        cdb.delete_final(user, rec["Class"])
                    else:
                        _cr = rec["Credits"] if rec["Credits"] == rec["Credits"] and rec["Credits"] else 1.0
                        cdb.set_final(user, rec["Class"], _p, _l, _cr, rec["Level"] if rec["Level"] in _lvl_names else None)
                st.toast("Grades saved. Every tab is updated.")
                st.rerun()
        s1, s2, s3 = st.columns(3)
        s1.metric("Average", "—" if SUM["avg_percent"] is None else f"{SUM['avg_percent']:g}%",
                  help="Average of the percentages of all your graded classes.")
        s2.metric("GPA", "—" if SUM["gpa"] is None else f"{SUM['gpa']:.2f}",
                  help="Unweighted GPA on your GPA scale, across all graded classes (current and previous).")
        s3.metric("Weighted GPA", "—" if SUM["gpa_weighted"] is None else f"{SUM['gpa_weighted']:.2f}",
                  help="Like GPA, but Honors / AP classes add bonus points.")
        st.markdown("##### How your grades are used")
        st.dataframe(pd.DataFrame([{
            "Class": r["name"], "Your grade": r["entered_text"] or "—",
            "Percent": "—" if r["percent"] is None else f"{r['percent']:g}%",
            "GPA letter": r["gpa_letter"] or "—",
            "Report card grade": "—" if r["percent"] is None else (r["entered_letter"] or grading.grade_for(scale, r["percent"])[0]),
            "From": {"entered": "your grade", "tests": "test average"}.get(r["source"], "—"),
        } for r in CT]), width="stretch", hide_index=True)
        st.caption("A letter is turned into a percentage with your GPA scale (the lowest % that earns it), and a percentage "
                   "into a letter the same way. If a class has no grade here, the average of its recorded test scores is used.")


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
    with st.container(border=True, key="card_1"):
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
            col.metric(label, value, help=RESULT_HELP.get(label))

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
    mode = st.radio("Show grades as", prefs_db.DISPLAY_MODES, horizontal=True, key="display_mode",
                    help="How results are shown: letter grades (A, B+), percentages (85%), or both. Saved to your account.")
    if mode != _saved_mode:
        prefs_db.save_display(user, mode)
    with st.form("student"):
        st.markdown("##### Student details")
        c1, c2 = st.columns(2)
        name = c1.text_input("Student name", help="Whose report card this is. Printed at the top.")
        roll = c2.text_input("Roll / ID number", help="Optional. The student's roll number or ID, shown on the report card.")
        cls = c1.text_input("Class / Grade", help="Optional. The year or section, for example 10-B.")
        exam = c2.text_input("Exam", help="Optional title shown under REPORT CARD, for example Final Term 2026.")

        st.markdown("##### Subject marks")
        _pf = overview.report_prefill(user)
        subjects = [n for n, _p in _pf] or DEFAULT_SUBJECTS
        _marks = [p for _n, p in _pf] or [None] * len(subjects)
        if any(p is not None for p in _marks):
            st.caption("Marks are filled in from your **✏️ My grades** tab (as a percentage out of 100). Change a grade there "
                       "and this updates. You can still edit the table. Hover a column heading for help.")
        elif my["current"]:
            st.caption("Pre-filled with your current classes. Enter your grades in the **✏️ My grades** tab to fill in the marks. Hover a column heading for help.")
        else:
            st.caption("Add or delete rows as needed. Hover a column heading for help. Add your classes in the My classes tab to pre-fill these.")
        table = st.data_editor(
            pd.DataFrame({"Subject": subjects, "Marks": _marks,
                          "Max": [100.0] * len(subjects)}),
            num_rows="dynamic", width="stretch", hide_index=True,
            column_config={
                "Subject": st.column_config.TextColumn(help="Name of the subject."),
                "Marks": st.column_config.NumberColumn(min_value=0.0, help="Marks the student scored in this subject."),
                "Max": st.column_config.NumberColumn(min_value=1.0, help="Total marks possible in this subject, for example 100."),
            },
        )
        submitted = st.form_submit_button("Generate report card", type="primary", width="stretch",
                                          help="Works out each subject's percentage and grade, the total, and PASS or FAIL using your Grading rules.")

    if submitted:
        if not name.strip():
            st.error("Please enter the student's name.")
        else:
            res, err = grading.compute_result(table.to_dict("records"), scale, rules)
            if err:
                st.error(err)
                st.session_state.pop("last_report", None)
            else:
                res = overview.apply_entered_letters(user, res)
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
    with st.container(border=True, key=f"card_classes_{status}"):
        st.markdown(f"#### {title} ({len(my[status])})")
        if not my[status]:
            st.caption(empty_msg)
        for n in my[status]:
            a, b, c = st.columns([5, 3, 1], vertical_alignment="center")
            _r = CLS_BY.get(n.lower())
            _g = f" · {_r['gpa_letter'] or ''} {_r['percent']:g}%" if _r and _r["percent"] is not None else (
                f" · {_r['gpa_letter']}" if _r and _r["gpa_letter"] else "")
            a.markdown(f"<span class='chip'>{html.escape(n)}{html.escape(_g)}</span>", unsafe_allow_html=True)
            b.button(move_label, key=f"mv_{status}_{n}", on_click=_move, args=(n, other),
                     width="stretch", help=f"Move to {other} classes")
            c.button("🗑", key=f"rm_{status}_{n}", on_click=_delete, args=(n,),
                     width="stretch", help="Remove")


with tab_classes:
    _class_list("📘 Current classes", "current", "No current classes yet — add some below.")
    _class_list("📗 Previous classes", "previous", "No previous classes yet.")
    with st.form("add_class", clear_on_submit=True):
        st.markdown("##### Add classes")
        names = st.text_input("Class name(s)", placeholder="Separate several with commas",
                              help="One class, or several separated by commas, for example Math, Physics.")
        where = st.radio("Add to", ["Current", "Previous"], horizontal=True,
                         help="Current = classes you are taking now. Previous = classes you have finished.")
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
            g_class = g1.selectbox("Class", all_classes, help="Which class this score belongs to.")
            g_marks = g2.number_input("Marks", min_value=0.0, value=None, step=0.5, placeholder="e.g. 45", help="The marks you got.")
            g_max = g3.number_input("Out of", min_value=1.0, value=100.0, step=1.0, help="The most you could have got, for example 50 for a quiz marked out of 50.")
            g_label = g4.text_input("Label (optional)", placeholder="Unit 3 test", help="A note to remember which test or assignment this was.")
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
        uploads = st.file_uploader("Add files", accept_multiple_files=True,
                                    help="Any file type (PDF, Word, images, notes). Up to 10 MB each. Only you can see your files.")
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
    api_key, ai_model = _ai_settings()
    st.markdown('<div class="ai-hero"><div class="orb">✨</div><div><b>Study assistant</b><br>'
                '<span>Tell me what you need. I can record grades, build study plans, make report cards, '
                'change your settings and move you around the app.</span></div></div>', unsafe_allow_html=True)
    use_claude = False
    if api_key:  # an API key is only ever configured on purpose
        use_claude = st.radio("Assistant", ["Built-in assistant", "Claude AI (uses your API credits)"],
                              horizontal=True, key="ai_mode",
                              help="Built-in: works with short commands and costs nothing. Claude AI: understands free-form questions but uses the app owner's API credits.").startswith("Claude")
    if use_claude:
        st.caption("Your messages, grades and any file I read are sent to Anthropic's Claude. "
                   "I can't change passwords or delete accounts or files.")
    st.session_state.setdefault("ai_msgs", [])
    st.session_state.setdefault("ai_log", [])
    st.session_state.setdefault("ai_usage", [0, 0])
    typing_on = UI["animations"] and UI["typing_fx"]
    stream_idx = st.session_state.pop("ai_stream", None)

    if not st.session_state["ai_log"]:
        with st.chat_message("assistant", avatar="✨"):
            st.markdown(f"Hi **{user}**! 👋 What would you like to do? You can say things like "
                        "*\"I got 45/50 in math\"*, *\"make me a study plan\"* or *\"turn animations off\"*. "
                        "Type **help** to see everything I can do.")
    for idx, m in enumerate(st.session_state["ai_log"]):
        with st.chat_message(m["role"], avatar="🧑‍🎓" if m["role"] == "user" else "✨"):
            if m.get("actions"):
                st.markdown("".join(f'<span class="act">{html.escape(x)}</span>' for x in m["actions"]), unsafe_allow_html=True)
            if idx == stream_idx and typing_on and m["role"] == "assistant":
                st.write_stream(_typewriter(m["text"]))
            else:
                st.markdown(m["text"])

    if not st.session_state["ai_log"]:
        sugg = [("📅 Study plan", "Make me a weekly study plan and save it"), ("📈 How am I doing?", "How am I doing?"),
                ("🎯 My GPA", "What's my GPA?"), ("💡 How to improve", "How can I improve?"),
                ("🧾 Make a report card", "Make a report card"), ("❓ What can you do?", "help")]
        for row in (sugg[:3], sugg[3:]):
            for col, (label, text) in zip(st.columns(3), row):
                if col.button(label, width="stretch", key=f"sg_{label}"):
                    st.session_state["ai_pending"] = text
    typed = st.chat_input("Ask me to do something…  e.g. I got 45/50 in math", max_chars=ai.MAX_USER_CHARS)
    prompt = typed or st.session_state.pop("ai_pending", None)
    if prompt:
        res = None
        if not use_claude:
            res = helper.handle(user, prompt, TAB_MAP, st.session_state.setdefault("ai_state", {}))
            res["usage"] = (0, 0)
        else:
            turns = sum(1 for m in st.session_state["ai_log"] if m["role"] == "user")
            rate_err = ai.check_rate(user) if turns < ai.MAX_TURNS_PER_CHAT else None
            if turns >= ai.MAX_TURNS_PER_CHAT:
                st.warning("This chat is getting long. Press **New chat** to start fresh.")
            elif rate_err:
                st.error(rate_err)
            else:
                with st.spinner("Thinking…"):
                    res = ai.chat_turn(_ai_client(api_key), ai_model, user, st.session_state["ai_msgs"], prompt, TAB_MAP)
        if res is not None:
            if res["error"]:
                st.error(res["error"])
            elif res.get("clear"):
                for k in ("ai_msgs", "ai_log", "ai_usage", "ai_state"):
                    st.session_state.pop(k, None)
                st.rerun()
            elif res.get("logout"):
                _clear_user_state()
                st.rerun()
            else:
                st.session_state["ai_log"] += [{"role": "user", "text": prompt},
                                               {"role": "assistant", "text": res["text"], "actions": res["actions"]}]
                st.session_state["ai_stream"] = len(st.session_state["ai_log"]) - 1
                st.session_state["ai_usage"][0] += res["usage"][0]
                st.session_state["ai_usage"][1] += res["usage"][1]
                if res.get("report"):
                    st.session_state["last_report"] = res["report"]
                if res.get("set_state"):
                    st.session_state["_pending_state"] = {**st.session_state.get("_pending_state", {}), **res["set_state"]}
                if res["nav"]:
                    st.session_state["goto"] = res["nav"]
                if res.get("open_settings"):
                    st.session_state["open_settings"] = True
                    if res.get("settings_tab"):
                        st.session_state["settings_tab"] = res["settings_tab"]
                st.rerun()
    if st.session_state["ai_log"]:
        n1, n_undo, n2 = st.columns([2, 1.2, 1], vertical_alignment="center")
        if use_claude:
            u_in, u_out = st.session_state["ai_usage"]
            n1.caption(f"Model: {ai_model} · tokens used this chat: {u_in:,} in / {u_out:,} out")
        else:
            n1.caption("Tip: say `undo` (or press the button) to reverse my last change. Type `help` to see what I can do.")
        if st.session_state.get("ai_state", {}).get("undo") and n_undo.button(
                "↩ Undo last change", width="stretch", key="ai_undo_btn", help="Reverses the last change I made for you."):
            st.session_state["ai_pending"] = "undo"
            st.rerun()
        if n2.button("New chat", width="stretch"):
            for k in ("ai_msgs", "ai_log", "ai_usage", "ai_state"):
                st.session_state.pop(k, None)
            st.rerun()


# ---- GPA tab
with tab_gpa:
    st.markdown("#### GPA calculator")
    gmode = st.radio("Enter grades as", ["Letter grades", "Percentages"], horizontal=True, key="gpa_mode",
                     help="Letter grades: pick A, B+, etc. Percentages: type 0-100 and it is converted to a letter with the cut-offs in your GPA scale.")
    st.caption("Uses your GPA scale. Weighted GPA adds each course level's bonus (no bonus for a 0-point grade). "
               "Leave a grade empty for courses still in progress. Hover a column heading for help. Change the scale, bonuses and "
               "percentage cut-offs in the Grading rules tab."
               + (" Percentages are converted to letters using your cut-offs." if gmode == "Percentages" else ""))
    level_names = [l["level"] for l in gpa_levels]
    _pre = overview.gpa_prefill(user)
    n = max(len(_pre), 4)
    _pad = n - len(_pre)
    names = [r["Course"] for r in _pre] + [""] * _pad
    _credits = [r["Credits"] for r in _pre] + [1.0] * _pad
    _levels = [r["Level"] for r in _pre] + [level_names[0]] * _pad
    if _pre:
        st.caption("Filled in from your **✏️ My grades** tab, so it updates whenever you change a grade there.")
    if gmode == "Letter grades":
        gdf = pd.DataFrame({"Course": names, "Grade": [r["Grade"] for r in _pre] + [None] * _pad,
                            "Credits": _credits, "Level": _levels})
        gcfg = {"Grade": st.column_config.SelectboxColumn(options=[g["grade"] for g in gpa_scale], help="The final letter grade. Leave empty if the course is not finished yet.")}
    else:
        gdf = pd.DataFrame({"Course": names, "Percent": [r["Percent"] for r in _pre] + [None] * _pad,
                            "Credits": _credits, "Level": _levels})
        gcfg = {"Percent": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=0.5, help="Final percentage (0-100). Converted to a letter using your GPA scale. Leave empty if not finished.")}
    with st.form("gpa"):
        gtable = st.data_editor(
            gdf, num_rows="dynamic", width="stretch", hide_index=True,
            column_config={**gcfg,
                           "Course": st.column_config.TextColumn(help="Name of the course."),
                           "Credits": st.column_config.NumberColumn(min_value=0.0, step=0.5, help="How much the course counts. A full-year course is usually 1, a semester 0.5."),
                           "Level": st.column_config.SelectboxColumn(options=level_names, required=True, help="Regular, Honors, AP / IB... Harder levels add bonus points to the weighted GPA.")},
        )
        calc = st.form_submit_button("Calculate GPA", type="primary", width="stretch",
                                    help="Averages the grade points of your graded courses, weighted by credits.")
    if calc:
        g, gerr = gpa_lib.compute_gpa(gtable.to_dict("records"), gpa_scale, gpa_levels)
        if gerr:
            st.error(gerr)
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Unweighted GPA", f"{g['unweighted']:.2f}", help="GPA on the standard scale where every course counts the same, whatever its difficulty.")
            m2.metric("Weighted GPA", f"{g['weighted']:.2f}", help="Like unweighted, but Honors / AP courses add bonus points (set in the Grading rules tab). Can go above 4.0.")
            m3.metric("Credits counted", f"{g['credits']:g}", help="Total credits of the courses that have a grade. Courses left empty are skipped.")
            st.dataframe(pd.DataFrame(g["rows"]), width="stretch", hide_index=True)


# ---- Grading rules tab
with tab_rules:
    st.markdown("#### Your grading rules")
    st.caption("These decide the grade letters and the pass/fail result on your report cards. "
               "Edit the table, add or delete rows, then save. Hover a column heading or a ? for help.")
    with st.form("rules"):
        edited = st.data_editor(
            pd.DataFrame({"Grade": [g["grade"] for g in scale],
                          "Minimum %": [g["min"] for g in scale],
                          "Remark": [g["remark"] for g in scale]}),
            num_rows="dynamic", width="stretch", hide_index=True,
            column_config={"Grade": st.column_config.TextColumn(help="The letter or label, for example A+ or Distinction."),
                           "Minimum %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=0.5, help="The lowest percentage that earns this grade. 90 means 90% and above. One grade must start at 0."),
                           "Remark": st.column_config.TextColumn(help="Optional short comment shown with the result, for example Excellent.")},
        )
        c1, c2 = st.columns(2)
        ps = c1.number_input("Pass mark per subject (%)", 0.0, 100.0, float(rules["pass_subject"]), 0.5,
                             help="A subject counts as passed when the student scores at least this percentage in it.")
        po = c2.number_input("Pass mark overall (%)", 0.0, 100.0, float(rules["pass_overall"]), 0.5,
                             help="The whole report card passes only when the overall percentage reaches this.")
        req = st.checkbox("Must pass every subject to pass overall", value=rules["require_all"],
                          help="When on, failing even one subject fails the whole report card, even if the overall percentage is high.")
        save_rules = st.form_submit_button("Save grading rules", type="primary", width="stretch",
                                           help="Applies to every report card you make from now on.")
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
            column_config={"Grade": st.column_config.TextColumn(help="A letter in the GPA scale, for example A- or B+."),
                           "Points": st.column_config.NumberColumn(min_value=0.0, max_value=10.0, step=0.1, help="GPA points this grade is worth. On the standard scale, A = 4.0."),
                           "Minimum %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=0.5, help="Lowest percentage that earns this grade when you enter percentages in the GPA tab. Leave empty if it should never come from a percentage. One grade must be 0.")},
        )
        st.markdown("**Course levels (weighted bonus)**")
        lv = st.data_editor(
            pd.DataFrame({"Level": [l["level"] for l in gpa_levels], "Bonus": [l["bonus"] for l in gpa_levels]}),
            num_rows="dynamic", width="stretch", hide_index=True, key="lv_editor",
            column_config={"Level": st.column_config.TextColumn(help="A course type, for example Honors or AP / IB."),
                           "Bonus": st.column_config.NumberColumn(min_value=0.0, max_value=5.0, step=0.1, help="Extra points added to the weighted GPA for courses of this level. No bonus is added to a 0-point grade.")},
        )
        save_gpa_rules = st.form_submit_button("Save GPA scale", type="primary", width="stretch",
                                               help="Changes how the GPA tab and the assistant calculate GPA.")
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


# ---- Admin tab (only on the admin's own device)
if IS_ADMIN:
    with tab_admin:
        members = auth.list_members()
        st.markdown(f"#### Accounts ({len(members)})")
        st.dataframe(pd.DataFrame(members, columns=["Username", "Email"]),
                     width="stretch", hide_index=True)
        others = [u for (u, _e) in members if u != user]
        with st.container(border=True, key="card_6"):
            st.markdown("##### Delete one account")
            target = st.selectbox("Account", others, index=None, placeholder="Choose an account")
            if st.button("Delete this account", disabled=target is None):
                auth.delete_member(target)
                st.rerun()
        with st.container(border=True, key="card_7"):
            st.markdown("##### Delete ALL other accounts")
            st.caption("Removes every account and its classes except yours. This cannot be undone.")
            confirm = st.text_input("Type DELETE to confirm", key="wipe_confirm")
            if st.button("Delete all other accounts", type="primary",
                         disabled=confirm != "DELETE" or not others):
                n = auth.delete_all_members(keep=user)
                st.session_state.pop("wipe_confirm", None)
                st.toast(f"Deleted {n} account(s).")
                st.rerun()


# ---- Settings window (opened from the profile menu or by the assistant)
if st.session_state.pop("open_settings", False):
    settings_dialog()

# ---- Let the assistant switch tabs (best effort: clicks the tab in the page)
_goto = st.session_state.pop("goto", None)
if _goto:
    components.html(
        "<script>setTimeout(function(){var t=[].slice.call(window.parent.document.querySelectorAll('button[role=\"tab\"]'))"
        ".filter(function(b){return b.innerText.trim()===" + json.dumps(_goto) + "})[0];if(t)t.click();},350);</script>",
        height=0)
