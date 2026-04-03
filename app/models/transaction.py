import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SAEnum, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(SAEnum(TransactionType), nullable=False)
    category = Column(String(100), nullable=False)
    date = Column(DateTime, nullable=False, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="transactions")