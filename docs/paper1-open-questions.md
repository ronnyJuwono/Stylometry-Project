# Paper 1 discrepancy and missing-information register

All items are open at S2A. Priority describes what blocks reproduction, not a
license to choose a default. Reference values come only from user-supplied S2A
context. No external paper/archive/code has been inspected.

| ID | Observation / missing detail | Required evidence / resolution | Impact |
|---|---|---|---|
| M01 | 46 profiles / 230 potential slots / 200 nonempty differs from primary 35 / 163 | Archived inventory version plus per-slot inclusion/exclusion ledger and final primary membership | Cannot reconcile exclusions or infer missingness types |
| M02 | Inventory PASS uses 100 words; primary uses 80 | Original classification definitions, token counts and tokenizer implementation/version | Inventory PASS cannot stand in for analytical eligibility |
| M03 | Primary requires at least four eligible tasks | Exact eligibility criteria and operation order, re-evaluation after exclusions, task coverage | Cannot reproduce writer selection |
| M04 | Four duplicate task pairs / two profiles; duplicated texts excluded | Private pair ledger, sample mapping, similarity/equality definition, normalization, adjudication, retained/excluded side(s) | Pair count does not determine unique removed text count |
| M05 | Sensitivity 24 / 110 at 100 words | Membership list, source cohort, writer minimum, duplicate handling and order | Cannot derive this cohort from primary membership alone |
| M06 | Balanced 23 / 115 | Membership list, length threshold, source cohort and duplicate rules | Five-task balance is known; cohort relationship is not |
| M07 | 43 engineered / 24 primary features | Complete versioned registry: names, families, formulas, units, normalization, subset, implementation/resource versions | Feature registry must remain incomplete |
| M08 | Word count and tokenization unspecified | Apostrophe/hyphen/number/punctuation/Unicode/whitespace rules, headers/prompts removal, test examples | Length thresholds cannot be recomputed faithfully |
| M09 | Extraction/cleaning unspecified | Formats, segmentation/task mapping, extractor/version, OCR if any, encoding, cleaning steps/order, manual corrections | Cannot reproduce clean text or hashes |
| M10 | Stability model specification absent | Approved paper + supplements + analysis scripts; exact estimands, ICC/model/effects if used, intervals, diagnostics, missingness, multiplicity | No model or verification implementation authorized |
| M11 | Feature transformations / EDA / sensitivity procedures absent | Exact scaling/log/outlier/zero handling, feature selection timing, plot specifications, robustness settings, seeds and package versions | No default transformations or analysis plan may be substituted |
| M12 | Study collection and ethics metadata absent | Task prompts, dates, timing, student eligibility, task conditions, consent/ethics and anonymization/storage protocol | Cannot characterize population or approve source access |
| M13 | Authoritative publication identity/status absent | Approved manuscript/version, supplement identifiers, venue/conference dates and status evidence | Publication metadata stays unknown/unverified |
| D01 | Data-contract format is a new engineering proposal | Review UUID/JSON/hash conventions, QC vocabulary, immutable record retention and snapshot sealing | This metadata design does not amend scientific methods |
| D02 | Clean-text lineage policy needs review | S2A proposes a separate version chain per extraction/sample; confirm this engineering convention and future corpus-version boundary | Avoid silently merging incompatible derivations |
| D03 | Private object/method/config references are opaque | Approved storage resolver, access controls, byte-hash verification and retention/version policy | Shape validation cannot prove evidence availability |

## Materials needed, without automatic loading

1. The authoritative Paper 1 manuscript and supplements, with version/date and
   verified citation; approved protocol or preregistration if available.
2. A redacted inventory schema/codebook and private per-slot ledger linking the
   archived source version to primary/sensitivity/balanced membership. Supply
   actual data only through a separately approved private workflow.
3. The duplicate adjudication ledger and exact duplicate-detection procedure.
4. Extraction, cleaning, word-counting, and task segmentation specifications and
   versioned code, with safe artificial examples and expected behavior.
5. The 43-feature registry and authoritative 24-feature subset, formulas, resource
   dependencies, transformation rules, and analysis scripts/environment lockfiles.
6. Exact stability/sensitivity model specifications and published reference tables
   sufficient to validate a later authorized reproduction.
7. Ethics/consent, anonymization, source access, storage and retention approvals.

First review S2A contracts/schema. Then resolve methodology items using these
materials, record evidence versions, and approve a separate implementation scope.
Do not fetch Drive files, infer missing formulas, or run experiments to make the
reported totals fit. One review commit and push of `feature/paper1-data-contracts`
are expressly authorized; merging and further implementation remain unauthorized.
