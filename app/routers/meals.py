from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import MessMonth, DailyMeal, User
from app.schemas import DailyMealBatchRequest, DailyMealOut
from app.security import get_current_user, require_roles

from app.month_utils import get_or_create_mess_month as get_or_create_month

from app.notification_service import create_and_broadcast_notification

router = APIRouter(prefix="/api/v1/meals", tags=["Meals"])

def get_or_create_mess_month(db: Session, target_date: date) -> MessMonth:
    return get_or_create_month(db, target_date.year, target_date.month)

@router.post("/batch", response_model=List[DailyMealOut])
def batch_update_meals(
    req: DailyMealBatchRequest,
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles(["SUPER_ADMIN", "MANAGER"]))
):
    mess_month = get_or_create_mess_month(db, req.date)
    if mess_month.is_closed:
        raise HTTPException(status_code=400, detail="Target mess month is closed")

    if not req.meals:
        return []

    # 1. Fetch all requested active users in 1 single query
    requested_user_ids = list({item.user_id for item in req.meals})
    active_users = db.query(User).filter(User.id.in_(requested_user_ids), User.is_active == True).all()
    user_map = {u.id: u for u in active_users}

    # 2. Fetch all existing meals for this date and month in 1 single query
    existing_meals = db.query(DailyMeal).filter(
        DailyMeal.month_id == mess_month.id,
        DailyMeal.date == req.date,
        DailyMeal.user_id.in_(user_map.keys())
    ).all()
    meal_map = {m.user_id: m for m in existing_meals}

    # 3. Update or create in memory
    saved_items = []
    for item in req.meals:
        user = user_map.get(item.user_id)
        if not user:
            continue

        daily_meal = meal_map.get(item.user_id)
        if daily_meal:
            daily_meal.lunch_count = max(0, item.lunch_count)
            daily_meal.dinner_count = max(0, item.dinner_count)
        else:
            daily_meal = DailyMeal(
                month_id=mess_month.id,
                user_id=item.user_id,
                date=req.date,
                lunch_count=max(0, item.lunch_count),
                dinner_count=max(0, item.dinner_count)
            )
            db.add(daily_meal)
            meal_map[item.user_id] = daily_meal

        saved_items.append((daily_meal, user.name))

    # 4. Single commit for all changes
    db.commit()

    # 5. Build output results directly from in-memory objects
    results = [
        DailyMealOut(
            id=dm.id,
            month_id=dm.month_id,
            user_id=dm.user_id,
            user_name=uname,
            date=dm.date,
            lunch_count=dm.lunch_count,
            dinner_count=dm.dinner_count
        ) for dm, uname in saved_items
    ]

    create_and_broadcast_notification(
        db,
        title="Daily Meals Logged",
        message=f"Daily meals for {req.date} updated by {manager.name}",
        notification_type="MEALS"
    )

    return results

@router.get("", response_model=List[DailyMealOut])
def list_meals(
    target_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query_date = target_date or datetime.now().date()
    mess_month = get_or_create_mess_month(db, query_date)

    meals = db.query(DailyMeal).filter(
        DailyMeal.month_id == mess_month.id,
        DailyMeal.date == query_date
    ).all()

    if not meals:
        return []

    meal_user_ids = list({m.user_id for m in meals})
    users = db.query(User.id, User.name).filter(User.id.in_(meal_user_ids)).all()
    user_map = {u.id: u.name for u in users}

    return [
        DailyMealOut(
            id=m.id,
            month_id=m.month_id,
            user_id=m.user_id,
            user_name=user_map.get(m.user_id, "Unknown"),
            date=m.date,
            lunch_count=m.lunch_count,
            dinner_count=m.dinner_count
        ) for m in meals
    ]
