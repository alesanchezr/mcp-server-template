from fastmcp import FastMCP

from app.content import create_post, list_posts
from app.oauth import create_oauth_provider

auth = create_oauth_provider()

mcp = FastMCP(
    "blog",
    instructions="MCP server for creating blog posts on this markdown blog.",
    auth=auth,
)


@mcp.tool()
def list_blog_posts() -> list[dict]:
    """List all blog posts with their slugs and titles."""
    return list_posts()


@mcp.tool()
def create_blog_post(slug: str, title: str, content: str) -> str:
    """Create a new blog post as a markdown file in the content directory."""
    create_post(slug, title, content)
    return f"Created post at /posts/{slug}"
