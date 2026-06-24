from kb_app.db import get_session
from kb_app.models import PantryItem, Recipe, RecipeIngredient, User


def get_pantry_names(user_id: int):
    session = get_session()
    items = session.query(PantryItem).filter_by(user_id=user_id).all()
    names = {item.ingredient.name.lower() for item in items}
    session.close()
    return names


def match_recipes(user_id: int, top_n: int = 5):
    session = get_session()
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        session.close()
        return []

    pantry_names = get_pantry_names(user_id)
    recipes = session.query(Recipe).all()

    results = []
    for recipe in recipes:
        ings = session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).all()
        total = len(ings)
        matched = sum(1 for i in ings if i.ingredient.name.lower() in pantry_names)
        missing = [i for i in ings if i.ingredient.name.lower() not in pantry_names]
        pct = round(matched / total * 100) if total else 0

        results.append({
            "recipe": recipe,
            "match_pct": pct,
            "matched": matched,
            "total": total,
            "missing": missing,
        })

    session.close()
    results.sort(key=lambda r: r["match_pct"], reverse=True)
    return results[:top_n]
