# Release v1.0.1 — corrected after independent chart review

The v1.0.0 code archive predates the independent chart review. Use this release for
the final manuscript.

## Changes

- eICU ICU-admission landmark: prior RRT redefined relative to ICU admission
- eICU mechanical ventilation supplemented with respiratory-care records
- Amsterdam landmark sex coding corrected
- Updated landmark table/figure and pooled estimates
- Independent chart-review agreement table

## Steps

1. Copy the corrected files in `analysis_code/` to the repository.
2. Commit: `git commit -m "Corrections after independent chart review v1.0.1"`
3. Tag: `git tag v1.0.1 && git push origin main --tags`
4. Create GitHub release v1.0.1.
5. Zenodo will archive it automatically; use the **concept DOI** 10.5281/zenodo.23634332
   in the manuscript, or the new version DOI if you prefer exact reproducibility.
6. Update `CITATION.cff`, `.zenodo.json`, and README with real authors.
