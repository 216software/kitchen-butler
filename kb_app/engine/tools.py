import json
import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta
from kb_app.db import get_session
from kb_app.models import (
    Ingredient, Nutrition, PantryItem, Preference, Recipe, RecipeIngredient,
    RecipeNutrition, MealLog, MealLogItem, MealPlan, MealPlanDay, User,
)


def _get_user(username=None, api_key=None):
    from kb_app.config import get_default_user
    session = get_session()
    if api_key:
        user = session.query(User).filter(User.api_key == api_key).first()
        if user:
            return user, session
        session.close()
        return None, None
    name = username or get_default_user()
    if name:
        user = session.query(User).filter(User.name.ilike(name)).first()
        if user:
            return user, session
        session.close()
        return None, None
    user = session.query(User).first()
    if not user:
        session.close()
        return None, None
    return user, session


def add_user(name: str, calorie_goal: int = 2500, protein_goal: int = 100, fiber_goal: int = 30) -> str:
    session = get_session()
    existing = session.query(User).filter(User.name.ilike(name)).first()
    if existing:
        session.close()
        return f"User '{name}' already exists."
    api_key = secrets.token_hex(32)
    user = User(name=name, calorie_goal=calorie_goal, protein_goal=protein_goal, fiber_goal=fiber_goal, api_key=api_key)
    session.add(user)
    session.commit()
    session.close()
    return f"Created user '{name}' (api_key: {api_key})"


def list_users() -> str:
    session = get_session()
    users = session.query(User).order_by(User.name).all()
    if not users:
        session.close()
        return "No users found."
    lines = []
    for u in users:
        lines.append(f"  [{u.id}] {u.name} — {u.calorie_goal} cal, {u.protein_goal}g protein, {u.fiber_goal}g fiber")
    session.close()
    return "\n".join(lines)


def setup_user(name: str, calorie_goal: int = 2500, protein_goal: int = 100, fiber_goal: int = 30) -> str:
    """Create or update a user (upsert by name)."""
    session = get_session()
    existing = session.query(User).filter(User.name.ilike(name)).first()
    if existing:
        existing.name = name
        existing.calorie_goal = calorie_goal
        existing.protein_goal = protein_goal
        existing.fiber_goal = fiber_goal
        api_key = existing.api_key
        session.commit()
        session.close()
        return f"Updated user '{name}' (api_key: {api_key})"
    api_key = secrets.token_hex(32)
    user = User(name=name, calorie_goal=calorie_goal, protein_goal=protein_goal, fiber_goal=fiber_goal, api_key=api_key)
    session.add(user)
    session.commit()
    session.close()
    return f"Created user '{name}' (api_key: {api_key})"


def get_pantry(username: str = None) -> str:
    user, session = _get_user(username)
    if not user:
        return "No user found. Run `kb setup` or `kb add-user` first."
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


def get_nutrition_remaining(username: str = None) -> str:
    user, session = _get_user(username)
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


def log_meal(items: list[dict], notes: str = "", username: str = None) -> str:
    user, session = _get_user(username)
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


def suggest_recipes(max_results: int = 5, username: str = None, prefer_tag: str = None, avoid_dislikes: bool = False) -> str:
    user, session = _get_user(username)
    if not user:
        return "No user found."
    pantry_names = {item.ingredient.name.lower() for item in session.query(PantryItem).filter_by(user_id=user.id).all()}
    if not pantry_names:
        session.close()
        return "Your pantry is empty. Add items first."

    disliked = set()
    if avoid_dislikes:
        disliked = {p.item.lower() for p in session.query(Preference).filter_by(user_id=user.id, kind="dislike").all()}

    recipes = session.query(Recipe).all()
    scored = []
    for recipe in recipes:
        ings = session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).all()
        total = len(ings)
        matched = sum(1 for i in ings if i.ingredient.name.lower() in pantry_names)
        missing = [i for i in ings if i.ingredient.name.lower() not in pantry_names]

        if avoid_dislikes:
            recipe_ing_names = {i.ingredient.name.lower() for i in ings}
            if recipe_ing_names & disliked:
                continue

        recipe_tags = json.loads(recipe.tags) if recipe.tags else []
        tag_bonus = 5 if prefer_tag and prefer_tag.lower() in recipe_tags else 0

        pct = round(matched / total * 100) if total else 0
        scored.append((pct + tag_bonus, matched, total, recipe, missing))
    scored.sort(key=lambda x: x[0], reverse=True)
    session.close()

    lines = []
    for score, matched, total, recipe, missing in scored[:max_results]:
        lines.append(f"\n## {recipe.name} ({recipe.cuisine}) — {score}% match ({matched}/{total} ingredients)")
        if missing:
            lines.append(f"Missing: {', '.join(i.ingredient.name for i in missing)}")
    return "\n".join(lines)


def get_expiring_items(days: int = 7, username: str = None) -> str:
    user, session = _get_user(username)
    if not user:
        return "No user found."
    cutoff = date.today() + timedelta(days=days)
    items = session.query(PantryItem).filter(
        PantryItem.user_id == user.id,
        PantryItem.expiry_date.isnot(None),
        PantryItem.expiry_date <= cutoff,
    ).order_by(PantryItem.expiry_date).all()
    if not items:
        session.close()
        return f"No items expiring within {days} days."
    lines = [f"Items expiring within {days} days (by {cutoff}):"]
    for item in items:
        ing = item.ingredient
        d = (item.expiry_date - date.today()).days
        lines.append(f"  - {ing.name}: {item.quantity} {item.unit} — expires {item.expiry_date} ({d} days)")
    session.close()
    return "\n".join(lines)


def get_week_summary(username: str = None) -> str:
    user, session = _get_user(username)
    if not user:
        return "No user found."
    today = date.today()
    week_ago = today - timedelta(days=7)
    logs = session.query(MealLog).filter(
        MealLog.user_id == user.id,
        MealLog.timestamp >= datetime(week_ago.year, week_ago.month, week_ago.day),
    ).order_by(MealLog.timestamp).all()
    if not logs:
        session.close()
        return "No meals logged in the past 7 days."
    daily = defaultdict(lambda: {"calories": 0.0, "protein_g": 0.0, "fiber_g": 0.0, "meals": 0})
    for log in logs:
        day = log.timestamp.date()
        daily[day]["meals"] += 1
        for item in session.query(MealLogItem).filter_by(meal_log_id=log.id).all():
            nut = item.ingredient.nutrition
            if nut:
                daily[day]["calories"] += nut.calories * item.quantity
                daily[day]["protein_g"] += nut.protein_g * item.quantity
                daily[day]["fiber_g"] += nut.fiber_g * item.quantity
    session.close()
    lines = [f"Weekly summary ({week_ago} — {today}):"]
    for day in sorted(daily.keys()):
        d = daily[day]
        lines.append(f"\n  {day}: {d['calories']:.0f} cal, {d['protein_g']:.0f}g protein, {d['fiber_g']:.0f}g fiber ({d['meals']} meals)")
    total_cal = sum(d["calories"] for d in daily.values())
    total_protein = sum(d["protein_g"] for d in daily.values())
    total_fiber = sum(d["fiber_g"] for d in daily.values())
    lines.append(f"\n  Total: {total_cal:.0f} cal, {total_protein:.0f}g protein, {total_fiber:.0f}g fiber")
    return "\n".join(lines)


def get_meal_history(days: int = 30, username: str = None) -> str:
    user, session = _get_user(username)
    if not user:
        return "No user found."
    cutoff = date.today() - timedelta(days=days)
    logs = session.query(MealLog).filter(
        MealLog.user_id == user.id,
        MealLog.timestamp >= datetime(cutoff.year, cutoff.month, cutoff.day),
    ).order_by(MealLog.timestamp.desc()).all()
    if not logs:
        session.close()
        return f"No meals logged in the past {days} days."
    lines = [f"Meal history (past {days} days):"]
    for log in logs:
        items = session.query(MealLogItem).filter_by(meal_log_id=log.id).all()
        time_str = log.timestamp.strftime("%Y-%m-%d %H:%M")
        lines.append(f"\n[{time_str}] {log.notes or 'Meal'}")
        for item in items:
            lines.append(f"  - {item.quantity} {item.unit} {item.ingredient.name}")
    session.close()
    return "\n".join(lines)


def _get_available_meals(session, user):
    pantry_names = {item.ingredient.name.lower() for item in session.query(PantryItem).filter_by(user_id=user.id).all()}
    recipes = session.query(Recipe).all()
    scored = []
    for recipe in recipes:
        ings = session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).all()
        total = len(ings)
        matched = sum(1 for i in ings if i.ingredient.name.lower() in pantry_names)
        pct = round(matched / total * 100) if total else 0
        tags = json.loads(recipe.tags) if recipe.tags else []
        scored.append((pct, recipe, tags))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def plan_week(username: str = None) -> str:
    user, session = _get_user(username)
    if not user:
        return "No user found."
    scored = _get_available_meals(session, user)
    if not scored:
        session.close()
        return "No recipes available."

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    meal_types = ["Breakfast", "Lunch", "Dinner"]

    import random
    rng = random.Random()

    plan = {}
    used = set()
    for day in day_names:
        plan[day] = {}
        for mt in meal_types:
            candidates = [r for r in scored if r[1].id not in used]
            if not candidates:
                candidates = scored
            chosen = rng.choice(candidates)
            used.add(chosen[1].id)
            plan[day][mt] = chosen[1]

    session.close()
    lines = ["## Weekly Meal Plan"]
    for day in day_names:
        lines.append(f"\n### {day}")
        for mt in meal_types:
            recipe = plan[day][mt]
            lines.append(f"  {mt}: {recipe.name}")
    return "\n".join(lines)


def save_plan(week_label: str = None, username: str = None) -> str:
    user, session = _get_user(username)
    if not user:
        return "No user found."
    if not week_label:
        week_label = date.today().strftime("%Y-W%W")
    scored = _get_available_meals(session, user)
    if not scored:
        session.close()
        return "No recipes available."

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    meal_types = ["Breakfast", "Lunch", "Dinner"]

    import random
    rng = random.Random()

    existing = session.query(MealPlan).filter_by(user_id=user.id, week_label=week_label).first()
    if existing:
        session.query(MealPlanDay).filter_by(plan_id=existing.id).delete()
        mp = existing
    else:
        mp = MealPlan(user_id=user.id, week_label=week_label)
        session.add(mp)
        session.flush()

    used = set()
    for day in day_names:
        for mt in meal_types:
            candidates = [r for r in scored if r[1].id not in used]
            if not candidates:
                candidates = scored
            chosen = rng.choice(candidates)
            used.add(chosen[1].id)
            session.add(MealPlanDay(plan_id=mp.id, day_name=day, meal_type=mt, recipe_id=chosen[1].id))

    session.commit()
    session.close()
    return f"Saved meal plan for '{week_label}' ({len(day_names) * len(meal_types)} meals)."


def get_grocery_list(week_label: str = None, username: str = None) -> str:
    user, session = _get_user(username)
    if not user:
        return "No user found."
    if not week_label:
        week_label = date.today().strftime("%Y-W%W")

    mp = session.query(MealPlan).filter_by(user_id=user.id, week_label=week_label).first()
    if not mp:
        session.close()
        return f"No meal plan found for '{week_label}'."

    pantry_items = {pi.ingredient_id: pi for pi in session.query(PantryItem).filter_by(user_id=user.id).all()}
    ing_map = {i.id: i.name for i in session.query(Ingredient).all()}

    needed = defaultdict(float)
    for day in session.query(MealPlanDay).filter_by(plan_id=mp.id).all():
        for ri in session.query(RecipeIngredient).filter_by(recipe_id=day.recipe_id).all():
            if ri.optional:
                continue
            needed[(ri.ingredient_id, ri.unit)] += ri.quantity

    session.close()

    lines = [f"## Grocery List — {week_label}"]
    for (ing_id, unit), qty in sorted(needed.items(), key=lambda x: ing_map.get(x[0][0], "")):
        ing_name = ing_map.get(ing_id, "?")
        have = pantry_items[ing_id].quantity if ing_id in pantry_items else 0
        need = qty - have
        if need <= 0:
            continue
        lines.append(f"  - {ing_name}: {need:.1f} {unit}")
    if len(lines) == 1:
        return f"Pantry covers all needs for '{week_label}' — no items to buy."
    return "\n".join(lines)


def get_user_preferences(username: str = None) -> str:
    user, session = _get_user(username)
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


def get_meal_logs_today(username: str = None) -> str:
    user, session = _get_user(username)
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


def add_pantry_item(name: str, quantity: float, unit: str = None, expiry: str = None, username: str = None) -> str:
    user, session = _get_user(username)
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


def update_pantry_item(name: str, quantity: float, unit: str = None, username: str = None) -> str:
    user, session = _get_user(username)
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


def delete_pantry_item(name: str, username: str = None) -> str:
    user, session = _get_user(username)
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
