import asyncio
import math
from typing import List, Dict, Tuple

import pandas as pd
from sqlalchemy import insert, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from tqdm import tqdm

from app.config import get_settings
from app.db.models.movies import (
    MoviesGenresModel,
    MoviesDirectorsModel,
    MoviesStarsModel,
    GenreModel,
    StarModel,
    DirectorModel,
    CertificationModel,
    MovieModel
)
from app.db.database import get_db_contextmanager

CHUNK_SIZE = 1000


class CSVDatabaseSeeder:
    def __init__(self, csv_file_path: str, db_session: AsyncSession) -> None:
        self._csv_file_path = csv_file_path
        self._db_session = db_session

    async def is_db_populated(self) -> bool:
        result = await self._db_session.execute(select(MovieModel).limit(1))
        first_movie = result.scalars().first()
        return first_movie is not None

    def _preprocess_csv(self) -> pd.DataFrame:
        data = pd.read_csv(self._csv_file_path)
        data = data.drop_duplicates(subset=['names', 'date_x'], keep='first')

        for col in ['crew', 'genre', 'certification']:
            data[col] = data[col].fillna('Unknown').astype(str)

        data['crew'] = (
            data['crew']
            .str.replace(r'\s+', '', regex=True)
            .apply(lambda x: ','.join(sorted(set(x.split(',')))) if x != 'Unknown' else x)
        )

        data['genre'] = data['genre'].str.replace('\u00A0', '', regex=True)
        data['date_x'] = pd.to_datetime(data['date_x'], format='%Y-%m-%d', errors='coerce').dt.date

        return data

    async def _get_or_create_bulk(self, model, items: List[str], unique_field: str) -> Dict[str, object]:
        existing_dict: Dict[str, object] = {}
        if items:
            for i in range(0, len(items), CHUNK_SIZE):
                chunk = items[i: i + CHUNK_SIZE]
                result = await self._db_session.execute(
                    select(model).where(getattr(model, unique_field).in_(chunk))
                )
                existing_in_chunk = result.scalars().all()
                for obj in existing_in_chunk:
                    key = getattr(obj, unique_field)
                    existing_dict[key] = obj

        new_items = [item for item in items if item not in existing_dict]
        new_records = [{unique_field: item} for item in new_items]

        if new_records:
            for i in range(0, len(new_records), CHUNK_SIZE):
                chunk = new_records[i: i + CHUNK_SIZE]
                await self._db_session.execute(insert(model).values(chunk))
                await self._db_session.flush()

            for i in range(0, len(new_items), CHUNK_SIZE):
                chunk = new_items[i: i + CHUNK_SIZE]
                result_new = await self._db_session.execute(
                    select(model).where(getattr(model, unique_field).in_(chunk))
                )
                inserted_in_chunk = result_new.scalars().all()
                for obj in inserted_in_chunk:
                    key = getattr(obj, unique_field)
                    existing_dict[key] = obj

        return existing_dict

    async def _bulk_insert(self, table, data_list: List[Dict[str, int]]) -> None:
        total_records = len(data_list)
        if total_records == 0:
            return

        num_chunks = math.ceil(total_records / CHUNK_SIZE)
        table_name = getattr(table, '__tablename__', str(table))

        for chunk_index in tqdm(range(num_chunks), desc=f"Inserting into {table_name}"):
            start = chunk_index * CHUNK_SIZE
            end = start + CHUNK_SIZE
            chunk = data_list[start:end]
            if chunk:
                await self._db_session.execute(insert(table).values(chunk))

        await self._db_session.flush()

    async def _prepare_reference_data(
            self, data: pd.DataFrame
    ) -> Tuple[Dict[str, object], Dict[str, object], Dict[str, object], Dict[str, object]]:
        # Genres
        genres = {
            genre.strip()
            for genres_str in data['genre'].dropna()
            for genre in genres_str.split(',')
            if genre.strip()
        }

        # Stars (crew)
        stars = {
            person.strip()
            for crew_str in data['crew'].dropna()
            for person in crew_str.split(',')
            if person.strip()
        }

        # Directors (optional column)
        if 'director' in data.columns:
            directors = {
                director.strip()
                for dir_str in data['director'].dropna()
                for director in dir_str.split(',')
                if director.strip()
            }
        else:
            directors = set()

        # Certifications (can be nullable)
        certifications = list(data['certification'].dropna().unique())

        # Create or get existing from DB
        genre_map = await self._get_or_create_bulk(GenreModel, list(genres), 'name')
        star_map = await self._get_or_create_bulk(StarModel, list(stars), 'name')
        director_map = await self._get_or_create_bulk(DirectorModel, list(directors), 'name')
        certification_map = await self._get_or_create_bulk(CertificationModel, certifications, 'name')

        return genre_map, star_map, director_map, certification_map

    def _prepare_movies_data(self, data: pd.DataFrame, certification_map: Dict[str, object]) -> List[Dict[str, object]]:
        movies_data = []
        for _, row in tqdm(data.iterrows(), total=data.shape[0], desc="Processing movies"):
            certification = certification_map.get(row['certification'], None)
            if certification is None:
                continue  # skip if no valid certification

            movie = {
                "name": row['names'],
                "year": row['date_x'].year if pd.notnull(row['date_x']) else 2000,
                "time": int(row.get('time', 100)),
                "imdb": float(row['score']),
                "votes": int(row.get('votes', 0)),
                "meta_score": float(row.get('meta_score', 0.0)),
                "gross": float(row.get('revenue', 0.0)),
                "description": row['overview'],
                "price": float(row.get('price', 10.00)),
                "certification_id": certification.id,
            }
            movies_data.append(movie)
        return movies_data

    def _prepare_associations(self, data: pd.DataFrame, movie_ids: List[int], genre_map, star_map, director_map) -> Tuple[List[Dict[str, int]], List[Dict[str, int]], List[Dict[str, int]]]:
        movie_genres_data = []
        movie_stars_data = []
        movie_directors_data = []

        for i, (_, row) in enumerate(tqdm(data.iterrows(), total=data.shape[0], desc="Processing associations")):
            movie_id = movie_ids[i]

            for genre_name in row['genre'].split(','):
                genre = genre_map.get(genre_name.strip())
                if genre:
                    movie_genres_data.append({"movie_id": movie_id, "genre_id": genre.id})

            for star_name in row['crew'].split(','):
                star = star_map.get(star_name.strip())
                if star:
                    movie_stars_data.append({"movie_id": movie_id, "star_id": star.id})

            if 'director' in row and pd.notnull(row['director']):
                for director_name in row['director'].split(','):
                    director = director_map.get(director_name.strip())
                    if director:
                        movie_directors_data.append({"movie_id": movie_id, "director_id": director.id})

        return movie_genres_data, movie_stars_data, movie_directors_data

    async def seed(self) -> None:
        try:
            if self._db_session.in_transaction():
                await self._db_session.rollback()

            data = self._preprocess_csv()

            genre_map, star_map, director_map, certification_map = await self._prepare_reference_data(data)

            movies_data = self._prepare_movies_data(data, certification_map)

            result = await self._db_session.execute(
                insert(MovieModel).returning(MovieModel.id),
                movies_data
            )
            movie_ids = list(result.scalars().all())

            movie_genres_data, movie_stars_data, movie_directors_data = self._prepare_associations(
                data, movie_ids, genre_map, star_map, director_map
            )

            await self._bulk_insert(MoviesGenresModel, movie_genres_data)
            await self._bulk_insert(MoviesStarsModel, movie_stars_data)
            await self._bulk_insert(MoviesDirectorsModel, movie_directors_data)

            await self._db_session.commit()
            print("Seeding completed.")

        except SQLAlchemyError as e:
            print(f"An error occurred: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise


async def main() -> None:
    settings = get_settings()
    async with get_db_contextmanager() as db_session:
        seeder = CSVDatabaseSeeder(settings.PATH_TO_MOVIES_CSV, db_session)

        if not await seeder.is_db_populated():
            try:
                await seeder.seed()
                print("Database seeding completed successfully.")
            except Exception as e:
                print(f"Failed to seed the database: {e}")
        else:
            print("Database is already populated. Skipping seeding.")


if __name__ == "__main__":
    asyncio.run(main())
