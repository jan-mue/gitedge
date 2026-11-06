-- One-time recovery for databases left at the removed RBAC/PAT revision.
-- Run against the affected database only; this is not an application migration.
-- Archive legacy feature data and restore main's migration marker atomically.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

DO $$
DECLARE
    legacy_table text;
BEGIN
    LOCK TABLE public.alembic_version IN EXCLUSIVE MODE;
    IF (SELECT count(*) FROM public.alembic_version) <> 1
        OR NOT EXISTS (
            SELECT 1 FROM public.alembic_version WHERE version_num = '05b106a4cc76'
        ) THEN
        RAISE EXCEPTION 'Recovery requires exactly revision 05b106a4cc76; database unchanged';
    END IF;

    -- Both removed feature migrations only added these tables after c45f8528cc79.
    -- Refuse an unexpected schema rather than guessing which migrations ran.
    FOREACH legacy_table IN ARRAY ARRAY[
        'organization_member', 'team', 'team_member',
        'repository_collaborator', 'personal_access_token'
    ] LOOP
        IF to_regclass(format('public.%I', legacy_table)) IS NULL THEN
            RAISE EXCEPTION 'Expected legacy table % is missing; database unchanged', legacy_table;
        END IF;
    END LOOP;
    IF to_regclass('public.casbin_rule') IS NOT NULL THEN
        RAISE EXCEPTION 'Casbin policies already exist; database unchanged';
    END IF;

    -- CREATE fails if this recovery has already been used or the name is occupied.
    CREATE SCHEMA gitedge_rbac_archive_20261106;
    FOREACH legacy_table IN ARRAY ARRAY[
        'organization_member', 'team', 'team_member',
        'repository_collaborator', 'personal_access_token'
    ] LOOP
        EXECUTE format(
            'ALTER TABLE public.%I SET SCHEMA gitedge_rbac_archive_20261106', legacy_table
        );
    END LOOP;
    UPDATE public.alembic_version SET version_num = 'c45f8528cc79';
END;
$$;

COMMIT;
