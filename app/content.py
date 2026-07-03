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


def validate_post(slug: str, title: str, content: str) -> list[str]:
    """Return a list of validation errors. Empty list means the post is valid."""
    errors: list[str] = []
    slug = slug.strip()
    title = title.strip()
    content = content.strip()

    if not slug:
        errors.append("Slug is required.")
    elif not SLUG_PATTERN.match(slug):
        errors.append(
            "Slug must be lowercase letters, numbers, and hyphens only "
            "(e.g. 'my-cool-post')."
        )
    elif slug == "home":
        errors.append("Slug 'home' is reserved.")
    elif (CONTENT_DIR / f"{slug}.md").exists():
        errors.append(f"A post with slug '{slug}' already exists.")

    if not title:
        errors.append("Title is required.")

    if not content:
        errors.append("Content is required.")
    elif content.startswith("---"):
        errors.append(
            "Content must be the post body only — do not include YAML frontmatter. "
            "Pass the title via the title parameter."
        )

    if errors:
        return errors

    try:
        post = frontmatter.Post(content, title=title)
        text = frontmatter.dumps(post)
        parsed = frontmatter.loads(text)
    except Exception as exc:
        errors.append(f"Frontmatter is invalid: {exc}")
        return errors

    if parsed.get("title") != title:
        errors.append("Title could not be preserved in frontmatter.")

    try:
        converter = markdown.Markdown(extensions=["fenced_code", "tables", "toc"])
        converter.convert(parsed.content)
        converter.reset()
    except Exception as exc:
        errors.append(f"Markdown is invalid: {exc}")

    return errors


def format_validation_errors(errors: list[str]) -> str:
    return "Post validation failed:\n" + "\n".join(f"- {error}" for error in errors)


def create_post(slug: str, title: str, content: str) -> None:
    errors = validate_post(slug, title, content)
    if errors:
        raise ValueError(format_validation_errors(errors))

    slug = slug.strip()
    title = title.strip()
    content = content.strip()

    path = CONTENT_DIR / f"{slug}.md"
    post = frontmatter.Post(content, title=title)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
