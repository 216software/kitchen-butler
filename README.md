# Kitchen Butler (KB)

> **Requires Python 3.11+**

A kitchen management app that tracks your pantry, logs meals, and suggests recipes. Exposes an **MCP server** so LLM tools (opencode, Claude Code, Cursor, Windsurf, etc.) can manage your kitchen data via natural language.

## Quick Start

```bash
git clone <repo-url> && cd kitchen-butler
python3 -m venv venv
source venv/bin/activate
pip install -e .
kb init
kb setup --name "Your Name" --calories 2500 --protein 100 --fiber 30
```

This initializes the database, seeds ingredients and recipes, and creates your user profile with daily nutritional goals.

### Try it out

```bash
# Add some items to your pantry
kb add "Chicken Breast" 16 --unit oz
kb add "Broccoli" 2 --unit cup
kb add "Rice (White)" 3 --unit "cup cooked"

# See what's in your pantry
kb pantry

# See which recipes match what you have
kb suggest

# Check today's nutrition vs your goals
kb day
```

(`kb init` is safe to re-run — it skips seeding if the database already has data.)

### Next steps

- To use KB with an LLM tool (opencode, Claude Code, etc.), see **MCP Integration** below.
- To add your own recipes, see `kb add-recipe` in the CLI table.

## CLI Usage

| Command | Description |
|---|---|
| `kb init` | Initialize database and seed with default data |
| `kb setup` | Set up user profile and nutritional goals |
| `kb add <ingredient> <qty>` | Add an ingredient to your pantry |
| `kb update <ingredient> <qty>` | Set an ingredient's quantity |
| `kb remove <ingredient>` | Remove an ingredient from your pantry |
| `kb pantry` | List all pantry items |
| `kb suggest` | Suggest recipes based on pantry contents |
| `kb day` | Show today's nutritional summary |
| `kb serve` | Start the MCP server (stdio) |
| `kb db-path` | Show the database file path |
| `kb add-recipe <file>` | Import a recipe from JSON (see format below) |

### `kb add-recipe` JSON format

```json
{
  "name": "My Recipe",
  "cuisine": "italian",
  "prep_time": 10,
  "cook_time": 25,
  "servings": 4,
  "tags": ["dinner", "vegetarian"],
  "ingredients": [
    {"name": "Pasta", "quantity": 4, "unit": "cup cooked"},
    {"name": "Garlic", "quantity": 3, "unit": "clove"}
  ],
  "nutrition": {
    "calories": 400,
    "protein_g": 15,
    "fiber_g": 3
  },
  "instructions": "Cook pasta. Saute garlic..."
}
```

Unknown ingredients are auto-created with category "imported" and zero nutrition.

## MCP Integration

KB runs an MCP server on stdio (`kb serve`). Configure it in your LLM tool of choice:

### Claude Code

`.mcp.json` is already included in the project for auto-discovery. No manual config needed — Claude Code finds it automatically.

Alternatively, add to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kitchen-butler": {
      "command": "/path/to/kitchen-butler/venv/bin/kb",
      "args": ["serve"]
    }
  }
}
```

### opencode

Add to your project's `opencode.json` (copy from `opencode.json.example`):

```json
{
  "mcp": {
    "kitchen-butler": {
      "type": "local",
      "command": ["./venv/bin/kb", "serve"],
      "enabled": true
    }
  }
}
```

### Cursor / Windsurf / others

All use the same pattern — configure a stdio MCP server pointing to `<project>/venv/bin/kb serve`. See your tool's MCP documentation.

### Test your setup

```bash
kb serve
```

Then ask your LLM tool:

- "What's in my pantry?"
- "What can I make for dinner with what I have?"
- "I ate 4 slices of cheese pizza for lunch — log that"
- "Show me today's nutrition"
- "Add 2 lbs of chicken breast to my pantry"

## MCP Tools

| Tool | Description |
|---|---|
| `kb_get_pantry` | List all pantry items |
| `kb_search_recipes` | Search recipes by name, cuisine, or tag |
| `kb_get_recipe_detail` | Get full recipe details |
| `kb_suggest_recipes` | Suggest recipes ranked by pantry match |
| `kb_log_meal` | Log a meal with ingredients |
| `kb_get_meal_logs_today` | Get today's logged meals |
| `kb_get_nutrition_remaining` | Get remaining calories/protein/fiber |
| `kb_get_user_preferences` | Get dietary likes/dislikes |
| `kb_add_pantry_item` | Add an item to the pantry (merges duplicates) |
| `kb_update_pantry_item` | Set item quantity |
| `kb_delete_pantry_item` | Remove item from pantry |
| `kb_add_recipe` | Add a new recipe with ingredients |

## Tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

## Data

Database: `~/.local/share/kitchen-butler/kb.db`. Seeded with 65+ ingredients (with per-unit nutrition) and 24 recipes across American, Mexican, Italian, and Asian cuisines.
