from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, DailyMeal, Deposit, Expense, MessMonth
from app.schemas import UserCreate, UserOut
from app.security import get_password_hash, get_current_user, require_roles

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(["SUPER_ADMIN"]))
):
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    new_user = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role.upper(),
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.get("", response_model=List[UserOut])
def list_users(
    include_super_admin: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "MANAGER"]))
):
    query = db.query(User).filter(User.is_active == True)
    if not include_super_admin:
        query = query.filter(User.role != "SUPER_ADMIN")
    return query.all()

@router.delete("/wipe-database", status_code=status.HTTP_200_OK)
def wipe_database(
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(["SUPER_ADMIN"]))
):
    """
    Super Admin only endpoint to completely wipe database mess records and non-super-admin users.
    """
    db.query(Expense).delete()
    db.query(Deposit).delete()
    db.query(DailyMeal).delete()
    db.query(MessMonth).delete()
    db.query(User).filter(User.role != "SUPER_ADMIN").delete()
    db.commit()
    return {"message": "Database wiped successfully. All mess data and roommate accounts removed except Super Admin."}

@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(["SUPER_ADMIN"]))
):
    """
    Super Admin endpoint to delete a roommate and cascade delete all their meals & deposits.
    """
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if target_user.role == "SUPER_ADMIN":
        raise HTTPException(status_code=400, detail="Super Admin account cannot be deleted")

    # 1. Delete all daily meals for this user
    db.query(DailyMeal).filter(DailyMeal.user_id == user_id).delete()

    # 2. Delete all deposits for this user
    db.query(Deposit).filter(Deposit.user_id == user_id).delete()

    # 3. If user is manager in any MessMonth, reassign manager to Super Admin
    super_admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
    if super_admin:
        db.query(MessMonth).filter(MessMonth.manager_id == user_id).update({"manager_id": super_admin.id})
        db.commit()

    # 4. Delete user record
    db.delete(target_user)
    db.commit()

    return {"message": f"User '{target_user.name}' and all associated meals and deposits were deleted successfully."}
