from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import MessMonth, User, DailyMeal, Expense, Deposit
from app.schemas import MonthSummaryResponse, MemberSummary
from app.security import get_current_user

router = APIRouter(prefix="/api/v1/summary", tags=["Summary"])

@router.get("", response_model=MonthSummaryResponse)
def get_month_summary(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.now()
    target_year = year or now.year
    target_month = month or now.month

    mess_month = db.query(MessMonth).filter(
        MessMonth.year == target_year,
        MessMonth.month == target_month
    ).first()

    if not mess_month:
        admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
        manager_id = admin.id if admin else current_user.id
        mess_month = MessMonth(
            year=target_year,
            month=target_month,
            manager_id=manager_id,
            is_closed=False
        )
        db.add(mess_month)
        db.commit()
        db.refresh(mess_month)

    manager = db.query(User).filter(User.id == mess_month.manager_id).first()
    manager_name = manager.name if manager else "N/A"

    # 1. Total Expense = SUM(Expenses in Month)
    total_expenses_res = db.query(func.sum(Expense.amount)).filter(Expense.month_id == mess_month.id).scalar()
    total_expenses = float(total_expenses_res or 0.0)

    # All active users
    active_users = db.query(User).filter(User.is_active == True).all()

    # Pre-calculate meals per user
    user_meals_map = {}
    total_meals_sum = 0
    daily_meals = db.query(DailyMeal).filter(DailyMeal.month_id == mess_month.id).all()
    for dm in daily_meals:
        user_id = dm.user_id
        consumed = (dm.lunch_count or 0) + (dm.dinner_count or 0)
        user_meals_map[user_id] = user_meals_map.get(user_id, 0) + consumed
        total_meals_sum += consumed

    # 2. Total Meals
    total_meals = total_meals_sum

    # 3. Meal Rate = Total Expense / Total Meals
    meal_rate = round(total_expenses / total_meals, 2) if total_meals > 0 else 0.0

    # Pre-calculate deposits per user
    user_deposits_map = {}
    deposits = db.query(Deposit).filter(Deposit.month_id == mess_month.id).all()
    for dep in deposits:
        user_deposits_map[dep.user_id] = user_deposits_map.get(dep.user_id, 0.0) + float(dep.amount or 0.0)

    member_summaries = []
    for user in active_users:
        u_meals = user_meals_map.get(user.id, 0)
        # 4. Member Total Cost = Member Consumed Meals * Meal Rate
        u_cost = round(u_meals * meal_rate, 2)
        u_deposits = round(user_deposits_map.get(user.id, 0.0), 2)
        # 5. Member Net Balance = Member Total Deposits - Member Total Cost
        u_balance = round(u_deposits - u_cost, 2)

        member_summaries.append(MemberSummary(
            user_id=user.id,
            name=user.name,
            total_meals=u_meals,
            total_cost=u_cost,
            total_deposits=u_deposits,
            net_balance=u_balance
        ))

    return MonthSummaryResponse(
        year=target_year,
        month=target_month,
        manager_name=manager_name,
        total_expenses=total_expenses,
        total_meals=total_meals,
        meal_rate=meal_rate,
        member_summaries=member_summaries
    )
