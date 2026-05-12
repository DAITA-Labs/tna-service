"""Service deployment environment."""
from enum import Enum


class Environment(str, Enum):
    """The four valid app environments. Drives env-file layering and
    environment-aware behavior (logging format, defaults, etc.)."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"
