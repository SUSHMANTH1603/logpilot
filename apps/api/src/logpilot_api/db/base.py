"""SQLAlchemy DeclarativeBase and metadata configuration."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Standard constraint naming convention for consistent migrations (PostgreSQL)
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """Base declarative class for all LogPilot relational models."""

    metadata = metadata


from logpilot_api.modules.analysis.models import AnomalySignal  # noqa: F401, E402
from logpilot_api.modules.identity.models import User  # noqa: F401, E402
from logpilot_api.modules.incidents.models import (  # noqa: F401, E402
    Incident,
    IncidentEvent,
)
from logpilot_api.modules.ingestion.models import (  # noqa: F401, E402
    IngestionRun,
    LogEvent,
    LogSource,
    LogTemplate,
)
from logpilot_api.modules.projects.models import Project, ProjectMembership  # noqa: F401, E402
