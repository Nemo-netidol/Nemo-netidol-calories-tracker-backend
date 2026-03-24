from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class FoodItemBase(SQLModel):
    name: str = Field(index=True)
    amount: int
    calories: int
    protein: int
    category: str

class FoodItemCreate(FoodItemBase): #DTO
    pass

class FoodItem(FoodItemBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    time: str = Field(default_factory=lambda: datetime.now().strftime("%I:%M %p"))
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
