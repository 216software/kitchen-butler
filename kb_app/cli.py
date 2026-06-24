import click
from kb_app.db import full_setup, DB_PATH


@click.group()
def cli():
    pass


@cli.command()
def init():
    """Initialize the database and seed with default data."""
    full_setup()
    click.echo(f"Kitchen Butler database initialized at {DB_PATH}")


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
    from kb_app.engine.tools import get_pantry

    click.echo(get_pantry())


@cli.command()
@click.argument("ingredient")
@click.argument("quantity", type=float)
@click.option("--unit", default=None, help="Unit (defaults to ingredient default)")
@click.option("--expiry", default=None, help="Expiry date (YYYY-MM-DD)")
def add(ingredient, quantity, unit, expiry):
    """Add an ingredient to your pantry."""
    from kb_app.engine.tools import add_pantry_item

    click.echo(add_pantry_item(ingredient, quantity, unit, expiry))


@cli.command()
def day():
    """Show today's nutritional summary."""
    from kb_app.engine.tools import get_meal_logs_today, get_nutrition_remaining

    click.echo(get_meal_logs_today())
    click.echo()
    click.echo(get_nutrition_remaining())


@cli.command()
@click.option("--top", default=5, help="Number of suggestions to show")
def suggest(top):
    """Suggest recipes based on what's in your pantry."""
    from kb_app.engine.tools import suggest_recipes

    click.echo(suggest_recipes(max_results=top))


@cli.command()
@click.argument("ingredient")
@click.argument("quantity", type=float)
@click.option("--unit", default=None, help="Unit (defaults to ingredient default)")
def update(ingredient, quantity, unit):
    """Update/set the quantity for a pantry ingredient."""
    from kb_app.engine.tools import update_pantry_item

    click.echo(update_pantry_item(ingredient, quantity, unit))


@cli.command()
@click.argument("ingredient")
def remove(ingredient):
    """Remove an ingredient from your pantry entirely."""
    from kb_app.engine.tools import delete_pantry_item

    click.echo(delete_pantry_item(ingredient))


@cli.command()
@click.argument("file", type=click.Path(exists=True))
def add_recipe(file):
    """Add a recipe from a JSON file."""
    import json
    from kb_app.engine.tools import add_recipe as add_recipe_tool

    with open(file) as f:
        data = json.load(f)
    click.echo(add_recipe_tool(**data))


@cli.command()
def db_path():
    """Show the database file path."""
    click.echo(str(DB_PATH))


@cli.command()
def serve():
    """Start the MCP server for opencode integration."""
    from kb_app.mcp_server import run_server
    run_server()
