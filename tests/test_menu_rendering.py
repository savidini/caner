from datetime import date, timedelta

import pytest
from sqlalchemy import event

from i18n import TRANSLATIONS
from meal_social import add_social_counts
from models import MealVote, db
from tests.preview import load_preview


@pytest.fixture(scope="module")
def menu():
    return load_preview()


def test_ui_translation_keys_match():
    assert TRANSLATIONS["de"].keys() == TRANSLATIONS["en"].keys()


def test_menu_queries_do_not_grow_with_meal_count(menu):
    app, raw_meals = menu
    with app.app.app_context():
        queries = []

        def record(*args):
            queries.append(args[2])

        event.listen(db.engine, "before_cursor_execute", record)
        try:
            for count in (1, 30):
                queries.clear()
                meals = app.sort_meals_for_display(raw_meals[:count], "en")
                add_social_counts(meals, "fixture-voter")
                assert len(queries) == 4
                assert all(meal["votes"] == {"up": 1, "down": 0} for meal in meals)
                assert all(meal["comment_count"] == 1 for meal in meals)
                assert all(meal["vote_type"] == "up" for meal in meals)
                assert meals[0]["display_description"].startswith("Chickpea curry")
        finally:
            event.remove(db.engine, "before_cursor_execute", record)


def test_old_votes_count_but_are_not_selected_today(menu):
    app, raw_meals = menu
    with app.app.app_context():
        meals = app.sort_meals_for_display(raw_meals[:1], "de")
        vote = MealVote(meal_id=meals[0]["id"], vote_type="down", client_id="yesterday", date=date.today() - timedelta(days=1))
        db.session.add(vote)
        db.session.commit()
        add_social_counts(meals, "yesterday")
        assert meals[0]["votes"] == {"up": 1, "down": 1}
        assert meals[0]["vote_type"] is None
        db.session.delete(vote)
        db.session.commit()


def test_empty_and_unpersisted_meals_need_no_social_queries(menu):
    app, _ = menu
    with app.app.app_context():
        meals = [{"id": 0}]
        add_social_counts(meals)
        assert meals == [{"id": 0, "votes": {"up": 0, "down": 0}, "comment_count": 0, "vote_type": None}]
        assert app.sort_meals_for_display([], "en") == []


def test_html_contains_social_totals_and_sets_one_actor_cookie(menu):
    app, _ = menu
    client = app.app.test_client()
    response = client.get("/?lang=en")
    assert response.status_code == 200
    assert b'class="upvote-count">1</span>' in response.data
    assert b'class="comment-count">1</span>' in response.data
    assert client.get_cookie("client_id") is not None
    actor = client.get_cookie("client_id").value
    assert client.post("/api/vote", json={"meal_id": 1, "vote_type": "down"}).status_code == 200
    response = client.get("/?lang=en")
    assert b'downvote-btn active' in response.data
    assert client.get_cookie("client_id").value == actor


def test_all_empty_menu_controls_still_render(menu):
    app, _ = menu
    response = app.app.test_client().get("/?mensa=Contine&lang=en")
    assert response.status_code == 200
    assert b'id="date"' in response.data
    assert b'id="mensa"' in response.data
    assert TRANSLATIONS['en']['no_meals_for_date'].encode() in response.data
