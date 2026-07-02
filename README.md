# Markdown Blog

A minimal blog built with FastAPI. Each `.md` file in `content/` becomes a page.

- `content/home.md` → `/` (home page)
- `content/my-post.md` → `/posts/my-post`

The blog also exposes an MCP server at `/mcp/` with OAuth DCR (RFC 8414/7591) for Claude.ai compatibility.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PUBLIC_URL=http://localhost:8000
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

You can also create posts via the MCP `create_blog_post` tool (see below).

## MCP server

The MCP endpoint is at `/mcp/`. It uses OAuth 2.1 with Dynamic Client Registration so Claude.ai can connect automatically.

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PUBLIC_URL` | Yes (production) | Public base URL, e.g. `https://your-app.railway.app`. Defaults to `http://localhost:8000` locally. |

### OAuth discovery endpoints

- `/.well-known/oauth-authorization-server/mcp` — RFC 8414 authorization server metadata
- `/.well-known/oauth-protected-resource/mcp` — RFC 9728 protected resource metadata
- `/mcp/register` — RFC 7591 dynamic client registration
- `/mcp/authorize` — OAuth authorization (shows a simple login page)
- `/mcp/token` — Token exchange

### Connect from Claude.ai

1. Deploy the app with `PUBLIC_URL` set to your public domain
2. In Claude.ai → Settings → Connectors → Add MCP server
3. Enter `https://your-domain/mcp/`
4. Claude discovers OAuth metadata, registers via DCR, and opens the login page
5. Click **Log in** to authorize
6. Ask Claude to create a post, e.g. "Create a blog post titled Hello MCP with slug hello-mcp"

### Available tools

| Tool | Description |
|------|-------------|
| `create_blog_post` | Create a new markdown post (`slug`, `title`, `content`) |

### Local testing

Verify OAuth metadata is reachable:

```bash
curl http://localhost:8000/.well-known/oauth-authorization-server/mcp
```

You should see JSON with a `registration_endpoint` pointing to `/mcp/register`.

## Deploy to Railway (free tier)

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) and create a new project
3. Choose **Deploy from GitHub repo** and select this repository
4. Railway auto-detects Python via `requirements.txt` and uses `railway.toml` for the start command
5. Your app gets a public URL under **Settings → Networking → Generate Domain**
6. Set environment variable `PUBLIC_URL` to your Railway domain (e.g. `https://your-app.up.railway.app`)

### Persistence note

Posts created via MCP are written to `content/` on the container filesystem. Railway's filesystem is ephemeral — posts are lost on redeploy. For persistent storage, mount a Railway volume at `content/` or commit posts to git.
