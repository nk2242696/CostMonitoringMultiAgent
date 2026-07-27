"""Add region column to azure_costs

Revision ID: 002_add_region
Revises: 001
Create Date: 2025-11-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_region'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    """Add region column and backfill from resource_id"""
    # Add region column
    op.add_column('azure_costs', sa.Column('region', sa.String(50), nullable=True))
    
    # Add resource_location column for more detailed location info
    op.add_column('azure_costs', sa.Column('resource_location', sa.String(50), nullable=True))
    
    # Create index for region
    op.create_index('idx_costs_region', 'azure_costs', ['region'])
    
    # Backfill region from resource_id using SQL
    op.execute("""
        UPDATE azure_costs 
        SET region = LOWER(
            SUBSTRING(resource_id FROM '/locations/([^/]+)')
        )
        WHERE resource_id IS NOT NULL 
        AND resource_id LIKE '%/locations/%'
    """)
    
    # Also try to extract from resource group pattern (common naming convention)
    op.execute("""
        UPDATE azure_costs 
        SET region = CASE
            WHEN LOWER(resource_group) LIKE '%eastus2%' THEN 'eastus2'
            WHEN LOWER(resource_group) LIKE '%eastus%' THEN 'eastus'
            WHEN LOWER(resource_group) LIKE '%westus3%' THEN 'westus3'
            WHEN LOWER(resource_group) LIKE '%westus2%' THEN 'westus2'
            WHEN LOWER(resource_group) LIKE '%westus%' THEN 'westus'
            WHEN LOWER(resource_group) LIKE '%centralus%' THEN 'centralus'
            WHEN LOWER(resource_group) LIKE '%northcentralus%' THEN 'northcentralus'
            WHEN LOWER(resource_group) LIKE '%southcentralus%' THEN 'southcentralus'
            WHEN LOWER(resource_group) LIKE '%westeurope%' THEN 'westeurope'
            WHEN LOWER(resource_group) LIKE '%northeurope%' THEN 'northeurope'
            ELSE 'unknown'
        END
        WHERE region IS NULL
    """)


def downgrade():
    """Remove region columns"""
    op.drop_index('idx_costs_region', table_name='azure_costs')
    op.drop_column('azure_costs', 'resource_location')
    op.drop_column('azure_costs', 'region')
