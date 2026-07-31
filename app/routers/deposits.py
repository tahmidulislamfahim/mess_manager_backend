from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import MessMonth, Deposit, User
from app.schemas import DepositCreate, DepositOut, DepositUpdate
from app.security import get_current_user, require_roles

from app.month_utils import get_or_create_mess_month, auto_clean_previous_months, get_current_local_now

router = APIRouter(prefix="/api/v1/deposits", tags=["Deposits"])

@router.post("", response_model=DepositOut, status_code=status.HTTP_201_CREATED)
def create_deposit(
    dep_in: DepositCreate,
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles(["SUPER_ADMIN", "MANAGER"]))
):
    dep_date = dep_in.date or get_current_local_now().date()
    target_user = db.query(User).filter(User.id == dep_in.user_id, User.is_active == True).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    mess_month = get_or_create_mess_month(db, dep_date.year, dep_date.month, fallback_user_id=manager.id)

    if mess_month.is_closed:
        raise HTTPException(status_code=400, detail="Target mess month is closed")

    new_dep = Deposit(
        month_id=mess_month.id,
        user_id=dep_in.user_id,
        amount=dep_in.amount,
        date=dep_date
    )
    db.add(new_dep)
    db.commit()
    db.refresh(new_dep)

    return DepositOut(
        id=new_dep.id,
        month_id=new_dep.month_id,
        user_id=new_dep.user_id,
        user_name=target_user.name,
        amount=new_dep.amount,
        date=new_dep.date
    )

@router.get("", response_model=List[DepositOut])
def list_deposits(
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

    deposits = db.query(Deposit).filter(Deposit.month_id == mess_month.id).order_by(Deposit.date.desc()).all()
    user_map = {u.id: u.name for u in db.query(User).all()}

    return [
        DepositOut(
            id=d.id,
            month_id=d.month_id,
            user_id=d.user_id,
            user_name=user_map.get(d.user_id, "Unknown"),
            amount=d.amount,
            date=d.date
        ) for d in deposits
    ]

@router.put("/{deposit_id}", response_model=DepositOut)
def update_deposit(
    deposit_id: int,
    dep_in: DepositUpdate,
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles(["SUPER_ADMIN", "MANAGER"]))
):
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    mess_month = db.query(MessMonth).filter(MessMonth.id == deposit.month_id).first()
    if mess_month and mess_month.is_closed:
        raise HTTPException(status_code=400, detail="Target mess month is closed")

    if dep_in.user_id is not None:
        target_user = db.query(User).filter(User.id == dep_in.user_id, User.is_active == True).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found")
        deposit.user_id = dep_in.user_id

    if dep_in.amount is not None:
        deposit.amount = dep_in.amount

    if dep_in.date is not None:
        new_date = dep_in.date
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
        deposit.month_id = new_month.id
        deposit.date = new_date

    db.commit()
    db.refresh(deposit)

    target_user = db.query(User).filter(User.id == deposit.user_id).first()
    user_name = target_user.name if target_user else "Unknown"

    return DepositOut(
        id=deposit.id,
        month_id=deposit.month_id,
        user_id=deposit.user_id,
        user_name=user_name,
        amount=deposit.amount,
        date=deposit.date
    )

@router.delete("/{deposit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deposit(
    deposit_id: int,
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles(["SUPER_ADMIN", "MANAGER"]))
):
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    mess_month = db.query(MessMonth).filter(MessMonth.id == deposit.month_id).first()
    if mess_month and mess_month.is_closed:
        raise HTTPException(status_code=400, detail="Target mess month is closed")

    db.delete(deposit)
    db.commit()
    return None
