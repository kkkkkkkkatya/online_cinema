from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.config import get_current_user
from app.db import UserModel, MovieModel, CartModel, CartItemModel
from app.db.database import get_db
from app.schemas import MessageResponseSchema
from app.schemas.carts import CartResponseSchema, CartItemBaseSchema

router = APIRouter()


@router.post(
    "/carts/",
    response_model=MessageResponseSchema,
    summary="Add a new cart item to cart",
    description=(
            "This endpoint allows clients to add a new cart item to the database. "
    ),
    responses={
        201: {
            "description": "Cart item added successfully.",
        },
        400: {
            "description": "Invalid input.",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid input data."}
                }
            },
        }
    },
    status_code=201
)
async def create_cart(
        movie_id: int,
        user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
) -> MessageResponseSchema:
    # Перевірка, чи існує фільм
    movie_result = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    movie = movie_result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    # Пошук або створення кошика
    cart_result = await db.execute(select(CartModel).where(CartModel.user_id == user.id))
    cart = cart_result.scalar_one_or_none()

    if not cart:
        cart = CartModel(user_id=user.id)
        db.add(cart)
        await db.flush()

    # Перевірка, чи фільм уже в кошику
    item_stmt = select(CartItemModel).where(
        CartItemModel.cart_id == cart.id,
        CartItemModel.movie_id == movie_id
    )
    item_result = await db.execute(item_stmt)
    if item_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Movie already in cart")

    # Додаємо фільм до кошика
    cart_item = CartItemModel(cart_id=cart.id, movie_id=movie_id)
    db.add(cart_item)
    await db.commit()

    return MessageResponseSchema(message="Movie added to cart successfully.")


@router.get(
    "/{cart_id}/",
    response_model=CartResponseSchema,
    summary="Get cart details by ID",
    description=(
            "Fetch detailed information about a specific movie by its unique ID. "
    ),
    responses={
        404: {
            "description": "Cart not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Cart with the given ID was not found."}
                }
            },
        }
    }
)
async def get_cart_by_id(
    cart_id: int,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CartResponseSchema:
    # Отримуємо кошик з БД
    cart_result = await db.execute(
        select(CartModel)
        .options(
            joinedload(CartModel.cart_items)
            .joinedload(CartItemModel.movie)
            .joinedload(MovieModel.genres)
        )
        .where(CartModel.id == cart_id)
    )
    cart = cart_result.scalar_one_or_none()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    # Доступ дозволено лише адміну або власнику
    if user.group.name != "ADMIN" and cart.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this cart.")

    # Створюємо список фільмів у кошику
    items: list[CartItemBaseSchema] = []
    for item in cart.cart_items:
        if item.movie:
            items.append(
                CartItemBaseSchema(
                    id=item.movie.id,
                    title=item.movie.title,
                    price=item.movie.price,
                    genre=[genre.name for genre in item.movie.genres],
                    release_year=item.movie.year,
                )
            )

    return CartResponseSchema(id=cart.id, items=items)


@router.delete(
    "/carts/{cart_id}/",
    summary="Delete a cart by ID",
    description=(
            "<h3>Delete a cart from the database by its unique ID.</h3>"
            "<p>If the cart exists, it will be deleted. If it does not exist, "
            "a 404 error will be returned.</p>"
    ),
    responses={
        204: {
            "description": "Cart deleted successfully."
        },
        404: {
            "description": "Cart not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Cart with the given ID was not found."}
                }
            },
        },
    },
    status_code=204
)
async def delete_cart(
    cart_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    cart_result = await db.execute(select(CartModel).where(CartModel.id == cart_id))
    cart = cart_result.scalar_one_or_none()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart with the given ID was not found.")

    # Перевірка прав доступу
    if user.id != cart.user_id and user.group.name != "ADMIN":
        raise HTTPException(status_code=403, detail="You are not allowed to delete this cart.")

    await db.delete(cart)
    await db.commit()
    return {"detail": "Cart deleted successfully."}


@router.delete(
    "/carts/{cart_id}/{cart_item_id}",
    summary="Delete a specific cart item from a cart",
    description=(
        "<h3>Delete a specific item from a cart by cart ID and item ID.</h3>"
        "<p>If the cart or item doesn't exist, a 404 error is returned.</p>"
        "<p>If the user is not the owner or an admin, a 403 error is returned.</p>"
    ),
    responses={
        204: {"description": "Cart item deleted successfully."},
        403: {"description": "Access denied."},
        404: {"description": "Cart or item not found."},
    },
    status_code=204
)
async def delete_cart_item(
    cart_id: int,
    cart_item_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    # Отримати кошик
    cart_result = await db.execute(select(CartModel).where(CartModel.id == cart_id))
    cart = cart_result.scalar_one_or_none()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    # Перевірка прав доступу
    if user.id != cart.user_id and user.group.name != "ADMIN":
        raise HTTPException(status_code=403, detail="You are not allowed to modify this cart.")

    # Отримати елемент кошика
    item_result = await db.execute(
        select(CartItemModel).where(
            CartItemModel.id == cart_item_id,
            CartItemModel.cart_id == cart.id
        )
    )
    item = item_result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found.")

    await db.delete(item)
    await db.commit()
    return {"detail": "Movie deleted successfully."}
