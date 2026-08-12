"""
Import point that registers every ORM model on `Base.metadata`.

This module is imported ONLY by Alembic's `env.py` (and by tests that need
to `create_all`) — never by `app/db/base.py` itself, to avoid a circular
import between `db.base` and `models.*` (each model imports `Base` from
`db.base`). Any new model must be added to `app/models/__init__.py`, which
is imported here.
"""
from app.db.base import Base  # noqa: F401
from app.models import RefreshToken, User  # noqa: F401
