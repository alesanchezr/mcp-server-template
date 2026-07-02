import re
from pathlib import Path

import frontmatter
import markdown

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

CONTENT_DIR = Path(__file__).parent.parent / "content"
md = markdown.Markdown(extensions=["fenced_code", "tables", "toc"])


def _parse(path: Path) -> dict:
    post = frontmatter.load(path)
    title = post.get("title") or path.stem.replace("-", " ").title()
    html = md.convert(post.content)
    md.reset()
    return {"slug": path.stem, "title": title, "html": html, "meta": post.metadata}


def get_home() -> dict:
    return _parse(CONTENT_DIR / "home.md")


def get_post(slug: str) -> dict | None:
    path = CONTENT_DIR / f"{slug}.md"
    if not path.exists() or slug == "home":
        return None
    return _parse(path)


def list_posts() -> list[dict]:
    posts = []
    for path in sorted(CONTENT_DIR.glob("*.md")):
        if path.stem == "home":
            continue
        post = frontmatter.load(path)
        title = post.get("title") or path.stem.replace("-", " ").title()
        posts.append({"slug": path.stem, "title": title})
    return posts


def create_post(slug: str, title: str, content: str) -> None:
    if not SLUG_PATTERN.match(slug):
        raise ValueError(
            "Slug must be lowercase letters, numbers, and hyphens only "
            "(e.g. 'my-cool-post')"
        )
    if slug == "home":
        raise ValueError("Slug 'home' is reserved")

    path = CONTENT_DIR / f"{slug}.md"
    if path.exists():
        raise ValueError(f"A post with slug '{slug}' already exists")

    body = f"---\ntitle: {title}\n---\n\n{content.rstrip()}\n"
    path.write_text(body, encoding="utf-8")
