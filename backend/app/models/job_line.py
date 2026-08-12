from sqlalchemy import Column, BigInteger, Integer, Numeric, Text, DateTime
from sqlalchemy.sql import func
from app.db.database import Base


# SQLite only auto-increments a plain INTEGER PRIMARY KEY, so a BIGINT key
# never gets a value there and inserts fail on a NOT NULL id. The variant keeps
# BIGINT on MySQL, which is what production uses, and lets the tests run against
# an in-memory database.
_AUTO_PK = BigInteger().with_variant(Integer, "sqlite")


class JobLine(Base):
    __tablename__ = "job_lines"

    id               = Column(_AUTO_PK, primary_key=True, autoincrement=True)
    item_id          = Column(BigInteger)
    job_id         = Column(BigInteger)
    price            = Column(Numeric(24, 2), nullable=False, default=0)
    item_details     = Column(Text)
    quantity         = Column(Integer, nullable=False, default=1)
    tax_amount       = Column(Numeric(24, 2), nullable=False, default=1)
    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())
    total_add_on_price = Column(Numeric(24, 2), nullable=False, default=0)
