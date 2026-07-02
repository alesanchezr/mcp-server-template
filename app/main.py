import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.content import get_home, get_post, list_posts
from app.mcp_server import auth, mcp

mcp_app = mcp.http_app(path="/")
app = FastAPI(title="Blog", lifespan=mcp_app.lifespan)
templates = Jinja2Templates(directory="app/templates")

for route in auth.get_well_known_routes(mcp_path=None):
    app.routes.insert(0, route)


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
