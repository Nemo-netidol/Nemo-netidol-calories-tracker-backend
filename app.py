import os
import urllib.parse
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Response, Request, Cookie
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Session, create_engine, select
from dotenv import load_dotenv
import certifi
from pydantic import BaseModel

from models import FoodItem, FoodItemCreate

# Load environment variables from the root directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Database connection details
DB_USERNAME = os.getenv("DB_USERNAME", "").strip("'").strip('"')
DB_PASSWORD = os.getenv("DB_PASSWORD", "").strip("'").strip('"')
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "4000")
DB_DATABASE = os.getenv("DB_DATABASE", "test")
APP_PASSWORD = os.getenv("PASSWORD", "792200").strip("'").strip('"')

# TiDB Connection String
encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
encoded_username = urllib.parse.quote_plus(DB_USERNAME)

database_url = f"mysql+pymysql://{encoded_username}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}"

engine = create_engine(
    database_url,
    connect_args={
        "ssl": {
            "ca": certifi.where(),
            "ssl_verify_identity": True
        }
    },
    pool_pre_ping=True
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="Calories Tracker API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://calories-tracker-ten.vercel.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Authentication Config
SESSION_COOKIE_NAME = "calories_tracker_session"

class LoginRequest(BaseModel):
    password: str

def verify_session(calories_tracker_session: Optional[str] = Cookie(None)):
    if calories_tracker_session != "authenticated":
        raise HTTPException(status_code=401, detail="Not authenticated")
    return calories_tracker_session

@app.post("/auth/login")
def auth_login(login_data: LoginRequest, response: Response):
    if login_data.password == APP_PASSWORD:
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value="authenticated",
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=86400 * 30
        )
        return {"ok": True, "message": "Login successful"}
    else:
        raise HTTPException(status_code=401, detail="Invalid password")

@app.get("/auth/check")
def auth_check(calories_tracker_session: Optional[str] = Cookie(None)):
    if calories_tracker_session == "authenticated":
        return {"authenticated": True}
    return {"authenticated": False}

@app.post("/auth/logout")
def auth_logout(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"ok": True}

@app.get("/")
def root():
    return {"message": "Calories Tracker Backend is running!"}

@app.get("/foods", response_model=List[FoodItem])
def get_foods(
    session: Session = Depends(get_session), 
    _auth: str = Depends(verify_session)
):
    foods = session.exec(select(FoodItem)).all()
    return foods

@app.post("/foods", response_model=FoodItem)
def add_food(
    item_create: FoodItemCreate, 
    session: Session = Depends(get_session), 
    _auth: str = Depends(verify_session)
):
    data = item_create.model_dump(exclude_unset=True)
    db_item = FoodItem(**data)
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item

@app.delete("/foods/{food_id}")
def delete_food(
    food_id: str, 
    session: Session = Depends(get_session), 
    _auth: str = Depends(verify_session)
):
    food = session.get(FoodItem, food_id)
    if not food:
        raise HTTPException(status_code=404, detail="Food not found")
    session.delete(food)
    session.commit()
    return {"ok": True}
