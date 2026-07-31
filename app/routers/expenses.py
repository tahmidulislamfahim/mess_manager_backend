from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import MessMonth, Expense, User
from app.schemas import ExpenseCreate, ExpenseOut
from app.security import get_current_user, require_roles

router = APIRouter(prefix="/api/v1/expenses", tags=["Expenses"])

@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(
    exp_in: ExpenseCreate,
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles(["SUPER_ADMIN", "MANAGER"]))
):
    exp_date = exp_in.date or datetime.now().date()
    mess_month = db.query(MessMonth).filter(
        MessMonth.year == exp_date.year,
        MessMonth.month == exp_date.month
    ).first()

    if not mess_month:
        admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
        manager_id = admin.id if admin else manager.id
        mess_month = MessMonth(
            year=exp_date.year,
            month=exp_date.month,
            manager_id=manager_id,
            is_closed=False
        )
        db.add(mess_month)
        db.commit()
        db.refresh(mess_month)

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

    return new_exp

@router.get("", response_model=List[ExpenseOut])
def list_expenses(
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
        return []

    return db.query(Expense).filter(Expense.month_id == mess_month.id).order_by(Expense.date.desc()).all()
