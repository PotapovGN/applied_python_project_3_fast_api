from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database.models import User
from app.dependencies import get_db
from passlib.hash import bcrypt

router = APIRouter()

@router.post("/users/register")
def register_user(email: str, password: str, db: Session = Depends(get_db)):
    exists = db.query(User).filter_by(email=email).first()
    if exists:
        raise HTTPException(400, "User already exists")
    user = User(email=email, password_hash=bcrypt.hash(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User registered", "user_id": user.id}

@router.post("/users/login")
def login_user(email: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=email).first()
    if not user or not bcrypt.verify(password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return {"message": "Logged in", "user_id": user.id}
