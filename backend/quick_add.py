"""Quick add: turn one line of plain text ("ran 5k in 27 min") into a draft
entry for one of the user's topics.

Code finds every candidate value in the text (numbers with their units,
dates, phrases); TypeSafe's Jev model only chooses between them, so a value
is never invented. One Jev request asks every question at once: which topic,
and, for every field of every topic, which candidate fills it. A draft for
each topic comes back, so switching topics in the UI needs no second call.
"""
import re
from datetime import date, timedelta

# --- Candidate extraction -----------------------------------------------------

KM_PER_MILE = 1.609344
MAX_PHRASES = 12

# Unit word after a number -> (kind, factor to the kind's base unit).
# Bases: km for distance, minutes for time.
UNITS = {
    **dict.fromkeys(("km", "kms", "kilometer", "kilometers", "kilometre", "kilometres"), ("distance", 1)),
    **dict.fromkeys(("mi", "mile", "miles"), ("distance", KM_PER_MILE)),
    **dict.fromkeys(("meter", "meters", "metre", "metres"), ("distance", 0.001)),
    **dict.fromkeys(("h", "hr", "hrs", "hour", "hours"), ("time", 60)),
    **dict.fromkeys(("m", "min", "mins", "minute", "minutes"), ("time", 1)),
    **dict.fromkeys(("s", "sec", "secs", "second", "seconds"), ("time", 1 / 60)),
}

# Things people count, each spelling -> one name. A field labelled with one
# ("Pages") only takes counts of it.
COUNT_UNITS = {
    **dict.fromkeys(("page", "pages", "pp"), "pages"),
    **dict.fromkeys(("step", "steps"), "steps"),
    **dict.fromkeys(("rep", "reps"), "reps"),
    **dict.fromkeys(("set", "sets"), "sets"),
    **dict.fromkeys(("lap", "laps"), "laps"),
    **dict.fromkeys(("chapter", "chapters"), "chapters"),
    **dict.fromkeys(("word", "words"), "words"),
    **dict.fromkeys(("glass", "glasses"), "glasses"),
    **dict.fromkeys(("cup", "cups"), "cups"),
    **dict.fromkeys(("pushup", "pushups", "push-up", "push-ups"), "push-ups"),
    **dict.fromkeys(("cal", "kcal", "calories"), "calories"),
    "kg": "kg",
    **dict.fromkeys(("lb", "lbs"), "lb"),
}

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
MONTH = (r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
         r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def _fmt(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _overlaps(span, taken):
    return any(span[0] < end and start < span[1] for start, end in taken)


def _matches(pattern, text, taken):
    """Matches of pattern not overlapping a span already taken; each one found
    is taken too, so a later, looser pattern can't reread its digits."""
    for m in re.finditer(pattern, text, re.IGNORECASE):
        if not _overlaps(m.span(), taken):
            taken.append(m.span())
            yield m


def _month_day(month, day, today):
    """The most recent month/day on or before today, or None if no such day."""
    try:
        d = date(today.year, MONTHS.index(month[:3].lower()) + 1, int(day))
    except ValueError:
        return None
    if d > today:
        try:
            d = d.replace(year=today.year - 1)
        except ValueError:  # Feb 29 a year back
            return None
    return d


def _dates(text, today, taken):
    found = []  # (start, date)

    def add(m, d):
        if d is not None and d <= today:
            found.append((m.start(), d, m.group(0)))

    for m in _matches(r"\b(today|tonight|this\s+(?:morning|afternoon|evening))\b", text, taken):
        add(m, today)
    for m in _matches(r"\b(yesterday|last\s+night)\b", text, taken):
        add(m, today - timedelta(days=1))
    for m in _matches(r"\b(\d+)\s+days?\s+ago\b", text, taken):
        add(m, today - timedelta(days=int(m.group(1))))
    for m in _matches(r"\b(last\s+)?(" + "|".join(WEEKDAYS) + r")\b", text, taken):
        back = (today.weekday() - WEEKDAYS.index(m.group(2).lower())) % 7
        add(m, today - timedelta(days=back or (7 if m.group(1) else 0)))
    for m in _matches(r"\b(\d{4})-(\d{2})-(\d{2})\b", text, taken):
        try:
            add(m, date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            pass
    for m in _matches(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + MONTH + r"\b", text, taken):
        add(m, _month_day(m.group(2), m.group(1), today))
    for m in _matches(r"\b" + MONTH + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b", text, taken):
        add(m, _month_day(m.group(1), m.group(2), today))

    out, seen = [], set()
    for _, d, span in sorted(found, key=lambda f: f[0]):
        if d not in seen:
            seen.add(d)
            out.append({"id": f"d{len(out)}", "date": d.isoformat(), "span": span})
    return out


def _number(kind, value, span, unit=None):
    value = round(value) if kind == "pace" else round(value, 2)
    if kind == "time":
        label = f"{_fmt(value)} min"
    elif kind == "distance":
        label = f"{_fmt(value)} km"
    elif kind == "pace":
        label = f"{value // 60}'{value % 60:02d}\" per km"
    elif kind == "count":
        label = f"{_fmt(value)} {unit}"
    else:
        label = _fmt(value)
    return {"kind": kind, "value": value, "unit": unit, "label": label, "span": span}


def _pace(minutes, seconds, per):
    sec = int(minutes) * 60 + int(seconds)
    return sec / KM_PER_MILE if per and per.lower().startswith("mi") else sec


def _numbers(text, taken):
    found = []  # (start, candidate)

    def add(m, *cands):
        found.extend((m.start(), c) for c in cands)

    for m in _matches(r"\b(\d{1,2}):(\d{2}):(\d{2})\b", text, taken):
        h, mi, s = (int(g) for g in m.groups())
        add(m, _number("time", h * 60 + mi + s / 60, m.group(0)))
    for m in _matches(r"\b(\d{1,2})\s*['’′]\s*(\d{2})\s*(?:\"|”|″|'')?(?:\s*(?:/\s*|per\s+)(km|mi|mile)\b)?",
                      text, taken):
        add(m, _number("pace", _pace(m.group(1), m.group(2), m.group(3)), m.group(0)))
    for m in _matches(r"\b(\d{1,2}):(\d{2})\s*(?:(?:min\s*)?(?:/\s*|per\s+)(km|mi|mile)\b|pace\b)",
                      text, taken):
        add(m, _number("pace", _pace(m.group(1), m.group(2), m.group(3)), m.group(0)))
    for m in _matches(r"\b(\d+(?:\.\d+)?)\s*(?:h|hrs?|hours?)\s*(?:and\s*)?(\d+)\s*(?:m|mins?|minutes?)\b",
                      text, taken):
        add(m, _number("time", float(m.group(1)) * 60 + int(m.group(2)), m.group(0)))
    # Bare "27:30" could be a time or a pace; offer both and let Jev pick.
    for m in _matches(r"\b(\d{1,3}):(\d{2})\b", text, taken):
        mi, s = int(m.group(1)), int(m.group(2))
        add(m, _number("time", mi + s / 60, m.group(0)), _number("pace", mi * 60 + s, m.group(0)))

    for m in re.finditer(r"(?<![\w.:'’])(\d+(?:\.\d+)?)(?:\s*(k)\b)?(?:\s*([a-z][a-z-]*))?", text, re.IGNORECASE):
        num, k, word = float(m.group(1)), m.group(2), (m.group(3) or "").lower()
        if word in COUNT_UNITS:
            end, cand = m.end(), lambda span: _number("count", num * (1000 if k else 1), span, COUNT_UNITS[word])
        elif k:
            end, cand = m.end(2), lambda span: _number("distance", num, span)
        elif word in UNITS:
            kind, factor = UNITS[word]
            end, cand = m.end(), lambda span: _number(kind, num * factor, span)
        else:
            end, cand = m.end(1), lambda span: _number(None, num, span)
        span = (m.start(), end)
        if _overlaps(span, taken):
            continue
        taken.append(span)
        found.append((m.start(), cand(text[span[0]:span[1]])))

    out = [c for _, c in sorted(found, key=lambda f: f[0])]
    for i, c in enumerate(out):
        c["id"] = f"n{i}"
    return out


def _phrases(text):
    parts = re.split(r"[,;!?\n]+|\.(?!\d)|\s+(?:and|but|then)\s+", text, flags=re.IGNORECASE)
    out, seen = [], set()
    for p in [text, *parts]:
        p = p.strip(" \t-–—")
        if len(p) < 2 or p.lower() in seen:
            continue
        seen.add(p.lower())
        out.append({"id": f"p{len(out)}", "text": p})
    return out[:MAX_PHRASES]


def extract_candidates(text, today):
    """Every value the text offers: {"numbers", "dates", "phrases"}, each a
    list of dicts with an "id" Jev's answers refer to. Dates are read first so
    their digits never come back as numbers."""
    taken = []
    found_dates = _dates(text, today, taken)
    return {"numbers": _numbers(text, taken), "dates": found_dates, "phrases": _phrases(text)}
