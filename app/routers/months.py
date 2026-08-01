from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import MessMonth, User
from app.schemas import AssignManagerRequest, MessMonthOut
from app.security import get_current_user, require_roles

from app.month_utils import get_current_local_now, get_or_create_mess_month

from app.notification_service import create_and_broadcast_notification

router = APIRouter(prefix="/api/v1/months", tags=["Mess Months"])

@router.post("/assign-manager", response_model=MessMonthOut)
def assign_manager(
    req: AssignManagerRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(["SUPER_ADMIN"]))
):
    now = get_current_local_now()
    target_year = req.year if req.year else now.year
    target_month = req.month if req.month else now.month

    target_user = db.query(User).filter(User.id == req.user_id, User.is_active == True).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")

    # 1. Revert all current MANAGER users (except SUPER_ADMIN) to MEMBER
    existing_managers = db.query(User).filter(User.role == "MANAGER").all()
    for mgr in existing_managers:
        mgr.role = "MEMBER"

    # 2. Update role of target user to MANAGER if not SUPER_ADMIN
    if target_user.role != "SUPER_ADMIN":
        target_user.role = "MANAGER"
    
    db.commit()

    mess_month = get_or_create_mess_month(db, target_year, target_month, fallback_user_id=req.user_id)
    mess_month.manager_id = req.user_id
    db.commit()
    db.refresh(mess_month)

    create_and_broadcast_notification(
        db,
        title="Mess Manager Assigned",
        message=f"{target_user.name} has been assigned as the Mess Manager",
        notification_type="MANAGER"
    )

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
    now = get_current_local_now()
    mess_month = get_or_create_mess_month(db, now.year, now.month, fallback_user_id=current_user.id)

    manager = db.query(User).filter(User.id == mess_month.manager_id, User.is_active == True).first()
    if not manager:
        active_mgr = db.query(User).filter(User.role == "MANAGER", User.is_active == True).first()
        if active_mgr:
            mess_month.manager_id = active_mgr.id
            db.commit()
            manager = active_mgr
        else:
            super_admin = db.query(User).filter(User.role == "SUPER_ADMIN", User.is_active == True).first()
            if super_admin:
                mess_month.manager_id = super_admin.id
                db.commit()
                manager = super_admin

    manager_name = manager.name if manager else "Super Admin"

    return MessMonthOut(
        id=mess_month.id,
        year=mess_month.year,
        month=mess_month.month,
        manager_id=mess_month.manager_id,
        manager_name=manager_name,
        is_closed=mess_month.is_closed
    )
