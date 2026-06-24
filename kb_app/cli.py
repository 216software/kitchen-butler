import click
from kb_app.db import full_setup, DB_PATH


@click.group()
@click.option("--user", default=None, envvar="KB_USER", help="Username (defaults to $KB_USER or config)")
@click.pass_context
def cli(ctx, user):
    ctx.ensure_object(dict)
    ctx.obj["user"] = user


@cli.command()
def init():
    """Initialize the database and seed with default data."""
    full_setup()
    click.echo(f"Kitchen Butler database initialized at {DB_PATH}")


@cli.command()
@click.option("--name", default="Default User", help="Your name")
@click.option("--calories", default=2500, help="Daily calorie goal")
@click.option("--protein", default=100, help="Daily protein goal in grams")
@click.option("--fiber", default=30, help="Daily fiber goal in grams")
def setup(name, calories, protein, fiber):
    """Create or update a user profile."""
    from kb_app.engine.tools import setup_user
    click.echo(setup_user(name, calories, protein, fiber))


@cli.command()
@click.argument("name")
@click.option("--calories", default=2500, help="Daily calorie goal")
@click.option("--protein", default=100, help="Daily protein goal in grams")
@click.option("--fiber", default=30, help="Daily fiber goal in grams")
def add_user(name, calories, protein, fiber):
    """Create a new user (fails if name already exists)."""
    from kb_app.engine.tools import add_user as add_user_tool
    click.echo(add_user_tool(name, calories, protein, fiber))


@cli.command()
def users():
    """List all registered users."""
    from kb_app.engine.tools import list_users
    click.echo(list_users())


@cli.command()
@click.argument("name")
def switch(name):
    """Set the default user (persisted in config file)."""
    from kb_app.config import set_default_user
    set_default_user(name)
    click.echo(f"Default user set to '{name}'.")


@cli.command()
def whoami():
    """Show the current default user."""
    from kb_app.config import get_default_user
    user = get_default_user()
    if user:
        click.echo(f"Current user: {user}")
    else:
        click.echo("No default user set. Use `kb switch <name>` or set $KB_USER.")


@cli.command()
@click.pass_context
def pantry(ctx):
    """List all items in your pantry."""
    from kb_app.engine.tools import get_pantry
    click.echo(get_pantry(username=ctx.obj["user"]))


@cli.command()
@click.argument("ingredient")
@click.argument("quantity", type=float)
@click.option("--unit", default=None, help="Unit (defaults to ingredient default)")
@click.option("--expiry", default=None, help="Expiry date (YYYY-MM-DD)")
@click.pass_context
def add(ingredient, quantity, unit, expiry, ctx):
    """Add an ingredient to your pantry."""
    from kb_app.engine.tools import add_pantry_item
    click.echo(add_pantry_item(ingredient, quantity, unit, expiry, username=ctx.obj["user"]))


@cli.command()
@click.pass_context
def day(ctx):
    """Show today's nutritional summary."""
    from kb_app.engine.tools import get_meal_logs_today, get_nutrition_remaining
    click.echo(get_meal_logs_today(username=ctx.obj["user"]))
    click.echo()
    click.echo(get_nutrition_remaining(username=ctx.obj["user"]))


@cli.command()
@click.option("--top", default=5, help="Number of suggestions to show")
@click.option("--prefer-tag", default=None, help="Prefer recipes with this tag (e.g. 'low carb')")
@click.option("--avoid-dislikes", is_flag=True, default=False, help="Exclude recipes with disliked ingredients")
@click.pass_context
def suggest(ctx, top, prefer_tag, avoid_dislikes):
    """Suggest recipes based on what's in your pantry."""
    from kb_app.engine.tools import suggest_recipes
    click.echo(suggest_recipes(max_results=top, username=ctx.obj["user"], prefer_tag=prefer_tag, avoid_dislikes=avoid_dislikes))


@cli.command()
@click.option("--days", default=7, help="Number of days to look ahead")
@click.pass_context
def expire(ctx, days):
    """Show pantry items nearing expiry."""
    from kb_app.engine.tools import get_expiring_items
    click.echo(get_expiring_items(days=days, username=ctx.obj["user"]))


@cli.command()
@click.pass_context
def week(ctx):
    """Show weekly nutritional summary."""
    from kb_app.engine.tools import get_week_summary
    click.echo(get_week_summary(username=ctx.obj["user"]))


@cli.command()
@click.option("--days", default=30, help="How far back to look")
@click.pass_context
def history(ctx, days):
    """Browse past meals."""
    from kb_app.engine.tools import get_meal_history
    click.echo(get_meal_history(days=days, username=ctx.obj["user"]))


@cli.command()
@click.option("--save", is_flag=True, default=False, help="Persist the plan to the database")
@click.option("--week", "week_label", default=None, help="Week label (e.g. '2026-W26')")
@click.pass_context
def plan_week(ctx, save, week_label):
    """Generate a 7-day meal plan prioritizing pantry ingredients."""
    from kb_app.engine.tools import plan_week, save_plan
    if save:
        click.echo(save_plan(week_label=week_label, username=ctx.obj["user"]))
    else:
        click.echo(plan_week(username=ctx.obj["user"]))


@cli.command()
@click.option("--week", "week_label", default=None, help="Week label (e.g. '2026-W26')")
@click.pass_context
def grocery_list(ctx, week_label):
    """Generate a shopping list from the current meal plan."""
    from kb_app.engine.tools import get_grocery_list
    click.echo(get_grocery_list(week_label=week_label, username=ctx.obj["user"]))


@cli.command()
@click.argument("ingredient")
@click.argument("quantity", type=float)
@click.option("--unit", default=None, help="Unit (defaults to ingredient default)")
@click.pass_context
def update(ingredient, quantity, unit, ctx):
    """Update/set the quantity for a pantry ingredient."""
    from kb_app.engine.tools import update_pantry_item
    click.echo(update_pantry_item(ingredient, quantity, unit, username=ctx.obj["user"]))


@cli.command()
@click.argument("ingredient")
@click.pass_context
def remove(ingredient, ctx):
    """Remove an ingredient from your pantry entirely."""
    from kb_app.engine.tools import delete_pantry_item
    click.echo(delete_pantry_item(ingredient, username=ctx.obj["user"]))


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
@click.option("--transport", default="stdio", type=click.Choice(["stdio", "sse"]), help="Transport protocol")
@click.option("--host", default="0.0.0.0", help="Host to bind (SSE only)")
@click.option("--port", default=8000, help="Port to bind (SSE only)")
def serve(transport, host, port):
    """Start the MCP server (stdio for local, SSE for remote)."""
    from kb_app.mcp_server import run_server
    run_server(transport=transport, host=host, port=port)


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind")
@click.option("--port", default=8001, help="Port to bind")
def serve_gpt(host, port):
    """Start the GPT API server (REST, for Custom GPT integration)."""
    from kb_app.gpt_api import run_gpt_api
    run_gpt_api(host=host, port=port)
