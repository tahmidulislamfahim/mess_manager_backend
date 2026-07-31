from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import MessMonth, DailyMeal, User
from app.schemas import DailyMealBatchRequest, DailyMealOut
from app.security import get_current_user, require_roles

router = APIRouter(prefix="/api/v1/meals", tags=["Meals"])

def get_or_create_mess_month(db: Session, target_date: date) -> MessMonth:
    mess_month = db.query(MessMonth).filter(
        MessMonth.year == target_date.year,
        MessMonth.month == target_date.month
    ).first()
    if not mess_month:
        admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
        manager_id = admin.id if admin else 1
        mess_month = MessMonth(
            year=target_date.year,
            month=target_date.month,
            manager_id=manager_id,
            is_closed=False
        )
        db.add(mess_month)
        db.commit()
        db.refresh(mess_month)
    return mess_month

@router.post("/batch", response_model=List[DailyMealOut])
def batch_update_meals(
    req: DailyMealBatchRequest,
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles(["SUPER_ADMIN", "MANAGER"]))
):
    mess_month = get_or_create_mess_month(db, req.date)
    if mess_month.is_closed:
        raise HTTPException(status_code=400, detail="Target mess month is closed")

    results = []
    for item in req.meals:
        user = db.query(User).filter(User.id == item.user_id, User.is_active == True).first()
        if not user:
            continue

        daily_meal = db.query(DailyMeal).filter(
            DailyMeal.month_id == mess_month.id,
            DailyMeal.user_id == item.user_id,
            DailyMeal.date == req.date
        ).first()

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

        db.commit()
        db.refresh(daily_meal)

        results.append(DailyMealOut(
            id=daily_meal.id,
            month_id=daily_meal.month_id,
            user_id=daily_meal.user_id,
            user_name=user.name,
            date=daily_meal.date,
            lunch_count=daily_meal.lunch_count,
            dinner_count=daily_meal.dinner_count
        ))

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

    user_map = {u.id: u.name for u in db.query(User).all()}

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
