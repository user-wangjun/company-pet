---
description: Treat user-marked visual boundaries as coordinate-locked, fail-closed material constraints.
alwaysApply: true
---

# User-Marked Visual Boundary Gate

Use this rule for Live2D/Cubism assets, desktop-pet artwork, masks, flat-color layers, material repairs, and any image edit where the user draws a boundary.

## Authority

- The latest explicit user markup is the authoritative boundary for the current visual scope.
- A red line is a hard constraint, not a visual hint, approximate guide, or request to make the shape merely similar.
- A new markup reopens the current visual gate and supersedes the previous candidate geometry. Keep old approvals, rejections, and candidates unchanged as history.

## Required coordinate contract

Before producing a candidate:

1. Preserve the original markup image and record its hash.
2. Map the markup into the exact authoritative source canvas; record canvas dimensions and the pixel-space transform.
3. Record each boundary segment, its direction, endpoints, and the allowed side.
4. Stop and ask if the marked side or a boundary segment is ambiguous. Do not infer a wider region to keep building.

## Required rendering behavior

- Visible/display alpha must be fully contained in the allowed red-line region.
- Apply the boundary constraint after geometry generation and again after supersampling/downsampling so antialiasing cannot ring outside it.
- Do not use blur, dilation, erosion, threshold expansion, smoothing overshoot, or topology repair to enlarge the visible region.
- Hidden anatomical continuity may be built separately, but it must never expand visible ownership beyond the user boundary.

## Required fail-closed checks

The builder or validation step must stop with failure when any condition is true:

- the boundary contract is absent, stale, or does not match the source/markup hash;
- any nonzero candidate alpha lies outside the allowed red-line region;
- candidate-to-guide or guide-to-candidate boundary coverage/error exceeds the declared tolerance;
- a machine metric passes while the direct overlay visibly disagrees with the markup.

At minimum, record `outsideBoundaryPixels`, bidirectional boundary error, uncovered guide segments, unmatched candidate boundary pixels, and the review image path. Do not convert a failure to a warning.

## Gate behavior

- Numeric checks, topology, ownership, hashes, and build success are necessary engineering evidence only; they cannot substitute for user visual approval.
- Review the original line, the markup, the candidate boundary, and the final antialiased layer together before freezing.
- Do not promote to texture, mesh, Cubism, Physics, Runtime, or a later visual gate while the current marked-boundary gate is unresolved.
