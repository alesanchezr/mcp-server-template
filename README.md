# Markdown Blog

A minimal blog built with FastAPI. Each `.md` file in `content/` becomes a page.

- `content/home.md` → `/` (home page)
- `content/my-post.md` → `/posts/my-post`

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000

## Adding posts

Create a file in `content/`:

```markdown
---
title: My Post Title
---

Your markdown content here.
```

If you omit `title`, the filename is used (e.g. `my-cool-post.md` → "My Cool Post").

## Deploy to Railway (free tier)

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) and create a new project
3. Choose **Deploy from GitHub repo** and select this repository
4. Railway auto-detects Python via `requirements.txt` and uses `railway.toml` for the start command
5. Your app gets a public URL under **Settings → Networking → Generate Domain**

No environment variables needed.

## FastMCP (later)

The app is structured so you can mount FastMCP on the same FastAPI instance. See the comment in `app/main.py`.

```python
from fastmcp import FastMCP

mcp = FastMCP("blog")
# add tools here
mcp.mount(app)
```
