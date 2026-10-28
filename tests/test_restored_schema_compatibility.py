"""Exact catalog compatibility, synthetic PostgreSQL fixtures rolled back only.

Reparse the nine documented original definitions to exercise PostgreSQL's actual
restore parser path without a backup, restore, cluster, or persistent migration.
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import text

from stylometry.contracts import canonical_sha256
from stylometry.initial_schema_evidence import EXPECTED
from stylometry.restored_schema_compatibility import (
    CONSTRAINT_VARIANTS, SEMANTIC_CONTEXT_QUERY, matches_restored_constraints,
)
from stylometry.upgrade_safety import (
    CATALOG_QUERIES, NEW_REVISION, assert_initialized_upgrade, schema_evidence,
)
from test_durable_operations import initialized  # noqa: F401 -- rollback fixture


def guard(connection):
    assert_initialized_upgrade(connection, database='stylometry_test', target=NEW_REVISION)


def replace_check(connection, row):
    table, name, _, _, _, _, definition = row
    # Identifiers and SQL originate only in fixed schema-only synthetic fixtures.
    connection.execute(text(f'ALTER TABLE public.{table} DROP CONSTRAINT {name}'))
    connection.execute(text(f'ALTER TABLE public.{table} ADD CONSTRAINT {name} {definition}'))


@pytest.fixture
def restored(initialized):
    rows = [tuple(row) for row in initialized.execute(text(CATALOG_QUERIES['constraints']))]
    assert len(rows) == 225
    assert canonical_sha256([list(row) for row in rows]) == EXPECTED['constraints']
    for original, alternative in CONSTRAINT_VARIANTS:
        assert original in rows
        # Reparse the emitted ORIGINAL definition, as pg_restore does. Do not
        # just insert the expected alternative into a mocked catalog result.
        replace_check(initialized, original)
    actual = [tuple(row) for row in initialized.execute(text(CATALOG_QUERIES['constraints']))]
    assert len(actual) == 225
    for _, alternative in CONSTRAINT_VARIANTS:
        assert alternative in actual
    assert {k: v for k, v in schema_evidence(initialized).items() if k != 'constraints'} == {
        k: v for k, v in EXPECTED.items() if k != 'constraints'}
    return initialized


def test_literal_ledger_matches_all_eighteen_historical_definitions():
    report = Path('docs/s2c03d-constraint-compatibility.md').read_text(encoding='utf-8')
    definitions = re.findall(r'```sql\n(.*?)\n```', report, re.S)
    assert len(CONSTRAINT_VARIANTS) == 9
    assert len({original[:2] for original, _ in CONSTRAINT_VARIANTS}) == 9
    assert [row[6] for pair in CONSTRAINT_VARIANTS for row in pair] == definitions
    for original, alternative in CONSTRAINT_VARIANTS:
        assert original[:6] == alternative[:6]
        assert original[2:6] == ('c', True, False, False)


def test_original_catalog_still_accepted(initialized):
    assert schema_evidence(initialized) == EXPECTED
    guard(initialized)


def test_actual_reparsed_restored_catalog_accepted(restored):
    assert schema_evidence(restored)['constraints'] != EXPECTED['constraints']
    assert restored.scalar(text(SEMANTIC_CONTEXT_QUERY)) is True
    guard(restored)


@pytest.mark.parametrize('variant', [
    'cast', 'operator', 'expression', 'missing', 'extra', 'renamed',
    'column-type', 'validation', 'index', 'other-category', 'combined',
])
def test_live_restored_schema_drift_refused(restored, variant):
    original, alternative = CONSTRAINT_VARIANTS[0]
    if variant in ('cast', 'operator', 'expression'):
        expression = alternative[6]
        if variant == 'cast':
            expression = expression.replace('context::text', 'context::character(7)::text')
        elif variant == 'operator':
            expression = expression.replace('= ANY', '<> ANY')
        else:
            expression = expression.replace("'primary_80'", "'unknown'")
        replace_check(restored, (*alternative[:6], expression))
    elif variant == 'missing':
        restored.execute(text(f'ALTER TABLE {original[0]} DROP CONSTRAINT {original[1]}'))
    elif variant == 'extra':
        restored.execute(text('ALTER TABLE corpus ADD CONSTRAINT unknown CHECK (true)'))
    elif variant == 'renamed':
        restored.execute(text(f'ALTER TABLE {original[0]} RENAME CONSTRAINT {original[1]} TO unknown'))
    elif variant == 'column-type':
        restored.execute(text('ALTER TABLE corpus ALTER COLUMN version TYPE varchar(121)'))
    elif variant == 'validation':
        replace_check(restored, (*alternative[:6], alternative[6] + ' NOT VALID'))
    elif variant == 'index':
        restored.execute(text('CREATE INDEX unknown ON corpus(version)'))
    elif variant == 'other-category':
        restored.execute(text('CREATE SCHEMA unknown'))
    elif variant == 'combined':
        # Every allowed restored expression is still present, plus an attack on
        # an unrelated CHECK. A nine-row-only comparison would accept this.
        restored.execute(text('ALTER TABLE provenance DROP CONSTRAINT ck_provenance_evidence_sha256_format'))
        restored.execute(text('ALTER TABLE provenance ADD CONSTRAINT ck_provenance_evidence_sha256_format CHECK (true)'))
    with pytest.raises(ValueError, match='Unexpected schema'):
        guard(restored)


@pytest.mark.parametrize('field,value', [
    (0, 'wrong_table'), (1, 'wrong_name'), (2, 'f'), (3, False),
    (4, True), (5, True), (6, 'CHECK (true)'),
])
def test_every_catalog_row_property_is_exact(restored, field, value):
    rows = [list(row) for row in restored.execute(text(CATALOG_QUERIES['constraints']))]
    row = next(row for row in rows if row[:2] == list(CONSTRAINT_VARIANTS[0][0][:2]))
    row[field] = value
    assert not matches_restored_constraints(rows)


@pytest.mark.parametrize('mutation', ['duplicate', 'missing-unrelated', 'extra-unrelated', 'reordered'])
def test_complete_ordered_inventory_required(restored, mutation):
    rows = [tuple(row) for row in restored.execute(text(CATALOG_QUERIES['constraints']))]
    if mutation == 'duplicate':
        rows.append(CONSTRAINT_VARIANTS[0][1])
    elif mutation == 'missing-unrelated':
        rows.pop(0)  # Alembic constraint, outside the nine-row ledger
    elif mutation == 'extra-unrelated':
        rows.append(('corpus', 'unknown', 'c', True, False, False, 'CHECK (true)'))
    else:
        rows.reverse()
    assert not matches_restored_constraints(rows)


def test_all_510_unreviewed_mixtures_refused(restored):
    baseline = [tuple(row) for row in restored.execute(text(CATALOG_QUERIES['constraints']))]
    for mask in range(1, 511):
        rows = baseline.copy()
        for i, (original, alternative) in enumerate(CONSTRAINT_VARIANTS):
            if mask & (1 << i):
                rows[rows.index(alternative)] = original
        assert not matches_restored_constraints(rows), mask


@pytest.mark.parametrize('drift', [False, True])
def test_guarded_alembic_entry_on_restored_fixture(restored, monkeypatch, drift):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    monkeypatch.setenv('STYLOMETRY_MIGRATION_TARGET', 'stylometry_test')
    monkeypatch.setenv('STYLOMETRY_MIGRATION_MODE', 'initialized')
    monkeypatch.setenv('STYLOMETRY_MIGRATION_REVISION', NEW_REVISION)
    config = Config('alembic.ini')
    config.attributes['connection'] = restored
    if drift:
        restored.execute(text('ALTER TABLE corpus ADD CONSTRAINT unknown CHECK (true)'))
        before = schema_evidence(restored)
        with pytest.raises(RuntimeError, match='Migration refused'):
            command.upgrade(config, NEW_REVISION)
        assert schema_evidence(restored) == before
        assert restored.scalar(text('SELECT version_num FROM alembic_version')) == 's2b01_0001'
        assert len(inspect(restored).get_table_names()) == 16
    else:
        command.upgrade(config, NEW_REVISION)
        assert restored.scalar(text('SELECT version_num FROM alembic_version')) == NEW_REVISION
        assert len(inspect(restored).get_table_names()) == 23
        with pytest.raises(RuntimeError, match='Migration refused'):
            command.upgrade(config, NEW_REVISION)
    # Alembic releases only its savepoint; fixture teardown rolls back all DDL.
    assert restored.in_transaction()


@pytest.mark.parametrize('category', sorted(set(EXPECTED) - {'constraints'}))
def test_each_other_category_remains_exact(restored, monkeypatch, category):
    import stylometry.upgrade_safety as safety
    evidence = schema_evidence(restored)
    evidence[category] = '0' * 64
    monkeypatch.setattr(safety, 'schema_evidence', lambda connection: evidence)
    with pytest.raises(ValueError, match='Unexpected schema'):
        guard(restored)


@pytest.mark.parametrize('version', ['180005', '180007', '190000', None])
def test_restored_version_refused(restored, monkeypatch, version):
    scalar = restored.scalar
    monkeypatch.setattr(restored, 'scalar', lambda sql, *a, **kw:
        version if str(sql) == 'SHOW server_version_num' else scalar(sql, *a, **kw))
    with pytest.raises(ValueError, match='Unreviewed server catalog version'):
        guard(restored)


@pytest.mark.parametrize('revision', ['unknown', NEW_REVISION, None])
def test_restored_revision_refused(restored, revision):
    restored.execute(text('DELETE FROM alembic_version'))
    if revision is not None:
        restored.execute(text('INSERT INTO alembic_version VALUES (:revision)'), {'revision': revision})
    with pytest.raises(ValueError, match='Migration revision refused'):
        guard(restored)


@pytest.mark.parametrize('code', ['T01', 'T02', 'T03', 'T04', 'T05'])
def test_each_modified_seed_value_refused(restored, monkeypatch, code):
    # Bypass the separate task-definition CHECK only in this synthetic result,
    # to prove the seed comparison itself still rejects modified values.
    execute = restored.execute
    def changed_seed(sql, *args, **kwargs):
        result = execute(sql, *args, **kwargs)
        if str(sql) == 'SELECT code,genre,form FROM public.task ORDER BY code':
            return [(r[0], 'unknown' if r[0] == code else r[1], r[2]) for r in result]
        return result
    monkeypatch.setattr(restored, 'execute', changed_seed)
    with pytest.raises(ValueError, match='Task definitions differ'):
        guard(restored)


@pytest.mark.parametrize('old,new', [
    ("(1043,'varchar','b',0,100)", "(1043,'varchar','d',0,100)"),
    ("castmethod='b'", "castmethod='f'"),
    ("(98,'=',25,67,'texteq')", "(98,'=',25,157,'textne')"),
    ('AND p.proisstrict', 'AND NOT p.proisstrict'),
    ("p.provolatile='i'", "p.provolatile='v'"),
    ('AND c.collisdeterministic', 'AND NOT c.collisdeterministic'),
])
def test_pinned_semantic_context_refuses_mismatch(restored, monkeypatch, old, new):
    assert old in SEMANTIC_CONTEXT_QUERY
    # Query actual built-in catalogs with one contradictory expectation. Never
    # mutate system catalogs to test the refusal branch.
    mismatch = restored.scalar(text(SEMANTIC_CONTEXT_QUERY.replace(old, new)))
    assert mismatch is False
    scalar = restored.scalar
    monkeypatch.setattr(restored, 'scalar', lambda sql, *a, **kw:
        mismatch if str(sql) == SEMANTIC_CONTEXT_QUERY else scalar(sql, *a, **kw))
    with pytest.raises(ValueError, match='Unexpected schema'):
        guard(restored)
