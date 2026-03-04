import os
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Grab PostgreSQL connection string from Docker env if present
DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:securepassword123@localhost:5432/infiniteseo")

async_engine = create_async_engine(DB_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    password_salt = Column(String(200), nullable=False)
    token = Column(String(200), nullable=True)
    credits = Column(Integer, default=5)
    plan = Column(String(20), default='free')
    is_admin = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(Float)

    
class Website(Base):
    __tablename__ = "websites"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    domain = Column(String(200), nullable=False)
    cms_type = Column(String(50), nullable=False)
    api_url = Column(String(200), nullable=False)
    api_key = Column(String(200))
    api_secret = Column(String(200))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    slug = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    meta_description = Column(String(300))
    keywords = Column(Text)
    focus_keyphrase = Column(String(150))
    seo_title = Column(String(200))
    category = Column(String(100))
    seo_score = Column(Integer, default=0)
    image_url = Column(String(500))
    website_id = Column(Integer, ForeignKey("websites.id"))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    published = Column(Integer, default=0)
    published_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

class UsedKeyphrase(Base):
    __tablename__ = "used_keyphrases"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    keyphrase = Column(String(200), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
