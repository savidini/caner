"""Deterministic browser fixture. Run only in the isolated test container."""

import importlib
import os
from datetime import date, timedelta
from unittest.mock import patch


def load_preview():
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ["STARTUP_MPS_ENABLED"] = "false"
    os.environ["STARTUP_TRANSLATIONS_ENABLED"] = "false"
    os.environ["SESSION_SECRET"] = "isolated-browser-fixture"
    with (
        patch("utils.xml_parser.parse_mensa_data", return_value={}),
        patch("threading.Thread.start"),
    ):
        module = importlib.import_module("app")

    from models import Meal, MealComment, MealVote, PageView, db

    names = [
        ("Kichererbsen-Curry mit Basmatireis und frischem Gemüse", "Chickpea curry with basmati rice and fresh vegetables"),
        ("Pasta mit Tomatensoße und Parmesan", "Pasta with tomato sauce and Parmesan"),
        ("Ofenkartoffel mit Kräuterquark und Salat", "Baked potato with herb quark and salad"),
        ("Gebratener Lachs auf Spinat mit Kartoffeln", "Grilled salmon with spinach and potatoes"),
    ]
    raw_meals = []
    with module.app.app_context():
        # The caller supplies a disposable database; never use the production env.
        for number in range(30):
            german, english = names[number % len(names)]
            suffix = f" · {number + 1}" if number >= len(names) else ""
            meal = Meal(
                description=german + suffix,
                description_en=english + suffix,
                marking="v" if number % 2 == 0 else "f",
                nutritional_values="Brennwert=2200 kJ (530 kcal), Eiweiß=22g, Fett=18g",
                mps_score=76 - number,
            )
            db.session.add(meal)
            db.session.flush()
            raw_meals.append({
                "description": meal.description,
                "price_student": "2,80", "price_employee": "4,20", "price_guest": "5,60",
                "nutritional_values": meal.nutritional_values, "marking": meal.marking,
            })
            db.session.add(MealVote(meal_id=meal.id, vote_type="up", client_id="fixture-voter", date=date.today()))
            db.session.add(MealComment(meal_id=meal.id, rating="good", client_id="fixture-commenter", text_en="Fresh and tasty.", text_de="Frisch und lecker.", source_language="en"))
        db.session.add(PageView(count=1234))
        db.session.commit()

    dates = [(date.today() + timedelta(days=offset)).strftime("%d.%m.%Y") for offset in (-1, 0, 1)]
    module.mensa_data = {
        mensa: {day: raw_meals if mensa != "Contine" else [] for day in dates}
        for mensa in ("Mensa Garbsen", "Hauptmensa", "Contine")
    }
    module.available_dates = dates
    module.available_mensen = list(module.mensa_data)
    module.translate_comment_text = lambda text, lang: {lang: text, "translation_failed": False}
    module.find_or_cache_meal_image = lambda *args, **kwargs: None
    return module, raw_meals


if __name__ == "__main__":
    module, _ = load_preview()
    from gevent.pywsgi import WSGIServer

    WSGIServer(("0.0.0.0", 30823), module.app).serve_forever()
