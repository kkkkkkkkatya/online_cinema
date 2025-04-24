from datetime import datetime

from sqlalchemy import UniqueConstraint, ForeignKey, Integer, DateTime, func

from sqlalchemy.orm import relationship, Mapped, mapped_column

from .base import Base
from .. import UserModel, MovieModel


class CartModel(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    cart_items: Mapped[list["CartItemModel"]] = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan"
    )
    user: Mapped["UserModel"] = relationship("User", back_populates="cart")

    __table_args__ = (UniqueConstraint("user_id"),)

    def __repr__(self) -> str:
        return f"<Cart(id: {self.id}, user_id: {self.user_id}, cart_items: {self.cart_items})>"


class CartItemModel(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column(Integer, ForeignKey("carts.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(Integer, ForeignKey("movies.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    cart: Mapped["CartModel"] = relationship("Cart", back_populates="cart_items")
    movie: Mapped["MovieModel"] = relationship("Movie", back_populates="cart_items")

    __table_args__ = (UniqueConstraint("cart_id", "movie_id"),)

    def __repr__(self):
        return f"<CartItem(id={self.id}, cart_id={self.cart_id}, movie_id={self.movie_id}, added_at={self.added_at})>"

