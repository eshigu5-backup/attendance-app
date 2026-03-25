import datetime as dt
import io
import os
import re
import time
import hmac
import hashlib
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from auth import check_login
import db

load_dotenv()

# -------------------------
# config
# -------------------------
st.set_page_config(page_title="יומן כניסה/יציאה", layout="centered")

IL = ZoneInfo("Asia/Jerusalem")

month_names = {
    1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל",
    5: "מאי", 6: "יוני", 7: "יולי", 8: "אוגוסט",
    9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר"
}

# -------------------------
# time widget (autocomplete + free typing)
# -------------------------
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def parse_hhmm(s: str) -> dt.time | None:
    s = (s or "").strip()
    m = TIME_RE.match(s)
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    return dt.time(hour=hh, minute=mm)


def time_widget(label: str, default_time: dt.time, key: str) -> dt.time:
    times = [f"{h:02d}:{m:02d}" for h in range(24) for m in range(60)]
    default_str = f"{default_time.hour:02d}:{default_time.minute:02d}"

    mode = st.radio(
        label,
        options=["בחירה מהרשימה", "הקלדה חופשית"],
        horizontal=True,
        key=f"{key}_mode",
    )

    if mode == "בחירה מהרשימה":
        chosen = st.selectbox(
            "בחרי שעה (אפשר להתחיל להקליד לחיפוש)",
            options=times,
            index=times.index(default_str),
            key=f"{key}_select",
        )
        return parse_hhmm(chosen) or default_time

    typed = st.text_input(
        "הקלידי שעה בפורמט HH:MM (לדוגמה 08:05 או 17:30)",
        value=default_str,
        key=f"{key}_text",
    )
    t = parse_hhmm(typed)
    if t is None:
        st.error("פורמט לא תקין. חייב HH:MM בין 00:00 ל-23:59")
        return default_time
    return t


# -------------------------
# auth persistence via query params (survives refresh)
# -------------------------
AUTH_SECRET = (os.getenv("AUTH_SECRET") or "").strip()
QP_KEY = "auth"  # URL param name
DAYS_VALID = 30


def _sign(payload: str) -> str:
    return hmac.new(
        AUTH_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def make_token(username: str, days_valid: int = DAYS_VALID) -> str:
    exp = int(time.time()) + days_valid * 24 * 3600
    payload = f"{username}|{exp}"
    sig = _sign(payload)
    return f"{payload}|{sig}"


def read_token(token: str) -> str | None:
    if not token or token.count("|") != 2:
        return None
    username, exp_str, sig = token.split("|", 2)
    payload = f"{username}|{exp_str}"

    if not AUTH_SECRET:
        return None

    try:
        exp = int(exp_str)
    except ValueError:
        return None

    if not hmac.compare_digest(_sign(payload), sig):
        return None
    if time.time() > exp:
        return None
    return username


def qp_get_token() -> str | None:
    t = st.query_params.get(QP_KEY, None)
    if isinstance(t, list):
        return t[0] if t else None
    return t


def qp_set_token(token: str):
    st.query_params[QP_KEY] = token


def qp_clear_token():
    qp = dict(st.query_params)
    qp.pop(QP_KEY, None)
    st.query_params.clear()
    for k, v in qp.items():
        st.query_params[k] = v


# -------------------------
# session state
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "busy" not in st.session_state:
    st.session_state.busy = False
if "username" not in st.session_state:
    st.session_state.username = ""

# Auto-login from query param (survives refresh)
if not st.session_state.logged_in:
    token = qp_get_token()
    user = read_token(token) if token else None
    if user:
        st.session_state.logged_in = True
        st.session_state.username = user

# -------------------------
# header + sidebar
# -------------------------
st.title("יומן כניסה / יציאה")

with st.sidebar:
    st.write("AUTH_SECRET loaded?", bool(AUTH_SECRET))
    st.caption("Storage mode: URL query param ✅")

    if st.session_state.logged_in:
        st.write(f"מחוברת כ: **{st.session_state.username}**")
        if st.button("התנתקות"):
            qp_clear_token()
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()

# -------------------------
# login
# -------------------------
if not st.session_state.logged_in:
    st.subheader("התחברות")
    u = st.text_input("שם משתמש")
    p = st.text_input("סיסמה", type="password")

    if st.button("התחברי"):
        if not AUTH_SECRET:
            st.error("AUTH_SECRET לא נטען. בדקי .env והריצי מחדש (Stop ואז Run).")
            st.stop()

        if check_login(u, p):
            st.session_state.logged_in = True
            st.session_state.username = u

            # persist login across refresh
            qp_set_token(make_token(u))

            st.success("התחברת ✅")
            st.rerun()
        else:
            st.error("שם משתמש / סיסמה שגויים")

    st.stop()

# -------------------------
# reporting section
# -------------------------
st.subheader("דיווח")

chosen_date = st.date_input("תאריך", value=dt.datetime.now(IL).date())

# block Saturday (by chosen date)
if chosen_date.weekday() == 5:
    st.warning("בשבת לא ניתן לדווח 🙂")
    st.stop()

sess = db.get_session_by_day(chosen_date)
flag = db.get_day_flag(chosen_date)

# status line
if flag and flag[1] == "off":
    st.info("היום מסומן כ: יום חופש 🥳")
elif sess and sess[1] and not sess[2]:
    st.info("סטטוס: יש כניסה פתוחה (אין יציאה עדיין)")
elif sess and sess[1] and sess[2]:
    st.success("סטטוס: כניסה ויציאה קיימים ליום הזה ✅")
else:
    st.write("סטטוס: אין דיווחים ליום הזה עדיין")

note = st.text_input("הערה (לא חובה)")

report_type = st.selectbox("סוג דיווח", ["כניסה", "יציאה"])

report_time = time_widget(
    "שעה",
    default_time=dt.datetime.now(IL).time().replace(second=0, microsecond=0),
    key="report_time",
)

colA, colB = st.columns(2)

with colA:
    if st.button("שמור דיווח", disabled=st.session_state.busy):
        st.session_state.busy = True
        try:
            if flag and flag[1] == "off":
                st.error("היום מסומן כיום חופש. אם זה לא נכון – בטלי יום חופש קודם.")
            else:
                if report_type == "כניסה":
                    if sess and sess[1] is not None:
                        st.error("כבר קיימת כניסה ליום הזה.")
                    else:
                        db.upsert_start(chosen_date, report_time, note=note or None)
                        st.success("כניסה נשמרה ✅")
                        st.rerun()
                else:
                    if not sess or sess[1] is None:
                        st.error("אין כניסה ליום הזה. קודם דווחי כניסה.")
                    elif sess[2] is not None:
                        st.error("כבר קיימת יציאה ליום הזה.")
                    else:
                        db.set_end(chosen_date, report_time, note=note or None)
                        st.success("יציאה נשמרה ✅")
                        st.rerun()
        except Exception as e:
            st.error(str(e))
        finally:
            st.session_state.busy = False

with colB:
    if st.button("יום חופש 🥳", disabled=st.session_state.busy):
        st.session_state.busy = True
        try:
            if sess and (sess[1] is not None or sess[2] is not None):
                st.error("כבר יש דיווחים ליום הזה. אי אפשר לסמן יום חופש.")
            else:
                db.set_day_off(chosen_date)
                st.success("סומן יום חופש 🥳")
                st.rerun()
        except Exception as e:
            st.error(str(e))
        finally:
            st.session_state.busy = False

st.divider()

# -------------------------
# daily summary + edit
# -------------------------
st.subheader("סיכום יומי")

sess = db.get_session_by_day(chosen_date)
flag = db.get_day_flag(chosen_date)


def fmt_local(ts):
    if ts is None or pd.isna(ts):
        return "-"
    return ts.astimezone(IL).strftime("%H:%M")


if flag and flag[1] == "off":
    st.write("✅ יום חופש")
else:
    if not sess:
        st.write("אין נתונים ליום הזה.")
    else:
        st.write(f"כניסה: **{fmt_local(sess[1])}**")
        st.write(f"יציאה: **{fmt_local(sess[2])}**")
        if sess[3] is not None:
            st.write(f"סה״כ: **{sess[3] / 3600:.2f} שעות**")

        st.markdown("### עריכה ✏️")
        with st.expander("עריכת דיווחים"):
            edit_type = st.selectbox("מה לערוך?", ["כניסה", "יציאה"], key="edit_type")

            new_time = time_widget(
                "שעה חדשה",
                default_time=dt.datetime.now(IL).time().replace(second=0, microsecond=0),
                key="edit_new_time",
            )

            if st.button("שמור עריכה", key="save_edit"):
                try:
                    if edit_type == "כניסה":
                        db.update_start(chosen_date, new_time)
                        st.success("שעת כניסה עודכנה ✅")
                    else:
                        db.update_end(chosen_date, new_time)
                        st.success("שעת יציאה עודכנה ✅")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

st.divider()

# -------------------------
# monthly overview + export
# -------------------------
st.subheader("לצפייה בדיווחי החודש")
show_month = st.toggle("פתח דוח חודשי", value=False)

if show_month:
    y = chosen_date.year
    m = chosen_date.month
    today = dt.date.today()

    years_options = list(range(today.year - 3, today.year + 1))
    default_year_index = years_options.index(y) if y in years_options else len(years_options) - 1

    colY, colM = st.columns(2)
    with colY:
        year = st.selectbox("שנה", options=years_options, index=default_year_index, key="month_year")
    with colM:
        month = st.selectbox(
            "חודש",
            options=list(month_names.keys()),
            format_func=lambda mm: month_names[mm],
            index=m - 1,
            key="month_month",
        )

    rows = db.month_overview(int(year), int(month))
    df = pd.DataFrame(rows, columns=["תאריך", "כניסה(UTC)", "יציאה(UTC)", "משך(שניות)", "הערה", "דגל"])

    def to_il_str(ts):
        if ts is None or pd.isna(ts):
            return ""
        return ts.astimezone(IL).strftime("%H:%M")

    df["כניסה"] = df["כניסה(UTC)"].apply(to_il_str)
    df["יציאה"] = df["יציאה(UTC)"].apply(to_il_str)
    df["שעות"] = df["משך(שניות)"].apply(lambda x: "" if x is None or pd.isna(x) else round(x / 3600, 2))

    def status_row(r):
        if r["דגל"] == "off":
            return "יום חופש 🥳"
        if r["כניסה"] and r["יציאה"]:
            return "✅"
        if r["כניסה"] and not r["יציאה"]:
            return "פתוח"
        return ""

    df["סטטוס"] = df.apply(status_row, axis=1)

    st.dataframe(df[["תאריך", "כניסה", "יציאה", "שעות", "סטטוס", "הערה"]], use_container_width=True)

    total_sec = df["משך(שניות)"].dropna().sum()
    st.write(f"סה״כ שעות חודש: **{total_sec/3600:.2f}**")

    st.subheader("ייצוא לאקסל")
    st.caption(f"ייצוא עבור: {month_names[int(month)]} {int(year)}")

    if st.button("הכן קובץ אקסל", key="export_excel"):
        rows_exp = db.export_month_rows(int(year), int(month))
        df_exp = pd.DataFrame(rows_exp, columns=["תאריך", "כניסה(UTC)", "יציאה(UTC)", "משך(שניות)", "הערה", "דגל"])

        def to_il(ts):
            if ts is None or pd.isna(ts):
                return ""
            return ts.astimezone(IL).strftime("%Y-%m-%d %H:%M")

        df_exp["כניסה (ישראל)"] = df_exp["כניסה(UTC)"].apply(to_il)
        df_exp["יציאה (ישראל)"] = df_exp["יציאה(UTC)"].apply(to_il)
        df_exp["שעות"] = df_exp["משך(שניות)"].apply(lambda x: "" if x is None or pd.isna(x) else round(x / 3600, 2))

        df_exp["סטטוס"] = df_exp.apply(
            lambda r: "יום חופש 🥳" if r["דגל"] == "off"
            else ("✅" if r["כניסה (ישראל)"] and r["יציאה (ישראל)"]
                  else ("פתוח" if r["כניסה (ישראל)"] and not r["יציאה (ישראל)"] else "")),
            axis=1
        )

        df_out = df_exp[["תאריך", "כניסה (ישראל)", "יציאה (ישראל)", "שעות", "סטטוס", "הערה"]]

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_out.to_excel(writer, index=False, sheet_name="דוח חודשי")
        buffer.seek(0)

        st.download_button(
            label="⬇️ הורד אקסל",
            data=buffer,
            file_name=f"attendance_{int(year)}-{int(month):02d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_excel",
        )
