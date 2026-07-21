from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class FoodItemBase(SQLModel):
    name: str = Field(index=True)
    calories: int
    protein: float
    carbs: Optional[int] = None
    fat: Optional[int] = None
    category: str
    date: Optional[str] = None
    time: Optional[str] = None

class FoodItemCreate(FoodItemBase): #DTO
    pass

class FoodItem(FoodItemBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # Ensure date and time are provided or generated locally
    time: str = Field(default_factory=lambda: datetime.now().strftime("%I:%M %p"))
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))


class Users(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    weight: float
    target_calories: float
    target_protein: float
    target_carbs: float = 0
    target_fat: float = 0
    tdee: float
    bmr: float


