"""Quick add against the real Jev, over the starter topics a new account
picks from. Skipped without TYPESAFE_API_KEY; run it after changing the
questions or thresholds in quick_add.py:

    TYPESAFE_API_KEY=... ../.venv/bin/python -m pytest test_quick_add_live.py -v
"""
import os
from datetime import date

import pytest

import quick_add as qa

pytestmark = pytest.mark.skipif(not os.environ.get("TYPESAFE_API_KEY"), reason="set TYPESAFE_API_KEY to call Jev")

TITLE = {"key": "title", "label": "Title", "type": "text", "direction": "none"}


def topic(name, number_label=None):
    fields = [TITLE]
    if number_label:
        fields.append({"key": "amount", "label": number_label, "type": "number", "direction": "higher"})
    return {"slug": name.lower(), "name": name, "fields": fields}


# Mirrors frontend/src/lib/starterTopics.ts.
STARTERS = [
    topic("Workout", "Duration (min)"), topic("Journal"), topic("Reading", "Pages"),
    topic("Meditation", "Minutes"), topic("Sleep", "Hours"), topic("Learning", "Minutes"),
    topic("Gratitude"), topic("Cooking"), topic("Walk", "Steps"),
]


@pytest.mark.parametrize("text, slug", [
    ("ran 5k in 27 min", "workout"),
    ("45 minute yoga class", "workout"),
    ("finished chapter 3 of Dune, 40 pages", "reading"),
    ("10 minutes of breathing before work", "meditation"),
    ("slept 8 hours straight", "sleep"),
    ("did a duolingo lesson for 20 min", "learning"),
    ("grateful my sister called", "gratitude"),
    ("made lasagna from scratch", "cooking"),
    ("walked 9000 steps around the lake", "walk"),
    ("wrote a page about how the week went", "journal"),
])
def test_topic(text, slug):
    assert qa.parse(STARTERS, text, date.today())["topic"] == slug


@pytest.mark.parametrize("text, slug, amount", [
    ("slept 8 hours", "sleep", 8),
    ("walked 9000 steps", "walk", 9000),
    ("ran 1h 10m, 8k", "workout", 70),
    ("read 25 pages before bed", "reading", 25),
])
def test_amount(text, slug, amount):
    assert qa.parse(STARTERS, text, date.today())["drafts"][slug].get("amount") == amount
