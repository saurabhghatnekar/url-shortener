"""Change API key to encrypted format

Revision ID: 1e3c7ce27467
Revises: 1a21b073af51
Create Date: 2025-03-08 13:16:28.283029

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
import base64
from cryptography.fernet import Fernet


# revision identifiers, used by Alembic.
revision = '1e3c7ce27467'
down_revision = '1a21b073af51'
branch_labels = None
depends_on = None


# Use a fixed key for migration to ensure consistency
SECRET_KEY = b'cThIIoDvpK8fCZSZlOveI7eVQYBRDYHWUUZCraMJwT4='

def encrypt_api_key(key):
    """Encrypt an API key."""
    cipher_suite = Fernet(SECRET_KEY)
    return cipher_suite.encrypt(key.encode())

def upgrade():
    # Step 1: Add encrypted_key column as nullable initially
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.add_column(sa.Column('encrypted_key', sa.LargeBinary(), nullable=True))
    
    # Step 2: Migrate data - encrypt existing keys
    bind = op.get_bind()
    session = Session(bind=bind)
    
    # Get all API keys
    api_keys = session.execute(sa.text('SELECT id, key FROM api_keys')).fetchall()
    
    # Encrypt each key and update the record
    for api_key in api_keys:
        encrypted = encrypt_api_key(api_key.key)
        session.execute(
            sa.text('UPDATE api_keys SET encrypted_key = :encrypted WHERE id = :id'),
            {'encrypted': encrypted, 'id': api_key.id}
        )
    
    session.commit()
    
    # Step 3: Make encrypted_key not nullable and drop the old key column
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.alter_column('encrypted_key', nullable=False)
        batch_op.drop_constraint('api_keys_key_key', type_='unique')
        batch_op.create_unique_constraint(None, ['encrypted_key'])
        batch_op.drop_column('key')

    # ### end Alembic commands ###


def decrypt_api_key(encrypted_key):
    """Decrypt an API key."""
    cipher_suite = Fernet(SECRET_KEY)
    return cipher_suite.decrypt(encrypted_key).decode()

def downgrade():
    # Step 1: Add key column as nullable initially
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.add_column(sa.Column('key', sa.VARCHAR(length=32), nullable=True))
    
    # Step 2: Migrate data - decrypt existing keys
    bind = op.get_bind()
    session = Session(bind=bind)
    
    # Get all API keys
    api_keys = session.execute(sa.text('SELECT id, encrypted_key FROM api_keys')).fetchall()
    
    # Decrypt each key and update the record
    for api_key in api_keys:
        try:
            decrypted = decrypt_api_key(api_key.encrypted_key)
            session.execute(
                sa.text('UPDATE api_keys SET key = :decrypted WHERE id = :id'),
                {'decrypted': decrypted, 'id': api_key.id}
            )
        except Exception as e:
            print(f"Error decrypting key for id {api_key.id}: {str(e)}")
    
    session.commit()
    
    # Step 3: Make key not nullable and drop the encrypted column
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.alter_column('key', nullable=False)
        batch_op.drop_constraint(None, type_='unique')
        batch_op.create_unique_constraint('api_keys_key_key', ['key'])
        batch_op.drop_column('encrypted_key')

    # ### end Alembic commands ###
