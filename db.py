import os
import datetime as dt
from zoneinfo import ZoneInfo

import psycopg

IL = ZoneInfo("Asia/Jerusalem")
UTC = ZoneInfo("UTC")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Missing DATABASE_URL env var")

def _combine_local(day: dt.date, t: dt.time) -> dt.datetime:
    """Create aware datetime in Israel time, then return UTC for DB."""
    local_dt = dt.datetime.combine(day, t).replace(tzinfo=IL)
    return local_dt.astimezone(UTC)

def _duration_sec(start_ts, end_ts) -> int | None:
    if not start_ts or not end_ts:
        return None
    return int((end_ts - start_ts).total_seconds())

def get_session_by_day(day: dt.date):
    q = """
    select id, start_ts, end_ts, duration_sec, note, day_date
    from sessions
    where day_date = %s
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(q, (day,))
            return cur.fetchone()

def upsert_start(day: dt.date, t: dt.time, note: str | None = None):
    start_utc = _combine_local(day, t)
    q = """
    insert into sessions (day_date, start_ts, note, created_at)
    values (%s, %s, %s, now())
    on conflict (day_date)
    do update set
      start_ts = coalesce(sessions.start_ts, excluded.start_ts),
      note = coalesce(excluded.note, sessions.note)
    returning id, start_ts, end_ts, duration_sec, note, day_date;
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(q, (day, start_utc, note))
            row = cur.fetchone()
            conn.commit()
            return row

def set_end(day: dt.date, t: dt.time, note: str | None = None):
    end_utc = _combine_local(day, t)

    # We require start exists to compute duration properly
    sess = get_session_by_day(day)
    if not sess or not sess[1]:
        raise ValueError("אין כניסה קיימת ליום הזה. קודם דווחי כניסה.")
    if sess[2] is not None:
        raise ValueError("כבר קיימת יציאה ליום הזה.")

    start_ts = sess[1]
    duration = _duration_sec(start_ts, end_utc)
    if duration is not None and duration < 0:
        raise ValueError("שעת יציאה לא יכולה להיות לפני שעת כניסה.")

    q = """
    update sessions
    set end_ts = %s,
        duration_sec = %s,
        note = coalesce(%s, note)
    where day_date = %s
    returning id, start_ts, end_ts, duration_sec, note, day_date;
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(q, (end_utc, duration, note, day))
            row = cur.fetchone()
            conn.commit()
            return row

def update_start(day: dt.date, t: dt.time):
    start_utc = _combine_local(day, t)
    sess = get_session_by_day(day)
    if not sess:
        raise ValueError("אין רשומה ליום הזה כדי לערוך.")
    end_ts = sess[2]
    if end_ts is not None and end_ts < start_utc:
        raise ValueError("שעת כניסה לא יכולה להיות אחרי שעת יציאה.")
    duration = _duration_sec(start_utc, end_ts)

    q = """
    update sessions
    set start_ts = %s,
        duration_sec = %s
    where day_date = %s
    returning id, start_ts, end_ts, duration_sec, note, day_date;
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(q, (start_utc, duration, day))
            row = cur.fetchone()
            conn.commit()
            return row

def update_end(day: dt.date, t: dt.time):
    end_utc = _combine_local(day, t)
    sess = get_session_by_day(day)
    if not sess or not sess[1]:
        raise ValueError("אין כניסה ליום הזה. אי אפשר לערוך יציאה בלי כניסה.")
    start_ts = sess[1]
    if end_utc < start_ts:
        raise ValueError("שעת יציאה לא יכולה להיות לפני שעת כניסה.")
    duration = _duration_sec(start_ts, end_utc)

    q = """
    update sessions
    set end_ts = %s,
        duration_sec = %s
    where day_date = %s
    returning id, start_ts, end_ts, duration_sec, note, day_date;
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(q, (end_utc, duration, day))
            row = cur.fetchone()
            conn.commit()
            return row

def set_day_off(day: dt.date):
    q = """
    insert into day_flags (day_date, flag, note, created_at)
    values (%s, 'off', 'יום חופש', now())
    on conflict (day_date)
    do update set flag='off', note='יום חופש'
    returning day_date, flag, note;
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(q, (day,))
            row = cur.fetchone()
            conn.commit()
            return row

def get_day_flag(day: dt.date):
    q = "select day_date, flag, note from day_flags where day_date=%s"
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(q, (day,))
            return cur.fetchone()

def month_overview(year: int, month: int):
    # returns list of rows for the month
    first = dt.date(year, month, 1)
    if month == 12:
        nxt = dt.date(year + 1, 1, 1)
    else:
        nxt = dt.date(year, month + 1, 1)

    q = """
    select
      d.day_date,
      s.start_ts,
      s.end_ts,
      s.duration_sec,
      coalesce(df.note, s.note) as note,
      coalesce(df.flag, '') as flag
    from (
      select generate_series(%s::date, (%s::date - interval '1 day')::date, interval '1 day')::date as day_date
    ) d
    left join sessions s on s.day_date = d.day_date
    left join day_flags df on df.day_date = d.day_date
    order by d.day_date;
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(q, (first, nxt))
            return cur.fetchall()


def export_month_rows(year: int, month: int):
    q = """
    select
      s.day_date,
      s.start_ts,
      s.end_ts,
      s.duration_sec,
      coalesce(df.note, s.note) as note,
      coalesce(df.flag, '') as flag
    from sessions s
    full outer join day_flags df
      on df.day_date = s.day_date
    where
      date_trunc('month', coalesce(s.day_date, df.day_date)::timestamp) = make_date(%s, %s, 1)
    order by coalesce(s.day_date, df.day_date);
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(q, (year, month))
            return cur.fetchall()
