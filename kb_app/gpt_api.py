"""FastAPI REST API — auth + tool endpoints for Custom GPT integration."""

from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from kb_app.db import get_session
from kb_app.models import User
from kb_app.engine import tools as T

app = FastAPI(
    title="Kitchen Butler API",
    description="REST API for Kitchen Butler — food management with pantry, recipes, meal logging, and menu planning.",
    version="1.0.0",
    servers=[
        {"url": "https://kb-gpt.216software.com", "description": "Production"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
#  Auth helpers
# ---------------------------------------------------------------------------


def _get_user_by_request(request: Request):
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization. Use: Bearer <api_key>")
    user, session = T._get_user(api_key=token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    session.close()
    return user


# ---------------------------------------------------------------------------
#  Request / Response models
# ---------------------------------------------------------------------------


class SignupRequest(BaseModel):
    name: str = Field(..., description="Username")
    calorie_goal: int = Field(2500, description="Daily calorie target")
    protein_goal: int = Field(100, description="Daily protein target (g)")
    fiber_goal: int = Field(30, description="Daily fiber target (g)")

class SignupResponse(BaseModel):
    api_key: str
    user_id: int
    name: str

class LoginRequest(BaseModel):
    name: str
    api_key: str

class LoginResponse(BaseModel):
    valid: bool
    name: str
    user_id: int

class WhoamiResponse(BaseModel):
    name: str
    user_id: int
    calorie_goal: int
    protein_goal: int
    fiber_goal: int

class LogMealItem(BaseModel):
    ingredient_name: str
    quantity: float
    unit: str

class LogMealRequest(BaseModel):
    items: list[LogMealItem]
    notes: str = ""

class PantryAddRequest(BaseModel):
    name: str
    quantity: float
    unit: Optional[str] = None
    expiry: Optional[str] = None

class PantryUpdateRequest(BaseModel):
    name: str
    quantity: float
    unit: Optional[str] = None

class PantryDeleteRequest(BaseModel):
    name: str

class RecipeIngredientItem(BaseModel):
    name: str
    quantity: float
    unit: str
    optional: bool = False
    category: Optional[str] = None

class RecipeNutritionInfo(BaseModel):
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    fiber_g: Optional[float] = None

class RecipeAddRequest(BaseModel):
    name: str
    cuisine: str
    instructions: str
    servings: int = 2
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    ingredients: list[RecipeIngredientItem] = []
    nutrition: Optional[RecipeNutritionInfo] = None
    tags: list[str] = []


# ---------------------------------------------------------------------------
#  Auth endpoints (no auth required)
# ---------------------------------------------------------------------------


@app.post("/auth/signup", response_model=SignupResponse, tags=["Auth"])
def signup(body: SignupRequest):
    """Create a new user account. Returns an API key — save this, it's your auth token."""
    result = T.add_user(body.name, body.calorie_goal, body.protein_goal, body.fiber_goal)
    if "already exists" in result:
        raise HTTPException(status_code=409, detail=result)
    session = get_session()
    user = session.query(User).filter(User.name.ilike(body.name)).first()
    session.close()
    return SignupResponse(api_key=user.api_key, user_id=user.id, name=user.name)


@app.post("/auth/login", response_model=LoginResponse, tags=["Auth"])
def login(body: LoginRequest):
    """Validate that a username + api_key pair is correct."""
    user, session = T._get_user(api_key=body.api_key)
    if not user or user.name.lower() != body.name.lower():
        if session:
            session.close()
        raise HTTPException(status_code=401, detail="Invalid username or API key")
    session.close()
    return LoginResponse(valid=True, name=user.name, user_id=user.id)


@app.get("/auth/whoami", response_model=WhoamiResponse, tags=["Auth"])
def whoami(username: str = Header(None, alias="X-Username")):
    """Get current user info by X-Username header."""
    user, session = T._get_user(username=username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    session.close()
    return WhoamiResponse(
        name=user.name, user_id=user.id,
        calorie_goal=user.calorie_goal, protein_goal=user.protein_goal,
        fiber_goal=user.fiber_goal,
    )


# ---------------------------------------------------------------------------
#  Tool endpoints (auth required — Bearer token via Authorization header)
# ---------------------------------------------------------------------------


@app.get("/pantry", tags=["Pantry"])
def get_pantry(request: Request):
    """List all items in your pantry."""
    user = _get_user_by_request(request)
    return {"result": T.get_pantry(username=user.name)}


@app.post("/pantry/add", tags=["Pantry"])
def add_pantry_item(body: PantryAddRequest, request: Request):
    """Add an ingredient to your pantry."""
    user = _get_user_by_request(request)
    return {"result": T.add_pantry_item(body.name, body.quantity, body.unit, body.expiry, username=user.name)}


@app.post("/pantry/update", tags=["Pantry"])
def update_pantry_item(body: PantryUpdateRequest, request: Request):
    """Update/set quantity for a pantry ingredient."""
    user = _get_user_by_request(request)
    return {"result": T.update_pantry_item(body.name, body.quantity, body.unit, username=user.name)}


@app.post("/pantry/delete", tags=["Pantry"])
def delete_pantry_item(body: PantryDeleteRequest, request: Request):
    """Remove an ingredient from your pantry."""
    user = _get_user_by_request(request)
    return {"result": T.delete_pantry_item(body.name, username=user.name)}


@app.get("/pantry/expiring", tags=["Pantry"])
def get_expiring(days: int = 7, request: Request = None):
    """Show pantry items expiring within N days."""
    user = _get_user_by_request(request)
    return {"result": T.get_expiring_items(days, username=user.name)}


@app.get("/recipes/search", tags=["Recipes"])
def search_recipes(query: str = "", cuisine: str = "", tag: str = "", max_results: int = 5):
    """Search for recipes by name, cuisine, or tag."""
    return {"result": T.search_recipes(query, cuisine, tag, max_results)}


@app.get("/recipes/{recipe_id}", tags=["Recipes"])
def get_recipe_detail(recipe_id: int):
    """Get full recipe details."""
    return {"result": T.get_recipe_detail(recipe_id)}


@app.post("/recipes/suggest", tags=["Recipes"])
def suggest_recipes(max_results: int = 5, prefer_tag: str = None, avoid_dislikes: bool = False, request: Request = None):
    """Suggest recipes based on your pantry."""
    user = _get_user_by_request(request)
    return {"result": T.suggest_recipes(max_results, username=user.name, prefer_tag=prefer_tag, avoid_dislikes=avoid_dislikes)}


@app.post("/recipes/add", tags=["Recipes"])
def add_recipe(body: RecipeAddRequest, request: Request):
    """Add a new recipe."""
    _get_user_by_request(request)
    ings = [i.model_dump() for i in body.ingredients]
    nut = body.nutrition.model_dump() if body.nutrition else None
    return {"result": T.add_recipe(body.name, body.cuisine, body.instructions, body.servings, body.prep_time, body.cook_time, ings, nut, body.tags)}


@app.post("/meals/log", tags=["Meals"])
def log_meal(body: LogMealRequest, request: Request):
    """Log a meal with ingredients."""
    user = _get_user_by_request(request)
    items = [i.model_dump() for i in body.items]
    return {"result": T.log_meal(items, body.notes, username=user.name)}


@app.get("/meals/today", tags=["Meals"])
def get_meals_today(request: Request):
    """Get all meals logged today."""
    user = _get_user_by_request(request)
    return {"result": T.get_meal_logs_today(username=user.name)}


@app.get("/meals/history", tags=["Meals"])
def get_meal_history(days: int = 30, request: Request = None):
    """Browse past meals."""
    user = _get_user_by_request(request)
    return {"result": T.get_meal_history(days, username=user.name)}


@app.get("/nutrition/remaining", tags=["Nutrition"])
def get_nutrition_remaining(request: Request):
    """Get today's remaining nutritional budget."""
    user = _get_user_by_request(request)
    return {"result": T.get_nutrition_remaining(username=user.name)}


@app.get("/nutrition/week", tags=["Nutrition"])
def get_week_summary(request: Request):
    """Get a nutritional summary of the past 7 days."""
    user = _get_user_by_request(request)
    return {"result": T.get_week_summary(username=user.name)}


@app.get("/preferences", tags=["Preferences"])
def get_preferences(request: Request):
    """Get your dietary likes and dislikes."""
    user = _get_user_by_request(request)
    return {"result": T.get_user_preferences(username=user.name)}


@app.post("/plan/week", tags=["Planning"])
def plan_week(request: Request):
    """Generate a 7-day meal plan (does not persist)."""
    user = _get_user_by_request(request)
    return {"result": T.plan_week(username=user.name)}


@app.post("/plan/save", tags=["Planning"])
def save_plan(week_label: str = None, request: Request = None):
    """Generate and persist a 7-day meal plan."""
    user = _get_user_by_request(request)
    return {"result": T.save_plan(week_label, username=user.name)}


@app.get("/plan/grocery-list", tags=["Planning"])
def get_grocery_list(week_label: str = None, request: Request = None):
    """Generate a shopping list from a saved meal plan."""
    user = _get_user_by_request(request)
    return {"result": T.get_grocery_list(week_label, username=user.name)}


@app.get("/users/me", response_model=WhoamiResponse, tags=["Users"])
def get_current_user(request: Request):
    """Get your user profile."""
    user = _get_user_by_request(request)
    return WhoamiResponse(
        name=user.name, user_id=user.id,
        calorie_goal=user.calorie_goal, protein_goal=user.protein_goal,
        fiber_goal=user.fiber_goal,
    )


@app.get("/users", tags=["Users"])
def list_users(request: Request):
    """List all registered users."""
    _get_user_by_request(request)
    return {"result": T.list_users()}


# ---------------------------------------------------------------------------
#  Entrypoint
# ---------------------------------------------------------------------------


def run_gpt_api(host: str = "0.0.0.0", port: int = 8001):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
