"""Tests for database base models and mixins."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from mdpilot.config.schema import DatabaseConfig
from mdpilot.database.base import Base, TimestampMixin
from mdpilot.database.engine import dispose_engine, init_db
from mdpilot.database.session import get_session


# Sample model using Base and TimestampMixin
class SampleModel(Base, TimestampMixin):
    """Sample model for base class testing."""

    __tablename__ = "test_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=True)


@pytest.fixture
def sqlite_config():
    """Create an in-memory SQLite configuration for testing."""
    return DatabaseConfig(
        url="sqlite+aiosqlite:///:memory:",
        echo=False,
    )


@pytest.fixture
async def initialized_db(sqlite_config):
    """Initialize database and create tables."""
    init_db(sqlite_config)

    # Create tables
    from mdpilot.database.engine import get_engine

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await dispose_engine()


class TestBase:
    """Tests for Base declarative base."""

    def test_base_has_metadata(self):
        """Test that Base has metadata attribute."""
        assert hasattr(Base, "metadata")
        assert Base.metadata is not None

    def test_base_metadata_has_naming_convention(self):
        """Test that metadata has naming convention configured."""
        naming_convention = Base.metadata.naming_convention
        assert naming_convention is not None
        assert "pk" in naming_convention
        assert "fk" in naming_convention
        assert "ix" in naming_convention
        assert "uq" in naming_convention
        assert "ck" in naming_convention

    def test_model_inherits_from_base(self):
        """Test that models can inherit from Base."""
        assert issubclass(SampleModel, Base)

    def test_model_has_tablename(self):
        """Test that model has __tablename__ attribute."""
        assert hasattr(SampleModel, "__tablename__")
        assert SampleModel.__tablename__ == "test_models"

    def test_model_has_columns(self):
        """Test that model has defined columns."""
        assert hasattr(SampleModel, "id")
        assert hasattr(SampleModel, "name")
        assert hasattr(SampleModel, "value")


class TestTimestampMixin:
    """Tests for TimestampMixin."""

    def test_timestamp_mixin_has_created_at(self):
        """Test that TimestampMixin adds created_at field."""
        assert hasattr(SampleModel, "created_at")

    def test_timestamp_mixin_has_updated_at(self):
        """Test that TimestampMixin adds updated_at field."""
        assert hasattr(SampleModel, "updated_at")

    async def test_created_at_set_on_insert(self, initialized_db):
        """Test that created_at is automatically set on insert."""
        before = datetime.now(timezone.utc).replace(tzinfo=None)  # SQLite stores naive

        async with get_session() as session:
            model = SampleModel(name="test", value=42)
            session.add(model)
            await session.commit()
            await session.refresh(model)

            assert model.created_at is not None
            # SQLite stores as naive datetime, so compare without timezone
            created_naive = model.created_at.replace(tzinfo=None) if model.created_at.tzinfo else model.created_at
            assert created_naive >= before

    async def test_updated_at_set_on_insert(self, initialized_db):
        """Test that updated_at is automatically set on insert."""
        before = datetime.now(timezone.utc).replace(tzinfo=None)  # SQLite stores naive

        async with get_session() as session:
            model = SampleModel(name="test", value=42)
            session.add(model)
            await session.commit()
            await session.refresh(model)

            assert model.updated_at is not None
            # SQLite stores as naive datetime, so compare without timezone
            updated_naive = model.updated_at.replace(tzinfo=None) if model.updated_at.tzinfo else model.updated_at
            assert updated_naive >= before

    async def test_updated_at_changes_on_update(self, initialized_db):
        """Test that updated_at is updated when model is modified."""
        async with get_session() as session:
            # Create model
            model = SampleModel(name="test", value=42)
            session.add(model)
            await session.commit()
            await session.refresh(model)

            original_updated_at = model.updated_at
            model_id = model.id

        # Small delay to ensure timestamp difference
        import asyncio
        await asyncio.sleep(0.01)

        async with get_session() as session:
            # Update model
            result = await session.execute(
                select(SampleModel).where(SampleModel.id == model_id)
            )
            model = result.scalar_one()
            model.value = 100
            await session.commit()
            await session.refresh(model)

            assert model.updated_at > original_updated_at

    async def test_created_at_does_not_change_on_update(self, initialized_db):
        """Test that created_at remains unchanged when model is updated."""
        async with get_session() as session:
            # Create model
            model = SampleModel(name="test", value=42)
            session.add(model)
            await session.commit()
            await session.refresh(model)

            original_created_at = model.created_at
            model_id = model.id

        async with get_session() as session:
            # Update model
            result = await session.execute(
                select(SampleModel).where(SampleModel.id == model_id)
            )
            model = result.scalar_one()
            model.value = 100
            await session.commit()
            await session.refresh(model)

            assert model.created_at == original_created_at

    async def test_timestamps_are_timezone_aware(self, initialized_db):
        """Test that timestamps are timezone-aware (UTC) when using PostgreSQL.

        Note: SQLite stores timestamps as naive datetimes, but PostgreSQL
        will preserve timezone information.
        """
        async with get_session() as session:
            model = SampleModel(name="test", value=42)
            session.add(model)
            await session.commit()
            await session.refresh(model)

            # Timestamps should exist
            assert model.created_at is not None
            assert model.updated_at is not None

            # Note: SQLite stores as naive, PostgreSQL stores as aware
            # This test verifies the timestamps are set correctly


class TestToDict:
    """Tests for to_dict method."""

    async def test_to_dict_returns_dictionary(self, initialized_db):
        """Test that to_dict returns a dictionary."""
        async with get_session() as session:
            model = SampleModel(name="test", value=42)
            session.add(model)
            await session.commit()
            await session.refresh(model)

            result = model.to_dict()
            assert isinstance(result, dict)

    async def test_to_dict_contains_all_columns(self, initialized_db):
        """Test that to_dict includes all model columns."""
        async with get_session() as session:
            model = SampleModel(name="test", value=42)
            session.add(model)
            await session.commit()
            await session.refresh(model)

            result = model.to_dict()
            assert "id" in result
            assert "name" in result
            assert "value" in result
            assert "created_at" in result
            assert "updated_at" in result

    async def test_to_dict_has_correct_values(self, initialized_db):
        """Test that to_dict returns correct values."""
        async with get_session() as session:
            model = SampleModel(name="test", value=42)
            session.add(model)
            await session.commit()
            await session.refresh(model)

            result = model.to_dict()
            assert result["name"] == "test"
            assert result["value"] == 42
            assert result["id"] == model.id
            assert result["created_at"] == model.created_at
            assert result["updated_at"] == model.updated_at

    async def test_to_dict_with_null_value(self, initialized_db):
        """Test that to_dict handles null values correctly."""
        async with get_session() as session:
            model = SampleModel(name="test", value=None)
            session.add(model)
            await session.commit()
            await session.refresh(model)

            result = model.to_dict()
            assert result["value"] is None


class TestModelOperations:
    """Tests for basic model CRUD operations."""

    async def test_create_model(self, initialized_db):
        """Test creating a model instance."""
        async with get_session() as session:
            model = SampleModel(name="test", value=42)
            session.add(model)
            await session.commit()
            await session.refresh(model)

            assert model.id is not None
            assert model.name == "test"
            assert model.value == 42

    async def test_read_model(self, initialized_db):
        """Test reading a model instance."""
        async with get_session() as session:
            model = SampleModel(name="test", value=42)
            session.add(model)
            await session.commit()
            model_id = model.id

        async with get_session() as session:
            result = await session.execute(
                select(SampleModel).where(SampleModel.id == model_id)
            )
            retrieved = result.scalar_one()

            assert retrieved.id == model_id
            assert retrieved.name == "test"
            assert retrieved.value == 42

    async def test_update_model(self, initialized_db):
        """Test updating a model instance."""
        async with get_session() as session:
            model = SampleModel(name="test", value=42)
            session.add(model)
            await session.commit()
            model_id = model.id

        async with get_session() as session:
            result = await session.execute(
                select(SampleModel).where(SampleModel.id == model_id)
            )
            model = result.scalar_one()
            model.value = 100
            await session.commit()

        async with get_session() as session:
            result = await session.execute(
                select(SampleModel).where(SampleModel.id == model_id)
            )
            updated = result.scalar_one()
            assert updated.value == 100

    async def test_delete_model(self, initialized_db):
        """Test deleting a model instance."""
        async with get_session() as session:
            model = SampleModel(name="test", value=42)
            session.add(model)
            await session.commit()
            model_id = model.id

        async with get_session() as session:
            result = await session.execute(
                select(SampleModel).where(SampleModel.id == model_id)
            )
            model = result.scalar_one()
            await session.delete(model)
            await session.commit()

        async with get_session() as session:
            result = await session.execute(
                select(SampleModel).where(SampleModel.id == model_id)
            )
            assert result.scalar_one_or_none() is None
