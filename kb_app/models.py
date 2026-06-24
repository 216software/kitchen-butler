import secrets
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, Date, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    api_key: Mapped[str] = mapped_column(String(128), default=lambda: secrets.token_hex(32))
    calorie_goal: Mapped[int] = mapped_column(default=2500)
    protein_goal: Mapped[int] = mapped_column(default=100)
    fiber_goal: Mapped[int] = mapped_column(default=30)
    vitamins_goal: Mapped[str] = mapped_column(Text, default="standard USRDA")

    preferences: Mapped[list["Preference"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    pantry_items: Mapped[list["PantryItem"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    meal_logs: Mapped[list["MealLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    meal_plans: Mapped[list["MealPlan"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    grocery_purchases: Mapped[list["GroceryPurchase"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Preference(Base):
    __tablename__ = "preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(16))
    item: Mapped[str] = mapped_column(String(128))

    user: Mapped["User"] = relationship(back_populates="preferences")


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    category: Mapped[str] = mapped_column(String(64))
    default_unit: Mapped[str] = mapped_column(String(32))

    nutrition: Mapped[Optional["Nutrition"]] = relationship(back_populates="ingredient", uselist=False, cascade="all, delete-orphan")


class Nutrition(Base):
    __tablename__ = "nutrition"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), unique=True)
    per_unit: Mapped[str] = mapped_column(String(32))
    calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    fiber_g: Mapped[float] = mapped_column(Float, default=0)
    vitamins_json: Mapped[str] = mapped_column(Text, default="{}")

    ingredient: Mapped["Ingredient"] = relationship(back_populates="nutrition")


class PantryItem(Base):
    __tablename__ = "pantry"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    purchased_date: Mapped[date] = mapped_column(Date, default=date.today)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    user: Mapped["User"] = relationship(back_populates="pantry_items")
    ingredient: Mapped["Ingredient"] = relationship()


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    cuisine: Mapped[str] = mapped_column(String(64))
    prep_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cook_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    servings: Mapped[int] = mapped_column(Integer, default=2)
    instructions_text: Mapped[str] = mapped_column(Text)
    tags: Mapped[str] = mapped_column(Text, default="[]")

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(back_populates="recipe", cascade="all, delete-orphan")
    nutrition: Mapped[Optional["RecipeNutrition"]] = relationship(back_populates="recipe", uselist=False, cascade="all, delete-orphan")


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    optional: Mapped[bool] = mapped_column(Boolean, default=False)

    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")
    ingredient: Mapped["Ingredient"] = relationship()


class RecipeNutrition(Base):
    __tablename__ = "recipe_nutrition"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), unique=True)
    per_serving_calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    fiber_g: Mapped[float] = mapped_column(Float, default=0)
    vitamins_json: Mapped[str] = mapped_column(Text, default="{}")

    recipe: Mapped["Recipe"] = relationship(back_populates="nutrition")


class MealLog(Base):
    __tablename__ = "meal_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="meal_logs")
    items: Mapped[list["MealLogItem"]] = relationship(back_populates="meal_log", cascade="all, delete-orphan")


class MealLogItem(Base):
    __tablename__ = "meal_log_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    meal_log_id: Mapped[int] = mapped_column(ForeignKey("meal_logs.id"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))

    meal_log: Mapped["MealLog"] = relationship(back_populates="items")
    ingredient: Mapped["Ingredient"] = relationship()


class MealPlan(Base):
    __tablename__ = "meal_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    week_label: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped["User"] = relationship(back_populates="meal_plans")
    days: Mapped[list["MealPlanDay"]] = relationship(back_populates="meal_plan", cascade="all, delete-orphan")


class MealPlanDay(Base):
    __tablename__ = "meal_plan_days"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("meal_plans.id"))
    day_name: Mapped[str] = mapped_column(String(16))
    meal_type: Mapped[str] = mapped_column(String(16))
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"))

    meal_plan: Mapped["MealPlan"] = relationship(back_populates="days")
    recipe: Mapped["Recipe"] = relationship()


class GroceryPurchase(Base):
    __tablename__ = "grocery_purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    source: Mapped[str] = mapped_column(String(32), default="manual")

    user: Mapped["User"] = relationship(back_populates="grocery_purchases")
    items: Mapped[list["GroceryPurchaseItem"]] = relationship(back_populates="purchase", cascade="all, delete-orphan")


class GroceryPurchaseItem(Base):
    __tablename__ = "grocery_purchase_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("grocery_purchases.id"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    purchase: Mapped["GroceryPurchase"] = relationship(back_populates="items")
    ingredient: Mapped["Ingredient"] = relationship()
