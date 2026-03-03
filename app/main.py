# app/main.py
"""
AI Blog Automation – FastAPI Application Entry Point (v2.0.0)

Architecture:
  - Lifespan context manager replaces deprecated @app.on_event
  - Structured logging via core.logging
  - Centralized exception handling via core.exceptions
  - Production-grade middleware stack via core.middleware
  - OpenAPI metadata for professional API documentation
"""
# ── UTF-8 fix (MUST be first) ──────────────────────────────────────────────────
# Windows default codec is cp1252; reconfigure() safely switches to UTF-8
# without replacing the stream object (avoids Errno 22 when uvicorn owns it).
import sys
import os

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    except Exception:
        pass

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

# ── Core imports (must happen before routes) ─────────────────────────────────
from core.config import settings
from core.logging import setup_logging, get_logger
from core.middleware import RequestIDMiddleware, ProcessTimeMiddleware, RequestLoggingMiddleware
from core.exceptions import register_exception_handlers

# ── Initialize logging FIRST ──────────────────────────────────────────────────
setup_logging()
logger = get_logger(__name__)

# ── App imports ───────────────────────────────────────────────────────────────
from app.database import db
from app.routes import generate_blog, publish_post, websites, image_gen, seo_score, auth, admin_data


# ─── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Async context manager to handle startup and shutdown events.
    Replaces the deprecated @app.on_event("startup") / ("shutdown") pattern.
    """
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info(
        "Application starting",
        extra={
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "groq_configured": settings.groq_configured,
            "pexels_configured": settings.pexels_configured,
        },
    )

    # Ensure data directories exist
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/images", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # Initialize database tables
    await db.init_db()
    logger.info("Database initialized successfully")

    yield  # ── Application runs here ──────────────────────────────────────────

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Application shutting down gracefully")


# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "**AI Blog Automation** – Production-ready SEO content generation engine.\n\n"
        "Generates Yoast-optimized blog posts via Groq (LLaMA 3.3), "
        "publishes to WordPress / Ghost, and tracks SEO performance."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ─── Middleware ───────────────────────────────────────────────────────────────

# Order matters: outermost → innermost
app.add_middleware(RequestIDMiddleware)
app.add_middleware(ProcessTimeMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Exception Handlers ───────────────────────────────────────────────────────
register_exception_handlers(app)

# ─── Static Files & Templates ─────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="ui/static"), name="static")
os.makedirs("data/images", exist_ok=True)
app.mount("/data/images", StaticFiles(directory="data/images"), name="generated-images")
templates = Jinja2Templates(directory="ui/templates")

# ─── API Routers ──────────────────────────────────────────────────────────────
app.include_router(generate_blog.router, prefix="/api", tags=["📝 Content Generation"])
app.include_router(publish_post.router,  prefix="/api", tags=["🚀 Publishing"])
app.include_router(websites.router,      prefix="/api", tags=["🌐 Websites"])
app.include_router(image_gen.router, prefix="/api")
app.include_router(seo_score.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(admin_data.router, prefix="/api")

# ─── WordPress Config Check ───────────────────────────────────────────────────

class WordPressCheck(BaseModel):
    api_url: str
    username: str
    password: str


@app.post("/api/check-wordpress", tags=["🔧 Utilities"])
async def check_wordpress_config(config: WordPressCheck):
    """Check WordPress REST API connectivity and permalink structure."""
    try:
        auth = (config.username, config.password)
        test_url = f"{config.api_url.rstrip('/')}/wp-json/wp/v2/posts?per_page=1"
        response = requests.get(test_url, auth=auth, timeout=10)

        if response.status_code == 401:
            return {"success": False, "error": "Authentication failed. Check username and password."}

        if response.status_code != 200:
            return {"success": False, "error": f"Connection failed with status {response.status_code}"}

        posts = response.json()
        permalink_type = "unknown"
        if posts:
            sample_url = posts[0].get("link", "")
            permalink_type = "default" if "?p=" in sample_url else "pretty"

        return {
            "success": True,
            "permalink_type": permalink_type,
            "message": "WordPress connection successful!",
            "warning": (
                "Please set permalinks to 'Post name' in WordPress settings"
                if permalink_type == "default"
                else None
            ),
        }

    except requests.exceptions.RequestException as exc:
        logger.warning("WordPress check failed", extra={"error": str(exc)})
        return {"success": False, "error": str(exc)}


# ─── Frontend Routes ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page(request: Request):
    """Serve the SaaS landing page."""
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    """Serve the login page."""
    return templates.TemplateResponse("auth.html", {"request": request, "mode": "login", "page_title": "Log In"})


@app.get("/signup", response_class=HTMLResponse, include_in_schema=False)
async def signup_page(request: Request):
    """Serve the signup page."""
    return templates.TemplateResponse("auth.html", {"request": request, "mode": "signup", "page_title": "Sign Up"})


@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request):
    """Serve the main dashboard SPA (requires login)."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/post/{post_id}", response_class=HTMLResponse, include_in_schema=False)
async def post_preview(request: Request, post_id: int):
    """Serve the post preview page."""
    return templates.TemplateResponse(
        "post_preview.html", {"request": request, "post_id": post_id}
    )

@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_login_page(request: Request):
    """Serve the admin login page."""
    return templates.TemplateResponse("auth.html", {"request": request, "mode": "login", "page_title": "Admin Login"})


@app.get("/admin/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def admin_dashboard(request: Request):
    """Serve the admin dashboard."""
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["🔧 Utilities"])
async def health_check():
    """
    Lightweight health-probe endpoint.
    Returns 200 when the application is ready to serve traffic.
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "integrations": {
            "groq_api": settings.groq_configured,
            "pexels_api": settings.pexels_configured,
            "huggingface_api": settings.hf_configured,
        },
        "features": {
            "blog_generation": True,
            "seo_optimization": True,
            "wordpress_publish": True,
            "ghost_publish": True,
            "image_generation": True,
        },
    }


# ─── Dev Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    logger.info(
        f"\n"
        f"  ╔═══════════════════════════════════════════════════╗\n"
        f"  ║   🤖  AI Blog Automation v{settings.APP_VERSION}  🚀        ║\n"
        f"  ╠═══════════════════════════════════════════════════╣\n"
        f"  ║  Dashboard : http://{settings.HOST}:{settings.PORT}              ║\n"
        f"  ║  API Docs  : http://{settings.HOST}:{settings.PORT}/docs         ║\n"
        f"  ╚═══════════════════════════════════════════════════╝"
    )

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )