"""Exact initialized-target preflight; no connection or DDL during import."""

from sqlalchemy import text
from sqlalchemy.engine import Connection

OLD_REVISION = 's2b01_0001'
NEW_REVISION = 's2c03_0001'


def local_identity(connection: Connection, database: str):
    url = connection.engine.url
    if (database not in ('stylometry_dev', 'stylometry_test') or url.database != database
            or url.drivername != 'postgresql+psycopg' or url.query
            or url.host not in ('localhost', '127.0.0.1', '::1')):
        raise ValueError('Migration target refused.')
    if (not connection.in_transaction()
            or connection.connection.driver_connection.autocommit is not False):
        raise ValueError('A real PostgreSQL transaction is required.')
    actual = connection.execute(text('SELECT current_database(), inet_server_addr()::text, inet_server_port(), current_schema(), current_schemas(false), pg_my_temp_schema()')).one()
    if (actual[0] != database or actual[1] not in ('127.0.0.1', '127.0.0.1/32', '::1', '::1/128')
            or actual[2] != (url.port or 5432) or actual[3] != 'public'
            or actual[4] != ['public'] or actual[5] != 0):
        raise ValueError('Migration identity refused.')


CATALOG_QUERIES = {
    'schemas': "SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname <> 'information_schema' ORDER BY 1",
    'extensions': 'SELECT extname, extversion FROM pg_extension ORDER BY 1',
    'event_triggers': 'SELECT evtname, evtevent, evtenabled FROM pg_event_trigger ORDER BY 1',
    'relations': "SELECT c.relname,c.relkind::text,c.relpersistence::text,c.relrowsecurity,c.relforcerowsecurity,c.relispartition,c.reloptions FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY 1",
    'columns': "SELECT c.relname,a.attname,a.attnum,format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity::text,a.attgenerated::text,a.attisdropped,co.collname,pg_get_expr(d.adbin,d.adrelid) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum LEFT JOIN pg_collation co ON co.oid=a.attcollation WHERE n.nspname='public' AND a.attnum>0 AND c.relkind IN ('r','p','v','m','f') ORDER BY 1,3",
    'constraints': "SELECT c.relname,k.conname,k.contype::text,k.convalidated,k.condeferrable,k.condeferred,pg_get_constraintdef(k.oid,true) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY 1,2",
    'indexes': "SELECT c.relname,i.indisvalid,i.indisready,pg_get_indexdef(i.indexrelid) FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY 1,4",
    'triggers': "SELECT c.relname,t.tgname,t.tgenabled::text,pg_get_triggerdef(t.oid,true) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY 1,2",
    'policies': "SELECT tablename,policyname,permissive,roles::text,cmd,qual,with_check FROM pg_policies WHERE schemaname='public' ORDER BY 1,2",
    'routines': "SELECT p.proname,pg_get_function_identity_arguments(p.oid),p.prokind::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' ORDER BY 1,2",
    'types': "SELECT t.typname,t.typtype::text FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public' ORDER BY 1",
    'rules': "SELECT c.relname,r.rulename,pg_get_ruledef(r.oid,true) FROM pg_rewrite r JOIN pg_class c ON c.oid=r.ev_class JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY 1,2",
    'other_objects': "SELECT d.classid::regclass::text,count(*) FROM pg_depend d JOIN pg_namespace n ON d.refclassid='pg_namespace'::regclass AND d.refobjid=n.oid WHERE n.nspname='public' GROUP BY 1 ORDER BY 1",
}


def schema_evidence(connection):
    # JSON round trip normalizes DB tuples/arrays; contains no owner, paths or rows.
    from stylometry.contracts import canonical_sha256
    return {k: canonical_sha256([list(row) for row in connection.execute(text(q))])
            for k, q in CATALOG_QUERIES.items()}


def assert_initialized_upgrade(connection: Connection, *, database: str, target: str):
    """Fail closed. Caller MUST retain this transaction through the entire upgrade.

    Exact PostgreSQL catalog evidence is deliberately version-sensitive. A server
    difference requires review, never automatic regeneration of approved evidence.
    Owners/ACLs require a separate private operational preflight.
    """
    from stylometry.initial_schema_evidence import EXPECTED
    if target != NEW_REVISION or not connection.in_transaction():
        raise ValueError('Explicit successor transaction required.')
    local_identity(connection, database)
    if connection.scalar(text('SHOW server_version_num')) != '180006':
        raise ValueError('Unreviewed server catalog version; migration refused.')
    if not connection.scalar(text('SELECT pg_try_advisory_xact_lock(21302401)')):
        raise ValueError('Migration already in progress.')
    connection.execute(text("SET LOCAL lock_timeout = '2s'"))
    revision = connection.execute(text('SELECT version_num FROM public.alembic_version')).scalars().all()
    if revision != [OLD_REVISION]:
        raise ValueError('Migration revision refused.')
    # Hold existing tables against cooperating and ordinary concurrent DML/DDL.
    from stylometry.models import Base
    names = sorted((*Base.metadata.tables, 'alembic_version'))
    connection.execute(text('LOCK TABLE ' + ','.join('public.' + n for n in names) + ' IN ACCESS EXCLUSIVE MODE'))
    if schema_evidence(connection) != EXPECTED:
        raise ValueError('Unexpected schema; migration refused.')
    from stylometry.paper1 import TASKS
    expected = sorted((str(t.code), str(t.genre), str(t.form)) for t in TASKS)
    actual = [tuple(row) for row in connection.execute(text('SELECT code,genre,form FROM public.task ORDER BY code'))]
    if actual != expected:
        raise ValueError('Task definitions differ; migration refused.')
