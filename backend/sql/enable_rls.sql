-- UrbanPulse: Enable Row Level Security (RLS) on all public schema tables
-- This blocks Supabase's public PostgREST API (anon & authenticated roles) from direct table access
-- while allowing the backend FastAPI service role / direct PostgreSQL connection to function normally.

-- 1. Enable RLS on core tables
ALTER TABLE IF EXISTS public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.complaints ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.complaint_contacts ENABLE ROW LEVEL SECURITY;

-- 2. Enable RLS on construction tables
ALTER TABLE IF EXISTS public.construction_work_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.construction_ward_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.construction_cluster_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.construction_metadata ENABLE ROW LEVEL SECURITY;

-- 3. Enable RLS on crime tables
ALTER TABLE IF EXISTS public.crime_historical ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.crime_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.crime_category_year_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.crime_metadata ENABLE ROW LEVEL SECURITY;

-- 4. Enable RLS on police tables
ALTER TABLE IF EXISTS public.police_locations ENABLE ROW LEVEL SECURITY;

-- 5. Enable RLS on ESG tables
ALTER TABLE IF EXISTS public.esg_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.esg_air_stations ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.esg_carbon_emissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.esg_water_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.esg_electricity ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.esg_air_live ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.esg_update_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.esg_recalc_log ENABLE ROW LEVEL SECURITY;

-- Dynamic safeguard: Enable RLS on any remaining tables in public schema
DO $$
DECLARE
    tbl record;
BEGIN
    FOR tbl IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename NOT IN ('alembic_version', 'spatial_ref_sys')
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', tbl.tablename);
    END LOOP;
END
$$;
