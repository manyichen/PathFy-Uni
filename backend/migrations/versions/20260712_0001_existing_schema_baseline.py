"""Baseline the schema previously managed by schema.sql and migrations 002-007."""

revision = "20260712_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing installations are verified and stamped; no DDL is repeated.
    pass


def downgrade() -> None:
    # A baseline stamp has no schema operation to reverse.
    pass
