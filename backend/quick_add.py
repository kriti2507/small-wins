"""Quick add: turn one line of plain text ("ran 5k in 27 min") into a draft
entry for one of the user's topics.

Code finds every candidate value in the text (numbers with their units,
dates, phrases); TypeSafe's Jev model only chooses between them, so a value
is never invented. One Jev request asks every question at once: which topic,
and, for every field of every topic, which candidate fills it. A draft for
each topic comes back, so switching topics in the UI needs no second call.
"""
import logging
import os
import re
from datetime import date, timedelta

import requests

log = logging.getLogger(__name__)

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


# --- Questions and drafts -----------------------------------------------------

NONE = "_none"  # criteria key for "nothing fits"; slugs never start with "_"
TOPIC_THRESHOLD = 0.6  # below this the UI asks "Which topic?"
FIELD_THRESHOLD = 0.5  # below this a field (or the date) is left to the user
SUGGESTION_MIN = 0.1  # topics this likely lead the "Which topic?" chips
MAX_SUGGESTIONS = 3

# A unit named in a field's label -> what the field takes, first match wins.
# A bare "Duration" or "Time" reads as minutes, "Distance" as km.
FIELD_TARGETS = (
    (r"\b(min|mins|minutes?)\b", ("time", 1)),
    (r"\b(hours?|hrs?)\b", ("time", 60)),
    (r"\b(sec|secs|seconds?)\b", ("time", 1 / 60)),
    (r"\b(km|kms|kilomet(?:er|re)s?)\b", ("distance", 1)),
    (r"\b(mi|miles?)\b", ("distance", KM_PER_MILE)),
    (r"\b(met(?:er|re)s?)\b", ("distance", 0.001)),
    (r"\b(duration|time)\b", ("time", 1)),
    (r"\bdistance\b", ("distance", 1)),
)


def field_target(label):
    """What a number field measures, from its label: ("time"|"distance",
    factor from the base unit), ("count", unit name), or None for anything."""
    label = label.lower()
    for pattern, target in FIELD_TARGETS:
        if re.search(pattern, label):
            return target
    for word in re.findall(r"[a-z-]+", label):
        if word in COUNT_UNITS:
            return ("count", COUNT_UNITS[word])
    return None


def _fit(number, f):
    """number's value in f's unit, or None if f can't take it."""
    if f["type"] == "pace" or number["kind"] == "pace":
        return number["value"] if f["type"] == number["kind"] == "pace" else None
    target = field_target(f["label"])
    if number["kind"] is None or target is None:
        return number["value"]
    if target[0] == "count":
        return number["value"] if number["kind"] == "count" and number["unit"] == target[1] else None
    kind, factor = target
    return round(number["value"] / factor, 2) if number["kind"] == kind else None


def field_options(f, cands):
    """{candidate id: (value for f, description for Jev)} for every candidate
    f could take."""
    if f["type"] == "text":
        return {p["id"]: (p["text"], p["text"]) for p in cands["phrases"]}
    out = {}
    for n in cands["numbers"]:
        value = _fit(n, f)
        if value is not None:
            out[n["id"]] = (value, f"{n['label']} (written “{n['span']}”)")
    return out


def build_state(topics, text, today):
    return {
        "message": text,
        "today": today.isoformat(),
        "topics": [{"name": t["name"], "fields": [f["label"] for f in t["fields"]]} for t in topics],
    }


def build_questions(topics, cands, today):
    """Every question at once: the topic, each field of every topic (asked
    as if the win were logged there; only the chosen topic's are used), and
    the day when the text names one."""
    questions = {"topic": {
        "type": "choice",
        "instructions": "The user typed `message` to log a small win in their diary. "
                        "Which of their topics should it be logged under?",
        "criteria": {
            **{t["slug"]: f"{t['name']}: the win belongs under “{t['name']}”, which records "
                          + ", ".join(f["label"] for f in t["fields"]) for t in topics},
            NONE: "None of the topics fits this win",
        },
    }}
    for t in topics:
        for f in t["fields"]:
            opts = field_options(f, cands)
            if not opts:
                continue
            if f["type"] == "text":
                ask = f"which part of the message is the best “{f['label']}” for the entry?"
            else:
                ask = f"which value from the message is its “{f['label']}”?"
            questions[f"f:{t['slug']}:{f['key']}"] = {
                "type": "choice",
                "instructions": f"If the win in `message` is logged under “{t['name']}”, {ask}",
                "criteria": {**{cid: desc for cid, (_, desc) in opts.items()},
                             NONE: f"The message gives no {f['label']}"},
            }
    if cands["dates"]:
        questions["date"] = {
            "type": "choice",
            "instructions": "On which day did the win in `message` happen? `today` is the day it was typed.",
            "criteria": {**{d["id"]: f"{d['date']} (written “{d['span']}”)" for d in cands["dates"]},
                         "today": f"{today.isoformat()}, the day it was typed"},
        }
    return questions


def _chosen(answers, qid):
    """(choice, its probability) for a choice answer, or (None, 0)."""
    a = answers.get(qid)
    if not isinstance(a, dict):
        return None, 0
    c = a.get("choice")
    probs = a.get("probabilities") or {}
    return c, probs.get(c, 0) if isinstance(probs, dict) else 0


def _topic_draft(t, cands, answers, text):
    values = {}
    for f in t["fields"]:
        opts = field_options(f, cands)
        c, p = _chosen(answers, f"f:{t['slug']}:{f['key']}")
        if c in opts and p >= FIELD_THRESHOLD:
            values[f["key"]] = opts[c][0]
    first_text = next((f for f in t["fields"] if f["type"] == "text"), None)
    if first_text and first_text["key"] not in values:
        values[first_text["key"]] = text
    return values


def _draft_date(cands, answers, today):
    by_id = {d["id"]: d["date"] for d in cands["dates"]}
    c, p = _chosen(answers, "date")
    if p >= FIELD_THRESHOLD and (c in by_id or c == "today"):
        return by_id.get(c, today.isoformat())
    return cands["dates"][0]["date"] if len(cands["dates"]) == 1 else today.isoformat()


def to_draft(topics, cands, answers, today):
    """The parse response: the likely topic (None when unsure), suggestions
    for the topic chips, the day, and a draft of field values per topic."""
    slugs = [t["slug"] for t in topics]
    text = cands["phrases"][0]["text"] if cands["phrases"] else ""
    c, p = _chosen(answers, "topic")
    probs = (answers.get("topic") or {}).get("probabilities") or {}
    ranked = sorted((s for s in slugs if probs.get(s, 0) >= SUGGESTION_MIN), key=lambda s: -probs[s])
    return {
        "topic": c if c in slugs and p >= TOPIC_THRESHOLD else None,
        "suggestions": ranked[:MAX_SUGGESTIONS],
        "date": _draft_date(cands, answers, today),
        "drafts": {t["slug"]: _topic_draft(t, cands, answers, text) for t in topics},
    }


# --- Jev ----------------------------------------------------------------------

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
JEV_TIMEOUT_SECONDS = 4  # past this the user is better off picking the topic
MAX_TEXT_CHARS = 500


class JevUnavailable(Exception):
    """No key, or Jev didn't answer usefully; quick add carries on without it."""


def ask_jev(state, questions):
    """Jev's answers ({question id: answer}) to one batch of questions."""
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise JevUnavailable("TYPESAFE_API_KEY is not set")
    try:
        res = requests.post(
            JEV_URL,
            json={"model": JEV_MODEL, "state": state, "questions": questions},
            headers={"Authorization": f"Bearer {key}"},
            timeout=JEV_TIMEOUT_SECONDS,
        )
        res.raise_for_status()
        answers = res.json()["answers"]
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        raise JevUnavailable(f"{type(e).__name__}: {e}") from e
    if not isinstance(answers, dict):
        raise JevUnavailable("answers is not an object")
    return answers


def parse(topics, text, today):
    """The draft for text (see to_draft). Without Jev the draft still comes
    back, just with no topic picked and only the titles filled in."""
    cands = extract_candidates(text, today)
    answers = {}
    if topics:
        try:
            answers = ask_jev(build_state(topics, text, today), build_questions(topics, cands, today))
        except JevUnavailable as e:
            log.warning("quick add without Jev: %s", e)
    return to_draft(topics, cands, answers, today)


def parse_today(value, server_today=None):
    """The user's local day as their browser sent it; the server's day if it's
    missing, malformed or more than a day off (no timezone is further)."""
    server_today = server_today or date.today()
    try:
        d = date.fromisoformat(value)
    except (TypeError, ValueError):
        return server_today
    return d if abs((d - server_today).days) <= 1 else server_today
