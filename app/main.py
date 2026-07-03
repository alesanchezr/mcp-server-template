import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from app.content import get_home, get_post, list_posts
from app.mcp_server import auth, mcp

logger = logging.getLogger(__name__)

mcp_app = mcp.http_app(path="/")
mcp_app.router.redirect_slashes = False
app = FastAPI(title="Blog", lifespan=mcp_app.lifespan)
app.router.redirect_slashes = False
templates = Jinja2Templates(directory="app/templates")

for route in auth.get_well_known_routes(mcp_path=None):
    app.routes.insert(0, route)


class McpRootForward:
    """Forward POST /mcp (no trailing slash) to the mounted MCP app.

    Starlette Mount only matches /mcp/... with a slash after /mcp, so bare /mcp
    would 307-redirect. Claude.ai POSTs to /mcp and does not follow redirects
    with the Bearer token.
    """

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope = dict(scope)
        scope["path"] = "/"
        scope["root_path"] = (scope.get("root_path") or "") + "/mcp"
        await self.asgi_app(scope, receive, send)


app.router.routes.insert(
    0,
    Route(
        "/mcp",
        endpoint=McpRootForward(mcp_app),
        methods=["GET", "POST", "DELETE", "OPTIONS"],
    ),
)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    page = get_home()
    return templates.TemplateResponse(
        request, "page.html", {"page": page, "posts": list_posts(), "is_home": True}
    )


@app.get("/posts/{slug}", response_class=HTMLResponse)
async def post(request: Request, slug: str):
    page = get_post(slug)
    if not page:
        raise HTTPException(status_code=404, detail="Post not found")
    return templates.TemplateResponse(
        request, "page.html", {"page": page, "posts": list_posts(), "is_home": False}
    )


app.mount("/mcp", mcp_app)

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
