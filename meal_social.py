"""Load menu social totals in a fixed number of queries."""

from datetime import date

from sqlalchemy import func

from models import MealComment, MealVote, db


def add_social_counts(meals, client_id=None):
    meal_ids = {meal["id"] for meal in meals if meal.get("id")}
    votes = {}
    comments = {}
    viewer_votes = {}
    if meal_ids:
        votes = {
            (meal_id, vote_type): count
            for meal_id, vote_type, count in db.session.query(
                MealVote.meal_id, MealVote.vote_type, func.count(MealVote.id)
            )
            .filter(MealVote.meal_id.in_(meal_ids))
            .group_by(MealVote.meal_id, MealVote.vote_type)
        }
        comments = dict(
            db.session.query(MealComment.meal_id, func.count(MealComment.id))
            .filter(MealComment.meal_id.in_(meal_ids))
            .group_by(MealComment.meal_id)
            .all()
        )
        if client_id:
            viewer_votes = dict(
                db.session.query(MealVote.meal_id, MealVote.vote_type)
                .filter(
                    MealVote.meal_id.in_(meal_ids),
                    MealVote.client_id == client_id,
                    MealVote.date == date.today(),
                )
                .all()
            )

    for meal in meals:
        meal_id = meal.get("id")
        meal["votes"] = {kind: votes.get((meal_id, kind), 0) for kind in ("up", "down")}
        meal["comment_count"] = comments.get(meal_id, 0)
        meal["vote_type"] = viewer_votes.get(meal_id)
