from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import MessMonth, Expense, User
from app.schemas import ExpenseCreate, ExpenseOut, ExpenseUpdate
from app.security import get_current_user, require_roles

from app.month_utils import get_or_create_mess_month, auto_clean_previous_months, get_current_local_now

from app.notification_service import create_and_broadcast_notification

router = APIRouter(prefix="/api/v1/expenses", tags=["Expenses"])

@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(
    exp_in: ExpenseCreate,
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles(["SUPER_ADMIN", "MANAGER"]))
):
    exp_date = exp_in.date or get_current_local_now().date()
    mess_month = get_or_create_mess_month(db, exp_date.year, exp_date.month, fallback_user_id=manager.id)

    if mess_month.is_closed:
        raise HTTPException(status_code=400, detail="Target mess month is closed")

    new_exp = Expense(
        month_id=mess_month.id,
        amount=exp_in.amount,
        description=exp_in.description,
        date=exp_date
    )
    db.add(new_exp)
    db.commit()
    db.refresh(new_exp)

    create_and_broadcast_notification(
        db,
        title="Grocery Expense Logged",
        message=f"৳{new_exp.amount} for '{new_exp.description}' logged by {manager.name}",
        notification_type="EXPENSE"
    )

    return new_exp

@router.get("", response_model=List[ExpenseOut])
def list_expenses(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = get_current_local_now()
    auto_clean_previous_months(db, now.year, now.month)
    target_year = year or now.year
    target_month = month or now.month

    mess_month = db.query(MessMonth).filter(
        MessMonth.year == target_year,
        MessMonth.month == target_month
    ).first()

    if not mess_month:
        return []

    return db.query(Expense).filter(Expense.month_id == mess_month.id).order_by(Expense.date.desc()).all()

@router.put("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int,
    exp_in: ExpenseUpdate,
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles(["SUPER_ADMIN", "MANAGER"]))
):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    mess_month = db.query(MessMonth).filter(MessMonth.id == expense.month_id).first()
    if mess_month and mess_month.is_closed:
        raise HTTPException(status_code=400, detail="Target mess month is closed")

    if exp_in.amount is not None:
        expense.amount = exp_in.amount
    if exp_in.description is not None:
        expense.description = exp_in.description
    if exp_in.date is not None:
        new_date = exp_in.date
        new_month = db.query(MessMonth).filter(
            MessMonth.year == new_date.year,
            MessMonth.month == new_date.month
        ).first()
        if not new_month:
            admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
            manager_id = admin.id if admin else manager.id
            new_month = MessMonth(
                year=new_date.year,
                month=new_date.month,
                manager_id=manager_id,
                is_closed=False
            )
            db.add(new_month)
            db.commit()
            db.refresh(new_month)
        expense.month_id = new_month.id
        expense.date = new_date

    db.commit()
    db.refresh(expense)

    create_and_broadcast_notification(
        db,
        title="Grocery Expense Updated",
        message=f"Expense '{expense.description}' updated to ৳{expense.amount} by {manager.name}",
        notification_type="EXPENSE"
    )

    return expense

@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles(["SUPER_ADMIN", "MANAGER"]))
):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    mess_month = db.query(MessMonth).filter(MessMonth.id == expense.month_id).first()
    if mess_month and mess_month.is_closed:
        raise HTTPException(status_code=400, detail="Target mess month is closed")

    exp_desc = expense.description
    db.delete(expense)
    db.commit()

    create_and_broadcast_notification(
        db,
        title="Grocery Expense Deleted",
        message=f"Expense '{exp_desc}' was removed by {manager.name}",
        notification_type="EXPENSE"
    )

    return None
