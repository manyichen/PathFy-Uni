"""seed default system settings and replace retired DeepSeek models

Revision ID: 20260715_0005
Revises: 20260715_0004
"""

from __future__ import annotations

import json

from alembic import op

from app.domains.settings.defaults_v1 import DEFAULT_SETTINGS_V1

revision = "20260715_0005"
down_revision = "20260715_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    defaults_json = json.dumps(DEFAULT_SETTINGS_V1, ensure_ascii=False, separators=(",", ":"))
    # SQLAlchemy TextClause treats ``:name`` inside raw SQL as a bind marker;
    # escape JSON colons so both online and ``alembic --sql`` modes preserve it.
    defaults_json = defaults_json.replace("'", "''").replace(":", r"\:")
    op.execute(f"""
        INSERT INTO system_setting_revisions (revision, settings_json, created_by)
        SELECT 1, '{defaults_json}', NULL
        FROM system_setting_state s
        WHERE s.id=1 AND s.current_revision_id IS NULL
    """)
    op.execute("""
        UPDATE system_setting_state s
        SET s.current_revision_id=(SELECT r.id FROM system_setting_revisions r WHERE r.revision=1)
        WHERE s.id=1 AND s.current_revision_id IS NULL
    """)
    op.execute("""
        INSERT INTO system_setting_revisions (revision, settings_json, created_by)
        SELECT r.revision + 1,
               JSON_SET(
                 r.settings_json,
                 '$.MATCH_DEEPSEEK_MODEL',
                   CASE JSON_UNQUOTE(JSON_EXTRACT(r.settings_json,'$.MATCH_DEEPSEEK_MODEL'))
                     WHEN 'deepseek-reasoner' THEN 'deepseek-v4-pro'
                     WHEN 'deepseek-chat' THEN 'deepseek-v4-flash'
                     ELSE JSON_UNQUOTE(JSON_EXTRACT(r.settings_json,'$.MATCH_DEEPSEEK_MODEL')) END,
                 '$.CAREER_DEEPSEEK_MODEL',
                   CASE JSON_UNQUOTE(JSON_EXTRACT(r.settings_json,'$.CAREER_DEEPSEEK_MODEL'))
                     WHEN 'deepseek-reasoner' THEN 'deepseek-v4-pro'
                     WHEN 'deepseek-chat' THEN 'deepseek-v4-pro'
                     ELSE JSON_UNQUOTE(JSON_EXTRACT(r.settings_json,'$.CAREER_DEEPSEEK_MODEL')) END,
                 '$.GRAPH_CAP_PRIMARY_MODEL',
                   CASE JSON_UNQUOTE(JSON_EXTRACT(r.settings_json,'$.GRAPH_CAP_PRIMARY_MODEL'))
                     WHEN 'deepseek-reasoner' THEN 'deepseek-v4-pro'
                     WHEN 'deepseek-chat' THEN 'deepseek-v4-flash'
                     ELSE JSON_UNQUOTE(JSON_EXTRACT(r.settings_json,'$.GRAPH_CAP_PRIMARY_MODEL')) END
               ),
               NULL
        FROM system_setting_state s
        JOIN system_setting_revisions r ON r.id=s.current_revision_id
        WHERE s.id=1 AND (
          JSON_UNQUOTE(JSON_EXTRACT(r.settings_json,'$.MATCH_DEEPSEEK_MODEL')) IN ('deepseek-chat','deepseek-reasoner') OR
          JSON_UNQUOTE(JSON_EXTRACT(r.settings_json,'$.CAREER_DEEPSEEK_MODEL')) IN ('deepseek-chat','deepseek-reasoner') OR
          JSON_UNQUOTE(JSON_EXTRACT(r.settings_json,'$.GRAPH_CAP_PRIMARY_MODEL')) IN ('deepseek-chat','deepseek-reasoner')
        )
    """)
    op.execute("""
        UPDATE system_setting_state s
        SET s.current_revision_id=(SELECT r.id FROM system_setting_revisions r ORDER BY r.revision DESC LIMIT 1)
        WHERE s.id=1
    """)


def downgrade() -> None:
    # Settings revisions are immutable. The subsequent 0004 downgrade drops
    # these tables, so this data migration intentionally does not rewrite them.
    pass
