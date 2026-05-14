"""Define the four deployment environments and their invariants."""
from enum import Enum


class Environment(str, Enum):
    """An enum of valid app deployment environments: development, staging, production, or test."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"
