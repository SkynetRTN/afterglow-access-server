"""Add user settings"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2'
down_revision = '1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
            'users', recreate='always',
            table_args=(
                sa.CheckConstraint(
                    'username is null or length(username) <= 255'),
                sa.CheckConstraint('email is null or length(email) <= 255'),
                sa.CheckConstraint(
                    'password is null or length(password) <= 255'),
                sa.CheckConstraint(
                    'auth_methods is null or length(auth_methods) <= 255'),
                sa.CheckConstraint(
                    'settings is null or length(settings) <= 1048576'),
            ),
            table_kwargs=dict(sqlite_autoincrement=True)) as batch_op:
        batch_op.add_column(sa.Column('settings', sa.String, default=''))

    with op.batch_alter_table(
            'roles', recreate='always',
            table_args=(
                sa.CheckConstraint('length(name) <= 80'),
                sa.CheckConstraint(
                    'description is null or length(description) <= 255'),
            )):
        pass

    with op.batch_alter_table(
            'user_oauth_clients', recreate='always',
            table_args=(
                sa.CheckConstraint('length(client_id) <= 40'),
            )):
        pass


def downgrade():
    with op.batch_alter_table('user_oauth_clients', recreate='always'):
        pass

    with op.batch_alter_table('roles', recreate='always'):
        pass

    with op.batch_alter_table('users', recreate='always') as batch_op:
        batch_op.drop_column('settings')
