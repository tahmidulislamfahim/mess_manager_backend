from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models import MessMonth, DailyMeal, Expense, Deposit, User

# Local Timezone for Bangladesh (UTC+6)
LOCAL_TZ = timezone(timedelta(hours=6))

def get_current_local_now() -> datetime:
    return datetime.now(LOCAL_TZ)

def auto_clean_previous_months(db: Session, current_year: int, current_month: int):
    """
    Automatically purges all meal logs, deposit records, expense records, and mess month entries
    for any month prior to (current_year, current_month).
    Roommate User accounts remain intact.
    """
    old_months = db.query(MessMonth).filter(
        (MessMonth.year < current_year) | 
        ((MessMonth.year == current_year) & (MessMonth.month < current_month))
    ).all()

    if not old_months:
        return

    old_month_ids = [m.id for m in old_months]

    db.query(DailyMeal).filter(DailyMeal.month_id.in_(old_month_ids)).delete(synchronize_session=False)
    db.query(Expense).filter(Expense.month_id.in_(old_month_ids)).delete(synchronize_session=False)
    db.query(Deposit).filter(Deposit.month_id.in_(old_month_ids)).delete(synchronize_session=False)
    db.query(MessMonth).filter(MessMonth.id.in_(old_month_ids)).delete(synchronize_session=False)

    db.commit()

def get_or_create_mess_month(db: Session, year: int, month: int, fallback_user_id: int = 1) -> MessMonth:
    """
    Triggers automatic cleanup of older months, then returns or creates the MessMonth for (year, month).
    """
    now = get_current_local_now()
    # Auto-clean any months prior to the current real-time calendar month
    auto_clean_previous_months(db, now.year, now.month)

    mess_month = db.query(MessMonth).filter(
        MessMonth.year == year,
        MessMonth.month == month
    ).first()

    if not mess_month:
        admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
        manager_id = admin.id if admin else fallback_user_id
        mess_month = MessMonth(
            year=year,
            month=month,
            manager_id=manager_id,
            is_closed=False
        )
        db.add(mess_month)
        db.commit()
        db.refresh(mess_month)

    return mess_month
