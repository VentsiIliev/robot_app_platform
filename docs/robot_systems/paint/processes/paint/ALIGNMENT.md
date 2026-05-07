# Paint Alignment Algorithms

This document explains how paint workpiece alignment works in:

- `src/robot_systems/paint/processes/paint/align/alignment/core.py`
- `src/robot_systems/paint/processes/paint/align/alignment/io.py`
- `src/robot_systems/paint/processes/paint/align/alignment/sampling.py`
- `src/robot_systems/paint/processes/paint/align/dxf_image_placement.py`

The goal of this layer is:

1. start from a saved workpiece or imported DXF
2. place it into image space
3. align it to the captured contour from vision
4. output a raw workpiece payload that later path planning can consume

---

## Two Distinct Steps

There are two separate geometry operations in the paint pipeline.

### 1. DXF image placement

`map_raw_workpiece_mm_to_image()` maps mm-space geometry into image-space coordinates using the current vision transformer and local image basis.

This is not the final fit. It is only the first coarse placement.

### 2. Contour alignment

`align_raw_workpiece_to_contour()` then fits the placed workpiece onto the actual captured contour.

That second step is the real alignment solve.

---

## Inputs And Outputs

### Input

- `raw`: saved raw workpiece payload
- `captured_contour`: contour detected by the camera
- `strategy`: `rigid` or `reference_smooth`
- `max_scale_deviation`: allowed uniform scale band around a reference scale

### Output

A deep-copied raw workpiece payload whose main contour and spray-pattern segments have been transformed into image-space alignment with the captured contour.

---

## Coordinate Model

The alignment is a 2D similarity transform:

- rotation `theta`
- uniform scale `s`
- translation `t = (tx, ty)`

Applied around the source contour centroid:

`p' = s * R(theta) * (p - c) + c + t`

Where:

- `p` is an original source point
- `c` is the source contour centroid
- `R(theta)` is the 2x2 rotation matrix

In code this is handled by:

- `_rotation_matrix()`
- `_rotate_and_scale_points()`
- `_transform_points()`

The solver is explicitly not doing:

- non-uniform scale
- affine shear
- projective warp

That is intentional. The DXF/workpiece shape is treated as rigid except for one bounded uniform scale.

---

## Why Resampling Happens First

Contours from the editor, DXF import, and vision capture do not have comparable point density or point ordering.

The solver first resamples both source and target into evenly spaced closed paths:

- sample count: `360`

This is done by `_resample_closed_path()`.

Purpose:

- remove bias from unevenly spaced vertices
- make indexed correspondences meaningful
- give ICP and local search enough resolution
- make area/length/bbox-based scale estimates more stable

Without this, a contour with a few long segments and a contour with many short segments would produce unstable nearest-neighbor behavior.

---

## Stage 1: Strong Initial Pose Search

The solver does not start from PCA alone.

It uses `_best_initial_pose()` to search for a strong initialization in three passes.

### Pass A: Cyclic contour correspondence search

The source contour is treated as a loop.

The algorithm tries:

- multiple cyclic shifts along the contour
- both winding directions

Current shift budget:

- `num_shifts=64`

For each candidate correspondence ordering, it solves an indexed similarity transform with SVD using `_estimate_similarity_transform_indexed()`.

That gives:

- candidate rotation
- candidate scale
- candidate translation

Each candidate is scored with symmetric nearest-neighbor contour distance.

This is the most important guard against poor point ordering and mirrored traversal assumptions.

### Pass B: Coarse global angle sweep

The solver also tries a coarse full-angle scan:

- `-180` to `+165` degrees
- step size `15` degrees

For each angle:

1. rotate and scale source
2. translate it to the target centroid
3. score it with symmetric contour distance

This helps on ambiguous contours where indexed correspondences alone can land in a bad rotational branch.

### Pass C: Conservative PCA fallback

Only if the stronger search fails, the solver falls back to:

- principal-axis angle from source
- principal-axis angle from target
- candidate angles separated by `180` degrees

This fallback exists for robustness, but it is intentionally not the main path.

---

## How Scale Is Estimated And Clamped

Scale is uniform and bounded.

### Reference scale

The solver builds a robust reference scale with `_robust_reference_scale()` from several global shape ratios:

- bounding-box width ratio
- bounding-box height ratio
- square root of area ratio
- perimeter ratio

It takes the median of the valid candidates.

That keeps scale estimation from being dominated by any one noisy measurement.

### Clamp rule

The final scale is clamped by `_clamp_scale()`:

`scale in [reference_scale * (1 - d), reference_scale * (1 + d)]`

Where:

- `d = max_scale_deviation`

Default:

- `DEFAULT_MAX_SCALE_DEVIATION = 0.03`

So by default the solver only allows about `+-3%` scale drift around the reference scale.

This is important because otherwise contour noise can distort the imported DXF too aggressively.

---

## Stage 2: ICP-Style Refinement

After the initial pose is found, `_refine_pose_icp()` runs a short ICP-like loop.

Current settings:

- `iterations=8`
- `trim_ratio=0.8`

Per iteration:

1. transform the source contour with the current pose
2. find nearest target points using a KD-tree
3. keep only the closest `80%` of matches
4. solve a new indexed similarity transform on the trimmed set
5. accept the candidate only if the symmetric error improves

Important detail:

- matching is nearest-neighbor
- solving is still similarity-only
- the loop stops once improvement stops

This is a local sharpening pass, not a free-form optimizer.

The trimming step is important because it reduces sensitivity to:

- contour outliers
- noisy corners
- partial mismatch in one region of the contour

---

## Stage 3: Local Overlap-Driven Refinement

The last stage is `_refine_alignment_with_mask_overlap()`.

This is a coarse-to-fine local search around the current best pose.

### Score function

Higher is better:

`score = overlap - 0.35 * symmetric_alignment_error`

Where:

- `overlap` comes from `calculate_mask_overlap(...)`
- `symmetric_alignment_error` is the average of source-to-target and target-to-source nearest-neighbor distances

This gives the solver two pressures at once:

- maximize visible filled overlap
- avoid contour drift that happens to overlap only in a coarse area sense

### Search schedule

The solver uses three progressively smaller step sizes.

Rotation steps:

- `4.0 deg`
- `0.5 deg`
- `0.05 deg`

Translation steps:

- `8.0 px`
- `0.75 px`
- `0.1 px`

Scale steps:

- `0.025`
- `0.005`
- `0.001`

For each step scale, it tries:

- pure rotation moves
- pure scale moves
- pure translation moves
- rotate + translate combinations
- scale + translate combinations

The loop keeps the best improving candidate and repeats until no candidate improves the score.

This is a bounded hill-climb, not a global optimization.

---

## Rigid Vs `reference_smooth`

The final alignment has two output modes.

### `rigid`

This is the simpler mode.

The solver applies the solved similarity transform directly to:

- the main contour
- `sprayPattern.Contour` segments
- `sprayPattern.Fill` segments

That means the saved geometry remains the saved geometry, just transformed into place.

### `reference_smooth`

This is a hybrid mode.

The aligned DXF is used as a denoising prior for the captured contour.

The process in `_apply_reference_smoothed_main_contour()` is:

1. resample the saved main contour to `360` points
2. transform that contour with the solved pose
3. treat that transformed contour as a reference prior
4. pull the captured contour gently toward that prior with `_bounded_reference_smooth()`
5. smooth the corrected result with `_laplacian_smooth_closed_path()`
6. write the smoothed captured contour back into the main contour payload

This mode keeps the captured contour as the visible result, but suppresses local noise by biasing it toward the aligned DXF.

### What `_bounded_reference_smooth()` actually does

Per point:

1. compute a local tangent from neighboring points
2. derive the local normal
3. find the nearest point on the aligned reference contour
4. decompose the delta into:
   - tangent component
   - normal component
5. clamp the correction

Current clamps:

- normal shift: up to `5 px`
- tangent shift: up to `1 px`
- tangent contribution scaled by `0.15`

This means most correction happens normal to the contour, which preserves the contour parameterization better than allowing strong tangential sliding.

### Laplacian smoothing

After bounded correction, `_laplacian_smooth_closed_path()` runs:

- `iterations=2`
- `alpha=0.18` in the reference-smooth branch

This averages each point slightly toward its neighbors without fully collapsing the contour.

---

## What Gets Transformed

The main contour is not the only geometry that moves.

After the solve, the same transform is applied to:

- the main contour payload
- contour spray segments
- fill spray segments

That is why alignment affects both the visible workpiece outline and the process geometry used later in path planning.

---

## Failure And Fallback Behavior

Alignment is intentionally conservative.

If either contour has fewer than three usable points:

- the function returns a deep copy of the input
- no transformation is applied

Other conservative choices:

- empty or degenerate resampling returns early
- scale is bounded
- refinement only accepts improving candidates

The alignment layer prefers "do nothing" over "invent an unstable transform."

---

## Why KD-Trees Are Used

Nearest-neighbor queries happen repeatedly in:

- contour-distance scoring
- ICP matching
- overlap refinement

The code uses `scipy.spatial.cKDTree` to avoid repeated `O(n^2)` scans over dense `360`-point contours.

This keeps the coarse-to-fine search practical while still using dense contour samples.

---

## Practical Interpretation

A concise mental model of the algorithm is:

1. put both contours on a common evenly sampled representation
2. find a good loop correspondence and coarse orientation
3. solve a bounded similarity transform
4. sharpen with trimmed ICP
5. sharpen again with overlap-aware local search
6. either:
   - transform the DXF rigidly
   - or use the DXF as a prior to smooth the captured contour

That is the full alignment story used by the paint workpiece pipeline.
