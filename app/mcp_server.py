from fastmcp import FastMCP

from app.content import create_post
from app.oauth import create_oauth_provider

auth = create_oauth_provider()

mcp = FastMCP(
    "blog",
    instructions="MCP server for creating blog posts on this markdown blog.",
    auth=auth,
)


@mcp.tool()
def create_blog_post(slug: str, title: str, content: str) -> str:
    """Create a new blog post as a markdown file in the content directory."""
    create_post(slug, title, content)
    return f"Created post at /posts/{slug}"
