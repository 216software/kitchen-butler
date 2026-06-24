# Kitchen Brain (KB)

A kitchen management app that tracks your pantry, logs meals, and suggests recipes. Designed to work with **opencode** via MCP — you talk to opencode in natural language, and opencode uses KB's MCP tools to manage your data.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"    # omit [dev] to skip test dependencies

# Initialize database and seed with ingredients + recipes
kb init
```

### First-time user profile

```bash
kb setup --name "Your Name" --calories 2500 --protein 100
```

## CLI Usage

| Command | Description |
|---|---|
| `kb init` | Initialize database and seed with default data |
| `kb setup` | Set up user profile and nutritional goals |
| `kb add "Chicken Breast" 16` | Add an ingredient to your pantry |
| `kb pantry` | List all pantry items |
| `kb suggest` | Suggest recipes based on pantry contents |
| `kb day` | Show today's nutritional summary |
| `kb db-path` | Show the database file path |
| `kb serve` | Start the MCP server (for opencode integration) |

## opencode Integration

Add KB as an MCP server in your `opencode.json` (adjust path to your project):

```json
{
  "mcp": {
    "kitchen-brain": {
      "type": "local",
      "command": ["/home/matt/Documents/brainmeal/venv/bin/kb", "serve"],
      "enabled": true
    }
  }
}
```

Once configured, restart opencode. Then you can ask it things like:

- "What's in my pantry?"
- "What can I make for dinner with what I have?"
- "I ate 4 slices of cheese pizza for lunch — log that"
- "Show me today's nutrition"
- "Add 2 lbs of chicken breast to my pantry"
- "Give me the recipe for Chicken Stir Fry"

## MCP Tools

| Tool | Description |
|---|---|
| `kb_get_pantry` | List all pantry items |
| `kb_search_recipes` | Search recipes by name, cuisine, or ingredient |
| `kb_get_recipe_detail` | Get full recipe details |
| `kb_suggest_recipes` | Suggest recipes ranked by pantry match |
| `kb_log_meal` | Log a meal with ingredients |
| `kb_get_meal_logs_today` | Get today's logged meals |
| `kb_get_nutrition_remaining` | Get remaining calories/protein/fiber for today |
| `kb_get_user_preferences` | Get dietary likes/dislikes |
| `kb_add_pantry_item` | Add an item to the pantry |

## Tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

Requires `pytest` (install via `pip install pytest`).

## Data

Database: `~/.local/share/kitchen-brain/kb.db`. Seeded with 65 ingredients (with per-unit nutrition) and 20 recipes across American, Mexican, Italian, and Asian cuisines.
