"""baseline_migration

Revision ID: 05fc282b8768
Revises: 
Create Date: 2026-10-07 21:45:30.403462

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05fc282b8768'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # Complaints
    op.create_table(
        'complaints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.String(length=32), nullable=False),
        sa.Column('secret_hash', sa.String(length=64), nullable=True),
        sa.Column('user_id', sa.String(length=100), nullable=True),
        sa.Column('is_identity_hidden', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('pseudonym', sa.String(length=100), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=2000), nullable=False),
        sa.Column('location', sa.String(length=300), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_complaints_id'), 'complaints', ['id'], unique=False)
    op.create_index(op.f('ix_complaints_ticket_id'), 'complaints', ['ticket_id'], unique=True)
    op.create_index(op.f('ix_complaints_user_id'), 'complaints', ['user_id'], unique=False)

    # Complaint Contacts (Separate table for anonymous/contact data)
    op.create_table(
        'complaint_contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('contact', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_complaint_contacts_complaint_id'), 'complaint_contacts', ['complaint_id'], unique=True)
    op.create_index(op.f('ix_complaint_contacts_id'), 'complaint_contacts', ['id'], unique=False)

    # Construction work orders
    op.create_table(
        'construction_work_orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slno', sa.Integer(), nullable=True),
        sa.Column('work_order_id', sa.String(length=50), nullable=True),
        sa.Column('ward', sa.String(length=50), nullable=False),
        sa.Column('wodetails', sa.Text(), nullable=False),
        sa.Column('contractor', sa.String(length=255), nullable=True),
        sa.Column('brnumber', sa.String(length=255), nullable=True),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('nett', sa.BigInteger(), nullable=False),
        sa.Column('deduction', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_construction_work_orders_contractor'), 'construction_work_orders', ['contractor'], unique=False)
    op.create_index(op.f('ix_construction_work_orders_id'), 'construction_work_orders', ['id'], unique=False)
    op.create_index(op.f('ix_construction_work_orders_slno'), 'construction_work_orders', ['slno'], unique=False)
    op.create_index(op.f('ix_construction_work_orders_ward'), 'construction_work_orders', ['ward'], unique=False)
    op.create_index(op.f('ix_construction_work_orders_work_order_id'), 'construction_work_orders', ['work_order_id'], unique=False)

    # Construction ward summaries
    op.create_table(
        'construction_ward_summaries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ward', sa.String(length=50), nullable=False),
        sa.Column('total_work_orders', sa.Integer(), nullable=False),
        sa.Column('total_amount', sa.BigInteger(), nullable=False),
        sa.Column('avg_project_amount', sa.Float(), nullable=False),
        sa.Column('total_net_expenditure', sa.BigInteger(), nullable=False),
        sa.Column('avg_net_amount', sa.Float(), nullable=False),
        sa.Column('total_deduction', sa.BigInteger(), nullable=False),
        sa.Column('avg_deduction', sa.Float(), nullable=False),
        sa.Column('unique_contractors', sa.Integer(), nullable=False),
        sa.Column('drain_projects', sa.Integer(), nullable=True),
        sa.Column('road_projects', sa.Integer(), nullable=True),
        sa.Column('maintenance_projects', sa.Integer(), nullable=True),
        sa.Column('development_projects', sa.Integer(), nullable=True),
        sa.Column('water_projects', sa.Integer(), nullable=True),
        sa.Column('cluster', sa.Integer(), nullable=True),
        sa.Column('cluster_name', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_construction_ward_summaries_cluster'), 'construction_ward_summaries', ['cluster'], unique=False)
    op.create_index(op.f('ix_construction_ward_summaries_id'), 'construction_ward_summaries', ['id'], unique=False)
    op.create_index(op.f('ix_construction_ward_summaries_ward'), 'construction_ward_summaries', ['ward'], unique=True)

    # Construction cluster stats
    op.create_table(
        'construction_cluster_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster', sa.Integer(), nullable=False),
        sa.Column('cluster_name', sa.String(length=100), nullable=False),
        sa.Column('ward_count', sa.Integer(), nullable=False),
        sa.Column('avg_work_orders', sa.Float(), nullable=False),
        sa.Column('avg_total_amount', sa.Float(), nullable=False),
        sa.Column('avg_net_expenditure', sa.Float(), nullable=False),
        sa.Column('avg_deduction', sa.Float(), nullable=False),
        sa.Column('avg_contractors', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cluster')
    )
    op.create_index(op.f('ix_construction_cluster_stats_id'), 'construction_cluster_stats', ['id'], unique=False)

    # Construction metadata
    op.create_table(
        'construction_metadata',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('key')
    )
    op.create_index(op.f('ix_construction_metadata_key'), 'construction_metadata', ['key'], unique=False)

    # Crime historical
    op.create_table(
        'crime_historical',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('period_label', sa.String(length=100), nullable=False),
        sa.Column('total_crimes', sa.Integer(), nullable=False),
        sa.Column('fatal_crimes', sa.Integer(), nullable=False),
        sa.Column('non_fatal_crimes', sa.Integer(), nullable=False),
        sa.Column('fatal_percentage', sa.Float(), nullable=False),
        sa.Column('highest_risk_year', sa.Integer(), nullable=False),
        sa.Column('highest_risk_score', sa.Float(), nullable=False),
        sa.Column('highest_risk_level', sa.String(length=50), nullable=False),
        sa.Column('highest_risk_volume_score', sa.Float(), nullable=False),
        sa.Column('highest_risk_severity_score', sa.Float(), nullable=False),
        sa.Column('volume_weight', sa.Float(), nullable=True),
        sa.Column('severity_weight', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_crime_historical_id'), 'crime_historical', ['id'], unique=False)

    # Crime records
    op.create_table(
        'crime_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('year', sa.String(length=10), nullable=False),
        sa.Column('item_name', sa.String(length=200), nullable=False),
        sa.Column('reported', sa.Integer(), nullable=True),
        sa.Column('detected', sa.Integer(), nullable=True),
        sa.Column('detection_pct', sa.Float(), nullable=True),
        sa.Column('male', sa.Integer(), nullable=True),
        sa.Column('female', sa.Integer(), nullable=True),
        sa.Column('total', sa.Integer(), nullable=True),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_crime_records_category'), 'crime_records', ['category'], unique=False)
    op.create_index(op.f('ix_crime_records_id'), 'crime_records', ['id'], unique=False)
    op.create_index(op.f('ix_crime_records_year'), 'crime_records', ['year'], unique=False)

    # Crime category year summaries
    op.create_table(
        'crime_category_year_summaries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('year', sa.String(length=10), nullable=False),
        sa.Column('total_reported', sa.Integer(), nullable=True),
        sa.Column('total_detected', sa.Integer(), nullable=True),
        sa.Column('overall_detection_pct', sa.Float(), nullable=True),
        sa.Column('total_suicides', sa.Integer(), nullable=True),
        sa.Column('total_accidental_deaths', sa.Integer(), nullable=True),
        sa.Column('total_male', sa.Integer(), nullable=True),
        sa.Column('total_female', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_crime_category_year_summaries_category'), 'crime_category_year_summaries', ['category'], unique=False)
    op.create_index(op.f('ix_crime_category_year_summaries_id'), 'crime_category_year_summaries', ['id'], unique=False)
    op.create_index(op.f('ix_crime_category_year_summaries_year'), 'crime_category_year_summaries', ['year'], unique=False)

    # Crime metadata
    op.create_table(
        'crime_metadata',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('key')
    )
    op.create_index(op.f('ix_crime_metadata_key'), 'crime_metadata', ['key'], unique=False)

    # Police locations
    op.create_table(
        'police_locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('location_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('source', sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_police_locations_category'), 'police_locations', ['category'], unique=False)
    op.create_index(op.f('ix_police_locations_id'), 'police_locations', ['id'], unique=False)
    op.create_index(op.f('ix_police_locations_location_code'), 'police_locations', ['location_code'], unique=True)

    # ESG Sources
    op.create_table(
        'esg_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=60), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('publisher', sa.String(length=300), nullable=True),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('doi', sa.Text(), nullable=True),
        sa.Column('period', sa.String(length=60), nullable=True),
        sa.Column('location', sa.String(length=300), nullable=True),
        sa.Column('geographic_level', sa.String(length=300), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_esg_sources_code'), 'esg_sources', ['code'], unique=True)
    op.create_index(op.f('ix_esg_sources_id'), 'esg_sources', ['id'], unique=False)

    # ESG Air Stations
    op.create_table(
        'esg_air_stations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=20), nullable=True),
        sa.Column('year', sa.String(length=20), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('so2', sa.Float(), nullable=True),
        sa.Column('no2', sa.Float(), nullable=True),
        sa.Column('pm10', sa.Float(), nullable=True),
        sa.Column('pm25', sa.Float(), nullable=True),
        sa.Column('nh3', sa.Float(), nullable=True),
        sa.Column('lead', sa.Float(), nullable=True),
        sa.Column('co', sa.Float(), nullable=True),
        sa.Column('aqi', sa.Float(), nullable=True),
        sa.Column('source_code', sa.String(length=60), nullable=False),
        sa.Column('source_name', sa.String(length=300), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('data_year', sa.String(length=80), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('verification_status', sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_esg_air_stations_code'), 'esg_air_stations', ['code'], unique=True)
    op.create_index(op.f('ix_esg_air_stations_id'), 'esg_air_stations', ['id'], unique=False)

    # ESG Carbon Emissions
    op.create_table(
        'esg_carbon_emissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('sector', sa.String(length=200), nullable=False),
        sa.Column('mmt_co2e', sa.Float(), nullable=True),
        sa.Column('share_pct', sa.Float(), nullable=True),
        sa.Column('is_derived', sa.Boolean(), nullable=True),
        sa.Column('boundary', sa.String(length=100), nullable=True),
        sa.Column('source_code', sa.String(length=60), nullable=False),
        sa.Column('source_name', sa.String(length=300), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('data_year', sa.String(length=80), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('verification_status', sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_esg_carbon_emissions_id'), 'esg_carbon_emissions', ['id'], unique=False)
    op.create_index(op.f('ix_esg_carbon_emissions_year'), 'esg_carbon_emissions', ['year'], unique=False)

    # ESG Water Readings
    op.create_table(
        'esg_water_readings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('station_code', sa.String(length=20), nullable=False),
        sa.Column('station_name', sa.String(length=200), nullable=False),
        sa.Column('district', sa.String(length=200), nullable=True),
        sa.Column('region', sa.String(length=50), nullable=True),
        sa.Column('month', sa.String(length=10), nullable=False),
        sa.Column('wq_class', sa.String(length=2), nullable=True),
        sa.Column('wqi_status', sa.String(length=2), nullable=True),
        sa.Column('source_code', sa.String(length=60), nullable=False),
        sa.Column('source_name', sa.String(length=300), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('data_year', sa.String(length=80), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('verification_status', sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_esg_water_readings_id'), 'esg_water_readings', ['id'], unique=False)
    op.create_index(op.f('ix_esg_water_readings_region'), 'esg_water_readings', ['region'], unique=False)
    op.create_index(op.f('ix_esg_water_readings_station_code'), 'esg_water_readings', ['station_code'], unique=False)

    # ESG Electricity
    op.create_table(
        'esg_electricity',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('area', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('year', sa.String(length=20), nullable=False),
        sa.Column('value_lakh_units', sa.Float(), nullable=False),
        sa.Column('source_code', sa.String(length=60), nullable=False),
        sa.Column('source_name', sa.String(length=300), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('data_year', sa.String(length=80), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('verification_status', sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_esg_electricity_id'), 'esg_electricity', ['id'], unique=False)

    # ESG Air Live
    op.create_table(
        'esg_air_live',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('station', sa.String(length=300), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('pollutant_id', sa.String(length=30), nullable=False),
        sa.Column('pollutant_min', sa.Float(), nullable=True),
        sa.Column('pollutant_avg', sa.Float(), nullable=True),
        sa.Column('pollutant_max', sa.Float(), nullable=True),
        sa.Column('observed_at', sa.DateTime(), nullable=False),
        sa.Column('source_name', sa.String(length=300), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('data_year', sa.String(length=80), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('verification_status', sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('station', 'pollutant_id', 'observed_at', name='uq_esg_air_live')
    )
    op.create_index(op.f('ix_esg_air_live_id'), 'esg_air_live', ['id'], unique=False)
    op.create_index(op.f('ix_esg_air_live_observed_at'), 'esg_air_live', ['observed_at'], unique=False)
    op.create_index(op.f('ix_esg_air_live_pollutant_id'), 'esg_air_live', ['pollutant_id'], unique=False)
    op.create_index(op.f('ix_esg_air_live_station'), 'esg_air_live', ['station'], unique=False)

    # ESG Update Runs
    op.create_table(
        'esg_update_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job', sa.String(length=30), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('fetched', sa.Integer(), nullable=True),
        sa.Column('inserted', sa.Integer(), nullable=True),
        sa.Column('updated', sa.Integer(), nullable=True),
        sa.Column('unchanged', sa.Integer(), nullable=True),
        sa.Column('data_hash', sa.String(length=64), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_esg_update_runs_id'), 'esg_update_runs', ['id'], unique=False)
    op.create_index(op.f('ix_esg_update_runs_job'), 'esg_update_runs', ['job'], unique=False)

    # ESG Recalc Log
    op.create_table(
        'esg_recalc_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('triggered_at', sa.DateTime(), nullable=False),
        sa.Column('data_version', sa.String(length=64), nullable=False),
        sa.Column('previous_version', sa.String(length=64), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_esg_recalc_log_id'), 'esg_recalc_log', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('esg_recalc_log')
    op.drop_table('esg_update_runs')
    op.drop_table('esg_air_live')
    op.drop_table('esg_electricity')
    op.drop_table('esg_water_readings')
    op.drop_table('esg_carbon_emissions')
    op.drop_table('esg_air_stations')
    op.drop_table('esg_sources')
    op.drop_table('police_locations')
    op.drop_table('crime_metadata')
    op.drop_table('crime_category_year_summaries')
    op.drop_table('crime_records')
    op.drop_table('crime_historical')
    op.drop_table('construction_metadata')
    op.drop_table('construction_cluster_stats')
    op.drop_table('construction_ward_summaries')
    op.drop_table('construction_work_orders')
    op.drop_table('complaint_contacts')
    op.drop_table('complaints')
    op.drop_table('users')
