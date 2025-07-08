import pytest
from sqlalchemy import select

from app.db import CartModel, CartItemModel


@pytest.mark.asyncio
async def test_add_movie_to_cart(client, seed_database, auth_headers, db_session):
    """
    Test adding a movie to the user's cart.
    """
    movie_id = 1

    response = await client.post(f"/api/carts/?movie_id={movie_id}", headers=auth_headers)

    assert response.status_code == 201, f"Expected 201, got {response.status_code}"
    assert response.json()["message"] == "Movie added to cart successfully."

    result = await db_session.execute(select(CartModel).where(CartModel.user_id == 1))
    cart = result.scalar_one_or_none()
    assert cart is not None, "Cart was not created in DB"

    item_result = await db_session.execute(select(CartItemModel).where(CartItemModel.cart_id == cart.id))
    cart_items = item_result.scalars().all()
    assert len(cart_items) == 1
    assert cart_items[0].movie_id == movie_id


@pytest.mark.asyncio
async def test_add_same_movie_twice_to_cart(client, seed_database, auth_headers):
    """
    Test adding the same movie twice should fail.
    """
    movie_id = 1

    await client.post(f"/api/carts/?movie_id={movie_id}", headers=auth_headers)
    response = await client.post(f"/api/carts/?movie_id={movie_id}", headers=auth_headers)

    assert response.status_code == 400
    assert response.json() == {"detail": "Movie already in cart"}


@pytest.mark.asyncio
async def test_get_cart_by_id(client, seed_database, auth_headers, db_session):
    """
    Test retrieving a user's cart by ID.
    """
    movie_id = 1
    await client.post(f"/api/carts/?movie_id={movie_id}", headers=auth_headers)

    cart_result = await db_session.execute(select(CartModel).where(CartModel.user_id == 1))
    cart = cart_result.scalar_one_or_none()

    response = await client.get(f"/api/carts/{cart.id}/", headers=auth_headers)
    assert response.status_code == 200
    cart_data = response.json()
    assert cart_data["id"] == cart.id
    assert len(cart_data["items"]) == 1
    assert cart_data["items"][0]["id"] == movie_id


@pytest.mark.asyncio
async def test_delete_cart(client, seed_database, auth_headers, db_session):
    """
    Test deleting a cart by ID.
    """
    movie_id = 1
    await client.post(f"/api/carts/?movie_id={movie_id}", headers=auth_headers)

    cart_result = await db_session.execute(select(CartModel).where(CartModel.user_id == 1))
    cart = cart_result.scalar_one_or_none()

    response = await client.delete(f"/api/carts/{cart.id}/", headers=auth_headers)
    assert response.status_code == 204

    cart_result = await db_session.execute(select(CartModel).where(CartModel.id == cart.id))
    assert cart_result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_cart_item(client, seed_database, auth_headers, db_session):
    """
    Test deleting a cart item by ID.
    """
    movie_id = 1
    await client.post(f"/api/carts/?movie_id={movie_id}", headers=auth_headers)

    cart_result = await db_session.execute(select(CartModel).where(CartModel.user_id == 1))
    cart = cart_result.scalar_one_or_none()

    item_result = await db_session.execute(select(CartItemModel).where(CartItemModel.cart_id == cart.id))
    cart_item = item_result.scalar_one()

    response = await client.delete(f"/api/carts/{cart.id}/{cart_item.id}", headers=auth_headers)
    assert response.status_code == 204

    item_result = await db_session.execute(select(CartItemModel).where(CartItemModel.id == cart_item.id))
    assert item_result.scalar_one_or_none() is None
