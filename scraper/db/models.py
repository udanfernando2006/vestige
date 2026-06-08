from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import String, ForeignKey, Numeric, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Series(Base):
    __tablename__ = 'series'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)

    books: Mapped[List["Book"]] = relationship(back_populates="series")


class Book(Base):
    __tablename__ = 'books'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    isbn: Mapped[str] = mapped_column(String, unique=True)
    is_series_entry: Mapped[bool] = mapped_column(default=False)
    
    # Optional foreign key
    series_id: Mapped[Optional[int]] = mapped_column(ForeignKey('series.id'))

    series: Mapped[Optional["Series"]] = relationship(back_populates="books")
    tracking_pairs: Mapped[List["TrackingPair"]] = relationship(back_populates="book")


class Store(Base):
    __tablename__ = 'stores'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    base_url: Mapped[str]
    search_url_template: Mapped[Optional[str]]

    tracking_pairs: Mapped[List["TrackingPair"]] = relationship(back_populates="store")


class TrackingPair(Base):
    __tablename__ = 'tracking_pairs'

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey('books.id'))
    store_id: Mapped[int] = mapped_column(ForeignKey('stores.id'))
    product_url: Mapped[Optional[str]]
    price_selector: Mapped[Optional[str]]
    stock_selector: Mapped[Optional[str]]
    status: Mapped[str] = mapped_column(default='PENDING')
    selector_found_at: Mapped[Optional[datetime]]

    __table_args__ = (
        UniqueConstraint('book_id', 'store_id', name='uq_book_store'),
    )

    book: Mapped["Book"] = relationship(back_populates="tracking_pairs")
    store: Mapped["Store"] = relationship(back_populates="tracking_pairs")
    snapshots: Mapped[List["AvailabilitySnapshot"]] = relationship(back_populates="tracking_pair")


class AvailabilitySnapshot(Base):
    __tablename__ = 'availability_snapshots'

    id: Mapped[int] = mapped_column(primary_key=True)
    pair_id: Mapped[int] = mapped_column(ForeignKey('tracking_pairs.id'))
    in_stock: Mapped[Optional[bool]]
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    status: Mapped[str]
    source: Mapped[Optional[str]]
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    
    tracking_pair: Mapped["TrackingPair"] = relationship(back_populates="snapshots")

Index(
    'idx_pair_scraped_desc',
    AvailabilitySnapshot.pair_id,
    AvailabilitySnapshot.scraped_at.desc()
)