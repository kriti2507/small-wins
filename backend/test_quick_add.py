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
        "ran 5k in 27 min, legs felt great and slept well",
        "ran 5k in 27 min", "legs felt great", "slept well",
    ]


def test_a_single_clause_is_one_phrase():
    assert phrases("made lasagna") == ["made lasagna"]
