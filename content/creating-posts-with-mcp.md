---
title: Creating Blog Posts with MCP
---

You don't have to open your editor and hand-write every post. If your blog exposes an **MCP server**, an AI assistant can create posts for you — right from the chat.

## What just happened?

When you ask Cursor (or any MCP-compatible client) to "create a blog post," it calls a tool on your blog's MCP server. That tool writes a new markdown file into `content/`, with frontmatter and body, ready to deploy.

No copy-paste. No switching apps. Just describe what you want and let the agent draft it.

## How it works

1. Your blog runs a FastMCP layer alongside FastAPI
2. The server exposes a `create_blog_post` tool with `slug`, `title`, and `content`
3. The AI client discovers the tool, drafts the post, and calls it
4. A new `.md` file appears in `content/` — same format as posts you write by hand

```python
# Under the hood, something like:
create_post(slug="my-new-post", title="My New Post", content="...")
```

## Why bother?

- **Faster drafts** — turn a rough idea into a published-ready post in one conversation
- **Consistent format** — the tool enforces slug rules and frontmatter structure
- **Same deploy path** — MCP-created posts are plain markdown; push to Railway like anything else

## Tips for good results

- Be specific about topic, tone, and length when you ask
- Pick a clear slug (lowercase, hyphens only, e.g. `my-topic-here`)
- Review the draft before pushing — the AI writes fast, but you're still the editor

## Try it yourself

Connect this blog's MCP server in Cursor, then say:

> Create a new blog post about [your topic]

You'll get a new file in `content/` without touching the filesystem yourself. That's the point of MCP: one protocol, many capabilities — including your blog.
