from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import MessMonth, User
from app.schemas import AssignManagerRequest, MessMonthOut
from app.security import get_current_user, require_roles

router = APIRouter(prefix="/api/v1/months", tags=["Mess Months"])

@router.post("/assign-manager", response_model=MessMonthOut)
def assign_manager(
    req: AssignManagerRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(["SUPER_ADMIN"]))
):
    now = datetime.now()
    target_year = req.year if req.year else now.year
    target_month = req.month if req.month else now.month

    target_user = db.query(User).filter(User.id == req.user_id, User.is_active == True).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")

    # Update role of user to MANAGER if not SUPER_ADMIN
    if target_user.role != "SUPER_ADMIN":
        target_user.role = "MANAGER"
        db.commit()

    mess_month = db.query(MessMonth).filter(
        MessMonth.year == target_year,
        MessMonth.month == target_month
    ).first()

    if mess_month:
        mess_month.manager_id = req.user_id
    else:
        mess_month = MessMonth(
            year=target_year,
            month=target_month,
            manager_id=req.user_id,
            is_closed=False
        )
        db.add(mess_month)

    db.commit()
    db.refresh(mess_month)

    return MessMonthOut(
        id=mess_month.id,
        year=mess_month.year,
        month=mess_month.month,
        manager_id=mess_month.manager_id,
        manager_name=target_user.name,
        is_closed=mess_month.is_closed
    )

@router.get("/current", response_model=MessMonthOut)
def get_current_month(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.now()
    mess_month = db.query(MessMonth).filter(
        MessMonth.year == now.year,
        MessMonth.month == now.month
    ).first()

    if not mess_month:
        # Create a default month with Super Admin or current user as manager if none exists
        default_manager = db.query(User).filter(User.role == "SUPER_ADMIN").first()
        manager_id = default_manager.id if default_manager else current_user.id
        mess_month = MessMonth(
            year=now.year,
            month=now.month,
            manager_id=manager_id,
            is_closed=False
        )
        db.add(mess_month)
        db.commit()
        db.refresh(mess_month)

    manager = db.query(User).filter(User.id == mess_month.manager_id).first()
    manager_name = manager.name if manager else "Unknown"

    return MessMonthOut(
        id=mess_month.id,
        year=mess_month.year,
        month=mess_month.month,
        manager_id=mess_month.manager_id,
        manager_name=manager_name,
        is_closed=mess_month.is_closed
    )
