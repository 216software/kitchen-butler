from mcp.server.fastmcp import FastMCP
from kb_app.engine.tools import (
    get_pantry, search_recipes, get_recipe_detail, get_nutrition_remaining,
    log_meal, get_user_preferences, get_meal_logs_today, suggest_recipes,
    add_pantry_item,
)

mcp = FastMCP("Kitchen Brain")


@mcp.tool()
def kb_get_pantry() -> str:
    """List all items currently in the user's pantry with quantities."""
    return get_pantry()


@mcp.tool()
def kb_search_recipes(query: str = "", cuisine: str = "", max_results: int = 5) -> str:
    """Search for recipes by name, cuisine, or ingredient.
    Cuisine options: american, mexican, italian, asian.
    """
    return search_recipes(query, cuisine, max_results)


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
    """
    return add_pantry_item(name, quantity, unit, expiry)


def run_server():
    mcp.run(transport="stdio")
