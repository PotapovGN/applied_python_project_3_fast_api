from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse
from datetime import datetime
from app.database.models import Link
from app.dependencies import get_db
from app.utils.shortener import generate_short_code
from app.services.cache import redis_client
from datetime import timedelta, datetime

router = APIRouter()

@router.post("/links/shorten")
def create_link(request: Request, original_url: str, custom_alias: str = None, expires_at: str = None, user_id: int = None, db: Session = Depends(get_db)):
    short_code = custom_alias or generate_short_code()
    exists = db.query(Link).filter_by(short_code=short_code).first()
    if exists:
        raise HTTPException(400, "Alias already exists")
    
    expires = datetime.fromisoformat(expires_at) if expires_at else None
    link = Link(original_url=original_url, short_code=short_code, expires_at=expires, user_id=user_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    
    base_url = str(request.base_url)
    return {"short_url": f"{base_url}{short_code}"}

@router.get("/{short_code}")
def redirect_link(short_code: str, db: Session = Depends(get_db)):
    cached = redis_client.get(short_code)
    if cached:
        return RedirectResponse(cached)
    
    link = db.query(Link).filter_by(short_code=short_code).first()
    if not link:
        raise HTTPException(404)
    if link.expires_at and link.expires_at < datetime.utcnow():
        raise HTTPException(410)
    
    link.clicks += 1
    link.last_used_at = datetime.utcnow()
    db.commit()
    
    # redis_client.set(short_code, link.original_url, ex=3600)
    return RedirectResponse(link.original_url)

@router.get("/links/{short_code}/stats")
def link_stats(short_code: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter_by(short_code=short_code).first()
    if not link:
        raise HTTPException(404)
    return {
        "original_url": link.original_url,
        "created_at": link.created_at,
        "clicks": link.clicks,
        "last_used_at": link.last_used_at
    }

@router.put("/links/{short_code}")
def update_link(short_code: str, original_url: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter_by(short_code=short_code).first()
    if not link:
        raise HTTPException(404)
    link.original_url = original_url
    db.commit()
    redis_client.delete(short_code)
    return {"message": "Link updated"}

@router.delete("/links/{short_code}")
def delete_link(short_code: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter_by(short_code=short_code).first()
    if not link:
        raise HTTPException(404)
    db.delete(link)
    db.commit()
    redis_client.delete(short_code)
    return {"message": "Link deleted"}

@router.get("/links/search")
def search_links(original_url: str, db: Session = Depends(get_db)):
    links = db.query(Link).filter_by(original_url=original_url).all()
    return [{"short_code": l.short_code, "original_url": l.original_url} for l in links]

@router.delete("/links/cleanup")
def cleanup_links(days: int = 30, db: Session = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(days=days)
    old_links = db.query(Link).filter(Link.last_used_at < cutoff).all()
    count = len(old_links)
    for l in old_links:
        db.delete(l)
        redis_client.delete(l.short_code)
    db.commit()
    return {"deleted_links": count}

@router.get("/links/expired")
def expired_links(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    expired = db.query(Link).filter(Link.expires_at != None, Link.expires_at < now).all()
    return [{"short_code": l.short_code, "original_url": l.original_url, "expires_at": l.expires_at} for l in expired]
