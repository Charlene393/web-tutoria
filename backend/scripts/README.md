# Backend Scripts

## KSL cleanup workflow

Use the dataset cleanup report generator from the repo root:

```bash
backend/api/.venv/bin/python backend/scripts/generate_ksl_cleanup_reports.py
```

Then build the manual decision sheet:

```bash
backend/api/.venv/bin/python backend/scripts/build_cleanup_decisions_template.py
```

If you want the sheet pre-populated with safe default actions and notes:

```bash
backend/api/.venv/bin/python backend/scripts/prefill_cleanup_decisions.py
```

When you are ready to derive a cleaned manifest from the drop decisions:

```bash
backend/api/.venv/bin/python backend/scripts/apply_cleanup_decisions_to_manifest.py
```

Then build the backend lesson catalog from the cleaned manifest:

```bash
backend/api/.venv/bin/python backend/scripts/build_ksl_lesson_catalog.py
```

It writes reports to:

```text
backend/reports/ksl_cleanup/
```

Main outputs:

- `manifest.csv`:
  one row per landmark file with paths, frame count, and hand presence
- `label_counts.csv`:
  one row per label with sample counts and quality summaries
- `missing_hands_report.csv`:
  samples where hand landmarks are weak or missing
- `suspicious_labels.csv`:
  labels that look structurally noisy, such as filename-like or malformed names
- `low_support_labels.csv`:
  labels with very few samples, useful for vocabulary triage
- `review_candidates.csv`:
  file-level records you should inspect manually
- `label_variants.csv`:
  normalized label groups that may reveal duplicates or naming drift
- `cleanup_decisions.csv`:
  the manual review sheet where you record keep, rename, merge, or drop decisions
- `cleaned/manifest.csv`:
  the derived manifest after applying `drop_sample` and `drop_label` decisions
- `cleaned/dropped_manifest_rows.csv`:
  the rows removed from the manifest, with the matching decision ids and notes
- `cleaned/applied_drop_decisions.csv`:
  the drop decisions that were applied, with manifest match counts
- `cleaned/label_counts.csv`:
  label-level counts recomputed from the cleaned manifest
- `backend/api/app/data/ksl_lesson_catalog.json`:
  the curated lesson asset catalog used by the FastAPI backend
- `summary.json`:
  overall dataset counts and thresholds used

Recommended workflow:

1. run the script
2. run `build_cleanup_decisions_template.py`
3. optionally run `prefill_cleanup_decisions.py`
4. open `cleanup_decisions.csv`
5. inspect the matching `.npy` and `Stickmans/*.mp4` files
6. adjust `selected_action`, `target_label`, and `notes` if needed
7. run `apply_cleanup_decisions_to_manifest.py`
8. run `build_ksl_lesson_catalog.py`
9. use `backend/api/app/data/ksl_lesson_catalog.json` as the backend lesson source of truth
10. only then update glossary or training inputs

Notes:

- the decision template does not modify the raw dataset
- by default it will not overwrite an existing `cleanup_decisions.csv`
- use `--force` only if you intentionally want to regenerate the file
- use `--include-low-support` if you also want low-sample labels added to the sheet
- the prefill script only fills blank `selected_action` and `notes` cells
- the apply script does not touch `.npy` or `.mp4` files; it only writes derived CSV and JSON outputs
- the apply script ignores non-drop actions like `keep`, `rename_label`, and `merge_label`
- if you want a `drop_sample` or `drop_label` row temporarily excluded, set `review_status` to `hold`, `skip`, or `rejected`
- the lesson catalog script picks one best cleaned sample per label for API playback and teaching use
