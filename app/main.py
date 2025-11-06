from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import os
import requests

# Load environment variables
load_dotenv()

# Import routes
from app.routes import generate_blog, publish_post, websites, image_gen, seo_score

# Initialize FastAPI app
app = FastAPI(
    title="AI Blog Automation",
    description="Free local AI blog automation tool powered by Groq API with clean URL support",
    version="1.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="ui/static"), name="static")
templates = Jinja2Templates(directory="ui/templates")

# Include routers
app.include_router(generate_blog.router, prefix="/api", tags=["Generate"])
app.include_router(publish_post.router, prefix="/api", tags=["Publish"])
app.include_router(websites.router, prefix="/api", tags=["Websites"])
app.include_router(image_gen.router, prefix="/api", tags=["Images"])
app.include_router(seo_score.router, prefix="/api", tags=["SEO"])

# WordPress configuration check endpoint
class WordPressCheck(BaseModel):
    api_url: str
    username: str
    password: str

@app.post("/api/check-wordpress")
async def check_wordpress_config(config: WordPressCheck):
    """Check WordPress configuration and permalink structure"""
    try:
        auth = (config.username, config.password)
        
        # Test connection
        test_url = f"{config.api_url.rstrip('/')}/wp-json/wp/v2/posts?per_page=1"
        response = requests.get(test_url, auth=auth, timeout=10)
        
        if response.status_code == 401:
            return {
                "success": False,
                "error": "Authentication failed. Check username and password."
            }
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Connection failed with status {response.status_code}"
            }
        
        # Check permalink structure
        posts = response.json()
        permalink_type = "unknown"
        
        if posts:
            sample_url = posts[0].get('link', '')
            if '?p=' in sample_url:
                permalink_type = "default"
            else:
                permalink_type = "pretty"
        
        return {
            "success": True,
            "permalink_type": permalink_type,
            "message": "WordPress connection successful!",
            "warning": "Please set permalinks to 'Post name' in WordPress settings" if permalink_type == "default" else None
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e)
        }

# Frontend routes
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/post/{post_id}", response_class=HTMLResponse)
async def post_preview(request: Request, post_id: int):
    """Post preview page"""
    return templates.TemplateResponse("post_preview.html", {
        "request": request,
        "post_id": post_id
    })

@app.get("/health")
async def health_check():
    """API health check"""
    return {
        "status": "healthy",
        "groq_api_configured": bool(os.getenv("GROQ_API_KEY")),
        "pexels_api_configured": bool(os.getenv("PEXELS_API_KEY")),
        "version": "1.1.0",
        "features": {
            "clean_urls": True,
            "wordpress_support": True,
            "ghost_support": True,
            "seo_optimization": True
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    # Initialize database
    from app.database import Database
    db = Database()
    
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    
    print(f"""
    ╔════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║        🤖 AI Blog Automation Tool v1.1.0 Started 🚀        ║
    ║                                                            ║
    ║  Dashboard: http://{host}:{port}                           ║
    ║  API Docs:  http://{host}:{port}/docs                      ║
    ║                                                            ║
    ║  Features:                                                 ║
    ║  ✅ Clean URL support for WordPress                        ║
    ║  ✅ Automatic slug generation                              ║
    ║  ✅ Category and tag management                            ║
    ║  ✅ Featured image upload                                  ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=os.getenv("DEBUG", "True") == "True"
    )