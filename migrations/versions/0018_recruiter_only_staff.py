"""MVP has two roles: recruiter (staff) and applicant (own table). Former admin/hiring_manager become recruiter."""

from alembic import op

revision = "0018_recruiter_only_staff"
down_revision = "0017_applicant_accounts"
branch_labels = None
depends_on = None

DROP_ROLE_CHECKS = """
    DO $$
    DECLARE name text;
    BEGIN
        FOR name IN
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'users'::regclass AND contype = 'c' AND pg_get_constraintdef(oid) LIKE '%role%'
        LOOP
            EXECUTE format('ALTER TABLE users DROP CONSTRAINT %I', name);
        END LOOP;
    END $$
"""


def upgrade() -> None:
    op.execute(DROP_ROLE_CHECKS)
    op.execute("UPDATE users SET role = 'recruiter' WHERE role <> 'recruiter'")
    op.execute("ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role = 'recruiter')")


def downgrade() -> None:
    # Former roles are not restored; every account stays recruiter.
    op.execute(DROP_ROLE_CHECKS)
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('admin', 'recruiter', 'hiring_manager'))"
    )
