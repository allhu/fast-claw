from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timedelta

class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, unique=True, index=True, nullable=True) # New strict unique domain column
    url = Column(String, index=True, nullable=False) # Full URL where it was found
    source = Column(String, default="unknown")  # e.g., extension, google, ads
    status = Column(String, default="pending")  # pending, scraping, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Flywheel additions
    is_parsed_for_keywords = Column(Boolean, default=False)
    
    # Tracking
    source_channel = Column(String, default="unknown") # e.g., yahoo, fb_ads, tiktok_ads, youtube, trustpilot, reddit

    contacts = relationship("Contact", back_populates="store", cascade="all, delete")

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    instagram = Column(String, nullable=True)
    facebook = Column(String, nullable=True)
    whatsapp = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    store = relationship("Store", back_populates="contacts")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String, nullable=False) # 'scrape_contacts', 'google_search', 'fb_ads', 'tiktok_ads', 'all_channels'
    status = Column(String, default="running") # 'running', 'completed', 'failed'
    parameters = Column(String, nullable=True) # JSON string of parameters like keywords
    result_summary = Column(String, nullable=True)
    
    # New fields for real-time tracking
    progress_text = Column(String, nullable=True) # e.g. "Processing FB Ads for 'jewelry' (Page 1/3)"
    current_keyword = Column(String, nullable=True)
    items_found = Column(Integer, default=0)
    items_saved = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    schedule_interval = Column(String, default="weekly") # 'daily', 'weekly', 'monthly'
    
    # New tracking fields
    current_status = Column(String, default="idle") # 'idle', 'running', 'error'
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True) # Explicitly stored next run time
    language = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Tracking
    source_channel = Column(String, default="unknown") # e.g., yahoo, fb_ads, tiktok_ads, youtube, trustpilot, reddit
    
    # Flywheel additions
    source = Column(String, default="manual") # manual, ai_expanded, scraped_from_store
    parent_id = Column(Integer, ForeignKey("keywords.id"), nullable=True)

class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String, index=True)
    keyword = Column(String)
    keywords_count = Column(Integer, default=1)
    links_found = Column(Integer, default=0)
    stores_saved = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
