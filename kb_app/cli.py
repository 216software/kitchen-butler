import click

from kb_app.db import full_setup, DB_PATH


@click.group()
def cli():
    pass


@cli.command()
def init():
    """Initialize the database and seed with default data."""
    full_setup()
    click.echo(f"Kitchen Brain database initialized at {DB_PATH}")


@cli.command()
@click.option("--name", default="Default User", help="Your name")
@click.option("--calories", default=2500, help="Daily calorie goal")
@click.option("--protein", default=100, help="Daily protein goal in grams")
def setup(name, calories, protein):
    """Set up your user profile and nutritional goals."""
    from kb_app.db import get_session
    from kb_app.models import User

    session = get_session()
    existing = session.query(User).first()
    if existing:
        existing.name = name
        existing.calorie_goal = calories
        existing.protein_goal = protein
        click.echo(f"Updated user '{name}'.")
    else:
        session.add(User(name=name, calorie_goal=calories, protein_goal=protein))
        click.echo(f"Created user '{name}'.")
    session.commit()
    session.close()


@cli.command()
def pantry():
    """List all items in your pantry."""
    from kb_app.db import get_session
    from kb_app.models import PantryItem, User

    session = get_session()
    user = session.query(User).first()
    if not user:
        click.echo("No user found. Run 'kb setup' first.")
        session.close()
        return

    items = session.query(PantryItem).filter_by(user_id=user.id).all()
    if not items:
        click.echo("Your pantry is empty.")
    else:
        for item in items:
            ing = item.ingredient
            expiry = f" (expires {item.expiry_date})" if item.expiry_date else ""
            click.echo(f"  {ing.name}: {item.quantity} {item.unit}{expiry}")
    session.close()


@cli.command()
@click.argument("ingredient")
@click.argument("quantity", type=float)
@click.option("--unit", default=None, help="Unit (defaults to ingredient default)")
@click.option("--expiry", default=None, help="Expiry date (YYYY-MM-DD)")
def add(ingredient, quantity, unit, expiry):
    """Add an ingredient to your pantry."""
    import json
    from datetime import date
    from kb_app.db import get_session
    from kb_app.models import PantryItem, Ingredient, User

    session = get_session()
    user = session.query(User).first()
    if not user:
        click.echo("No user found. Run 'kb setup' first.")
        session.close()
        return

    ing = session.query(Ingredient).filter(Ingredient.name.ilike(ingredient)).first()
    if not ing:
        ing = session.query(Ingredient).filter(Ingredient.name.ilike(f"%{ingredient}%")).first()
    if not ing:
        click.echo(f"Ingredient '{ingredient}' not found. Available: type any partial name.")
        session.close()
        return

    unit = unit or ing.default_unit
    expiry_date = date.fromisoformat(expiry) if expiry else None

    item = PantryItem(user_id=user.id, ingredient_id=ing.id, quantity=quantity, unit=unit, expiry_date=expiry_date)
    session.add(item)
    session.commit()
    click.echo(f"Added {quantity} {unit} of {ing.name} to pantry.")
    session.close()


@cli.command()
def db_path():
    """Show the database file path."""
    click.echo(str(DB_PATH))
