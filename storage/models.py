from sqlalchemy.orm import DeclarativeBase, mapped_column
from sqlalchemy import Integer, String, DateTime, Float, func
from sqlalchemy.dialects.mysql import TIMESTAMP

class Base(DeclarativeBase):
    pass


class AttractionInfo(Base):
    __tablename__ = "attraction_info"
    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(String(50), nullable=False)
    attraction_category = mapped_column(String(50), nullable=False)
    hours_open = mapped_column(Integer, nullable=False)
    attraction_timestamp = mapped_column(DateTime, nullable=False)
    date_created = mapped_column(TIMESTAMP(fsp=6), nullable=False, default=func.now(6))
    trace_id = mapped_column(String(50), nullable=False)

    def to_dict(self):
        dict = {}
        dict['id'] = self.id
        dict['user_id'] = self.user_id
        dict['attraction_category'] = self.attraction_category
        dict['hours_open'] = self.hours_open
        dict['attraction_timestamp'] = self.attraction_timestamp
        dict['date_created'] = self.date_created
        dict['trace_id'] = self.trace_id

        return dict


class ExpenseInfo(Base):
    __tablename__ = "expense_info"
    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(String(50), nullable=False)
    amount = mapped_column(Float, nullable=False)
    expense_category = mapped_column(String(50), nullable=False)
    expense_timestamp = mapped_column(DateTime, nullable=False)
    date_created = mapped_column(TIMESTAMP(fsp=6), nullable=False, default=func.now(6))
    trace_id = mapped_column(String(50), nullable=False)

    def to_dict(self):
        dict = {}
        dict['id'] = self.id
        dict['user_id'] = self.user_id
        dict['amount'] = self.amount
        dict['expense_category'] = self.expense_category
        dict['expense_timestamp'] = self.expense_timestamp
        dict['date_created'] = self.date_created
        dict['trace_id'] = self.trace_id

        return dict