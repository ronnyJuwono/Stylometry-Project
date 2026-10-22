# Paper 1 discrepancy and missing-information register

This register distinguishes draft-documented methodology from unresolved
implementation and evidence unavailable to this review. It incorporates the
user's S2A.1 correction about the existing manuscript draft; the draft is not an
approved final protocol. No source documents or code were fetched or independently
validated. Reference counts are reported values, never recomputed results.

Source: `P1-MANUSCRIPT-DRAFT`, **A Data Science Approach to Measuring Stylometric
Stability and Variability in EFL Student Writing**. Validated-copy reference,
version/date, SHA-256 and section/page citations: **TBD**. See the source-reference
block in `paper1-methodology.md`. Missing a validated copy here does not mean that
the project manuscript or its methodology is unavailable.

## Documented in the draft

As described in the user's S2A.1 correction, the draft includes cleaning rules,
exact-duplicate exclusion followed by reapplication of the four-task rule,
23 five-task / 12 four-task writers in the primary corpus, Spearman correlation,
standardized PCA, random-intercept mixed-effects models, writing task as a fixed
effect in adjusted models, and sensitivity analyses. These are documented method
choices awaiting source-version validation, not open choices to replace.

## Unresolved implementation and evidence follow-up

| ID | Observation / missing detail | Required evidence / resolution | Impact |
|---|---|---|---|
| M01 | 46 profiles / 230 potential slots / 200 nonempty differs from primary 35 / 163 | Archived inventory version plus per-slot inclusion/exclusion ledger and final primary membership | Cannot reconcile exclusions or infer missingness types |
| M02 | Inventory PASS uses 100 words; primary uses 80 | Original classification definitions, token counts and tokenizer implementation/version | Inventory PASS cannot stand in for analytical eligibility |
| M03 | Draft documents four-task rule reapplied after exact-duplicate exclusion and primary composition of 23 five-task / 12 four-task writers | Validate draft sections and per-writer/task membership; resolve remaining selection details without replacing the documented order | Known sequence/composition is not a computed selection ledger |
| M04 | Four duplicate task pairs / two profiles; draft specifies exact-duplicate exclusion | Private pair ledger, sample mapping, exact comparison representation, normalization and implementation, adjudication and retained/excluded side(s) | No similarity threshold is implied; pair count does not determine unique removed text count |
| M05 | Sensitivity 24 / 110 at 100 words | Membership list, source cohort, writer minimum, duplicate handling and order | Cannot derive this cohort from primary membership alone |
| M06 | Balanced 23 / 115 | Membership list, length threshold, source cohort and duplicate rules | Five-task balance is known; cohort relationship is not |
| M07 | 43 engineered / 24 primary features; complete authoritative registry not imported here | Validate draft/supplement/code definitions and import versioned names, families, formulas, units, subset and resource versions | Registry remains incomplete; do not infer missing feature definitions |
| M08 | Exact word-count/tokenization implementation remains unresolved here | Validate apostrophe/hyphen/number/punctuation/Unicode/whitespace rules, headers/prompts removal and test examples against draft/code | Length thresholds cannot be recomputed faithfully until implementation is validated |
| M09 | Cleaning rules are documented in the draft; extraction/cleaning code mapping is not validated here | Validate actual cleaning rules, formats, segmentation, extractor/version, encoding, step order and correction handling against source/code | Do not invent cleaning rules or equate source validation gaps with absent methodology |
| M10 | Draft documents random-intercept mixed-effects models and writing task as a fixed effect in adjusted models | Validate exact formulas, estimands, grouping, estimation, uncertainty, diagnostics and software from draft/supplements/code | Method family is known; executable model details remain unresolved here |
| M11 | Draft documents Spearman correlation, standardized PCA and sensitivity analyses | Validate exact inputs, standardization convention, missing/zero/outlier handling, PCA/correlation settings, sensitivity construction, seeds and versions | Do not replace documented methods or guess numerical implementation details |
| M12 | Collection/ethics details have not been established in this review | Check existing draft/project records for task prompts, dates, timing, eligibility, conditions, consent/ethics and anonymization/storage protocol | Availability elsewhere is unverified; source access remains gated |
| M13 | Manuscript draft exists; approved final protocol and verified publication status are unavailable to this review | Validate draft identity/version separately from final approval, supplement identifiers and venue/date/status evidence | Draft is a research source, not a final protocol or publication-status confirmation |
| D01 | Data-contract format is a new engineering proposal | Review UUID/JSON/hash conventions, QC vocabulary, immutable record retention and snapshot sealing | This metadata design does not amend scientific methods |
| D02 | Clean-text lineage policy needs review | S2A proposes a separate version chain per extraction/sample; confirm this engineering convention and future corpus-version boundary | Avoid silently merging incompatible derivations |
| D03 | Private object/method/config references are opaque | Approved storage resolver, access controls, byte-hash verification and retention/version policy | Shape validation cannot prove evidence availability |
| D04 | Current logical sample is one writer/task/corpus slot | Future dissertation studies may need explicit repeated-submission/attempt and authored-draft relationships | Design note only; no S2A.1 contract or schema change |

## Information unavailable to this review

An approved final protocol, a validated version-pinned manuscript copy, verified
publication status and a complete imported authoritative feature registry are
not available here. This does not establish that all underlying materials are
missing from the project. Check the existing draft and project records first;
classify any genuinely absent material only when its absence is established.

## Materials needed, without automatic loading

1. Validate and reference the existing Paper 1 manuscript draft and its
   supplements, with version/date, digest and section citations. Separately
   establish final protocol approval or preregistration status; do not relabel
   the draft as final.
2. A redacted inventory schema/codebook and private per-slot ledger linking the
   archived source version to primary/sensitivity/balanced membership. Supply
   actual data only through a separately approved private workflow.
3. The duplicate adjudication ledger and exact duplicate-detection procedure.
4. Validate draft-documented cleaning rules against extraction, word-counting,
   segmentation and versioned code, with safe artificial examples. Obtain only
   details still unresolved after that comparison.
5. The 43-feature registry and authoritative 24-feature subset, formulas, resource
   dependencies, transformation rules, and analysis scripts/environment lockfiles.
6. Validate the draft's Spearman, standardized PCA, mixed-effects, adjusted-task
   and sensitivity specifications against versioned code and reference tables;
   obtain remaining details needed for a later authorized reproduction.
7. Ethics/consent, anonymization, source access, storage and retention approvals.

First review S2A contracts/schema. Then resolve methodology items using these
materials, record evidence versions, and approve a separate implementation scope.
Do not fetch Drive files, infer missing formulas, or run experiments to make the
reported totals fit. One review commit and push of `feature/paper1-data-contracts`
are expressly authorized; merging and further implementation remain unauthorized.
