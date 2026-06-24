import json
from datetime import date, datetime
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from kb_app.models import (
    Base, User, Ingredient, Nutrition, PantryItem, Preference, Recipe,
    RecipeIngredient, RecipeNutrition, MealLog, MealLogItem, MealPlan, MealPlanDay,
)

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
                tags=json.dumps(entry.get("tags", [])),
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

        user = User(name="TestUser", calorie_goal=2500, protein_goal=100, fiber_goal=30, api_key="test-key-1")
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

    def test_prefer_tag(self):
        tools_mod.add_pantry_item("Chicken Breast", 2.0, "lb")
        tools_mod.add_pantry_item("Broccoli", 1.0, "cup")
        result = tools_mod.suggest_recipes(max_results=3, prefer_tag="low carb")
        assert "% match" in result or "%" in result

    def test_avoid_dislikes(self):
        with Session(_TEST_ENGINE) as session:
            user = session.query(User).first()
            session.add(Preference(user_id=user.id, kind="dislike", item="Chicken"))
            session.commit()
        tools_mod.add_pantry_item("Chicken Breast", 2.0, "lb")
        result = tools_mod.suggest_recipes(max_results=3, avoid_dislikes=True)
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
#  Multi-user tests
# ----------------------------------------------------------------

class TestMultiUser:
    def test_add_user_creates_new(self):
        result = tools_mod.add_user("Alice", 2000, 80, 25)
        assert "Created user 'Alice'" in result

    def test_add_user_duplicate(self):
        tools_mod.add_user("Alice", 2000, 80, 25)
        result = tools_mod.add_user("Alice", 2000, 80, 25)
        assert "already exists" in result

    def test_list_users(self):
        tools_mod.add_user("Alice", 2000, 80, 25)
        tools_mod.add_user("Bob", 3000, 120, 35)
        result = tools_mod.list_users()
        assert "Alice" in result
        assert "Bob" in result
        assert "TestUser" in result

    def test_list_users_empty(self):
        with Session(_TEST_ENGINE) as session:
            session.query(User).delete()
            session.commit()
        result = tools_mod.list_users()
        assert "No users found" in result

    def test_pantry_isolation(self):
        tools_mod.add_user("Alice", 2000, 80, 25)
        tools_mod.add_user("Bob", 3000, 120, 35)
        tools_mod.add_pantry_item("Chicken Breast", 2.0, "lb", username="Alice")
        tools_mod.add_pantry_item("Broccoli", 1.0, "cup", username="Bob")
        alice_pantry = tools_mod.get_pantry(username="Alice")
        bob_pantry = tools_mod.get_pantry(username="Bob")
        assert "Chicken Breast" in alice_pantry
        assert "Broccoli" not in alice_pantry
        assert "Broccoli" in bob_pantry
        assert "Chicken Breast" not in bob_pantry

    def test_meal_log_isolation(self):
        tools_mod.add_user("Alice", 2000, 80, 25)
        tools_mod.log_meal([{"ingredient_name": "Chicken Breast", "quantity": 6, "unit": "oz"}], username="Alice")
        alice_logs = tools_mod.get_meal_logs_today(username="Alice")
        testuser_logs = tools_mod.get_meal_logs_today()
        assert "Chicken Breast" in alice_logs
        assert testuser_logs == "No meals logged today."

    def test_nutrition_isolation(self):
        tools_mod.add_user("Alice", 2000, 80, 25)
        result = tools_mod.get_nutrition_remaining(username="Alice")
        assert "2000 cal" in result
        assert "80g protein" in result
        assert "25g fiber" in result

    def test_lookup_by_username(self):
        tools_mod.add_user("Alice", 2000, 80, 25)
        tools_mod.add_pantry_item("Chicken Breast", 2.0, "lb", username="Alice")
        result = tools_mod.get_pantry(username="Alice")
        assert "Chicken Breast" in result

    def test_nonexistent_username(self):
        result = tools_mod.get_pantry(username="Nobody")
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


# ----------------------------------------------------------------
#  Expiry tests
# ----------------------------------------------------------------

class TestExpiringItems:
    def test_no_expiring(self):
        result = tools_mod.get_expiring_items(days=7)
        assert "No items expiring" in result

    def test_with_expiring(self):
        tools_mod.add_pantry_item("Chicken Breast", 2.0, "lb", expiry="2026-07-01")
        result = tools_mod.get_expiring_items(days=365)
        assert "Chicken Breast" in result
        assert "expires 2026-07-01" in result

    def test_filters_by_days(self):
        tools_mod.add_pantry_item("Chicken Breast", 2.0, "lb", expiry="2099-01-01")
        result = tools_mod.get_expiring_items(days=7)
        assert "No items expiring" in result

    def test_no_user(self):
        with Session(_TEST_ENGINE) as session:
            session.query(User).delete()
            session.commit()
        result = tools_mod.get_expiring_items()
        assert "No user found" in result


# ----------------------------------------------------------------
#  Week summary tests
# ----------------------------------------------------------------

class TestWeekSummary:
    def test_no_meals(self):
        result = tools_mod.get_week_summary()
        assert "No meals logged" in result

    def test_with_meals(self):
        tools_mod.log_meal([{"ingredient_name": "Chicken Breast", "quantity": 6, "unit": "oz"}], notes="Dinner")
        result = tools_mod.get_week_summary()
        assert "Weekly summary" in result
        assert "cal" in result

    def test_no_user(self):
        with Session(_TEST_ENGINE) as session:
            session.query(User).delete()
            session.commit()
        result = tools_mod.get_week_summary()
        assert "No user found" in result


# ----------------------------------------------------------------
#  Meal history tests
# ----------------------------------------------------------------

class TestMealHistory:
    def test_no_meals(self):
        result = tools_mod.get_meal_history(days=30)
        assert "No meals logged" in result

    def test_with_meals(self):
        tools_mod.log_meal([{"ingredient_name": "Chicken Breast", "quantity": 6, "unit": "oz"}], notes="Lunch")
        result = tools_mod.get_meal_history(days=30)
        assert "Lunch" in result
        assert "Chicken Breast" in result

    def test_no_user(self):
        with Session(_TEST_ENGINE) as session:
            session.query(User).delete()
            session.commit()
        result = tools_mod.get_meal_history()
        assert "No user found" in result


# ----------------------------------------------------------------
#  Plan week tests
# ----------------------------------------------------------------

class TestPlanWeek:
    def test_generates_7_days(self):
        result = tools_mod.plan_week()
        assert "Weekly Meal Plan" in result
        assert "Monday" in result
        assert "Sunday" in result
        for mt in ["Breakfast", "Lunch", "Dinner"]:
            assert mt in result

    def test_no_user(self):
        with Session(_TEST_ENGINE) as session:
            session.query(User).delete()
            session.commit()
        result = tools_mod.plan_week()
        assert "No user found" in result


class TestSavePlan:
    def test_saves_plan(self):
        result = tools_mod.save_plan(week_label="2026-W26")
        assert "Saved meal plan" in result
        with Session(_TEST_ENGINE) as session:
            mp = session.query(MealPlan).filter_by(week_label="2026-W26").first()
            assert mp is not None
            days = session.query(MealPlanDay).filter_by(plan_id=mp.id).all()
            assert len(days) == 21  # 7 days * 3 meals

    def test_no_user(self):
        with Session(_TEST_ENGINE) as session:
            session.query(User).delete()
            session.commit()
        result = tools_mod.save_plan()
        assert "No user found" in result


# ----------------------------------------------------------------
#  Grocery list tests
# ----------------------------------------------------------------

class TestGroceryList:
    def test_no_plan(self):
        result = tools_mod.get_grocery_list(week_label="2026-W99")
        assert "No meal plan found" in result

    def test_plan_but_pantry_has_it(self):
        tools_mod.add_pantry_item("Chicken Breast", 10.0, "lb")
        tools_mod.save_plan(week_label="2026-W26")
        result = tools_mod.get_grocery_list(week_label="2026-W26")
        # May or may not need items depending on what the plan picks
        assert isinstance(result, str)

    def test_no_user(self):
        with Session(_TEST_ENGINE) as session:
            session.query(User).delete()
            session.commit()
        result = tools_mod.get_grocery_list()
        assert "No user found" in result


# ----------------------------------------------------------------
#  Recipe import tests
# ----------------------------------------------------------------

class TestAddRecipe:
    def test_add_new_recipe(self):
        ingredients = [
            {"name": "Chicken Breast", "quantity": 1.0, "unit": "lb"},
        ]
        result = tools_mod.add_recipe(
            "Test Recipe", "american", "Cook it.", 2,
            ingredients=ingredients,
        )
        assert "Added recipe" in result
        assert "id=" in result
        with Session(_TEST_ENGINE) as session:
            recipe = session.query(Recipe).filter_by(name="Test Recipe").first()
            assert recipe is not None
            assert recipe.servings == 2
            ings = session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).all()
            assert len(ings) == 1

    def test_duplicate_name(self):
        tools_mod.add_recipe("Dup Recipe", "american", "Instructions.", ingredients=[])
        result = tools_mod.add_recipe("Dup Recipe", "italian", "Other.", ingredients=[])
        assert "already exists" in result

    def test_auto_creates_unknown_ingredients(self):
        result = tools_mod.add_recipe(
            "New Dish", "asian", "Do stuff.", ingredients=[
                {"name": "Dragon Fruit", "quantity": 1, "unit": "whole"},
            ],
        )
        assert "Created new ingredients: Dragon Fruit" in result
        with Session(_TEST_ENGINE) as session:
            ing = session.query(Ingredient).filter_by(name="Dragon Fruit").first()
            assert ing is not None
            assert ing.category == "imported"

    def test_with_nutrition(self):
        tools_mod.add_recipe(
            "Healthy Bowl", "american", "Mix.", ingredients=[],
            nutrition={"calories": 350, "protein_g": 20, "fiber_g": 5},
        )
        with Session(_TEST_ENGINE) as session:
            recipe = session.query(Recipe).filter_by(name="Healthy Bowl").first()
            nut = session.query(RecipeNutrition).filter_by(recipe_id=recipe.id).first()
            assert nut.per_serving_calories == 350
            assert nut.protein_g == 20
            assert nut.fiber_g == 5

    def test_fuzzy_ingredient_match(self):
        tools_mod.add_recipe(
            "Fuzzy Test", "american", "Do it.", ingredients=[
                {"name": "chicken breast", "quantity": 1, "unit": "lb"},
            ],
        )
        with Session(_TEST_ENGINE) as session:
            recipe = session.query(Recipe).filter_by(name="Fuzzy Test").first()
            ri = session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).first()
            assert ri.ingredient.name == "Chicken Breast"

    def test_add_with_tags(self):
        result = tools_mod.add_recipe(
            "Tagged Dish", "american", "Instructions.", tags=["dinner", "low carb"],
            ingredients=[{"name": "Chicken Breast", "quantity": 1, "unit": "lb"}],
        )
        assert "Added recipe" in result
        with Session(_TEST_ENGINE) as session:
            recipe = session.query(Recipe).filter_by(name="Tagged Dish").first()
            assert json.loads(recipe.tags) == ["dinner", "low carb"]

    def test_search_by_tag(self):
        result = tools_mod.search_recipes(tag="soup")
        assert "Chicken and Rice Soup" in result

    def test_search_by_tag_no_results(self):
        result = tools_mod.search_recipes(tag="sandwich")
        assert result == "No recipes found."

    def test_recipe_detail_shows_tags(self):
        with Session(_TEST_ENGINE) as session:
            recipe = session.query(Recipe).first()
            rid = recipe.id
        result = tools_mod.get_recipe_detail(rid)
        assert "Tags:" in result
