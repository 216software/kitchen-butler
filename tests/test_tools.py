import json
from datetime import date, datetime
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from kb_app.models import Base, User, Ingredient, Nutrition, PantryItem, Preference, Recipe, RecipeIngredient, MealLog, MealLogItem

DATA_DIR = Path(__file__).parent.parent / "kb_app" / "seed_data"


def load_json(filename):
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def build_engine():
    return create_engine("sqlite:///:memory:", echo=False)


def seed_db(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ingest_data = load_json("ingredients.json")
        for entry in ingest_data:
            ing = Ingredient(
                name=entry["name"],
                category=entry["category"],
                default_unit=entry.get("default_unit", "unit"),
            )
            session.add(ing)
            session.flush()
            nut = entry.get("nutrition")
            if nut:
                session.add(Nutrition(
                    ingredient_id=ing.id,
                    per_unit=nut.get("per_unit", ing.default_unit),
                    calories=nut.get("calories", 0),
                    protein_g=nut.get("protein_g", 0),
                    fiber_g=nut.get("fiber_g", 0),
                    vitamins_json=json.dumps(nut.get("vitamins", {})),
                ))

        ing_map = {r.name.lower(): r for r in session.query(Ingredient).all()}

        rec_data = load_json("recipes.json")
        for entry in rec_data:
            recipe = Recipe(
                name=entry["name"],
                cuisine=entry["cuisine"],
                prep_time=entry.get("prep_time"),
                cook_time=entry.get("cook_time"),
                servings=entry.get("servings", 2),
                instructions_text=entry["instructions"],
            )
            session.add(recipe)
            session.flush()

            for ri in entry.get("ingredients", []):
                ing = ing_map.get(ri["name"].lower())
                if not ing:
                    continue
                session.add(RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=ing.id,
                    quantity=ri["quantity"],
                    unit=ri["unit"],
                    optional=ri.get("optional", False),
                ))

        user = User(name="TestUser", calorie_goal=2500, protein_goal=100, fiber_goal=30)
        session.add(user)
        session.commit()


# ----------------------------------------------------------------
#  Monkey-patch get_session so tools use our test engine
# ----------------------------------------------------------------
import kb_app.db as db_mod
import kb_app.engine.tools as tools_mod

_TEST_ENGINE = None


def _test_get_session(engine=None):
    return Session(_TEST_ENGINE)


# ----------------------------------------------------------------
#  Fixtures
# ----------------------------------------------------------------
import pytest


@pytest.fixture(autouse=True)
def test_db(monkeypatch):
    global _TEST_ENGINE
    engine = build_engine()
    _TEST_ENGINE = engine
    seed_db(engine)
    monkeypatch.setattr(db_mod, "get_session", _test_get_session)
    monkeypatch.setattr(tools_mod, "get_session", _test_get_session)


@pytest.fixture
def user_id(test_db):
    with Session(_TEST_ENGINE) as session:
        return session.query(User).first().id


@pytest.fixture
def chicken_breast_id(test_db):
    with Session(_TEST_ENGINE) as session:
        return session.query(Ingredient).filter_by(name="Chicken Breast").first().id


# ----------------------------------------------------------------
#  PantryItem tests
# ----------------------------------------------------------------

class TestAddPantryItem:
    def test_add_new_item(self):
        result = tools_mod.add_pantry_item("Chicken Breast", 2.0, "lb")
        assert "2.0 lb" in result
        with Session(_TEST_ENGINE) as session:
            count = session.query(PantryItem).count()
            assert count == 1
            item = session.query(PantryItem).first()
            assert item.quantity == 2.0
            assert item.unit == "lb"

    def test_merge_same_unit(self):
        tools_mod.add_pantry_item("Chicken Breast", 2.0, "lb")
        result = tools_mod.add_pantry_item("Chicken Breast", 3.0, "lb")
        assert "5.0 lb" in result
        with Session(_TEST_ENGINE) as session:
            count = session.query(PantryItem).count()
            assert count == 1

    def test_no_merge_different_unit(self):
        tools_mod.add_pantry_item("Chicken Breast", 1.0, "lb")
        tools_mod.add_pantry_item("Chicken Breast", 16.0, "oz")
        with Session(_TEST_ENGINE) as session:
            count = session.query(PantryItem).count()
            assert count == 2

    def test_ingredient_not_found(self):
        result = tools_mod.add_pantry_item("Unobtainium", 1)
        assert "not found" in result

    def test_default_unit(self):
        result = tools_mod.add_pantry_item("Chicken Breast", 1.0)
        assert "oz" in result  # default_unit for Chicken Breast is "oz"


class TestUpdatePantryItem:
    def test_update_existing(self):
        tools_mod.add_pantry_item("Chicken Breast", 2.0, "lb")
        tools_mod.add_pantry_item("Chicken Breast", 16.0, "oz")
        result = tools_mod.update_pantry_item("Chicken Breast", 3.0, "lb")
        assert "3.0 lb" in result
        with Session(_TEST_ENGINE) as session:
            items = session.query(PantryItem).all()
            assert len(items) == 1
            assert items[0].quantity == 3.0
            assert items[0].unit == "lb"

    def test_update_nonexistent(self):
        result = tools_mod.update_pantry_item("Chicken Breast", 2.0, "lb")
        assert "Added" in result

    def test_update_unknown_ingredient(self):
        result = tools_mod.update_pantry_item("FakeIngredient", 1.0)
        assert "not found" in result


class TestDeletePantryItem:
    def test_delete_existing(self):
        tools_mod.add_pantry_item("Chicken Breast", 2.0, "lb")
        tools_mod.add_pantry_item("Chicken Breast", 16.0, "oz")
        result = tools_mod.delete_pantry_item("Chicken Breast")
        assert "Removed Chicken Breast from pantry" in result
        with Session(_TEST_ENGINE) as session:
            count = session.query(PantryItem).count()
            assert count == 0

    def test_delete_not_in_pantry(self):
        result = tools_mod.delete_pantry_item("Chicken Breast")
        assert "not found in pantry" in result

    def test_delete_unknown_ingredient(self):
        result = tools_mod.delete_pantry_item("FakeIngredient")
        assert "not found" in result


class TestGetPantry:
    def test_empty_pantry(self):
        result = tools_mod.get_pantry()
        assert result == "Your pantry is empty."

    def test_with_items(self):
        tools_mod.add_pantry_item("Chicken Breast", 2.0, "lb")
        tools_mod.add_pantry_item("Broccoli", 1.0, "cup")
        result = tools_mod.get_pantry()
        assert "Chicken Breast" in result
        assert "Broccoli" in result
        assert "lb" in result
        assert "cup" in result

    def test_no_user(self):
        with Session(_TEST_ENGINE) as session:
            session.query(User).delete()
            session.commit()
        result = tools_mod.get_pantry()
        assert "No user found" in result


# ----------------------------------------------------------------
#  Recipe tests
# ----------------------------------------------------------------

class TestSearchRecipes:
    def test_search_by_name(self):
        result = tools_mod.search_recipes(query="chicken")
        assert "Chicken" in result or "chicken" in result

    def test_search_by_cuisine(self):
        result = tools_mod.search_recipes(cuisine="italian")
        assert "italian" in result.lower()

    def test_no_results(self):
        result = tools_mod.search_recipes(query="xyznonexistent")
        assert result == "No recipes found."

    def test_limit(self):
        result = tools_mod.search_recipes(max_results=1)
        lines = [l for l in result.split("\n") if l.startswith("  [")]
        assert len(lines) <= 1


class TestGetRecipeDetail:
    def test_existing(self):
        with Session(_TEST_ENGINE) as session:
            recipe = session.query(Recipe).first()
            rid = recipe.id
        result = tools_mod.get_recipe_detail(rid)
        assert recipe.name in result
        assert "Ingredients" in result
        assert "Instructions" in result

    def test_not_found(self):
        result = tools_mod.get_recipe_detail(99999)
        assert result == "Recipe not found."


# ----------------------------------------------------------------
#  Meal logging tests
# ----------------------------------------------------------------

class TestLogMeal:
    def test_log_known_ingredients(self):
        items = [
            {"ingredient_name": "Chicken Breast", "quantity": 6, "unit": "oz"},
            {"ingredient_name": "Broccoli", "quantity": 1, "unit": "cup"},
        ]
        result = tools_mod.log_meal(items, notes="Lunch")
        assert "Logged:" in result
        assert "Chicken Breast" in result
        assert "Broccoli" in result
        assert "Notes: Lunch" in result

    def test_log_unknown_ingredient(self):
        items = [{"ingredient_name": "FakeIngredient", "quantity": 1, "unit": "unit"}]
        result = tools_mod.log_meal(items)
        assert "Unknown: FakeIngredient" in result

    def test_no_user(self):
        with Session(_TEST_ENGINE) as session:
            session.query(User).delete()
            session.commit()
        result = tools_mod.log_meal([{"ingredient_name": "Chicken Breast", "quantity": 1, "unit": "oz"}])
        assert "No user found" in result


class TestGetMealLogsToday:
    def test_no_meals(self):
        result = tools_mod.get_meal_logs_today()
        assert result == "No meals logged today."

    def test_with_meals(self):
        items = [{"ingredient_name": "Chicken Breast", "quantity": 6, "unit": "oz"}]
        tools_mod.log_meal(items, notes="Dinner")
        result = tools_mod.get_meal_logs_today()
        assert "Dinner" in result
        assert "Chicken Breast" in result

    def test_no_user(self):
        with Session(_TEST_ENGINE) as session:
            session.query(User).delete()
            session.commit()
        result = tools_mod.get_meal_logs_today()
        assert "No user found" in result


# ----------------------------------------------------------------
#  Nutrition tests
# ----------------------------------------------------------------

class TestGetNutritionRemaining:
    def test_defaults(self):
        result = tools_mod.get_nutrition_remaining()
        assert "2500 cal" in result
        assert "100g protein" in result
        assert "30g fiber" in result
        assert "Remaining:" in result

    def test_after_meal(self):
        items = [
            {"ingredient_name": "Chicken Breast", "quantity": 6, "unit": "oz"},
            {"ingredient_name": "Broccoli", "quantity": 1, "unit": "cup"},
        ]
        tools_mod.log_meal(items)
        result = tools_mod.get_nutrition_remaining()
        assert "Remaining:" in result
        assert "Consumed:" in result

    def test_no_user(self):
        with Session(_TEST_ENGINE) as session:
            session.query(User).delete()
            session.commit()
        result = tools_mod.get_nutrition_remaining()
        assert "No user found" in result


# ----------------------------------------------------------------
#  Suggest / Preferences tests
# ----------------------------------------------------------------

class TestSuggestRecipes:
    def test_empty_pantry(self):
        result = tools_mod.suggest_recipes()
        assert "Your pantry is empty" in result

    def test_with_pantry_items(self):
        tools_mod.add_pantry_item("Chicken Breast", 2.0, "lb")
        tools_mod.add_pantry_item("Broccoli", 1.0, "cup")
        result = tools_mod.suggest_recipes(max_results=3)
        assert "% match" in result or "%" in result


class TestGetUserPreferences:
    def test_no_preferences(self):
        result = tools_mod.get_user_preferences()
        assert result == "No preferences set."

    def test_with_preferences(self):
        with Session(_TEST_ENGINE) as session:
            user = session.query(User).first()
            session.add(Preference(user_id=user.id, kind="like", item="Chicken"))
            session.add(Preference(user_id=user.id, kind="dislike", item="Fish"))
            session.commit()
        result = tools_mod.get_user_preferences()
        assert "Likes: Chicken" in result
        assert "Dislikes: Fish" in result

    def test_no_user(self):
        with Session(_TEST_ENGINE) as session:
            session.query(User).delete()
            session.commit()
        result = tools_mod.get_user_preferences()
        assert "No user found" in result


# ----------------------------------------------------------------
#  Edge cases
# ----------------------------------------------------------------

class TestEdgeCases:
    def test_update_item_with_no_initial(self):
        result = tools_mod.update_pantry_item("Chicken Breast", 3.0, "lb")
        assert "Added" in result

    def test_add_with_expiry(self):
        result = tools_mod.add_pantry_item("Chicken Breast", 1.0, "lb", expiry="2026-07-01")
        assert "Added" in result
        with Session(_TEST_ENGINE) as session:
            item = session.query(PantryItem).first()
            assert item.expiry_date == date(2026, 7, 1)

    def test_merge_preserves_latest_expiry(self):
        tools_mod.add_pantry_item("Chicken Breast", 1.0, "lb", expiry="2026-07-01")
        tools_mod.add_pantry_item("Chicken Breast", 1.0, "lb", expiry="2026-08-15")
        with Session(_TEST_ENGINE) as session:
            item = session.query(PantryItem).first()
            assert item.quantity == 2.0
            assert item.expiry_date == date(2026, 8, 15)

    def test_merge_keeps_original_expiry_when_none_given(self):
        tools_mod.add_pantry_item("Chicken Breast", 1.0, "lb", expiry="2026-07-01")
        tools_mod.add_pantry_item("Chicken Breast", 1.0, "lb")
        with Session(_TEST_ENGINE) as session:
            item = session.query(PantryItem).first()
            assert item.quantity == 2.0
            assert item.expiry_date == date(2026, 7, 1)

    def test_delete_one_of_two_ingredients(self):
        tools_mod.add_pantry_item("Chicken Breast", 1.0, "lb")
        tools_mod.add_pantry_item("Broccoli", 2.0, "cup")
        tools_mod.delete_pantry_item("Chicken Breast")
        result = tools_mod.get_pantry()
        assert "Chicken Breast" not in result
        assert "Broccoli" in result

    def test_case_insensitive_ingredient_match(self):
        result = tools_mod.add_pantry_item("chicken breast", 2.0, "lb")
        assert "Chicken Breast" in result

    def test_fuzzy_ingredient_match(self):
        result = tools_mod.add_pantry_item("chicken", 2.0, "lb")
        assert "Chicken Breast" in result
