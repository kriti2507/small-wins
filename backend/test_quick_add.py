from datetime import date

import pytest

import quick_add as qa

TODAY = date(2026, 10, 29)  # a Thursday


def numbers(text):
    return [(n["kind"], n["value"], n["unit"]) for n in qa.extract_candidates(text, TODAY)["numbers"]]


def dates(text):
    return [d["date"] for d in qa.extract_candidates(text, TODAY)["dates"]]


def phrases(text):
    return [p["text"] for p in qa.extract_candidates(text, TODAY)["phrases"]]


# --- Numbers ------------------------------------------------------------------

def test_distance_and_minutes():
    assert numbers("ran 5k in 27 min") == [("distance", 5, None), ("time", 27, None)]


def test_miles_become_km():
    assert numbers("ran 3 miles") == [("distance", 4.83, None)]


def test_hours_and_minutes_make_one_duration():
    assert numbers("walked 1h 20m") == [("time", 80, None)]


def test_clock_duration():
    assert numbers("half marathon in 1:52:30") == [("time", 112.5, None)]


def test_pace_with_quote_marks():
    assert numbers("easy run at 8'35\" pace") == [("pace", 515, None)]


def test_pace_per_mile_becomes_per_km():
    assert numbers("8:00/mi") == [("pace", 298, None)]


def test_bare_minutes_seconds_could_be_a_time_or_a_pace():
    assert numbers("5k in 27:30") == [
        ("distance", 5, None), ("time", 27.5, None), ("pace", 1650, None),
    ]


def test_counts_keep_their_unit():
    assert numbers("read 30 pages") == [("count", 30, "pages")]
    assert numbers("10k steps") == [("count", 10000, "steps")]
    assert numbers("1 page") == [("count", 1, "pages")]


def test_a_number_without_a_unit():
    assert numbers("slept 7.5") == [(None, 7.5, None)]


def test_an_unknown_word_after_a_number_is_not_a_unit():
    assert numbers("3 times") == [(None, 3, None)]


def test_numbers_inside_dates_are_not_values():
    assert numbers("ran 5k on oct 3") == [("distance", 5, None)]
    assert numbers("2026-10-03 ran 5k") == [("distance", 5, None)]


def test_candidates_carry_ids_labels_and_spans():
    n = qa.extract_candidates("ran 5k in 27 min", TODAY)["numbers"]
    assert [(c["id"], c["label"], c["span"]) for c in n] == [
        ("n0", "5 km", "5k"), ("n1", "27 min", "27 min"),
    ]


# --- Dates --------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("walked yesterday", ["2026-10-28"]),
    ("long run last night", ["2026-10-28"]),
    ("ran this morning", ["2026-10-29"]),
    ("yoga on monday", ["2026-10-26"]),
    ("yoga last thursday", ["2026-10-22"]),
    ("yoga thursday", ["2026-10-29"]),
    ("swam 3 days ago", ["2026-10-26"]),
    ("hike on oct 3", ["2026-10-03"]),
    ("hike on 3rd october", ["2026-10-03"]),
    ("dinner on dec 25", ["2025-12-25"]),
    ("2026-10-03 hike", ["2026-10-03"]),
    ("2026-11-05 hike", []),
    ("feb 30 hike", []),
    ("ran 5k", []),
])
def test_dates(text, expected):
    assert dates(text) == expected


def test_the_same_day_twice_is_one_candidate():
    assert dates("yesterday, last night") == ["2026-10-28"]


# --- Phrases ------------------------------------------------------------------

def test_phrases_are_the_whole_text_then_its_clauses():
    assert phrases("ran 5k in 27 min, legs felt great and slept well") == [
        "Ran 5k in 27 min, legs felt great and slept well",
        "Ran 5k in 27 min", "Legs felt great", "Slept well",
    ]


def test_a_single_clause_is_one_phrase():
    assert phrases("made lasagna") == ["Made lasagna"]


def title(text):
    return qa.extract_candidates(text, TODAY)["title"]


@pytest.mark.parametrize("text, expected", [
    ("i did a 30 min workout today", "30 min workout"),
    ("finally finished Dune, 40 pages", "Finished Dune"),
    ("went for a walk yesterday", "Walk"),
    ("I just had a great run!", "Great run"),
    ("ran 5k on monday", "Ran 5k"),
    ("did yoga this morning lol", "Yoga"),
    ("made lasagna", "Made lasagna"),
    ("did my homework finally", "Homework"),
    ("today", "Today"),  # nothing left once trimmed: keep what was typed
])
def test_the_title_is_the_first_clause_without_filler(text, expected):
    assert title(text) == expected


def test_trimmed_titles_are_offered_alongside_what_was_typed():
    assert phrases("i did a 30 min workout today") == ["I did a 30 min workout today", "30 min workout"]
    assert phrases("finally finished Dune, 40 pages") == [
        "Finally finished Dune, 40 pages", "Finished Dune", "Finally finished Dune", "40 pages",
    ]


# --- Fields, questions and drafts ---------------------------------------------

def field(key, label, type="number"):
    return {"key": key, "label": label, "type": type, "direction": "higher"}


TITLE = field("title", "Title", "text")
TOPICS = [
    {"slug": "workout", "name": "Workout", "fields": [TITLE, field("duration", "Duration (min)")]},
    {"slug": "journal", "name": "Journal", "fields": [TITLE]},
    {"slug": "reading", "name": "Reading", "fields": [TITLE, field("pages", "Pages")]},
    {"slug": "run", "name": "Run", "fields": [field("distance", "Distance (km)"), field("pace", "Pace", "pace")]},
]


def options(text, f):
    cands = qa.extract_candidates(text, TODAY)
    return {cid: value for cid, (value, _) in qa.field_options(f, cands).items()}


def test_options_convert_to_the_field_unit():
    assert options("walked 1h 20m", field("d", "Duration (min)")) == {"n0": 80}
    assert options("walked 1h 20m", field("h", "Hours")) == {"n0": 1.33}
    assert options("ran 5000 meters", field("k", "Distance (km)")) == {"n0": 5}


def test_a_count_field_takes_only_its_unit_or_a_bare_number():
    text = "read 30 pages in 45 min, chapter 4"
    assert options(text, field("p", "Pages")) == {"n0": 30, "n2": 4}
    assert options(text, field("d", "Duration (min)")) == {"n1": 45, "n2": 4}


def test_a_field_without_a_unit_takes_any_number():
    assert options("ran 5k in 27 min", field("x", "Effort")) == {"n0": 5, "n1": 27}


def test_only_pace_fields_take_paces():
    text = "5k in 27:30"
    assert options(text, field("p", "Pace", "pace")) == {"n2": 1650}
    assert options(text, field("d", "Duration (min)")) == {"n1": 27.5}


def test_text_fields_take_phrases():
    assert options("ran 5k, felt great", TITLE) == {"p0": "Ran 5k, felt great", "p1": "Ran 5k", "p2": "Felt great"}


def questions(text):
    return qa.build_questions(TOPICS, qa.extract_candidates(text, TODAY), TODAY)


def test_the_topic_question_lists_every_topic_and_none():
    q = questions("ran 5k in 27 min")["topic"]
    assert q["type"] == "choice"
    assert set(q["criteria"]) == {"workout", "journal", "reading", "run", "_none"}
    assert "Duration (min)" in q["criteria"]["workout"]


def test_each_field_gets_a_question_over_the_values_it_could_take():
    q = questions("ran 5k in 27 min")
    assert set(q["f:workout:duration"]["criteria"]) == {"n1", "_none"}
    assert set(q["f:run:distance"]["criteria"]) == {"n0", "_none"}
    assert set(q["f:workout:title"]["criteria"]) == {"p0", "_none"}
    assert "5 km" in q["f:run:distance"]["criteria"]["n0"]
    # Nothing in the text could be a page count or a pace.
    assert "f:reading:pages" not in q and "f:run:pace" not in q


def test_the_date_question_only_comes_with_a_date():
    assert "date" not in questions("ran 5k")
    assert set(questions("ran 5k yesterday")["date"]["criteria"]) == {"d0", "today"}


def test_state_carries_the_message_and_topics():
    state = qa.build_state(TOPICS, "ran 5k", TODAY)
    assert state["message"] == "ran 5k"
    assert state["today"] == "2026-10-29"
    assert state["topics"][0] == {"name": "Workout", "fields": ["Title", "Duration (min)"]}


def choice(c, p, others=None):
    return {"type": "choice", "choice": c, "probabilities": {c: p, **(others or {})}}


def draft(text, answers):
    return qa.to_draft(TOPICS, qa.extract_candidates(text, TODAY), answers, TODAY)


def test_a_confident_answer_makes_a_full_draft():
    d = draft("ran 5k in 27 min, legs felt great", {
        "topic": choice("workout", 0.9, {"run": 0.08}),
        "f:workout:title": choice("p1", 0.8),
        "f:workout:duration": choice("n1", 0.95),
        "f:run:distance": choice("n0", 0.9),
    })
    assert d["topic"] == "workout"
    assert d["suggestions"] == ["workout"]
    assert d["date"] == "2026-10-29"
    assert d["drafts"]["workout"] == {"title": "Ran 5k in 27 min", "duration": 27}
    # Every topic gets a draft, so the user can switch without asking again.
    assert d["drafts"]["run"] == {"distance": 5}
    assert d["drafts"]["journal"] == {"title": "Ran 5k in 27 min"}


def test_an_unsure_topic_is_left_for_the_user_with_suggestions():
    d = draft("did a thing", {"topic": choice("workout", 0.45, {"run": 0.4, "reading": 0.05})})
    assert d["topic"] is None
    assert d["suggestions"] == ["workout", "run"]


def test_none_of_these_means_no_topic():
    d = draft("did a thing", {"topic": choice("_none", 0.9, {"journal": 0.1})})
    assert d["topic"] is None
    assert d["suggestions"] == ["journal"]


def test_an_unsure_field_stays_blank():
    d = draft("ran 5k in 27 min", {"topic": choice("workout", 0.9), "f:workout:duration": choice("n1", 0.3)})
    assert d["drafts"]["workout"] == {"title": "Ran 5k in 27 min"}


def test_a_field_answer_naming_an_unknown_candidate_is_ignored():
    d = draft("ran 5k in 27 min", {"f:workout:duration": choice("n9", 0.9)})
    assert "duration" not in d["drafts"]["workout"]


def test_the_title_falls_back_to_the_trimmed_first_clause():
    d = draft("i ran 5k, felt great", {"f:workout:title": choice("_none", 0.9)})
    assert d["drafts"]["workout"]["title"] == "Ran 5k"


def test_the_first_text_field_is_asked_for_a_short_heading():
    q = questions("ran 5k in 27 min")
    assert "short" in q["f:workout:title"]["instructions"]


def test_the_date_comes_from_the_answer():
    assert draft("swam yesterday", {"date": choice("d0", 0.9)})["date"] == "2026-10-28"
    assert draft("swam yesterday", {"date": choice("today", 0.9)})["date"] == "2026-10-29"


def test_without_a_date_answer_a_single_date_found_is_used():
    assert draft("swam yesterday", {})["date"] == "2026-10-28"
    assert draft("swam yesterday, ran on monday", {})["date"] == "2026-10-29"


def test_no_answers_at_all_still_drafts_the_titles():
    d = draft("ran 5k", {})
    assert d["topic"] is None and d["suggestions"] == []
    assert d["drafts"] == {"workout": {"title": "Ran 5k"}, "journal": {"title": "Ran 5k"},
                           "reading": {"title": "Ran 5k"}, "run": {}}


# --- Jev client and parse -----------------------------------------------------

class FakeResponse:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise qa.requests.HTTPError(f"{self.status_code}")

    def json(self):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data


def test_ask_jev_needs_a_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(qa.JevUnavailable):
        qa.ask_jev({}, {})


def test_ask_jev_posts_the_questions_and_returns_the_answers(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "k-123")
    calls = []

    def post(url, json, headers, timeout):
        calls.append((url, json, headers, timeout))
        return FakeResponse({"answers": {"topic": choice("workout", 0.9)}})

    monkeypatch.setattr(qa.requests, "post", post)
    assert qa.ask_jev({"message": "hi"}, {"topic": {}}) == {"topic": choice("workout", 0.9)}
    url, body, headers, timeout = calls[0]
    assert url == "https://api.typesafe.ai/v1/systemone"
    assert body == {"model": "jev-latest", "state": {"message": "hi"}, "questions": {"topic": {}}}
    assert headers["Authorization"] == "Bearer k-123"
    assert timeout == qa.JEV_TIMEOUT_SECONDS


@pytest.mark.parametrize("response", [
    FakeResponse({"error": "bad"}, status=422),
    FakeResponse(ValueError("not json")),
    FakeResponse({"no": "answers"}),
    FakeResponse({"answers": ["not", "a", "dict"]}),
])
def test_ask_jev_turns_failures_into_unavailable(monkeypatch, response):
    monkeypatch.setenv("TYPESAFE_API_KEY", "k-123")
    monkeypatch.setattr(qa.requests, "post", lambda *a, **kw: response)
    with pytest.raises(qa.JevUnavailable):
        qa.ask_jev({}, {})


def test_ask_jev_turns_timeouts_into_unavailable(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "k-123")

    def post(*a, **kw):
        raise qa.requests.Timeout("slow")

    monkeypatch.setattr(qa.requests, "post", post)
    with pytest.raises(qa.JevUnavailable):
        qa.ask_jev({}, {})


def test_parse_asks_jev_once_and_drafts_from_its_answers(monkeypatch):
    seen = []

    def ask(state, questions):
        seen.append((state, questions))
        return {"topic": choice("workout", 0.9), "f:workout:duration": choice("n1", 0.9)}

    monkeypatch.setattr(qa, "ask_jev", ask)
    d = qa.parse(TOPICS, "ran 5k in 27 min", TODAY)
    assert d["topic"] == "workout"
    assert d["drafts"]["workout"]["duration"] == 27
    assert len(seen) == 1 and seen[0][0]["message"] == "ran 5k in 27 min"
    assert "f:workout:duration" in seen[0][1]


def test_parse_without_jev_still_drafts(monkeypatch):
    def ask(state, questions):
        raise qa.JevUnavailable("no key")

    monkeypatch.setattr(qa, "ask_jev", ask)
    d = qa.parse(TOPICS, "journaled yesterday", TODAY)
    assert d["topic"] is None and d["suggestions"] == []
    assert d["date"] == "2026-10-28"
    assert d["drafts"]["journal"] == {"title": "Journaled"}


def test_parse_with_no_topics_skips_jev(monkeypatch):
    monkeypatch.setattr(qa, "ask_jev", lambda *a: pytest.fail("asked Jev"))
    assert qa.parse([], "ran", TODAY)["drafts"] == {}


@pytest.mark.parametrize("value, expected", [
    ("2026-10-29", date(2026, 10, 29)),
    ("2026-10-30", date(2026, 10, 30)),  # ahead of the server's day: another timezone
    ("2026-10-28", date(2026, 10, 28)),
    ("2026-10-20", TODAY),
    ("not a date", TODAY),
    (None, TODAY),
    (20261029, TODAY),
])
def test_parse_today_trusts_the_client_within_a_day(value, expected):
    assert qa.parse_today(value, TODAY) == expected


# --- Clear enough to save without asking ---------------------------------------

def test_a_confident_parse_is_clear():
    d = draft("ran 5k in 27 min", {"topic": choice("workout", 0.9), "f:workout:duration": choice("n1", 0.9)})
    assert d["clear"] is True


def test_a_likely_but_not_sure_topic_is_prefilled_but_not_clear():
    d = draft("ran 5k in 27 min", {"topic": choice("workout", 0.7), "f:workout:duration": choice("n1", 0.9)})
    assert d["topic"] == "workout"
    assert d["clear"] is False


def test_an_unsure_value_is_not_clear():
    d = draft("ran 5k in 27 min", {"topic": choice("workout", 0.9), "f:workout:duration": choice("n1", 0.6)})
    assert d["clear"] is False


def test_an_unanswered_value_is_not_clear():
    assert draft("ran 5k in 27 min", {"topic": choice("workout", 0.9)})["clear"] is False


def test_a_confident_not_mentioned_is_clear():
    d = draft("ran 5k in 27 min", {"topic": choice("workout", 0.9), "f:workout:duration": choice("_none", 0.9)})
    assert d["clear"] is True


def test_nothing_to_fill_is_clear():
    assert draft("did yoga", {"topic": choice("workout", 0.9)})["clear"] is True


def test_an_unsure_day_is_not_clear():
    sure = {"topic": choice("journal", 0.9), "date": choice("d0", 0.9)}
    unsure = {"topic": choice("journal", 0.9), "date": choice("d0", 0.6)}
    assert draft("journaled yesterday", sure)["clear"] is True
    assert draft("journaled yesterday", unsure)["clear"] is False


def test_without_answers_nothing_is_clear():
    assert draft("ran 5k", {})["clear"] is False
