import os
import urllib.parse
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Response, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Session, create_engine, select
from dotenv import load_dotenv
import certifi
from pydantic import BaseModel
import secrets

from models import FoodItem, FoodItemCreate, Users

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
        "https://calories-tracker-ten.vercel.app",
    ],
    # Vite picks the next free port (3001, 3002, ...) whenever 3000 is taken, so match
    # any localhost port. Also allow any private-network IP (phone hotspot / LAN testing,
    # e.g. http://172.20.10.4:3000) and VS Code/Cursor port-forwarding (Dev Tunnels), whose
    # hostname carries a random tunnel id that changes each session, e.g.
    # https://abcd1234-3000.usw2.devtunnels.ms.
    allow_origin_regex=(
        r"http://(localhost|127\.0\.0\.1"
        r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
        r"|192\.168\.\d{1,3}\.\d{1,3}):\d+"
        r"|https://.*\.devtunnels\.ms"
    ),
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Authentication Config
# Since cross-site cookies are blocked by Safari ITP, we will use a Bearer token.
# For simplicity, we use the APP_PASSWORD as the token since this is a personal tracker.
# In a real app, this would be a signed JWT or a random session token.
AUTH_TOKEN = APP_PASSWORD 

class LoginRequest(BaseModel):
    password: str

def verify_session(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Bearer <token> format
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer" or token != AUTH_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    return token

@app.post("/auth/login")
def auth_login(login_data: LoginRequest):
    if login_data.password == APP_PASSWORD:
        # Instead of a cookie, we return a token for the client to store in localStorage
        return {"ok": True, "token": AUTH_TOKEN, "message": "Login successful"}
    else:
        raise HTTPException(status_code=401, detail="Invalid password")

@app.get("/auth/check")
def auth_check(authorization: Optional[str] = Header(None)):
    try:
        verify_session(authorization)
        return {"authenticated": True}
    except:
        return {"authenticated": False}

@app.post("/auth/logout")
def auth_logout():
    # Logout is handled on the client side by removing the token
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
    food_id: int, 
    session: Session = Depends(get_session), 
    _auth: str = Depends(verify_session)
):
    food = session.get(FoodItem, food_id)
    if not food:
        raise HTTPException(status_code=404, detail="Food not found")
    session.delete(food)
    session.commit()
    return {"ok": True}

class FoodItemUpdate(BaseModel):
    name: Optional[str] = None
    calories: Optional[int] = None
    protein: Optional[int] = None
    carbs: Optional[int] = None
    fat: Optional[int] = None
    category: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None

@app.patch("/foods/{food_id}", response_model=FoodItem)
def update_food(
    food_id: int,
    food_update: FoodItemUpdate,
    session: Session = Depends(get_session),
    _auth: str = Depends(verify_session)
):
    db_food = session.get(FoodItem, food_id)
    if not db_food:
        raise HTTPException(status_code=404, detail="Food not found")
    
    update_data = food_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_food, key, value)
    
    session.add(db_food)
    session.commit()
    session.refresh(db_food)
    return db_food


@app.get("/user")
def get_user(
    session: Session = Depends(get_session),
    _auth: str = Depends(verify_session)
):
    user = session.exec(select(Users)).first()

    return user

class UserUpdateTargets(BaseModel):
    target_calories: Optional[float] = None
    target_protein: Optional[float] = None
    target_carbs: Optional[float] = None
    target_fat: Optional[float] = None

@app.patch("/user/targets")
def update_user_targets(
    targets: UserUpdateTargets,
    session: Session = Depends(get_session),
    _auth: str = Depends(verify_session)
):
    user = session.exec(select(Users)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if targets.target_calories is not None:
        user.target_calories = targets.target_calories
    if targets.target_protein is not None:
        user.target_protein = targets.target_protein
    if targets.target_carbs is not None:
        user.target_carbs = targets.target_carbs
    if targets.target_fat is not None:
        user.target_fat = targets.target_fat

    session.add(user)
    session.commit()
    session.refresh(user)
    return user
