import uvicorn
from fastapi import FastAPI

from app.routes import accounts

app = FastAPI()

app.include_router(accounts, prefix="/accounts", tags=["accounts"])

