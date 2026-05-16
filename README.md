# cookidoo-mcp

An unofficial MCP server for [Cookidoo](https://cookidoo.thermomix.com/) (Thermomix recipe platform).
Lets LLMs help you plan meals, manage your shopping list, and schedule recipes in your meal calendar.

> **Note:** This project uses the unofficial [`cookidoo-api`](https://github.com/miaucl/cookidoo-api) library.
> There is no official Cookidoo API.

---

## Features

| Tool | Description |
|------|-------------|
| `search_recipes` | Search recipes by name, ingredient, or cuisine |
| `get_recipe_details` | Full recipe info: ingredients, timing, nutrition, categories |
| `get_shopping_list` | Current shopping list items |
| `add_to_shopping_list` | Add recipe ingredients to shopping list |
| `remove_from_shopping_list` | Remove recipe ingredients from shopping list |
| `clear_shopping_list` | Wipe the entire shopping list |
| `get_calendar_week` | View meal plan for a given week |
| `add_to_calendar` | Schedule recipes for a specific day |
| `remove_from_calendar` | Remove a recipe from a calendar day |

---

## Setup

### Prerequisites

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv) package manager

### Install

```bash
git clone https://github.com/pawel-rusakiewicz/cookidoo-mcp.git
cd cookidoo-mcp
uv sync
```

### Configure credentials

```bash
cp .env.example .env
# Edit .env and fill in your Cookidoo email, password, and locale
```

`.env` contents:

```
COOKIDOO_EMAIL=your@email.com
COOKIDOO_PASSWORD=yourpassword
COOKIDOO_LOCALE=en-US   # Options: en-US, pl, en-GB, de-DE, fr-FR, es-ES, it-IT, nl-NL, pt-PT, ru-RU
```

### Run the server

```bash
uv run python -m cookidoo_mcp
```

### Local launcher

For Claude Code, install/use the local launcher:

```bash
~/.local/bin/cookidoo-mcp-server
```

It reads credentials from `~/.secrets/cookidoo`. The file can either be a shell
env file:

```bash
COOKIDOO_EMAIL=you@example.com
COOKIDOO_PASSWORD=yourpassword
COOKIDOO_LOCALE=en-US
```

or a single-line password file, in which case the launcher defaults
`COOKIDOO_EMAIL` to `thomas.wilsher@gmail.com` and `COOKIDOO_LOCALE` to `en-US`.

Claude Code registration entry:

```json
{
  "mcpServers": {
    "cookidoo": {
      "command": "/Users/twilsher/.local/bin/cookidoo-mcp-server"
    }
  }
}
```

---

## Claude Desktop integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cookidoo": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/cookidoo-mcp",
        "python",
        "-m",
        "cookidoo_mcp"
      ]
    }
  }
}
```

Replace `/path/to/cookidoo-mcp` with the absolute path to your clone.

---

## Usage examples

Once connected in Claude Desktop or any MCP-capable client:

- *"Find me a quick pasta recipe"* → calls `search_recipes`
- *"What's in my meal plan this week?"* → calls `get_calendar_week`
- *"Add the ingredients for recipe r907001 to my shopping list"* → calls `add_to_shopping_list`
- *"Clear my shopping list"* → calls `clear_shopping_list`
- *"Schedule recipe r907001 for March 20"* → calls `add_to_calendar`

---

## Security

- Credentials are loaded from `.env` only — never hardcoded.
- Tokens are never returned in tool output.
- Recipe data is sanitized before returning to prevent prompt injection.
- `.env` is in `.gitignore` and will never be committed.

---

## License

MIT
