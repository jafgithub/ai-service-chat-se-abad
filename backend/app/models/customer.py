from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String(255), nullable=False)
    email      = Column(String(255), nullable=False)
    phone      = Column(String(30))
    latitude   = Column(Numeric(10, 7))
    longitude  = Column(Numeric(10, 7))
    address    = Column(Text)
    type       = Column(String(50), default="customer")
    created_at = Column(DateTime, server_default=func.now())

    orders = relationship("Job", back_populates="customer")
