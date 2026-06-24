# Kitchen Butler (KB)

A kitchen management app that tracks your pantry, logs meals, and suggests recipes. Exposes an **MCP server** so LLM tools (opencode, Claude Code, Cursor, Windsurf, etc.) can manage your kitchen data via natural language.

## Quick Start

```bash
git clone <repo-url> && cd kitchen-butler
python3 -m venv venv
source venv/bin/activate
pip install -e .
kb init
kb setup --name "Your Name" --calories 2500 --protein 100

# Try it out:
kb add "Chicken Breast" 16 --unit oz
kb add "Broccoli" 2 --unit cup
kb add "Rice (White)" 3 --unit "cup cooked"
kb pantry
kb suggest
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
| `kb serve` | Start the MCP server (stdio) |
| `kb add-recipe <file>` | Import a recipe from JSON |

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

Once configured, you can ask your LLM things like:

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
