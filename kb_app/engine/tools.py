from datetime import date, datetime
from kb_app.db import get_session
from kb_app.models import (
    Ingredient, Nutrition, PantryItem, Preference, Recipe, RecipeIngredient,
    RecipeNutrition, MealLog, MealLogItem, User,
)


def _ensure_user():
    session = get_session()
    user = session.query(User).first()
    if not user:
        session.close()
        return None, None
    return user, session


def get_pantry() -> str:
    user, session = _ensure_user()
    if not user:
        return "No user found. Run `kb setup` first."
    items = session.query(PantryItem).filter_by(user_id=user.id).all()
    if not items:
        session.close()
        return "Your pantry is empty."
    lines = []
    for item in items:
        ing = item.ingredient
        expiry = f" (expires {item.expiry_date})" if item.expiry_date else ""
        lines.append(f"  - {ing.name}: {item.quantity} {item.unit}{expiry}")
    session.close()
    return "\n".join(lines)


def search_recipes(query: str = "", cuisine: str = "", tag: str = "", max_results: int = 5) -> str:
    session = get_session()
    q = session.query(Recipe)
    if query:
        q = q.filter(Recipe.name.ilike(f"%{query}%"))
    if cuisine:
        q = q.filter(Recipe.cuisine.ilike(f"%{cuisine}%"))
    if tag:
        q = q.filter(Recipe.tags.ilike(f"%{tag.lower()}%"))
    recipes = q.limit(max_results).all()
    if not recipes:
        session.close()
        return "No recipes found."
    lines = []
    for r in recipes:
        ings = session.query(RecipeIngredient).filter_by(recipe_id=r.id).all()
        ing_names = [i.ingredient.name for i in ings]
        import json as _json
        tags_list = _json.loads(r.tags) if r.tags else []
        tag_str = f" [{', '.join(tags_list)}]" if tags_list else ""
        lines.append(f"  [{r.id}] {r.name} ({r.cuisine}) — {r.servings} servings{tag_str}")
        lines.append(f"       Ingredients: {', '.join(ing_names)}")
    session.close()
    return "\n".join(lines)


def get_recipe_detail(recipe_id: int) -> str:
    session = get_session()
    r = session.query(Recipe).filter_by(id=recipe_id).first()
    if not r:
        session.close()
        return "Recipe not found."
    ings = session.query(RecipeIngredient).filter_by(recipe_id=r.id).all()
    parts = [f"# {r.name} ({r.cuisine})"]
    import json as _json
    tags_list = _json.loads(r.tags) if r.tags else []
    if tags_list:
        parts.append(f"Tags: {', '.join(tags_list)}")
    if r.prep_time:
        parts.append(f"Prep: {r.prep_time} min | Cook: {r.cook_time} min | Servings: {r.servings}")
    parts.append("\n## Ingredients")
    for i in ings:
        opt = " (optional)" if i.optional else ""
        parts.append(f"  - {i.quantity} {i.unit} {i.ingredient.name}{opt}")
    if r.nutrition:
        n = r.nutrition
        parts.append(f"\n## Nutrition per serving")
        parts.append(f"  Calories: {n.per_serving_calories} | Protein: {n.protein_g}g | Fiber: {n.fiber_g}g")
    parts.append(f"\n## Instructions\n{r.instructions_text}")
    session.close()
    return "\n".join(parts)


def get_nutrition_remaining() -> str:
    user, session = _ensure_user()
    if not user:
        return "No user found."
    today = date.today()
    logs = session.query(MealLog).filter(
        MealLog.user_id == user.id,
        MealLog.timestamp >= datetime(today.year, today.month, today.day),
    ).all()
    consumed = {"calories": 0.0, "protein_g": 0.0, "fiber_g": 0.0}
    for log in logs:
        for item in session.query(MealLogItem).filter_by(meal_log_id=log.id).all():
            nut = item.ingredient.nutrition
            if nut:
                consumed["calories"] += nut.calories * item.quantity
                consumed["protein_g"] += nut.protein_g * item.quantity
                consumed["fiber_g"] += nut.fiber_g * item.quantity
    session.close()
    remaining = {
        "calories": user.calorie_goal - consumed["calories"],
        "protein_g": user.protein_goal - consumed["protein_g"],
        "fiber_g": user.fiber_goal - consumed["fiber_g"],
    }
    return (
        f"Goals: {user.calorie_goal} cal, {user.protein_goal}g protein, {user.fiber_goal}g fiber\n"
        f"Consumed: {consumed['calories']:.0f} cal, {consumed['protein_g']:.0f}g protein, {consumed['fiber_g']:.0f}g fiber\n"
        f"Remaining: {remaining['calories']:.0f} cal, {remaining['protein_g']:.0f}g protein, {remaining['fiber_g']:.0f}g fiber"
    )


def log_meal(items: list[dict], notes: str = "") -> str:
    user, session = _ensure_user()
    if not user:
        return "No user found."
    log = MealLog(user_id=user.id, notes=notes)
    session.add(log)
    session.flush()
    registered = []
    unknown = []
    for item in items:
        ing = session.query(Ingredient).filter(Ingredient.name.ilike(item["ingredient_name"])).first()
        if not ing:
            ing = session.query(Ingredient).filter(Ingredient.name.ilike(f"%{item['ingredient_name']}%")).first()
        if not ing:
            unknown.append(item["ingredient_name"])
            continue
        session.add(MealLogItem(
            meal_log_id=log.id, ingredient_id=ing.id,
            quantity=item["quantity"], unit=item["unit"],
        ))
        registered.append(f"{item['quantity']} {item['unit']} {ing.name}")
    session.commit()
    session.close()
    parts = [f"Logged: {', '.join(registered)}"]
    if unknown:
        parts.append(f"Unknown: {', '.join(unknown)}")
    if notes:
        parts.append(f"Notes: {notes}")
    return "\n".join(parts)


def suggest_recipes(max_results: int = 5) -> str:
    user, session = _ensure_user()
    if not user:
        return "No user found."
    pantry_names = {item.ingredient.name.lower() for item in session.query(PantryItem).filter_by(user_id=user.id).all()}
    if not pantry_names:
        session.close()
        return "Your pantry is empty. Add items first."

    recipes = session.query(Recipe).all()
    scored = []
    for recipe in recipes:
        ings = session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).all()
        total = len(ings)
        matched = sum(1 for i in ings if i.ingredient.name.lower() in pantry_names)
        missing = [i for i in ings if i.ingredient.name.lower() not in pantry_names]
        pct = round(matched / total * 100) if total else 0
        scored.append((pct, matched, total, recipe, missing))
    scored.sort(key=lambda x: x[0], reverse=True)
    session.close()

    lines = []
    for pct, matched, total, recipe, missing in scored[:max_results]:
        lines.append(f"\n## {recipe.name} ({recipe.cuisine}) — {pct}% match ({matched}/{total} ingredients)")
        if missing:
            lines.append(f"Missing: {', '.join(i.ingredient.name for i in missing)}")
    return "\n".join(lines)


def get_user_preferences() -> str:
    user, session = _ensure_user()
    if not user:
        return "No user found."
    likes = [p.item for p in session.query(Preference).filter_by(user_id=user.id, kind="like").all()]
    dislikes = [p.item for p in session.query(Preference).filter_by(user_id=user.id, kind="dislike").all()]
    session.close()
    parts = []
    if likes:
        parts.append(f"Likes: {', '.join(likes)}")
    if dislikes:
        parts.append(f"Dislikes: {', '.join(dislikes)}")
    return "\n".join(parts) if parts else "No preferences set."


def get_meal_logs_today() -> str:
    user, session = _ensure_user()
    if not user:
        return "No user found."
    today = date.today()
    logs = session.query(MealLog).filter(
        MealLog.user_id == user.id,
        MealLog.timestamp >= datetime(today.year, today.month, today.day),
    ).order_by(MealLog.timestamp).all()
    if not logs:
        session.close()
        return "No meals logged today."
    lines = [f"Meals for {today}:"]
    for log in logs:
        items = session.query(MealLogItem).filter_by(meal_log_id=log.id).all()
        time_str = log.timestamp.strftime("%H:%M")
        lines.append(f"\n[{time_str}] {log.notes or ''}")
        for item in items:
            ing = item.ingredient
            nut = ing.nutrition
            cals = nut.calories * item.quantity if nut else 0
            protein = nut.protein_g * item.quantity if nut else 0
            lines.append(f"  - {item.quantity} {item.unit} {ing.name} ({cals:.0f} cal, {protein:.0f}g protein)")
    session.close()
    return "\n".join(lines)


def add_pantry_item(name: str, quantity: float, unit: str = None, expiry: str = None) -> str:
    user, session = _ensure_user()
    if not user:
        return "No user found."
    ing = session.query(Ingredient).filter(Ingredient.name.ilike(name)).first()
    if not ing:
        ing = session.query(Ingredient).filter(Ingredient.name.ilike(f"%{name}%")).first()
    if not ing:
        session.close()
        return f"Ingredient '{name}' not found."
    unit = unit or ing.default_unit
    ing_name = ing.name

    existing = session.query(PantryItem).filter_by(
        user_id=user.id, ingredient_id=ing.id, unit=unit,
    ).first()

    if existing:
        if expiry:
            existing.expiry_date = date.fromisoformat(expiry)
        existing.quantity += quantity
        new_qty = existing.quantity
        session.commit()
        session.close()
        return f"Merged: {ing_name} now at {new_qty} {unit}."

    expiry_date = date.fromisoformat(expiry) if expiry else None
    session.add(PantryItem(user_id=user.id, ingredient_id=ing.id, quantity=quantity, unit=unit, expiry_date=expiry_date))
    session.commit()
    session.close()
    return f"Added {quantity} {unit} of {ing_name} to pantry."


def update_pantry_item(name: str, quantity: float, unit: str = None) -> str:
    user, session = _ensure_user()
    if not user:
        return "No user found."
    ing = session.query(Ingredient).filter(Ingredient.name.ilike(name)).first()
    if not ing:
        ing = session.query(Ingredient).filter(Ingredient.name.ilike(f"%{name}%")).first()
    if not ing:
        session.close()
        return f"Ingredient '{name}' not found."
    unit = unit or ing.default_unit
    ing_name = ing.name

    existing = session.query(PantryItem).filter_by(
        user_id=user.id, ingredient_id=ing.id,
    ).all()

    if not existing:
        session.add(PantryItem(user_id=user.id, ingredient_id=ing.id, quantity=quantity, unit=unit))
        session.commit()
        session.close()
        return f"Added {quantity} {unit} of {ing_name} to pantry (no existing entry found)."

    for item in existing:
        session.delete(item)
    session.add(PantryItem(user_id=user.id, ingredient_id=ing.id, quantity=quantity, unit=unit))
    session.commit()
    session.close()
    return f"Set {ing_name} to {quantity} {unit}."


def delete_pantry_item(name: str) -> str:
    user, session = _ensure_user()
    if not user:
        return "No user found."
    ing = session.query(Ingredient).filter(Ingredient.name.ilike(name)).first()
    if not ing:
        ing = session.query(Ingredient).filter(Ingredient.name.ilike(f"%{name}%")).first()
    if not ing:
        session.close()
        return f"Ingredient '{name}' not found."
    ing_name = ing.name

    items = session.query(PantryItem).filter_by(
        user_id=user.id, ingredient_id=ing.id,
    ).all()

    if not items:
        session.close()
        return f"{ing_name} not found in pantry."

    for item in items:
        session.delete(item)
    session.commit()
    session.close()
    return f"Removed {ing_name} from pantry."


def add_recipe(
    name: str,
    cuisine: str,
    instructions: str,
    servings: int = 2,
    prep_time: int = None,
    cook_time: int = None,
    ingredients: list = None,
    nutrition: dict = None,
    tags: list = None,
) -> str:
    session = get_session()
    existing = session.query(Recipe).filter(Recipe.name.ilike(name)).first()
    if existing:
        session.close()
        return f"Recipe '{name}' already exists (id={existing.id})."

    import json
    recipe = Recipe(
        name=name, cuisine=cuisine, servings=servings,
        prep_time=prep_time, cook_time=cook_time,
        instructions_text=instructions,
        tags=json.dumps(tags or []),
    )
    session.add(recipe)
    session.flush()

    created = []
    unknown = []

    for ri in (ingredients or []):
        ing = session.query(Ingredient).filter(Ingredient.name.ilike(ri["name"])).first()
        if not ing:
            ing = session.query(Ingredient).filter(Ingredient.name.ilike(f"%{ri['name']}%")).first()
        if not ing:
            ing = Ingredient(
                name=ri["name"].strip().title(),
                category=ri.get("category", "imported"),
                default_unit=ri.get("unit", "unit"),
            )
            session.add(ing)
            session.flush()
            created.append(ing.name)
        session.add(RecipeIngredient(
            recipe_id=recipe.id, ingredient_id=ing.id,
            quantity=ri["quantity"], unit=ri["unit"],
            optional=ri.get("optional", False),
        ))

    if nutrition:
        session.add(RecipeNutrition(
            recipe_id=recipe.id,
            per_serving_calories=nutrition.get("calories", 0),
            protein_g=nutrition.get("protein_g", 0),
            fiber_g=nutrition.get("fiber_g", 0),
        ))

    session.commit()
    rid = recipe.id
    session.close()

    parts = [f"Added recipe '{name}' (id={rid}) with {len(ingredients or [])} ingredients."]
    if created:
        parts.append(f"Created new ingredients: {', '.join(created)}.")
    return "\n".join(parts)
