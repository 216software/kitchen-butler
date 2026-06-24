import json
import os
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from kb_app.models import Base

DATA_DIR = Path(__file__).parent / "seed_data"
DB_PATH = Path.home() / ".local" / "share" / "kitchen-butler" / "kb.db"


def get_engine(db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}")


def init_db(engine=None):
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    # add tags column to existing databases (safe to re-run)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE recipes ADD COLUMN tags TEXT DEFAULT '[]'"))
            conn.commit()
        except Exception:
            conn.rollback()
    return engine


def get_session(engine=None):
    if engine is None:
        engine = get_engine()
    return Session(engine)


def load_json(filename: str):
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def seed_ingredients(session: Session):
    if session.execute(text("SELECT 1 FROM ingredients LIMIT 1")).scalar():
        return
    from kb_app.models import Ingredient, Nutrition

    data = load_json("ingredients.json")
    for entry in data:
        ing = Ingredient(name=entry["name"], category=entry["category"], default_unit=entry.get("default_unit", "unit"))
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
    session.commit()


def seed_recipes(session: Session):
    if session.execute(text("SELECT 1 FROM recipes LIMIT 1")).scalar():
        return
    from kb_app.models import Recipe, RecipeIngredient, RecipeNutrition
    from kb_app.models import Ingredient

    data = load_json("recipes.json")
    ing_map = {r.name.lower(): r for r in session.query(Ingredient).all()}

    for entry in data:
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

        nut = entry.get("nutrition")
        if nut:
            session.add(RecipeNutrition(
                recipe_id=recipe.id,
                per_serving_calories=nut.get("calories", 0),
                protein_g=nut.get("protein_g", 0),
                fiber_g=nut.get("fiber_g", 0),
                vitamins_json=json.dumps(nut.get("vitamins", {})),
            ))
    session.commit()


def seed_all(session: Session):
    seed_ingredients(session)
    seed_recipes(session)


def full_setup():
    engine = init_db()
    with Session(engine) as session:
        seed_all(session)
    return engine
