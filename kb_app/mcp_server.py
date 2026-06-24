"""MCP server — stdio for local use, SSE for remote with optional api_key auth."""

import os
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

from kb_app.db import get_session
from kb_app.models import User
from kb_app.engine.tools import (
    get_pantry, search_recipes, get_recipe_detail, get_nutrition_remaining,
    log_meal, get_user_preferences, get_meal_logs_today, suggest_recipes,
    add_pantry_item, update_pantry_item, delete_pantry_item, add_recipe,
    add_user, list_users, setup_user, get_expiring_items, get_week_summary,
    get_meal_history, plan_week, save_plan, get_grocery_list,
)

mcp = FastMCP("Kitchen Butler")


@mcp.tool()
def kb_get_pantry(username: str = None) -> str:
    """List all items currently in the user's pantry with quantities."""
    return get_pantry(username)


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
def kb_get_nutrition_remaining(username: str = None) -> str:
    """Get today's remaining nutritional budget (calories, protein, fiber)."""
    return get_nutrition_remaining(username)


@mcp.tool()
def kb_log_meal(items: list[dict], notes: str = "", username: str = None) -> str:
    """Log a meal with ingredients and quantities.

    Each item should have: {"ingredient_name": "...", "quantity": number, "unit": "..."}
    Example: [{"ingredient_name": "Pasta", "quantity": 2, "unit": "cup cooked"}, {"ingredient_name": "Chicken Breast", "quantity": 6, "unit": "oz"}]
    """
    return log_meal(items, notes, username)


@mcp.tool()
def kb_get_user_preferences(username: str = None) -> str:
    """Get the user's dietary likes and dislikes."""
    return get_user_preferences(username)


@mcp.tool()
def kb_get_meal_logs_today(username: str = None) -> str:
    """Get all meals logged today with nutritional breakdown."""
    return get_meal_logs_today(username)


@mcp.tool()
def kb_suggest_recipes(max_results: int = 5, username: str = None, prefer_tag: str = None, avoid_dislikes: bool = False) -> str:
    """Suggest recipes based on what's in your pantry, ranked by match percentage.
    Optionally prefer recipes with a given tag (e.g. 'low carb') and/or skip recipes with disliked ingredients.
    """
    return suggest_recipes(max_results, username, prefer_tag, avoid_dislikes)


@mcp.tool()
def kb_add_pantry_item(name: str, quantity: float, unit: str = None, expiry: str = None, username: str = None) -> str:
    """Add an ingredient to your pantry.
    Use standard food names like 'Chicken Breast', 'Eggs', 'Broccoli'.
    Merges with existing entry if same ingredient + unit already exists.
    """
    return add_pantry_item(name, quantity, unit, expiry, username)


@mcp.tool()
def kb_update_pantry_item(name: str, quantity: float, unit: str = None, username: str = None) -> str:
    """Update/set the quantity for a pantry ingredient. Replaces existing entries
    (including duplicates) with a single row at the specified quantity.
    """
    return update_pantry_item(name, quantity, unit, username)


@mcp.tool()
def kb_delete_pantry_item(name: str, username: str = None) -> str:
    """Remove an ingredient from your pantry entirely."""
    return delete_pantry_item(name, username)


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


@mcp.tool()
def kb_add_user(name: str, calorie_goal: int = 2500, protein_goal: int = 100, fiber_goal: int = 30) -> str:
    """Add a new user with daily nutritional goals.

    Each user has their own pantry, meal logs, and preferences.
    Returns an API key for SSE-based authentication.
    """
    return add_user(name, calorie_goal, protein_goal, fiber_goal)


@mcp.tool()
def kb_list_users() -> str:
    """List all registered users."""
    return list_users()


@mcp.tool()
def kb_get_expiring_items(days: int = 7, username: str = None) -> str:
    """Show pantry items expiring within the given number of days."""
    return get_expiring_items(days, username)


@mcp.tool()
def kb_get_week_summary(username: str = None) -> str:
    """Get a nutritional summary of the past 7 days."""
    return get_week_summary(username)


@mcp.tool()
def kb_get_meal_history(days: int = 30, username: str = None) -> str:
    """Browse past meals up to `days` days back."""
    return get_meal_history(days, username)


@mcp.tool()
def kb_plan_week(username: str = None) -> str:
    """Generate a 7-day meal plan prioritizing pantry ingredients (does not persist)."""
    return plan_week(username)


@mcp.tool()
def kb_save_plan(week_label: str = None, username: str = None) -> str:
    """Generate and persist a 7-day meal plan to the database."""
    return save_plan(week_label, username)


@mcp.tool()
def kb_get_grocery_list(week_label: str = None, username: str = None) -> str:
    """Generate a shopping list from a saved meal plan, subtracting what's in the pantry."""
    return get_grocery_list(week_label, username)


# ---------------------------------------------------------------------------
#  SSE auth middleware
# ---------------------------------------------------------------------------

class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        api_key = request.query_params.get("api_key")
        if not api_key:
            return JSONResponse(status_code=401, content={"error": "Missing api_key query parameter"})
        session = get_session()
        user = session.query(User).filter(User.api_key == api_key).first()
        session.close()
        if not user:
            return JSONResponse(status_code=401, content={"error": "Invalid API key"})
        request.state.username = user.name
        return await call_next(request)


def run_server(transport: str = "stdio", host: str = "0.0.0.0", port: int = 8000):
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        sse_app = mcp.sse_app()
        sse_app.add_middleware(ApiKeyAuthMiddleware)
        import uvicorn
        uvicorn.run(sse_app, host=host, port=port)
