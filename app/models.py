from sqlalchemy import Column, Integer, String, Boolean, Float, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="MEMBER")  # SUPER_ADMIN, MANAGER, MEMBER
    is_active = Column(Boolean, default=True)

    managed_months = relationship("MessMonth", back_populates="manager")
    daily_meals = relationship("DailyMeal", back_populates="user")
    deposits = relationship("Deposit", back_populates="user")


class MessMonth(Base):
    __tablename__ = "mess_months"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_closed = Column(Boolean, default=False)

    __table_args__ = (UniqueConstraint("year", "month", name="uq_year_month"),)

    manager = relationship("User", back_populates="managed_months")
    daily_meals = relationship("DailyMeal", back_populates="month")
    expenses = relationship("Expense", back_populates="month")
    deposits = relationship("Deposit", back_populates="month")


class DailyMeal(Base):
    __tablename__ = "daily_meals"

    id = Column(Integer, primary_key=True, index=True)
    month_id = Column(Integer, ForeignKey("mess_months.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    lunch_count = Column(Integer, default=1)
    dinner_count = Column(Integer, default=1)

    __table_args__ = (UniqueConstraint("month_id", "user_id", "date", name="uq_month_user_date"),)

    month = relationship("MessMonth", back_populates="daily_meals")
    user = relationship("User", back_populates="daily_meals")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    month_id = Column(Integer, ForeignKey("mess_months.id"), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(String, nullable=False)
    date = Column(Date, nullable=False)

    month = relationship("MessMonth", back_populates="expenses")


class Deposit(Base):
    __tablename__ = "deposits"

    id = Column(Integer, primary_key=True, index=True)
    month_id = Column(Integer, ForeignKey("mess_months.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False)

    month = relationship("MessMonth", back_populates="deposits")
    user = relationship("User", back_populates="deposits")
