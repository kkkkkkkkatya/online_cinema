from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.config import require_moderator_or_admin_user
from app.db import get_db, UserModel
from app.db.models.movies import (
    MovieModel,
    GenreModel,
    DirectorModel,
    StarModel,
    CertificationModel
)
from app.schemas.movies import (
    MovieListItemSchema,
    MovieListResponseSchema,
    MovieDetailSchema,
    MovieCreateSchema,
    MovieUpdateSchema
)

router = APIRouter()


@router.get(
    "/movies/",
    response_model=MovieListResponseSchema,
    summary="Get a paginated list of movies",
    description=(
            "This endpoint retrieves a paginated list of movies from the database. "
            "Clients can specify the `page` number and the number of items per page using `per_page`. "
            "The response includes details about the movies, total pages, and total items, "
            "along with links to the previous and next pages if applicable."
    ),
    responses={
        404: {
            "description": "No movies found.",
            "content": {
                "application/json": {
                    "example": {"detail": "No movies found."}
                }
            },
        }
    }
)
async def get_movie_list(
        page: int = Query(1, ge=1, description="Page number (1-based index)"),
        per_page: int = Query(10, ge=1, le=20, description="Number of items per page"),
        year: int | None = Query(None, description="Filter by year"),
        min_imdb: float | None = Query(None, description="Filter by min_imdb"),
        max_imdb: float | None = Query(None, description="Filter by max_imdb"),
        genre: str | None = Query(None, description="Filter by genre name"),
        director: str | None = Query(None, description="Filter by director name"),
        star: str | None = Query(None, description="Filter by star name"),
        search: str | None = Query(None, description="Search by title, description, actor or director"),
        sort_by: str | None = Query(None, description="Sort by 'price', 'year', 'votes'"),
        db: AsyncSession = Depends(get_db),
) -> MovieListResponseSchema:
    """
    Fetch a paginated list of movies from the database.

    This function retrieves a paginated list of movies, allowing the client to specify
    the page number and the number of items per page. It calculates the total pages
    and provides links to the previous and next pages when applicable.
    """
    offset = (page - 1) * per_page

    stmt = select(MovieModel).options(
        selectinload(MovieModel.directors),
        selectinload(MovieModel.stars),
        selectinload(MovieModel.genres),
    )

    # Filters
    if year:
        stmt = stmt.where(MovieModel.year == year)
    if min_imdb:
        stmt = stmt.where(MovieModel.imdb >= min_imdb)
    if max_imdb:
        stmt = stmt.where(MovieModel.imdb <= max_imdb)
    if director:
        stmt = stmt.join(MovieModel.directors).where(DirectorModel.name.ilike(f"%{director}%"))
    if star:
        stmt = stmt.join(MovieModel.stars).where(StarModel.name.ilike(f"%{star}%"))
    if genre:
        stmt = stmt.join(MovieModel.genres).where(GenreModel.name.ilike(f"%{genre}%"))
    if search:
        stmt = (
            stmt.outerjoin(MovieModel.directors)
            .outerjoin(MovieModel.stars)
            .where(
                or_(
                    MovieModel.name.ilike(f"%{search}%"),
                    MovieModel.description.ilike(f"%{search}%"),
                    DirectorModel.name.ilike(f"%{search}%"),
                    StarModel.name.ilike(f"%{search}%"),
                )
            )
        )

    sort_fields = {
        "price": MovieModel.price,
        "year": MovieModel.year,
        "votes": MovieModel.votes,
    }
    if sort_by in sort_fields:
        stmt = stmt.order_by(sort_fields[sort_by].desc())
    else:
        # Default ordering if no sort provided
        default_order = MovieModel.default_order_by()
        if default_order:
            stmt = stmt.order_by(*default_order)

    count_stmt = select(func.count(MovieModel.id))
    if stmt._where_criteria:
        count_stmt = count_stmt.where(*stmt._where_criteria)
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    if not total_items:
        raise HTTPException(status_code=404, detail="No movies found.")

    # Pagination
    stmt = stmt.offset(offset).limit(per_page)
    result_movies = await db.execute(stmt)
    movies = result_movies.scalars().all()

    movie_list = [MovieListItemSchema.model_validate(movie) for movie in movies]

    total_pages = (total_items + per_page - 1) // per_page

    response = MovieListResponseSchema(
        movies=movie_list,
        prev_page=f"/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None,
        next_page=f"/movies/?page={page + 1}&per_page={per_page}" if page < total_pages else None,
        total_pages=total_pages,
        total_items=total_items,
    )
    return response


@router.post(
    "/movies/",
    response_model=MovieDetailSchema,
    summary="Add a new movie",
    description=(
            "This endpoint allows clients to add a new movie to the database. "
            "It accepts details such as name, date, genres, actors, languages, and "
            "other attributes. The associated country, genres, actors, and languages "
            "will be created or linked automatically."
    ),
    responses={
        201: {
            "description": "Movie created successfully.",
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
async def create_movie(
        movie_data: MovieCreateSchema,
        _: UserModel = Depends(require_moderator_or_admin_user),
        db: AsyncSession = Depends(get_db)
) -> MovieDetailSchema:
    """
        Add a new movie to the database.
        Only accessible by admins or moderators.
    """
    existing_stmt = select(MovieModel).where(
        (MovieModel.name == movie_data.name),
        (MovieModel.year == movie_data.year)
    )
    existing_result = await db.execute(existing_stmt)
    existing_movie = existing_result.scalars().first()

    if existing_movie:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A movie with the name '{movie_data.name}' and release year "
                f"'{movie_data.year}' already exists."
            )
        )

    try:
        certification_stmt = select(CertificationModel).where(CertificationModel.name == movie_data.certification)
        certification_result = await db.execute(certification_stmt)
        certification = certification_result.scalars().first()
        if not certification:
            certification = CertificationModel(name=movie_data.certification)
            db.add(certification)
            await db.flush()

        genres = []
        for genre_name in movie_data.genres:
            genre_stmt = select(GenreModel).where(GenreModel.name == genre_name)
            genre_result = await db.execute(genre_stmt)
            genre = genre_result.scalars().first()

            if not genre:
                genre = GenreModel(name=genre_name)
                db.add(genre)
                await db.flush()
            genres.append(genre)

        stars = []
        for star_name in movie_data.stars:
            star_stmt = select(StarModel).where(StarModel.name == star_name)
            star_result = await db.execute(star_stmt)
            star = star_result.scalars().first()

            if not star:
                star = StarModel(name=star_name)
                db.add(star)
                await db.flush()
            stars.append(star)

        directors = []
        for director_name in movie_data.directors:
            director_stmt = select(DirectorModel).where(DirectorModel.name == director_name)
            director_result = await db.execute(director_stmt)
            director = director_result.scalars().first()

            if not director:
                director = DirectorModel(name=director_name)
                db.add(director)
                await db.flush()
            directors.append(director)

        movie = MovieModel(
            uuid=movie_data.uuid,
            name=movie_data.name,
            year=movie_data.year,
            time=movie_data.time,
            imdb=movie_data.imdb,
            votes=movie_data.votes,
            meta_score=movie_data.meta_score,
            gross=movie_data.gross,
            description=movie_data.description,
            price=movie_data.price,
            genres=genres,
            stars=stars,
            directors=directors,
            certification=certification,
        )
        db.add(movie)
        await db.commit()
        await db.refresh(movie, ["genres", "stars", "directors"])

        return MovieDetailSchema.model_validate(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.get(
    "/genres/",
    summary="Get list of genres",
    description="This endpoint retrieves a list of genres with the count of movies in each.",
    responses={
        404: {
            "description": "No genres found.",
            "content": {"application/json": {"example": {"detail": "No genres found."}}},
        }
    },
)
async def get_genres(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(GenreModel, func.count(MovieModel.id).label("movie_count"))
        .join(MovieModel.genres)
        .group_by(GenreModel.id)
    )

    result = await db.execute(stmt)
    genres_with_movie_count = result.all()

    return [
        {"name": genre.name, "movie_count": movie_count}
        for genre, movie_count in genres_with_movie_count
    ]


@router.get(
    "/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Get movie details by ID",
    description=(
            "Fetch detailed information about a specific movie by its unique ID. "
            "This endpoint retrieves all available details for the movie, such as "
            "its name, genre, crew, budget, and revenue. If the movie with the given "
            "ID is not found, a 404 error will be returned."
    ),
    responses={
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        }
    }
)
async def get_movie_by_id(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    """
    Retrieve detailed information about a specific movie by its ID.

    This function fetches detailed information about a movie identified by its unique ID.
    If the movie does not exist, a 404 error is returned.
    """
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.certification),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.stars),
            joinedload(MovieModel.directors),
        )
        .where(MovieModel.id == movie_id)
    )

    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    return MovieDetailSchema.model_validate(movie)


@router.patch(
    "/{movie_id}/",
    summary="Update a movie by ID",
    description=(
            "<h3>Update details of a specific movie by its unique ID.</h3>"
            "<p>This endpoint updates the details of an existing movie. If the movie with "
            "the given ID does not exist, a 404 error is returned.</p>"
    ),
    responses={
        200: {
            "description": "Movie updated successfully.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie updated successfully."}
                }
            },
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
    }
)
async def update_movie(
        movie_id: int,
        movie_data: MovieUpdateSchema,
        _: UserModel = Depends(require_moderator_or_admin_user),
        db: AsyncSession = Depends(get_db),
):
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    for field, value in movie_data.model_dump(exclude_unset=True).items():
        setattr(movie, field, value)

    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return {"detail": "Movie updated successfully."}


@router.delete(
    "/movies/{movie_id}/",
    summary="Delete a movie by ID",
    description=(
            "<h3>Delete a specific movie from the database by its unique ID.</h3>"
            "<p>If the movie exists, it will be deleted. If it does not exist, "
            "a 404 error will be returned.</p>"
    ),
    responses={
        204: {
            "description": "Movie deleted successfully."
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
    },
    status_code=204
)
async def delete_movie(
        movie_id: int,
        _: UserModel = Depends(require_moderator_or_admin_user),
        db: AsyncSession = Depends(get_db),
):
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    await db.delete(movie)
    await db.commit()

    return {"detail": "Movie deleted successfully."}
