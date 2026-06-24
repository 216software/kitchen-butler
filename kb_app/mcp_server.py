from mcp.server.fastmcp import FastMCP
from kb_app.engine.tools import (
    get_pantry, search_recipes, get_recipe_detail, get_nutrition_remaining,
    log_meal, get_user_preferences, get_meal_logs_today, suggest_recipes,
    add_pantry_item, update_pantry_item, delete_pantry_item, add_recipe,
)

mcp = FastMCP("Kitchen Butler")


@mcp.tool()
def kb_get_pantry() -> str:
    """List all items currently in the user's pantry with quantities."""
    return get_pantry()


@mcp.tool()
def kb_search_recipes(query: str = "", cuisine: str = "", tag: str = "", max_results: int = 5) -> str:
    """Search for recipes by name, cuisine, or tag.
    Cuisine options: american, mexican, italian, asian.
    Tag options: dinner, lunch, breakfast, soup, sandwich, low carb, vegan, vegetarian, gluten free
    """
    return search_recipes(query, cuisine, tag, max_results)


@mcp.tool()
def kb_get_recipe_detail(recipe_id: int) -> str:
    """Get full details for a specific recipe including ingredients and instructions."""
    return get_recipe_detail(recipe_id)


@mcp.tool()
def kb_get_nutrition_remaining() -> str:
    """Get today's remaining nutritional budget (calories, protein, fiber)."""
    return get_nutrition_remaining()


@mcp.tool()
def kb_log_meal(items: list[dict], notes: str = "") -> str:
    """Log a meal with ingredients and quantities.

    Each item should have: {"ingredient_name": "...", "quantity": number, "unit": "..."}
    Example: [{"ingredient_name": "Pasta", "quantity": 2, "unit": "cup cooked"}, {"ingredient_name": "Chicken Breast", "quantity": 6, "unit": "oz"}]
    """
    return log_meal(items, notes)


@mcp.tool()
def kb_get_user_preferences() -> str:
    """Get the user's dietary likes and dislikes."""
    return get_user_preferences()


@mcp.tool()
def kb_get_meal_logs_today() -> str:
    """Get all meals logged today with nutritional breakdown."""
    return get_meal_logs_today()


@mcp.tool()
def kb_suggest_recipes(max_results: int = 5) -> str:
    """Suggest recipes based on what's in your pantry, ranked by match percentage."""
    return suggest_recipes(max_results)


@mcp.tool()
def kb_add_pantry_item(name: str, quantity: float, unit: str = None, expiry: str = None) -> str:
    """Add an ingredient to your pantry.
    Use standard food names like 'Chicken Breast', 'Eggs', 'Broccoli'.
    Merges with existing entry if same ingredient + unit already exists.
    """
    return add_pantry_item(name, quantity, unit, expiry)


@mcp.tool()
def kb_update_pantry_item(name: str, quantity: float, unit: str = None) -> str:
    """Update/set the quantity for a pantry ingredient. Replaces existing entries
    (including duplicates) with a single row at the specified quantity.
    """
    return update_pantry_item(name, quantity, unit)


@mcp.tool()
def kb_delete_pantry_item(name: str) -> str:
    """Remove an ingredient from your pantry entirely."""
    return delete_pantry_item(name)


@mcp.tool()
def kb_add_recipe(
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
    """Add a new recipe with ingredients and optional nutrition.

    Each ingredient should have: {"name": "...", "quantity": number, "unit": "...", "optional": bool}
    Ingredients not found in the DB will be auto-created.
    Nutrition format: {"calories": number, "protein_g": number, "fiber_g": number}
    """
    return add_recipe(name, cuisine, instructions, servings, prep_time, cook_time, ingredients, nutrition, tags)


def run_server():
    mcp.run(transport="stdio")
