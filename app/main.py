import uvicorn
from fastapi import FastAPI

from app.routes import accounts, profiles, movies

app = FastAPI()

app.include_router(accounts, prefix="/accounts", tags=["accounts"])
app.include_router(profiles, prefix=f"/profiles", tags=["profiles"])
app.include_router(movies, prefix="/movies", tags=["movies"])
