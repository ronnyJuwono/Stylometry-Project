"""S2C-03D's nine literal CHECK alternatives, not a SQL normalizer.

Only the complete observed restored state is accepted. Constants are transcribed
from O1/R1--O9/R9 in the diagnosis, independently checked against rollback
fixtures of the frozen initial migration. No live database generates evidence.
"""

from stylometry.contracts import canonical_sha256
from stylometry.initial_schema_evidence import EXPECTED


# Each immutable entry is (complete original catalog row, complete restored row).
CONSTRAINT_VARIANTS = ((('dataset_snapshot',
   'ck_dataset_snapshot_context',
   'c',
   True,
   False,
   False,
   "CHECK (context::text = ANY (ARRAY['primary_80'::character varying, "
   "'sensitivity_100'::character varying, 'balanced_five_task'::character varying]::text[]))"),
  ('dataset_snapshot',
   'ck_dataset_snapshot_context',
   'c',
   True,
   False,
   False,
   "CHECK (context::text = ANY (ARRAY['primary_80'::character varying::text, "
   "'sensitivity_100'::character varying::text, 'balanced_five_task'::character varying::text]))")),
 (('experiment_run',
   'ck_experiment_run_lifecycle',
   'c',
   True,
   False,
   False,
   "CHECK (status::text = 'planned'::text AND started_at IS NULL AND finished_at IS NULL OR "
   "status::text = 'running'::text AND started_at IS NOT NULL AND finished_at IS NULL OR "
   "(status::text = ANY (ARRAY['succeeded'::character varying, 'failed'::character "
   'varying]::text[])) AND started_at IS NOT NULL AND finished_at IS NOT NULL OR status::text = '
   "'cancelled'::text AND finished_at IS NOT NULL)"),
  ('experiment_run',
   'ck_experiment_run_lifecycle',
   'c',
   True,
   False,
   False,
   "CHECK (status::text = 'planned'::text AND started_at IS NULL AND finished_at IS NULL OR "
   "status::text = 'running'::text AND started_at IS NOT NULL AND finished_at IS NULL OR "
   "(status::text = ANY (ARRAY['succeeded'::character varying::text, 'failed'::character "
   'varying::text])) AND started_at IS NOT NULL AND finished_at IS NOT NULL OR status::text = '
   "'cancelled'::text AND finished_at IS NOT NULL)")),
 (('experiment_run',
   'ck_experiment_run_status',
   'c',
   True,
   False,
   False,
   "CHECK (status::text = ANY (ARRAY['planned'::character varying, 'running'::character varying, "
   "'succeeded'::character varying, 'failed'::character varying, 'cancelled'::character "
   'varying]::text[]))'),
  ('experiment_run',
   'ck_experiment_run_status',
   'c',
   True,
   False,
   False,
   "CHECK (status::text = ANY (ARRAY['planned'::character varying::text, 'running'::character "
   "varying::text, 'succeeded'::character varying::text, 'failed'::character varying::text, "
   "'cancelled'::character varying::text]))")),
 (('extraction_event',
   'ck_extraction_event_status',
   'c',
   True,
   False,
   False,
   "CHECK (status::text = ANY (ARRAY['succeeded'::character varying, 'failed'::character "
   'varying]::text[]))'),
  ('extraction_event',
   'ck_extraction_event_status',
   'c',
   True,
   False,
   False,
   "CHECK (status::text = ANY (ARRAY['succeeded'::character varying::text, 'failed'::character "
   'varying::text]))')),
 (('qc_evaluation',
   'ck_qc_evaluation_context',
   'c',
   True,
   False,
   False,
   "CHECK (context::text = ANY (ARRAY['source_inventory_100'::character varying, "
   "'primary_80'::character varying, 'sensitivity_100'::character varying, "
   "'balanced_five_task'::character varying]::text[]))"),
  ('qc_evaluation',
   'ck_qc_evaluation_context',
   'c',
   True,
   False,
   False,
   "CHECK (context::text = ANY (ARRAY['source_inventory_100'::character varying::text, "
   "'primary_80'::character varying::text, 'sensitivity_100'::character varying::text, "
   "'balanced_five_task'::character varying::text]))")),
 (('qc_evaluation',
   'ck_qc_evaluation_context_threshold',
   'c',
   True,
   False,
   False,
   "CHECK ((context::text <> ALL (ARRAY['source_inventory_100'::character varying, "
   "'primary_80'::character varying, 'sensitivity_100'::character varying]::text[])) OR "
   'word_threshold IS NOT NULL AND word_threshold =\n'
   'CASE\n'
   "    WHEN context::text = 'primary_80'::text THEN 80\n"
   '    ELSE 100\n'
   'END)'),
  ('qc_evaluation',
   'ck_qc_evaluation_context_threshold',
   'c',
   True,
   False,
   False,
   "CHECK ((context::text <> ALL (ARRAY['source_inventory_100'::character varying::text, "
   "'primary_80'::character varying::text, 'sensitivity_100'::character varying::text])) OR "
   'word_threshold IS NOT NULL AND word_threshold =\n'
   'CASE\n'
   "    WHEN context::text = 'primary_80'::text THEN 80\n"
   '    ELSE 100\n'
   'END)')),
 (('qc_evaluation',
   'ck_qc_evaluation_status',
   'c',
   True,
   False,
   False,
   "CHECK (status::text = ANY (ARRAY['not_evaluated'::character varying, 'pass'::character "
   "varying, 'excluded'::character varying, 'review_required'::character varying]::text[]))"),
  ('qc_evaluation',
   'ck_qc_evaluation_status',
   'c',
   True,
   False,
   False,
   "CHECK (status::text = ANY (ARRAY['not_evaluated'::character varying::text, 'pass'::character "
   "varying::text, 'excluded'::character varying::text, 'review_required'::character "
   'varying::text]))')),
 (('qc_reason',
   'ck_qc_reason_reason_code',
   'c',
   True,
   False,
   False,
   "CHECK (reason_code::text = ANY (ARRAY['missing_text'::character varying, "
   "'below_word_threshold'::character varying, 'duplicate_text'::character varying, "
   "'insufficient_eligible_tasks'::character varying, 'extraction_failed'::character varying, "
   "'unresolved_method'::character varying]::text[]))"),
  ('qc_reason',
   'ck_qc_reason_reason_code',
   'c',
   True,
   False,
   False,
   "CHECK (reason_code::text = ANY (ARRAY['missing_text'::character varying::text, "
   "'below_word_threshold'::character varying::text, 'duplicate_text'::character varying::text, "
   "'insufficient_eligible_tasks'::character varying::text, 'extraction_failed'::character "
   "varying::text, 'unresolved_method'::character varying::text]))")),
 (('source_document',
   'ck_source_document_media_type',
   'c',
   True,
   False,
   False,
   "CHECK (media_type::text = ANY (ARRAY['application/pdf'::character varying, "
   "'application/vnd.openxmlformats-officedocument.wordprocessingml.document'::character varying, "
   "'text/plain'::character varying, 'application/octet-stream'::character varying]::text[]))"),
  ('source_document',
   'ck_source_document_media_type',
   'c',
   True,
   False,
   False,
   "CHECK (media_type::text = ANY (ARRAY['application/pdf'::character varying::text, "
   "'application/vnd.openxmlformats-officedocument.wordprocessingml.document'::character "
   "varying::text, 'text/plain'::character varying::text, 'application/octet-stream'::character "
   'varying::text]))')))


def matches_restored_constraints(rows):
    """Compare the ENTIRE ordered inventory against the original frozen digest.

    Substitute only complete literal restored rows in a comparison copy. All
    nine must occur exactly once; mixtures, duplicates and unknown rows fail.
    Nothing is written to the database or transformed as SQL.
    """
    originals = {restored[:2]: (original, restored)
                 for original, restored in CONSTRAINT_VARIANTS}
    seen = set()
    comparison = []
    for value in rows:
        row = tuple(value)
        pair = originals.get(row[:2])
        if pair is None:
            comparison.append(list(row))
            continue
        original, restored = pair
        if row != restored or row[:2] in seen:
            return False
        seen.add(row[:2])
        comparison.append(list(original))
    return (len(seen) == 9
            and canonical_sha256(comparison) == EXPECTED['constraints'])


# Pin the built-in semantic context used in the S2C-03D proof. This supplements
# (never replaces) the unchanged complete columns/types/indexes fingerprints.
# No system-catalog writes or user-controlled SQL are involved.
SEMANTIC_CONTEXT_QUERY = """
SELECT
  (SELECT count(*) = 5 FROM pg_catalog.pg_type t
   JOIN pg_catalog.pg_namespace n ON n.oid=t.typnamespace
   JOIN (VALUES (23,'int4','b',0,0), (25,'text','b',0,100),
                (1043,'varchar','b',0,100), (1009,'_text','b',25,100),
                (1015,'_varchar','b',1043,100))
        AS e(id,name,kind,element,collation_id)
     ON t.oid=e.id AND t.typname=e.name AND t.typtype::text=e.kind
        AND t.typelem=e.element AND t.typcollation=e.collation_id
   WHERE n.nspname='pg_catalog' AND t.typbasetype=0)
  AND (SELECT count(*) = 1 FROM pg_catalog.pg_cast
       WHERE castsource=1043 AND casttarget=25 AND castmethod='b'
         AND castfunc=0 AND castcontext='i')
  AND (SELECT count(*) = 3 FROM pg_catalog.pg_operator o
       JOIN pg_catalog.pg_namespace n ON n.oid=o.oprnamespace
       JOIN pg_catalog.pg_proc p ON p.oid=o.oprcode
       JOIN pg_catalog.pg_namespace pn ON pn.oid=p.pronamespace
       JOIN (VALUES (98,'=',25,67,'texteq'), (531,'<>',25,157,'textne'),
                    (96,'=',23,65,'int4eq')) AS e(id,name,arg,fn,impl)
         ON o.oid=e.id AND o.oprname=e.name AND o.oprleft=e.arg
            AND o.oprright=e.arg AND o.oprcode=e.fn
            AND p.proname=e.impl AND p.prosrc=e.impl
       WHERE n.nspname='pg_catalog' AND pn.nspname='pg_catalog'
         AND o.oprresult=16 AND p.prorettype=16 AND p.pronargs=2
         AND p.proargtypes[0]=e.arg AND p.proargtypes[1]=e.arg
         AND p.proisstrict AND p.provolatile='i' AND p.prokind='f'
         AND p.prolang=12 AND p.probin IS NULL)
  AND (SELECT count(*) = 1 FROM pg_catalog.pg_collation c
       JOIN pg_catalog.pg_namespace n ON n.oid=c.collnamespace
       WHERE c.oid=100 AND c.collname='default' AND n.nspname='pg_catalog'
         AND c.collisdeterministic AND c.collprovider='d')
"""
