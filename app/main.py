from fastapi import FastAPI
from app.routers import links, users
from app.database.db import Base, engine

app = FastAPI(title="URL Shortener API")

Base.metadata.create_all(bind=engine)
app.include_router(links.router)
app.include_router(users.router)

@app.get("/")
def root():
    return {"status": "working"}
