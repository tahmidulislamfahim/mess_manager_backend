from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import MessMonth, DailyMeal, Expense, Deposit, User

# Local Timezone for Bangladesh (UTC+6)
LOCAL_TZ = timezone(timedelta(hours=6))

def get_current_local_now() -> datetime:
    return datetime.now(LOCAL_TZ)

def auto_clean_previous_months(db: Session, current_year: int, current_month: int):
    """
    Purges meal logs, deposit records, expense records, and mess month entries
    for any month prior to (current_year, current_month) ONLY after the 5-day grace period (now.day > 5).
    Roommate User accounts remain 100% intact.
    """
    now = get_current_local_now()
    # 5-day grace period protection: Only execute purge after day 5 of current month
    if now.day <= 5 and now.year == current_year and now.month == current_month:
        return

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

def _send_previous_month_end_summary_notifications(db: Session, prev_month_record: MessMonth):
    """
    Calculates final monthly calculations for prev_month_record and broadcasts
    individual detailed notification messages to all active roommate accounts.
    """
    from app.notification_service import create_and_broadcast_per_user_notifications
    
    # 1. Total Expense
    total_expenses_res = db.query(func.sum(Expense.amount)).filter(Expense.month_id == prev_month_record.id).scalar()
    total_expenses = float(total_expenses_res or 0.0)

    # 2. Total Meals
    daily_meals = db.query(DailyMeal).filter(DailyMeal.month_id == prev_month_record.id).all()
    user_meals_map = {}
    total_meals_sum = 0
    for dm in daily_meals:
        consumed = (dm.lunch_count or 0) + (dm.dinner_count or 0)
        user_meals_map[dm.user_id] = user_meals_map.get(dm.user_id, 0) + consumed
        total_meals_sum += consumed

    meal_rate = round(total_expenses / total_meals_sum, 2) if total_meals_sum > 0 else 0.0

    # 3. Total Deposits per User
    deposits = db.query(Deposit).filter(Deposit.month_id == prev_month_record.id).all()
    user_deposits_map = {}
    for dep in deposits:
        user_deposits_map[dep.user_id] = user_deposits_map.get(dep.user_id, 0.0) + float(dep.amount or 0.0)

    active_users = db.query(User).filter(User.is_active == True, User.role != "SUPER_ADMIN").all()

    month_names = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    prev_month_str = month_names[prev_month_record.month] if 1 <= prev_month_record.month <= 12 else str(prev_month_record.month)

    user_notifications = []
    for u in active_users:
        u_meals = user_meals_map.get(u.id, 0)
        u_cost = round(u_meals * meal_rate, 2)
        u_deposits = round(user_deposits_map.get(u.id, 0.0), 2)
        u_balance = round(u_deposits - u_cost, 2)

        balance_str = f"+{u_balance:.2f} Tk" if u_balance >= 0 else f"{u_balance:.2f} Tk"

        title = f"[Month Summary] {prev_month_str} Ended - Final Calculation"
        message = (
            f"Final calculation for {prev_month_str} {prev_month_record.year}:\n"
            f"- Meal Rate: {meal_rate:.2f} Tk\n"
            f"- Your Consumed Meals: {u_meals}\n"
            f"- Your Total Cost: {u_cost:.2f} Tk\n"
            f"- Your Total Deposits: {u_deposits:.2f} Tk\n"
            f"- Net Balance: {balance_str}\n\n"
            f"IMPORTANT: Please take a screenshot of this notification! Data will be auto-cleaned in 5 days."
        )
        user_notifications.append((u.id, title, message, "SYSTEM"))

    create_and_broadcast_per_user_notifications(db, user_notifications)

def get_or_create_mess_month(db: Session, year: int, month: int, fallback_user_id: int = 1) -> MessMonth:
    """
    Returns existing MessMonth (1 single fast DB lookup).
    If a new MessMonth is initialized, triggers month-end summary notifications and grace period cleanup.
    """
    # 1. Fast direct query check first
    mess_month = db.query(MessMonth).filter(
        MessMonth.year == year,
        MessMonth.month == month
    ).first()

    if mess_month:
        return mess_month

    # 2. If month record does NOT exist yet, initialize it
    now = get_current_local_now()

    # Check for previous month to send month-end notification report
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1

    prev_record = db.query(MessMonth).filter(
        MessMonth.year == prev_year,
        MessMonth.month == prev_month
    ).first()

    if prev_record:
        try:
            _send_previous_month_end_summary_notifications(db, prev_record)
        except Exception as e:
            print(f"[Month Transition Warning] Could not send month end notification summary: {e}")

    # Auto-clean any months prior to current real-time month (respecting 5-day grace period)
    auto_clean_previous_months(db, now.year, now.month)

    admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
    manager_id = admin.id if admin else fallback_user_id
    new_mess_month = MessMonth(
        year=year,
        month=month,
        manager_id=manager_id,
        is_closed=False
    )
    db.add(new_mess_month)
    db.commit()
    db.refresh(new_mess_month)

    return new_mess_month
