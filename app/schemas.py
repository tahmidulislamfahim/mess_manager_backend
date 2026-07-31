from datetime import date as DateType
from typing import List, Optional
from pydantic import BaseModel, EmailStr, ConfigDict

# User Schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: str = "MEMBER"

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None

# Auth Schemas
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

# Month Schemas
class AssignManagerRequest(BaseModel):
    user_id: int
    year: Optional[int] = None
    month: Optional[int] = None

class MessMonthOut(BaseModel):
    id: int
    year: int
    month: int
    manager_id: int
    manager_name: str
    is_closed: bool

    model_config = ConfigDict(from_attributes=True)

# Meal Schemas
class DailyMealItem(BaseModel):
    user_id: int
    lunch_count: int = 1
    dinner_count: int = 1

class DailyMealBatchRequest(BaseModel):
    date: DateType
    meals: List[DailyMealItem]

class DailyMealOut(BaseModel):
    id: int
    month_id: int
    user_id: int
    user_name: str
    date: DateType
    lunch_count: int
    dinner_count: int

    model_config = ConfigDict(from_attributes=True)

# Expense Schemas
class ExpenseCreate(BaseModel):
    amount: float
    description: str
    date: Optional[DateType] = None

class ExpenseUpdate(BaseModel):
    amount: Optional[float] = None
    description: Optional[str] = None
    date: Optional[DateType] = None

class ExpenseOut(BaseModel):
    id: int
    month_id: int
    amount: float
    description: str
    date: DateType

    model_config = ConfigDict(from_attributes=True)

# Deposit Schemas
class DepositCreate(BaseModel):
    user_id: int
    amount: float
    date: Optional[DateType] = None

class DepositUpdate(BaseModel):
    user_id: Optional[int] = None
    amount: Optional[float] = None
    date: Optional[DateType] = None

class DepositOut(BaseModel):
    id: int
    month_id: int
    user_id: int
    user_name: str
    amount: float
    date: DateType

    model_config = ConfigDict(from_attributes=True)

# Summary Schemas
class MemberSummary(BaseModel):
    user_id: int
    name: str
    total_meals: int
    total_cost: float
    total_deposits: float
    net_balance: float

class MonthSummaryResponse(BaseModel):
    year: int
    month: int
    manager_name: str
    total_expenses: float
    total_meals: int
    meal_rate: float
    member_summaries: List[MemberSummary]
