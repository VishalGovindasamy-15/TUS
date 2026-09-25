"""Initial schema — creates all tables from the SQLAlchemy metadata."""

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op  # noqa: E402
from app.db import Base  # noqa: E402
import app.models  # noqa: E402,F401


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
