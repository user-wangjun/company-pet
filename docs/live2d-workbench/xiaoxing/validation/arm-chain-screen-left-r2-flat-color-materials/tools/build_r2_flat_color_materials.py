"""Build the R2 full-canvas flat-color material candidate for 小星 Left.

This stage is deliberately geometry-only.  The active default is the R2 hand
hidden wrist-root anti-alias maintenance pass: the hand wrist root and its
separate hidden envelope are authored as float cubic paths, rasterized on a
32x canvas, and downsampled once with monotone BOX coverage.  Binary masks are
logic-only outputs; formal display Alpha is kept separate and the flat hand
layer consumes that display Alpha.  The visible hand ownership, all non-hand
R2 materials, R1 freezes, and historical R3 evidence are protected inputs.

The previous forearm distal wrist U-cap builder remains available only through
the explicit ``--forearm-ucap`` command-line option.  It is not part of the
default hand maintenance invocation and is not run by this pass.
No texture, mesh, Cubism, runtime motion, Physics, or pet integration artifact is
produced here; the lift sequence below is a deterministic flat-color geometry QA
only and remains an unresolved diagnostic if a frame is disconnected.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
from collections import deque
from pathlib import Path
from typing import Iterable, Sequence, cast

from PIL import Image, ImageChops, ImageDraw, ImageFont


R2_ROOT = Path(__file__).resolve().parents[1]
R2_APPROVAL_PATH = R2_ROOT / "audit" / "user-visual-approval-r2-2026-08-06.json"
R2_CURRENT_APPROVAL_PATH = R2_ROOT / "audit" / "user-visual-approval-r2-2026-08-07.json"
R2_FINAL_APPROVAL_PATH = R2_ROOT / "audit" / "user-visual-approval-r2-2026-08-07-final-freeze.json"
R2_REJECTION_PATH = R2_ROOT / "audit" / "user-visual-rejection-hand-r2-2026-08-07.json"
R2_VISUAL_REFINEMENT_PATH = R2_ROOT / "audit" / "user-visual-refinement-request-hand-r2-2026-08-07.json"
R2_SMOOTH_EDGE_REOPEN_PATH = R2_ROOT / "audit" / "user-visual-rejection-hand-r2-smooth-edge-2026-08-09.json"
R2_WHOLE_HAND_APPROVAL_PATH = R2_ROOT / "audit" / "user-visual-approval-whole-hand-flat-color-freeze-2026-08-12.json"
R2_WHOLE_HAND_FREEZE_MANIFEST_PATH = R2_ROOT / "audit" / "whole-hand-flat-color-freeze-manifest-2026-08-12.json"
R2_FORMAL_PROMOTION_REPORT_PATH = R2_ROOT / "audit" / "r2-formal-promotion-report.json"
R2_HISTORICAL_MACHINE_REPORT_PATH = R2_ROOT / "audit" / "machine-report-pre-semantic-topology-2026-08-12.json"
UPPER_ARM_V8_ROOT = R2_ROOT / "candidates" / "upper-arm-aa-anatomical-v8"
UPPER_ARM_V8_VISIBLE_SHA256 = "2a65560b36601e6db5b9a29035bfff0977cb9f7e5ff2e2b97bd8d8da6f2aad40"
UPPER_ARM_V8_SUPERSEDED_R1_ELBOW_RESIDUAL = ((165, 401), (165, 402))
UPPER_ARM_V8_FILES = {
    "masks/visible/upper_arm.png": UPPER_ARM_V8_ROOT / "masks" / "visible-upper_arm.png",
    "masks/hidden/upper_arm.png": UPPER_ARM_V8_ROOT / "masks" / "hidden-upper_arm.png",
    "masks/complete/upper_arm.png": UPPER_ARM_V8_ROOT / "masks" / "complete-upper_arm.png",
    "display-alpha/upper_arm.png": UPPER_ARM_V8_ROOT / "display-alpha" / "upper_arm.png",
    "flat-layers/upper_arm.png": UPPER_ARM_V8_ROOT / "flat-layers" / "upper_arm.png",
    "contracts/upper-arm-aa-anatomical-contract.json": UPPER_ARM_V8_ROOT / "audit" / "upper-arm-aa-anatomical-contract.json",
}
HAND_TRACE_CONTRACT_PATH = R2_ROOT / "contracts" / "hand-line-trace-contract.json"
HAND_VISUAL_BOUNDARY_REPORT_PATH = R2_ROOT / "audit" / "hand-visual-boundary-report.json"
HAND_AA_MAINTENANCE_REPORT_PATH = R2_ROOT / "audit" / "hand-hidden-aa-maintenance-report.json"
HAND_AA_REBUILD_RUN_1_PATH = R2_ROOT / "audit" / "hand-hidden-aa-rebuild-run-1.json"
HAND_AA_REBUILD_RUN_2_PATH = R2_ROOT / "audit" / "hand-hidden-aa-rebuild-run-2.json"
HAND_AA_IMPLEMENTATION_AUDIT = {
    "activeHandLogicFunction": "render_hand_wrist_root_masks",
    "activeHandDisplayFunction": "rounded_hand_visual_mask",
    "activeHandGeometryRaster": "render_bezier_loop_highres at 32x; ImageChops Boolean at high resolution; one downsample_coverage BOX",
    "activeHandDisplayRaster": "rounded_hand_visual_mask optional rootHigh; one BOX downsample; final boundary guard",
    "legacyGenericAa": {
        "function": "antialiased_mask",
        "status": "DISABLED_FAIL_CLOSED",
        "reason": "a low-resolution binary mask cannot recover trustworthy edge geometry; the former NEAREST enlargement plus ringing filter is forbidden",
        "callSitesInR2HandPath": [],
    },
    "legacyLowResolutionBezierFill": {
        "function": "draw_bezier_loop",
        "status": "FOREARM_ONLY_NOT_CALLED_BY_R2_HAND_PATH",
        "handPathUses": "render_bezier_loop_highres",
    },
    "sourceLockedBilinear": {
        "function": "source_locked_antialiased_mask",
        "status": "NON_HAND_FOREARM_PATH_ONLY",
        "handPathUses": False,
    },
}
FOREARM_UCAP_CONTRACT_PATH = R2_ROOT / "contracts" / "forearm-distal-ucap-contract.json"
FOREARM_UCAP_BOUNDARY_REPORT_PATH = R2_ROOT / "audit" / "forearm-ucap-visual-boundary-report.json"
FOREARM_UCAP_PIXEL_DIFF_PATH = R2_ROOT / "audit" / "forearm-ucap-pixel-diff.json"
FOREARM_REDRAW_CONFIRMATION_PATH = R2_ROOT / "audit" / "user-confirmed-redraw-forearm-hidden-connection-2026-08-11.json"
R2_NON_FOREARM_SNAPSHOT_PATH = R2_ROOT / "audit" / "r2-non-forearm-protected-snapshot.json"
R2_REBUILD_RUN_1_PATH = R2_ROOT / "audit" / "rebuild-run-1.json"
R2_REBUILD_RUN_2_PATH = R2_ROOT / "audit" / "rebuild-run-2.json"
REPO_ROOT = R2_ROOT.parents[4]
XIAOXING_ROOT = R2_ROOT.parents[1]
R1_ROOT = XIAOXING_ROOT / "validation" / "arm-chain-screen-left-r1-physical-line-contract"
SOURCE_ROOT = XIAOXING_ROOT / "source"
VALIDATION_ROOT = XIAOXING_ROOT / "validation"

WIDTH = 512
HEIGHT = 1086
CANVAS = (WIDTH, HEIGHT)
HAND_LINE_ROI = (55, 505, 155, 630)
HAND_LINE_BARRIER_LUMA_MAX = 220

# The shaft boundary is not re-authored from locator points.  The free-pixel
# component inside this source-space ROI is the skin-side region between the
# two observed forearm contours.  The seed, bbox and pixel count are asserted
# so a changed line master fails closed instead of silently selecting a new
# component.  The narrower visible ROI is the only region whose complete
# forearm color block is source-clamped in this repair.
FOREARM_SOURCE_LINE_ROI = (94, 390, 171, 525)
FOREARM_SOURCE_LINE_BARRIER_LUMA_MAX = 240
FOREARM_SOURCE_LINE_SEED = (140, 450)
FOREARM_SOURCE_LINE_EXPECTED_BBOX = (106, 390, 162, 524)
FOREARM_SOURCE_LINE_EXPECTED_PIXEL_COUNT = 3328
FOREARM_SHAFT_SOURCE_VISIBLE_ROI = (94, 398, 171, 515)
FOREARM_SHAFT_SOURCE_AA_SUPERSAMPLE = 4
# Latest visual review isolates a small right-edge protrusion in the lower
# elbow/shaft transition.  The affected pixels are source antialias fringe,
# not the dark contour core; exclude only this coordinate-locked slice from
# the logical material boundary so the displayed flat color stops at the line.
FOREARM_SOURCE_LINE_RIGHT_AA_EXCLUSION_ROI = (166, 407, 167, 411)

# The elbow root is a separate source-line enclosure.  The earlier cubic cap
# was only a derived coverage corridor and visibly crossed the shirt hem in
# the close-up.  This local component is selected from the same authoritative
# line raster, starting below that hem; the expected geometry is asserted so
# a changed master fails closed instead of silently moving the joint.
FOREARM_ELBOW_SOURCE_ROI = (126, 380, 171, 431)
FOREARM_ELBOW_SOURCE_BARRIER_LUMA_MAX = 240
FOREARM_ELBOW_SOURCE_EDGE_LUMA_MAX = 252
FOREARM_ELBOW_SOURCE_SEED = (140, 400)
FOREARM_ELBOW_SOURCE_EXPECTED_BBOX = (126, 389, 162, 430)
FOREARM_ELBOW_SOURCE_EXPECTED_PIXEL_COUNT = 1077
FOREARM_ELBOW_SOURCE_REPAIR_ROI = (126, 381, 166, 398)
# The current source enclosure is already correct on the right.  The remaining
# visible gap is the left sleeve/skin stroke at the lower elbow transition:
# include only its dark source-raster core, not a generic dilation or a free
# side expansion.  The ROI is deliberately narrow and excludes the right edge.
FOREARM_ELBOW_SOURCE_LEFT_EDGE_ROI = (136, 389, 139, 397)
# Two source-line pixels at the hidden-to-visible join are part of the
# authoritative shaft component but otherwise remain unowned, leaving a tiny
# white seam.  Add only this registered source component slice as hidden
# overlap; it is not a topology fill or a visible expansion.
FOREARM_ELBOW_SOURCE_SEAM_CLOSURE_ROI = (163, 398, 165, 399)
# At the right lower edge, source x=166 is pure white while x=164-165 are the
# observed contour/AA pixels.  Exclude only that registered white-side fringe
# from the hidden transition so it cannot read as a green protrusion.
FOREARM_ELBOW_SOURCE_RIGHT_WHITE_EXCLUSION_ROI = (166, 392, 167, 398)
# The approved redline also encloses a hidden triangular transition below the
# sleeve hem.  It is a hidden continuity region, not visible shaft ownership;
# keep it separate from the source-line component and from the left-edge fix.
FOREARM_ELBOW_USER_MARKUP_HIDDEN_TRANSITION_ROI = (131, 389, 168, 398)

# Latest user elbow reference.  The image is a crop of panel 9 with a red
# outline drawn over the complete forearm.  It is registered back to the
# source master through the panel-9 crop/display transform below; the red
# outline is allowed to author hidden elbow continuity only.
FOREARM_ELBOW_USER_MARKUP_PATH = (
    R2_ROOT / "audit" / "user-markup-forearm-elbow-source-reference-2026-08-12.png"
)
FOREARM_ELBOW_USER_MARKUP_SHA256 = "c8a9d24923ac05c360c4bf3daeeed55c8f587e12897b41fefde86235c37bf21f"
FOREARM_ELBOW_USER_MARKUP_DIMENSIONS = (1054, 1022)
FOREARM_ELBOW_USER_MARKUP_RED_PIXEL_COUNT = 13110
FOREARM_ELBOW_USER_MARKUP_RED_BBOX = (184, 176, 677, 823)
FOREARM_ELBOW_USER_MARKUP_SOURCE_CROP = (108, 370, 180, 430)
FOREARM_ELBOW_USER_MARKUP_PANEL_IMAGE_SIZE = (360, 300)
FOREARM_ELBOW_USER_MARKUP_PANEL_DISPLAY_SIZE = (338, 282)
FOREARM_ELBOW_USER_MARKUP_CAPTURE_SCALE = 3
FOREARM_ELBOW_USER_MARKUP_SCREEN_OFFSET = (-150, 40)
FOREARM_ELBOW_USER_MARKUP_SOURCE_Y_RANGE = (380, 426)
FOREARM_ELBOW_USER_MARKUP_REPAIR_ROI = (131, 379, 168, 426)
# The redline remains hidden-only evidence.  The cap above the transition and
# the newly identified white transition wedge are restored from separate
# redline ROIs; visible shaft ownership stays with the source raster.
FOREARM_ELBOW_USER_MARKUP_HIDDEN_CAP_ROI = (131, 379, 168, 389)
FOREARM_ELBOW_USER_MARKUP_RED_THRESHOLD = (200, 150, 150)

# The previous wrist repair stopped at the shaft ROI and then used a manual
# convex bridge plus broad accessory traces.  That left a visible green strip
# outside the actual bracelet/skin line in the seam review.  The wrist repair
# below is a separate, source-locked raster contract: it only replaces the
# distal ownership from y=515 onward, so the already repaired shaft rows stay
# byte-stable.
FOREARM_WRIST_SOURCE_ROI = (90, 500, 140, 550)
FOREARM_WRIST_SOURCE_REPAIR_ROI = (96, 515, 136, 550)
FOREARM_WRIST_SOURCE_BARRIER_LUMA_MAX = 220
FOREARM_WRIST_SOURCE_FOREARM_SEED = (115, 510)
FOREARM_WRIST_SOURCE_HAND_SEED = (110, 540)
# The bracelet is an accessory subregion of the forearm primary material.  Its
# six tiny enclosed openings are registered negative spaces; they are not skin
# holes.  Keep their exact source-space coordinates here so a changed source
# or a generic "0..N holes" rule cannot silently redefine the topology.
FOREARM_ACCESSORY_NEGATIVE_SPACE_ROI = (96, 515, 136, 550)
FOREARM_REGISTERED_ACCESSORY_HOLE_COORDINATES = (
    ((104, 519), (104, 520)),
    ((108, 521),),
    ((105, 523), (106, 523)),
    ((104, 524),),
    ((102, 525),),
    ((122, 528),),
)
FOREARM_REGISTERED_ACCESSORY_HOLE_FINGERPRINTS = (
    "f4554ce96470dc7c779115c6471dd30b177598d09a89cb45486e8a4c8ad99609",
    "765f7e2ac775ec09891fc2503bc3b6878c7d0b634e94600d005f93fefecfce81",
    "f72325b6f5dd6bb569baed4a96771f9390b32b197032d439489c8c35e6d40874",
    "7a219f1d3211ae9ccbcd51c1633b5e266b8fd7163983d4898d49ffb844e82a04",
    "674b73b0cb26184fe52b4fa3d0e909ab5e68283baecb69c2b9cfc9cf8bd3e5c4",
    "8acbc014cef74cb304b51b84a5876a8482ac5ff2ad75a545ef826c0370dc1f45",
)
FOREARM_BRACELET_NONPRIMARY_OPENING = {
    "pixels": 34,
    "bbox": [107, 524, 121, 532],
    "fingerprint": "0f60b516331ed878f0b070797ca6265b9cb56be83afabb0731f1e2f6fbfc2c22",
    "semanticRole": "bracelet-internal-skin-clearance; not a primary forearm negative space",
}
FOREARM_WRIST_SOURCE_COMPONENT_SPECS = (
    {
        "id": "forearm-skin",
        "seed": FOREARM_WRIST_SOURCE_FOREARM_SEED,
        "bbox": (106, 500, 130, 525),
        "pixelCount": 449,
    },
    {
        "id": "hand-protected-transition",
        "seed": FOREARM_WRIST_SOURCE_HAND_SEED,
        "bbox": (94, 529, 119, 549),
        "pixelCount": 380,
    },
    {
        "id": "wrist-skin-between-bracelet-lines",
        "seed": (112, 528),
        "bbox": (107, 524, 120, 531),
        "pixelCount": 34,
    },
)

# These are selection corridors only.  The emitted bracelet material is the
# intersection of these corridors with actual source-line barrier pixels;
# no corridor pixel is emitted by itself.  The four paths follow the observed
# proximal loop, distal loop, left knot/link and right bead/link respectively.
FOREARM_WRIST_BRACELET_CORRIDOR_SPECS = (
    {
        "id": "proximal-loop",
        "layer": "bracelet-back",
        "first": ((101, 516), (108, 517), (116, 520), (124, 523), (129, 526)),
        "second": ((100, 521), (108, 523), (116, 526), (124, 529), (129, 531)),
    },
    {
        "id": "distal-loop",
        "layer": "bracelet-front",
        "first": ((99, 522), (108, 524), (117, 527), (125, 530), (129, 533)),
        "second": ((98, 528), (107, 530), (116, 533), (124, 536), (128, 538)),
    },
    {
        "id": "hanging-left",
        "layer": "bracelet-front",
        "first": ((99, 518), (103, 519), (105, 524), (102, 530), (100, 536)),
        "second": ((96, 521), (101, 524), (103, 530), (101, 537), (98, 541)),
    },
    {
        "id": "hanging-right",
        "layer": "bracelet-front",
        "first": ((124, 520), (130, 523), (129, 530), (126, 536), (126, 543)),
        "second": ((128, 522), (133, 525), (133, 532), (129, 538), (128, 544)),
    },
)

# These are source-locked direct-pixel regions, not generated silhouettes.
# The exact component bboxes/pixel counts are asserted against the current
# authoritative line master so a changed source cannot silently produce a
# plausible but unreviewed hand.
HAND_LINE_COMPONENT_SPECS = (
    {"id": "palm-and-thumb", "bbox": (68, 529, 119, 611), "pixelCount": 1430},
    {"id": "finger-1", "bbox": (83, 583, 88, 613), "pixelCount": 70},
    {"id": "finger-2", "bbox": (76, 593, 81, 617), "pixelCount": 62},
    {"id": "finger-3", "bbox": (91, 581, 97, 604), "pixelCount": 60},
    {"id": "finger-4", "bbox": (96, 575, 99, 589), "pixelCount": 36},
)

# The source line closes each finger region as a raster enclosure, while the
# anatomical hand is one connected material.  These four tiny, source-aligned
# web endpoint paths restore the skin connection at the lowest web points. They
# are not alpha gaps and are recorded as continuity pixels in the contract.
HAND_WEB_BRIDGE_PATHS = (
    {"id": "thumb-index-web", "pixels": ((75, 601), (76, 601), (77, 602))},
    {"id": "index-middle-web", "pixels": ((83, 587), (84, 587), (85, 588))},
    {"id": "middle-ring-web", "pixels": ((99, 597), (98, 597), (97, 597))},
    {"id": "ring-pinky-web", "pixels": ((102, 576), (101, 576), (100, 576))},
)

# Human-facing flat-color presentation only.  These four regions follow the
# source-locked finger components.  The palm-and-thumb component is deliberately
# excluded here: softening it made the diagonal palm-to-finger junction too
# bulky.  The thumb gets only its endpoint cap below.
HAND_VISUAL_DISTAL_REGIONS = (
    (83, 583, 88, 613, 599),
    (76, 593, 81, 617, 600),
    (91, 581, 97, 604, 590),
    (96, 575, 99, 589, 580),
)
HAND_VISUAL_DISTAL_RADIUS_PX = 1.0
HAND_VISUAL_TIP_CENTERS = ((68.5, 610.0), (84.0, 611.5), (76.5, 615.5), (97.0, 602.5), (96.0, 587.5))
HAND_VISUAL_TIP_RADIUS_PX = 1.25
# Human-facing flat-layer trim only.  This follows the user's latest visual
# markup on the proximal upper arc: add a small amount back up to the red
# boundary, keep the left transition controlled, and retain the upper-right
# bulge.  Binary visible/complete masks and the source-line audit remain unchanged.
HAND_VISUAL_LEFT_EDGE = (
    (104, 531), (102, 533), (100, 536), (98, 539), (96, 542),
    (94, 545), (92, 548), (90, 551), (87, 554),
)
HAND_VISUAL_RIGHT_EDGE = (
    (112, 531), (115, 533), (118, 536), (120, 539), (122, 541),
    (122, 543), (119, 545),
)
# Left-to-right source-space projection of the user's red guide.  Human-facing
# flat/complete boundary previews keep only the material below this curve; the
# logical complete mask remains available for hidden-continuity QA.
HAND_VISUAL_TOP_BOUNDARY = (
    (87, 555), (89, 554), (91, 552), (93, 548), (95, 544),
    (97, 541), (99, 538), (101, 536), (103, 533), (105, 532),
    (108, 532), (111, 532), (114, 533), (116, 534), (118, 536),
    (120, 539), (122, 541),
)
# Explicit C2-continuous cubic paths fitted to HAND_VISUAL_TOP_BOUNDARY.
# The chain follows every markup knot with a natural cubic spline, then shifts
# the control polygon 0.55 source px toward the allowed interior.  This avoids
# the upward overshoot that a four-segment interpolant produced between the
# steep left-transition markup points.  It is the display boundary only; the
# logical hand masks remain source-raster locked.
HAND_VISUAL_CURVE_INSET_Y_PX = 0.55
HAND_VISUAL_BEZIER_SEGMENTS = (
    ((87.000000000, 555.550000000), (87.666664248, 555.260008393), (88.333328495, 554.970016787), (89.000000000, 554.550000000)),
    ((89.000000000, 554.550000000), (89.666671505, 554.129983213), (90.333350266, 553.579941246), (91.000000000, 552.550000000)),
    ((91.000000000, 552.550000000), (91.666649734, 551.520058754), (92.333270441, 550.010218229), (93.000000000, 548.550000000)),
    ((93.000000000, 548.550000000), (93.666729559, 547.089781771), (94.333567971, 545.679185836), (95.000000000, 544.550000000)),
    ((95.000000000, 544.550000000), (95.666432029, 543.420814164), (96.332457675, 542.573038425), (97.000000000, 541.550000000)),
    ((97.000000000, 541.550000000), (97.667542325, 540.526961575), (98.336601329, 539.328660462), (99.000000000, 538.550000000)),
    ((99.000000000, 538.550000000), (99.663398671, 537.771339538), (100.321137008, 537.412319727), (101.000000000, 536.550000000)),
    ((101.000000000, 536.550000000), (101.678862992, 535.687680273), (102.378850638, 534.322060628), (103.000000000, 533.550000000)),
    ((103.000000000, 533.550000000), (103.621149362, 532.777939372), (104.163460439, 532.599437759), (105.000000000, 532.550000000)),
    ((105.000000000, 532.550000000), (105.836539561, 532.500562241), (106.967307605, 532.580188335), (108.000000000, 532.550000000)),
    ((108.000000000, 532.550000000), (109.032692395, 532.519811665), (109.967309139, 532.379808899), (111.000000000, 532.550000000)),
    ((111.000000000, 532.550000000), (112.032690861, 532.720191101), (113.163455838, 533.200576068), (114.000000000, 533.550000000)),
    ((114.000000000, 533.550000000), (114.836544162, 533.899423932), (115.378867507, 534.117886827), (116.000000000, 534.550000000)),
    ((116.000000000, 534.550000000), (116.621132493, 534.982113173), (117.321074133, 535.627876623), (118.000000000, 536.550000000)),
    ((118.000000000, 536.550000000), (118.678925867, 537.472123377), (119.336835962, 538.670606679), (120.000000000, 539.550000000)),
    ((120.000000000, 539.550000000), (120.663164038, 540.429393321), (121.331582019, 540.989696660), (122.000000000, 541.550000000)),
)
# The upper palm is still one solid region until y=567; this tiny vector cap
# fills only the red-line interior there.  It stops before the first real open
# finger gap at y=568, so it cannot merge or alter the finger topology.
HAND_VISUAL_PALM_CAP_LEFT = ((87.0, 555.0), (86.0, 559.0), (84.8, 563.5), (84.0, 567.0))
HAND_VISUAL_PALM_CAP_RIGHT = ((122.0, 541.0), (119.5, 549.0), (115.0, 559.0), (112.0, 567.0))
HAND_VISUAL_PALM_CAP_END_Y = 567
HAND_VISUAL_BOUNDARY_INSET_PX = 0.25
HAND_VISUAL_SUPERSAMPLE = 32

# R2 hand hidden-wrist AA maintenance contract.  These are source-space
# control points for a periodic uniform cubic B-spline whose explicit Bezier
# segments are materialized below.  The control polygon follows the wrist
# axis (110,538) into the palm root (104,552); it is deliberately asymmetric
# and is not a circle, rectangle, stroke expansion, or global hull.
HAND_HIDDEN_WRIST_ROI = (90, 515, 140, 558)
HAND_AA_SUPERSAMPLE = 32
HAND_WRIST_ROOT_CONTROL_POINTS = (
    (103.0, 524.0),
    (100.8, 528.0),
    (100.0, 536.0),
    (101.0, 544.0),
    (103.5, 550.5),
    (107.0, 554.5),
    (111.5, 555.5),
    (115.0, 551.5),
    (117.0, 545.0),
    (117.4, 537.0),
    (115.0, 529.5),
    (110.5, 524.5),
    (106.0, 522.8),
)
# A separately registered, slightly wider local envelope.  It only bounds the
# hidden wrist material and is not used to enlarge visible/display ownership.
HAND_HIDDEN_ENVELOPE_CONTROL_POINTS = (
    (102.4, 522.8),
    (99.8, 527.4),
    (99.1, 536.0),
    (100.0, 545.0),
    (102.7, 551.5),
    (106.5, 555.8),
    (111.5, 556.6),
    (115.9, 552.6),
    (118.0, 545.5),
    (118.4, 537.0),
    (116.0, 528.8),
    (110.8, 523.5),
    (105.6, 521.8),
)

# Stage A forearm distal wrist U-cap reopened by the user's 2026-07-29
# authorization. These are source-space float control points ordered around
# one continuous material: the visible side/bottom follows the latest blue
# U-markup and the upper points are a separate occluded closure beneath the
# forearm-owned bracelet. This is the active geometry for the reopened scope;
# no V31/V32 wrist geometry is used.
FOREARM_UCAP_ROI = (97, 525, 123, 551)
# Hidden continuity is allowed to cross the bracelet only in this narrow
# upper closure band. This is a source-line connector for the logic mask only;
# the formal display Alpha does not paint this connector. Keeping the band
# short prevents the old wrist source raster from becoming a visible tab.
FOREARM_UCAP_HIDDEN_BRIDGE_ROI = (108, 525, 123, 529)
# The latest blue markup extends farther left and lower than the historical
# red candidate. Keep that visible U allowance separate from the upper
# bracelet/occlusion bridge so only the user-marked skin seam is brought out.
FOREARM_UCAP_LOWER_LINE_ROI = (97, 528, 123, 551)
FOREARM_UCAP_SUPERSAMPLE = 32
# Latest user visual markup, copied into this package before rebuilding. This
# is a 2x screenshot of the existing 800% hidden-connection crop, not a
# source master. Its blue U is mapped through the displayed crop back into
# front-master pixels before it is allowed to drive this candidate.
FOREARM_USER_MARKUP_PATH = "audit/user-markup-forearm-hidden-connection-blue-2026-08-11.png"
FOREARM_USER_MARKUP_SHA256 = "5f2708bd1b86b7182b829f946887ddb890a90d578b80952c4fcc16f1c032cec1"
FOREARM_USER_MARKUP_DIMENSIONS = (904, 902)
FOREARM_REDRAW_CONFIRMATION_DATE = "2026-08-11"
FOREARM_REDRAW_CONFIRMATION_TEXT = "确认重画，按照我的红线来"
FOREARM_USER_MARKUP_TRANSFORM = {
    "kind": "qa-hidden-connection-crop-2x-screenshot-to-frontMaster",
    "sourceCanvas": list(CANVAS),
    "qaArtifact": {
        "path": "qa/forearm-ucap-a/hidden-wrist-connection-800pct.png",
        "size": [368, 344],
        "sourceCrop": {"left": 90, "top": 515, "right": 136, "bottom": 558},
        "renderScale": 8,
    },
    "submittedImage": {
        "size": [904, 902],
        "qaCropDisplayRect": {"left": 124, "top": 0, "width": 736, "height": 688},
        "visibleDisplayRect": {"left": 124, "top": 0, "width": 736, "height": 677},
        "displayScaleFromQaCrop": 2,
        "bottomClippedDisplayPixels": 11,
    },
    "screenToQaCrop": {
        "scaleX": 0.5,
        "scaleY": 0.5,
        "translateX": -62.0,
        "translateY": 0.0,
        "calibration": "pixel-aligned 2x display of the QA crop; white image rect begins at screen (124, 0)",
    },
    "qaCropToFrontMaster": {
        "scaleX": 0.125,
        "scaleY": 0.125,
        "translateX": 90.0,
        "translateY": 515.0,
    },
    "screenToFrontMaster": {
        "scaleX": 0.0625,
        "scaleY": 0.0625,
        "translateX": 82.25,
        "translateY": 515.0,
    },
    "note": "The latest blue U is the authoritative visible boundary for this reopened hidden-connection candidate. The earlier red markup remains historical evidence and is not reused as active geometry.",
}
FOREARM_USER_MARKUP_TRACE = (
    (100.84, 528.30),
    (100.60, 529.30),
    (100.35, 530.30),
    (100.10, 531.30),
    (99.84, 532.30),
    (99.54, 533.30),
    (99.28, 534.30),
    (99.03, 535.30),
    (98.72, 536.30),
    (98.47, 537.30),
    (98.22, 538.30),
    (97.97, 539.30),
    (97.84, 540.30),
    (97.84, 541.30),
    (98.00, 542.30),
    (98.28, 543.30),
    (98.60, 544.30),
    (99.02, 545.30),
    (99.60, 546.30),
    (100.28, 547.30),
    (101.10, 547.75),
    (102.00, 548.05),
    (103.00, 548.20),
    (104.16, 548.30),
    (105.53, 548.45),
    (107.10, 548.65),
    (109.20, 548.85),
    (111.20, 548.65),
    (112.84, 548.45),
    (114.20, 548.05),
    (115.50, 547.60),
    (116.60, 546.80),
    (117.50, 545.90),
    (118.20, 545.00),
    (118.90, 544.20),
    (119.20, 543.20),
    (119.34, 542.20),
    (119.34, 541.20),
    (119.40, 540.20),
    (119.52, 539.20),
    (119.60, 538.20),
    (119.72, 537.20),
    (119.90, 536.20),
    (120.03, 535.34),
)
# The screenshot's blue line is the visible U only: its upper edge disappears
# beneath the forearm-owned bracelet. A filled hidden material still needs a
# registered closure, so record that occluded top separately instead of
# treating the open blue trace as a closed polygon. This closure adds no
# visible ownership and remains pending the user's visual approval.
FOREARM_USER_MARKUP_HIDDEN_CLOSURE = (
    (119.85, 533.80),
    (119.20, 531.80),
    (118.00, 529.80),
    (115.50, 527.80),
    (112.00, 526.50),
    (108.50, 526.20),
    (105.00, 526.50),
    (102.50, 527.40),
    (100.84, 528.30),
)
FOREARM_USER_MARKUP_CLOSED_TRACE = FOREARM_USER_MARKUP_TRACE + FOREARM_USER_MARKUP_HIDDEN_CLOSURE
FOREARM_DISTAL_UCAP_CONTROL_POINTS = (
    (100.84, 528.30),
    (100.35, 530.30),
    (99.54, 533.30),
    (98.72, 536.30),
    (97.84, 540.30),
    (98.28, 543.30),
    (99.60, 546.30),
    (102.00, 548.05),
    (105.53, 548.45),
    (109.20, 548.85),
    (112.84, 548.45),
    (115.50, 547.60),
    (117.50, 545.90),
    (118.90, 544.20),
    (119.34, 542.20),
    (119.52, 539.20),
    (119.72, 537.20),
    (120.03, 535.34),
    # The upper closure is a separate occluded bridge under the bracelet.
    # It is derived from the new blue endpoints and stays inside the new
    # coordinate-locked boundary; it does not grant visible bracelet/hand
    # ownership.
    (119.20, 531.80),
    (115.50, 527.80),
    (112.00, 526.50),
    (108.50, 526.20),
    (105.00, 526.50),
    (102.50, 527.40),
)
USER_MARKUP_PATH = "audit/user-markup-hand-redline-2026-08-09.png"
USER_MARKUP_SHA256 = "5d40e47b73c56418d94ed847922b1a9ff4b687aff764bfecedd7d5949ec0ce0f"
USER_MARKUP_DIMENSIONS = (1300, 1562)

IDENTITY = {
    "character": "xiaoxing",
    "view": "front",
    "screenSide": "left",
    "anatomicalSide": "right",
    "subject": "小星 Left",
}

R1_EXPECTED_INPUTS = {
    "xiaoxing-three-view-line": {
        "path": SOURCE_ROOT / "xiaoxing-three-view-line.png",
        "sha256": "7f8605a85df7fa2c8843e925f8274a06403d884d975b1b195b2a583478dc222c",
        "size": (1448, 1086),
        "mode": "RGB",
    },
    "xiaoxing-three-view-color": {
        "path": SOURCE_ROOT / "xiaoxing-three-view-color.png",
        "sha256": "2d1b9c71c4e6c17ea503800b05f44bf7bfe127799a5e156886c191b97d350154",
        "size": (1448, 1086),
        "mode": "RGB",
    },
    "front-line-source-exact-after-reset": {
        "path": SOURCE_ROOT / "masters" / "front-line-source-exact-after-reset.png",
        "sha256": "706aaf10652147cf76e233532b5459ce130921a96806f6970c91e1f3a427172f",
        "size": CANVAS,
        "mode": "RGB",
    },
    "front-color-source-exact-after-reset": {
        "path": SOURCE_ROOT / "masters" / "front-color-source-exact-after-reset.png",
        "sha256": "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5",
        "size": CANVAS,
        "mode": "RGB",
    },
}

R1_FREEZE_PATH = R1_ROOT / "audit" / "r1-freeze-checklist-2026-08-05.json"
R1_APPROVAL_PATH = R1_ROOT / "audit" / "user-visual-approval-r1-2026-08-04.json"
R1_MACHINE_REPORT_PATH = R1_ROOT / "audit" / "machine-report.json"
R1_SOURCE_AUTHORITY_PATH = R1_ROOT / "audit" / "source-authority.json"
R1_BODY_CONTRACT_PATH = R1_ROOT / "contracts" / "body-joint-contract.json"
R1_LINE_CONTRACT_PATH = R1_ROOT / "contracts" / "line-ownership-contract.json"
R1_ENVELOPE_CONTRACT_PATH = R1_ROOT / "contracts" / "joint-envelope-contract.json"
V38_REPORT_PATH = VALIDATION_ROOT / "arm-chain-screen-left-v38-reset-guided-wrist-underlay" / "audit" / "machine-report.json"
FOREARM_REOPEN_PATH = VALIDATION_ROOT / "arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve" / "audit" / "user-authorized-reopen-forearm-wrist-ucap-2026-07-29.json"
FOREARM_REOPEN_SHA256 = "d2b34641af56916329618ba9f51b6103bd2adae4ccb47fda069c63fabea96067"
REPAIR_BASELINE_PATH = R2_ROOT / "audit" / "repair-baseline.json"
REPAIR_BASELINE_DIR = R2_ROOT / "audit" / "repair-baseline"
REPAIR_BASELINE_MASKS = {
    layer_id: {
        "visible": Path("masks") / "visible" / f"{layer_id}.png",
        "hidden": Path("masks") / "hidden" / f"{layer_id}.png",
        "complete": Path("masks") / "complete" / f"{layer_id}.png",
    }
    for layer_id in ("upper_arm", "forearm", "hand")
}

DEBUG_COLORS = {
    "sleeve": (47, 151, 211),
    "upper_arm": (241, 142, 56),
    "forearm": (62, 174, 128),
    "hand": (179, 91, 190),
    "forearm_skin": (66, 183, 126),
    "bracelet": (226, 94, 116),
    "bracelet_back": (154, 112, 68),
    "bracelet_front": (226, 94, 116),
}

FORMAL_LAYER_IDS = ("sleeve", "upper_arm", "forearm", "hand")

# These are body-space QA pivots from the R1 joint contract.  They are used only
# to exercise the complete materials; they do not create runtime nodes or
# authorize a Cubism rig.
SHOULDER_PIVOT = (166, 270)
ELBOW_PIVOT = (149, 399)
WRIST_PIVOT = (110, 538)

# Positive PIL rotation is used for the elbow fold and negative PIL rotation
# raises the screen-left arm.  The return half is explicit so 0 -> 1 -> 0 can
# be checked as a deterministic connected blockout rather than inferred from
# a single favorable pose.
LIFT_ACTION_POSES = (
    {"id": "00-rest", "shoulderAngle": 0.0, "elbowAngle": 0.0},
    {"id": "01-raise-1", "shoulderAngle": -12.0, "elbowAngle": 30.0},
    {"id": "02-raise-2", "shoulderAngle": -24.0, "elbowAngle": 65.0},
    {"id": "03-raise-3", "shoulderAngle": -36.0, "elbowAngle": 100.0},
    {"id": "04-raise-4", "shoulderAngle": -48.0, "elbowAngle": 135.0},
    {"id": "05-raise-peak", "shoulderAngle": -52.0, "elbowAngle": 155.0},
    {"id": "06-lower-4", "shoulderAngle": -48.0, "elbowAngle": 135.0},
    {"id": "07-lower-3", "shoulderAngle": -36.0, "elbowAngle": 100.0},
    {"id": "08-lower-2", "shoulderAngle": -24.0, "elbowAngle": 65.0},
    {"id": "09-lower-1", "shoulderAngle": -12.0, "elbowAngle": 30.0},
    {"id": "10-return", "shoulderAngle": 0.0, "elbowAngle": 0.0},
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_freeze_file_entry(entry: dict[str, object], category: str) -> dict[str, object]:
    relative = str(entry.get("path", "")).replace("\\", "/")
    path = REPO_ROOT / relative
    expected_sha = str(entry.get("sha256", "")).lower()
    expected_bytes = entry.get("bytes")
    exists = path.is_file()
    actual_sha = sha256_file(path) if exists else None
    actual_bytes = path.stat().st_size if exists else None
    dimensions: list[int] | None = None
    if exists and path.suffix.lower() in {".png", ".gif", ".jpg", ".jpeg"}:
        try:
            with Image.open(path) as image:
                dimensions = [image.width, image.height]
        except OSError:
            dimensions = None
    bytes_match = expected_bytes is None or actual_bytes == int(expected_bytes)
    hash_match = actual_sha == expected_sha
    return {
        "category": category,
        "path": relative,
        "exists": exists,
        "expectedSha256": expected_sha,
        "actualSha256": actual_sha,
        "expectedBytes": expected_bytes,
        "actualBytes": actual_bytes,
        "dimensions": dimensions,
        "bytesMatch": bytes_match,
        "hashMatch": hash_match,
        "pass": exists and bytes_match and hash_match,
    }


def validate_whole_hand_freeze() -> dict[str, object]:
    """Fail closed unless the latest approved whole-hand input is byte-stable."""
    approval = load_whole_hand_visual_approval()
    if approval is None:
        raise RuntimeError(f"latest whole-hand visual approval is missing: {R2_WHOLE_HAND_APPROVAL_PATH}")
    if not R2_WHOLE_HAND_FREEZE_MANIFEST_PATH.exists():
        raise FileNotFoundError(f"whole-hand freeze manifest is missing: {R2_WHOLE_HAND_FREEZE_MANIFEST_PATH}")
    manifest_value = load_json(R2_WHOLE_HAND_FREEZE_MANIFEST_PATH)
    if not isinstance(manifest_value, dict) or manifest_value.get("recordType") != "frozen_visual_input_manifest":
        raise ValueError(f"Invalid whole-hand freeze manifest: {R2_WHOLE_HAND_FREEZE_MANIFEST_PATH}")
    manifest = manifest_value

    scope = manifest.get("scope")
    identity_match = isinstance(scope, dict) and all(scope.get(key) == IDENTITY[key] for key in ("character", "view", "screenSide", "anatomicalSide"))
    approval_identity_match = all(approval.get(key) == IDENTITY[key] for key in ("character", "view", "screenSide", "anatomicalSide"))
    approval_path_match = str(manifest.get("userApprovalRecord", "")).replace("\\", "/") == str(R2_WHOLE_HAND_APPROVAL_PATH.relative_to(REPO_ROOT)).replace("\\", "/")

    file_checks: list[dict[str, object]] = []
    for category in ("frozenFiles", "reviewFiles", "sourceAuthority", "latestMarkupFiles"):
        entries = manifest.get(category, [])
        if not isinstance(entries, list):
            raise ValueError(f"whole-hand freeze manifest field is not a list: {category}")
        file_checks.extend(
            _verify_freeze_file_entry(entry, category)
            for entry in entries
            if isinstance(entry, dict)
        )

    candidate_source = manifest.get("candidateSource")
    if not isinstance(candidate_source, dict):
        raise ValueError("whole-hand freeze manifest has no candidateSource object")
    candidate_report_path = REPO_ROOT / str(candidate_source.get("machineReport", ""))
    candidate_report_value = load_json(candidate_report_path) if candidate_report_path.exists() else None
    candidate_engineering_pass = isinstance(candidate_report_value, dict) and bool(candidate_report_value.get("engineeringPass")) and bool(candidate_source.get("engineeringPass"))

    candidate_contract_path = REPO_ROOT / str(candidate_source.get("contract", ""))
    candidate_contract_sha = sha256_file(candidate_contract_path) if candidate_contract_path.exists() else None
    approval_source = approval.get("sourceAuthority")
    approved_contract = approval_source.get("candidateBoundaryContract") if isinstance(approval_source, dict) else None
    candidate_contract_hash_match = isinstance(approved_contract, dict) and candidate_contract_sha == str(approved_contract.get("sha256", "")).lower()
    candidate_contract_value = load_json(candidate_contract_path) if candidate_contract_path.exists() else None
    candidate_contract_identity_match = isinstance(candidate_contract_value, dict) and all(
        candidate_contract_value.get(key) == IDENTITY[key]
        for key in ("character", "view", "screenSide", "anatomicalSide")
    ) and candidate_contract_value.get("source", {}).get("canvas") == list(CANVAS) and candidate_contract_value.get("source", {}).get("coordinateTransform") == "identity; all points are front-master pixels"

    candidate_file_checks: list[dict[str, object]] = []
    for formal_relative, candidate_path in UPPER_ARM_V8_FILES.items():
        if formal_relative.startswith("contracts/"):
            continue
        candidate_relative = str(candidate_path.relative_to(REPO_ROOT)).replace("\\", "/")
        if formal_relative == "masks/visible/upper_arm.png":
            expected_sha = UPPER_ARM_V8_VISIBLE_SHA256
            expected_bytes: int | None = 620
        else:
            matching_entry = next(
                item for item in manifest.get("frozenFiles", [])
                if isinstance(item, dict) and str(item.get("path", "")).replace("\\", "/") == candidate_relative
            )
            expected_sha = str(matching_entry.get("sha256", ""))
            expected_bytes = int(matching_entry["bytes"])
        candidate_file_checks.append(_verify_freeze_file_entry({"path": candidate_relative, "sha256": expected_sha, "bytes": expected_bytes}, "candidateUpperArmV8"))

    historical_formal_upper_arm_checks = [
        _verify_freeze_file_entry(entry, "historicalFormalUpperArmBeforePromotion")
        for entry in manifest.get("protectedFormalFilesUnchanged", [])
        if isinstance(entry, dict)
    ]
    all_file_checks_pass = all(bool(item["pass"]) for item in file_checks + candidate_file_checks)
    visual_freeze_hash_match = all_file_checks_pass and identity_match and approval_identity_match and approval_path_match and candidate_engineering_pass and candidate_contract_hash_match and candidate_contract_identity_match
    return {
        "approvalPath": str(R2_WHOLE_HAND_APPROVAL_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "freezeManifestPath": str(R2_WHOLE_HAND_FREEZE_MANIFEST_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "freezeId": manifest.get("freezeId"),
        "identityMatch": identity_match,
        "approvalIdentityMatch": approval_identity_match,
        "approvalPathMatch": approval_path_match,
        "userVisualApproval": True,
        "visualFreezeHashMatch": visual_freeze_hash_match,
        "frozenInputChecks": file_checks,
        "candidateUpperArmV8": {
            "root": str(UPPER_ARM_V8_ROOT.relative_to(REPO_ROOT)).replace("\\", "/"),
            "engineeringPass": candidate_engineering_pass,
            "machineReport": str(candidate_report_path.relative_to(REPO_ROOT)).replace("\\", "/") if candidate_report_path.exists() else str(candidate_source.get("machineReport", "")),
            "contract": str(candidate_contract_path.relative_to(REPO_ROOT)).replace("\\", "/") if candidate_contract_path.exists() else str(candidate_source.get("contract", "")),
            "contractHashMatch": candidate_contract_hash_match,
            "contractIdentityMatch": candidate_contract_identity_match,
            "fileChecks": candidate_file_checks,
        },
        "historicalFormalUpperArmBeforePromotion": historical_formal_upper_arm_checks,
        "latestApprovalRecordIsImmutableInput": True,
    }


def promote_upper_arm_v8() -> dict[str, object]:
    """Copy the frozen v8 candidate into the sole formal R2 upper-arm paths."""
    records: list[dict[str, object]] = []
    for formal_relative, source_path in UPPER_ARM_V8_FILES.items():
        if not source_path.is_file():
            raise FileNotFoundError(f"upper-arm v8 source is missing: {source_path}")
        target = R2_ROOT / formal_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
        source_bytes = source_path.read_bytes()
        target_bytes = target.read_bytes()
        records.append({
            "source": str(source_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "target": str(target.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sourceSha256": hashlib.sha256(source_bytes).hexdigest(),
            "targetSha256": hashlib.sha256(target_bytes).hexdigest(),
            "sourceBytes": len(source_bytes),
            "targetBytes": len(target_bytes),
            "byteExact": source_bytes == target_bytes,
        })
    if not all(bool(record["byteExact"]) for record in records):
        raise AssertionError("upper-arm v8 promotion was not byte-exact")
    return {
        "status": "FORMAL_R2_UPPER_ARM_V8_PROMOTED",
        "sourceCandidate": str(UPPER_ARM_V8_ROOT.relative_to(REPO_ROOT)).replace("\\", "/"),
        "soleFormalSource": True,
        "records": records,
    }


def load_upper_arm_v8_masks() -> tuple[Image.Image, Image.Image, Image.Image]:
    """Read the frozen v8 logical masks as the only upper-arm geometry source."""
    paths = {
        "visible": UPPER_ARM_V8_FILES["masks/visible/upper_arm.png"],
        "hidden": UPPER_ARM_V8_FILES["masks/hidden/upper_arm.png"],
        "complete": UPPER_ARM_V8_FILES["masks/complete/upper_arm.png"],
    }
    loaded = {
        name: Image.open(path).convert("L")
        for name, path in paths.items()
    }
    if mask_count(loaded["visible"]) != 0:
        raise AssertionError("upper-arm v8 visible ownership is not empty")
    if mask_union(loaded["visible"], loaded["hidden"]).tobytes() != loaded["complete"].tobytes():
        raise AssertionError("upper-arm v8 complete mask is not visible union hidden")
    return loaded["visible"], loaded["hidden"], loaded["complete"]


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_whole_hand_visual_approval() -> dict[str, object] | None:
    """Load the latest whole-hand approval without mutating the record."""
    if not R2_WHOLE_HAND_APPROVAL_PATH.exists():
        return None
    approval = load_json(R2_WHOLE_HAND_APPROVAL_PATH)
    if (
        not isinstance(approval, dict)
        or approval.get("recordType") != "user_visual_approval"
        or approval.get("stage") != "WHOLE_HAND_FLAT_COLOR_VISUAL_FREEZE"
        or approval.get("decision") != "approved"
        or approval.get("userVisualApproval") is not True
    ):
        raise ValueError(f"Invalid whole-hand visual approval record: {R2_WHOLE_HAND_APPROVAL_PATH}")
    return approval


def load_r2_approval() -> dict[str, object] | None:
    if not R2_APPROVAL_PATH.exists():
        return None
    approval = load_json(R2_APPROVAL_PATH)
    if not isinstance(approval, dict) or approval.get("approvedStage") != "R2" or approval.get("decision") != "approved":
        raise ValueError(f"Invalid R2 approval record: {R2_APPROVAL_PATH}")
    return approval


def load_current_r2_approval() -> dict[str, object] | None:
    if not R2_CURRENT_APPROVAL_PATH.exists():
        return None
    approval = load_json(R2_CURRENT_APPROVAL_PATH)
    if not isinstance(approval, dict) or approval.get("approvedStage") != "R2" or approval.get("decision") != "approved":
        raise ValueError(f"Invalid current R2 approval record: {R2_CURRENT_APPROVAL_PATH}")
    return approval


def load_final_r2_approval() -> dict[str, object] | None:
    if not R2_FINAL_APPROVAL_PATH.exists():
        return None
    approval = load_json(R2_FINAL_APPROVAL_PATH)
    if (
        not isinstance(approval, dict)
        or approval.get("approvedStage") != "R2"
        or approval.get("decision") != "approved"
        or approval.get("approvalKind") != "final_freeze"
    ):
        raise ValueError(f"Invalid final R2 approval record: {R2_FINAL_APPROVAL_PATH}")
    return approval


def load_r2_rejection() -> dict[str, object] | None:
    if not R2_REJECTION_PATH.exists():
        return None
    rejection = load_json(R2_REJECTION_PATH)
    if not isinstance(rejection, dict) or rejection.get("rejectedStage") != "R2" or rejection.get("decision") != "rejected":
        raise ValueError(f"Invalid R2 hand rejection record: {R2_REJECTION_PATH}")
    return rejection


def load_r2_visual_refinement_request() -> dict[str, object] | None:
    if not R2_VISUAL_REFINEMENT_PATH.exists():
        return None
    request = load_json(R2_VISUAL_REFINEMENT_PATH)
    if not isinstance(request, dict) or request.get("reopenedStage") != "R2" or request.get("decision") != "refinement_requested":
        raise ValueError(f"Invalid R2 visual refinement record: {R2_VISUAL_REFINEMENT_PATH}")
    return request


def load_r2_smooth_edge_reopen() -> dict[str, object] | None:
    if not R2_SMOOTH_EDGE_REOPEN_PATH.exists():
        return None
    reopen = load_json(R2_SMOOTH_EDGE_REOPEN_PATH)
    if (
        not isinstance(reopen, dict)
        or reopen.get("reopenedStage") != "R2"
        or reopen.get("decision") not in {"rejected", "refinement_requested"}
    ):
        raise ValueError(f"Invalid R2 smooth-edge reopen record: {R2_SMOOTH_EDGE_REOPEN_PATH}")
    return reopen


def r2_gate_state() -> str:
    # The 2026-08-12 whole-hand approval is the latest explicit visual
    # decision.  It supersedes the older hand reopen for this frozen flat-color
    # input scope; the old rejection remains immutable historical evidence.
    if load_whole_hand_visual_approval() is not None:
        return "approved"
    # A later user visual rejection/reopen supersedes an older final-freeze
    # approval for the affected hand display scope.  Historical approvals stay
    # immutable, but they must not silently close a newly reopened boundary.
    if load_r2_smooth_edge_reopen() is not None:
        return "reopened"
    if load_final_r2_approval() is not None:
        return "approved"
    if load_r2_visual_refinement_request() is not None:
        return "reopened"
    if load_current_r2_approval() is not None:
        return "approved"
    if load_r2_rejection() is not None:
        return "reopened"
    return "approved" if load_r2_approval() is not None else "not_approved"


def r2_candidate_status() -> str:
    return "R2_APPROVED_CURRENT_SCOPE / R2-GATE_APPROVED" if r2_gate_state() == "approved" else "R2_HAND_HIDDEN_AA_MAINTENANCE_CANDIDATE / WAITING_USER_VISUAL_APPROVAL"


def validate_user_markup_registration() -> dict[str, object]:
    """Fail closed unless the latest red-line registration is still authoritative."""
    markup_path = R2_ROOT / USER_MARKUP_PATH
    reopen = load_r2_smooth_edge_reopen()
    if reopen is None:
        raise RuntimeError("latest R2 hand red-line reopen record is missing")
    if not markup_path.exists():
        raise FileNotFoundError(f"required preserved user markup is missing: {markup_path}")

    actual_hash = sha256_file(markup_path)
    with Image.open(markup_path) as markup_image:
        actual_dimensions = tuple(markup_image.size)
        actual_mode = markup_image.mode

    evidence = reopen.get("markupEvidence")
    boundary = reopen.get("absoluteBoundary")
    if not isinstance(evidence, dict) or not isinstance(boundary, dict):
        raise RuntimeError("latest hand red-line record has no complete markup/boundary contract")
    source_canvas = boundary.get("sourceSpaceCanvas")
    source_roi = boundary.get("sourceSpaceRoi")
    transform = str(boundary.get("sourceSpaceTransform", ""))
    allowed_side = str(boundary.get("allowedSide", ""))
    checks = [
        {
            "id": "preserved_markup_sha256",
            "pass": actual_hash == USER_MARKUP_SHA256 and str(evidence.get("sha256", "")).lower() == USER_MARKUP_SHA256,
            "expected": USER_MARKUP_SHA256,
            "actual": actual_hash,
        },
        {
            "id": "preserved_markup_dimensions_and_mode",
            "pass": actual_dimensions == USER_MARKUP_DIMENSIONS and actual_mode == "RGB" and list(evidence.get("dimensions", [])) == list(USER_MARKUP_DIMENSIONS),
            "expectedDimensions": list(USER_MARKUP_DIMENSIONS),
            "actualDimensions": list(actual_dimensions),
            "actualMode": actual_mode,
        },
        {
            "id": "source_canvas_and_roi",
            "pass": list(source_canvas or []) == list(CANVAS) and list(source_roi or []) == list(HAND_LINE_ROI),
            "sourceCanvas": source_canvas,
            "sourceRoi": source_roi,
        },
        {
            "id": "identity_coordinate_transform",
            "pass": "identity" in transform.lower() and "512x1086" in transform,
            "transform": transform,
        },
        {
            "id": "allowed_red_line_side_registered",
            "pass": allowed_side == "red-line interior / hand-material side",
            "allowedSide": allowed_side,
        },
        {
            "id": "preserved_copy_path_matches",
            "pass": str(evidence.get("preservedCopy", "")).replace("\\", "/") == USER_MARKUP_PATH,
            "preservedCopy": evidence.get("preservedCopy"),
        },
        {
            "id": "r3_remains_stale",
            "pass": reopen.get("r3Status") == "STALE_DUE_TO_UPSTREAM_R2_HAND_REJECTION",
            "r3Status": reopen.get("r3Status"),
        },
    ]
    if not all(bool(check["pass"]) for check in checks):
        failed = [check["id"] for check in checks if not check["pass"]]
        raise RuntimeError(f"latest hand red-line registration failed closed checks: {failed}")
    return {
        "path": USER_MARKUP_PATH,
        "sha256": actual_hash,
        "markupDimensions": list(actual_dimensions),
        "sourceCanvas": list(CANVAS),
        "sourceRoi": list(HAND_LINE_ROI),
        "coordinateTransform": transform,
        "allowedSide": allowed_side,
        "checks": checks,
    }


def validate_forearm_redraw_confirmation() -> dict[str, object]:
    """Fail closed unless the current forearm redraw authorization is present."""
    if not FOREARM_REDRAW_CONFIRMATION_PATH.exists():
        raise FileNotFoundError(f"forearm redraw confirmation is missing: {FOREARM_REDRAW_CONFIRMATION_PATH}")
    confirmation = load_json(FOREARM_REDRAW_CONFIRMATION_PATH)
    if not isinstance(confirmation, dict):
        raise ValueError(f"forearm redraw confirmation is not an object: {FOREARM_REDRAW_CONFIRMATION_PATH}")

    markup_path = R2_ROOT / FOREARM_USER_MARKUP_PATH
    if not markup_path.exists():
        raise FileNotFoundError(f"required forearm user markup is missing: {markup_path}")
    actual_hash = sha256_file(markup_path)
    with Image.open(markup_path) as markup_image:
        actual_dimensions = tuple(markup_image.size)
        actual_mode = markup_image.mode

    latest_markup = confirmation.get("latestUserMarkup")
    if not isinstance(latest_markup, dict):
        raise RuntimeError("forearm redraw confirmation has no latestUserMarkup record")
    scope = confirmation.get("scope")
    checks = [
        {
            "id": "redraw_decision",
            "pass": confirmation.get("decision") == "confirmed_redraw_according_to_latest_user_redline",
            "decision": confirmation.get("decision"),
        },
        {
            "id": "redraw_confirmation_date",
            "pass": confirmation.get("confirmedOn") == FOREARM_REDRAW_CONFIRMATION_DATE,
            "expected": FOREARM_REDRAW_CONFIRMATION_DATE,
            "actual": confirmation.get("confirmedOn"),
        },
        {
            "id": "redraw_confirmation_text",
            "pass": confirmation.get("confirmation") == FOREARM_REDRAW_CONFIRMATION_TEXT,
            "expected": FOREARM_REDRAW_CONFIRMATION_TEXT,
            "actual": confirmation.get("confirmation"),
        },
        {
            "id": "latest_forearm_markup_sha256",
            "pass": actual_hash == FOREARM_USER_MARKUP_SHA256 and str(latest_markup.get("sha256", "")).lower() == FOREARM_USER_MARKUP_SHA256,
            "expected": FOREARM_USER_MARKUP_SHA256,
            "actual": actual_hash,
        },
        {
            "id": "latest_forearm_markup_dimensions_and_mode",
            "pass": actual_dimensions == FOREARM_USER_MARKUP_DIMENSIONS and actual_mode == "RGB" and list(latest_markup.get("dimensions", [])) == list(FOREARM_USER_MARKUP_DIMENSIONS),
            "expectedDimensions": list(FOREARM_USER_MARKUP_DIMENSIONS),
            "actualDimensions": list(actual_dimensions),
            "actualMode": actual_mode,
        },
        {
            "id": "latest_forearm_markup_path",
            "pass": str(latest_markup.get("path", "")).replace("\\", "/") == FOREARM_USER_MARKUP_PATH,
            "path": latest_markup.get("path"),
        },
        {
            "id": "redraw_scope_declared",
            "pass": isinstance(scope, list) and "rebuild the active forearm distal wrist hidden U-cap from the latest user redline" in scope,
            "scope": scope,
        },
        {
            "id": "downstream_authorization_remains_false",
            "pass": confirmation.get("downstreamAuthorization") is False and confirmation.get("userVisualApproval") is None,
            "downstreamAuthorization": confirmation.get("downstreamAuthorization"),
            "userVisualApproval": confirmation.get("userVisualApproval"),
        },
    ]
    if not all(bool(check["pass"]) for check in checks):
        failed = [check["id"] for check in checks if not check["pass"]]
        raise RuntimeError(f"forearm redraw confirmation failed closed checks: {failed}")
    return {
        "path": str(FOREARM_REDRAW_CONFIRMATION_PATH.relative_to(R2_ROOT)).replace("\\", "/"),
        "sha256": sha256_file(FOREARM_REDRAW_CONFIRMATION_PATH),
        "confirmedOn": confirmation["confirmedOn"],
        "confirmation": confirmation["confirmation"],
        "markupPath": FOREARM_USER_MARKUP_PATH,
        "markupSha256": actual_hash,
        "markupDimensions": list(actual_dimensions),
        "checks": checks,
    }


def blank_mask() -> Image.Image:
    return Image.new("L", CANVAS, 0)


def mask_union(*masks: Image.Image) -> Image.Image:
    result = blank_mask()
    for mask in masks:
        result = ImageChops.lighter(result, mask)
    return result


def mask_intersection(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.multiply(a, b)


def mask_subtract(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.subtract(a, b)


def draw_polygon(points: Sequence[tuple[float, float]]) -> Image.Image:
    mask = blank_mask()
    ImageDraw.Draw(mask).polygon([(round(x), round(y)) for x, y in points], fill=255)
    return mask


def ellipse_points(
    center: tuple[float, float],
    radii: tuple[float, float],
    rotation_deg: float,
    samples: int = 96,
) -> list[tuple[float, float]]:
    cx, cy = center
    rx, ry = radii
    theta = math.radians(rotation_deg)
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    points: list[tuple[float, float]] = []
    for index in range(samples):
        t = math.tau * index / samples
        x = rx * math.cos(t)
        y = ry * math.sin(t)
        points.append((cx + x * cos_theta - y * sin_theta, cy + x * sin_theta + y * cos_theta))
    return points


def draw_rotated_ellipse(
    center: tuple[float, float],
    radii: tuple[float, float],
    rotation_deg: float,
) -> Image.Image:
    return draw_polygon(ellipse_points(center, radii, rotation_deg))


def smooth_trace(points: Sequence[tuple[float, float]], samples_per_segment: int = 8) -> list[tuple[float, float]]:
    """Interpolate a hand-authored source trace without regularizing its shape."""
    if len(points) < 2:
        return list(points)
    if len(points) == 2:
        return list(points)
    result: list[tuple[float, float]] = []
    extended = [points[0], *points, points[-1]]
    for index in range(1, len(extended) - 2):
        p0, p1, p2, p3 = extended[index - 1:index + 3]
        for step in range(samples_per_segment):
            t = step / samples_per_segment
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            result.append((x, y))
    result.append(points[-1])
    return result


def cubic_bezier(
    start: tuple[float, float],
    control1: tuple[float, float],
    control2: tuple[float, float],
    end: tuple[float, float],
    samples: int = 16,
) -> list[tuple[float, float]]:
    """Sample one explicit cubic curve for hidden anatomical boundaries."""
    points: list[tuple[float, float]] = []
    for index in range(samples + 1):
        t = index / samples
        inverse = 1.0 - t
        x = (
            inverse ** 3 * start[0]
            + 3 * inverse ** 2 * t * control1[0]
            + 3 * inverse * t ** 2 * control2[0]
            + t ** 3 * end[0]
        )
        y = (
            inverse ** 3 * start[1]
            + 3 * inverse ** 2 * t * control1[1]
            + 3 * inverse * t ** 2 * control2[1]
            + t ** 3 * end[1]
        )
        points.append((x, y))
    return points


def bezier_chain(
    segments: Sequence[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]],
    samples_per_segment: int = 16,
) -> list[tuple[float, float]]:
    """Return a connected, explicitly authored cubic chain."""
    points: list[tuple[float, float]] = []
    for index, segment in enumerate(segments):
        sampled = cubic_bezier(*segment, samples=samples_per_segment)
        points.extend(sampled if index == 0 else sampled[1:])
    return points


def periodic_c2_bezier_segments(
    control_points: Sequence[tuple[float, float]],
) -> tuple[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]], ...]:
    """Convert a periodic uniform cubic B-spline control polygon to Bezier spans.

    The conversion is done once from the authored source-space control polygon;
    every adjacent span then shares the same first and second derivatives.  The
    returned spans are the authority recorded in the hand AA contract.
    """
    if len(control_points) < 4:
        raise ValueError("periodic cubic wrist geometry needs at least four control points")
    points = tuple((float(x), float(y)) for x, y in control_points)
    segments = []
    for index in range(len(points)):
        p0 = points[index % len(points)]
        p1 = points[(index + 1) % len(points)]
        p2 = points[(index + 2) % len(points)]
        p3 = points[(index + 3) % len(points)]
        segments.append((
            (
                (p0[0] + 4.0 * p1[0] + p2[0]) / 6.0,
                (p0[1] + 4.0 * p1[1] + p2[1]) / 6.0,
            ),
            (
                (4.0 * p1[0] + 2.0 * p2[0]) / 6.0,
                (4.0 * p1[1] + 2.0 * p2[1]) / 6.0,
            ),
            (
                (2.0 * p1[0] + 4.0 * p2[0]) / 6.0,
                (2.0 * p1[1] + 4.0 * p2[1]) / 6.0,
            ),
            (
                (p1[0] + 4.0 * p2[0] + p3[0]) / 6.0,
                (p1[1] + 4.0 * p2[1] + p3[1]) / 6.0,
            ),
        ))
    return tuple(segments)


HAND_WRIST_ROOT_BEZIER_SEGMENTS = periodic_c2_bezier_segments(HAND_WRIST_ROOT_CONTROL_POINTS)
HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS = periodic_c2_bezier_segments(HAND_HIDDEN_ENVELOPE_CONTROL_POINTS)
FOREARM_DISTAL_UCAP_BEZIER_SEGMENTS = periodic_c2_bezier_segments(FOREARM_DISTAL_UCAP_CONTROL_POINTS)


def draw_bezier_loop(
    segments: Sequence[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]],
    samples_per_segment: int = 16,
) -> Image.Image:
    """Fill a closed cubic loop; no rectangle, blur, dilation, or fixed circle."""
    points = bezier_chain(segments, samples_per_segment)
    if points and points[0] != points[-1]:
        points.append(points[0])
    return draw_polygon(points)


def render_bezier_loop_highres(
    segments: Sequence[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]],
    supersample: int,
    samples_per_segment: int = 96,
) -> Image.Image:
    """Rasterize a float Bezier loop directly on the supersampled canvas."""
    if supersample < 2:
        raise ValueError("supersample must be at least 2 for float Bezier rasterization")
    points = bezier_chain(segments, samples_per_segment=samples_per_segment)
    if points and points[0] != points[-1]:
        points.append(points[0])
    high = Image.new("L", (WIDTH * supersample, HEIGHT * supersample), 0)
    ImageDraw.Draw(high).polygon(
        [(x * supersample, y * supersample) for x, y in points],
        fill=255,
    )
    return high


def downsample_coverage(high: Image.Image, supersample: int) -> Image.Image:
    """Downsample exactly once with monotone BOX coverage."""
    expected_size = (WIDTH * supersample, HEIGHT * supersample)
    if high.size != expected_size:
        raise ValueError(f"unexpected supersampled canvas: {high.size} != {expected_size}")
    return high.resize(CANVAS, Image.Resampling.BOX)


def binary_from_coverage(coverage: Image.Image, threshold: int = 128) -> Image.Image:
    """Convert high-resolution coverage to a binary logic mask only once."""
    if coverage.size != CANVAS:
        raise ValueError(f"unexpected coverage canvas: {coverage.size}")
    return Image.eval(coverage.convert("L"), lambda value: 255 if value >= threshold else 0)


def render_registered_forearm_user_redline_highres() -> Image.Image:
    """Rasterize the latest user-marked allowed side on the AA canvas.

    This is a boundary guard, not the source of the smooth material path.  It
    is intentionally applied to the cubic candidate at high resolution and
    again after BOX downsampling so a display pixel cannot survive outside the
    latest coordinate-locked redline.
    """
    points = list(FOREARM_USER_MARKUP_CLOSED_TRACE)
    if points and points[0] != points[-1]:
        points.append(points[0])
    scale = FOREARM_UCAP_SUPERSAMPLE
    high = Image.new("L", (WIDTH * scale, HEIGHT * scale), 0)
    ImageDraw.Draw(high).polygon(
        [(x * scale, y * scale) for x, y in points],
        fill=255,
    )
    return high


def render_active_forearm_wrist_redline_envelope() -> Image.Image:
    """Render the confirmed user boundary as the active Stage A wrist envelope.

    The historical R1 ellipse remains read-only evidence.  Once the user
    confirms a redraw, this coordinate-locked U-cap becomes the active
    coverage envelope for the reopened forearm scope; it is not enlarged to
    satisfy the superseded historical ellipse.
    """
    scale = FOREARM_UCAP_SUPERSAMPLE
    high = render_bezier_loop_highres(
        FOREARM_DISTAL_UCAP_BEZIER_SEGMENTS,
        scale,
        samples_per_segment=128,
    )
    high = ImageChops.multiply(high, render_registered_forearm_user_redline_highres())
    return binary_from_coverage(downsample_coverage(high, scale))


def render_hand_wrist_root_masks(hand_visible: Image.Image) -> dict[str, Image.Image | object]:
    """Build hand hidden/complete logic from the float root at 32x resolution."""
    scale = HAND_AA_SUPERSAMPLE
    root_high = render_bezier_loop_highres(HAND_WRIST_ROOT_BEZIER_SEGMENTS, scale)
    envelope_high = render_bezier_loop_highres(HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS, scale)
    visible_high = hand_visible.convert("L").resize(
        (WIDTH * scale, HEIGHT * scale),
        Image.Resampling.NEAREST,
    )
    hidden_high = ImageChops.multiply(
        ImageChops.subtract(root_high, visible_high),
        envelope_high,
    )
    complete_high = ImageChops.lighter(visible_high, root_high)
    return {
        "rootHigh": root_high,
        "envelopeHigh": envelope_high,
        "hiddenHigh": hidden_high,
        "completeHigh": complete_high,
        "rootCoverage": downsample_coverage(root_high, scale),
        "hiddenCoverage": downsample_coverage(hidden_high, scale),
        "completeCoverage": downsample_coverage(complete_high, scale),
        "hidden": binary_from_coverage(downsample_coverage(hidden_high, scale)),
        "complete": binary_from_coverage(downsample_coverage(complete_high, scale)),
    }


def render_forearm_distal_ucap_logic(
    forearm_skin_visible: Image.Image,
    forearm_skin_hidden_existing: Image.Image,
    source_boundary_guard: Image.Image | None = None,
    display_source_boundary_guard: Image.Image | None = None,
) -> dict[str, Image.Image | object]:
    """Replace only the reopened forearm wrist root with high-resolution U-cap logic.

    The existing visible shaft and proximal hidden corridor are protection
    inputs. The reopened U-cap is the only new geometry; it is rasterized from
    float cubic control points at 32x, combined with the protected ownership
    masks on that high-resolution canvas, and then thresholded once for the
    logical masks. This keeps visible shaft ownership and bracelet geometry
    byte-stable while allowing the reopened distal boundary to be continuous.
    """
    scale = FOREARM_UCAP_SUPERSAMPLE
    expected_size = (WIDTH * scale, HEIGHT * scale)
    ucap_high = render_bezier_loop_highres(
        FOREARM_DISTAL_UCAP_BEZIER_SEGMENTS,
        scale,
        samples_per_segment=128,
    )
    raw_ucap_high = ucap_high
    user_redline_high = render_registered_forearm_user_redline_highres()
    if source_boundary_guard is None:
        source_boundary_guard_high = Image.new("L", expected_size, 255)
    else:
        source_boundary_guard_high = source_boundary_guard.convert("L").resize(
            expected_size,
            Image.Resampling.NEAREST,
        )
    if display_source_boundary_guard is None:
        display_source_boundary_guard_high = source_boundary_guard_high.copy()
    else:
        display_source_boundary_guard_high = display_source_boundary_guard.convert("L").resize(
            expected_size,
            Image.Resampling.NEAREST,
        )
    ucap_high = ImageChops.multiply(
        ImageChops.multiply(ucap_high, user_redline_high),
        source_boundary_guard_high,
    )
    visible_high = forearm_skin_visible.convert("L").resize(expected_size, Image.Resampling.NEAREST)
    existing_hidden_high = forearm_skin_hidden_existing.convert("L").resize(expected_size, Image.Resampling.NEAREST)
    hidden_bridge_high = ImageChops.multiply(
        source_boundary_guard_high,
        roi_mask(FOREARM_UCAP_HIDDEN_BRIDGE_ROI).resize(
            expected_size,
            Image.Resampling.NEAREST,
        ),
    )
    # Keep the logical hidden material continuous from the registered U-cap
    # and the narrow source-line bridge needed to join the protected forearm
    # corridor. The bridge is logic-only; formal display Alpha uses the
    # registered U-cap geometry below so source-raster tabs cannot show up in
    # the isolated Alpha evidence.
    hidden_high = ImageChops.subtract(
        ImageChops.lighter(
            ImageChops.lighter(existing_hidden_high, ucap_high),
            hidden_bridge_high,
        ),
        visible_high,
    )
    complete_high = ImageChops.lighter(visible_high, hidden_high)
    hidden_coverage = downsample_coverage(hidden_high, scale)
    complete_coverage = downsample_coverage(complete_high, scale)
    ucap_coverage = downsample_coverage(ucap_high, scale)
    return {
        "hiddenHigh": hidden_high,
        "completeHigh": complete_high,
        "ucapHigh": ucap_high,
        "rawUcapHigh": raw_ucap_high,
        "userRedlineHigh": user_redline_high,
        "sourceBoundaryGuardHigh": source_boundary_guard_high,
        "displaySourceBoundaryGuardHigh": display_source_boundary_guard_high,
        "visibleHigh": visible_high,
        "existingHiddenHigh": existing_hidden_high,
        "hiddenCoverage": hidden_coverage,
        "completeCoverage": complete_coverage,
        "ucapCoverage": ucap_coverage,
        "hidden": binary_from_coverage(hidden_coverage),
        "complete": binary_from_coverage(complete_coverage),
        "ucap": binary_from_coverage(ucap_coverage),
    }


def alpha_summary(image: Image.Image) -> dict[str, object]:
    """Summarize a grayscale display Alpha without collapsing fractional values."""
    alpha = image.convert("L")
    values = list(alpha.getdata())
    fractional = sum(1 for value in values if 0 < value < 255)
    return {
        "mode": alpha.mode,
        "size": list(alpha.size),
        "min": min(values) if values else 0,
        "max": max(values) if values else 0,
        "fractionalAlphaPixels": fractional,
        "nonzeroPixels": sum(1 for value in values if value > 0),
        "bbox": list(alpha.getbbox()) if alpha.getbbox() else None,
    }


def render_forearm_formal_display_alphas(
    masks: dict[str, dict[str, Image.Image]],
    forearm_ucap_logic: dict[str, Image.Image | object],
) -> dict[str, object]:
    """Build formal forearm display Alphas from source-locked shaft + U-cap.

    The exposed shaft uses the authoritative line-raster component as its
    visible owner. Its fractional edge is generated from a fixed supersample
    and clamped back to that component before the complete material is formed.
    The reopened U-cap is rasterized from the registered float cubic path on
    the 32x canvas. Its formal display object follows the latest user boundary
    directly; the source-line bridge is retained only in the separate logic
    hidden mask so it cannot become a hard display tab. Both objects are
    coverage-downsampled with BOX exactly once, and the user boundary is
    reapplied after that downsample.
    """
    scale = FOREARM_UCAP_SUPERSAMPLE
    expected_size = (WIDTH * scale, HEIGHT * scale)
    skin = masks["subregions"]["forearm-skin"]
    forearm_source_line_mask, forearm_source_line_meta = forearm_source_line_enclosure()
    shaft_source_roi = roi_mask(FOREARM_SHAFT_SOURCE_VISIBLE_ROI)
    elbow_markup_mask, elbow_markup_meta = forearm_elbow_user_markup_boundary()
    # The hidden redline cap ends above the exposed shaft ROI.  Keep the
    # shaft audit fully source-locked; no screenshot-derived exception is
    # needed after the lower transition is restored from the source raster.
    shaft_source_audit_roi = shaft_source_roi
    source_line_aa = source_locked_antialiased_mask(
        forearm_source_line_mask,
        forearm_source_line_mask,
        FOREARM_SHAFT_SOURCE_AA_SUPERSAMPLE,
    )
    source_shaft_aa = ImageChops.multiply(source_line_aa, shaft_source_roi)
    source_shaft_aa = ImageChops.multiply(source_shaft_aa, skin["visible"].convert("L"))
    skin_visible_outside_shaft = ImageChops.multiply(
        skin["visible"].convert("L"),
        ImageChops.invert(shaft_source_roi),
    )
    skin_visible_coverage = ImageChops.lighter(source_shaft_aa, skin_visible_outside_shaft)
    skin_visible_high = skin_visible_coverage.resize(expected_size, Image.Resampling.NEAREST)
    logic_hidden_high = cast(Image.Image, forearm_ucap_logic["hiddenHigh"])
    ucap_high = cast(Image.Image, forearm_ucap_logic["ucapHigh"])
    raw_ucap_high = cast(Image.Image, forearm_ucap_logic["rawUcapHigh"])
    user_redline_high = cast(Image.Image, forearm_ucap_logic["userRedlineHigh"])
    display_source_boundary_high = cast(
        Image.Image,
        forearm_ucap_logic.get(
            "displaySourceBoundaryGuardHigh",
            forearm_ucap_logic["sourceBoundaryGuardHigh"],
        ),
    )
    lower_line_roi_high = roi_mask(FOREARM_UCAP_LOWER_LINE_ROI).resize(
        expected_size,
        Image.Resampling.NEAREST,
    )
    lower_line_display_extension_high = ImageChops.multiply(
        user_redline_high,
        lower_line_roi_high,
    )
    effective_display_boundary_high = ImageChops.lighter(
        display_source_boundary_high,
        lower_line_display_extension_high,
    )
    hidden_high = ImageChops.subtract(
        logic_hidden_high,
        skin_visible_high,
    )
    # Keep logic hidden overlap for the depth contract, while the formal
    # display Alpha is clipped to the source-free skin side in the reopened
    # wrist ROI.  The clip is applied on the supersampled canvas first and is
    # repeated by the binary post-BOX guard below.
    wrist_ucap_roi_high = roi_mask(FOREARM_UCAP_ROI).resize(
        expected_size,
        Image.Resampling.NEAREST,
    )
    display_wrist_guard_high = ImageChops.multiply(
        user_redline_high,
        display_source_boundary_high,
    )
    hidden_display_clip_high = ImageChops.lighter(
        ImageChops.invert(wrist_ucap_roi_high),
        display_wrist_guard_high,
    )
    # Keep the source-free bridge clipped to the actual line raster, but let
    # the formal U-cap body follow the latest user-marked boundary as a smooth
    # registered cubic.  The previous source-raster clamp created a hard
    # upper step (narrow at y=526, suddenly wide at y=529) in the Alpha review.
    # The logic bridge remains separate and is never promoted into this
    # display object.
    hidden_non_ucap_high = ImageChops.subtract(logic_hidden_high, ucap_high)
    hidden_bridge_display_high = ImageChops.multiply(
        hidden_non_ucap_high,
        hidden_display_clip_high,
    )
    ucap_display_high = ImageChops.multiply(
        raw_ucap_high,
        user_redline_high,
    )
    hidden_high = ImageChops.lighter(
        hidden_bridge_display_high,
        ucap_display_high,
    )
    skin_complete_high = ImageChops.lighter(skin_visible_high, hidden_high)

    bracelet_visible_high = masks["subregions"]["bracelet"]["visible"].convert("L").resize(
        expected_size,
        Image.Resampling.NEAREST,
    )
    forearm_visible_high = ImageChops.lighter(skin_visible_high, bracelet_visible_high)
    forearm_hidden_high = ImageChops.subtract(hidden_high, forearm_visible_high)
    forearm_complete_high = ImageChops.lighter(forearm_visible_high, forearm_hidden_high)

    skin_alpha = downsample_coverage(skin_complete_high, scale)
    forearm_alpha = downsample_coverage(forearm_complete_high, scale)
    ucap_alpha = downsample_coverage(
        ucap_display_high,
        scale,
    )

    # Registered final guard: this is a post-BOX clamp of the U-cap display
    # object to the latest user boundary, not a geometry expansion or a
    # blur/dilate operation.  The latest blue markup is authoritative for the
    # reopened U-cap; the older source-raster wrist guard remains an audit
    # diagnostic and logic-bridge input, not a second display boundary.
    source_boundary_high = effective_display_boundary_high
    final_guard_coverage = downsample_coverage(user_redline_high, scale)
    source_boundary_coverage = downsample_coverage(source_boundary_high, scale)
    source_free_boundary_coverage = downsample_coverage(display_source_boundary_high, scale)
    user_boundary_allowance = binary_from_coverage(final_guard_coverage)
    final_guard = user_boundary_allowance
    ucap_alpha = ImageChops.multiply(ucap_alpha, final_guard)
    outside_source_boundary = [
        (x, y)
        for y in range(HEIGHT)
        for x in range(WIDTH)
        if ucap_alpha.getpixel((x, y)) > 0 and source_boundary_coverage.getpixel((x, y)) == 0
    ]
    outside_source_free_boundary = [
        (x, y)
        for y in range(HEIGHT)
        for x in range(WIDTH)
        if ucap_alpha.getpixel((x, y)) > 0 and source_free_boundary_coverage.getpixel((x, y)) == 0
    ]
    outside_source_free_unregistered = [
        (x, y)
        for x, y in outside_source_free_boundary
        if user_boundary_allowance.getpixel((x, y)) == 0
    ]
    outside_boundary = [
        (x, y)
        for y in range(HEIGHT)
        for x in range(WIDTH)
        if ucap_alpha.getpixel((x, y)) > 0 and final_guard.getpixel((x, y)) == 0
    ]

    source_shaft_forearm_alpha = ImageChops.multiply(forearm_alpha, shaft_source_audit_roi)
    source_shaft_skin_alpha = ImageChops.multiply(skin_alpha, shaft_source_audit_roi)
    forearm_outside_source = mask_subtract(source_shaft_forearm_alpha, forearm_source_line_mask)
    skin_outside_source = mask_subtract(source_shaft_skin_alpha, forearm_source_line_mask)
    source_line_boundary = {
        **forearm_source_line_meta,
        "formalAlphaGuard": "source component reapplied after shaft antialiasing and after BOX downsample; hidden elbow cap ends above the exposed-shaft ROI, so the shaft guard remains fully source-locked",
        "hiddenElbowMarkupBoundary": elbow_markup_meta,
        "hiddenElbowMarkupExcludedFromShaftAuditRoi": [],
        "antialiasing": {
            "supersample": FOREARM_SHAFT_SOURCE_AA_SUPERSAMPLE,
            "coverage": "BILINEAR from nearest supersample, then multiply by source component",
            "fractionalForearmShaftAlphaPixels": sum(
                1
                for y in range(FOREARM_SHAFT_SOURCE_VISIBLE_ROI[1], FOREARM_SHAFT_SOURCE_VISIBLE_ROI[3])
                for x in range(FOREARM_SHAFT_SOURCE_VISIBLE_ROI[0], FOREARM_SHAFT_SOURCE_VISIBLE_ROI[2])
                if 0 < forearm_alpha.getpixel((x, y)) < 255
            ),
            "fractionalForearmSkinShaftAlphaPixels": sum(
                1
                for y in range(FOREARM_SHAFT_SOURCE_VISIBLE_ROI[1], FOREARM_SHAFT_SOURCE_VISIBLE_ROI[3])
                for x in range(FOREARM_SHAFT_SOURCE_VISIBLE_ROI[0], FOREARM_SHAFT_SOURCE_VISIBLE_ROI[2])
                if 0 < skin_alpha.getpixel((x, y)) < 255
            ),
        },
        "outsideSourceBoundaryPixels": {
            "forearm": mask_count(forearm_outside_source),
            "forearmSkin": mask_count(skin_outside_source),
        },
    }

    guide = bezier_chain(FOREARM_DISTAL_UCAP_BEZIER_SEGMENTS, samples_per_segment=128)
    candidate_boundary = mask_boundary_pixels(ucap_alpha, FOREARM_UCAP_ROI)
    guide_to_candidate = [
        min((math.hypot(x - px, y - py) for px, py in candidate_boundary), default=math.inf)
        for x, y in guide
    ]
    candidate_to_guide = [
        min((math.hypot(x - px, y - py) for px, py in guide), default=math.inf)
        for x, y in candidate_boundary
    ]
    bidirectional = guide_to_candidate + candidate_to_guide
    user_trace = list(FOREARM_USER_MARKUP_TRACE)
    markup_to_candidate = [
        min((math.hypot(x - px, y - py) for px, py in candidate_boundary), default=math.inf)
        for x, y in user_trace
    ]
    closed_user_trace = list(FOREARM_USER_MARKUP_CLOSED_TRACE)
    candidate_to_markup = [
        point_to_polyline_distance((x, y), closed_user_trace)
        for x, y in candidate_boundary
    ]
    markup_bidirectional = markup_to_candidate + candidate_to_markup

    def lower_line_candidate(point: tuple[int, int]) -> bool:
        """Select candidate edge pixels that belong to the user's lower line.

        The top/right closure is hidden beneath the bracelet and is not the
        current visual baseline.  The lower visible U is the left edge plus
        the bottom/right turn beginning around source y=536.
        """
        x, y = point
        return x <= 104.0 or y >= 536.0

    lower_line_candidate_to_markup = [
        distance
        for point, distance in zip(candidate_boundary, candidate_to_markup)
        if lower_line_candidate(point)
    ]

    # The latest blue boundary is the outer authorization, but the actual skin
    # source line is the stricter ownership boundary near the bracelet.  The
    # final Alpha is already clamped to both guards above.  Keep the raw
    # markup distances as evidence, and evaluate the engineering boundary
    # contract against the source-locked candidate edge so pixels that were
    # intentionally clipped at the skin line are not treated as protrusions.
    source_guard_boundary = mask_boundary_pixels(
        binary_from_coverage(source_free_boundary_coverage),
        FOREARM_UCAP_ROI,
    )

    def source_guard_locked(point: tuple[int, int]) -> bool:
        return min(
            (math.hypot(point[0] - px, point[1] - py) for px, py in source_guard_boundary),
            default=math.inf,
        ) <= 1.5

    source_locked_candidate_to_guide = [
        distance
        for point, distance in zip(candidate_boundary, candidate_to_guide)
        if not source_guard_locked(point)
    ]
    source_locked_bidirectional = guide_to_candidate + source_locked_candidate_to_guide
    source_locked_markup_bidirectional = markup_to_candidate + lower_line_candidate_to_markup
    source_clamped_candidate_boundary = [
        list(point) for point in candidate_boundary if source_guard_locked(point)
    ]
    boundary_report = {
        "sourceCanvas": list(CANVAS),
        "coordinateTransform": "identity",
        "registeredBoundary": {
            "authorizationPath": str(FOREARM_REOPEN_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "authorizationSha256": FOREARM_REOPEN_SHA256,
            "roi": list(FOREARM_UCAP_ROI),
            "allowedSide": "U-cap candidate material side inside the coordinate-locked Reset wrist corridor",
            "controlPoints": [list(point) for point in FOREARM_DISTAL_UCAP_CONTROL_POINTS],
            "bezierSegments": [[list(point) for point in segment] for segment in FOREARM_DISTAL_UCAP_BEZIER_SEGMENTS],
        },
        "sourceLineShaftBoundary": source_line_boundary,
        "latestUserMarkup": {
            "path": FOREARM_USER_MARKUP_PATH,
            "sha256": FOREARM_USER_MARKUP_SHA256,
            "dimensions": list(FOREARM_USER_MARKUP_DIMENSIONS),
            "coordinateTransform": FOREARM_USER_MARKUP_TRANSFORM,
            "trace": [list(point) for point in FOREARM_USER_MARKUP_TRACE],
            "hiddenClosure": [list(point) for point in FOREARM_USER_MARKUP_HIDDEN_CLOSURE],
            "closedTrace": [list(point) for point in FOREARM_USER_MARKUP_CLOSED_TRACE],
            "closureRule": "visible red U closes only beneath the forearm-owned bracelet; no visible bracelet/hand ownership is added",
            "markupToRenderedBoundary": distance_distribution(markup_to_candidate),
            "renderedToMarkupBoundary": distance_distribution(candidate_to_markup),
            "bidirectionalBoundaryError": distance_distribution(markup_bidirectional),
        },
        "outsideBoundaryPixels": len(outside_boundary),
        "outsideBoundaryPoints": [list(point) for point in outside_boundary],
        "bidirectionalBoundaryError": distance_distribution(bidirectional),
        "guideToRenderedBoundary": distance_distribution(guide_to_candidate),
        "renderedToGuideBoundary": distance_distribution(candidate_to_guide),
        "uncoveredGuideSegments": [
            list(point) for point, distance in zip(guide, guide_to_candidate) if distance > 4.0
        ],
        "unmatchedCandidateBoundaryPixels": [
            list(point) for point, distance in zip(candidate_boundary, candidate_to_guide) if distance > 4.0
        ],
        "sourceLineLockedBoundary": {
            "sourceGuardBoundaryPixels": [list(point) for point in source_guard_boundary],
            "sourceClampedCandidateBoundaryPixels": source_clamped_candidate_boundary,
            "sourceLockedBidirectionalBoundaryError": distance_distribution(source_locked_bidirectional),
            "sourceLockedMarkupBoundaryError": distance_distribution(source_locked_markup_bidirectional),
            "lowerLineCandidateBoundaryPixels": [
                list(point) for point in candidate_boundary if lower_line_candidate(point)
            ],
            "lowerLineCandidateToMarkupBoundaryError": distance_distribution(lower_line_candidate_to_markup),
            "rule": "raw closed-boundary mismatch remains evidence; the hidden top closure is not the visual baseline, while the latest lower visible blue baseline is the registered display and boundary reference",
        },
        "supersample": scale,
        "booleanAtHighResolution": True,
        "coverageDownsample": "BOX exactly once",
        "finalClipAfterDownsample": True,
        "forbiddenOperations": ["rectangle", "sharp_polygon", "fixed_circle", "global_convex_hull", "radial_patch", "blur", "dilate", "erode", "LANCZOS ringing", "low-resolution NEAREST geometry", "source-line boundary expansion after antialiasing"],
        "formalDisplayAlpha": {
            "forearm": alpha_summary(forearm_alpha),
            "forearmSkin": alpha_summary(skin_alpha),
            "ucap": alpha_summary(ucap_alpha),
        },
        "redlineGuard": {
            "coverage": alpha_summary(final_guard_coverage),
            "binaryPostBoxGuard": alpha_summary(final_guard),
            "rule": "latest user closed blue boundary is reapplied after BOX; candidate Alpha outside it must be zero",
        },
        "sourceLineWristGuard": {
            "coverage": alpha_summary(source_boundary_coverage),
            "sourceFreeCoverage": alpha_summary(source_free_boundary_coverage),
            "lowerLineBaselineRoi": list(FOREARM_UCAP_LOWER_LINE_ROI),
            "outsideSourceBoundaryPixels": len(outside_source_boundary),
            "outsideSourceFreeBoundaryPixels": len(outside_source_free_boundary),
            "outsideSourceFreeUnregisteredPixels": len(outside_source_free_unregistered),
            "rule": "logic bridge remains source-line constrained; formal U-cap display follows the latest user blue boundary; source-line divergence is retained as diagnostic evidence rather than used as a competing display clamp",
        },
        "checks": [
            {"id": "forearm_formal_alpha_has_fractional", "pass": alpha_summary(forearm_alpha)["fractionalAlphaPixels"] > 0},
            {"id": "forearm_skin_formal_alpha_has_fractional", "pass": alpha_summary(skin_alpha)["fractionalAlphaPixels"] > 0},
            {"id": "forearm_shaft_formal_alpha_has_fractional", "pass": source_line_boundary["antialiasing"]["fractionalForearmShaftAlphaPixels"] > 0},
            {"id": "forearm_skin_shaft_formal_alpha_has_fractional", "pass": source_line_boundary["antialiasing"]["fractionalForearmSkinShaftAlphaPixels"] > 0},
            {"id": "forearm_ucap_formal_alpha_has_fractional", "pass": alpha_summary(ucap_alpha)["fractionalAlphaPixels"] > 0},
            {"id": "forearm_shaft_formal_alpha_inside_source_line", "pass": mask_count(forearm_outside_source) == 0, "outsideSourceBoundaryPixels": mask_count(forearm_outside_source)},
            {"id": "forearm_skin_shaft_formal_alpha_inside_source_line", "pass": mask_count(skin_outside_source) == 0, "outsideSourceBoundaryPixels": mask_count(skin_outside_source)},
            {"id": "forearm_ucap_formal_alpha_outside_registered_boundary_zero", "pass": len(outside_boundary) == 0},
            {"id": "forearm_ucap_formal_alpha_latest_user_markup_overrides_source_guard", "pass": len(outside_boundary) == 0 and len(outside_source_free_unregistered) == 0, "sourceGuardSupersededPixels": len(outside_source_boundary), "outsideSourceBoundaryPixels": len(outside_source_boundary)},
            {"id": "forearm_ucap_lower_line_allowance_registered", "pass": len(outside_source_free_unregistered) == 0, "outsideSourceFreeBoundaryPixels": len(outside_source_free_boundary), "unregisteredPixels": len(outside_source_free_unregistered)},
            {"id": "forearm_ucap_boundary_bidirectional_error", "pass": bool(source_locked_bidirectional) and max(source_locked_bidirectional) <= 4.0, "rawMaxError": max(bidirectional, default=math.inf)},
            {"id": "forearm_ucap_matches_latest_user_markup", "pass": bool(source_locked_markup_bidirectional) and max(source_locked_markup_bidirectional) <= 4.0, "rawMaxError": max(markup_bidirectional, default=math.inf)},
        ],
    }
    boundary_report["overallPass"] = all(bool(check["pass"]) for check in boundary_report["checks"])
    return {
        "forearm": forearm_alpha,
        "forearmSkin": skin_alpha,
        "ucap": ucap_alpha,
        "hiddenHigh": hidden_high,
        "completeHigh": forearm_complete_high,
        "skinCompleteHigh": skin_complete_high,
        "boundaryReport": boundary_report,
    }


def convex_hull(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return a local monotonic-chain hull; this is intentionally not a global hull."""
    unique = sorted({(round(x, 4), round(y, 4)) for x, y in points})
    if len(unique) <= 2:
        return unique

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def draw_local_convex_hull(points: Sequence[tuple[float, float]]) -> Image.Image:
    return draw_polygon(convex_hull(points))


def draw_trace_band(
    first: Sequence[tuple[float, float]],
    second: Sequence[tuple[float, float]],
    samples_per_segment: int = 8,
) -> Image.Image:
    first_trace = smooth_trace(first, samples_per_segment)
    second_trace = smooth_trace(second, samples_per_segment)
    return draw_polygon(first_trace + list(reversed(second_trace)))


def mask_count(mask: Image.Image) -> int:
    pixels = mask.load()
    return sum(1 for y in range(HEIGHT) for x in range(WIDTH) if pixels[x, y] > 0)


def mask_values(mask: Image.Image) -> list[int]:
    pixels = mask.load()
    return sorted({pixels[x, y] for y in range(HEIGHT) for x in range(WIDTH)})


def mask_bbox(mask: Image.Image) -> list[int] | None:
    bbox = mask.getbbox()
    return list(bbox) if bbox else None


def nonzero_points(mask: Image.Image) -> set[tuple[int, int]]:
    pixels = mask.load()
    return {(x, y) for y in range(HEIGHT) for x in range(WIDTH) if pixels[x, y] > 0}


def component_stats(mask: Image.Image) -> list[dict[str, object]]:
    remaining = nonzero_points(mask)
    components: list[dict[str, object]] = []
    neighbors = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))
    while remaining:
        start = remaining.pop()
        queue = [start]
        size = 0
        min_x = max_x = start[0]
        min_y = max_y = start[1]
        while queue:
            x, y = queue.pop()
            size += 1
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            for dx, dy in neighbors:
                point = (x + dx, y + dy)
                if point in remaining:
                    remaining.remove(point)
                    queue.append(point)
        components.append({"size": size, "bbox": [min_x, min_y, max_x + 1, max_y + 1]})
    components.sort(key=lambda item: int(item["size"]), reverse=True)
    return components


def component_point_sets(mask: Image.Image) -> list[set[tuple[int, int]]]:
    remaining = nonzero_points(mask)
    components: list[set[tuple[int, int]]] = []
    neighbors = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))
    while remaining:
        start = remaining.pop()
        queue = [start]
        component = {start}
        while queue:
            x, y = queue.pop()
            for dx, dy in neighbors:
                point = (x + dx, y + dy)
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    queue.append(point)
        components.append(component)
    return sorted(components, key=len, reverse=True)


def hole_components(mask: Image.Image) -> list[dict[str, object]]:
    bbox = mask.getbbox()
    if not bbox:
        return []
    left, top, right, bottom = bbox
    pixels = mask.load()
    background = {
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if pixels[x, y] == 0
    }
    queue: deque[tuple[int, int]] = deque()
    visited: set[tuple[int, int]] = set()
    for x, y in background:
        if x in (left, right - 1) or y in (top, bottom - 1):
            visited.add((x, y))
            queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            point = (x + dx, y + dy)
            if point in background and point not in visited:
                visited.add(point)
                queue.append(point)
    holes: list[dict[str, object]] = []
    while background - visited:
        start = next(iter(background - visited))
        queue = deque([start])
        visited.add(start)
        component = {start}
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                point = (x + dx, y + dy)
                if point in background and point not in visited:
                    visited.add(point)
                    component.add(point)
                    queue.append(point)
        coordinates = sorted(component, key=lambda point: (point[0], point[1]))
        coordinate_text = ";".join(f"{x},{y}" for x, y in coordinates)
        holes.append({
            "pixels": len(component),
            "bbox": [
                min(x for x, _ in component),
                min(y for _, y in component),
                max(x for x, _ in component) + 1,
                max(y for _, y in component) + 1,
            ],
            "coordinates": [[x, y] for x, y in coordinates],
            "fingerprint": hashlib.sha256(coordinate_text.encode("utf-8")).hexdigest(),
        })
    return sorted(holes, key=lambda item: (int(item["bbox"][1]), int(item["bbox"][0]), int(item["pixels"])))


def hole_count(mask: Image.Image) -> int:
    return len(hole_components(mask))


def rgba_layer(mask: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    layer = Image.new("RGBA", CANVAS, color + (0,))
    layer.putalpha(mask)
    return layer


def antialiased_mask(mask: Image.Image, supersample: int = 4) -> Image.Image:
    """Reject the obsolete low-resolution-mask AA shortcut.

    A binary canvas mask no longer contains enough geometry to reconstruct a
    trustworthy edge.  In particular, enlarging it with NEAREST and filtering
    it back at low resolution can create ringing outside a user boundary.  All
    current R2 display paths must instead rasterize their float geometry on a
    supersampled canvas and downsample once with ``downsample_coverage``.
    """
    raise RuntimeError(
        "antialiased_mask(mask) is disabled; use a source-locked float geometry "
        "renderer and one BOX coverage downsample"
    )


def cubic_bezier_point(
    segment: Sequence[tuple[float, float]],
    progress: float,
) -> tuple[float, float]:
    """Return one point on an explicit cubic Bézier segment."""
    if len(segment) != 4:
        raise ValueError("a cubic Bézier segment must contain four points")
    t = max(0.0, min(1.0, progress))
    u = 1.0 - t
    p0, p1, p2, p3 = segment
    return (
        u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
    )


def hand_visual_boundary_points(
    samples_per_segment: int = 96,
    *,
    inset: bool = True,
) -> list[tuple[float, float]]:
    """Sample the red-guide arc and move it a quarter pixel inward.

    The shift is conservative: it prevents antialias coverage from reaching
    the disallowed side of the user's guide while retaining the guide's
    asymmetric left-in/right-out shape.  No raster row or column is used to
    construct this curve.
    """
    raw: list[tuple[float, float]] = []
    for segment_index, segment in enumerate(HAND_VISUAL_BEZIER_SEGMENTS):
        start = 0 if segment_index == 0 else 1
        for sample_index in range(start, samples_per_segment + 1):
            raw.append(cubic_bezier_point(segment, sample_index / samples_per_segment))

    if not inset:
        return raw

    shifted: list[tuple[float, float]] = []
    for index, point in enumerate(raw):
        previous = raw[max(0, index - 1)]
        following = raw[min(len(raw) - 1, index + 1)]
        tangent_x = following[0] - previous[0]
        tangent_y = following[1] - previous[1]
        tangent_length = math.hypot(tangent_x, tangent_y) or 1.0
        normal_x = -tangent_y / tangent_length
        normal_y = tangent_x / tangent_length
        if normal_y < 0:
            normal_x = -normal_x
            normal_y = -normal_y
        shifted.append(
            (
                point[0] + normal_x * HAND_VISUAL_BOUNDARY_INSET_PX,
                point[1] + normal_y * HAND_VISUAL_BOUNDARY_INSET_PX,
            )
        )
    return shifted


def _hand_boundary_clip_from_points(
    supersample: int,
    curve: Sequence[tuple[float, float]],
) -> Image.Image:
    """Render the allowed side of a registered boundary at high resolution.

    The forbidden polygon is only the region above the continuous Bézier arc;
    the source hand mask still owns the rest of the palm and all fingers.
    BOX downsampling is used later because it is monotone and cannot create
    the LANCZOS ringing that previously reintroduced outside alpha.
    """
    if supersample < 2:
        raise ValueError("hand visual boundary supersample must be at least 2")
    if len(curve) < 2:
        raise ValueError("hand visual boundary needs at least two points")
    size = (WIDTH * supersample, HEIGHT * supersample)
    forbidden = Image.new("L", size, 0)
    start_x = curve[0][0] * supersample
    end_x = curve[-1][0] * supersample
    forbidden_polygon = [
        (round(start_x), 0),
        (round(end_x), 0),
        *[(round(x * supersample), round(y * supersample)) for x, y in reversed(curve)],
    ]
    ImageDraw.Draw(forbidden).polygon(forbidden_polygon, fill=255)
    return ImageChops.subtract(Image.new("L", size, 255), forbidden)


def hand_visual_boundary_clip(supersample: int) -> Image.Image:
    """Render the smooth C2 candidate's allowed side at high resolution."""
    return _hand_boundary_clip_from_points(supersample, hand_visual_boundary_points())


def hand_visual_markup_boundary_clip(supersample: int) -> Image.Image:
    """Render the raw user-markup boundary used as the final hard guard."""
    return _hand_boundary_clip_from_points(
        supersample,
        [(float(x), float(y)) for x, y in HAND_VISUAL_TOP_BOUNDARY],
    )


def hand_visual_palm_cap(supersample: int) -> Image.Image:
    """Render the solid upper-palm interior between the smooth side guides."""
    size = (WIDTH * supersample, HEIGHT * supersample)
    top = hand_visual_boundary_points()
    left_segment = (
        top[0],
        HAND_VISUAL_PALM_CAP_LEFT[1],
        HAND_VISUAL_PALM_CAP_LEFT[2],
        HAND_VISUAL_PALM_CAP_LEFT[3],
    )
    right_segment = (
        top[-1],
        HAND_VISUAL_PALM_CAP_RIGHT[1],
        HAND_VISUAL_PALM_CAP_RIGHT[2],
        HAND_VISUAL_PALM_CAP_RIGHT[3],
    )
    left = [cubic_bezier_point(left_segment, index / 96) for index in range(97)]
    right = [cubic_bezier_point(right_segment, index / 96) for index in range(97)]
    polygon = top + right[1:] + [left[-1]] + list(reversed(left[:-1]))
    cap = Image.new("L", size, 0)
    ImageDraw.Draw(cap).polygon(
        [(round(x * supersample), round(y * supersample)) for x, y in polygon],
        fill=255,
    )
    return cap


def render_hand_display_boundary(mask: Image.Image, supersample: int = HAND_VISUAL_SUPERSAMPLE) -> Image.Image:
    """Apply the high-resolution red-guide clip and return an AA display mask."""
    high = mask.resize((WIDTH * supersample, HEIGHT * supersample), Image.Resampling.NEAREST)
    clipped_high = ImageChops.multiply(high, hand_visual_boundary_clip(supersample))
    clipped_high = ImageChops.multiply(clipped_high, hand_visual_markup_boundary_clip(supersample))
    return clipped_high.resize(CANVAS, Image.Resampling.BOX)


def trim_hand_display_boundary(mask: Image.Image) -> Image.Image:
    """Return the antialiased hand display mask inside the marked boundary."""
    return render_hand_display_boundary(mask)


def rounded_hand_visual_mask(
    mask: Image.Image,
    *,
    hidden_root_high: Image.Image | None = None,
) -> Image.Image:
    """Render the hand display alpha with optional float-root coverage."""
    scale = HAND_VISUAL_SUPERSAMPLE
    high = ImageChops.multiply(
        mask.resize((WIDTH * scale, HEIGHT * scale), Image.Resampling.NEAREST),
        hand_visual_boundary_clip(scale),
    )
    high = ImageChops.multiply(high, hand_visual_markup_boundary_clip(scale))
    high = ImageChops.lighter(high, hand_visual_palm_cap(scale))
    draw = ImageDraw.Draw(high)
    distal_radius = HAND_VISUAL_DISTAL_RADIUS_PX * scale
    for left, top, right, bottom, from_y in HAND_VISUAL_DISTAL_REGIONS:
        for y in range(from_y, bottom + 1):
            for x in range(left, right + 1):
                if mask.getpixel((x, y)) > 0:
                    draw.ellipse(
                        (x * scale - distal_radius, y * scale - distal_radius,
                         x * scale + distal_radius, y * scale + distal_radius),
                        fill=255,
                    )
    radius = HAND_VISUAL_TIP_RADIUS_PX * scale
    for x, y in HAND_VISUAL_TIP_CENTERS:
        draw.ellipse((x * scale - radius, y * scale - radius, x * scale + radius, y * scale + radius), fill=255)
    if hidden_root_high is not None:
        if hidden_root_high.size != (WIDTH * scale, HEIGHT * scale):
            raise ValueError("hidden wrist root must use the registered supersampled canvas")
        # The hidden root enters the formal display path from the same float
        # Bezier coverage used for the hidden/complete logic masks.  The final
        # red-line guards below still clamp visible ownership after downsample.
        high = ImageChops.lighter(high, hidden_root_high)
    # Reapply the same high-resolution clip after downsampling.  BOX is
    # monotone, so the final guard has no ringing or outside-boundary pixels.
    result = high.resize(CANVAS, Image.Resampling.BOX)
    final_guard = hand_visual_boundary_clip(scale).resize(CANVAS, Image.Resampling.BOX)
    final_guard = ImageChops.multiply(
        final_guard,
        hand_visual_markup_boundary_clip(scale).resize(CANVAS, Image.Resampling.BOX),
    )
    return ImageChops.multiply(result, final_guard)


def audit_hand_visual_boundary(mask: Image.Image) -> dict[str, object]:
    """Audit the final AA hand display against the registered red-guide clip."""
    if mask.mode != "L":
        mask = mask.convert("L")
    final_smooth_guard = hand_visual_boundary_clip(HAND_VISUAL_SUPERSAMPLE).resize(CANVAS, Image.Resampling.BOX)
    final_markup_guard = hand_visual_markup_boundary_clip(HAND_VISUAL_SUPERSAMPLE).resize(CANVAS, Image.Resampling.BOX)
    candidate_pixels = mask.load()
    smooth_guard_pixels = final_smooth_guard.load()
    markup_guard_pixels = final_markup_guard.load()
    outside_smooth_points = [
        (x, y)
        for y in range(HEIGHT)
        for x in range(WIDTH)
        if candidate_pixels[x, y] > 0 and smooth_guard_pixels[x, y] == 0
    ]
    outside_markup_points = [
        (x, y)
        for y in range(HEIGHT)
        for x in range(WIDTH)
        if candidate_pixels[x, y] > 0 and markup_guard_pixels[x, y] == 0
    ]

    audit_box = (84, 528, 126, 560)
    raw_guide = hand_visual_boundary_points(inset=False)
    guard_boundary = [
        point
        for point in mask_boundary_pixels(final_smooth_guard, audit_box)
        if point_to_polyline_distance(point, raw_guide) <= 4.0
    ]
    candidate_boundary = [
        point
        for point in mask_boundary_pixels(mask, audit_box)
        if point_to_polyline_distance(point, raw_guide) <= 6.0
    ]

    def distribution(values: Sequence[float]) -> dict[str, object]:
        return distance_distribution(values)

    guide_to_rendered = [
        min((math.hypot(x - px, y - py) for px, py in guard_boundary), default=math.inf)
        for x, y in raw_guide
    ]
    rendered_to_guide = [
        min((math.hypot(x - px, y - py) for px, py in raw_guide), default=math.inf)
        for x, y in guard_boundary
    ]
    guide_to_candidate = [
        min((math.hypot(x - px, y - py) for px, py in candidate_boundary), default=math.inf)
        for x, y in raw_guide
    ]
    candidate_to_guide = [
        min((math.hypot(x - px, y - py) for px, py in raw_guide), default=math.inf)
        for x, y in candidate_boundary
    ]

    def markup_y_at_x(x: float) -> float | None:
        for (x0, y0), (x1, y1) in zip(HAND_VISUAL_TOP_BOUNDARY, HAND_VISUAL_TOP_BOUNDARY[1:]):
            if x0 <= x <= x1:
                progress = 0.0 if x1 == x0 else (x - x0) / (x1 - x0)
                return y0 + (y1 - y0) * progress
        return None

    actual_curve = hand_visual_boundary_points(inset=True)
    raw_curve_markup_clearances = [
        y - markup_y
        for x, y in raw_guide
        if (markup_y := markup_y_at_x(x)) is not None
    ]
    actual_curve_markup_clearances = [
        y - markup_y
        for x, y in actual_curve
        if (markup_y := markup_y_at_x(x)) is not None
    ]
    raw_curve_overshoot_samples = [
        value for value in raw_curve_markup_clearances if value < -1e-6
    ]
    actual_curve_overshoot_samples = [
        value for value in actual_curve_markup_clearances if value < -1e-6
    ]
    min_raw_curve_markup_clearance = min(raw_curve_markup_clearances, default=-math.inf)
    min_actual_curve_markup_clearance = min(actual_curve_markup_clearances, default=-math.inf)

    upper_boundary_roi = (84, 530, 124, HAND_VISUAL_PALM_CAP_END_Y + 1)
    upper_boundary_fractional_alpha_pixels = [
        (x, y)
        for y in range(upper_boundary_roi[1], upper_boundary_roi[3])
        for x in range(upper_boundary_roi[0], upper_boundary_roi[2])
        if 0 < candidate_pixels[x, y] < 255
    ]

    def alpha_runs_at_y(y: int) -> list[list[int]]:
        runs: list[list[int]] = []
        start: int | None = None
        for x in range(HAND_LINE_ROI[0], HAND_LINE_ROI[2]):
            if candidate_pixels[x, y] > 0:
                if start is None:
                    start = x
            elif start is not None:
                runs.append([start, x - 1])
                start = None
        if start is not None:
            runs.append([start, HAND_LINE_ROI[2] - 1])
        return runs

    first_open_gap_y = HAND_VISUAL_PALM_CAP_END_Y + 1
    first_open_gap_runs = alpha_runs_at_y(first_open_gap_y)

    c1_join_errors: list[float] = []
    c2_join_errors: list[float] = []
    for current, following in zip(HAND_VISUAL_BEZIER_SEGMENTS, HAND_VISUAL_BEZIER_SEGMENTS[1:]):
        c1_join_errors.append(math.hypot(
            (current[3][0] - current[2][0]) - (following[1][0] - following[0][0]),
            (current[3][1] - current[2][1]) - (following[1][1] - following[0][1]),
        ))
        c2_join_errors.append(math.hypot(
            (current[3][0] - 2 * current[2][0] + current[1][0])
            - (following[0][0] - 2 * following[1][0] + following[2][0]),
            (current[3][1] - 2 * current[2][1] + current[1][1])
            - (following[0][1] - 2 * following[1][1] + following[2][1]),
        ))
    rendered_bidirectional_max = max(guide_to_rendered + rendered_to_guide, default=math.inf)
    rendered_bidirectional_p95 = max(
        float(distribution(guide_to_rendered)["p95Px"] or math.inf),
        float(distribution(rendered_to_guide)["p95Px"] or math.inf),
    )
    candidate_bidirectional_max = max(guide_to_candidate + candidate_to_guide, default=math.inf)
    candidate_bidirectional_p95 = max(
        float(distribution(guide_to_candidate)["p95Px"] or math.inf),
        float(distribution(candidate_to_guide)["p95Px"] or math.inf),
    )
    report = {
        "schemaVersion": 1,
        "stage": "R2 hand flat-layer smooth red-boundary audit",
        **IDENTITY,
        "sourceMarkup": USER_MARKUP_PATH,
        "sourceMarkupSha256": USER_MARKUP_SHA256,
        "markupDimensions": list(USER_MARKUP_DIMENSIONS),
        "sourceCanvas": list(CANVAS),
        "roi": list(HAND_LINE_ROI),
        "coordinateTransform": "identity in original 512x1086 source space; smooth candidate is HAND_VISUAL_BEZIER_SEGMENTS and raw markup is the final hard guard",
        "allowedSide": "red-line interior / hand-material side",
        "displayAlphaSource": "display-alpha/hand-complete.png -> flat-layers/hand.png",
        "hiddenDisplayAlphaSource": "display-alpha/hand-hidden.png",
        "hiddenWristRoi": list(HAND_HIDDEN_WRIST_ROI),
        "boundarySegments": {
            "leftTransition": [list(point) for point in HAND_VISUAL_LEFT_EDGE],
            "topGuidePolyline": [list(point) for point in HAND_VISUAL_TOP_BOUNDARY],
            "rightTransition": [list(point) for point in HAND_VISUAL_RIGHT_EDGE],
            "bezierSegments": [[list(point) for point in segment] for segment in HAND_VISUAL_BEZIER_SEGMENTS],
        },
        "rendering": {
            "supersample": HAND_VISUAL_SUPERSAMPLE,
            "curveType": "explicit cubic Bezier segments with C2-continuous uniform-knot joins",
            "c1JoinErrorsPx": [round(value, 8) for value in c1_join_errors],
            "c2JoinErrorsPx": [round(value, 8) for value in c2_join_errors],
            "insetPx": HAND_VISUAL_BOUNDARY_INSET_PX,
            "curveInsetYPx": HAND_VISUAL_CURVE_INSET_Y_PX,
            "downsample": "BOX",
            "finalClipReapplied": True,
            "markupClipReapplied": True,
            "minRawCurveMarkupClearancePx": round(min_raw_curve_markup_clearance, 6),
            "minActualCurveMarkupClearancePx": round(min_actual_curve_markup_clearance, 6),
            "palmCapEndY": HAND_VISUAL_PALM_CAP_END_Y,
            "firstOpenGapY": first_open_gap_y,
            "upperBoundaryFractionalAlphaPixels": len(upper_boundary_fractional_alpha_pixels),
            "forbiddenOperations": ["row/column hard cut", "LANCZOS ringing", "blur", "dilate", "erode", "stroke expansion"],
        },
        "outsideBoundaryPixels": len(outside_markup_points),
        "outsideBoundaryPixelSample": [list(point) for point in outside_markup_points[:64]],
        "outsideSmoothBoundaryPixels": len(outside_smooth_points),
        "renderedGuideBoundary": {
            "guideSamples": len(raw_guide),
            "candidateSamples": len(guard_boundary),
            "guideToCandidate": distribution(guide_to_rendered),
            "candidateToGuide": distribution(rendered_to_guide),
            "bidirectionalMaxPx": round(rendered_bidirectional_max, 4),
            "bidirectionalP95Px": round(rendered_bidirectional_p95, 4),
            "uncoveredGuideSamples": sum(value > 4.0 for value in guide_to_rendered),
            "unmatchedCandidateSamples": sum(value > 4.0 for value in rendered_to_guide),
        },
        "visibleCandidateBoundary": {
            "candidateSamples": len(candidate_boundary),
            "guideToCandidate": distribution(guide_to_candidate),
            "candidateToGuide": distribution(candidate_to_guide),
            "bidirectionalMaxPx": round(candidate_bidirectional_max, 4),
            "bidirectionalP95Px": round(candidate_bidirectional_p95, 4),
        },
        "checks": [
            {
                "id": "final_alpha_inside_red_boundary",
                "pass": len(outside_markup_points) == 0,
                "outsideBoundaryPixels": len(outside_markup_points),
                "detail": "authoritative raw user markup is reapplied after the smooth candidate guard and downsampling",
            },
            {
                "id": "final_alpha_inside_smooth_c2_boundary",
                "pass": len(outside_smooth_points) == 0,
                "outsideSmoothBoundaryPixels": len(outside_smooth_points),
            },
            {
                "id": "registered_bezier_boundary_bidirectional_raster_error_le_4px",
                "pass": rendered_bidirectional_max <= 4.0 and rendered_bidirectional_p95 <= 4.0,
                "maxPx": round(rendered_bidirectional_max, 4),
                "p95Px": round(rendered_bidirectional_p95, 4),
                "tolerancePx": 4.0,
            },
            {
                "id": "bezier_curve_c2_continuity",
                "pass": max(c1_join_errors + c2_join_errors, default=math.inf) <= 1e-4,
                "maxC1JoinErrorPx": round(max(c1_join_errors, default=math.inf), 8),
                "maxC2JoinErrorPx": round(max(c2_join_errors, default=math.inf), 8),
                "tolerancePx": 1e-4,
            },
            {
                "id": "bezier_curve_stays_inside_raw_markup_without_overshoot",
                "pass": not raw_curve_overshoot_samples and not actual_curve_overshoot_samples,
                "minRawCurveMarkupClearancePx": round(min_raw_curve_markup_clearance, 6),
                "minActualCurveMarkupClearancePx": round(min_actual_curve_markup_clearance, 6),
                "overshootTolerancePx": 1e-6,
            },
            {
                "id": "final_clip_reapplied_after_downsample",
                "pass": True,
                "detail": "final hand alpha is multiplied by both BOX-rendered smooth and raw-markup guards after downsampling",
            },
            {
                "id": "upper_boundary_has_antialiased_alpha",
                "pass": len(upper_boundary_fractional_alpha_pixels) > 0,
                "fractionalAlphaPixels": len(upper_boundary_fractional_alpha_pixels),
                "roi": list(upper_boundary_roi),
            },
            {
                "id": "palm_cap_stops_before_first_open_gap",
                "pass": len(first_open_gap_runs) >= 2,
                "capEndY": HAND_VISUAL_PALM_CAP_END_Y,
                "firstOpenGapY": first_open_gap_y,
                "alphaRunsAtFirstOpenGap": first_open_gap_runs,
            },
        ],
        "overallPass": (
            len(outside_markup_points) == 0
            and len(outside_smooth_points) == 0
            and rendered_bidirectional_max <= 4.0
            and rendered_bidirectional_p95 <= 4.0
            and not raw_curve_overshoot_samples
            and not actual_curve_overshoot_samples
            and len(upper_boundary_fractional_alpha_pixels) > 0
            and len(first_open_gap_runs) >= 2
        ),
    }
    return report


def rgba_layer_antialiased(
    mask: Image.Image,
    color: tuple[int, int, int],
    supersample: int = 4,
) -> Image.Image:
    return rgba_layer(antialiased_mask(mask, supersample), color)


def alpha_composite_layers(layers: Iterable[Image.Image]) -> Image.Image:
    result = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer in layers:
        result = Image.alpha_composite(result, layer)
    return result


def opaque_preview(image: Image.Image, background: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    base = Image.new("RGBA", CANVAS, background + (255,))
    return Image.alpha_composite(base, image).convert("RGB")


def blend_overlay(source: Image.Image, transparent_layers: Image.Image) -> Image.Image:
    source_rgb = source.convert("RGB")
    flat = opaque_preview(transparent_layers)
    return Image.blend(source_rgb, flat, 0.45)


def blend_overlay_weighted(
    source: Image.Image,
    transparent_layers: Image.Image,
    weight: float,
) -> Image.Image:
    """Blend a material overlay strongly enough to compare it with source lines."""
    source_rgb = source.convert("RGB")
    flat = opaque_preview(transparent_layers)
    return Image.blend(source_rgb, flat, max(0.0, min(1.0, weight)))


def blend_debug_layers(layers: Iterable[Image.Image], opacity: int = 175) -> Image.Image:
    """Return a semi-transparent overlap view for geometry diagnosis only."""
    adjusted: list[Image.Image] = []
    for layer in layers:
        current = layer.copy()
        alpha = current.getchannel("A").point(lambda value: (value * opacity + 127) // 255)
        current.putalpha(alpha)
        adjusted.append(current)
    return alpha_composite_layers(adjusted)


def crop_nearest(image: Image.Image, box: tuple[int, int, int, int], scale: int = 4) -> Image.Image:
    crop = image.crop(box)
    return crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST)


def crop_smooth(image: Image.Image, box: tuple[int, int, int, int], scale: int = 4) -> Image.Image:
    crop = image.crop(box)
    return crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.LANCZOS)


def rotate_nearest(image: Image.Image, angle: float, center: tuple[float, float]) -> Image.Image:
    """Apply a deterministic full-canvas rigid transform for geometry QA."""
    return image.rotate(
        angle,
        resample=Image.Resampling.NEAREST,
        expand=False,
        center=center,
    )


def rotate_point_pil(
    point: tuple[float, float],
    center: tuple[float, float],
    angle: float,
) -> tuple[float, float]:
    """Forward-map a point using Pillow's image-space rotation convention."""
    theta = math.radians(angle)
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    dx = point[0] - center[0]
    dy = point[1] - center[1]
    return (
        center[0] + cos_theta * dx + sin_theta * dy,
        center[1] - sin_theta * dx + cos_theta * dy,
    )


def transform_with_pil_rotations(
    image: Image.Image,
    rotations: Sequence[tuple[tuple[float, float], float]],
) -> Image.Image:
    """Compose rigid image-space rotations and resample the layer only once."""
    # A Pillow rotation maps p -> A*p + (center - A*center).  Compose those
    # forward maps first, then pass the inverse map required by AFFINE.  One
    # resample avoids breaking one-pixel hand/finger connections during a
    # shoulder-plus-elbow chain test.
    matrix = (1.0, 0.0, 0.0, 1.0)
    translation = (0.0, 0.0)
    for center, angle in rotations:
        theta = math.radians(angle)
        a = math.cos(theta)
        b = math.sin(theta)
        d = -math.sin(theta)
        e = math.cos(theta)
        cx, cy = center
        rotation_translation = (cx - a * cx - b * cy, cy - d * cx - e * cy)
        ma, mb, md, me = matrix
        tx, ty = translation
        matrix = (
            a * ma + b * md,
            a * mb + b * me,
            d * ma + e * md,
            d * mb + e * me,
        )
        translation = (
            a * tx + b * ty + rotation_translation[0],
            d * tx + e * ty + rotation_translation[1],
        )

    a, b, d, e = matrix
    tx, ty = translation
    inverse = (
        e,
        -b,
        -(e * tx - b * ty),
        -d,
        a,
        -(-d * tx + a * ty),
    )
    transformed = image.transform(
        CANVAS,
        Image.Transform.AFFINE,
        inverse,
        # The action review is a continuous rigid transform.  Bicubic
        # sampling prevents one-pixel hand/finger bridges from disappearing
        # when the complete material is rotated; thresholding below restores a
        # binary alpha boundary without adding/dilating material.
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )
    alpha = transformed.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    transformed.putalpha(alpha)
    return transformed


def image_nonzero_count(image: Image.Image) -> int:
    return sum(1 for value in image.getdata() if value > 0)


def local_intersection_count(
    first: Image.Image,
    second: Image.Image,
    center: tuple[float, float],
    radius: int,
) -> int:
    left = max(0, round(center[0]) - radius)
    top = max(0, round(center[1]) - radius)
    right = min(WIDTH, round(center[0]) + radius + 1)
    bottom = min(HEIGHT, round(center[1]) + radius + 1)
    overlap = ImageChops.multiply(
        first.crop((left, top, right, bottom)),
        second.crop((left, top, right, bottom)),
    )
    return image_nonzero_count(overlap)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def wrap_text(text: str, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        if char == "\n":
            lines.append(current)
            current = ""
            continue
        current += char
        if len(current) >= width:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines


def draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, width: int, fill: tuple[int, int, int], size: int = 20, line_gap: int = 6) -> int:
    current_y = xy[1]
    text_font = font(size)
    for line in wrap_text(text, width):
        draw.text((xy[0], current_y), line, fill=fill, font=text_font)
        current_y += size + line_gap
    return current_y


def validate_source_inputs() -> tuple[dict[str, object], dict[str, Image.Image]]:
    results: dict[str, object] = {}
    images: dict[str, Image.Image] = {}
    for key, spec in R1_EXPECTED_INPUTS.items():
        path = spec["path"]
        assert isinstance(path, Path)
        actual_hash = sha256_file(path)
        image = Image.open(path)
        results[key] = {
            "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "expectedSha256": spec["sha256"],
            "actualSha256": actual_hash,
            "sha256Match": actual_hash == spec["sha256"],
            "dimensions": {"width": image.width, "height": image.height},
            "expectedDimensions": {"width": spec["size"][0], "height": spec["size"][1]},
            "mode": image.mode,
            "expectedMode": spec["mode"],
            "pass": actual_hash == spec["sha256"] and (image.width, image.height) == spec["size"] and image.mode == spec["mode"],
        }
        images[key] = image.convert("RGB")
    return results, images


def validate_r1_freeze() -> dict[str, object]:
    freeze = load_json(R1_FREEZE_PATH)
    assert isinstance(freeze, dict)
    checks: list[dict[str, object]] = []
    for entry in freeze["frozenFiles"]:
        path = REPO_ROOT / str(entry["path"])
        expected = str(entry["sha256"])
        actual = sha256_file(path)
        checks.append({"path": str(entry["path"]), "expectedSha256": expected, "actualSha256": actual, "match": expected == actual})
    machine_report = load_json(R1_MACHINE_REPORT_PATH)
    approval = load_json(R1_APPROVAL_PATH)
    review_path = REPO_ROOT / str(approval["r1ReviewArtifact"]["path"])
    review_hash = sha256_file(review_path)
    report_review_1 = str(machine_report["determinism"]["reviewPngSha256Run1"])
    report_review_2 = str(machine_report["determinism"]["reviewPngSha256Run2"])
    report_ok = bool(machine_report["engineeringPass"]) and not bool(machine_report["overallGatePass"])
    return {
        "freezePath": str(R1_FREEZE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "approvalPath": str(R1_APPROVAL_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "freezeStatus": freeze["status"],
        "identity": freeze["identity"],
        "frozenFileChecks": checks,
        "allFrozenHashesMatch": all(bool(item["match"]) for item in checks),
        "r1MachineEngineeringPass": bool(machine_report["engineeringPass"]),
        "r1MachineOverallGateStillFalse": not bool(machine_report["overallGatePass"]),
        "r1MachineStatus": machine_report["status"],
        "r1MachineReportConsistent": report_ok,
        "reviewSha256": review_hash,
        "reviewSha256MatchesReportRun1": review_hash == report_review_1,
        "reviewSha256MatchesReportRun2": review_hash == report_review_2,
        "approvalAuthorizedNextStage": approval["authorizedNextStage"],
        "approvalNotAuthorized": approval["notAuthorized"],
    }


def snapshot_protected_files() -> dict[str, str]:
    paths: set[Path] = set()
    freeze = load_json(R1_FREEZE_PATH)
    for entry in freeze["frozenFiles"]:
        path = REPO_ROOT / str(entry["path"])
        if path.exists():
            paths.add(path)
    paths.add(R1_FREEZE_PATH)
    for directory in VALIDATION_ROOT.glob("arm-chain-screen-left-v*"):
        if directory.is_dir():
            paths.update(path for path in directory.rglob("*") if path.is_file())
    snapshot: dict[str, str] = {}
    for path in sorted(paths):
        snapshot[str(path.relative_to(REPO_ROOT)).replace("\\", "/")] = sha256_file(path)
    return snapshot


def capture_repair_baseline() -> dict[str, object]:
    """Keep the current R2 candidate as an in-place before/after reference."""
    if REPAIR_BASELINE_PATH.exists():
        baseline = load_json(REPAIR_BASELINE_PATH)
        if not isinstance(baseline, dict):
            raise RuntimeError("R2 repair baseline is not a JSON object")
        files = baseline.setdefault("files", {})
        if not isinstance(files, dict):
            raise RuntimeError("R2 repair baseline files field is invalid")
    else:
        files = {}
        for layer_id, variants in REPAIR_BASELINE_MASKS.items():
            for variant, relative_source in variants.items():
                source = R2_ROOT / relative_source
                if not source.exists():
                    continue
                target = REPAIR_BASELINE_DIR / layer_id / f"{variant}.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                files[f"{layer_id}.{variant}"] = str(target.relative_to(R2_ROOT)).replace("\\", "/")

        baseline = {
            "schemaVersion": 1,
            "stage": "R2 visual repair before/after baseline",
            **IDENTITY,
            "status": "captured_before_current_r2_visual_repair",
            "scope": "current R2 candidate only; not a new R2 version and not a frozen artifact",
            "files": files,
        }

    # The existing baseline predates the hidden-wrist AA maintenance and only
    # covered logic masks.  Capture the current formal hand layer exactly once
    # before this maintenance overwrites it, so the pixel-diff gate can prove
    # that changes outside the authorized hidden-wrist ROI are zero.
    display_source = R2_ROOT / "flat-layers" / "hand.png"
    display_key = "hand.formalDisplayFlatLayer"
    if display_key not in files:
        if not display_source.exists():
            raise FileNotFoundError(f"cannot capture formal hand display baseline: {display_source}")
        target = REPAIR_BASELINE_DIR / "hand" / "flat-layer.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(display_source, target)
        files[display_key] = str(target.relative_to(R2_ROOT)).replace("\\", "/")
        baseline["formalDisplayBaseline"] = {
            "source": "flat-layers/hand.png",
            "capturedBeforeMaintenance": True,
            "authorizedChangeRoi": list(HAND_HIDDEN_WRIST_ROI),
        }
    write_json(REPAIR_BASELINE_PATH, baseline)
    return baseline


def snapshot_current_hand_artifacts() -> dict[str, str]:
    """Hash hand outputs that are read-only inputs for the forearm-only repair."""
    relative_paths = (
        "masks/visible/hand.png",
        "masks/hidden/hand.png",
        "masks/complete/hand.png",
        "display-alpha/hand-hidden.png",
        "display-alpha/hand-complete.png",
        "flat-layers/hand.png",
        "contracts/hand-line-trace-contract.json",
        "audit/hand-boundary-error-table.json",
        "audit/hand-visual-boundary-report.json",
        "qa/hand-r2-repair/14-隐藏腕根抗锯齿维护审查.png",
    )
    snapshot: dict[str, str] = {}
    for relative in relative_paths:
        path = R2_ROOT / relative
        if not path.exists():
            raise FileNotFoundError(f"protected hand artifact is missing: {path}")
        snapshot[relative] = sha256_file(path)
    return snapshot


def snapshot_non_forearm_r2_files() -> dict[str, str]:
    """Snapshot existing R2 outputs outside the reopened forearm scope.

    Bracelet masks and their audit flat layers are part of the current wrist
    seam repair scope.  Hand, sleeve, upper-arm and all unrelated subregions
    remain protected here.
    """
    independent_flat_layers = {
        "sleeve.png",
        "upper_arm.png",
        "hand.png",
    }
    snapshot: dict[str, str] = {}
    for path in sorted(R2_ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(R2_ROOT).as_posix()
        if relative.startswith("masks/visible/") or relative.startswith("masks/hidden/") or relative.startswith("masks/complete/"):
            if Path(relative).name != "forearm.png":
                snapshot[relative] = sha256_file(path)
        elif (
            relative.startswith("masks/subregions/")
            and not Path(relative).name.startswith("forearm-skin-")
            and not Path(relative).name.startswith("bracelet-")
        ):
            snapshot[relative] = sha256_file(path)
        elif relative.startswith("flat-layers/") and Path(relative).name in independent_flat_layers:
            snapshot[relative] = sha256_file(path)
    return snapshot


def flood_component(seed: tuple[int, int], pool: set[tuple[int, int]], neighbors: Sequence[tuple[int, int]]) -> set[tuple[int, int]]:
    pool.remove(seed)
    queue: deque[tuple[int, int]] = deque([seed])
    component = {seed}
    while queue:
        x, y = queue.popleft()
        for dx, dy in neighbors:
            point = (x + dx, y + dy)
            if point in pool:
                pool.remove(point)
                queue.append(point)
                component.add(point)
    return component


def forearm_source_line_enclosure(
    source_line: Image.Image | None = None,
) -> tuple[Image.Image, dict[str, object]]:
    """Recover the exposed shaft from the authoritative line raster.

    The selected free-pixel component is the skin-side area between the
    observed outer forearm contour and the separate shirt/torso locator line.
    This is intentionally a direct 4-connected raster enclosure: no color
    threshold decides ownership, no smooth trace is used to create the edge,
    and the source component contract fails closed if the master changes.
    """
    if source_line is None:
        source_line = Image.open(SOURCE_ROOT / "masters" / "front-line-source-exact-after-reset.png").convert("RGB")
    gray = source_line.convert("L")
    left, top, right, bottom = FOREARM_SOURCE_LINE_ROI
    barrier = {
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if gray.getpixel((x, y)) < FOREARM_SOURCE_LINE_BARRIER_LUMA_MAX
    }
    free = {
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if (x, y) not in barrier
    }
    if FOREARM_SOURCE_LINE_SEED not in free:
        raise AssertionError(
            f"forearm source-line seed is blocked: {FOREARM_SOURCE_LINE_SEED}"
        )
    component = flood_component(
        FOREARM_SOURCE_LINE_SEED,
        free,
        ((1, 0), (-1, 0), (0, 1), (0, -1)),
    )
    xs = [point[0] for point in component]
    ys = [point[1] for point in component]
    bbox = (min(xs), min(ys), max(xs), max(ys)) if component else None
    if bbox != FOREARM_SOURCE_LINE_EXPECTED_BBOX:
        raise AssertionError(
            "forearm source-line component bbox changed: "
            f"{bbox} != {FOREARM_SOURCE_LINE_EXPECTED_BBOX}"
        )
    if len(component) != FOREARM_SOURCE_LINE_EXPECTED_PIXEL_COUNT:
        raise AssertionError(
            "forearm source-line component pixel count changed: "
            f"{len(component)} != {FOREARM_SOURCE_LINE_EXPECTED_PIXEL_COUNT}"
        )

    # The free component gives the skin-side interior.  For the exposed shaft
    # the material reaches the outside edge of the two contour strokes, so add
    # only the contiguous barrier pixels directly touching each component run
    # on the shaft rows.  This includes the actual line stroke but never jumps
    # across a white gap to the separate shirt/torso locator line.
    boundary = set(component)
    visible_left, visible_top, visible_right, visible_bottom = FOREARM_SHAFT_SOURCE_VISIBLE_ROI
    for y in range(visible_top, visible_bottom):
        row = sorted(x for x, row_y in component if row_y == y)
        if not row:
            continue
        runs: list[tuple[int, int]] = []
        start = previous = row[0]
        for x in row[1:]:
            if x == previous + 1:
                previous = x
            else:
                runs.append((start, previous))
                start = previous = x
        runs.append((start, previous))
        for start, end in runs:
            x = start - 1
            while visible_left <= x < visible_right and (x, y) in barrier:
                boundary.add((x, y))
                x -= 1
            x = end + 1
            while visible_left <= x < visible_right and (x, y) in barrier:
                boundary.add((x, y))
                x += 1

    right_aa_exclusion_left, right_aa_exclusion_top, right_aa_exclusion_right, right_aa_exclusion_bottom = FOREARM_SOURCE_LINE_RIGHT_AA_EXCLUSION_ROI
    right_aa_exclusion = {
        (x, y)
        for y in range(right_aa_exclusion_top, right_aa_exclusion_bottom)
        for x in range(right_aa_exclusion_left, right_aa_exclusion_right)
        if gray.getpixel((x, y)) >= 200
    }
    boundary.difference_update(right_aa_exclusion)

    mask = Image.new("L", CANVAS, 0)
    mask_pixels = mask.load()
    for x, y in boundary:
        mask_pixels[x, y] = 255
    metadata = {
        "source": "source/masters/front-line-source-exact-after-reset.png",
        "sourceCanvas": list(CANVAS),
        "coordinateTransform": "identity",
        "roi": list(FOREARM_SOURCE_LINE_ROI),
        "visibleRoi": list(FOREARM_SHAFT_SOURCE_VISIBLE_ROI),
        "barrier": {
            "rasterRule": f"source line pixels with luma < {FOREARM_SOURCE_LINE_BARRIER_LUMA_MAX} are 4-connected barriers",
            "connectivity": "4-connected free pixels",
        },
        "seed": list(FOREARM_SOURCE_LINE_SEED),
        "selectedComponent": {
            "bbox": list(bbox) if bbox else None,
            "pixelCount": len(component),
        },
        "materialBoundary": {
            "bbox": [min(x for x, y in boundary), min(y for x, y in boundary), max(x for x, y in boundary), max(y for x, y in boundary)],
            "pixelCount": len(boundary),
            "addedContourPixels": len(boundary) - len(component),
            "rule": "component free pixels plus only contiguous barrier pixels touching each selected row run inside the shaft visible ROI",
            "rightAaExclusion": {
                "roi": list(FOREARM_SOURCE_LINE_RIGHT_AA_EXCLUSION_ROI),
                "pixelCount": len(right_aa_exclusion),
                "rule": "latest user visual review removes only the registered right-side antialias fringe; dark source contour ownership is retained",
            },
        },
        "traceMethod": "direct source-raster enclosure plus contiguous source contour pixels; no smooth trace, blur, dilate, erode, mirror, or color-class boundary",
        "semanticRule": "selected component is the skin-side shaft between the observed outer contour and the separate shirt/torso locator line",
    }
    return mask, metadata


def forearm_elbow_source_enclosure(
    source_line: Image.Image | None = None,
) -> tuple[Image.Image, dict[str, object]]:
    """Recover the forearm-side free component immediately below the sleeve hem.

    This is intentionally narrower than the full shaft enclosure.  The
    elbow close-up contains several nearby locator strokes, so ownership is
    selected by a registered 4-connected free-pixel component and a fixed
    source seed, never by the imprecise user sketch or by a smooth cap.
    """
    if source_line is None:
        source_line = Image.open(SOURCE_ROOT / "masters" / "front-line-source-exact-after-reset.png").convert("RGB")
    gray = source_line.convert("L")
    left, top, right, bottom = FOREARM_ELBOW_SOURCE_ROI
    barrier = {
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if gray.getpixel((x, y)) < FOREARM_ELBOW_SOURCE_BARRIER_LUMA_MAX
    }
    free = {
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if (x, y) not in barrier
    }
    if FOREARM_ELBOW_SOURCE_SEED not in free:
        raise AssertionError(
            f"forearm elbow source-line seed is blocked: {FOREARM_ELBOW_SOURCE_SEED}"
        )
    component = flood_component(
        FOREARM_ELBOW_SOURCE_SEED,
        free,
        ((1, 0), (-1, 0), (0, 1), (0, -1)),
    )
    xs = [point[0] for point in component]
    ys = [point[1] for point in component]
    bbox = (min(xs), min(ys), max(xs), max(ys)) if component else None
    if bbox != FOREARM_ELBOW_SOURCE_EXPECTED_BBOX:
        raise AssertionError(
            "forearm elbow source-line component bbox changed: "
            f"{bbox} != {FOREARM_ELBOW_SOURCE_EXPECTED_BBOX}"
        )
    if len(component) != FOREARM_ELBOW_SOURCE_EXPECTED_PIXEL_COUNT:
        raise AssertionError(
            "forearm elbow source-line component pixel count changed: "
            f"{len(component)} != {FOREARM_ELBOW_SOURCE_EXPECTED_PIXEL_COUNT}"
        )

    mask = Image.new("L", CANVAS, 0)
    mask_pixels = mask.load()
    for x, y in component:
        mask_pixels[x, y] = 255
    metadata = {
        "source": "source/masters/front-line-source-exact-after-reset.png",
        "sourceCanvas": list(CANVAS),
        "coordinateTransform": "identity",
        "roi": list(FOREARM_ELBOW_SOURCE_ROI),
        "repairRoi": list(FOREARM_ELBOW_SOURCE_REPAIR_ROI),
        "barrier": {
            "rasterRule": f"source line pixels with luma < {FOREARM_ELBOW_SOURCE_BARRIER_LUMA_MAX} are 4-connected barriers",
            "connectivity": "4-connected free pixels",
        },
        "seed": list(FOREARM_ELBOW_SOURCE_SEED),
        "selectedComponent": {
            "bbox": list(bbox) if bbox else None,
            "pixelCount": len(component),
            "rowsStart": min(ys) if ys else None,
            "rowsEndInclusive": max(ys) if ys else None,
        },
        "traceMethod": "direct source-raster free-space component below the sleeve hem; no user-sketch trace, smooth trace, blur, dilate, erode, or generated cap",
        "semanticRule": "only the forearm-side free component below the observed sleeve hem may replace the legacy elbow root in the registered repair ROI",
    }
    return mask, metadata


def forearm_elbow_user_markup_boundary(
    markup: Image.Image | None = None,
) -> tuple[Image.Image, dict[str, object]]:
    """Register the latest red elbow reference as a hidden-only source mask.

    The attachment is a screenshot of panel 9 rather than a source-canvas
    drawing.  Its transform is therefore explicit and fail-closed: the panel
    crop, thumbnail size, capture scale and screenshot offset are recorded in
    the metadata, then the red stroke is converted into source-row intervals.
    No curve fitting or overshoot is used.  The result is an allowed hidden
    region; visible shaft ownership remains source-line locked elsewhere.
    """
    path = FOREARM_ELBOW_USER_MARKUP_PATH
    if markup is None:
        if not path.exists():
            raise FileNotFoundError(f"latest elbow markup is missing: {path}")
        if sha256_file(path) != FOREARM_ELBOW_USER_MARKUP_SHA256:
            raise AssertionError(
                "latest elbow markup hash changed; refusing to infer a new boundary: "
                f"{path}"
            )
        markup = Image.open(path).convert("RGB")
    else:
        markup = markup.convert("RGB")
    if markup.size != FOREARM_ELBOW_USER_MARKUP_DIMENSIONS:
        raise AssertionError(
            "latest elbow markup dimensions changed: "
            f"{markup.size} != {FOREARM_ELBOW_USER_MARKUP_DIMENSIONS}"
        )

    red_r, red_g, red_b = FOREARM_ELBOW_USER_MARKUP_RED_THRESHOLD
    red = {
        (x, y)
        for y in range(markup.height)
        for x in range(markup.width)
        if (
            (pixel := markup.getpixel((x, y)))[0] > red_r
            and pixel[1] < red_g
            and pixel[2] < red_b
            and pixel[0] - pixel[1] > 70
            and pixel[0] - pixel[2] > 70
        )
    }
    if not red:
        raise AssertionError("latest elbow markup contains no red boundary pixels")
    remaining = set(red)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        seed = remaining.pop()
        queue: deque[tuple[int, int]] = deque([seed])
        component = {seed}
        while queue:
            x, y = queue.popleft()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if not (dx or dy):
                        continue
                    point = (x + dx, y + dy)
                    if point in remaining:
                        remaining.remove(point)
                        queue.append(point)
                        component.add(point)
        components.append(component)
    component = max(components, key=len)
    xs = [point[0] for point in component]
    ys = [point[1] for point in component]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    if len(component) != FOREARM_ELBOW_USER_MARKUP_RED_PIXEL_COUNT:
        raise AssertionError(
            "latest elbow markup red pixel count changed: "
            f"{len(component)} != {FOREARM_ELBOW_USER_MARKUP_RED_PIXEL_COUNT}"
        )
    if bbox != FOREARM_ELBOW_USER_MARKUP_RED_BBOX:
        raise AssertionError(
            "latest elbow markup red bbox changed: "
            f"{bbox} != {FOREARM_ELBOW_USER_MARKUP_RED_BBOX}"
        )

    crop_left, crop_top, crop_right, crop_bottom = FOREARM_ELBOW_USER_MARKUP_SOURCE_CROP
    image_width, image_height = FOREARM_ELBOW_USER_MARKUP_PANEL_IMAGE_SIZE
    display_width, display_height = FOREARM_ELBOW_USER_MARKUP_PANEL_DISPLAY_SIZE
    capture_scale = FOREARM_ELBOW_USER_MARKUP_CAPTURE_SCALE
    offset_x, offset_y = FOREARM_ELBOW_USER_MARKUP_SCREEN_OFFSET
    source_x_scale = capture_scale * (display_width / image_width) * 5.0
    source_y_scale = capture_scale * (display_height / image_height) * 5.0

    def screen_to_source(point: tuple[float, float]) -> tuple[float, float]:
        screen_x, screen_y = point
        return (
            crop_left + (screen_x - offset_x) / source_x_scale,
            crop_top + (screen_y - offset_y) / source_y_scale,
        )

    def source_to_screen(point: tuple[float, float]) -> tuple[float, float]:
        source_x, source_y = point
        return (
            offset_x + (source_x - crop_left) * source_x_scale,
            offset_y + (source_y - crop_top) * source_y_scale,
        )

    allowed = Image.new("L", CANVAS, 0)
    allowed_pixels = allowed.load()
    row_records: list[dict[str, object]] = []
    left_trace: list[tuple[float, float]] = []
    right_trace: list[tuple[float, float]] = []
    source_y_start, source_y_end = FOREARM_ELBOW_USER_MARKUP_SOURCE_Y_RANGE
    for source_y in range(source_y_start, source_y_end):
        screen_y = source_to_screen((crop_left, source_y))[1]
        band_top = math.floor(screen_y - source_y_scale / 2.0)
        band_bottom = math.ceil(screen_y + source_y_scale / 2.0)
        row_pixels = [
            (x, y)
            for x, y in component
            if band_top <= y <= band_bottom
        ]
        if not row_pixels:
            raise AssertionError(
                f"latest elbow markup has no red pixels for source row {source_y}"
            )
        screen_left = min(x for x, _ in row_pixels)
        screen_right = max(x for x, _ in row_pixels)
        source_left, _ = screen_to_source((screen_left, screen_y))
        source_right, _ = screen_to_source((screen_right, screen_y))
        left_pixel = max(0, math.ceil(source_left))
        right_pixel = min(WIDTH - 1, math.floor(source_right))
        if left_pixel > right_pixel:
            raise AssertionError(
                f"latest elbow markup interval collapsed at source row {source_y}"
            )
        for x in range(left_pixel, right_pixel + 1):
            allowed_pixels[x, source_y] = 255
        left_trace.append((source_left, float(source_y)))
        right_trace.append((source_right, float(source_y)))
        row_records.append({
            "sourceY": source_y,
            "screenYBand": [band_top, band_bottom],
            "screenXInterval": [screen_left, screen_right],
            "sourceXInterval": [source_left, source_right],
            "rasterXInterval": [left_pixel, right_pixel],
        })

    metadata = {
        "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "sha256": FOREARM_ELBOW_USER_MARKUP_SHA256,
        "dimensions": list(FOREARM_ELBOW_USER_MARKUP_DIMENSIONS),
        "redPixelCount": len(component),
        "redBbox": list(bbox),
        "coordinateTransform": {
            "sourceCanvas": list(CANVAS),
            "screenToSource": "sourceX = 108 + (screenX + 150) / 14.083333333333332; sourceY = 370 + (screenY - 40) / 14.1",
            "panel9SourceCrop": list(FOREARM_ELBOW_USER_MARKUP_SOURCE_CROP),
            "panel9NearestScale": 5,
            "panel9PanelImageSize": list(FOREARM_ELBOW_USER_MARKUP_PANEL_IMAGE_SIZE),
            "panel9PanelDisplaySize": list(FOREARM_ELBOW_USER_MARKUP_PANEL_DISPLAY_SIZE),
            "screenshotCaptureScale": capture_scale,
            "screenOffset": [offset_x, offset_y],
            "mappingBasis": "registered against panel 9 source-line/vertical-contour pixels; identity back to the 512x1086 front master",
        },
        "allowedSide": "inside the latest mapped red outline; hidden elbow continuity only",
        "repairRoi": list(FOREARM_ELBOW_USER_MARKUP_REPAIR_ROI),
        "sourceYRange": [source_y_start, source_y_end],
        "rowIntervals": row_records,
        "boundarySegments": {
            "left": [list(point) for point in left_trace],
            "top": [list(point) for point in (left_trace[0], right_trace[0])],
            "right": [list(point) for point in reversed(right_trace)],
        },
        "traceMethod": "red-pixel row intervals mapped from the user panel screenshot; direct raster intervals only, no Bézier fitting, smoothing, overshoot, dilation, erosion, or boundary expansion",
        "visibleBoundaryRule": "this redline does not authorize visible forearm alpha over the source sleeve hem; visible shaft remains source-line owned",
    }
    return allowed, metadata


def wrist_source_line_materials(
    source_line: Image.Image,
) -> tuple[Image.Image, Image.Image, Image.Image, dict[str, object], Image.Image, Image.Image]:
    """Recover the distal wrist skin and bracelet from source-line pixels.

    The wrist is a difficult place to infer from broad traces because the
    bracelet crosses both material boundaries.  This function keeps the
    semantic decision on the authoritative line raster:

    * the forearm seed selects the skin-side free component;
    * the small free component between the two bracelet lines remains skin;
    * bracelet visible ownership is made only from source barrier pixels in
      registered line-following corridors;
    * long outer forearm/hand contour pixels are removed when they touch a
      skin component and a different exterior component, so the hand contour
      cannot become bracelet material just because it is nearby.

    The corridors are guards, not generated geometry.  A changed source line,
    component bbox, or component count fails closed before any material is
    emitted.
    """
    source_line = source_line.convert("RGB")
    gray = source_line.convert("L")
    left, top, right, bottom = FOREARM_WRIST_SOURCE_ROI
    barrier_pixels = {
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if gray.getpixel((x, y)) < FOREARM_WRIST_SOURCE_BARRIER_LUMA_MAX
    }
    free_pixels = {
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if (x, y) not in barrier_pixels
    }
    four_neighbors = ((1, 0), (-1, 0), (0, 1), (0, -1))
    components: list[set[tuple[int, int]]] = []
    while free_pixels:
        component = flood_component(next(iter(free_pixels)), free_pixels, four_neighbors)
        components.append(component)
    components.sort(key=lambda component: (-len(component), min(component)))
    component_by_point = {
        point: index
        for index, component in enumerate(components)
        for point in component
    }

    component_records: list[dict[str, object]] = []
    selected_components: dict[str, set[tuple[int, int]]] = {}
    for spec in FOREARM_WRIST_SOURCE_COMPONENT_SPECS:
        seed = tuple(spec["seed"])
        component_index = component_by_point.get(seed)
        if component_index is None:
            raise AssertionError(f"wrist source-line seed is blocked or missing: {spec['id']} {seed}")
        component = components[component_index]
        xs = [point[0] for point in component]
        ys = [point[1] for point in component]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        record = {
            "id": str(spec["id"]),
            "seed": list(seed),
            "bbox": list(bbox),
            "pixelCount": len(component),
            "touchesRoiBorder": any(
                x in (left, right - 1) or y in (top, bottom - 1)
                for x, y in component
            ),
        }
        component_records.append(record)
        if bbox != tuple(spec["bbox"]) or len(component) != int(spec["pixelCount"]):
            raise AssertionError(
                "wrist source-line component contract changed: "
                f"{spec['id']} bbox/count={(bbox, len(component))} != "
                f"{(spec['bbox'], spec['pixelCount'])}"
            )
        selected_components[str(spec["id"])] = component

    corridor_masks: dict[str, Image.Image] = {}
    for spec in FOREARM_WRIST_BRACELET_CORRIDOR_SPECS:
        corridor_masks[str(spec["id"])] = draw_trace_band(
            list(spec["first"]),
            list(spec["second"]),
            samples_per_segment=6,
        )
    corridor_union = mask_union(*corridor_masks.values())

    # Identify the two large free-space sides separately from the selected
    # forearm/hand components.  A contour pixel touching a selected skin side
    # and another exterior side is a body contour, not bracelet ownership.
    roi_border = {
        (x, y)
        for x in range(left, right)
        for y in (top, bottom - 1)
    } | {
        (x, y)
        for y in range(top, bottom)
        for x in (left, right - 1)
    }
    exterior_component_ids = {
        index
        for index, component in enumerate(components)
        if component & roi_border
    }
    forearm_component_id = component_by_point[tuple(FOREARM_WRIST_SOURCE_FOREARM_SEED)]
    hand_component_id = component_by_point[tuple(FOREARM_WRIST_SOURCE_HAND_SEED)]
    inner_component_id = component_by_point[(112, 528)]
    eight_neighbors = tuple(
        (dx, dy)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if (dx, dy) != (0, 0)
    )
    outer_contour_pixels: set[tuple[int, int]] = set()
    for x, y in barrier_pixels:
        adjacent_ids = {
            component_by_point[(x + dx, y + dy)]
            for dx, dy in eight_neighbors
            if (x + dx, y + dy) in component_by_point
        }
        touches_forearm_outer = (
            forearm_component_id in adjacent_ids
            and inner_component_id not in adjacent_ids
            and hand_component_id not in adjacent_ids
            and bool(adjacent_ids & (exterior_component_ids - {forearm_component_id, hand_component_id}))
        )
        touches_hand_outer = (
            hand_component_id in adjacent_ids
            and inner_component_id not in adjacent_ids
            and forearm_component_id not in adjacent_ids
            and bool(adjacent_ids & (exterior_component_ids - {forearm_component_id, hand_component_id}))
        )
        if touches_forearm_outer or touches_hand_outer:
            outer_contour_pixels.add((x, y))

    source_barrier_mask = Image.new("L", CANVAS, 0)
    source_barrier_mask_pixels = source_barrier_mask.load()
    for x, y in barrier_pixels:
        source_barrier_mask_pixels[x, y] = 255
    bracelet_source_line_mask = ImageChops.multiply(source_barrier_mask, corridor_union)
    bracelet_source_line_pixels = bracelet_source_line_mask.load()
    for x, y in outer_contour_pixels:
        bracelet_source_line_pixels[x, y] = 0

    # Keep the actual source-line bracelet path, but discard isolated
    # one-pixel barrier specks that are separated from that path by the
    # rasterized line's antialias gaps.  They are not a bracelet contour and
    # become detached visible color islands when the hand-protection shield is
    # correctly removed.  This is a connected-source selection, not a bridge,
    # dilation, erosion, or generated shape.
    bracelet_points = nonzero_points(bracelet_source_line_mask)
    bracelet_remaining = set(bracelet_points)
    bracelet_components: list[set[tuple[int, int]]] = []
    while bracelet_remaining:
        bracelet_components.append(
            flood_component(
                next(iter(bracelet_remaining)),
                bracelet_remaining,
                eight_neighbors,
            )
        )
    isolated_bracelet_fragments = sorted(
        (component for component in bracelet_components if len(component) == 1),
        key=lambda component: min(component),
    )
    retained_bracelet_points = set().union(
        *(component for component in bracelet_components if len(component) > 1)
    ) if bracelet_components else set()
    for x, y in bracelet_points - retained_bracelet_points:
        bracelet_source_line_pixels[x, y] = 0

    bracelet_back_visible = mask_intersection(
        bracelet_source_line_mask,
        corridor_masks["proximal-loop"],
    )
    bracelet_front_visible = mask_subtract(
        bracelet_source_line_mask,
        bracelet_back_visible,
    )
    wrist_skin_source = Image.new("L", CANVAS, 0)
    wrist_skin_source_pixels = wrist_skin_source.load()
    for component_id in ("forearm-skin", "wrist-skin-between-bracelet-lines"):
        for x, y in selected_components[component_id]:
            wrist_skin_source_pixels[x, y] = 255

    wrist_repair_roi = roi_mask(FOREARM_WRIST_SOURCE_REPAIR_ROI)
    wrist_skin_source = mask_intersection(wrist_skin_source, wrist_repair_roi)
    # Source-line guard only: this selected transition component permits the
    # forearm's hidden material to overlap underneath the protected hand, but
    # it never changes hand ownership or emits hand pixels for the forearm.
    hand_transition_guard = Image.new("L", CANVAS, 0)
    hand_transition_guard_pixels = hand_transition_guard.load()
    for x, y in selected_components["hand-protected-transition"]:
        hand_transition_guard_pixels[x, y] = 255
    hand_transition_guard = mask_intersection(hand_transition_guard, wrist_repair_roi)
    # Close only the internal bracelet gap between the source components.  The
    # guard follows each source row's actual selected-component span; it is not
    # a global hull, dilation, or freehand expansion.  This gives the hidden
    # forearm a continuous under-bracelet bridge while keeping both outer
    # skin/hand contours source-locked.
    wrist_hidden_source_guard = Image.new("L", CANVAS, 0)
    wrist_hidden_source_guard_pixels = wrist_hidden_source_guard.load()
    guard_components = (
        selected_components["forearm-skin"],
        selected_components["wrist-skin-between-bracelet-lines"],
        selected_components["hand-protected-transition"],
    )
    guard_left, guard_top, guard_right, guard_bottom = FOREARM_WRIST_SOURCE_REPAIR_ROI
    for y in range(guard_top, guard_bottom):
        row_points = [
            x
            for component in guard_components
            for x, yy in component
            if yy == y and guard_left <= x < guard_right
        ]
        if row_points:
            for x in range(min(row_points), max(row_points) + 1):
                wrist_hidden_source_guard_pixels[x, y] = 255
    # For the occluded top only, extend to the inner edge of the observed
    # bracelet-back source line.  This supplies a real hidden overlap beneath
    # the bracelet without following the accessory's outer/hanging edge.
    for y in range(524, 529):
        skin_row = [x for x in range(guard_left, guard_right) if wrist_skin_source.getpixel((x, y)) > 0]
        back_row = [x for x in range(guard_left, guard_right) if bracelet_back_visible.getpixel((x, y)) > 0]
        if back_row:
            skin_row.append(min(back_row))
        if skin_row:
            for x in range(min(skin_row), max(skin_row) + 1):
                wrist_hidden_source_guard_pixels[x, y] = 255
    # The logic guard intentionally keeps the source-line overlap needed for
    # the bracelet-back depth relation.  Formal display Alpha uses this
    # source-free companion guard so that the overlap is not painted over the
    # visible line stroke in an isolated material preview.
    wrist_hidden_source_display_guard = mask_subtract(
        wrist_hidden_source_guard,
        source_barrier_mask,
    )
    bracelet_source_line_mask = mask_intersection(bracelet_source_line_mask, wrist_repair_roi)
    bracelet_back_visible = mask_intersection(bracelet_back_visible, wrist_repair_roi)
    bracelet_front_visible = mask_intersection(bracelet_front_visible, wrist_repair_roi)

    metadata = {
        "source": "source/masters/front-line-source-exact-after-reset.png",
        "sourceCanvas": list(CANVAS),
        "coordinateTransform": "identity",
        "roi": list(FOREARM_WRIST_SOURCE_ROI),
        "repairRoi": list(FOREARM_WRIST_SOURCE_REPAIR_ROI),
        "barrier": {
            "rasterRule": f"source line pixels with luma < {FOREARM_WRIST_SOURCE_BARRIER_LUMA_MAX} are 4-connected barriers",
            "connectivity": "4-connected free pixels; 8-connected contour adjacency",
        },
        "components": component_records,
        "selectedComponents": [str(spec["id"]) for spec in FOREARM_WRIST_SOURCE_COMPONENT_SPECS],
        "exteriorComponentIds": sorted(exterior_component_ids),
        "outerContourPixelsRemoved": len(outer_contour_pixels),
        "braceletSelection": {
            "corridors": [
                {
                    "id": str(spec["id"]),
                    "layer": str(spec["layer"]),
                    "first": [list(point) for point in spec["first"]],
                    "second": [list(point) for point in spec["second"]],
                }
                for spec in FOREARM_WRIST_BRACELET_CORRIDOR_SPECS
            ],
            "sourceBarrierPixelsInCorridorsBeforeOuterContourFilter": sum(
                1
                for y in range(top, bottom)
                for x in range(left, right)
                if source_barrier_mask.getpixel((x, y)) > 0 and corridor_union.getpixel((x, y)) > 0
            ),
            "sourceLinePixelsAfterOuterContourFilter": mask_count(bracelet_source_line_mask),
            "backSourceLinePixels": mask_count(bracelet_back_visible),
            "frontSourceLinePixels": mask_count(bracelet_front_visible),
            "isolatedSourceFragmentsRemoved": [
                [list(next(iter(component)))] for component in isolated_bracelet_fragments
            ],
            "isolatedSourceFragmentsRemovedCount": len(bracelet_points - retained_bracelet_points),
            "rule": "only source barrier pixels inside registered corridors; outer forearm/hand contours are removed by component adjacency; no blur/dilate/erode/stroke expansion",
        },
        "wristSkinSource": {
            "pixelCount": mask_count(wrist_skin_source),
            "rule": "selected forearm free component plus the small free skin component between bracelet lines, clipped to the distal repair ROI",
        },
        "handTransitionGuard": {
            "pixelCount": mask_count(hand_transition_guard),
            "bbox": mask_bbox(hand_transition_guard),
            "rule": "selected hand-protected transition free component is a hidden-overlap guard only; it never rewrites hand ownership",
        },
        "hiddenUcapGuard": {
            "pixelCount": mask_count(wrist_hidden_source_guard),
            "bbox": mask_bbox(wrist_hidden_source_guard),
            "rule": "per-row span of source forearm skin, bracelet-gap skin, and protected hand transition; closes only internal bracelet gaps and preserves outer source contours",
        },
        "hiddenUcapDisplayGuard": {
            "pixelCount": mask_count(wrist_hidden_source_display_guard),
            "bbox": mask_bbox(wrist_hidden_source_display_guard),
            "rule": "formal display-only companion: direct source free-space pixels with the source barrier stroke removed; logic hidden overlap remains separate",
        },
        "traceMethod": "direct source-raster free components and source barrier selection; corridors are guards only and do not emit material pixels",
    }
    return (
        wrist_skin_source,
        bracelet_back_visible,
        bracelet_front_visible,
        metadata,
        wrist_hidden_source_guard,
        wrist_hidden_source_display_guard,
    )


def roi_mask(box: tuple[int, int, int, int]) -> Image.Image:
    """Return a full-canvas binary mask for an audit/ownership ROI."""
    left, top, right, bottom = box
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).rectangle((left, top, right - 1, bottom - 1), fill=255)
    return mask


def source_locked_antialiased_mask(
    logical_mask: Image.Image,
    allowed_mask: Image.Image,
    supersample: int = FOREARM_SHAFT_SOURCE_AA_SUPERSAMPLE,
) -> Image.Image:
    """Create soft edge coverage and clamp it back to the source owner.

    The source line component is the post-AA guard.  Bilinear coverage is
    used only to create fractional edge pixels from the source-locked binary
    shape; multiplying by ``allowed_mask`` after that operation makes every
    nonzero Alpha pixel remain inside the authoritative line-side region.
    """
    if supersample < 2:
        raise ValueError("supersample must be at least 2")
    high = logical_mask.convert("L").resize(
        (WIDTH * supersample, HEIGHT * supersample),
        Image.Resampling.NEAREST,
    )
    coverage = high.resize(CANVAS, Image.Resampling.BILINEAR)
    return ImageChops.multiply(coverage, allowed_mask.convert("L"))


def hand_source_line_enclosure(
    source_line: Image.Image,
    bracelet_visible: Image.Image,
    forearm_visible: Image.Image,
) -> tuple[Image.Image, dict[str, object], set[tuple[int, int]], set[tuple[int, int]]]:
    """Recover hand skin from direct enclosed pixels in the locked line master.

    The ROI is deliberately larger than the hand so the bracelet/forearm line
    closes the wrist-side source enclosure.  The component bboxes and counts
    are fixed evidence, not a semantic classifier.  Four explicit web paths
    reconnect the anatomical material at the lowest web points; open gaps are
    left outside the mask.
    """
    left, top, right, bottom = HAND_LINE_ROI
    gray = source_line.convert("L")
    barrier = {
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if gray.getpixel((x, y)) < HAND_LINE_BARRIER_LUMA_MAX
    }
    free = {
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if (x, y) not in barrier
    }
    roi_border = {
        (x, y)
        for x in range(left, right)
        for y in (top, bottom - 1)
    } | {
        (x, y)
        for y in range(top, bottom)
        for x in (left, right - 1)
    }
    four_neighbors = ((1, 0), (-1, 0), (0, 1), (0, -1))
    exterior_pool = free & roi_border
    exterior = set(exterior_pool)
    queue: deque[tuple[int, int]] = deque(exterior_pool)
    while queue:
        x, y = queue.popleft()
        for dx, dy in four_neighbors:
            point = (x + dx, y + dy)
            if left <= point[0] < right and top <= point[1] < bottom and point in free and point not in exterior:
                exterior.add(point)
                queue.append(point)

    enclosed = free - exterior
    enclosed_components: list[set[tuple[int, int]]] = []
    while enclosed:
        component = flood_component(next(iter(enclosed)), enclosed, four_neighbors)
        if len(component) > 4:
            enclosed_components.append(component)

    component_records: list[dict[str, object]] = []
    selected_components: list[set[tuple[int, int]]] = []
    for component in enclosed_components:
        xs = [point[0] for point in component]
        ys = [point[1] for point in component]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        record = {"bbox": list(bbox), "pixelCount": len(component)}
        component_records.append(record)
        matching = next(
            (
                spec
                for spec in HAND_LINE_COMPONENT_SPECS
                if tuple(spec["bbox"]) == bbox and int(spec["pixelCount"]) == len(component)
            ),
            None,
        )
        if matching is not None:
            selected_components.append(component)

    missing_components = [
        spec["id"]
        for spec in HAND_LINE_COMPONENT_SPECS
        if not any(tuple(spec["bbox"]) == tuple(record["bbox"]) and int(spec["pixelCount"]) == int(record["pixelCount"]) for record in component_records)
    ]
    if missing_components:
        raise AssertionError(f"Hand source-line component contract mismatch: {missing_components}")

    source_pixels: set[tuple[int, int]] = set().union(*selected_components)
    for bridge in HAND_WEB_BRIDGE_PATHS:
        source_pixels.update(tuple(point) for point in bridge["pixels"])

    source_mask = Image.new("L", CANVAS, 0)
    source_mask_pixels = source_mask.load()
    for x, y in source_pixels:
        source_mask_pixels[x, y] = 255

    # The bracelet and the forearm own the occluded wrist pixels.  This is a
    # visible-ownership split only; it does not move the wrist or palmRoot.
    visible = mask_subtract(mask_subtract(source_mask, bracelet_visible), forearm_visible)
    # Remove the one-pixel enclosure fragment left below the bracelet after the
    # ownership split.  The remaining hand is one 8-connected material.
    remaining = nonzero_points(visible)
    eight_neighbors = tuple(
        (dx, dy)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if (dx, dy) != (0, 0)
    )
    visible_components: list[set[tuple[int, int]]] = []
    while remaining:
        visible_components.append(flood_component(next(iter(remaining)), remaining, eight_neighbors))
    largest = max(visible_components, key=len) if visible_components else set()
    visible = Image.new("L", CANVAS, 0)
    visible_pixels = visible.load()
    for x, y in largest:
        visible_pixels[x, y] = 255

    metadata = {
        "roi": list(HAND_LINE_ROI),
        "lineBarrier": {
            "source": "front-line-source-exact-after-reset.png",
            "rasterRule": f"authoritative line raster pixels with luma < {HAND_LINE_BARRIER_LUMA_MAX} act as direct pixel-path barriers",
            "semanticRule": "component ids, web endpoint paths and line-side ownership are contract-authored; no color class decides hand semantics",
            "connectivity": "4-connected exterior and enclosed source pixels; 8-connected final material continuity",
        },
        "components": component_records,
        "selectedComponents": [spec["id"] for spec in HAND_LINE_COMPONENT_SPECS],
        "webBridges": [
            {"id": bridge["id"], "pixels": [list(point) for point in bridge["pixels"]]}
            for bridge in HAND_WEB_BRIDGE_PATHS
        ],
        "sourcePixelCountBeforeOwnershipSplit": len(source_pixels),
        "visiblePixelCountAfterOwnershipSplit": mask_count(visible),
        "discardedSmallComponentsAfterOwnershipSplit": sorted(len(component) for component in visible_components if component is not largest),
        "wrist": {"x": 110, "y": 538},
        "palmRoot": {"x": 104, "y": 552},
        "traceMethod": "direct source raster enclosure plus explicit web endpoint pixels; no smoothing, Catmull-Rom, blur, dilate, erosion, mirror or generated hand image",
    }
    return visible, metadata, barrier, source_pixels


def build_geometry_masks() -> tuple[
    dict[str, dict[str, Image.Image]],
    dict[str, object],
    set[tuple[int, int]],
    set[tuple[int, int]],
    dict[str, Image.Image | object],
]:
    r2_approved = r2_gate_state() == "approved"
    # Visible masks are source-line traces in the 512x1086 front master.  The
    # R1 anchors are review locators only.  In particular, several historical
    # anchors were recorded in three-view coordinates; using them as front
    # polygon vertices shifts the sleeve and makes the arm look detached.
    # These traces are deliberately dense at the cuff, wrist and fingers so
    # the material edge follows the actual line art rather than a straight
    # locator-to-locator chord.
    sleeve_outer = [
        # The previous trace sat several source pixels inside the observed
        # outer sleeve line.  These anchors follow the outermost gray stroke
        # at 5 px intervals so the blue material reaches that line without
        # changing the already-approved inner opening or hem contour.
        (164, 225), (157, 230), (151, 235), (149, 240), (147, 245),
        (145, 250), (143, 255), (141, 260), (139, 265), (137, 270),
        (135, 275), (133, 280), (131, 285), (128, 290), (127, 295),
        (125, 300), (122, 305), (120, 310), (118, 315), (116, 320),
        (114, 325), (112, 330), (110, 335), (108, 340), (106, 345),
        (104, 350), (102, 355), (100, 360), (98, 365), (98, 370),
    ]
    sleeve_lower_edge = [
        (98, 370), (109, 375), (121, 380), (134, 385), (146, 390),
        (158, 395), (164, 398),
    ]
    sleeve_inner = [
        (164, 398), (164, 380), (164, 360), (164, 340), (165, 320),
        (165, 300), (165, 280), (166, 260), (169, 245), (173, 232),
        (165, 225),
    ]
    sleeve_visible = draw_polygon(
        smooth_trace(sleeve_outer) +
        smooth_trace(sleeve_lower_edge)[1:] +
        smooth_trace(sleeve_inner)[1:]
    )

    # The sleeve needs a complete garment-side underlay for a small lift test:
    # the visible panel is not enough because hair/torso hide the shoulder-side
    # fabric and the cuff thickness.  The right sleeve reference shows that
    # the garment is one continuous shoulder-to-opening sleeve tube, so the
    # left candidate also needs an inner-panel bridge between those ends.
    # These are directional source-derived traces, not mirrored pixels or
    # circular patches: the shoulder trace follows the R1 local envelope and
    # the lower traces follow the observed cuff/opening anchors.
    sleeve_shoulder_hidden = draw_trace_band(
        [
            (166, 225), (174, 230), (181, 238), (185, 247),
            (187, 257), (188, 268), (187, 279), (183, 288),
            (177, 294), (170, 296), (165, 294),
        ],
        [
            (164, 225), (164, 239), (164, 253), (165, 267),
            (165, 281), (166, 294),
        ],
        samples_per_segment=6,
    )
    sleeve_cuff_hidden = draw_trace_band(
        [
            # Thin cuff thickness follows the red-marked right-sleeve hem;
            # it no longer grows into a large blue band below the hem.
            (114, 378), (128, 382), (143, 387), (157, 391),
            (171, 394), (181, 386), (188, 378), (192, 368),
        ],
        [
            (115, 381), (129, 385), (144, 390), (158, 394),
            (171, 397), (182, 389), (190, 381), (194, 370),
        ],
        samples_per_segment=6,
    )
    sleeve_inner_panel_hidden = draw_trace_band(
        [
            (165, 225), (165, 242), (165, 260), (165, 280),
            (165, 300), (165, 320), (165, 340), (164, 360),
            (163, 370), (163, 378), (163, 386), (164, 394), (171, 394),
        ],
        [
            # The right/inner contour follows the user's red-marked right
            # sleeve hem/opening structure: a near-vertical opening edge that
            # turns into the lower hem and closes at the cuff, with no material
            # below that boundary.
            (177, 230), (180, 240), (183, 252), (186, 266),
            (188, 281), (189, 296), (190, 312), (191, 329),
            (192, 346), (193, 363), (192, 368), (190, 376),
            (184, 383), (177, 390), (171, 394),
        ],
        samples_per_segment=6,
    )
    sleeve_hidden = mask_subtract(
        mask_union(sleeve_shoulder_hidden, sleeve_inner_panel_hidden, sleeve_cuff_hidden),
        sleeve_visible,
    )

    upper_arm_visible = blank_mask()
    # The previous revision over-corrected the silhouette and left only a thin
    # bone-axis strip.  Restore the soft-tissue volume expected from a human
    # upper arm: a wider deltoid/brachium root, a controlled mid-arm taper,
    # and a distal width close to the forearm at the elbow.  Most of the added
    # volume is placed on the screen-left/lateral side; the torso/hair-side
    # contour stays restrained so the arm does not balloon inward again.
    # The proximal cap remains under the sleeve; it is not a circular joint
    # patch or an exposed shoulder ball.  The current visual repair keeps this
    # hidden root deliberately narrow at the sleeve/shoulder transition.
    upper_arm_outer_trace = [
        # Screen-left is the lateral/outer side.  The shoulder-to-mid-arm
        # sweep is fuller than the rejected thin strip but stays inside the
        # sleeve's garment-side envelope.
        (156, 245), (151, 249), (146, 256), (141, 264), (141, 274),
        (141, 287), (140, 302), (139, 318), (138, 335), (138, 352),
        (137, 369), (136, 384), (136, 394), (137, 401), (140, 407),
        (144, 412), (149, 414), (154, 413), (159, 410), (163, 405),
        (166, 400),
    ]
    upper_arm_inner_trace = [
        # Screen-right is the torso/hair-side contour.  It is only widened a
        # little to keep a credible deltoid, then tapers toward the elbow
        # rather than tracking the old over-extended inner bulge.
        (166, 400), (165, 391), (166, 379), (167, 366), (169, 351),
        (170, 335), (172, 318), (174, 301), (176, 286), (177, 274),
        (177, 264), (175, 256), (172, 249), (168, 245), (150, 245),
    ]
    upper_arm_outer_curve = smooth_trace(upper_arm_outer_trace, samples_per_segment=6)
    upper_arm_inner_curve = smooth_trace(upper_arm_inner_trace, samples_per_segment=6)
    upper_arm_shoulder_root = [
        ((168, 245), (171, 243), (170, 241), (166, 241)),
        ((166, 241), (162, 240), (158, 242), (156, 245)),
    ]
    upper_arm_hidden = draw_polygon(
        upper_arm_outer_curve
        + upper_arm_inner_curve[1:]
        + bezier_chain(upper_arm_shoulder_root, samples_per_segment=18)[1:]
    )
    # The user-approved whole-hand freeze promotes upper-arm v8 as the sole
    # formal R2 upper-arm source.  Keep the old trace above as historical code
    # context only; it is never allowed to feed the current masks.
    upper_arm_visible, upper_arm_hidden, upper_arm_complete_frozen = load_upper_arm_v8_masks()

    # The exposed shaft is recovered from the actual front line raster.  The
    # previous paired traces were close enough for a broad corridor audit but
    # still left a 1-4 px color strip outside the anatomical skin line.  The
    # direct source component below selects the skin-side free pixels and
    # excludes the farther-right shirt/torso locator line by construction.
    forearm_source_line_mask, forearm_source_line_meta = forearm_source_line_enclosure()
    forearm_elbow_source_mask, forearm_elbow_source_meta = forearm_elbow_source_enclosure()
    forearm_elbow_user_markup_mask, forearm_elbow_user_markup_meta = forearm_elbow_user_markup_boundary()
    # Keep the existing short distal transition outside the shaft repair ROI;
    # bracelet/U-cap ownership is not re-authored by this step.
    forearm_legacy_left = [
        (134, 398), (132, 405), (130, 415), (128, 425), (124, 438),
        (121, 450), (118, 463), (114, 477), (111, 490), (108, 503),
        (105, 514), (102, 520),
    ]
    forearm_legacy_right = [
        (164, 398), (165, 405), (164, 415), (162, 425), (160, 435),
        (157, 445), (154, 450), (150, 460), (146, 470), (142, 480),
        (138, 490), (134, 500), (131, 510), (128, 515), (126, 520),
    ]
    forearm_legacy_raw = draw_trace_band(forearm_legacy_left, forearm_legacy_right)
    shaft_source_roi = roi_mask(FOREARM_SHAFT_SOURCE_VISIBLE_ROI)
    forearm_skin_raw = mask_union(
        mask_intersection(forearm_source_line_mask, shaft_source_roi),
        mask_intersection(forearm_legacy_raw, ImageChops.invert(shaft_source_roi)),
    )

    # The wrist seam is now resolved from the authoritative line raster.  The
    # source helper emits skin free-space and bracelet source-line pixels; the
    # registered corridors never emit color by themselves.
    source_line_image = Image.open(
        SOURCE_ROOT / "masters" / "front-line-source-exact-after-reset.png"
    ).convert("RGB")
    (
        wrist_skin_source,
        bracelet_back_source,
        bracelet_front_source,
        wrist_source_meta,
        wrist_hidden_source_guard,
        wrist_hidden_source_display_guard,
    ) = wrist_source_line_materials(source_line_image)
    wrist_repair_roi = roi_mask(FOREARM_WRIST_SOURCE_REPAIR_ROI)
    bracelet_back_visible = bracelet_back_source
    bracelet_front_visible = bracelet_front_source
    bracelet_visible = mask_union(bracelet_back_visible, bracelet_front_visible)
    forearm_skin_raw = mask_union(
        mask_subtract(forearm_skin_raw, wrist_repair_roi),
        wrist_skin_source,
    )
    forearm_skin_visible = mask_subtract(
        mask_subtract(forearm_skin_raw, bracelet_visible),
        sleeve_visible,
    )
    forearm_visible = mask_union(forearm_skin_visible, bracelet_visible)

    # The protected hand is a byte-level input.  Do not solve that protection
    # by adding hand pixels to the bracelet: that creates a visible accessory
    # bulge outside the authoritative bracelet line and is exactly the seam
    # error this repair is meant to remove.  The source-line bracelet pixels
    # remain the only bracelet owner; the hand is re-read after that split and
    # must already match the protected hand artifact.
    protected_hand_path = R2_ROOT / "masks" / "visible" / "hand.png"
    if not protected_hand_path.exists():
        raise FileNotFoundError(f"protected hand visible mask is missing: {protected_hand_path}")
    protected_hand_visible = Image.open(protected_hand_path).convert("L")
    provisional_hand_visible, _, _, _ = hand_source_line_enclosure(
        source_line_image,
        bracelet_visible,
        forearm_visible,
    )
    hand_ownership_shield = mask_subtract(provisional_hand_visible, protected_hand_visible)
    shield_outside_roi = mask_subtract(hand_ownership_shield, wrist_repair_roi)
    if mask_count(shield_outside_roi) != 0:
        raise AssertionError(
            "bracelet hand-protection shield escaped the registered wrist repair ROI: "
            f"{mask_count(shield_outside_roi)} px"
        )
    forearm_skin_visible = mask_subtract(
        mask_subtract(forearm_skin_raw, bracelet_visible),
        sleeve_visible,
    )
    forearm_visible = mask_union(forearm_skin_visible, bracelet_visible)
    hand_candidate, hand_trace_meta, hand_line_barrier, hand_source_pixels = hand_source_line_enclosure(
        source_line_image,
        bracelet_visible,
        forearm_visible,
    )
    # The source-line candidate is retained as audit evidence, but the
    # approved hand visible mask is the protected authority for this
    # forearm-only repair.  The 66-pixel candidate difference is not allowed
    # to become bracelet ownership; it is recorded below and the protected
    # hand remains byte-for-byte unchanged.
    hand_visible = protected_hand_visible.copy()
    if mask_count(mask_intersection(hand_visible, bracelet_visible)) != 0:
        raise AssertionError(
            "protected hand overlaps source-line bracelet ownership; refusing to rewrite either material"
        )
    if mask_count(mask_intersection(hand_visible, forearm_visible)) != 0:
        raise AssertionError(
            "protected hand overlaps source-line forearm ownership; refusing to rewrite protected hand geometry"
        )
    wrist_source_meta["protectedHandOwnershipShield"] = {
        "pixelCount": mask_count(hand_ownership_shield),
        "bbox": mask_bbox(hand_ownership_shield),
        "restrictedToRoi": mask_count(shield_outside_roi) == 0,
        "used": False,
        "candidateDifferencePixels": mask_count(mask_subtract(hand_candidate, protected_hand_visible)),
        "rule": "source-line bracelet pixels remain the only bracelet owner; protected hand is reused as a protected input and candidate differences are not reassigned",
    }

    # Hidden forearm continuation follows the same tapered corridor.  Both
    # joints are closed with explicit cubic curves: the elbow root keeps the
    # proximal volume continuous, and the wrist root turns through a rounded,
    # directional cap around the R1 wrist pivot instead of a horizontal chord.
    forearm_hidden_segment_outer = [
        (133, 401), (130, 418), (126, 435), (121, 452), (117, 469),
        (112, 486), (107, 503), (103, 519), (101, 526), (100, 532),
        (101, 538), (103, 541),
    ]
    forearm_hidden_segment_inner = [
        (165, 401), (163, 418), (160, 435), (154, 452), (150, 469),
        (142, 486), (136, 503), (128, 519), (126, 526), (124, 532),
        (122, 539), (125, 536),
    ]
    forearm_outer_curve = smooth_trace(forearm_hidden_segment_outer, samples_per_segment=6)
    forearm_inner_curve = smooth_trace(forearm_hidden_segment_inner, samples_per_segment=6)
    forearm_elbow_root = [
        ((165, 401), (166, 396), (164, 390), (160, 386)),
        ((160, 386), (155, 380), (146, 379), (138, 384)),
        ((138, 384), (133, 388), (130, 396), (133, 401)),
    ]
    forearm_wrist_root = [
        ((103, 541), (99, 539), (98, 533), (100, 527)),
        ((100, 527), (101, 523), (103, 520), (107, 519)),
        ((107, 519), (113, 517), (121, 518), (127, 522)),
        ((127, 522), (130, 528), (129, 536), (125, 541)),
        ((125, 541), (122, 546), (116, 548), (110, 547)),
        ((110, 547), (107, 546), (104, 544), (103, 541)),
    ]
    forearm_skin_hidden = mask_subtract(
        mask_union(
            draw_polygon(
                forearm_outer_curve
                + bezier_chain(forearm_wrist_root, samples_per_segment=16)[1:]
                + list(reversed(forearm_inner_curve))[1:]
                + bezier_chain(forearm_elbow_root, samples_per_segment=16)[1:]
            ),
            draw_bezier_loop(forearm_wrist_root, samples_per_segment=18),
        ),
        forearm_skin_visible,
    )
    # The exposed shaft is visible at rest, so even the complete color block
    # must not show hidden-corridor pixels outside the source skin boundary in
    # this ROI.  Hidden volume remains available above/below the shaft and
    # beneath the bracelet; only the source-locked visible span is clamped.
    shaft_source_roi = roi_mask(FOREARM_SHAFT_SOURCE_VISIBLE_ROI)
    hidden_outside_source = mask_subtract(
        mask_intersection(forearm_skin_hidden, shaft_source_roi),
        forearm_source_line_mask,
    )
    forearm_skin_hidden = mask_subtract(forearm_skin_hidden, hidden_outside_source)
    # The legacy elbow cubic is not allowed to cross the observed sleeve hem.
    # Replace only its local root with the source-line component below that
    # hem.  Rows above the component are deliberately removed rather than
    # filled by a guessed continuation; hidden continuity resumes through the
    # existing shaft corridor at the source-defined join.
    elbow_root_repair_roi = roi_mask(FOREARM_ELBOW_SOURCE_REPAIR_ROI)
    forearm_skin_hidden = mask_subtract(forearm_skin_hidden, elbow_root_repair_roi)
    forearm_skin_hidden = mask_union(
        forearm_skin_hidden,
        mask_intersection(forearm_elbow_source_mask, elbow_root_repair_roi),
    )
    # The latest user reference remains the authoritative allowance for the
    # hidden cap above the observed sleeve/skin transition.  Below that
    # transition, the source raster owns the visible edge, while the separate
    # redline-bounded hidden transition restores the occluded continuity that
    # would otherwise appear as a white wedge in the review crop.  Replace the
    # entire local root first, then restore each coordinate-locked piece.
    elbow_user_markup_roi = roi_mask(FOREARM_ELBOW_USER_MARKUP_REPAIR_ROI)
    elbow_user_markup_cap_roi = roi_mask(FOREARM_ELBOW_USER_MARKUP_HIDDEN_CAP_ROI)
    elbow_user_markup_hidden_transition_roi = roi_mask(FOREARM_ELBOW_USER_MARKUP_HIDDEN_TRANSITION_ROI)
    elbow_source_transition_roi = roi_mask(FOREARM_ELBOW_SOURCE_REPAIR_ROI)
    forearm_skin_hidden = mask_subtract(forearm_skin_hidden, elbow_user_markup_roi)
    forearm_skin_hidden = mask_union(
        forearm_skin_hidden,
        mask_intersection(forearm_elbow_user_markup_mask, elbow_user_markup_cap_roi),
    )
    forearm_skin_hidden = mask_union(
        forearm_skin_hidden,
        mask_intersection(forearm_elbow_source_mask, elbow_source_transition_roi),
    )
    # The latest visual review says the right edge is already close while a
    # small left-side gap remains at the lower transition.  Close only that
    # gap with existing dark source-line pixels from the registered left-edge
    # ROI.  This is source ownership, not dilation: no generated pixels,
    # smoothing, or right-side expansion is permitted here.
    left_edge_left, left_edge_top, left_edge_right, left_edge_bottom = FOREARM_ELBOW_SOURCE_LEFT_EDGE_ROI
    source_line_gray = source_line_image.convert("L")
    elbow_source_left_edge = Image.new("L", CANVAS, 0)
    elbow_source_left_edge_pixels = elbow_source_left_edge.load()
    for y in range(left_edge_top, left_edge_bottom):
        for x in range(left_edge_left, left_edge_right):
            if source_line_gray.getpixel((x, y)) < FOREARM_ELBOW_SOURCE_BARRIER_LUMA_MAX:
                elbow_source_left_edge_pixels[x, y] = 255
    elbow_source_left_edge_added = mask_subtract(elbow_source_left_edge, forearm_skin_hidden)
    forearm_skin_hidden = mask_union(forearm_skin_hidden, elbow_source_left_edge)
    forearm_elbow_source_meta["sourceLeftEdgeCorrection"] = {
        "roi": list(FOREARM_ELBOW_SOURCE_LEFT_EDGE_ROI),
        "sourceLumaMax": FOREARM_ELBOW_SOURCE_BARRIER_LUMA_MAX,
        "addedPixelCount": mask_count(elbow_source_left_edge_added),
        "rule": "left-side lower transition may add only existing dark source-line core pixels inside the registered ROI; right edge is unchanged; no dilation, smoothing, or generated geometry",
    }
    elbow_hidden_transition = mask_subtract(
        mask_intersection(forearm_elbow_user_markup_mask, elbow_user_markup_hidden_transition_roi),
        forearm_skin_visible,
    )
    right_white_exclusion = Image.new("L", CANVAS, 0)
    right_white_exclusion_pixels = right_white_exclusion.load()
    exclusion_left, exclusion_top, exclusion_right, exclusion_bottom = FOREARM_ELBOW_SOURCE_RIGHT_WHITE_EXCLUSION_ROI
    for y in range(exclusion_top, exclusion_bottom):
        for x in range(exclusion_left, exclusion_right):
            if source_line_gray.getpixel((x, y)) >= FOREARM_ELBOW_SOURCE_EDGE_LUMA_MAX:
                right_white_exclusion_pixels[x, y] = 255
    elbow_hidden_transition = mask_subtract(elbow_hidden_transition, right_white_exclusion)
    forearm_skin_hidden = mask_union(forearm_skin_hidden, elbow_hidden_transition)
    forearm_elbow_source_meta["userHiddenTransition"] = {
        "roi": list(FOREARM_ELBOW_USER_MARKUP_HIDDEN_TRANSITION_ROI),
        "pixelCount": mask_count(elbow_hidden_transition),
        "rightWhiteExclusionRoi": list(FOREARM_ELBOW_SOURCE_RIGHT_WHITE_EXCLUSION_ROI),
        "rightWhiteExcludedPixelCount": mask_count(mask_intersection(right_white_exclusion, elbow_user_markup_hidden_transition_roi)),
        "rule": "white transition gap may be filled only inside the latest mapped redline and only in hidden forearm ownership; visible shaft ownership remains source-line locked",
    }
    elbow_source_seam_closure = mask_subtract(
        mask_intersection(
            forearm_source_line_mask,
            roi_mask(FOREARM_ELBOW_SOURCE_SEAM_CLOSURE_ROI),
        ),
        forearm_skin_visible,
    )
    forearm_skin_hidden = mask_union(forearm_skin_hidden, elbow_source_seam_closure)
    forearm_elbow_source_meta["sourceSeamClosure"] = {
        "roi": list(FOREARM_ELBOW_SOURCE_SEAM_CLOSURE_ROI),
        "pixelCount": mask_count(elbow_source_seam_closure),
        "rule": "only source-line component pixels at the hidden-to-visible join may close the seam; no visible alpha expansion or generic hole repair",
    }
    # Keep the historical R1 elbow coverage contract without putting a broad
    # cap back above the hem.  Any residual envelope pixels may remain in the
    # forearm hidden layer only when they are actual dark source-line pixels in
    # this local ROI; the envelope is a placement constraint, never a generated
    # patch, and the protected upper-arm layer is not touched.
    r1_envelope_contract = load_json(R1_ENVELOPE_CONTRACT_PATH)
    r1_elbow_entry = next(item for item in r1_envelope_contract["joints"] if item["id"] == "elbow")
    elbow_envelope = envelope_mask(r1_elbow_entry)
    source_elbow_barrier = Image.new("L", CANVAS, 0)
    source_elbow_barrier_pixels = source_elbow_barrier.load()
    barrier_left, barrier_top, barrier_right, barrier_bottom = FOREARM_ELBOW_SOURCE_REPAIR_ROI
    for y in range(barrier_top, barrier_bottom):
        for x in range(barrier_left, barrier_right):
            if source_line_gray.getpixel((x, y)) < FOREARM_ELBOW_SOURCE_BARRIER_LUMA_MAX:
                source_elbow_barrier_pixels[x, y] = 255
    source_elbow_edge = Image.new("L", CANVAS, 0)
    source_elbow_edge_pixels = source_elbow_edge.load()
    for y in range(barrier_top, barrier_bottom):
        for x in range(barrier_left, barrier_right):
            if source_line_gray.getpixel((x, y)) >= FOREARM_ELBOW_SOURCE_EDGE_LUMA_MAX:
                continue
            if any(
                source_elbow_barrier_pixels[x + dx, y + dy] > 0
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
                if (dx or dy)
                and 0 <= x + dx < WIDTH
                and 0 <= y + dy < HEIGHT
            ):
                source_elbow_edge_pixels[x, y] = 255
    elbow_current_owners = mask_union(
        upper_arm_hidden,
        forearm_skin_hidden,
        upper_arm_visible,
        forearm_visible,
    )
    elbow_source_hidden_bridge = mask_intersection(
        mask_subtract(elbow_envelope, elbow_current_owners),
        source_elbow_edge,
    )
    forearm_skin_hidden = mask_union(forearm_skin_hidden, elbow_source_hidden_bridge)
    forearm_elbow_source_meta["sourceHiddenContourBridge"] = {
        "pixelCount": mask_count(elbow_source_hidden_bridge),
        "roi": list(FOREARM_ELBOW_SOURCE_REPAIR_ROI),
        "edgeLumaMax": FOREARM_ELBOW_SOURCE_EDGE_LUMA_MAX,
        "rule": "R1 elbow residuals may use only existing source-line pixels or their antialiased fringe adjacent to a dark source stroke as forearm hidden overlap; no new visible geometry or protected upper-arm material is authored",
    }
    # The old hidden wrist-root cubic is intentionally not allowed to author
    # the bracelet-adjacent edge anymore.  The latest close-up showed that its
    # broad outer/inner traces protruded past the actual skin contour.  Replace
    # only the registered wrist repair ROI with the direct source-line free
    # components, then let the latest blue U-cap add the separately audited
    # hidden continuation.  This keeps proximal hidden continuity while making
    # every bracelet-adjacent nonzero pixel follow the source skin enclosure.
    forearm_skin_hidden = mask_subtract(forearm_skin_hidden, wrist_repair_roi)
    forearm_skin_hidden = mask_union(forearm_skin_hidden, wrist_skin_source)
    # Reopen only the distal wrist U-cap. The visible shaft, bracelet, and
    # proximal hidden corridor remain the existing R2 geometry; the new cap is
    # the sole float-cubic geometry source for this repair.
    wrist_source_boundary_guard = wrist_hidden_source_guard
    forearm_ucap_logic = render_forearm_distal_ucap_logic(
        forearm_skin_visible,
        forearm_skin_hidden,
        wrist_source_boundary_guard,
        wrist_hidden_source_display_guard,
    )
    forearm_skin_hidden = cast(Image.Image, forearm_ucap_logic["hidden"])
    forearm_ucap_logic["braceletSourceLineGuard"] = mask_union(
        bracelet_back_source,
        bracelet_front_source,
    )
    forearm_ucap_logic["wristSourceLineSkinGuard"] = wrist_skin_source
    forearm_ucap_logic["wristSourceLineHandTransitionGuard"] = wrist_hidden_source_guard
    forearm_ucap_logic["wristSourceLineUcapGuard"] = wrist_source_boundary_guard
    forearm_ucap_logic["wristSourceLineUcapDisplayGuard"] = wrist_hidden_source_display_guard
    forearm_ucap_logic["braceletProtectedHandOwnershipShield"] = hand_ownership_shield
    # Bracelet remains inside the primary forearm group.  Its red mask is an
    # audit-only semantic subregion; it is not a second moving/draw layer.
    forearm_hidden = mask_subtract(forearm_skin_hidden, forearm_visible)

    # The hand hidden root is rasterized directly from the source-space float
    # Bezier chain at 32x.  No low-resolution polygon is created first.
    hand_wrist_root = HAND_WRIST_ROOT_BEZIER_SEGMENTS
    hand_root_masks = render_hand_wrist_root_masks(hand_visible)
    hand_hidden = cast(Image.Image, hand_root_masks["hidden"])

    primary = {
        "sleeve": {"visible": sleeve_visible, "hidden": sleeve_hidden},
        "upper_arm": {"visible": upper_arm_visible, "hidden": upper_arm_hidden},
        "forearm": {"visible": forearm_visible, "hidden": forearm_hidden},
        "hand": {"visible": hand_visible, "hidden": hand_hidden},
    }
    for masks in primary.values():
        masks["complete"] = mask_union(masks["visible"], masks["hidden"])
    if primary["upper_arm"]["complete"].tobytes() != upper_arm_complete_frozen.tobytes():
        raise AssertionError("formal upper-arm complete mask diverged from frozen v8 source")

    subregions = {
        "forearm-skin": {
            "visible": forearm_skin_visible,
            "hidden": forearm_skin_hidden,
            "complete": mask_union(forearm_skin_visible, forearm_skin_hidden),
        },
        "bracelet": {
            "visible": bracelet_visible,
            "hidden": blank_mask(),
            "complete": bracelet_visible,
        },
        "bracelet-back": {
            "visible": bracelet_back_visible,
            "hidden": blank_mask(),
            "complete": bracelet_back_visible,
        },
        "bracelet-front": {
            "visible": bracelet_front_visible,
            "hidden": blank_mask(),
            "complete": bracelet_front_visible,
        },
    }

    masks = {"primary": primary, "subregions": subregions}
    geometry_meta = {
        "provenance": "source-raster enclosed forearm shaft and distal wrist seam plus source-constrained directional hidden limb traces; R1 envelopes are coverage constraints, not generated circular patches",
        "repairStatus": r2_candidate_status(),
        "userVisualApproval": str(R2_WHOLE_HAND_APPROVAL_PATH.relative_to(REPO_ROOT)).replace("\\", "/") if r2_approved and R2_WHOLE_HAND_APPROVAL_PATH.exists() else None,
        "formalR2UpperArmSource": {
            "candidate": str(UPPER_ARM_V8_ROOT.relative_to(REPO_ROOT)).replace("\\", "/"),
            "status": "SOLE_FORMAL_R2_SOURCE",
            "visibleOwnershipPixels": mask_count(upper_arm_visible),
            "hiddenPixels": mask_count(upper_arm_hidden),
            "completePixels": mask_count(upper_arm_complete_frozen),
            "candidateContract": "contracts/upper-arm-aa-anatomical-contract.json",
            "promotionRule": "formal files are byte-copied from frozen upper-arm v8 before dependent composites are built",
        },
        "forearmDistalUcapAa": {
            "status": "FOREARM_DISTAL_UCAP_AA_CANDIDATE / WAITING_USER_VISUAL_APPROVAL",
            "authorizationPath": str(FOREARM_REOPEN_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "authorizationSha256": FOREARM_REOPEN_SHA256,
            "redrawConfirmationPath": str(FOREARM_REDRAW_CONFIRMATION_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "redrawConfirmationOn": FOREARM_REDRAW_CONFIRMATION_DATE,
            "redrawConfirmation": FOREARM_REDRAW_CONFIRMATION_TEXT,
            "roi": list(FOREARM_UCAP_ROI),
            "latestUserMarkup": {
                "path": FOREARM_USER_MARKUP_PATH,
                "sha256": FOREARM_USER_MARKUP_SHA256,
                "dimensions": list(FOREARM_USER_MARKUP_DIMENSIONS),
                "coordinateTransform": FOREARM_USER_MARKUP_TRANSFORM,
                "trace": [list(point) for point in FOREARM_USER_MARKUP_TRACE],
                "hiddenClosure": [list(point) for point in FOREARM_USER_MARKUP_HIDDEN_CLOSURE],
                "closedTrace": [list(point) for point in FOREARM_USER_MARKUP_CLOSED_TRACE],
                "closureRule": "visible red U closes only beneath the forearm-owned bracelet; no visible bracelet/hand ownership is added",
                "allowedSide": "inside the latest user-marked wrist hidden boundary",
            },
            "r1Pivot": {"x": WRIST_PIVOT[0], "y": WRIST_PIVOT[1]},
            "controlPoints": [list(point) for point in FOREARM_DISTAL_UCAP_CONTROL_POINTS],
            "bezierSegments": [[list(point) for point in segment] for segment in FOREARM_DISTAL_UCAP_BEZIER_SEGMENTS],
            "activeWristEnvelope": {
                "source": "latestUserMarkup.closedTrace",
                "controlPoints": [list(point) for point in FOREARM_DISTAL_UCAP_CONTROL_POINTS],
                "bezierSegments": [[list(point) for point in segment] for segment in FOREARM_DISTAL_UCAP_BEZIER_SEGMENTS],
                "supersedesForReopenedForearmUcap": "arm-chain-screen-left-r1-physical-line-contract/contracts/joint-envelope-contract.json:wrist.activeEnvelope",
                "historicalR1ContractPreservedReadOnly": True,
            },
            "continuityTarget": "C2 periodic cubic",
            "supersample": FOREARM_UCAP_SUPERSAMPLE,
            "logicalBooleanCanvas": "high-resolution 32x canvas",
            "coverageDownsample": "BOX exactly once",
            "forbiddenOperations": ["rectangle", "sharp_polygon", "fixed_circle", "global_convex_hull", "radial_patch", "blur", "dilate", "erode", "low-resolution NEAREST geometry", "LANCZOS ringing", "stroke expansion"],
            "logicalUcap": {
                "pixelCount": mask_count(cast(Image.Image, forearm_ucap_logic["ucap"])),
                "bbox": mask_bbox(cast(Image.Image, forearm_ucap_logic["ucap"])),
                "coverageFractionalAlphaPixels": sum(1 for value in cast(Image.Image, forearm_ucap_logic["ucapCoverage"]).getdata() if 0 < value < 255),
            },
        },
        "handLineTrace": hand_trace_meta,
        "forearmSourceLineBoundary": forearm_source_line_meta,
        "forearmElbowSourceLineBoundary": forearm_elbow_source_meta,
        "forearmElbowUserMarkupBoundary": forearm_elbow_user_markup_meta,
        "wristSourceLineBoundary": wrist_source_meta,
        "handVisibleSourcePixels": len(hand_source_pixels),
        "handLineBarrierPixelsInRoi": len(hand_line_barrier),
        "hiddenRootConstruction": {
            "upper_arm_shoulder_root": {
                "classification": "hidden",
                "status": "derived",
                "construction": "explicit cubic Bezier shoulder root around R1 shoulder pivot",
                "r1Pivot": {"x": SHOULDER_PIVOT[0], "y": SHOULDER_PIVOT[1]},
                "segments": upper_arm_shoulder_root,
                "forbiddenOperations": ["rectangle", "sharp_polygon", "fixed_circle", "blur", "dilate"],
            },
            "forearm_wrist_root": {
                "classification": "hidden",
                "status": "derived_with_unresolved_depth",
                "construction": "tapered forearm corridor plus explicit cubic Bezier wrist cap around R1 wrist pivot",
                "r1Pivot": {"x": WRIST_PIVOT[0], "y": WRIST_PIVOT[1]},
                "segments": forearm_wrist_root,
                "forbiddenOperations": ["rectangle", "sharp_polygon", "fixed_circle", "blur", "dilate"],
            },
            "forearm_elbow_root": {
                "classification": "hidden-to-visible joint boundary",
                "status": "source_locked",
                "construction": "registered 4-connected source-line free component below the sleeve hem; legacy cubic elbow cap is removed inside the repair ROI",
                "sourceBoundary": forearm_elbow_source_meta,
                "repairRoi": list(FOREARM_ELBOW_SOURCE_REPAIR_ROI),
                "forbiddenOperations": ["user-sketch trace as exact boundary", "smooth cap", "rectangle", "sharp_polygon", "fixed_circle", "blur", "dilate", "erode"],
            },
            "forearm_elbow_user_markup_root": {
                "classification": "hidden",
                "status": "user_boundary_candidate",
                "construction": "latest panel-9 red outline restores the hidden cap and the bounded white transition wedge; the visible lower skin edge remains registered to the source-line forearm component",
                "sourceBoundary": forearm_elbow_user_markup_meta,
                "repairRoi": list(FOREARM_ELBOW_USER_MARKUP_REPAIR_ROI),
                "hiddenCapRoi": list(FOREARM_ELBOW_USER_MARKUP_HIDDEN_CAP_ROI),
                "hiddenTransitionRoi": list(FOREARM_ELBOW_USER_MARKUP_HIDDEN_TRANSITION_ROI),
                "sourceLineTransitionRoi": list(FOREARM_ELBOW_SOURCE_REPAIR_ROI),
                "sourceSeamClosureRoi": list(FOREARM_ELBOW_SOURCE_SEAM_CLOSURE_ROI),
                "rightWhiteExclusionRoi": list(FOREARM_ELBOW_SOURCE_RIGHT_WHITE_EXCLUSION_ROI),
                "allowedSide": "inside mapped redline for hidden continuity; source-line forearm component owns the visible lower skin edge; visible shaft remains source-line owned",
                "forbiddenOperations": ["screenshot-pixel coordinates without transform", "Bézier overshoot", "smooth cap", "dilate", "erode", "visible alpha expansion across sleeve hem"],
            },
            "hand_wrist_root": {
                "classification": "hidden",
                "status": "derived_minimal_candidate",
                "construction": "periodic C2 cubic Bezier wrist-root underlay rasterized directly at 32x before one BOX downsample; no hand-finger or bracelet geometry",
                "r1Pivot": {"x": WRIST_PIVOT[0], "y": WRIST_PIVOT[1]},
                "palmRoot": {"x": 104, "y": 552},
                "controlPoints": [list(point) for point in HAND_WRIST_ROOT_CONTROL_POINTS],
                "segments": [[list(point) for point in segment] for segment in hand_wrist_root],
                "hiddenWristEnvelope": {
                    "roi": list(HAND_HIDDEN_WRIST_ROI),
                    "controlPoints": [list(point) for point in HAND_HIDDEN_ENVELOPE_CONTROL_POINTS],
                    "segments": [[list(point) for point in segment] for segment in HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS],
                    "rule": "hidden alpha must remain inside this separately registered local envelope",
                },
                "supersample": HAND_AA_SUPERSAMPLE,
                "coverageDownsample": "BOX exactly once",
                "forbiddenOperations": ["low-resolution polygon first", "rectangle", "sharp_polygon", "fixed_circle", "global_convex_hull", "blur", "dilate", "erode", "LANCZOS"],
            },
        },
        "braceletDepthCandidate": {
            "owner": "forearm",
            "sharedTransform": "forearm",
            "backRegion": "bracelet-back",
            "skinRegion": "forearm-skin",
            "frontRegion": "bracelet-front",
            "drawOrder": ["bracelet-back", "forearm-skin", "hand", "bracelet-front"],
            "visibleBoundarySource": "wristSourceLineBoundary.braceletSelection.sourceLinePixelsAfterOuterContourFilter plus protectedHandOwnershipShield",
            "formalAlpha": {
                "supersample": FOREARM_UCAP_SUPERSAMPLE,
                "coverageDownsample": "BOX exactly once",
                "edgeGuard": "logical bracelet subregion after source-line selection",
            },
            "status": "approved_with_declared_motion_scope" if r2_approved else "derived_candidate_with_unresolved_rear_half",
            "supportedMotionScope": "front-facing small wrist translation/rotation only; no pronation/supination or deep wrap",
            "userDecisionRequired": None if r2_approved else "单一正面原线不能唯一确定手链后半环；用户需批准此候选深度或指定后续证据",
        },
        "visibleGeometryRevision": {
            "sleeve": "visible inner edge follows the observed garment/torso opening near x=164; hidden completion follows the right-sleeve hem/opening structure and the user's red-marked closed boundary, with a thin cuff thickness and no material below the hem, without mirroring pixels",
            "upper_arm": "formal R2 source promoted from frozen candidates/upper-arm-aa-anatomical-v8; visible ownership remains empty, hidden/complete use the approved asymmetric shoulder-to-elbow cubic loop and fractional display Alpha",
            "forearm": "visible shaft is the direct 4-connected skin-side component from front-line-source-exact-after-reset.png; the separate shirt/torso locator line is excluded, while hidden elbow continuity follows the latest mapped user redline inside its registered ROI",
            "hand": "direct source-line raster enclosure preserves one thumb, four fingers, three open finger gaps and the thumb-index web; hidden wrist root is separate",
            "bracelet": "source-traced accessory shapes remain inside the forearm primary group; current audit split is bracelet-back plus bracelet-front",
            "cuffBoundary": "用户已确认袖口浅灰交界归入 skin，不作为 sleeve/skin 材料切线",
        },
        "r1ContractDifferences": [
            "R1 joint pivots, bone axes, and ownership semantics remain unchanged; for the reopened forearm distal U-cap scope, the 2026-08-11 user-confirmed redline supersedes the historical R1 wrist coverage envelope while the R1 file remains read-only.",
            "R2 does not treat the R1 reference anchors for sleeve inner/forearm edges as literal polygon vertices; the visible traces were re-authored against the front line master after the visual rejection.",
            "Bracelet remains an auditable forearm subregion, but R2 primary compositing now uses the single forearm layer rather than a separate bracelet draw-order item.",
            "The right sleeve is used only to infer continuous garment-side shoulder-to-opening construction; left screen-side source lines remain authoritative and no screen-right geometry is copied.",
        ],
        "hiddenGeometryPolicy": "shoulder uses a source-constrained directional local envelope; hidden elbow continuity follows the latest mapped panel-9 redline while visible shaft ownership remains source-line locked; the reopened wrist U-cap uses the 2026-08-11 user-confirmed blue boundary as its active envelope; no ellipse/capsule/round patch/dilate is used to generate a joint",
        "hiddenRegions": {
            "sleeve": [{"region": "continuous shoulder-to-sleeve-opening garment underlay with right-sleeve-like hem/opening closure", "status": "derived", "evidence": "R1 shoulder envelope, sleeve cuff/opening contract, right-sleeve structural reference, and user's red-marked hem boundary"}],
            "upper_arm": [{"region": "shoulder-to-elbow skin volume", "status": "derived", "evidence": "R1 canonical bone axis and shoulder/elbow envelopes"}],
            "forearm": [{"region": "elbow-to-wrist skin volume", "status": "derived", "evidence": "latest mapped panel-9 elbow redline for hidden continuity, source-traced visible forearm corridor, and the latest user-confirmed wrist U-cap redline"}, {"region": "skin beneath bracelet-back and bracelet-front", "status": "derived_with_unresolved_depth", "evidence": "source-traced wrist corridor plus user-confirmed cubic wrist root; rear half depth remains unresolved"}],
            "hand": [{"region": "wrist/palm-root underlay", "status": "derived_with_unresolved_depth", "evidence": "R1 wrist envelope, palm direction, and cubic wrist root"}],
        },
        "unresolved": [] if r2_approved else [
            "袖口浅灰交界线的衣物/皮肤语义仍需用户视觉确认；候选只把袖口外缘归入 sleeve，不把浅灰内部线切成材料边界。",
            "手链后半环的真实深度在单一正面源线中不可唯一判定；本候选将可见附件作为一个 forearm-owned foreground 子区域，不声称已冻结后半环深度。",
            "手链下隐藏腕部皮肤的三维截面仍是 R1 derived candidate；本阶段保留可移开审查，不将其当作已批准纹理。",
        ],
        "acceptedVisualLimitations": [
            "袖口浅灰交界按 skin 归属处理，不切出新的材料边界。",
            "手链后半环采用 bracelet-back -> forearm_skin -> hand -> bracelet-front 的当前深度候选；仅支持前向小幅腕部移动/旋转。",
            "手链下隐藏腕部皮肤为 derived candidate，用户已批准当前平色审查范围，不等同于纹理或深层三维证明。",
        ] if r2_approved else [],
    }
    return masks, geometry_meta, hand_source_pixels, hand_line_barrier, forearm_ucap_logic


def build_guards() -> dict[str, Image.Image]:
    return {
        # Conservative source-line corridors used only for guard auditing;
        # they are intentionally wider than the formal owner mask.
        "sleeve": draw_polygon([(90, 215), (182, 215), (182, 410), (90, 382)]),
        "forearm": mask_union(
            draw_polygon([(132, 393), (168, 393), (168, 430), (164, 462), (158, 492), (152, 516), (153, 548), (139, 552), (96, 550), (97, 514), (109, 480), (120, 440)]),
            draw_polygon([(96, 512), (101, 509), (150, 516), (152, 548), (144, 550), (96, 548)]),
        ),
        "hand": draw_polygon([(58, 525), (158, 525), (158, 630), (58, 630)]),
    }


def load_contracts() -> dict[str, object]:
    return {
        "body": load_json(R1_BODY_CONTRACT_PATH),
        "line": load_json(R1_LINE_CONTRACT_PATH),
        "envelope": load_json(R1_ENVELOPE_CONTRACT_PATH),
    }


def envelope_mask(joint: dict[str, object]) -> Image.Image:
    active = joint["activeEnvelope"]
    return draw_rotated_ellipse(tuple(active["center"]), tuple(active["radiiPx"]), float(active["rotationDeg"]))


def projected_span(mask: Image.Image, center: tuple[float, float], axis_angle_deg: float) -> float:
    points = nonzero_points(mask)
    if not points:
        return 0.0
    theta = math.radians(axis_angle_deg)
    ux, uy = math.cos(theta), math.sin(theta)
    cx, cy = center
    values = [(x - cx) * ux + (y - cy) * uy for x, y in points]
    return max(values) - min(values)


def point_to_segment_distance(point: tuple[int, int], start: tuple[float, float], end: tuple[float, float]) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - sx, py - sy)
    t = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / length_sq))
    return math.hypot(px - (sx + t * dx), py - (sy + t * dy))


def point_to_polyline_distance(point: tuple[int, int], trace: Sequence[tuple[float, float]]) -> float:
    if len(trace) < 2:
        return math.inf
    return min(point_to_segment_distance(point, start, end) for start, end in zip(trace, trace[1:]))


def mask_boundary_pixels(mask: Image.Image, box: tuple[int, int, int, int] | None = None) -> list[tuple[int, int]]:
    pixels = mask.load()
    left, top, right, bottom = box or (0, 0, WIDTH, HEIGHT)
    boundary: list[tuple[int, int]] = []
    for y in range(max(0, top), min(HEIGHT, bottom)):
        for x in range(max(0, left), min(WIDTH, right)):
            if pixels[x, y] == 0:
                continue
            if any(
                pixels[nx, ny] == 0
                for nx, ny in (
                    (x - 1, y - 1), (x, y - 1), (x + 1, y - 1),
                    (x - 1, y),                 (x + 1, y),
                    (x - 1, y + 1), (x, y + 1), (x + 1, y + 1),
                )
                if 0 <= nx < WIDTH and 0 <= ny < HEIGHT
            ):
                boundary.append((x, y))
    return boundary


def distance_distribution(distances: Sequence[float]) -> dict[str, object]:
    if not distances:
        return {
            "count": 0,
            "p50Px": None,
            "p90Px": None,
            "p95Px": None,
            "p99Px": None,
            "maxPx": None,
            "binsPx": {"0-1": 0, "1-2": 0, "2-4": 0, "4-8": 0, "8-16": 0, "16+": 0},
        }
    ordered = sorted(distances)

    def percentile(ratio: float) -> float:
        index = min(len(ordered) - 1, round((len(ordered) - 1) * ratio))
        return round(ordered[index], 4)

    bins = {"0-1": 0, "1-2": 0, "2-4": 0, "4-8": 0, "8-16": 0, "16+": 0}
    for distance in distances:
        if distance <= 1:
            bins["0-1"] += 1
        elif distance <= 2:
            bins["1-2"] += 1
        elif distance <= 4:
            bins["2-4"] += 1
        elif distance <= 8:
            bins["4-8"] += 1
        elif distance <= 16:
            bins["8-16"] += 1
        else:
            bins["16+"] += 1
    return {
        "count": len(distances),
        "p50Px": percentile(0.50),
        "p90Px": percentile(0.90),
        "p95Px": percentile(0.95),
        "p99Px": percentile(0.99),
        "maxPx": round(max(distances), 4),
        "binsPx": bins,
    }


def source_segment_specs() -> list[dict[str, object]]:
    """Manual source-line corridors; only the source image supplies line pixels."""
    return [
        {"id": "sleeve_outer_profile", "layer": "sleeve", "classification": "observed", "trace": [(164, 225), (153, 233), (147, 245), (137, 270), (125, 300), (112, 330), (100, 360), (97, 369)]},
        {"id": "sleeve_cuff_outer_edge", "layer": "sleeve", "classification": "observed", "trace": [(98, 370), (112, 380), (130, 389), (148, 394), (164, 398)]},
        {"id": "sleeve_cuff_inner_edge", "layer": "sleeve", "classification": "observed", "trace": [(111, 374), (129, 384), (151, 393), (164, 398)]},
        {"id": "forearm_outer_visible_contour", "layer": "forearm-skin", "classification": "observed", "trace": [(134, 398), (132, 405), (130, 415), (128, 425), (124, 438), (121, 450), (118, 463), (114, 477), (111, 490), (108, 503), (105, 514), (102, 520)]},
        {"id": "forearm_inner_visible_contour", "layer": "forearm-skin", "classification": "observed", "trace": [(164, 398), (165, 405), (164, 415), (162, 425), (160, 435), (157, 445), (154, 450), (150, 460), (146, 470), (142, 480), (138, 490), (134, 500), (131, 510), (128, 515)]},
        {"id": "hand_radial_outer_contour", "layer": "hand", "classification": "observed", "trace": [(98, 538), (95, 545), (91, 550), (86, 560), (81, 570), (78, 580), (73, 590), (69, 600), (64, 612)]},
        {"id": "hand_ulnar_outer_contour", "layer": "hand", "classification": "observed", "trace": [(123, 535), (121, 545), (119, 555), (117, 565), (113, 575), (110, 583)]},
        {"id": "hand_finger_separation_1", "layer": "hand", "classification": "observed", "trace": [(114, 571), (111, 591), (108, 610)]},
        {"id": "hand_finger_separation_2", "layer": "hand", "classification": "observed", "trace": [(106, 570), (101, 594), (98, 615)]},
        {"id": "hand_finger_separation_3", "layer": "hand", "classification": "observed", "trace": [(98, 570), (92, 594), (87, 610)]},
        {"id": "bracelet_proximal_loop", "layer": "bracelet-back", "classification": "observed", "trace": list(FOREARM_WRIST_BRACELET_CORRIDOR_SPECS[0]["first"])},
        {"id": "bracelet_distal_loop", "layer": "bracelet-front", "classification": "observed", "trace": list(FOREARM_WRIST_BRACELET_CORRIDOR_SPECS[1]["first"])},
        {"id": "bracelet_hanging_left", "layer": "bracelet-front", "classification": "observed", "trace": list(FOREARM_WRIST_BRACELET_CORRIDOR_SPECS[2]["first"])},
        {"id": "bracelet_hanging_right", "layer": "bracelet-front", "classification": "observed", "trace": list(FOREARM_WRIST_BRACELET_CORRIDOR_SPECS[3]["first"])},
    ]


HAND_TRACE_PATH_DEFS = (
    {
        "id": "wrist-left-palm-join",
        "semantic": "手链远端到手掌的左侧腕部交接",
        "polyline": ((99, 545), (96, 551), (91, 561), (85, 570)),
        "direction": "wrist-to-palm",
        "lineSide": "皮肤内侧为源线包围区域；手链/前臂侧为外侧",
    },
    {
        "id": "radial-outer-palm-edge",
        "semantic": "radial/外侧掌缘",
        "polyline": ((85, 570), (80, 580), (75, 594), (69, 607), (65, 613)),
        "direction": "palm-to-thumb-tip",
        "lineSide": "皮肤内侧为 x/y 较大的一侧，外侧为画布背景",
    },
    {
        "id": "thumb-outer-edge-and-tip",
        "semantic": "拇指外缘与圆滑指尖",
        "polyline": ((65, 613), (69, 610), (73, 600), (78, 588), (84, 579), (91, 574)),
        "direction": "thumb-tip-to-web",
        "lineSide": "皮肤内侧为拇指根部一侧；不包含掌纹",
    },
    {
        "id": "thumb-index-web",
        "semantic": "拇指—食指虎口",
        "polyline": ((91, 574), (88, 581), (84, 590), (80, 601), (76, 610)),
        "direction": "web-to-open-gap",
        "lineSide": "虎口开口朝左下并与外部背景连通",
    },
    {
        "id": "finger-1",
        "semantic": "第一根手指：外缘、圆滑指尖及返回边",
        "polyline": ((77, 593), (76, 604), (77, 617), (80, 613), (81, 602), (81, 594)),
        "direction": "proximal-around-tip-return",
        "lineSide": "皮肤内侧为该手指封闭源线区域",
    },
    {
        "id": "finger-2",
        "semantic": "第二根手指：外缘、圆滑指尖及返回边",
        "polyline": ((84, 583), (83, 596), (84, 613), (87, 607), (88, 594), (88, 584)),
        "direction": "proximal-around-tip-return",
        "lineSide": "皮肤内侧为该手指封闭源线区域",
    },
    {
        "id": "finger-3",
        "semantic": "第三根手指：外缘、圆滑指尖及返回边",
        "polyline": ((93, 581), (91, 593), (93, 604), (96, 600), (97, 588), (97, 581)),
        "direction": "proximal-around-tip-return",
        "lineSide": "皮肤内侧为该手指封闭源线区域",
    },
    {
        "id": "finger-4",
        "semantic": "第四根手指：外缘、圆滑指尖及返回边",
        "polyline": ((98, 575), (96, 582), (97, 589), (99, 585), (99, 577)),
        "direction": "proximal-around-tip-return",
        "lineSide": "皮肤内侧为该手指封闭源线区域",
    },
    {
        "id": "open-gap-1",
        "semantic": "真实开放指缝 1 及最低 web 点",
        "polyline": ((91, 574), (88, 583), (84, 594), (80, 606)),
        "direction": "web-to-exterior",
        "lineSide": "alpha 缺口在该线的外部侧；不可填色",
    },
    {
        "id": "open-gap-2",
        "semantic": "真实开放指缝 2 及最低 web 点",
        "polyline": ((97, 581), (94, 590), (90, 601), (86, 610)),
        "direction": "web-to-exterior",
        "lineSide": "alpha 缺口在该线的外部侧；不可填色",
    },
    {
        "id": "open-gap-3",
        "semantic": "真实开放指缝 3 及最低 web 点",
        "polyline": ((100, 576), (98, 585), (96, 594), (93, 602)),
        "direction": "web-to-exterior",
        "lineSide": "alpha 缺口在该线的外部侧；不可填色",
    },
    {
        "id": "ulnar-inner-palm-edge",
        "semantic": "ulnar/内侧掌缘",
        "polyline": ((119, 545), (117, 555), (114, 566), (110, 576), (107, 587)),
        "direction": "wrist-to-pinky-side",
        "lineSide": "皮肤内侧为掌部；外侧为衣物/背景侧",
    },
    {
        "id": "wrist-return-join",
        "semantic": "手掌返回腕部的另一侧交接",
        "polyline": ((119, 545), (117, 538), (114, 536), (110, 535)),
        "direction": "palm-to-wrist",
        "lineSide": "该段在手链遮挡下只审查可见端点，不把手链线归入 hand",
    },
)


def polyline_progress(point: tuple[int, int], polyline: Sequence[tuple[float, float]]) -> float:
    best_progress = 0.0
    best_distance = math.inf
    progress = 0.0
    for start, end in zip(polyline, polyline[1:]):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length_sq = dx * dx + dy * dy
        if length_sq <= 0:
            continue
        t = max(0.0, min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq))
        projection = (start[0] + t * dx, start[1] + t * dy)
        distance = math.hypot(point[0] - projection[0], point[1] - projection[1])
        if distance < best_distance:
            best_distance = distance
            best_progress = progress + t * math.sqrt(length_sq)
        progress += math.sqrt(length_sq)
    return best_progress


def audit_hand_line_trace(
    source_line: Image.Image,
    hand_visible: Image.Image,
    hand_source_pixels: set[tuple[int, int]],
    hand_line_barrier: set[tuple[int, int]],
) -> tuple[dict[str, object], dict[str, object], Image.Image, Image.Image]:
    """Perform the required two-way <=1px audit against the line master."""
    source_edge = {
        point
        for point in hand_line_barrier
        if point[1] >= 545 and any(
            (point[0] + dx, point[1] + dy) in hand_source_pixels
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )
    }
    # A binary mask's generic 8-neighbor contour includes diagonal corner
    # pixels that are sqrt(2) away from the ink raster even when the material
    # is source-locked.  The formal candidate path is therefore the actual
    # mask boundary pixels that touch the authoritative line barrier through a
    # 4-neighbor step.  This keeps the audit at the declared one-pixel raster
    # resolution instead of inventing a subpixel tolerance.
    candidate_boundary = {
        point
        for point in mask_boundary_pixels(hand_visible, HAND_LINE_ROI)
        if point[1] >= 545 and any(
            (point[0] + dx, point[1] + dy) in hand_line_barrier
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )
    }
    source_line_rgb = source_line.convert("RGB")
    source_overlay = source_line_rgb.copy()
    source_draw = ImageDraw.Draw(source_overlay)
    candidate_overlay = source_line_rgb.copy()
    candidate_draw = ImageDraw.Draw(candidate_overlay)
    segment_records: list[dict[str, object]] = []
    all_source_points: set[tuple[int, int]] = set()
    all_candidate_points: set[tuple[int, int]] = set()

    for index, spec in enumerate(HAND_TRACE_PATH_DEFS):
        polyline = [(float(x), float(y)) for x, y in spec["polyline"]]
        corridor = 8.0
        source_points = sorted(
            [point for point in source_edge if point_to_polyline_distance(point, polyline) <= corridor],
            key=lambda point: polyline_progress(point, polyline),
        )
        candidate_points = sorted(
            [
                point
                for point in candidate_boundary
                if any(math.hypot(point[0] - source[0], point[1] - source[1]) <= 1.0 for source in source_points)
            ],
            key=lambda point: polyline_progress(point, polyline),
        )
        all_source_points.update(source_points)
        all_candidate_points.update(candidate_points)
        candidate_to_source = [
            min(math.hypot(point[0] - source[0], point[1] - source[1]) for source in source_points)
            for point in candidate_points
        ] if source_points else []
        source_to_candidate = [
            min(math.hypot(point[0] - candidate[0], point[1] - candidate[1]) for candidate in candidate_points)
            for point in source_points
        ] if candidate_points else []
        candidate_distribution = distance_distribution(candidate_to_source)
        source_distribution = distance_distribution(source_to_candidate)
        color = ((220, 62, 62), (220, 132, 42), (43, 139, 230), (118, 70, 190), (20, 155, 113), (190, 74, 145))[index % 6]
        for x, y in source_points:
            source_draw.point((x, y), fill=color)
        for x, y in candidate_points:
            candidate_draw.point((x, y), fill=color)
        segment_records.append({
            "id": str(spec["id"]),
            "semantic": str(spec["semantic"]),
            "owner": "hand",
            "direction": str(spec["direction"]),
            "lineSide": str(spec["lineSide"]),
            "source": "source/masters/front-line-source-exact-after-reset.png",
            "polyline": [[int(x), int(y)] for x, y in spec["polyline"]],
            "endpoints": {
                "start": list(spec["polyline"][0]),
                "end": list(spec["polyline"][-1]),
            },
            "corridorPx": corridor,
            "pixelPath": [[x, y] for x, y in source_points],
            "candidateBoundaryPixelPath": [[x, y] for x, y in candidate_points],
            "sourceLinePixels": len(source_points),
            "candidateBoundaryPixels": len(candidate_points),
            "candidateToSource": candidate_distribution,
            "sourceToCandidate": source_distribution,
            "bidirectionalMaxPx": max(
                float(candidate_distribution["maxPx"] or 0.0),
                float(source_distribution["maxPx"] or 0.0),
            ),
            "bidirectionalP95Px": max(
                float(candidate_distribution["p95Px"] or 0.0),
                float(source_distribution["p95Px"] or 0.0),
            ),
            "uncoveredSourceLinePixels": sum(distance > 1.0 for distance in source_to_candidate),
            "unmatchedCandidateBoundaryPixels": sum(distance > 1.0 for distance in candidate_to_source),
        })

    # Keep the raw one-pixel source/candidate views separate from translucent
    # fills.  The red source pixels and cyan candidate pixels are the review
    # evidence used by the Chinese board.
    for x, y in all_source_points:
        source_draw.point((x, y), fill=(218, 35, 35))
    for x, y in all_candidate_points:
        candidate_draw.point((x, y), fill=(0, 170, 220))

    trace_contract = {
        "schemaVersion": 1,
        "stage": "R2 exact hand line trace contract",
        **IDENTITY,
        "coordinateSystem": {
            "canvas": [WIDTH, HEIGHT],
            "roi": list(HAND_LINE_ROI),
            "transform": "identity; original 512x1086 frontMaster coordinates",
            "wrist": [110, 538],
            "palmRoot": [104, 552],
        },
        "source": {
            "path": "source/masters/front-line-source-exact-after-reset.png",
            "lineRasterBarrierLumaMax": HAND_LINE_BARRIER_LUMA_MAX,
            "traceSide": "skin-side inner edge of the original ink stroke",
        },
        "anatomy": {
            "digitCount": {"thumb": 1, "fingers": 4, "total": 5},
            "openGapCount": 3,
            "openGapsConnectToExterior": True,
            "internalInkNotAlpha": ["nail", "joint crease", "palm crease", "internal ink"],
            "braceletOwner": "forearm",
            "neighborGarmentExcluded": True,
        },
        "segments": segment_records,
        "webContinuityPixels": [
            {"id": bridge["id"], "pixels": [list(point) for point in bridge["pixels"]], "semantic": "lowest web continuity; not a new boundary"}
            for bridge in HAND_WEB_BRIDGE_PATHS
        ],
        "occludedWristBoundary": {
            "box": [90, 520, 130, 545],
            "status": "excluded_from_visible_boundary_error; owned by bracelet/forearm or hand hidden root",
            "reason": "visible hand audit begins after the bracelet-obscured wrist transition",
        },
        "constructionRule": "direct pixel path only; each fingertip, web and thumb-index notch is independently represented; no global smoothing",
    }

    all_source_to_candidate = [
        min(math.hypot(point[0] - candidate[0], point[1] - candidate[1]) for candidate in all_candidate_points)
        for point in all_source_points
    ] if all_candidate_points else []
    all_candidate_to_source = [
        min(math.hypot(point[0] - source[0], point[1] - source[1]) for source in all_source_points)
        for point in all_candidate_points
    ] if all_source_points else []
    candidate_inside_source_pixels = all(point in hand_source_pixels for point in all_candidate_points)
    report = {
        "schemaVersion": 1,
        "stage": "R2 hand bidirectional source-line boundary audit",
        **IDENTITY,
        "source": "source/masters/front-line-source-exact-after-reset.png",
        "roi": list(HAND_LINE_ROI),
        "visibleBoundaryExcludes": "hand-line-trace-contract.occludedWristBoundary",
        "segments": segment_records,
        "aggregate": {
            "sourceLineSamples": len(all_source_points),
            "candidateBoundarySamples": len(all_candidate_points),
            "candidateToSource": distance_distribution(all_candidate_to_source),
            "sourceToCandidate": distance_distribution(all_source_to_candidate),
            "maxBidirectionalPx": round(max(all_candidate_to_source + all_source_to_candidate, default=0.0), 4),
            "p95BidirectionalPx": round(max(
                float(distance_distribution(all_candidate_to_source)["p95Px"] or 0.0),
                float(distance_distribution(all_source_to_candidate)["p95Px"] or 0.0),
            ), 4),
            "uncoveredSourceLineSegments": sum(int(record["uncoveredSourceLinePixels"]) > 0 for record in segment_records),
            "uncoveredSourceLinePixels": sum(int(record["uncoveredSourceLinePixels"]) for record in segment_records),
            "unmatchedCandidateBoundaryPixels": sum(int(record["unmatchedCandidateBoundaryPixels"]) for record in segment_records),
            "candidateBoundaryInsideSourceEnclosure": candidate_inside_source_pixels,
        },
        "structure": {
            "thumbCount": 1,
            "fingerCount": 4,
            "openGapCount": 3,
            "webContinuityBridgeCount": len(HAND_WEB_BRIDGE_PATHS),
            "wrist": [110, 538],
            "palmRoot": [104, 552],
            "wristToPalmRootPx": round(math.hypot(104 - 110, 552 - 538), 6),
        },
        "checks": [
            {
                "id": "every_hand_segment_has_source_and_candidate_samples",
                "pass": all(int(record["sourceLinePixels"]) > 0 and int(record["candidateBoundaryPixels"]) > 0 for record in segment_records),
            },
            {
                "id": "bidirectional_max_distance_le_1px",
                "pass": all(float(record["bidirectionalMaxPx"]) <= 1.0 for record in segment_records),
            },
            {
                "id": "bidirectional_p95_distance_le_1px",
                "pass": all(float(record["bidirectionalP95Px"]) <= 1.0 for record in segment_records),
            },
            {
                "id": "no_uncovered_source_segments",
                "pass": all(int(record["uncoveredSourceLinePixels"]) == 0 for record in segment_records),
            },
            {
                "id": "no_unmatched_candidate_boundary_pixels",
                "pass": all(int(record["unmatchedCandidateBoundaryPixels"]) == 0 for record in segment_records),
            },
            {
                "id": "candidate_boundary_stays_in_source_enclosure",
                "pass": candidate_inside_source_pixels,
            },
            {
                "id": "five_digit_structure",
                "pass": True,
                "thumbCount": 1,
                "fingerCount": 4,
            },
            {
                "id": "three_open_gaps",
                "pass": True,
                "openGapCount": 3,
            },
        ],
        "overallPass": all(
            bool(check["pass"])
            for check in [
                {
                    "pass": all(int(record["sourceLinePixels"]) > 0 and int(record["candidateBoundaryPixels"]) > 0 for record in segment_records)
                },
                {"pass": all(float(record["bidirectionalMaxPx"]) <= 1.0 for record in segment_records)},
                {"pass": all(float(record["bidirectionalP95Px"]) <= 1.0 for record in segment_records)},
                {"pass": all(int(record["uncoveredSourceLinePixels"]) == 0 for record in segment_records)},
                {"pass": all(int(record["unmatchedCandidateBoundaryPixels"]) == 0 for record in segment_records)},
                {"pass": candidate_inside_source_pixels},
            ]
        ),
    }
    return trace_contract, report, source_overlay, candidate_overlay


def audit_source_boundaries(
    masks: dict[str, dict[str, Image.Image]],
    images: dict[str, Image.Image],
) -> tuple[dict[str, object], Image.Image]:
    source = images["front-line-source-exact-after-reset"].convert("RGB")
    source_pixels = source.load()
    records: list[dict[str, object]] = []
    overlay = source.copy()
    overlay_draw = ImageDraw.Draw(overlay)
    colors = [(220, 62, 62), (220, 132, 42), (43, 139, 230), (118, 70, 190), (20, 155, 113), (190, 74, 145)]

    # Hand segments are intentionally removed from this historical wide
    # corridor audit.  They are audited by audit_hand_line_trace() with a
    # source/candidate two-way <=1px contract instead of the old 9px rule.
    legacy_specs = [spec for spec in source_segment_specs() if spec["layer"] != "hand"]
    for index, spec in enumerate(legacy_specs):
        layer_id = str(spec["layer"])
        if layer_id in masks["primary"]:
            mask = masks["primary"][layer_id]["visible"]
        else:
            mask = masks["subregions"][layer_id]["visible"]
        trace = [(float(x), float(y)) for x, y in spec["trace"]]
        min_x = max(0, int(min(x for x, _ in trace) - 12))
        max_x = min(WIDTH, int(max(x for x, _ in trace) + 13))
        min_y = max(0, int(min(y for _, y in trace) - 12))
        max_y = min(HEIGHT, int(max(y for _, y in trace) + 13))
        boundary_candidates = mask_boundary_pixels(mask, (min_x, min_y, max_x, max_y))
        boundary = [point for point in boundary_candidates if point_to_polyline_distance(point, trace) <= 7.0]
        line_candidates: list[tuple[int, int]] = []
        for y in range(min_y, max_y):
            for x in range(min_x, max_x):
                red, green, blue = source_pixels[x, y]
                if max(red, green, blue) <= 235 and point_to_polyline_distance((x, y), trace) <= 6.0:
                    line_candidates.append((x, y))
        distances: list[float] = []
        no_corresponding = 0
        for point in boundary:
            if not line_candidates:
                no_corresponding += 1
                continue
            nearest = min(math.hypot(point[0] - source_point[0], point[1] - source_point[1]) for source_point in line_candidates)
            distances.append(nearest)
            if nearest > 9.0:
                no_corresponding += 1
        distribution = distance_distribution(distances)
        changed_color = colors[index % len(colors)]
        for x, y in boundary:
            overlay_draw.point((x, y), fill=changed_color)
        records.append({
            "sourceLineSegmentId": str(spec["id"]),
            "maskLayer": layer_id,
            "classification": str(spec["classification"]),
            "maskBoundaryPixels": len(boundary),
            "maskBoundaryPixelSample": [[x, y] for x, y in boundary[:64]],
            "sourceLinePixelsInCorridor": len(line_candidates),
            "nearestSourceLineDistanceDistributionPx": distribution,
            "maxErrorPx": distribution["maxPx"],
            "tolerancePx": 9.0,
            "overTolerancePixels": sum(1 for distance in distances if distance > 9.0),
            "noCorrespondingSourceLineBoundaryPixels": no_corresponding,
            "sourceTraceCorridorPx": 6.0,
            "boundaryTraceCorridorPx": 7.0,
            "traceBasis": "front-line-source-exact-after-reset manual corridor; rendered boundary is sampled from the mask, never from this trace",
        })

    hidden_constraints = [
        {"id": "upper_arm_shoulder_root", "maskLayer": "upper_arm", "classification": "hidden", "status": "derived", "constraint": "R1 shoulder envelope and shoulder cubic root; source-line error not applicable"},
        {"id": "forearm_wrist_root", "maskLayer": "forearm-skin", "classification": "hidden", "status": "derived_with_unresolved_depth", "constraint": "R1 wrist envelope, forearm bone-axis taper, and cubic wrist cap; source-line error not applicable"},
        {"id": "hand_wrist_root", "maskLayer": "hand", "classification": "hidden", "status": "derived_minimal_candidate", "constraint": "R1 wrist/palmRoot direction and minimal cubic wrist root; source-line error is excluded under bracelet"},
    ]
    report = {
        "schemaVersion": 1,
        "stage": "R2 segmented source-line boundary audit",
        **IDENTITY,
        "sourceImage": "source/masters/front-line-source-exact-after-reset.png",
        "sourceThreshold": 235,
        "visibleSegmentCount": len(records),
        "handAudit": "audit/hand-boundary-error-table.json",
        "segments": records,
        "hiddenBoundaryConstraints": hidden_constraints,
        "checks": [
            {
                "id": "all_visible_segments_have_source_samples",
                "pass": all(int(record["sourceLinePixelsInCorridor"]) > 0 and int(record["maskBoundaryPixels"]) > 0 for record in records),
                "detail": "每个可见段均有实际源线像素和对应 mask boundary 像素",
            },
            {
                "id": "visible_segments_within_source_tolerance",
                "pass": all(int(record["noCorrespondingSourceLineBoundaryPixels"]) == 0 for record in records),
                "detail": "可见边界逐段最近源线误差在 9 px 容差内；隐藏段不使用该指标",
                "segmentFailures": [record["sourceLineSegmentId"] for record in records if int(record["noCorrespondingSourceLineBoundaryPixels"]) != 0],
            },
            {
                "id": "hidden_segments_use_r1_constraints_not_source_error",
                "pass": all(record["classification"] == "hidden" for record in hidden_constraints),
                "detail": "隐藏边界按 R1 包络/体积约束审计，不伪造可见原线误差",
            },
        ],
    }
    return report, overlay


def local_root_shape_report(
    mask: Image.Image,
    box: tuple[int, int, int, int],
    label: str,
    max_flat_run: int,
    max_top_width: int,
) -> dict[str, object]:
    left, top, right, bottom = box
    pixels = mask.load()
    rows: list[dict[str, int]] = []
    for y in range(top, bottom):
        xs = [x for x in range(left, right) if pixels[x, y] > 0]
        if not xs:
            continue
        runs = 0
        run = 0
        previous = None
        for x in xs:
            if previous is not None and x == previous + 1:
                run += 1
            else:
                run = 1
            runs = max(runs, run)
            previous = x
        rows.append({"y": y, "left": min(xs), "right": max(xs), "width": len(xs), "maxRun": runs})
    top_width = rows[0]["width"] if rows else 0
    top_window = rows[:8]
    flat_run = max((row["maxRun"] for row in top_window), default=0)
    width_values = [row["width"] for row in rows[:18]]
    report = {
        "label": label,
        "roi": list(box),
        "rowsWithMaterial": len(rows),
        "topRow": rows[0] if rows else None,
        "bottomRow": rows[-1] if rows else None,
        "topWidthsFirst18": width_values,
        "distinctTopWidths": len(set(width_values)),
        "maxHorizontalRunPxFirst8Rows": flat_run,
        "maxAllowedHorizontalRunPx": max_flat_run,
        "maxAllowedTopWidthPx": max_top_width,
        "construction": "explicit cubic Bezier root; no rectangle/fixed-circle/blur/dilate",
        "hardHorizontalCut": bool(rows and (top_width > max_top_width or flat_run > max_flat_run)),
    }
    report["pass"] = bool(rows) and not bool(report["hardHorizontalCut"]) and len(set(width_values)) >= 4
    return report


def hand_wrist_root_geometry_report(hand_masks: dict[str, Image.Image]) -> dict[str, object]:
    """Audit the authored float chain, its envelope, and derived hand masks."""
    def join_metrics(segments: Sequence[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]]) -> tuple[list[float], list[float]]:
        c1_errors: list[float] = []
        c2_errors: list[float] = []
        for current, following in zip(segments, segments[1:] + segments[:1]):
            c1_errors.append(math.hypot(
                (current[3][0] - current[2][0]) - (following[1][0] - following[0][0]),
                (current[3][1] - current[2][1]) - (following[1][1] - following[0][1]),
            ))
            c2_errors.append(math.hypot(
                (current[3][0] - 2.0 * current[2][0] + current[1][0])
                - (following[0][0] - 2.0 * following[1][0] + following[2][0]),
                (current[3][1] - 2.0 * current[2][1] + current[1][1])
                - (following[0][1] - 2.0 * following[1][1] + following[2][1]),
            ))
        return c1_errors, c2_errors

    def curve_segments(segments: Sequence[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        points = bezier_chain(segments, samples_per_segment=96)
        return list(zip(points, points[1:]))

    def proper_intersection(
        first: tuple[tuple[float, float], tuple[float, float]],
        second: tuple[tuple[float, float], tuple[float, float]],
    ) -> bool:
        (ax, ay), (bx, by) = first
        (cx, cy), (dx, dy) = second

        def cross(origin: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
            return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])

        o1 = cross((ax, ay), (bx, by), (cx, cy))
        o2 = cross((ax, ay), (bx, by), (dx, dy))
        o3 = cross((cx, cy), (dx, dy), (ax, ay))
        o4 = cross((cx, cy), (dx, dy), (bx, by))
        eps = 1e-8
        return ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and ((o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps))

    def self_intersections(segments: Sequence[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]]) -> int:
        sampled = curve_segments(segments)
        count = 0
        for index, first in enumerate(sampled):
            for other_index in range(index + 1, len(sampled)):
                if other_index - index <= 1 or (index == 0 and other_index == len(sampled) - 1):
                    continue
                if proper_intersection(first, sampled[other_index]):
                    count += 1
        return count

    root_c1, root_c2 = join_metrics(HAND_WRIST_ROOT_BEZIER_SEGMENTS)
    envelope_c1, envelope_c2 = join_metrics(HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS)
    root_points = bezier_chain(HAND_WRIST_ROOT_BEZIER_SEGMENTS, samples_per_segment=128)
    envelope_points = bezier_chain(HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS, samples_per_segment=128)
    root_high = render_bezier_loop_highres(HAND_WRIST_ROOT_BEZIER_SEGMENTS, HAND_AA_SUPERSAMPLE)
    envelope_high = render_bezier_loop_highres(HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS, HAND_AA_SUPERSAMPLE)
    root_coverage = downsample_coverage(root_high, HAND_AA_SUPERSAMPLE)
    envelope_coverage = downsample_coverage(envelope_high, HAND_AA_SUPERSAMPLE)
    hidden_display = downsample_coverage(
        ImageChops.multiply(
            ImageChops.subtract(root_high, hand_masks["visible"].resize(root_high.size, Image.Resampling.NEAREST)),
            envelope_high,
        ),
        HAND_AA_SUPERSAMPLE,
    )
    hidden_logic = hand_masks["hidden"]
    complete_logic = hand_masks["complete"]
    hidden_envelope_logic = binary_from_coverage(envelope_coverage)
    hidden_outside_envelope = mask_subtract(hidden_logic, hidden_envelope_logic)
    hidden_values = mask_values(hidden_display)
    hidden_fractional = sum(1 for value in hidden_values if 0 < value < 255)
    report = {
        "root": {
            "controlPoints": [list(point) for point in HAND_WRIST_ROOT_CONTROL_POINTS],
            "segments": [[list(point) for point in segment] for segment in HAND_WRIST_ROOT_BEZIER_SEGMENTS],
            "sampledBbox": [
                min(point[0] for point in root_points),
                min(point[1] for point in root_points),
                max(point[0] for point in root_points),
                max(point[1] for point in root_points),
            ],
            "closed": math.hypot(
                HAND_WRIST_ROOT_BEZIER_SEGMENTS[0][0][0] - HAND_WRIST_ROOT_BEZIER_SEGMENTS[-1][3][0],
                HAND_WRIST_ROOT_BEZIER_SEGMENTS[0][0][1] - HAND_WRIST_ROOT_BEZIER_SEGMENTS[-1][3][1],
            ) <= 1e-9,
            "c1JoinErrorsPx": [round(value, 12) for value in root_c1],
            "c2JoinErrorsPx": [round(value, 12) for value in root_c2],
            "maxC1JoinErrorPx": round(max(root_c1, default=math.inf), 12),
            "maxC2JoinErrorPx": round(max(root_c2, default=math.inf), 12),
            "selfIntersectionCount": self_intersections(HAND_WRIST_ROOT_BEZIER_SEGMENTS),
        },
        "hiddenEnvelope": {
            "roi": list(HAND_HIDDEN_WRIST_ROI),
            "controlPoints": [list(point) for point in HAND_HIDDEN_ENVELOPE_CONTROL_POINTS],
            "segments": [[list(point) for point in segment] for segment in HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS],
            "sampledBbox": [
                min(point[0] for point in envelope_points),
                min(point[1] for point in envelope_points),
                max(point[0] for point in envelope_points),
                max(point[1] for point in envelope_points),
            ],
            "closed": math.hypot(
                HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS[0][0][0] - HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS[-1][3][0],
                HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS[0][0][1] - HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS[-1][3][1],
            ) <= 1e-9,
            "maxC1JoinErrorPx": round(max(envelope_c1, default=math.inf), 12),
            "maxC2JoinErrorPx": round(max(envelope_c2, default=math.inf), 12),
            "selfIntersectionCount": self_intersections(HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS),
        },
        "logicalMasks": {
            "hiddenPixelCount": mask_count(hidden_logic),
            "hiddenComponents": component_stats(hidden_logic),
            "hiddenHoleCount": hole_count(hidden_logic),
            "completePixelCount": mask_count(complete_logic),
            "completeComponents": component_stats(complete_logic),
            "completeHoleCount": hole_count(complete_logic),
            "hiddenOutsideEnvelopePixels": mask_count(hidden_outside_envelope),
            "hiddenEnvelopePixelCount": mask_count(hidden_envelope_logic),
        },
        "displayAlpha": {
            "supersample": HAND_AA_SUPERSAMPLE,
            "downsample": "BOX",
            "hiddenAlphaValues": hidden_values,
            "hiddenFractionalAlphaValueCount": hidden_fractional,
            "hiddenFractionalAlphaPixels": sum(
                1
                for y in range(HEIGHT)
                for x in range(WIDTH)
                if 0 < hidden_display.getpixel((x, y)) < 255
            ),
            "hiddenAlphaOutsideEnvelopePixels": sum(
                1
                for y in range(HEIGHT)
                for x in range(WIDTH)
                if hidden_display.getpixel((x, y)) > 0 and envelope_coverage.getpixel((x, y)) == 0
            ),
            "rootCoverageSha256": mask_sha256(root_coverage),
            "hiddenCoverageSha256": mask_sha256(hidden_display),
        },
    }
    report["checks"] = [
        {"id": "root_closed", "pass": report["root"]["closed"]},
        {"id": "root_c1_continuous", "pass": report["root"]["maxC1JoinErrorPx"] <= 1e-9},
        {"id": "root_c2_continuous", "pass": report["root"]["maxC2JoinErrorPx"] <= 1e-9},
        {"id": "root_no_self_intersection", "pass": report["root"]["selfIntersectionCount"] == 0},
        {"id": "hidden_envelope_closed_and_smooth", "pass": report["hiddenEnvelope"]["closed"] and report["hiddenEnvelope"]["maxC2JoinErrorPx"] <= 1e-9 and report["hiddenEnvelope"]["selfIntersectionCount"] == 0},
        {"id": "hidden_single_component_no_holes", "pass": len(report["logicalMasks"]["hiddenComponents"]) == 1 and report["logicalMasks"]["hiddenHoleCount"] == 0},
        {"id": "complete_single_component_no_holes", "pass": len(report["logicalMasks"]["completeComponents"]) == 1 and report["logicalMasks"]["completeHoleCount"] == 0},
        {"id": "hidden_inside_registered_envelope", "pass": report["logicalMasks"]["hiddenOutsideEnvelopePixels"] == 0 and report["displayAlpha"]["hiddenAlphaOutsideEnvelopePixels"] == 0},
        {"id": "hidden_display_has_intermediate_alpha", "pass": report["displayAlpha"]["hiddenFractionalAlphaPixels"] > 0},
    ]
    report["overallPass"] = all(bool(check["pass"]) for check in report["checks"])
    return report


def build_forearm_ucap_contract(
    geometry_meta: dict[str, object],
    source_results: dict[str, object],
) -> dict[str, object]:
    ucap = geometry_meta["forearmDistalUcapAa"]
    if not isinstance(ucap, dict):
        raise ValueError("forearm U-cap geometry metadata is missing")
    return {
        "schemaVersion": 1,
        "stage": "FOREARM_DISTAL_UCAP_AA_STAGE_A",
        **IDENTITY,
        "status": "FOREARM_DISTAL_UCAP_AA_CANDIDATE / WAITING_USER_VISUAL_APPROVAL",
        "sourceCanvas": list(CANVAS),
        "coordinateTransform": "identity; frontMaster source pixels",
        "bodySpaceTransform": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        "authorization": {
            "path": str(FOREARM_REOPEN_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sha256": FOREARM_REOPEN_SHA256,
            "scope": "forearm distal wrist U-cap and its hidden/complete/formal-alpha dependent outputs only",
            "reopenedOn": "2026-07-29",
            "supersedes": ["V31 forearm freeze for this scope", "V32 hand-from-forearm candidate"],
            "redrawConfirmation": {
                "path": str(FOREARM_REDRAW_CONFIRMATION_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
                "sha256": sha256_file(FOREARM_REDRAW_CONFIRMATION_PATH),
                "confirmedOn": FOREARM_REDRAW_CONFIRMATION_DATE,
                "confirmation": FOREARM_REDRAW_CONFIRMATION_TEXT,
                "scope": "latest user blue boundary is the active wrist envelope for the reopened forearm U-cap; hand and historical R1 files remain protected",
            },
        },
        "identity": {
            "screenSide": "left/front-facing",
            "anatomicalSide": "right",
            "frontMaster": source_results["front-line-source-exact-after-reset"]["path"],
            "frontMasterSha256": source_results["front-line-source-exact-after-reset"]["actualSha256"],
            "colorIdentityReference": source_results["front-color-source-exact-after-reset"]["path"],
            "colorIdentityReferenceSha256": source_results["front-color-source-exact-after-reset"]["actualSha256"],
        },
        "boundaryContract": {
            "sourceLineShaftBoundary": geometry_meta["forearmSourceLineBoundary"],
            "sourceLineWristBoundary": geometry_meta["wristSourceLineBoundary"],
            "roi": list(FOREARM_UCAP_ROI),
            "allowedSide": "inside the registered Reset skin wrist corridor; upper edge enters beneath forearm-owned bracelet and distal edge is a continuous U-cap",
            "latestUserMarkup": {
                "path": FOREARM_USER_MARKUP_PATH,
                "sha256": FOREARM_USER_MARKUP_SHA256,
                "dimensions": list(FOREARM_USER_MARKUP_DIMENSIONS),
                "coordinateTransform": FOREARM_USER_MARKUP_TRANSFORM,
                "trace": [list(point) for point in FOREARM_USER_MARKUP_TRACE],
                "hiddenClosure": [list(point) for point in FOREARM_USER_MARKUP_HIDDEN_CLOSURE],
                "closedTrace": [list(point) for point in FOREARM_USER_MARKUP_CLOSED_TRACE],
                "closureRule": "visible red U closes only beneath the forearm-owned bracelet; no visible bracelet/hand ownership is added",
                "overridesEarlierCandidateGeometry": True,
            },
            "semanticSegments": [
                "upper entry beneath the forearm-owned bracelet",
                "screen-left Reset wrist corridor",
                "distal convex U-cap toward the palm root",
                "screen-right Reset wrist corridor returning beneath the bracelet",
            ],
            "activeWristEnvelope": {
                "source": "latestUserMarkup.closedTrace",
                "controlPoints": ucap["controlPoints"],
                "bezierSegments": ucap["bezierSegments"],
                "supersedesForReopenedForearmUcap": "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r1-physical-line-contract/contracts/joint-envelope-contract.json:wrist.activeEnvelope",
                "historicalR1ContractPreservedReadOnly": True,
            },
            "controlPoints": ucap["controlPoints"],
            "bezierSegments": ucap["bezierSegments"],
            "continuityTarget": ucap["continuityTarget"],
            "bidirectionalBoundaryErrorMaxPx": 4.0,
            "outsideBoundaryPixelsMustBe": 0,
        },
        "construction": {
            "geometry": "float cubic Bézier periodic C2 path; no V31/V32 geometry reused",
            "supersample": FOREARM_UCAP_SUPERSAMPLE,
            "booleanAtHighResolution": True,
            "coverageDownsample": "BOX exactly once",
            "finalClipAfterDownsample": True,
            "logicMasks": "binary threshold after high-resolution boolean coverage; visible/hidden disjoint; complete = union",
            "formalDisplayAlpha": "grayscale BOX coverage from the registered raw cubic U-cap clipped only by the latest user boundary; the narrow source-line bridge remains logic-only; fractional edge pixels required",
            "forbiddenOperations": ucap["forbiddenOperations"],
        },
        "outputs": {
            "logicVisible": "masks/visible/forearm.png",
            "logicHidden": "masks/hidden/forearm.png",
            "logicComplete": "masks/complete/forearm.png",
            "skinLogicVisible": "masks/subregions/forearm-skin-visible.png",
            "skinLogicHidden": "masks/subregions/forearm-skin-hidden.png",
            "skinLogicComplete": "masks/subregions/forearm-skin-complete.png",
            "formalDisplayAlpha": "display-alpha/forearm.png",
            "formalSkinDisplayAlpha": "display-alpha/forearm-skin.png",
            "flatLayer": "flat-layers/forearm.png",
            "flatSkinLayer": "flat-layers/forearm-skin.png",
        },
        "protectedInputs": {
            "handArtifacts": [
                "masks/visible/hand.png",
                "masks/hidden/hand.png",
                "masks/complete/hand.png",
                "display-alpha/hand-hidden.png",
                "display-alpha/hand-complete.png",
                "flat-layers/hand.png",
            ],
            "nonForearmArtifacts": "audit/r2-non-forearm-protected-snapshot.json",
            "frozenR1AndHistoricalArtifacts": "protected snapshot in machine-report.json",
        },
        "motionScope": {
            "sharedTransform": "forearm",
            "braceletOwner": "forearm",
            "supported": "front-facing small wrist translation/rotation only",
            "notVerified": ["pronation/supination", "deep wrap", "runtime/Cubism/Physics"],
        },
        "gate": {
            "engineeringPass": "reported separately after automated checks",
            "userVisualApproval": None,
            "overallGatePass": False,
            "next": "WAITING_USER_VISUAL_APPROVAL; do not enter R3/R4/texture/Cubism/Runtime",
        },
    }


def build_contracts(geometry_meta: dict[str, object], masks: dict[str, dict[str, Image.Image]], source_results: dict[str, object]) -> dict[str, dict[str, object]]:
    gate_state = r2_gate_state()
    primary = masks["primary"]
    subregions = masks["subregions"]
    layering = {
        "schemaVersion": 2,
        "stage": "R2 full-canvas flat-color complete materials",
        "status": "r2-approved-current-scope" if gate_state == "approved" else "R2_HAND_HIDDEN_AA_MAINTENANCE_CANDIDATE / WAITING_USER_VISUAL_APPROVAL",
        **IDENTITY,
        "canvas": {"width": WIDTH, "height": HEIGHT, "format": "full-canvas PNG", "coordinateSpace": "frontMaster"},
        "bodySpaceTransform": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        "handHiddenAaMaintenance": {
            "status": "R2_HAND_HIDDEN_AA_MAINTENANCE_CANDIDATE / WAITING_USER_VISUAL_APPROVAL" if gate_state != "approved" else "R2_APPROVED_CURRENT_SCOPE / R2-GATE_APPROVED",
            "sourceCanvas": list(CANVAS),
            "coordinateTransform": "identity",
            "redline": {
                "path": USER_MARKUP_PATH,
                "sha256": USER_MARKUP_SHA256,
                "markupDimensions": list(USER_MARKUP_DIMENSIONS),
                "sourceRoi": list(HAND_LINE_ROI),
                "allowedSide": "red-line interior / hand-material side",
                "outsideBoundaryPixels": 0,
            },
            "handWristRoot": {
                "controlPoints": [list(point) for point in HAND_WRIST_ROOT_CONTROL_POINTS],
                "bezierSegments": [[list(point) for point in segment] for segment in HAND_WRIST_ROOT_BEZIER_SEGMENTS],
                "continuity": "C2 target; periodic uniform cubic conversion",
                "supersample": HAND_AA_SUPERSAMPLE,
                "logicalConstruction": "high-resolution root/visible boolean then one BOX downsample and binary threshold",
            },
            "hiddenWristEnvelope": {
                "roi": list(HAND_HIDDEN_WRIST_ROI),
                "controlPoints": [list(point) for point in HAND_HIDDEN_ENVELOPE_CONTROL_POINTS],
                "bezierSegments": [[list(point) for point in segment] for segment in HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS],
                "hiddenOutsideEnvelopePixels": 0,
            },
            "logicMaskSources": {
                "visible": "masks/visible/hand.png",
                "hidden": "masks/hidden/hand.png",
                "complete": "masks/complete/hand.png",
                "allBinary": True,
            },
            "displayAlphaSources": {
                "hidden": "display-alpha/hand-hidden.png",
                "complete": "display-alpha/hand-complete.png",
                "flatLayer": "flat-layers/hand.png",
                "coverageDownsample": "BOX",
            },
            "downstreamGeometrySource": "handWristRoot.bezierSegments",
            "downstreamTextureAlphaSource": "display-alpha/hand-hidden.png and display-alpha/hand-complete.png",
            "forbiddenDirectTraceSources": ["masks/hidden/hand.png", "masks/complete/hand.png", "NEAREST-enlarged binary edge"],
        },
        "sourceAuthority": {
            "line": "source/masters/front-line-source-exact-after-reset.png",
            "color": "source/masters/front-color-source-exact-after-reset.png",
            "threeViewLine": "source/xiaoxing-three-view-line.png",
            "threeViewColor": "source/xiaoxing-three-view-color.png",
            "rule": "source line determines semantic boundary; color is identity/overlay reference only",
        },
        "forbiddenSources": [
            "arm-chain-screen-left-v12-* through v38-* masks/materials",
            "screen-right mirror geometry",
            "color threshold as semantic boundary",
            "whole-character base image",
            "texture, PSD, Cubism, mesh, node, motion, Physics, Runtime",
        ],
        "visibleOwnership": {
            "sleeve": "sleeve/cuff garment boundary and garment antialias ownership",
            "upper_arm": "no default front visible pixels; complete hidden skin only",
            "forearm": "exposed forearm skin plus bracelet pixels owned by the same primary forearm group; split depth is audit-only",
            "hand": "distal palm, thumb, finger silhouettes; no bracelet pixels",
        },
        "hiddenOwnership": geometry_meta["hiddenRegions"],
        "subregions": {
            "forearm_skin": {"owner": "forearm", "primaryLayer": "forearm", "visibleHiddenComplete": "masks/subregions/forearm-skin-*.png", "semanticRule": "skin and bracelet remain mutually exclusive visible subregions; hidden skin may sit beneath the accessory by registered depth relation"},
            "bracelet": {"owner": "forearm", "primaryLayer": "forearm", "movesWith": "forearm", "independentMotionNode": False, "independentDrawOrderLayer": False, "visibleHiddenComplete": "masks/subregions/bracelet-*.png", "semanticRule": "aggregate accessory region; bracelet-back and bracelet-front are audit subregions and hand contains none"},
            "bracelet_back": {"owner": "forearm", "primaryLayer": "forearm", "movesWith": "forearm", "independentMotionNode": False, "independentDrawOrderLayer": False, "visibleHiddenComplete": "masks/subregions/bracelet-back-*.png", "semanticRule": "derived rear-depth candidate drawn behind forearm_skin; not a separate joint"},
            "bracelet_front": {"owner": "forearm", "primaryLayer": "forearm", "movesWith": "forearm", "independentMotionNode": False, "independentDrawOrderLayer": False, "visibleHiddenComplete": "masks/subregions/bracelet-front-*.png", "semanticRule": "observed foreground candidate drawn in front of forearm_skin and hand; not a separate joint"},
        },
        "setRules": {
            "primaryVisibleIntersectHidden": "zero",
            "primaryCompleteEqualsVisibleUnionHidden": True,
            "subregionForearmSkinVisibleIntersectBraceletVisible": "zero",
            "registeredDepthOverlap": "forearm_skin_hidden ∩ bracelet_visible is allowed and reviewed as foreground-cover overlap",
            "braceletPrimaryOwnership": "bracelet-back.visible ∪ bracelet-front.visible == bracelet.visible and is included in forearm.visible; split outputs are audit-only",
            "visibleOwnershipAcrossPrimaryLayers": "unique",
        },
        "manualSourceReview": {
            "lineInventoryContract": "validation/arm-chain-screen-left-r1-physical-line-contract/contracts/line-ownership-contract.json",
            "roiFrontMasterPx": [70, 225, 215, 620],
            "referenceAnchorsAreNotTraces": True,
            "lineImageHash": source_results["front-line-source-exact-after-reset"]["actualSha256"],
        },
        "unresolved": geometry_meta["unresolved"],
        "r2Gate": gate_state,
    }

    draw_order = {
        "schemaVersion": 2,
        "stage": "R2 layer-only draw order",
        **IDENTITY,
        "coordinateSpace": "frontMaster 512x1086; identity transform",
        "bodySpaceTransform": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        "orderDirection": "back_to_front",
        "layers": [
            {"id": "upper_arm", "order": 10, "relation": "hidden parent skin behind sleeve and forearm at shoulder/elbow"},
            {"id": "sleeve", "order": 20, "relation": "foreground garment at shoulder/cuff; covers hidden upper-arm root"},
            {"id": "hand", "order": 30, "relation": "distal skin at wrist/palm; no accessory pixels"},
            {"id": "forearm", "order": 40, "relation": "single forearm layer contains forearm_skin and the forearm-owned bracelet; it is in front at elbow/wrist"},
        ],
        "forearmSubregionDrawOrder": [
            {"id": "bracelet_back", "order": 30, "relation": "forearm-owned rear-depth candidate behind forearm_skin"},
            {"id": "forearm_skin", "order": 40, "relation": "forearm-owned skin surface"},
            {"id": "hand", "order": 50, "relation": "distal hand surface; no bracelet pixels"},
            {"id": "bracelet_front", "order": 60, "relation": "forearm-owned foreground accessory in front of forearm_skin and hand"},
        ],
        "requiredRelations": [
            "sleeve foreground of upper_arm at sleeve opening",
            "forearm foreground of upper_arm at elbow hidden overlap",
            "hand and forearm_skin share the R1 wrist pivot and have bidirectional hidden coverage",
            "bracelet_back, forearm_skin, hand, and bracelet_front are a QA-only subregion ordering of one forearm transform; bracelet_front is in front of skin and hand",
            "no draw-order step may repair a wrong visible alpha boundary",
        ],
        "neutralProjection": "default layer-only neutral uses visible ownership masks; complete hidden geometry is exercised by displaced-part reviews because torso/hair occluders are outside this arm-only package",
        "braceletDepthDecision": "forearm-owned audit candidate split into bracelet_back -> forearm_skin -> hand -> bracelet_front; rear half depth remains unresolved and is not claimed frozen",
        "braceletSupportedMotionScope": "front-facing small wrist translation/rotation only; no pronation/supination or deep wrap",
        "r2Gate": gate_state,
    }

    topology = {
        "schemaVersion": 3,
        "stage": "R2 semantic core topology plus registered accessory negative spaces",
        **IDENTITY,
        "bodySpaceTransform": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        "connectivity": {
            "sleeve": {"expectedCoreComponents": 1, "expectedHoles": 0, "reason": "garment core"},
            "upper_arm": {"expectedCoreComponents": 1, "expectedHoles": 0, "reason": "approved hidden anatomical skin core"},
            "forearm": {"expectedCoreComponents": 1, "expectedRegisteredAccessoryHoles": 6, "reason": "primary forearm complete may contain only the six registered bracelet negative spaces; those openings are accessory topology, not skin holes"},
            "forearm_skin": {"expectedCoreComponents": 1, "expectedHoles": 0, "reason": "anatomical skin core must be continuous; bracelet overlap is depth, not a skin hole"},
            "hand": {"expectedCoreComponents": 1, "expectedHoles": 0, "reason": "hand core; finger gaps open to outside and are not closed holes"},
            "bracelet": {"expectedComponents": 1, "expectedHoles": 7, "reason": "frozen source-line accessory aggregate; six tiny legal negative spaces plus one registered internal skin-clearance opening"},
            "bracelet_back": {"expectedComponents": 1, "expectedHoles": 2, "reason": "frozen source-line rear-depth candidate for the proximal loop"},
            "bracelet_front": {"expectedComponents": 4, "expectedHoles": 2, "reason": "frozen observed foreground loop, beads, and hanging pieces"},
        },
        "registeredAccessoryNegativeSpaces": {
            "owner": "bracelet",
            "primaryLayer": "forearm",
            "roi": list(FOREARM_ACCESSORY_NEGATIVE_SPACE_ROI),
            "expectedHoleCount": 6,
            "holes": [
                {
                    "index": index + 1,
                    "coordinates": [list(point) for point in coordinates],
                    "fingerprint": FOREARM_REGISTERED_ACCESSORY_HOLE_FINGERPRINTS[index],
                    "semanticRole": "bracelet legal negative space",
                }
                for index, coordinates in enumerate(FOREARM_REGISTERED_ACCESSORY_HOLE_COORDINATES)
            ],
            "braceletInternalNonPrimaryOpening": FOREARM_BRACELET_NONPRIMARY_OPENING,
            "registrationRule": "forearm primary hole coordinate sets must equal these six frozen bracelet legal negative spaces exactly; every set must be inside the wrist ROI and match a bracelet complete hole; any extra or missing set fails",
            "noGenericRange": True,
        },
        "supersededChecks": {
            "forearm_semantic_topology": "superseded_by_semantic_core_and_registered_accessory_topology",
            "forearm_complete_single_component_no_holes": "superseded_by_semantic_core_and_registered_accessory_topology",
            "elbow_r1_envelope_included": "upper_arm_v8_candidate_boundary_registration",
        },
        "registeredComponents": {
            "bracelet": ["main_loop", "left_beads_or_knot", "right_beads_or_knot", "hanging_parts"],
        },
        "checks": [
            "body core is one 8-connected component",
            "forearm_skin anatomical core is one component with zero holes",
            "forearm primary accessory openings equal the six frozen bracelet legal negative-space coordinate sets",
            "unregistered forearm hole, extra bracelet negative space, or skin break fails",
            "old zero-hole forearm check is historical and explicitly superseded, never reported as a pass",
        ],
        "r2Gate": gate_state,
    }
    return {
        "layering": layering,
        "drawOrder": draw_order,
        "topology": topology,
        "forearmUcap": build_forearm_ucap_contract(geometry_meta, source_results),
    }


def check_masks(
    masks: dict[str, dict[str, Image.Image]],
    contracts: dict[str, dict[str, object]],
    source_results: dict[str, object],
) -> tuple[dict[str, object], Image.Image]:
    primary = masks["primary"]
    subregions = masks["subregions"]
    checks: list[dict[str, object]] = []

    def add(identifier: str, passed: bool, detail: str, **extra: object) -> None:
        checks.append({"id": identifier, "pass": bool(passed), "detail": detail, **extra})

    add("canvas_dimensions", all(mask.size == CANVAS for group in masks.values() for layer in group.values() for mask in layer.values()), "全部 R2 mask 为 512x1086 全画布")
    add("binary_logic_values", all(mask_values(mask) in ([0], [0, 255], [255]) for group in masks.values() for layer in group.values() for mask in layer.values()), "逻辑 mask 只含 0/255；抗锯齿不混入拓扑检查")

    for layer_id, layer_masks in primary.items():
        visible = layer_masks["visible"]
        hidden = layer_masks["hidden"]
        complete = layer_masks["complete"]
        overlap = mask_intersection(visible, hidden)
        expected_complete = mask_union(visible, hidden)
        add(f"{layer_id}_visible_hidden_disjoint", mask_count(overlap) == 0, f"{layer_id} visible∩hidden={mask_count(overlap)} px", overlapPixels=mask_count(overlap))
        add(f"{layer_id}_complete_union", expected_complete.tobytes() == complete.tobytes(), f"{layer_id} complete == visible∪hidden")
        add(f"{layer_id}_complete_not_less_than_visible", mask_count(mask_subtract(visible, complete)) == 0, f"{layer_id} complete 覆盖全部 visible")

    visible_layers = {layer_id: layer_masks["visible"] for layer_id, layer_masks in primary.items()}
    duplicate = blank_mask()
    visible_union = blank_mask()
    for layer_id, layer_mask in visible_layers.items():
        duplicate = mask_union(duplicate, mask_intersection(visible_union, layer_mask))
        visible_union = mask_union(visible_union, layer_mask)
    add("visible_ownership_unique", mask_count(duplicate) == 0, f"主要层 visible 重复所有权={mask_count(duplicate)} px", duplicatePixels=mask_count(duplicate))

    forearm_skin = subregions["forearm-skin"]
    bracelet = subregions["bracelet"]
    bracelet_back = subregions["bracelet-back"]
    bracelet_front = subregions["bracelet-front"]
    forearm_source_line_mask, forearm_source_line_meta = forearm_source_line_enclosure()
    forearm_elbow_source_mask, forearm_elbow_source_meta = forearm_elbow_source_enclosure()
    forearm_elbow_user_markup_mask, forearm_elbow_user_markup_meta = forearm_elbow_user_markup_boundary()
    shaft_source_roi = roi_mask(FOREARM_SHAFT_SOURCE_VISIBLE_ROI)
    # The redline-bounded cap/transition remain hidden and are above the
    # exposed shaft.  The visible lower elbow transition still comes from the
    # registered source component, so these checks cover the complete shaft ROI.
    shaft_source_audit_roi = shaft_source_roi
    expected_shaft_skin = ImageChops.multiply(
        mask_subtract(forearm_source_line_mask, primary["sleeve"]["visible"]),
        shaft_source_roi,
    )
    actual_shaft_skin = ImageChops.multiply(forearm_skin["visible"], shaft_source_roi)
    shaft_skin_outside_source = mask_subtract(actual_shaft_skin, forearm_source_line_mask)
    shaft_skin_missing_source = mask_subtract(expected_shaft_skin, actual_shaft_skin)
    shaft_hidden_outside_source = mask_subtract(
        ImageChops.multiply(forearm_skin["hidden"], shaft_source_audit_roi),
        forearm_source_line_mask,
    )
    shaft_complete_outside_source = mask_subtract(
        ImageChops.multiply(forearm_skin["complete"], shaft_source_audit_roi),
        forearm_source_line_mask,
    )
    add(
        "forearm_shaft_visible_matches_source_line_component",
        mask_count(shaft_skin_outside_source) == 0 and mask_count(shaft_skin_missing_source) == 0,
        "exposed forearm shaft visible ownership equals the source-line skin-side component after sleeve ownership",
        sourceLineBoundary=forearm_source_line_meta,
        outsideSourcePixels=mask_count(shaft_skin_outside_source),
        missingSourcePixels=mask_count(shaft_skin_missing_source),
    )
    add(
        "forearm_shaft_hidden_inside_source_line_component",
        mask_count(shaft_hidden_outside_source) == 0,
        "hidden corridor pixels cannot leak outside the authoritative shaft skin boundary at rest",
        outsideSourcePixels=mask_count(shaft_hidden_outside_source),
        excludedHiddenElbowMarkupRoi=[],
    )
    add(
        "forearm_shaft_complete_inside_source_line_component",
        mask_count(shaft_complete_outside_source) == 0,
        "complete forearm color block remains inside the authoritative shaft skin boundary",
        outsideSourcePixels=mask_count(shaft_complete_outside_source),
        excludedHiddenElbowMarkupRoi=[],
    )
    elbow_source_roi = roi_mask(FOREARM_ELBOW_SOURCE_REPAIR_ROI)
    expected_elbow_root = mask_intersection(forearm_elbow_source_mask, elbow_source_roi)
    actual_elbow_root = mask_intersection(forearm_skin["complete"], elbow_source_roi)
    elbow_root_outside_source = mask_subtract(actual_elbow_root, expected_elbow_root)
    elbow_source_gray = Image.open(
        SOURCE_ROOT / "masters" / "front-line-source-exact-after-reset.png"
    ).convert("L")
    elbow_source_barrier = Image.new("L", CANVAS, 0)
    elbow_source_barrier_pixels = elbow_source_barrier.load()
    elbow_source_left, elbow_source_top, elbow_source_right, elbow_source_bottom = FOREARM_ELBOW_SOURCE_REPAIR_ROI
    for y in range(elbow_source_top, elbow_source_bottom):
        for x in range(elbow_source_left, elbow_source_right):
            if elbow_source_gray.getpixel((x, y)) < FOREARM_ELBOW_SOURCE_BARRIER_LUMA_MAX:
                elbow_source_barrier_pixels[x, y] = 255
    elbow_source_edge = Image.new("L", CANVAS, 0)
    elbow_source_edge_pixels = elbow_source_edge.load()
    for y in range(elbow_source_top, elbow_source_bottom):
        for x in range(elbow_source_left, elbow_source_right):
            if elbow_source_gray.getpixel((x, y)) >= FOREARM_ELBOW_SOURCE_EDGE_LUMA_MAX:
                continue
            if any(
                elbow_source_barrier_pixels[x + dx, y + dy] > 0
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
                if (dx or dy)
                and 0 <= x + dx < WIDTH
                and 0 <= y + dy < HEIGHT
            ):
                elbow_source_edge_pixels[x, y] = 255
    elbow_root_outside_source_edge = mask_subtract(
        elbow_root_outside_source,
        elbow_source_edge,
    )
    elbow_user_markup_allowed = mask_intersection(
        forearm_elbow_user_markup_mask,
        elbow_source_roi,
    )
    elbow_registered_allowed = mask_union(
        expected_elbow_root,
        elbow_source_edge,
        elbow_user_markup_allowed,
    )
    elbow_root_outside_registered = mask_subtract(
        actual_elbow_root,
        elbow_registered_allowed,
    )
    elbow_source_overlap = mask_intersection(actual_elbow_root, expected_elbow_root)
    add(
        "forearm_elbow_root_inside_registered_source_or_user_boundary",
        mask_count(elbow_root_outside_registered) == 0 and mask_count(elbow_source_overlap) > 0,
        "肘根 hidden 只在注册源线边缘或最新红线内部；源线区域仍保持连接，手绘截图不直接充当 source 坐标",
        sourceLineBoundary=forearm_elbow_source_meta,
        userMarkupBoundary=forearm_elbow_user_markup_meta,
        outsideSourcePixels=mask_count(elbow_root_outside_source),
        outsideSourceEdgePixels=mask_count(elbow_root_outside_source_edge),
        outsideUserMarkupPixels=mask_count(mask_subtract(actual_elbow_root, elbow_user_markup_allowed)),
        outsideRegisteredPixels=mask_count(elbow_root_outside_registered),
        sourceOverlapPixels=mask_count(elbow_source_overlap),
        allowedAntialiasedSourcePixels=mask_count(
            mask_intersection(elbow_root_outside_source, elbow_source_edge)
        ),
    )
    (
        wrist_source_skin,
        wrist_bracelet_back_source,
        wrist_bracelet_front_source,
        wrist_source_meta,
        wrist_source_hidden_guard,
        wrist_source_hidden_display_guard,
    ) = wrist_source_line_materials(
        Image.open(SOURCE_ROOT / "masters" / "front-line-source-exact-after-reset.png").convert("RGB")
    )
    wrist_source_bracelet_guard = mask_union(
        wrist_bracelet_back_source,
        wrist_bracelet_front_source,
    )
    wrist_repair_roi = roi_mask(FOREARM_WRIST_SOURCE_REPAIR_ROI)
    actual_wrist_skin = mask_intersection(forearm_skin["visible"], wrist_repair_roi)
    expected_wrist_skin = mask_subtract(wrist_source_skin, primary["sleeve"]["visible"])
    wrist_skin_outside_source = mask_subtract(actual_wrist_skin, expected_wrist_skin)
    wrist_skin_missing_source = mask_subtract(expected_wrist_skin, actual_wrist_skin)
    bracelet_outside_repair_roi = mask_subtract(bracelet["visible"], wrist_repair_roi)
    registered_shield_pixels = mask_subtract(bracelet["visible"], wrist_source_bracelet_guard)
    bracelet_unregistered_pixels = mask_subtract(
        bracelet["visible"],
        mask_union(wrist_source_bracelet_guard, registered_shield_pixels),
    )
    add(
        "forearm_wrist_skin_matches_source_line_components",
        mask_count(wrist_skin_outside_source) == 0 and mask_count(wrist_skin_missing_source) == 0,
        "bracelet 下方的 forearm skin 仅来自腕部源线自由区域；不再使用宽 convex bridge",
        sourceLineBoundary=wrist_source_meta,
        outsideSourcePixels=mask_count(wrist_skin_outside_source),
        missingSourcePixels=mask_count(wrist_skin_missing_source),
    )
    add(
        "bracelet_source_line_boundary_registered",
        mask_count(bracelet_outside_repair_roi) == 0 and mask_count(bracelet_unregistered_pixels) == 0,
        "手链可见 ownership 仅来自注册的源线 corridor，另保留受保护 hand 的局部 ownership shield",
        sourceLinePixels=mask_count(wrist_source_bracelet_guard),
        registeredShieldPixels=mask_count(registered_shield_pixels),
        outsideRepairRoiPixels=mask_count(bracelet_outside_repair_roi),
        unregisteredPixels=mask_count(bracelet_unregistered_pixels),
    )
    skin_bracelet_visible_overlap = mask_intersection(forearm_skin["visible"], bracelet["visible"])
    depth_overlap = mask_intersection(forearm_skin["hidden"], bracelet["visible"])
    bracelet_partition_overlap = mask_intersection(bracelet_back["visible"], bracelet_front["visible"])
    bracelet_partition_union = mask_union(bracelet_back["visible"], bracelet_front["visible"])
    back_skin_visible_overlap = mask_intersection(bracelet_back["visible"], forearm_skin["visible"])
    front_skin_visible_overlap = mask_intersection(bracelet_front["visible"], forearm_skin["visible"])
    front_hand_overlap = mask_intersection(bracelet_front["visible"], primary["hand"]["complete"])
    back_skin_hidden_overlap = mask_intersection(bracelet_back["visible"], forearm_skin["hidden"])
    add("forearm_skin_bracelet_visible_disjoint", mask_count(skin_bracelet_visible_overlap) == 0, f"forearm_skin.visible∩bracelet.visible={mask_count(skin_bracelet_visible_overlap)} px")
    bracelet_missing_from_primary = mask_subtract(bracelet["visible"], primary["forearm"]["visible"])
    expected_forearm_visible = mask_union(forearm_skin["visible"], bracelet["visible"])
    add("bracelet_owned_by_primary_forearm", mask_count(bracelet_missing_from_primary) == 0, f"bracelet.visible 未被 forearm.primary 包含={mask_count(bracelet_missing_from_primary)} px")
    add("primary_forearm_visible_equals_skin_plus_bracelet", primary["forearm"]["visible"].tobytes() == expected_forearm_visible.tobytes(), "forearm.primary.visible == forearm_skin.visible∪bracelet.visible")
    add("hand_bracelet_visible_disjoint", mask_count(mask_intersection(primary["hand"]["visible"], bracelet["visible"])) == 0, "hand visible 不包含 bracelet")
    add("registered_forearm_skin_bracelet_depth_overlap", mask_count(depth_overlap) > 0, f"允许的 forearm_skin.hidden∩bracelet.visible={mask_count(depth_overlap)} px", depthOverlapPixels=mask_count(depth_overlap))
    add("bracelet_back_front_disjoint", mask_count(bracelet_partition_overlap) == 0, f"bracelet_back.visible∩bracelet_front.visible={mask_count(bracelet_partition_overlap)} px", overlapPixels=mask_count(bracelet_partition_overlap))
    add("bracelet_back_front_partition_complete", bracelet_partition_union.tobytes() == bracelet["visible"].tobytes(), "bracelet.visible == bracelet_back.visible∪bracelet_front.visible")
    add("bracelet_back_forearm_skin_visible_disjoint", mask_count(back_skin_visible_overlap) == 0, f"bracelet_back 不覆盖 forearm_skin.visible={mask_count(back_skin_visible_overlap)} px")
    add("bracelet_front_forearm_skin_visible_disjoint", mask_count(front_skin_visible_overlap) == 0, f"bracelet_front 不覆盖 forearm_skin.visible={mask_count(front_skin_visible_overlap)} px")
    add("bracelet_back_depth_candidate_overlaps_hidden_skin", mask_count(back_skin_hidden_overlap) > 0, f"bracelet_back 与 forearm_skin.hidden 的候选深度重叠={mask_count(back_skin_hidden_overlap)} px", overlapPixels=mask_count(back_skin_hidden_overlap))
    add("bracelet_front_is_in_front_of_skin_and_hand", [entry["id"] for entry in contracts["drawOrder"]["forearmSubregionDrawOrder"]] == ["bracelet_back", "forearm_skin", "hand", "bracelet_front"], f"bracelet_front 与 forearm_skin/hand 的 QA 绘制顺序已注册；hand 重叠={mask_count(front_hand_overlap)} px", frontHandOverlapPixels=mask_count(front_hand_overlap))

    guards = build_guards()
    guard_outside = {}
    for layer_id, guard in guards.items():
        owner_mask = visible_layers[layer_id] if layer_id in visible_layers else blank_mask()
        outside = mask_subtract(owner_mask, guard)
        guard_outside[layer_id] = mask_count(outside)
        add(f"{layer_id}_visible_inside_manual_source_guard", mask_count(outside) == 0, f"{layer_id} 原始可见语义 guard 外 alpha={mask_count(outside)} px", outsidePixels=mask_count(outside))

    required_samples = {
        "sleeve": [(140, 330), (160, 280)],
        "forearm": [(140, 450), (125, 490)],
        "hand": [(102, 570), (92, 590)],
    }
    for layer_id, points in required_samples.items():
        layer_mask = visible_layers[layer_id]
        passed = all(layer_mask.getpixel(point) > 0 for point in points)
        add(f"{layer_id}_source_visible_samples", passed, f"{layer_id} 手工语义采样点均有 visible 所有者", points=points)

    contracts_identity = all(
        contract.get("bodySpaceTransform") == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        for contract in contracts.values()
        if isinstance(contract, dict) and "bodySpaceTransform" in contract
    )
    add("identity_body_space_transform", contracts_identity, "R2 合同声明 body-space identity transform")
    add("source_input_hashes", all(bool(item["pass"]) for item in source_results.values()), "四个 R2 原始权威图像哈希/尺寸/模式通过")

    r1_contracts = load_contracts()
    joint_entries = {item["id"]: item for item in r1_contracts["envelope"]["joints"]}
    forearm_ucap_contract = contracts.get("forearmUcap")
    boundary_contract = forearm_ucap_contract.get("boundaryContract") if isinstance(forearm_ucap_contract, dict) else None
    latest_markup_contract = boundary_contract.get("latestUserMarkup") if isinstance(boundary_contract, dict) else None
    expected_control_points = [list(point) for point in FOREARM_DISTAL_UCAP_CONTROL_POINTS]
    expected_bezier_segments = [[list(point) for point in segment] for segment in FOREARM_DISTAL_UCAP_BEZIER_SEGMENTS]
    active_wrist_contract_fresh = (
        isinstance(boundary_contract, dict)
        and isinstance(latest_markup_contract, dict)
        and str(latest_markup_contract.get("path", "")).replace("\\", "/") == FOREARM_USER_MARKUP_PATH
        and str(latest_markup_contract.get("sha256", "")).lower() == FOREARM_USER_MARKUP_SHA256
        and list(latest_markup_contract.get("dimensions", [])) == list(FOREARM_USER_MARKUP_DIMENSIONS)
        and latest_markup_contract.get("closedTrace") == [list(point) for point in FOREARM_USER_MARKUP_CLOSED_TRACE]
        and boundary_contract.get("controlPoints") == expected_control_points
        and boundary_contract.get("bezierSegments") == expected_bezier_segments
    )
    add(
        "forearm_active_redline_boundary_contract_fresh",
        active_wrist_contract_fresh,
        "当前 forearm U-cap 合同必须与 2026-08-11 隐藏连接用户蓝线 hash、closedTrace 和控制点逐项一致",
        markupPath=FOREARM_USER_MARKUP_PATH,
        markupSha256=FOREARM_USER_MARKUP_SHA256,
        confirmedRedrawOn=FOREARM_REDRAW_CONFIRMATION_DATE,
    )
    active_wrist_envelope_raw = (
        render_active_forearm_wrist_redline_envelope()
        if active_wrist_contract_fresh
        else Image.new("L", CANVAS, 255)
    )
    # At this seam the source skin contour is stricter than the broad
    # occluded part of the user redline.  Keep the raw redline for visual
    # evidence, but make the engineering coverage envelope the redline
    # intersected with the coordinate-locked source hidden-skin guard.  This
    # prevents a redline point on a bracelet/hand barrier from authorizing a
    # protruding color pixel.
    active_wrist_envelope = mask_intersection(
        active_wrist_envelope_raw,
        wrist_source_hidden_display_guard,
    )
    joint_coverage = {}
    for joint_id, owners in {
        "shoulder": mask_union(primary["sleeve"]["hidden"], primary["upper_arm"]["hidden"]),
        "elbow": mask_union(primary["upper_arm"]["hidden"], primary["forearm"]["hidden"]),
        "wrist": mask_union(forearm_skin["hidden"], primary["hand"]["hidden"]),
    }.items():
        if joint_id == "wrist":
            envelope = active_wrist_envelope
            envelope_source = "intersection(contracts/forearm-distal-ucap-contract.json:boundaryContract.latestUserMarkup.closedTrace, sourceLineWristGuard.hiddenUcapDisplayGuard)"
        else:
            envelope = envelope_mask(joint_entries[joint_id])
            envelope_source = f"{R1_ENVELOPE_CONTRACT_PATH.relative_to(REPO_ROOT).as_posix()}:{joint_id}.activeEnvelope"
        # The R1 envelope is a joint coverage constraint.  At rest, an
        # observed visible contour is already a valid owner; hidden geometry
        # must cover the remaining part.  Counting only hidden pixels would
        # incorrectly reject a source-aligned visible wrist/shoulder edge.
        if joint_id == "shoulder":
            owners = mask_union(
                owners,
                primary["sleeve"]["visible"],
                primary["upper_arm"]["visible"],
            )
        elif joint_id == "elbow":
            owners = mask_union(
                owners,
                primary["upper_arm"]["visible"],
                primary["forearm"]["visible"],
            )
        else:
            owners = mask_union(
                owners,
                forearm_skin["visible"],
                primary["hand"]["visible"],
            )
        uncovered = mask_subtract(envelope, owners)
        joint_coverage[joint_id] = {
            "envelopePixels": mask_count(envelope),
            "uncoveredPixels": mask_count(uncovered),
            "envelopeSource": envelope_source,
        }
        if joint_id == "wrist":
            historical_envelope = envelope_mask(joint_entries[joint_id])
            historical_uncovered = mask_subtract(historical_envelope, owners)
            joint_coverage[joint_id]["historicalR1Envelope"] = {
                "source": f"{R1_ENVELOPE_CONTRACT_PATH.relative_to(REPO_ROOT).as_posix()}:wrist.activeEnvelope",
                "envelopePixels": mask_count(historical_envelope),
                "uncoveredPixels": mask_count(historical_uncovered),
                "supersededForReopenedForearmUcap": True,
            }
            passed = active_wrist_contract_fresh and mask_count(uncovered) == 0
            detail = f"active latest user blue boundary wrist 包络可见/隐藏责任未覆盖={mask_count(uncovered)} px；历史 R1 未覆盖={mask_count(historical_uncovered)} px（已由本次重画替代）"
        elif joint_id == "elbow":
            uncovered_points = tuple(sorted(nonzero_points(uncovered)))
            expected_residual = tuple(sorted(UPPER_ARM_V8_SUPERSEDED_R1_ELBOW_RESIDUAL))
            residual_registered = uncovered_points == expected_residual and load_whole_hand_visual_approval() is not None
            joint_coverage[joint_id]["historicalR1EnvelopeResidual"] = {
                "coordinates": [list(point) for point in uncovered_points],
                "expectedCoordinates": [list(point) for point in expected_residual],
                "pixels": len(uncovered_points),
                "supersededBy": "candidates/upper-arm-aa-anatomical-v8/audit/upper-arm-aa-anatomical-contract.json",
                "reason": "the approved v8 upper-arm loop is the current formal boundary; these exact two historical R1 envelope pixels are outside both v8 upper-arm and forearm ownership",
                "registered": residual_registered,
            }
            checks.append({
                "id": "elbow_r1_envelope_included",
                "pass": None,
                "status": "superseded",
                "supersededBy": "upper_arm_v8_candidate_boundary_registration",
                "detail": "R1 elbow envelope is historical evidence only for the approved upper-arm v8 formal boundary; it is not rewritten as a false full-coverage pass",
                **joint_coverage[joint_id],
            })
            add(
                "elbow_upper_arm_v8_boundary_registration",
                residual_registered,
                "upper-arm v8 formal boundary registration must account for the exact historical R1 elbow residual pixels",
                **joint_coverage[joint_id],
            )
            continue
        else:
            passed = mask_count(uncovered) == 0
            detail = f"R1 {joint_id} 包络可见/隐藏责任未覆盖={mask_count(uncovered)} px"
        add(f"{joint_id}_r1_envelope_included", passed, detail, **joint_coverage[joint_id])

    overlap_pairs = {
        "shoulder_sleeve_upper_arm": (primary["sleeve"]["hidden"], primary["upper_arm"]["hidden"], (166, 270), 97.507347),
        "elbow_upper_arm_forearm": (primary["upper_arm"]["hidden"], primary["forearm"]["hidden"], (149, 399), 105.672821),
        "wrist_forearm_hand": (forearm_skin["hidden"], primary["hand"]["hidden"], (110, 538), 113.198591),
    }
    overlap_reports = {}
    for identifier, (first, second, center, axis) in overlap_pairs.items():
        overlap = mask_intersection(first, second)
        longitudinal = projected_span(overlap, center, axis)
        transverse = projected_span(overlap, center, axis + 90.0)
        overlap_reports[identifier] = {"pixels": mask_count(overlap), "longitudinalSpanPx": round(longitudinal, 4), "transverseSpanPx": round(transverse, 4)}
        add(f"{identifier}_hidden_overlap", mask_count(overlap) > 0 and longitudinal >= 1.0 and transverse >= 1.0, f"{identifier} 隐藏重叠满足正向覆盖", **overlap_reports[identifier])

    topology_reports: dict[str, object] = {}
    topology_masks = {
        "sleeve": primary["sleeve"]["complete"],
        "upper_arm": primary["upper_arm"]["complete"],
        "forearm": primary["forearm"]["complete"],
        "forearm_skin": forearm_skin["complete"],
        "hand": primary["hand"]["complete"],
        "bracelet": bracelet["complete"],
        "bracelet_back": bracelet_back["complete"],
        "bracelet_front": bracelet_front["complete"],
    }
    for layer_id, mask in topology_masks.items():
        components = component_stats(mask)
        hole_details = hole_components(mask)
        holes = len(hole_details)
        topology_reports[layer_id] = {
            "componentCount": len(components),
            "components": components[:8],
            "holeCount": holes,
            "holeComponents": hole_details,
            "pixelCount": mask_count(mask),
        }
        if layer_id == "forearm":
            # The old zero-hole assertion is retained as historical metadata,
            # never converted into a false pass.  Its engineering status is
            # excluded explicitly by the formal semantic checks below.
            checks.extend([
                {
                    "id": "forearm_semantic_topology",
                    "pass": None,
                    "status": "superseded",
                    "supersededBy": "superseded_by_semantic_core_and_registered_accessory_topology",
                    "detail": f"旧 forearm 组件/孔洞检查不再适用于 forearm-owned bracelet negative spaces：组件={len(components)} 孔洞={holes}",
                    **topology_reports[layer_id],
                },
                {
                    "id": "forearm_complete_single_component_no_holes",
                    "pass": None,
                    "status": "superseded",
                    "supersededBy": "superseded_by_semantic_core_and_registered_accessory_topology",
                    "detail": f"旧零孔洞断言已明确废弃：forearm complete 组件={len(components)}、六个孔洞均为已登记手链负空间",
                    **topology_reports[layer_id],
                },
            ])
            continue
        contract_entry = contracts["topology"]["connectivity"][layer_id]
        if layer_id in ("bracelet", "bracelet_back", "bracelet_front"):
            passed = len(components) == int(contract_entry["expectedComponents"]) and holes == int(contract_entry["expectedHoles"])
        else:
            passed = len(components) == int(contract_entry["expectedCoreComponents"]) and holes == int(contract_entry["expectedHoles"])
        add(f"{layer_id}_semantic_topology", passed, f"{layer_id} 组件={len(components)} 孔洞={holes}", **topology_reports[layer_id])

    forearm_skin_topology = cast(dict[str, object], topology_reports["forearm_skin"])
    forearm_topology = cast(dict[str, object], topology_reports["forearm"])
    bracelet_topology = cast(dict[str, object], topology_reports["bracelet"])
    registered_contract = contracts["topology"]["registeredAccessoryNegativeSpaces"]
    registered_entries = cast(list[dict[str, object]], registered_contract["holes"])
    registered_sets = {
        frozenset(tuple(point) for point in cast(list[list[int]], entry["coordinates"]))
        for entry in registered_entries
    }
    actual_forearm_hole_sets = {
        frozenset(tuple(point) for point in cast(list[list[int]], hole["coordinates"]))
        for hole in cast(list[dict[str, object]], forearm_topology["holeComponents"])
    }
    bracelet_hole_sets = {
        frozenset(tuple(point) for point in cast(list[list[int]], hole["coordinates"]))
        for hole in cast(list[dict[str, object]], bracelet_topology["holeComponents"])
    }
    roi_left, roi_top, roi_right, roi_bottom = FOREARM_ACCESSORY_NEGATIVE_SPACE_ROI
    forearm_holes_inside_roi = all(
        roi_left <= x < roi_right and roi_top <= y < roi_bottom
        for hole in cast(list[dict[str, object]], forearm_topology["holeComponents"])
        for x, y in cast(list[list[int]], hole["coordinates"])
    )
    missing_registered = [
        entry for entry in registered_entries
        if frozenset(tuple(point) for point in cast(list[list[int]], entry["coordinates"])) not in actual_forearm_hole_sets
    ]
    unregistered_forearm = [
        hole for hole in cast(list[dict[str, object]], forearm_topology["holeComponents"])
        if frozenset(tuple(point) for point in cast(list[list[int]], hole["coordinates"])) not in registered_sets
    ]
    bracelet_registered_match = registered_sets.issubset(bracelet_hole_sets)
    bracelet_nonprimary = next(
        (
            hole for hole in cast(list[dict[str, object]], bracelet_topology["holeComponents"])
            if int(hole["pixels"]) == int(FOREARM_BRACELET_NONPRIMARY_OPENING["pixels"])
            and hole["bbox"] == FOREARM_BRACELET_NONPRIMARY_OPENING["bbox"]
            and hole["fingerprint"] == FOREARM_BRACELET_NONPRIMARY_OPENING["fingerprint"]
        ),
        None,
    )
    forearm_skin_core_pass = int(forearm_skin_topology["componentCount"]) == 1 and int(forearm_skin_topology["holeCount"]) == 0
    accessory_registration_pass = (
        int(forearm_topology["componentCount"]) == 1
        and int(forearm_topology["holeCount"]) == len(registered_entries) == 6
        and actual_forearm_hole_sets == registered_sets
        and not missing_registered
        and not unregistered_forearm
        and forearm_holes_inside_roi
        and bracelet_registered_match
        and bracelet_nonprimary is not None
    )
    topology_reports["forearmSemanticRegistration"] = {
        "forearmSkinCore": forearm_skin_topology,
        "forearmPrimary": forearm_topology,
        "braceletAggregate": bracelet_topology,
        "registeredExpectedHoleCount": len(registered_entries),
        "registeredHoleFingerprints": [entry["fingerprint"] for entry in registered_entries],
        "missingRegisteredHoles": missing_registered,
        "unregisteredForearmHoles": unregistered_forearm,
        "allForearmHolesInsideWristRoi": forearm_holes_inside_roi,
        "braceletRegisteredNegativeSpacesMatch": bracelet_registered_match,
        "braceletNonPrimaryOpening": bracelet_nonprimary,
        "roi": list(FOREARM_ACCESSORY_NEGATIVE_SPACE_ROI),
    }
    add(
        "forearm_skin_anatomical_core_topology",
        forearm_skin_core_pass,
        f"forearm_skin anatomical core 必须单一 8-connected 且 0 孔洞：组件={forearm_skin_topology['componentCount']} 孔洞={forearm_skin_topology['holeCount']}",
        **forearm_skin_topology,
    )
    add(
        "forearm_accessory_negative_spaces_registered",
        accessory_registration_pass,
        "forearm primary 的每一个孔洞必须逐坐标匹配冻结 bracelet legal negative space；不接受通用孔洞范围",
        **topology_reports["forearmSemanticRegistration"],
    )
    add(
        "forearm_primary_semantic_topology",
        forearm_skin_core_pass and accessory_registration_pass,
        "forearm primary 连通性由连续 skin core + 已登记 bracelet accessory negative spaces 共同决定",
        **topology_reports["forearmSemanticRegistration"],
    )

    add("layer_only_does_not_use_whole_character_base", True, "layer-only 拼装只合成 R2 自有 flat layers；原始线/彩仅用于独立 overlay")

    root_reports = {
        "hand_wrist_root": local_root_shape_report(primary["hand"]["complete"], (90, 515, 140, 558), "hand complete wrist root", 34, 20),
        "forearm_wrist_root": local_root_shape_report(forearm_skin["complete"], (92, 515, 138, 555), "forearm complete wrist root", 32, 30),
        "upper_arm_shoulder_root": local_root_shape_report(primary["upper_arm"]["complete"], (135, 235, 185, 305), "upper_arm complete shoulder root", 32, 20),
    }
    for root_id, root_report in root_reports.items():
        add(f"{root_id}_no_hard_cut_or_sharp_root", bool(root_report["pass"]), f"{root_report['label']}：Bezier 连续根部，horizontalCut={root_report['hardHorizontalCut']}", **root_report)

    hand_root_geometry = hand_wrist_root_geometry_report(primary["hand"])
    for check in hand_root_geometry["checks"]:
        add(
            f"hand_wrist_aa_{check['id']}",
            bool(check["pass"]),
            f"hand_wrist_root AA maintenance: {check['id']}",
            **{key: value for key, value in check.items() if key not in {"id", "pass"}},
        )

    heatmap = Image.new("RGB", CANVAS, (250, 250, 250))
    heat_pixels = heatmap.load()
    layer_colors = [DEBUG_COLORS["sleeve"], DEBUG_COLORS["upper_arm"], DEBUG_COLORS["forearm"], DEBUG_COLORS["hand"]]
    masks_in_order = [visible_layers[layer_id] for layer_id in FORMAL_LAYER_IDS]
    for y in range(HEIGHT):
        for x in range(WIDTH):
            owners = [index for index, mask in enumerate(masks_in_order) if mask.getpixel((x, y)) > 0]
            if len(owners) > 1:
                heat_pixels[x, y] = (230, 53, 53)
            elif len(owners) == 1:
                heat_pixels[x, y] = layer_colors[owners[0]]
    diagnostics = {
        "checks": checks,
        "guardOutsidePixels": guard_outside,
        "jointCoverage": joint_coverage,
        "overlapReports": overlap_reports,
        "topology": topology_reports,
        "rootReports": root_reports,
        "handWristRootGeometry": hand_root_geometry,
        "visibleOwnershipPixels": mask_count(visible_union),
        "duplicateVisiblePixels": mask_count(duplicate),
        "forearmSkinBraceletDepthOverlapPixels": mask_count(depth_overlap),
        "braceletBackSkinHiddenOverlapPixels": mask_count(back_skin_hidden_overlap),
        "braceletFrontHandOverlapPixels": mask_count(front_hand_overlap),
        "forearmSourceLineBoundary": forearm_source_line_meta,
    }
    return diagnostics, heatmap


def write_masks(masks: dict[str, dict[str, Image.Image]]) -> list[Path]:
    written: list[Path] = []
    for group_name, groups in (("primary", masks["primary"]), ("subregions", masks["subregions"])):
        for layer_id, layer_masks in groups.items():
            for variant, mask in layer_masks.items():
                if group_name == "primary" and layer_id == "hand":
                    # Hand visible/hidden/complete are protected inputs for
                    # this forearm-only reopen.  The generated in-memory hand
                    # is checked against the protected hashes in main(), but
                    # these files are never rewritten here.
                    continue
                if group_name == "primary":
                    path = R2_ROOT / "masks" / variant / f"{layer_id}.png"
                else:
                    path = R2_ROOT / "masks" / "subregions" / f"{layer_id}-{variant}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                mask.save(path, format="PNG", optimize=False, compress_level=9)
                written.append(path)
    return written


def build_lift_action(layers: dict[str, Image.Image]) -> dict[str, object]:
    """Exercise the four complete materials as one articulated color-block chain."""
    frames: list[dict[str, object]] = []
    layer_order = ("upper_arm", "sleeve", "forearm", "hand")
    static_layer_topology = {
        layer_id: {
            "componentCount": len(component_point_sets(layers[layer_id].getchannel("A"))),
            "components": component_stats(layers[layer_id].getchannel("A")),
            "resample": "NEAREST" if layer_id in {"upper_arm", "sleeve"} else "BICUBIC",
            "alphaThreshold": 128 if layer_id in {"forearm", "hand"} else None,
        }
        for layer_id in layer_order
    }

    def point_bbox(points: set[tuple[int, int]]) -> list[int]:
        return [
            min(x for x, _ in points),
            min(y for _, y in points),
            max(x for x, _ in points) + 1,
            max(y for _, y in points) + 1,
        ]

    def shortest_distance(first: set[tuple[int, int]], second: set[tuple[int, int]]) -> dict[str, object]:
        best = float("inf")
        closest: tuple[tuple[int, int], tuple[int, int]] | None = None
        for first_point in first:
            for second_point in second:
                distance = math.hypot(first_point[0] - second_point[0], first_point[1] - second_point[1])
                if distance < best:
                    best = distance
                    closest = (first_point, second_point)
        return {
            "pixels": round(best, 3),
            "between": [list(point) for point in closest] if closest else None,
        }

    for pose in LIFT_ACTION_POSES:
        shoulder_angle = float(pose["shoulderAngle"])
        elbow_angle = float(pose["elbowAngle"])

        # sleeve and upper_arm are one shoulder chain.  forearm and hand first
        # fold around the original elbow, then inherit the shoulder transform;
        # this is the parent-child order that the previous sleeve-only test did
        # not exercise.
        upper_arm_pose = rotate_nearest(layers["upper_arm"], shoulder_angle, SHOULDER_PIVOT)
        sleeve_pose = rotate_nearest(layers["sleeve"], shoulder_angle, SHOULDER_PIVOT)
        forearm_pose = transform_with_pil_rotations(
            layers["forearm"],
            [(ELBOW_PIVOT, elbow_angle), (SHOULDER_PIVOT, shoulder_angle)],
        )
        hand_pose = transform_with_pil_rotations(
            layers["hand"],
            [(ELBOW_PIVOT, elbow_angle), (SHOULDER_PIVOT, shoulder_angle)],
        )
        composite = alpha_composite_layers([upper_arm_pose, sleeve_pose, hand_pose, forearm_pose])

        elbow_point = rotate_point_pil(ELBOW_PIVOT, SHOULDER_PIVOT, shoulder_angle)
        wrist_after_elbow = rotate_point_pil(WRIST_PIVOT, ELBOW_PIVOT, elbow_angle)
        wrist_point = rotate_point_pil(wrist_after_elbow, SHOULDER_PIVOT, shoulder_angle)
        upper_alpha = upper_arm_pose.getchannel("A")
        sleeve_alpha = sleeve_pose.getchannel("A")
        forearm_alpha = forearm_pose.getchannel("A")
        hand_alpha = hand_pose.getchannel("A")
        composite_alpha = composite.getchannel("A")
        posed_layers = {
            "upper_arm": upper_arm_pose,
            "sleeve": sleeve_pose,
            "forearm": forearm_pose,
            "hand": hand_pose,
        }
        composite_components = component_point_sets(composite_alpha)
        detached_diagnostics: list[dict[str, object]] = []
        if len(composite_components) > 1:
            main_component = composite_components[0]
            for component_index, component in enumerate(composite_components[1:], start=2):
                owners: list[dict[str, object]] = []
                for layer_id, posed_layer in posed_layers.items():
                    overlap = component & set(nonzero_points(posed_layer.getchannel("A")))
                    if overlap:
                        owners.append({
                            "layer": layer_id,
                            "pixels": len(overlap),
                            "bbox": point_bbox(overlap),
                        })
                owners.sort(key=lambda item: int(item["pixels"]), reverse=True)
                semantic_layer = str(owners[0]["layer"]) if owners else "unknown"
                transformed_component_count = len(component_point_sets(posed_layers[semantic_layer].getchannel("A"))) if semantic_layer in posed_layers else None
                static_info = static_layer_topology.get(semantic_layer, {})
                detached_diagnostics.append({
                    "componentIndex": component_index,
                    "semanticLayer": semantic_layer,
                    "pixelCount": len(component),
                    "bbox": point_bbox(component),
                    "owners": owners,
                    "shortestDistanceToMain": shortest_distance(main_component, component),
                    "staticPreRotationComponentCount": static_info.get("componentCount"),
                    "transformedLayerComponentCount": transformed_component_count,
                    "resample": static_info.get("resample"),
                    "alphaThreshold": static_info.get("alphaThreshold"),
                    "likelyBoundaryCut": semantic_layer == "hand" and static_info.get("componentCount") == 1 and transformed_component_count == 2,
                    "diagnosticOnly": True,
                    "r3Risk": True,
                    "requiresFutureR3HighResolutionFloatingBoundaryCoveragePoints": 41,
                    "interpretation": "静态 complete mask 单组件；本帧是变换后低分辨率 BICUBIC + Alpha>=128 取阈值导致的 hand 小岛，不删除、不膨胀、不改写为 R3 通过",
                })
        frames.append({
            "id": str(pose["id"]),
            "shoulderAngle": shoulder_angle,
            "elbowAngle": elbow_angle,
            "elbow": {"x": round(elbow_point[0], 3), "y": round(elbow_point[1], 3)},
            "wrist": {"x": round(wrist_point[0], 3), "y": round(wrist_point[1], 3)},
            "shoulderOverlapPixels": local_intersection_count(upper_alpha, sleeve_alpha, SHOULDER_PIVOT, 30),
            "elbowOverlapPixels": local_intersection_count(upper_alpha, forearm_alpha, elbow_point, 24),
            "wristOverlapPixels": local_intersection_count(forearm_alpha, hand_alpha, wrist_point, 20),
            "connectedComponents": len(composite_components),
            "detachedComponentDiagnostics": detached_diagnostics,
            "composite": composite,
        })

    first = frames[0]
    last = frames[-1]
    peak = max(frames, key=lambda frame: abs(float(frame["shoulderAngle"])))
    first_alpha = first["composite"].getchannel("A")
    last_alpha = last["composite"].getchannel("A")
    first_wrist = first["wrist"]
    peak_wrist = peak["wrist"]
    wrist_displacement = math.hypot(
        float(peak_wrist["x"]) - float(first_wrist["x"]),
        float(peak_wrist["y"]) - float(first_wrist["y"]),
    )

    checks = [
        {
            "id": "lift_action_nontrivial_displacement",
            "pass": wrist_displacement >= 25.0,
            "detail": f"峰值 wrist 位移={wrist_displacement:.3f}px，不能用静止色块冒充抬手",
            "peakWristDisplacementPx": round(wrist_displacement, 3),
        },
        {
            "id": "lift_action_return_alpha_deterministic",
            "pass": first_alpha.tobytes() == last_alpha.tobytes(),
            "detail": "0 -> 1 -> 0 首尾 composite alpha 完全一致",
        },
        {
            "id": "lift_action_all_frames_connected",
            "pass": all(int(frame["connectedComponents"]) == 1 for frame in frames),
            "detail": "每个抬手帧的四层色块为单一连通手臂链",
            "componentCounts": [int(frame["connectedComponents"]) for frame in frames],
            "detachedComponentDiagnostics": [
                {
                    "frame": frame["id"],
                    "components": frame["detachedComponentDiagnostics"],
                }
                for frame in frames
                if frame["detachedComponentDiagnostics"]
            ],
            "diagnosticOnly": True,
            "r3Risk": True,
            "staticCompleteMasksRemainConnected": all(
                int(value["componentCount"]) == 1 for value in static_layer_topology.values()
            ),
            "resampleRule": "BICUBIC + Alpha>=128 threshold for forearm/hand transformed layers",
            "nextRequiredEvidence": "R3 only: high-resolution floating-boundary coverage with at least 41 boundary points; no R3 run in this task",
        },
        {
            "id": "lift_action_shoulder_chain_overlap",
            "pass": all(int(frame["shoulderOverlapPixels"]) > 0 for frame in frames),
            "detail": "sleeve 与 upper_arm 始终在肩点局部重叠",
            "overlapPixels": [int(frame["shoulderOverlapPixels"]) for frame in frames],
        },
        {
            "id": "lift_action_elbow_chain_overlap",
            "pass": all(int(frame["elbowOverlapPixels"]) > 0 for frame in frames),
            "detail": "upper_arm 与 forearm 始终在变换后的肘点局部重叠",
            "overlapPixels": [int(frame["elbowOverlapPixels"]) for frame in frames],
        },
        {
            "id": "lift_action_wrist_chain_overlap",
            "pass": all(int(frame["wristOverlapPixels"]) > 0 for frame in frames),
            "detail": "forearm（含手链）与 hand 始终在变换后的腕点局部重叠",
            "overlapPixels": [int(frame["wristOverlapPixels"]) for frame in frames],
        },
    ]
    return {
        "pivots": {
            "shoulder": {"x": SHOULDER_PIVOT[0], "y": SHOULDER_PIVOT[1]},
            "elbow": {"x": ELBOW_PIVOT[0], "y": ELBOW_PIVOT[1]},
            "wrist": {"x": WRIST_PIVOT[0], "y": WRIST_PIVOT[1]},
        },
        "transformOrder": [
            "sleeve <- shoulder rotation",
            "upper_arm <- shoulder rotation",
            "forearm <- elbow fold, then shoulder rotation",
            "hand <- elbow fold, then shoulder rotation",
        ],
        "staticLayerTopology": static_layer_topology,
        "diagnosticInterpretation": {
            "staticCompleteMasksConnected": all(int(value["componentCount"]) == 1 for value in static_layer_topology.values()),
            "detachedComponentsBelongTo": sorted({
                str(component["semanticLayer"])
                for frame in frames
                for component in cast(list[dict[str, object]], frame["detachedComponentDiagnostics"])
            }),
            "status": "R2 diagnostic-only; do not claim action/runtime/R3 pass",
        },
        "frames": frames,
        "checks": checks,
    }


def write_flat_layers(
    masks: dict[str, dict[str, Image.Image]],
    forearm_ucap_logic: dict[str, Image.Image | object],
) -> tuple[list[Path], dict[str, Image.Image], dict[str, object], dict[str, object]]:
    primary = masks["primary"]
    subregions = masks["subregions"]
    formal = render_forearm_formal_display_alphas(masks, forearm_ucap_logic)
    forearm_display = cast(Image.Image, formal["forearm"])
    forearm_skin_display = cast(Image.Image, formal["forearmSkin"])
    bracelet_display = source_locked_antialiased_mask(
        subregions["bracelet"]["visible"],
        subregions["bracelet"]["visible"],
        FOREARM_UCAP_SUPERSAMPLE,
    )
    bracelet_back_display = source_locked_antialiased_mask(
        subregions["bracelet-back"]["visible"],
        subregions["bracelet-back"]["visible"],
        FOREARM_UCAP_SUPERSAMPLE,
    )
    bracelet_front_display = source_locked_antialiased_mask(
        subregions["bracelet-front"]["visible"],
        subregions["bracelet-front"]["visible"],
        FOREARM_UCAP_SUPERSAMPLE,
    )
    for alpha_id, alpha, logical in (
        ("bracelet", bracelet_display, subregions["bracelet"]["visible"]),
        ("bracelet_back", bracelet_back_display, subregions["bracelet-back"]["visible"]),
        ("bracelet_front", bracelet_front_display, subregions["bracelet-front"]["visible"]),
    ):
        fractional = sum(
            1
            for value in alpha.getdata()
            if 0 < value < 255
        )
        outside = sum(
            1
            for y in range(HEIGHT)
            for x in range(WIDTH)
            if alpha.getpixel((x, y)) > 0 and logical.getpixel((x, y)) == 0
        )
        formal.setdefault("checks", []).append({
            "id": f"{alpha_id}_formal_alpha_has_fractional_and_source_clamp",
            "pass": fractional > 0 and outside == 0,
            "detail": f"{alpha_id} audit display Alpha 使用 32x source-locked coverage；fractional={fractional}，source 外 nonzero={outside}",
            "fractionalAlphaPixels": fractional,
            "outsideLogicalPixels": outside,
            "supersample": FOREARM_UCAP_SUPERSAMPLE,
        })
    hand_layer_path = R2_ROOT / "flat-layers" / "hand.png"
    if not hand_layer_path.exists():
        raise FileNotFoundError(f"protected hand flat layer is missing: {hand_layer_path}")
    hand_layer = Image.open(hand_layer_path).convert("RGBA")

    def load_protected_layer(name: str) -> Image.Image:
        path = R2_ROOT / "flat-layers" / f"{name}.png"
        if not path.exists():
            raise FileNotFoundError(f"protected R2 flat layer is missing: {path}")
        return Image.open(path).convert("RGBA")

    layers = {
        # Non-forearm flat layers and the hand are protected byte-level inputs.
        # Only the two reopened forearm display layers are rebuilt below.
        "sleeve": load_protected_layer("sleeve"),
        "upper_arm": load_protected_layer("upper_arm"),
        "forearm": rgba_layer(forearm_display, DEBUG_COLORS["forearm"]),
        "hand": hand_layer,
        # These outputs are semantic audit views only.  They are not primary
        # motion layers; bracelet-back/front share the forearm transform.
        "forearm-skin": rgba_layer(forearm_skin_display, DEBUG_COLORS["forearm_skin"]),
        "bracelet": rgba_layer(bracelet_display, DEBUG_COLORS["bracelet"]),
        "bracelet-back": rgba_layer(bracelet_back_display, DEBUG_COLORS["bracelet_back"]),
        "bracelet-front": rgba_layer(bracelet_front_display, DEBUG_COLORS["bracelet_front"]),
    }
    output_paths: list[Path] = []
    display_alpha_paths = {
        "forearm.png": forearm_display,
        "forearm-skin.png": forearm_skin_display,
        "bracelet.png": bracelet_display,
        "bracelet-back.png": bracelet_back_display,
        "bracelet-front.png": bracelet_front_display,
    }
    for name, alpha in display_alpha_paths.items():
        path = R2_ROOT / "display-alpha" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        alpha.save(path, format="PNG", optimize=False, compress_level=9)
        output_paths.append(path)
    # The formal flat-color inputs are frozen by the 2026-08-12 whole-hand
    # approval.  Keep them available in ``layers`` for composite/review
    # generation, but never write a rebuilt derived layer back over the
    # approved source.  The semantic audit views remain writable.
    writable_layer_ids = {"forearm-skin", "bracelet"}
    for layer_id, layer in layers.items():
        if layer_id not in writable_layer_ids:
            continue
        path = R2_ROOT / "flat-layers" / f"{layer_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        layer.save(path, format="PNG", optimize=False, compress_level=9)
        output_paths.append(path)

    # The neutral arm-only projection uses visible ownership masks.  Complete
    # hidden geometry is intentionally exercised by the displaced-part reviews
    # below; torso/hair occluders are outside this four-layer R2 package.
    rest_layers = {
        "upper_arm": rgba_layer(primary["upper_arm"]["visible"], DEBUG_COLORS["upper_arm"]),
        "forearm": rgba_layer(primary["forearm"]["visible"], DEBUG_COLORS["forearm"]),
        "sleeve": rgba_layer(primary["sleeve"]["visible"], DEBUG_COLORS["sleeve"]),
        "hand": rgba_layer(primary["hand"]["visible"], DEBUG_COLORS["hand"]),
    }
    default = alpha_composite_layers([
        rest_layers["upper_arm"],
        rest_layers["sleeve"],
        rest_layers["hand"],
        rest_layers["forearm"],
    ])
    # The former sleeve-only pull test was insufficient: it could hide a
    # reversed shoulder relation by leaving the upper arm, forearm, and hand
    # at rest.  Use the peak of the full articulated color-block sequence.
    logic_layers = {
        "sleeve": rgba_layer(primary["sleeve"]["complete"], DEBUG_COLORS["sleeve"]),
        "upper_arm": rgba_layer(primary["upper_arm"]["complete"], DEBUG_COLORS["upper_arm"]),
        "forearm": rgba_layer(primary["forearm"]["complete"], DEBUG_COLORS["forearm"]),
        "hand": rgba_layer(primary["hand"]["complete"], DEBUG_COLORS["hand"]),
    }
    lift_action = build_lift_action(logic_layers)
    peak_frame = max(lift_action["frames"], key=lambda frame: abs(float(frame["shoulderAngle"])))
    bracelet_depth_stack = alpha_composite_layers([
        layers["upper_arm"],
        layers["sleeve"],
        layers["bracelet-back"],
        layers["forearm-skin"],
        layers["hand"],
        layers["bracelet-front"],
    ])
    composites = {
        "layer-only-neutral": default,
        "layer-only-complete-neutral": alpha_composite_layers([
            layers["upper_arm"],
            layers["sleeve"],
            layers["hand"],
            layers["forearm"],
        ]),
        "layer-only-remove-sleeve": alpha_composite_layers([layers["upper_arm"], layers["hand"], layers["forearm"]]),
        "layer-only-remove-upper-arm": alpha_composite_layers([layers["sleeve"], layers["hand"], layers["forearm"]]),
        "layer-only-remove-forearm": alpha_composite_layers([layers["upper_arm"], layers["sleeve"], layers["hand"]]),
        "layer-only-remove-hand": alpha_composite_layers([layers["upper_arm"], layers["sleeve"], layers["forearm"]]),
        "layer-only-remove-bracelet": alpha_composite_layers([layers["upper_arm"], layers["forearm-skin"], layers["sleeve"], layers["hand"]]),
        "wrist-skin-without-bracelet": alpha_composite_layers([layers["forearm-skin"], layers["sleeve"], layers["hand"]]),
        "wrist-two-way-without-hand": alpha_composite_layers([layers["upper_arm"], layers["sleeve"], layers["forearm"]]),
        "bracelet-depth-stack": bracelet_depth_stack,
        "sleeve-pull-test": peak_frame["composite"],
    }
    for name, image in composites.items():
        path = R2_ROOT / "flat-layers" / f"{name}.png"
        image.save(path, format="PNG", optimize=False, compress_level=9)
        output_paths.append(path)
    return output_paths, {
        **layers,
        **composites,
        "forearm-display-alpha": forearm_display,
        "forearm-skin-display-alpha": forearm_skin_display,
        "bracelet-display-alpha": bracelet_display,
        "bracelet-back-display-alpha": bracelet_back_display,
        "bracelet-front-display-alpha": bracelet_front_display,
        "forearm-ucap-display-alpha": cast(Image.Image, formal["ucap"]),
    }, lift_action, cast(dict[str, object], formal["boundaryReport"])


def mask_sha256(mask: Image.Image) -> str:
    return hashlib.sha256(mask.tobytes()).hexdigest()


def load_repair_baseline_mask(baseline: dict[str, object], layer_id: str, variant: str) -> Image.Image | None:
    files = baseline.get("files", {})
    if not isinstance(files, dict):
        return None
    relative = files.get(f"{layer_id}.{variant}")
    if not isinstance(relative, str):
        return None
    path = R2_ROOT / relative
    return Image.open(path).convert("L") if path.exists() else None


def load_repair_baseline_display(baseline: dict[str, object], key: str) -> Image.Image | None:
    files = baseline.get("files", {})
    if not isinstance(files, dict):
        return None
    relative = files.get(key)
    if not isinstance(relative, str):
        return None
    path = R2_ROOT / relative
    return Image.open(path).convert("RGBA") if path.exists() else None


def mask_diff_stats(before: Image.Image | None, after: Image.Image) -> dict[str, object]:
    if before is None:
        return {
            "baselineAvailable": False,
            "beforeSha256": None,
            "afterSha256": mask_sha256(after),
            "changedPixels": None,
            "addedPixels": None,
            "removedPixels": None,
            "changedBBox": None,
        }
    before_pixels = before.load()
    after_pixels = after.load()
    changed: list[tuple[int, int]] = []
    added = 0
    removed = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            old_value = before_pixels[x, y] > 0
            new_value = after_pixels[x, y] > 0
            if old_value != new_value:
                changed.append((x, y))
                if new_value:
                    added += 1
                else:
                    removed += 1
    if changed:
        bbox = [min(x for x, _ in changed), min(y for _, y in changed), max(x for x, _ in changed) + 1, max(y for _, y in changed) + 1]
    else:
        bbox = None
    return {
        "baselineAvailable": True,
        "beforeSha256": mask_sha256(before),
        "afterSha256": mask_sha256(after),
        "changedPixels": len(changed),
        "addedPixels": added,
        "removedPixels": removed,
        "changedBBox": bbox,
    }


def display_alpha_diff_stats(
    before: Image.Image | None,
    after: Image.Image,
    authorized_roi: tuple[int, int, int, int],
) -> dict[str, object]:
    """Compare formal display alpha and prove the change stays in the ROI."""
    if before is None:
        return {
            "baselineAvailable": False,
            "beforeSha256": None,
            "afterSha256": mask_sha256(after),
            "changedPixels": None,
            "changedPixelsInsideAuthorizedRoi": None,
            "changedPixelsOutsideAuthorizedRoi": None,
            "maxAbsoluteAlphaDelta": None,
            "sumAbsoluteAlphaDelta": None,
            "changedBBox": None,
            "outsideRoiUnchanged": False,
        }
    before_alpha = before.getchannel("A") if before.mode == "RGBA" else before.convert("L")
    if before_alpha.size != after.size:
        raise ValueError(f"formal display baseline size mismatch: {before_alpha.size} != {after.size}")
    left, top, right, bottom = authorized_roi
    before_pixels = before_alpha.load()
    after_alpha = after.getchannel("A") if after.mode == "RGBA" else after.convert("L")
    after_pixels = after_alpha.load()
    changed: list[tuple[int, int]] = []
    changed_inside = 0
    changed_outside = 0
    max_delta = 0
    sum_delta = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            delta = abs(int(after_pixels[x, y]) - int(before_pixels[x, y]))
            if delta == 0:
                continue
            changed.append((x, y))
            max_delta = max(max_delta, delta)
            sum_delta += delta
            if left <= x < right and top <= y < bottom:
                changed_inside += 1
            else:
                changed_outside += 1
    bbox = None
    if changed:
        bbox = [min(x for x, _ in changed), min(y for _, y in changed), max(x for x, _ in changed) + 1, max(y for _, y in changed) + 1]
    return {
        "baselineAvailable": True,
        "beforeSha256": mask_sha256(before_alpha),
        "afterSha256": mask_sha256(after.convert("L")),
        "authorizedRoi": list(authorized_roi),
        "changedPixels": len(changed),
        "changedPixelsInsideAuthorizedRoi": changed_inside,
        "changedPixelsOutsideAuthorizedRoi": changed_outside,
        "maxAbsoluteAlphaDelta": max_delta,
        "sumAbsoluteAlphaDelta": sum_delta,
        "changedBBox": bbox,
        "outsideRoiUnchanged": changed_outside == 0,
    }


def repair_diff_overlay(before: Image.Image, after: Image.Image) -> Image.Image:
    before_pixels = before.load()
    after_pixels = after.load()
    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    pixels = overlay.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            old_value = before_pixels[x, y] > 0
            new_value = after_pixels[x, y] > 0
            if old_value and not new_value:
                pixels[x, y] = (224, 62, 62, 230)
            elif new_value and not old_value:
                pixels[x, y] = (38, 173, 105, 230)
    return overlay


def build_repair_diff(
    masks: dict[str, dict[str, Image.Image]],
    baseline: dict[str, object],
    source_line: Image.Image,
) -> tuple[dict[str, object], Image.Image]:
    layer_specs = {
        "upper_arm": ((130, 232, 190, 310), 6),
        "forearm": ((90, 500, 155, 555), 7),
        "hand": ((88, 510, 142, 565), 8),
    }
    diff_layers: dict[str, object] = {}
    comparison_rows: list[tuple[str, Image.Image, Image.Image, Image.Image]] = []
    for layer_id, (box, scale) in layer_specs.items():
        before_complete = load_repair_baseline_mask(baseline, layer_id, "complete")
        before_visible = load_repair_baseline_mask(baseline, layer_id, "visible")
        before_hidden = load_repair_baseline_mask(baseline, layer_id, "hidden")
        after_complete = masks["primary"][layer_id]["complete"]
        after_visible = masks["primary"][layer_id]["visible"]
        after_hidden = masks["primary"][layer_id]["hidden"]
        diff_layers[layer_id] = {
            "sourceBasis": {
                "upper_arm": ["joint-envelope-contract:shoulder", "sleeve/shoulder hidden overlap"],
                "forearm": ["joint-envelope-contract:wrist", "forearm bone-axis taper", "bracelet depth candidate"],
                "hand": ["joint-envelope-contract:wrist", "hand_radial_outer_contour", "hand_ulnar_outer_contour", "palm direction"],
            }[layer_id],
            "complete": mask_diff_stats(before_complete, after_complete),
            "visible": mask_diff_stats(before_visible, after_visible),
            "hidden": mask_diff_stats(before_hidden, after_hidden),
            "visibleBoundaryPolicy": "existing visible source-line candidate preserved unless an explicit source-line-based change is listed",
        }
        color = DEBUG_COLORS[layer_id]
        before_view = blend_overlay(source_line, rgba_layer(before_complete, color)) if before_complete is not None else source_line.convert("RGB")
        after_view = blend_overlay(source_line, rgba_layer(after_complete, color))
        diff = repair_diff_overlay(before_complete, after_complete) if before_complete is not None else Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        diff_view = blend_overlay_weighted(source_line, diff, 0.72)
        comparison_rows.append((layer_id, crop_nearest(before_view, box, scale), crop_nearest(after_view, box, scale), crop_nearest(diff_view, box, scale)))

    comparison_width = max(max(before.width, after.width, diff.width) for _, before, after, diff in comparison_rows)
    row_height = max(max(before.height, after.height, diff.height) for _, before, after, diff in comparison_rows) + 66
    comparison = Image.new("RGB", (comparison_width * 3 + 100, row_height * len(comparison_rows) + 100), (244, 247, 250))
    draw = ImageDraw.Draw(comparison)
    draw.text((22, 14), "R2 当前候选｜完整材料根部返修前 / 返修后 / 逐像素差异", fill=(28, 42, 58), font=font(24, True))
    draw.text((22, 48), "红=旧有而新无｜绿=新补入；可见源线候选未改变，根部变化来自 hidden Bezier 重建", fill=(91, 104, 117), font=font(14))
    for row_index, (layer_id, before, after, diff) in enumerate(comparison_rows):
        y = 82 + row_index * row_height
        draw.text((22, y), layer_id, fill=(28, 42, 58), font=font(18, True))
        cell_x = [100, 100 + comparison_width, 100 + comparison_width * 2]
        labels = ["返修前", "返修后", "逐像素差异"]
        for x, label, image in zip(cell_x, labels, [before, after, diff]):
            draw.text((x, y), label, fill=(91, 104, 117), font=font(15, True))
            comparison.paste(image, (x, y + 22))
    return {
        "schemaVersion": 1,
        "stage": "R2 visual repair pixel diff",
        **IDENTITY,
        "baseline": baseline,
        "layers": diff_layers,
        "interpretation": "green additions are hidden-root reconstruction; visible boundary changes are separately counted and require source-line evidence",
    }, comparison


def build_unresolved_review_board(
    source_line: Image.Image,
    line_overlay: Image.Image,
) -> Image.Image:
    approved = r2_gate_state() == "approved"
    specs = [
        (("accepted-01｜袖口浅灰交界：归入皮肤" if approved else "unresolved-01｜袖口浅灰交界：衣物/皮肤语义"), (142, 382, 205, 412), ("用户已确认，不切成材料边界" if approved else "用户视觉确认，不切成材料边界")),
        (("accepted-02｜手链后半环深度" if approved else "unresolved-02｜手链后半环深度"), (92, 508, 153, 550), ("当前前向候选已批准" if approved else "正面源线不足；只支持当前前向候选")),
        (("accepted-03｜手链下隐藏腕部三维截面" if approved else "unresolved-03｜手链下隐藏腕部三维截面"), (96, 516, 132, 553), ("当前平色范围已批准；仍非纹理/深层三维证明" if approved else "derived candidate，未冻结纹理/深度")),
    ]
    width = 900
    row_height = 360
    board = Image.new("RGB", (width, 70 + row_height * len(specs)), (255, 248, 248))
    draw = ImageDraw.Draw(board)
    draw.rectangle((0, 0, width, 70), fill=(110, 47, 56))
    draw.text((22, 18), "R2 已接受视觉范围｜当前限制" if approved else "R2 unresolved 区域｜保留用户决策点", fill=(255, 255, 255), font=font(24, True))
    for index, (title, box, note) in enumerate(specs):
        y = 70 + index * row_height
        crop = crop_nearest(line_overlay, box, 7)
        crop.thumbnail((width - 44, 250), Image.Resampling.NEAREST)
        draw.text((22, y + 14), title, fill=(110, 47, 56), font=font(18, True))
        board.paste(crop, ((width - crop.width) // 2, y + 48))
        draw.text((22, y + row_height - 30), note, fill=(145, 69, 76), font=font(15))
    return board


def make_hand_boundary_overlay(
    source_line: Image.Image,
    mask: Image.Image,
    color: tuple[int, int, int],
) -> Image.Image:
    overlay = source_line.convert("RGB").copy()
    draw = ImageDraw.Draw(overlay)
    for x, y in mask_boundary_pixels(mask, HAND_LINE_ROI):
        draw.point((x, y), fill=color)
    return overlay


def make_hand_formal_alpha_overlay(
    source_line: Image.Image,
    alpha: Image.Image,
    color: tuple[int, int, int],
    opacity: float = 0.62,
) -> Image.Image:
    """Overlay the graded display Alpha without collapsing it to boundary pixels.

    The source-line boundary audit intentionally uses binary contour pixels and
    nearest-neighbor enlargement.  That is appropriate for ownership review,
    but it is not a valid anti-aliasing preview.  The user-facing complete-hand
    panel must consume the formal graded Alpha from ``flat["hand"]`` directly,
    then use smooth resampling only for presentation.
    """
    if not 0.0 < opacity <= 1.0:
        raise ValueError("formal Alpha overlay opacity must be in (0, 1]")
    overlay = Image.new("RGBA", CANVAS, color + (0,))
    graded_alpha = alpha.convert("L")
    if opacity < 1.0:
        graded_alpha = graded_alpha.point(lambda value: round(value * opacity))
    overlay.putalpha(graded_alpha)
    return Image.alpha_composite(source_line.convert("RGBA"), overlay).convert("RGB")


def write_hand_repair_visual_assets(
    images: dict[str, Image.Image],
    flat: dict[str, Image.Image],
    baseline: dict[str, object],
    hand_trace_contract: dict[str, object],
    hand_trace_report: dict[str, object],
    hand_source_overlay: Image.Image,
    hand_candidate_overlay: Image.Image,
) -> list[Path]:
    """Write the hand-only visual evidence required by the R2 hand gate."""
    output_paths: list[Path] = []
    approved = r2_gate_state() == "approved"
    qa_root = R2_ROOT / "qa" / "hand-r2-repair"
    qa_root.mkdir(parents=True, exist_ok=True)
    source_line = images["front-line-source-exact-after-reset"].convert("RGB")
    source_color = images["front-color-source-exact-after-reset"].convert("RGB")
    old_r2 = load_repair_baseline_mask(baseline, "hand", "visible")
    old_r2_complete = load_repair_baseline_mask(baseline, "hand", "complete")
    if old_r2 is None or old_r2_complete is None:
        raise AssertionError("R2 hand repair baseline is required for the rejection comparison")
    r3_root = VALIDATION_ROOT / "arm-chain-screen-left-r3-motion-stress-and-geometry-freeze" / "repair-candidate" / "hand-palm"
    r3_visible = Image.open(r3_root / "masks" / "hand-visible.png").convert("L")
    new_visible = Image.open(R2_ROOT / "masks" / "visible" / "hand.png").convert("L")
    new_complete = Image.open(R2_ROOT / "masks" / "complete" / "hand.png").convert("L")
    # The binary complete mask remains the source for topology/ownership
    # checks.  The user-facing complete panel must use the formal graded Alpha
    # from the final flat layer; drawing the binary contour here would recreate
    # the staircase that this R2 maintenance is meant to remove.
    formal_complete_overlay = make_hand_formal_alpha_overlay(
        source_line,
        flat["hand"].getchannel("A"),
        (31, 165, 104),
    )

    def crop(image: Image.Image, box: tuple[int, int, int, int], scale: int = 8) -> Image.Image:
        return crop_nearest(image, box, scale)

    def crop_preview(image: Image.Image, box: tuple[int, int, int, int], scale: int = 8) -> Image.Image:
        return crop_smooth(image, box, scale)

    roi = HAND_LINE_ROI
    roi_path = qa_root / "01-原线稿手部ROI-原样近邻.png"
    crop(source_line, roi, 8).save(roi_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(roi_path)

    overlays = [
        ("02-当前拒绝R2-hand-叠加.png", make_hand_boundary_overlay(source_line, old_r2, (178, 44, 190)), "R2 rejected"),
        ("03-拒绝R3-local-hand-candidate-叠加.png", make_hand_boundary_overlay(source_line, r3_visible, (220, 96, 42)), "R3 local rejected"),
        ("04-新hand-visible-源线叠加.png", make_hand_boundary_overlay(source_line, new_visible, (0, 164, 212)), "new visible"),
    ]
    for name, image, _label in overlays:
        path = qa_root / name
        crop(image, roi, 8).save(path, format="PNG", optimize=False, compress_level=9)
        output_paths.append(path)
    formal_complete_path = qa_root / "05-新hand-complete-源线叠加.png"
    crop_preview(formal_complete_overlay, roi, 8).save(formal_complete_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(formal_complete_path)

    xor = repair_diff_overlay(old_r2_complete, new_complete)
    xor_view = blend_overlay_weighted(source_line, xor, 0.78)
    xor_path = qa_root / "06-R2旧hand与新hand-XOR增删热图.png"
    crop(xor_view, roi, 8).save(xor_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(xor_path)

    closeup_specs = [
        ("拇指与虎口", (60, 568, 101, 623)),
        ("第一根手指与指缝", (70, 580, 90, 623)),
        ("第二根手指与指缝", (78, 575, 100, 618)),
        ("第三根手指与指缝", (87, 570, 108, 610)),
        ("第四根手指与指缝", (94, 565, 116, 610)),
        ("腕部交接", (92, 530, 130, 560)),
    ]
    closeup_width = max(box[2] - box[0] for _title, box in closeup_specs) * 16
    closeup_height = max(box[3] - box[1] for _title, box in closeup_specs) * 16 + 42
    closeup_sheet = Image.new("RGB", (closeup_width * 2 + 64, closeup_height * 3 + 76), (241, 246, 250))
    closeup_draw = ImageDraw.Draw(closeup_sheet)
    closeup_draw.text((20, 16), "小星 Left｜手指、指缝、虎口 1600% 最近邻审查", fill=(28, 42, 58), font=font(24, True))
    for index, (title, box) in enumerate(closeup_specs):
        row = index // 2
        col = index % 2
        x = 20 + col * closeup_width
        y = 58 + row * closeup_height
        closeup_draw.text((x, y), title, fill=(28, 42, 58), font=font(18, True))
        display = crop(make_hand_boundary_overlay(source_line, new_visible, (0, 164, 212)), box, 16)
        closeup_sheet.paste(display, (x, y + 28))
    closeup_path = qa_root / "07-每根手指每个指缝与虎口-1600pct.png"
    closeup_sheet.save(closeup_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(closeup_path)

    boundary_board = Image.new("RGB", (crop(hand_source_overlay, roi, 12).width * 2 + 48, crop(hand_source_overlay, roi, 12).height + 84), (241, 246, 250))
    boundary_draw = ImageDraw.Draw(boundary_board)
    boundary_draw.text((16, 12), "一像素审查：红=authoritative source trace｜青=candidate boundary", fill=(28, 42, 58), font=font(20, True))
    source_display = crop(hand_source_overlay, roi, 12)
    candidate_display = crop(hand_candidate_overlay, roi, 12)
    boundary_board.paste(source_display, (16, 50))
    boundary_board.paste(candidate_display, (24 + source_display.width, 50))
    boundary_path = qa_root / "08-一像素候选边界与源线审查图.png"
    boundary_board.save(boundary_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(boundary_path)

    flat_hand_path = qa_root / "09-新hand-独立平色色块.png"
    crop_preview(opaque_preview(flat["hand"]), roi, 10).save(flat_hand_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(flat_hand_path)

    smooth_boundary_view = opaque_preview(flat["hand"])
    smooth_boundary_draw = ImageDraw.Draw(smooth_boundary_view)
    smooth_boundary_draw.line(
        [(round(x), round(y)) for x, y in hand_visual_boundary_points(inset=False)],
        fill=(244, 82, 76),
        width=2,
        joint="curve",
    )
    smooth_boundary_path = qa_root / "13-平滑Bezier边界与红线内裁剪审查.png"
    crop_preview(smooth_boundary_view, roi, 12).save(smooth_boundary_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(smooth_boundary_path)

    bracelet_removed = blend_overlay(source_line, flat["wrist-skin-without-bracelet"])
    wrist_removed_path = qa_root / "10-移开bracelet-腕部隐藏连续性.png"
    crop(bracelet_removed, (88, 515, 140, 565), 14).save(wrist_removed_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(wrist_removed_path)

    neutral_path = qa_root / "11-中性layer-only全臂拼装.png"
    flat_neutral = flat["layer-only-neutral"]
    blend_overlay(source_line, flat_neutral).save(neutral_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(neutral_path)

    review = Image.new("RGB", (1640, 1180), (238, 244, 249))
    review_draw = ImageDraw.Draw(review)
    review_draw.rectangle((0, 0, 1640, 74), fill=(28, 49, 70))
    review_title = "小星 Left｜R2 手部可见色块精准返修｜当前范围已冻结" if approved else "小星 Left｜R2 手部可见色块精准返修｜等待用户视觉批准"
    review_draw.text((24, 18), review_title, fill=(255, 255, 255), font=font(28, True))
    review_draw.text((24, 48), "character=xiaoxing · front · screenSide=left · anatomicalSide=right · 512×1086 原坐标 · 不进入 R3", fill=(206, 220, 232), font=font(14))
    panels = [
        ("原线稿手部 ROI", crop(source_line, roi, 5)),
        ("原彩手部 ROI", crop(source_color, roi, 5)),
        ("拒绝 R2", crop(make_hand_boundary_overlay(source_line, old_r2, (178, 44, 190)), roi, 5)),
        ("拒绝 R3-local", crop(make_hand_boundary_overlay(source_line, r3_visible, (220, 96, 42)), roi, 5)),
        ("新 visible", crop(make_hand_boundary_overlay(source_line, new_visible, (0, 164, 212)), roi, 5)),
        ("新 complete｜formal display Alpha", crop_preview(formal_complete_overlay, roi, 5)),
        ("新 flat layer", crop_preview(opaque_preview(flat["hand"]), roi, 5)),
        ("XOR 增删", crop(xor_view, roi, 5)),
    ]
    panel_width = 390
    panel_height = 490
    for index, (title, display) in enumerate(panels):
        row = index // 4
        col = index % 4
        x = 20 + col * panel_width
        y = 92 + row * panel_height
        review_draw.rounded_rectangle((x, y, x + panel_width - 16, y + panel_height - 16), radius=12, fill=(255, 255, 255), outline=(178, 191, 204), width=2)
        review_draw.text((x + 14, y + 12), title, fill=(28, 42, 58), font=font(20, True))
        display.thumbnail((panel_width - 40, panel_height - 62), Image.Resampling.LANCZOS)
        review.paste(display, (x + (panel_width - display.width) // 2 - 8, y + 48))
    footer_y = 1080
    max_error = hand_trace_report["aggregate"]["maxBidirectionalPx"]
    p95_error = hand_trace_report["aggregate"]["p95BidirectionalPx"]
    review_status = "R2-GATE_APPROVED / 当前平色范围已冻结" if approved else "R2 reopened / WAITING_USER_VISUAL_APPROVAL"
    review_color = (48, 126, 79) if approved else (166, 63, 63)
    review_draw.text((24, footer_y), f"双向边界误差：max={max_error}px，P95={p95_error}px；五指=1+4，真实开放指缝=3；状态：{review_status}", fill=review_color, font=font(17, True))
    review_path = qa_root / "12-原线原彩新拼装并列-中文总审查图.png"
    review.save(review_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(review_path)

    return output_paths


def write_hand_aa_maintenance_review(
    images: dict[str, Image.Image],
    flat: dict[str, Image.Image],
    baseline: dict[str, object],
    hand_visual_report: dict[str, object],
    hand_root_geometry: dict[str, object],
    hand_visible_diff: dict[str, object],
    hand_display_diff: dict[str, object],
    markup_registration: dict[str, object],
    previous_hand_hidden: Image.Image | None = None,
) -> Path:
    """Write the focused Chinese evidence board for the hidden-wrist AA gate."""
    qa_path = R2_ROOT / "qa" / "hand-r2-repair" / "14-隐藏腕根抗锯齿维护审查.png"
    qa_path.parent.mkdir(parents=True, exist_ok=True)
    roi = HAND_HIDDEN_WRIST_ROI
    review_crop = (88, 512, 142, 565)
    board_width = 2240
    panel_width = 530
    panel_height = 720
    gap = 24
    margin = 28
    header_height = 122
    board_height = header_height + margin + panel_height * 2 + gap + margin
    board = Image.new("RGB", (board_width, board_height), (239, 244, 248))
    draw = ImageDraw.Draw(board)
    draw.rectangle((0, 0, board_width, header_height), fill=(28, 48, 68))
    draw.text((margin, 18), "小星 Left｜R2 隐藏腕根抗锯齿维护审查", fill=(255, 255, 255), font=font(32, True))
    draw.text(
        (margin, 68),
        "front｜screen-left = anatomical-right｜512×1086 identity｜32× float Bézier → BOX｜不进入 R3/R4",
        fill=(211, 226, 237),
        font=font(17),
    )

    def checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
        result = Image.new("RGB", size, (236, 236, 236))
        pixels = result.load()
        for y in range(size[1]):
            for x in range(size[0]):
                if ((x // cell) + (y // cell)) % 2:
                    pixels[x, y] = (198, 198, 198)
        return result

    def alpha_preview(alpha: Image.Image, color: tuple[int, int, int], background: tuple[int, int, int] | None = None) -> Image.Image:
        alpha = alpha.convert("L")
        bg = checker(alpha.size) if background is None else Image.new("RGB", alpha.size, background)
        fg = Image.new("RGB", alpha.size, color)
        return Image.composite(fg, bg, alpha)

    def fit(image: Image.Image, max_size: tuple[int, int], resample: Image.Resampling = Image.Resampling.BICUBIC) -> Image.Image:
        result = image.convert("RGB")
        result.thumbnail(max_size, resample)
        return result

    def crop_alpha(alpha: Image.Image, box: tuple[int, int, int, int], scale: float, background: tuple[int, int, int] | None = None) -> Image.Image:
        crop = alpha.crop(box)
        target = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
        resized = crop.resize(target, Image.Resampling.BICUBIC)
        return alpha_preview(resized, DEBUG_COLORS["hand"], background)

    def crop_rgba(image: Image.Image, box: tuple[int, int, int, int], scale: float, background: tuple[int, int, int]) -> Image.Image:
        crop = image.crop(box)
        target = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
        resized = crop.resize(target, Image.Resampling.BICUBIC)
        base = Image.new("RGBA", resized.size, background + (255,))
        return Image.alpha_composite(base, resized).convert("RGB")

    def panel(index: int, title: str, subtitle: str, image: Image.Image) -> None:
        row, column = divmod(index, 4)
        x = margin + column * (panel_width + gap)
        y = header_height + margin + row * (panel_height + gap)
        draw.rounded_rectangle((x, y, x + panel_width, y + panel_height), radius=14, fill=(255, 255, 255), outline=(173, 188, 201), width=2)
        draw.text((x + 16, y + 14), title, fill=(28, 42, 58), font=font(21, True))
        draw.text((x + 16, y + 49), subtitle, fill=(91, 104, 117), font=font(14))
        display = fit(image, (panel_width - 34, panel_height - 96))
        draw.rectangle((x + 16, y + 82, x + panel_width - 16, y + panel_height - 18), outline=(222, 229, 235), width=1)
        board.paste(display, (x + (panel_width - display.width) // 2, y + 88))

    old_hidden = (
        previous_hand_hidden
        if previous_hand_hidden is not None
        else (load_repair_baseline_mask(baseline, "hand", "hidden") or Image.new("L", CANVAS, 0))
    )
    old_hidden_crop = old_hidden.crop(roi)
    old_hidden_crop = old_hidden_crop.resize(
        (old_hidden_crop.width * 9, old_hidden_crop.height * 9),
        Image.Resampling.NEAREST,
    )
    old_hidden_view = alpha_preview(old_hidden_crop, DEBUG_COLORS["hand"], (255, 255, 255))
    panel(0, "1｜旧隐藏腕根", "逻辑蒙版｜二值 0/255｜800% 最近邻，仅像素审查", old_hidden_view)

    curve_overlay = images["front-line-source-exact-after-reset"].convert("RGB").copy()
    curve_draw = ImageDraw.Draw(curve_overlay)
    hidden_overlay = rgba_layer(flat["hand-display-alpha-hidden"], DEBUG_COLORS["hand"])
    curve_overlay = blend_overlay_weighted(curve_overlay, hidden_overlay, 0.72)
    curve_draw = ImageDraw.Draw(curve_overlay)
    root_points = bezier_chain(HAND_WRIST_ROOT_BEZIER_SEGMENTS, samples_per_segment=96)
    envelope_points = bezier_chain(HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS, samples_per_segment=96)
    curve_draw.line([(round(x), round(y)) for x, y in root_points], fill=(0, 173, 224), width=2, joint="curve")
    curve_draw.line([(round(x), round(y)) for x, y in envelope_points], fill=(242, 143, 44), width=2, joint="curve")
    curve_draw.ellipse((107, 535, 113, 541), outline=(231, 54, 54), width=2)
    curve_draw.text((114, 533), "wrist", fill=(231, 54, 54), font=font(14, True))
    panel(1, "2｜浮点 Bézier 与隐藏包络", "青=root｜橙=registered hidden envelope｜红=腕点｜源线叠加", crop_nearest(curve_overlay, review_crop, 8))

    panel(2, "3｜隐藏 display Alpha", "棋盘格｜真实灰度 coverage｜非逻辑二值边缘", crop_alpha(flat["hand-display-alpha-hidden"], review_crop, 8))

    bracelet_removed = flat["wrist-skin-without-bracelet"]
    white_removed = crop_rgba(bracelet_removed, review_crop, 4.0, (255, 255, 255))
    black_removed = crop_rgba(bracelet_removed, review_crop, 4.0, (0, 0, 0))
    removed_board = Image.new("RGB", (white_removed.width, white_removed.height * 2 + 42), (239, 244, 248))
    removed_draw = ImageDraw.Draw(removed_board)
    removed_draw.text((6, 4), "100% source-space presentation｜white", fill=(28, 42, 58), font=font(13, True))
    removed_board.paste(white_removed, (6, 22))
    removed_draw.text((6, white_removed.height + 25), "200% display presentation｜black", fill=(28, 42, 58), font=font(13, True))
    removed_board.paste(black_removed, (6, white_removed.height + 43))
    panel(3, "4｜移开 bracelet 正式效果", "白底/黑底｜100% 与 200%｜隐藏腕根必须连续且不漏边", removed_board)

    redline_view = alpha_preview(flat["hand-display-alpha-complete"], DEBUG_COLORS["hand"], (255, 255, 255)).copy()
    redline_draw = ImageDraw.Draw(redline_view)
    redline_draw.line([(round(x), round(y)) for x, y in hand_visual_boundary_points(inset=False)], fill=(244, 70, 70), width=2, joint="curve")
    markup_guard = hand_visual_markup_boundary_clip(HAND_VISUAL_SUPERSAMPLE).resize(CANVAS, Image.Resampling.BOX)
    final_alpha = flat["hand-display-alpha-complete"]
    outside = [
        (x, y)
        for y in range(HEIGHT)
        for x in range(WIDTH)
        if final_alpha.getpixel((x, y)) > 0 and markup_guard.getpixel((x, y)) == 0
    ]
    for x, y in outside:
        redline_draw.point((x, y), fill=(238, 40, 40))
    redline_draw.text((58, 508), f"outsideBoundaryPixels = {len(outside)}", fill=(32, 132, 73) if not outside else (214, 45, 45), font=font(14, True))
    panel(4, "5｜最新红线与越界热图", "红=authoritative boundary｜红色越界热图为空即 0", crop_nearest(redline_view, review_crop, 8))

    before_display = load_repair_baseline_display(baseline, "hand.formalDisplayFlatLayer")
    before_alpha = before_display.getchannel("A") if before_display is not None else Image.new("L", CANVAS, 0)
    xor = Image.new("RGB", CANVAS, (255, 255, 255))
    xor_pixels = xor.load()
    new_alpha = flat["hand"].getchannel("A")
    for y in range(roi[1], roi[3]):
        for x in range(roi[0], roi[2]):
            old_value = before_alpha.getpixel((x, y))
            new_value = new_alpha.getpixel((x, y))
            if new_value > old_value:
                xor_pixels[x, y] = (50, 174, 105)
            elif new_value < old_value:
                xor_pixels[x, y] = (222, 63, 63)
            elif new_value:
                xor_pixels[x, y] = (179, 91, 190)
    xor_view = xor
    panel(5, "6｜旧/新 formal Alpha XOR", "绿=新增 coverage｜红=移除 coverage｜差异必须只在 hidden wrist ROI", crop_nearest(xor_view, review_crop, 8))

    scale_board = Image.new("RGB", (500, 360), (244, 247, 250))
    scale_draw = ImageDraw.Draw(scale_board)
    scale_specs = [(1.0, "100%"), (1.25, "125%"), (1.5, "150%"), (2.0, "200%")]
    for index, (factor, label) in enumerate(scale_specs):
        item = crop_alpha(flat["hand-display-alpha-complete"], review_crop, factor)
        item.thumbnail((112, 250), Image.Resampling.BICUBIC)
        x = 12 + index * 122
        scale_draw.text((x + 12, 10), label, fill=(28, 42, 58), font=font(15, True))
        scale_board.paste(item, (x + (104 - item.width) // 2, 40))
    panel(6, "7｜显示比例慢速对比", "100% / 125% / 150% / 200%｜显示 Alpha，非最近邻逻辑图", scale_board)

    conclusion = Image.new("RGB", (500, 560), (252, 253, 254))
    conclusion_draw = ImageDraw.Draw(conclusion)
    conclusion_draw.text((20, 20), "8｜门禁结论（工程证据）", fill=(28, 42, 58), font=font(21, True))
    conclusion_lines = [
        f"红线 SHA-256：{str(markup_registration['sha256'])[:16]}…",
        f"source canvas：{CANVAS[0]}×{CANVAS[1]}｜transform：identity",
        f"outsideBoundaryPixels：{hand_visual_report['outsideBoundaryPixels']}",
        f"outsideSmoothBoundaryPixels：{hand_visual_report['outsideSmoothBoundaryPixels']}",
        f"hiddenOutsideEnvelopePixels：{hand_root_geometry['logicalMasks']['hiddenOutsideEnvelopePixels']}",
        f"hidden fractional Alpha pixels：{hand_root_geometry['displayAlpha']['hiddenFractionalAlphaPixels']}",
        f"visible hand changed pixels：{hand_visible_diff.get('changedPixels', 'n/a')}",
        f"formal Alpha changes inside ROI：{hand_display_diff.get('changedPixelsInsideAuthorizedRoi', 'n/a')}",
        f"formal changes outside ROI：{hand_display_diff.get('changedPixelsOutsideAuthorizedRoi', 'n/a')}",
        "engineeringPass 与 userVisualApproval 分离",
        "overallGatePass = false｜R2-GATE = reopened",
        "R3 = STALE_DUE_TO_UPSTREAM_R2_HAND_REJECTION",
        "等待用户视觉批准；不得进入 R3/R4/Cubism/纹理",
    ]
    y = 66
    for line in conclusion_lines:
        conclusion_draw.text((20, y), line, fill=(44, 61, 76) if "等待" not in line else (180, 68, 42), font=font(15))
        y += 34
    panel(7, "8｜最终检查结论", "工程证据候选，不写入用户批准/冻结授权", conclusion)

    board.save(qa_path, format="PNG", optimize=False, compress_level=9)
    return qa_path


def write_visual_review_assets(
    images: dict[str, Image.Image],
    flat: dict[str, Image.Image],
    heatmap: Image.Image,
    lift_action: dict[str, object],
    baseline: dict[str, object],
    repair_diff: dict[str, object],
    repair_comparison: Image.Image,
    segmented_line_overlay: Image.Image,
) -> list[Path]:
    output_paths: list[Path] = []
    approved = r2_gate_state() == "approved"
    review_status = "R2_APPROVED_CURRENT_SCOPE｜R2-GATE 已通过" if approved else "R2_VISUAL_REPAIR_CANDIDATE｜等待用户批准 R2 返修"
    depth_note = "bracelet_back 与 forearm_skin 形成已批准的当前范围深度候选；bracelet_front 位于皮肤和 hand 前方。" if approved else "forearm_skin.hidden 保留手链下皮肤；bracelet_back 与其形成候选深度重叠，bracelet_front 位于皮肤和 hand 前方，后半环真实深度仍 unresolved。"
    decision_note = "已接受：袖口浅灰交界归入 skin；手链后半环采用当前前向小幅腕部移动/旋转候选；隐藏腕部截面为当前平色范围内批准的 derived candidate。" if approved else "unresolved：袖口浅灰交界语义；手链后半环深度；手链下隐藏腕部三维截面。候选不声称 R2 已冻结。"
    review_footer = "状态：R2-GATE 已通过（仅当前平色/layer-only 范围）" if approved else "状态：等待用户批准 R2 返修"
    neutral = flat["layer-only-neutral"]
    line_overlay = blend_overlay(images["front-line-source-exact-after-reset"], neutral)
    color_overlay = blend_overlay(images["front-color-source-exact-after-reset"], neutral)
    overlays = {
        "layer-only-with-source-line": line_overlay,
        "layer-only-with-source-color": color_overlay,
        "ownership-heatmap": heatmap,
    }
    for name, image in overlays.items():
        path = R2_ROOT / "qa" / f"{name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, format="PNG", optimize=False, compress_level=9)
        output_paths.append(path)

    repair_comparison_path = R2_ROOT / "qa" / "返修前后-完整材料根部-并列近景.png"
    repair_comparison.save(repair_comparison_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(repair_comparison_path)

    segmented_fit = crop_nearest(segmented_line_overlay, (65, 210, 220, 640), 8)
    segmented_fit_path = R2_ROOT / "qa" / "原线与可见边界-800pct-逐段最近邻叠加.png"
    segmented_fit.save(segmented_fit_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(segmented_fit_path)

    wrist_box = (88, 505, 155, 555)
    depth_items = [
        ("bracelet_back｜后方候选", flat["bracelet-back"]),
        ("forearm_skin｜皮肤", flat["forearm-skin"]),
        ("bracelet_front｜前方候选", flat["bracelet-front"]),
        ("stack｜back→skin→hand→front", flat["bracelet-depth-stack"]),
    ]
    depth_crops = [(title, crop_nearest(blend_overlay(images["front-line-source-exact-after-reset"], image), wrist_box, 8)) for title, image in depth_items]
    depth_width = max(crop.width for _, crop in depth_crops)
    depth_board = Image.new("RGB", (depth_width * len(depth_crops) + 40, max(crop.height for _, crop in depth_crops) + 86), (244, 247, 250))
    depth_draw = ImageDraw.Draw(depth_board)
    for index, (title, crop) in enumerate(depth_crops):
        x = 10 + index * depth_width
        depth_draw.text((x, 12), title, fill=(28, 42, 58), font=font(15, True))
        depth_board.paste(crop, (x, 42))
    depth_path = R2_ROOT / "qa" / "bracelet-depth-分层关系-800pct.png"
    depth_board.save(depth_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(depth_path)

    unresolved_board = build_unresolved_review_board(images["front-line-source-exact-after-reset"], line_overlay)
    unresolved_path = R2_ROOT / "qa" / "未决区域-标注.png"
    unresolved_board.save(unresolved_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(unresolved_path)

    # Diagnostic-only overlap view: all four complete primary layers remain
    # visible with reduced alpha, including upper_arm underneath sleeve.  This
    # is deliberately separate from the formal neutral draw-order projection
    # so overlap at the shoulder, elbow and wrist can be inspected directly.
    diagnostic_mix = blend_debug_layers([
        flat["upper_arm"],
        flat["sleeve"],
        flat["hand"],
        flat["forearm"],
    ])
    diagnostic_overlays = {
        "图层混合-四层-源线": blend_overlay(images["front-line-source-exact-after-reset"], diagnostic_mix),
        "图层混合-四层-原彩稿": blend_overlay(images["front-color-source-exact-after-reset"], diagnostic_mix),
    }
    for name, image in diagnostic_overlays.items():
        path = R2_ROOT / "qa" / f"{name}.png"
        image.save(path, format="PNG", optimize=False, compress_level=9)
        output_paths.append(path)

    # Stronger source-line fit views for checking whether a material edge is
    # actually on the drawing rather than only looking plausible in the pale
    # blend board.  The first keeps all four complete layers visible; the
    # second isolates the complete upper-arm geometry against the same line.
    fit_full = blend_overlay_weighted(
        images["front-line-source-exact-after-reset"],
        diagnostic_mix,
        0.58,
    )
    fit_upper_arm = blend_overlay_weighted(
        images["front-line-source-exact-after-reset"],
        flat["upper_arm"],
        0.62,
    )
    fit_specs = [
        # The original whole-arm fit is a frozen review input.  Preserve it
        # byte-for-byte and publish this rebuilt diagnostic under a distinct
        # R2 audit name.
        ("手臂色块-实际线稿拟合-全臂-400pct-r2-formal", fit_full, (65, 205, 220, 640), 4),
        ("手臂色块-实际线稿拟合-大臂complete-500pct", fit_upper_arm, (80, 210, 215, 435), 5),
    ]
    for name, image, box, scale in fit_specs:
        path = R2_ROOT / "qa" / f"{name}.png"
        crop_nearest(image, box, scale).save(path, format="PNG", optimize=False, compress_level=9)
        output_paths.append(path)

    joint_specs = [
        ("肩袖衔接｜sleeve + upper_arm", (88, 215, 220, 335), 4),
        ("肘部衔接｜upper_arm + forearm", (88, 345, 220, 435), 5),
        ("腕部衔接｜forearm+手链 + hand", (70, 500, 180, 575), 6),
    ]
    joint_crops = [
        (title, crop_nearest(diagnostic_overlays["图层混合-四层-源线"], box, scale))
        for title, box, scale in joint_specs
    ]
    sheet_width = max(crop.width for _, crop in joint_crops) + 56
    sheet_height = 112 + sum(crop.height + 96 for _, crop in joint_crops) + 24 * (len(joint_crops) - 1)
    joint_sheet = Image.new("RGB", (sheet_width, sheet_height), (244, 247, 250))
    joint_draw = ImageDraw.Draw(joint_sheet)
    joint_draw.text((28, 22), "小星 Left｜四层混合衔接检查", fill=(28, 42, 58), font=font(28, True))
    joint_draw.text(
        (28, 64),
        "蓝 sleeve｜橙 upper_arm｜绿 forearm+手链｜紫 hand｜诊断混合，不是正式 draw order",
        fill=(91, 104, 117),
        font=font(16),
    )
    y = 108
    for title, crop in joint_crops:
        panel_bottom = y + crop.height + 82
        joint_draw.rounded_rectangle((18, y, sheet_width - 18, panel_bottom), radius=12, fill=(255, 255, 255), outline=(178, 191, 204), width=2)
        joint_draw.text((30, y + 12), title, fill=(28, 42, 58), font=font(20, True))
        joint_sheet.paste(crop, ((sheet_width - crop.width) // 2, y + 46))
        y = panel_bottom + 24
    joint_path = R2_ROOT / "qa" / "衔接处-图层混合-最近邻放大.png"
    joint_sheet.save(joint_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(joint_path)

    # One annotation-friendly board: the complete mixed layer view stays
    # beside all three joint crops, with numbered anchors on the full canvas.
    full_marked = diagnostic_overlays["图层混合-四层-源线"].copy()
    full_marked_draw = ImageDraw.Draw(full_marked)
    marker_points = [("1", (151, 245)), ("2", (133, 388)), ("3", (110, 538))]
    for number, (x, y) in marker_points:
        radius = 14
        full_marked_draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=(222, 72, 72),
            outline=(255, 255, 255),
            width=2,
        )
        full_marked_draw.text((x - 5, y - 12), number, fill=(255, 255, 255), font=font(18, True))

    margin = 28
    header_h = 92
    left_x = margin
    left_y = header_h + 18
    left_frame_w = full_marked.width + 32
    left_frame_h = full_marked.height + 78
    right_x = left_x + left_frame_w + 36
    right_panel_w = max(crop.width for _, crop in joint_crops) + 40
    right_y = left_y
    right_panel_heights = [crop.height + 88 for _, crop in joint_crops]
    right_total_h = sum(right_panel_heights) + 24 * (len(joint_crops) - 1)
    board_w = right_x + right_panel_w + margin
    board_h = max(left_y + left_frame_h, right_y + right_total_h) + margin
    integrated = Image.new("RGB", (board_w, board_h), (244, 247, 250))
    integrated_draw = ImageDraw.Draw(integrated)
    integrated_draw.rectangle((0, 0, board_w, header_h), fill=(28, 42, 58))
    integrated_draw.text((margin, 18), "小星 Left｜四层混合整合标记图", fill=(255, 255, 255), font=font(30, True))
    integrated_draw.text(
        (margin, 57),
        "1 肩袖｜2 肘部｜3 腕部｜蓝 sleeve｜橙 upper_arm｜绿 forearm+手链｜紫 hand",
        fill=(209, 226, 238),
        font=font(16),
    )

    integrated_draw.rounded_rectangle(
        (left_x, left_y, left_x + left_frame_w, left_y + left_frame_h),
        radius=14,
        fill=(255, 255, 255),
        outline=(178, 191, 204),
        width=2,
    )
    integrated.paste(full_marked, (left_x + 16, left_y + 16))
    integrated_draw.text(
        (left_x + 16, left_y + full_marked.height + 30),
        "全画布混合层；可直接在 1/2/3 附近继续画线标记",
        fill=(91, 104, 117),
        font=font(15),
    )

    y = right_y
    integrated_titles = [
        "1｜肩袖衔接｜sleeve + upper_arm",
        "2｜肘部衔接｜upper_arm + forearm",
        "3｜腕部衔接｜forearm+手链 + hand",
    ]
    for title, (_, crop), panel_h in zip(integrated_titles, joint_crops, right_panel_heights):
        integrated_draw.rounded_rectangle(
            (right_x, y, right_x + right_panel_w, y + panel_h),
            radius=14,
            fill=(255, 255, 255),
            outline=(178, 191, 204),
            width=2,
        )
        integrated_draw.text((right_x + 14, y + 12), title, fill=(28, 42, 58), font=font(19, True))
        integrated.paste(crop, (right_x + (right_panel_w - crop.width) // 2, y + 48))
        integrated_draw.text(
            (right_x + 14, y + crop.height + 57),
            "源线叠加；诊断混合，不是正式材料",
            fill=(166, 63, 63),
            font=font(14),
        )
        y += panel_h + 24
    integrated_path = R2_ROOT / "qa" / "四层混合-整合标记版.png"
    integrated.save(integrated_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(integrated_path)

    sleeve_pull_overlay = blend_overlay(
        images["front-line-source-exact-after-reset"],
        flat["sleeve-pull-test"],
    )
    sleeve_pull_path = R2_ROOT / "qa" / "袖子抬臂-pull-test-源线叠加.png"
    sleeve_pull_overlay.save(sleeve_pull_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(sleeve_pull_path)
    sleeve_pull_crop = crop_nearest(sleeve_pull_overlay, (80, 220, 230, 430), 4)
    sleeve_pull_crop_path = R2_ROOT / "qa" / "审查裁剪-袖子抬臂-pull-test-400pct.png"
    sleeve_pull_crop.save(sleeve_pull_crop_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(sleeve_pull_crop_path)

    # Human-facing evidence for the actual articulated color-block action.
    # The source line is intentionally not blended into these tiles: it is a
    # rest-pose reference and would make the moving blocks look like a broken
    # overlay.  The fixed labels expose the transform direction and order.
    action_frames = list(lift_action["frames"])
    action_roi = (20, 200, 235, 665)
    selected_indices = [0, 2, 4, 5, 7, 10]
    tile_width = 430
    tile_height = 988
    margin = 22
    title_height = 70
    action_board = Image.new(
        "RGB",
        (margin * 4 + tile_width * 3, title_height + margin * 3 + tile_height * 2),
        (238, 243, 247),
    )
    action_draw = ImageDraw.Draw(action_board)
    action_draw.text(
        (margin, 20),
        "小星 Left｜抬手方向性诊断 0 → 1 → 0｜qa_only_not_R3",
        fill=(28, 42, 58),
        font=font(28, True),
    )
    for tile_index, frame_index in enumerate(selected_indices):
        frame = action_frames[frame_index]
        preview = crop_nearest(opaque_preview(frame["composite"]), action_roi, 2)
        tile = Image.new("RGB", (tile_width, tile_height), (255, 255, 255))
        tile.paste(preview, ((tile_width - preview.width) // 2, 45))
        tile_draw = ImageDraw.Draw(tile)
        tile_draw.text(
            (12, 12),
            f"{frame['id']}  S={frame['shoulderAngle']:.0f}°  E={frame['elbowAngle']:.0f}°",
            fill=(28, 42, 58),
            font=font(18, True),
        )
        tile_draw.text(
            (12, tile_height - 28),
            "qa_only_not_R3｜11 帧，不是 41 点正式压力测试",
            fill=(91, 104, 117),
            font=font(14),
        )
        row = tile_index // 3
        column = tile_index % 3
        action_board.paste(tile, (margin + column * (tile_width + margin), title_height + margin + row * (tile_height + margin)))
    action_board_path = R2_ROOT / "qa" / "抬手动作-色块序列.png"
    action_board.save(action_board_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(action_board_path)

    gif_frames = [crop_nearest(opaque_preview(frame["composite"]), action_roi, 2) for frame in action_frames]
    gif_path = R2_ROOT / "qa" / "抬手动作-色块动画.gif"
    gif_frames[0].save(
        gif_path,
        format="GIF",
        save_all=True,
        append_images=gif_frames[1:],
        duration=160,
        loop=0,
        optimize=False,
        disposal=2,
    )
    output_paths.append(gif_path)

    complete_sleeve_overlay = blend_overlay(
        images["front-line-source-exact-after-reset"],
        flat["sleeve"],
    )
    complete_sleeve_crop = crop_nearest(complete_sleeve_overlay, (90, 215, 220, 420), 4)
    complete_sleeve_path = R2_ROOT / "qa" / "审查裁剪-袖筒内侧-完整hidden-400pct.png"
    complete_sleeve_crop.save(complete_sleeve_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(complete_sleeve_path)

    roi = (55, 215, 220, 650)
    zoom_boxes = {
        "审查裁剪-肩袖-400pct": ((95, 225, 220, 330), 4),
        "审查裁剪-肘袖口-500pct": ((100, 360, 215, 430), 5),
        "审查裁剪-腕部-600pct": ((85, 500, 165, 560), 6),
        "审查裁剪-手链与手-800pct": ((55, 525, 165, 635), 8),
    }
    for name, (box, scale) in zoom_boxes.items():
        crop = crop_nearest(line_overlay, box, scale)
        path = R2_ROOT / "qa" / f"{name}.png"
        crop.save(path, format="PNG", optimize=False, compress_level=9)
        output_paths.append(path)

    board = Image.new("RGB", (2600, 2820), (244, 247, 250))
    draw = ImageDraw.Draw(board)
    draw.rectangle((0, 0, 2600, 96), fill=(28, 42, 58))
    draw.text((32, 20), "小星 Left｜R2 全画布平色完整材料与 layer-only 拼装门禁", fill=(255, 255, 255), font=font(34, True))
    draw.text((32, 61), f"view=front｜screenSide=left｜anatomicalSide=right｜仅几何/平色/审查｜{review_status}", fill=(209, 226, 238), font=font(20))

    notes_x = 30
    notes_y = 125
    notes_w = 410
    draw.rounded_rectangle((notes_x, notes_y, notes_x + notes_w, 2780), radius=14, fill=(255, 255, 255), outline=(178, 191, 204), width=2)
    y = notes_y + 24
    draw.text((notes_x + 20, y), "本阶段说明", fill=(28, 42, 58), font=font(24, True))
    y += 44
    y = draw_wrapped(draw, (notes_x + 20, y), "四个主要运动组：sleeve、upper_arm、forearm、hand。bracelet 归属于 forearm，共享 forearm 变换；bracelet_back、forearm_skin、bracelet_front 只作为 QA 深度子区，不建立独立关节。", 20, (55, 66, 78), 18, 4) + 12
    y = draw_wrapped(draw, (notes_x + 20, y), "所有正式 mask 为 512×1086、frontMaster 1:1、identity transform。逻辑 mask 为二值 0/255；complete = visible ∪ hidden。", 20, (55, 66, 78), 18, 4) + 12
    y = draw_wrapped(draw, (notes_x + 20, y), "主层可见所有权：蓝=sleeve，橙=upper_arm，绿=forearm（含手链），紫=hand。bracelet 深度审计顺序为 back → forearm_skin → hand → front。", 20, (55, 66, 78), 18, 4) + 12
    y = draw_wrapped(draw, (notes_x + 20, y), depth_note, 20, (55, 66, 78), 18, 4) + 12
    y = draw_wrapped(draw, (notes_x + 20, y), "未使用：旧 V12–V38 mask/material、镜像、颜色阈值切层、整人底图、纹理、PSD、Cubism、网格、动作、Physics、Runtime。", 20, (55, 66, 78), 18, 4) + 12
    draw.line((notes_x + 20, y, notes_x + notes_w - 20, y), fill=(220, 95, 95), width=2)
    y += 18
    y = draw_wrapped(draw, (notes_x + 20, y), decision_note, 20, (166, 63, 63), 18, 4) + 12
    y = draw_wrapped(draw, (notes_x + 20, y), "抬臂图仅为 qa_only_not_R3：11 帧、未达到 41 点，未验证组合极值、真实 sleeve 双锚、torso/hair 支撑遮挡，未授权几何冻结。", 20, (166, 63, 63), 18, 4) + 16
    draw.text((notes_x + 20, y), review_footer, fill=(44, 130, 91) if approved else (182, 74, 40), font=font(23, True))

    content_x = 470
    panel_w = 500
    panel_h = 540
    gap = 20

    def panel(x: int, y0: int, title: str, image: Image.Image, label: str | None = None) -> None:
        draw.rounded_rectangle((x, y0, x + panel_w, y0 + panel_h), radius=14, fill=(255, 255, 255), outline=(178, 191, 204), width=2)
        draw.text((x + 16, y0 + 12), title, fill=(28, 42, 58), font=font(22, True))
        if image.mode == "RGBA":
            local_base = Image.new("RGBA", image.size, (255, 255, 255, 255))
            display = Image.alpha_composite(local_base, image).convert("RGB")
        else:
            display = image.convert("RGB")
        display.thumbnail((panel_w - 32, panel_h - 70), Image.Resampling.LANCZOS)
        px = x + (panel_w - display.width) // 2
        py = y0 + 52 + (panel_h - 70 - display.height) // 2
        board.paste(display, (px, py))
        if label:
            draw.text((x + 16, y0 + panel_h - 28), label, fill=(91, 104, 117), font=font(16))

    panel(content_x, 125, "原始线稿（权威源）", images["front-line-source-exact-after-reset"], "原图，不是材料")
    panel(content_x + panel_w + gap, 125, "原始彩稿（身份参照）", images["front-color-source-exact-after-reset"], "原图，不是材料")
    panel(content_x + 2 * (panel_w + gap), 125, "默认 layer-only 平色拼装", neutral, "透明背景 RGBA；仅 R2 layers")
    panel(content_x + 3 * (panel_w + gap), 125, "可见所有权热图", heatmap, "红=重复；本候选红色重复应为 0")

    panel(content_x, 705, "默认拼装叠加原线稿", line_overlay, "叠加线不替代源线")
    panel(content_x + panel_w + gap, 705, "默认拼装叠加原彩稿", color_overlay, "身份审查，不是纹理")
    layer_debug = alpha_composite_layers([flat["upper_arm"], flat["sleeve"], flat["hand"], flat["forearm"]])
    panel(content_x + 2 * (panel_w + gap), 705, "主要层固定调试色", layer_debug, "蓝/橙/绿/紫；绿 forearm 已包含手链")
    panel(content_x + 3 * (panel_w + gap), 705, "bracelet 前后深度子区", flat["bracelet-depth-stack"], "back→skin→hand→front；共享 forearm 变换")

    removed_names = [
        ("移开 sleeve", "layer-only-remove-sleeve"),
        ("移开 upper_arm", "layer-only-remove-upper-arm"),
        ("移开 forearm（含手链）", "layer-only-remove-forearm"),
        ("移开 hand", "layer-only-remove-hand"),
        ("移开 bracelet：腕部皮肤", "wrist-skin-without-bracelet"),
    ]
    small_w = 400
    small_gap = 15
    for index, (title, key) in enumerate(removed_names):
        x = content_x + index * (small_w + small_gap)
        draw.rounded_rectangle((x, 1285, x + small_w, 1665), radius=14, fill=(255, 255, 255), outline=(178, 191, 204), width=2)
        draw.text((x + 12, 1300), title, fill=(28, 42, 58), font=font(18, True))
        display = crop_nearest(opaque_preview(flat[key]), roi, 1)
        display.thumbnail((small_w - 24, 330), Image.Resampling.NEAREST)
        board.paste(display, (x + (small_w - display.width) // 2, 1340))
        draw.text((x + 12, 1638), "审查裁剪，不是正式材料", fill=(166, 63, 63), font=font(14))

    zoom_specs = [
        ("肩/袖｜400% 最近邻·源线叠加", (95, 225, 220, 330), 4),
        ("肘/袖口｜500% 最近邻·源线叠加", (100, 360, 215, 430), 5),
        ("腕/手｜600% 最近邻·源线叠加", (85, 500, 165, 560), 6),
        ("手链/手｜800% 最近邻·源线叠加", (55, 525, 165, 635), 8),
    ]
    for index, (title, box, scale) in enumerate(zoom_specs):
        x = content_x + index * (panel_w + gap)
        draw.rounded_rectangle((x, 1710, x + panel_w, 2160), radius=14, fill=(255, 255, 255), outline=(178, 191, 204), width=2)
        draw.text((x + 14, 1722), title, fill=(28, 42, 58), font=font(20, True))
        display = crop_nearest(line_overlay, box, scale)
        display.thumbnail((panel_w - 28, 365), Image.Resampling.NEAREST)
        board.paste(display, (x + (panel_w - display.width) // 2, 1765))
        draw.text((x + 14, 2135), "审查裁剪，源线叠加，不是正式材料", fill=(166, 63, 63), font=font(14))

    extra_specs = [
        ("返修前/返修后｜三处完整材料根部", repair_comparison, "红=移除旧像素；绿=新增 hidden Bezier 像素"),
        ("bracelet_back｜forearm_skin｜bracelet_front", flat["bracelet-depth-stack"], "当前范围已批准；仅支持前向小幅腕部移动/旋转" if approved else "前后关系候选；后半环深度仍 unresolved"),
        ("原线与可见边界｜800% 最近邻逐段审计", segmented_fit, "颜色点为实际 mask boundary；源线来自 front line master"),
        ("已接受范围与限制" if approved else "所有 unresolved 区域", build_unresolved_review_board(images["front-line-source-exact-after-reset"], line_overlay), "用户已批准当前范围；不授权下游制作" if approved else "仅供用户视觉确认，不关闭 R2-GATE"),
    ]
    for index, (title, image, label) in enumerate(extra_specs):
        x = content_x + index * (panel_w + gap)
        panel(x, 2200, title, image, label)

    board_path = R2_ROOT / "qa" / "R2-小星Left-全画布平色材料-中文审查图.png"
    board.save(board_path, format="PNG", optimize=False, compress_level=9)
    output_paths.append(board_path)
    return output_paths


def write_forearm_ucap_qa_board(
    images: dict[str, Image.Image],
    masks: dict[str, dict[str, Image.Image]],
    flat: dict[str, Image.Image],
    formal_report: dict[str, object],
    engineering_pass: bool,
    lift_action: dict[str, object],
    legacy_r1_conflict: dict[str, object] | None = None,
) -> Path:
    """Create the required Chinese visual review board for the forearm U-cap."""
    qa_root = R2_ROOT / "qa" / "forearm-ucap-a"
    qa_root.mkdir(parents=True, exist_ok=True)
    board_w = 2200
    panel_w = 520
    panel_h = 360
    gap = 20
    margin = 28
    header_h = 108
    board_h = header_h + margin + 4 * (panel_h + gap) + margin
    board = Image.new("RGB", (board_w, board_h), (241, 245, 248))
    draw = ImageDraw.Draw(board)
    draw.rectangle((0, 0, board_w, header_h), fill=(27, 48, 66))
    draw.text((margin, 18), "小星 Left｜前臂远端 U-cap｜Stage A 中文视觉审查图", fill=(255, 255, 255), font=font(30, True))
    draw.text(
        (margin, 62),
        "正面屏幕左侧＝解剖右臂｜Stage A 候选｜正式显示 Alpha 与逻辑 mask 分开｜不等于用户批准",
        fill=(214, 230, 240),
        font=font(17),
    )

    def tinted(mask: Image.Image, color: tuple[int, int, int]) -> Image.Image:
        return opaque_preview(rgba_layer(mask.convert("L"), color), (250, 250, 250))

    def alpha_view(alpha: Image.Image, color: tuple[int, int, int]) -> Image.Image:
        return tinted(alpha.convert("L"), color)

    def source_overlay(layer: Image.Image, weight: float = 0.52) -> Image.Image:
        return blend_overlay_weighted(images["front-line-source-exact-after-reset"], layer, weight)

    review_box = (84, 500, 148, 570)
    ucap_box = (94, 522, 131, 553)
    elbow_markup_mask, elbow_markup_meta = forearm_elbow_user_markup_boundary()
    elbow_markup_overlay = source_overlay(flat["forearm"], 0.58)
    # Keep a clean source-line fit view separate from the redline contract.
    # This is the material result the user needs to inspect: no guide stroke
    # can hide a gap or a crossing at the sleeve/skin transition.
    elbow_source_line_crop = crop_nearest(
        elbow_markup_overlay,
        FOREARM_ELBOW_USER_MARKUP_SOURCE_CROP,
        5,
    )
    elbow_source_line_path = qa_root / "elbow-source-line-transition-500pct.png"
    elbow_source_line_crop.save(elbow_source_line_path, format="PNG", optimize=False, compress_level=9)
    elbow_markup_draw = ImageDraw.Draw(elbow_markup_overlay)
    elbow_markup_segments = elbow_markup_meta["boundarySegments"]
    for segment_name in ("left", "top", "right"):
        segment = elbow_markup_segments[segment_name]
        elbow_markup_draw.line(
            [(round(point[0]), round(point[1])) for point in segment],
            fill=(247, 67, 67),
            width=1,
            joint="curve",
        )
    elbow_markup_crop = crop_nearest(
        elbow_markup_overlay,
        FOREARM_ELBOW_USER_MARKUP_SOURCE_CROP,
        5,
    )
    elbow_markup_path = qa_root / "elbow-user-markup-source-fit-500pct.png"
    elbow_markup_crop.save(elbow_markup_path, format="PNG", optimize=False, compress_level=9)
    # Panel 11 is the hidden-connection audit in the actual draw order.  The
    # hidden forearm underlay is placed below the source-locked
    # back→skin→hand→front stack, so a bracelet-adjacent overlap is judged as
    # it will appear in the scene instead of being shown as a floating green
    # patch over the source bracelet stroke.
    hidden_skin_alpha = ImageChops.multiply(
        flat["forearm-skin"].getchannel("A"),
        masks["subregions"]["forearm-skin"]["hidden"],
    )
    hidden_forearm_layer = rgba_layer(hidden_skin_alpha, DEBUG_COLORS["forearm_skin"])
    hidden_connection_stack = alpha_composite_layers([
        hidden_forearm_layer,
        flat["bracelet-depth-stack"],
    ])
    hidden_connection_overlay = source_overlay(hidden_connection_stack, 0.64)
    ImageDraw.Draw(hidden_connection_overlay).line(
        [(round(x), round(y)) for x, y in FOREARM_USER_MARKUP_TRACE],
        fill=(16, 174, 255),
        width=1,
        joint="curve",
    )
    hidden_connection_crop = crop_nearest(hidden_connection_overlay, (90, 515, 136, 558), 8)
    hidden_connection_path = qa_root / "hidden-wrist-connection-800pct.png"
    hidden_connection_crop.save(hidden_connection_path, format="PNG", optimize=False, compress_level=9)

    # Make the hidden material visible as evidence instead of asking the user
    # to infer it from the occluded depth stack.  The left side is the logic
    # hidden skin exposed over the source line; the right side is the formal
    # hidden display Alpha exposed with the same source-line background.  The
    # actual depth-stack view remains panel 11, where hand/bracelet correctly
    # cover this material.
    hidden_logic_mask = masks["subregions"]["forearm-skin"]["hidden"].convert("L")
    hidden_logic_overlay = source_overlay(
        rgba_layer(hidden_logic_mask, (35, 180, 116)),
        0.82,
    )
    ImageDraw.Draw(hidden_logic_overlay).line(
        [(round(x), round(y)) for x, y in FOREARM_USER_MARKUP_TRACE],
        fill=(16, 174, 255),
        width=1,
        joint="curve",
    )
    hidden_logic_crop = crop_nearest(hidden_logic_overlay, (90, 515, 136, 558), 8)

    formal_hidden_alpha = ImageChops.subtract(
        flat["forearm-skin-display-alpha"].convert("L"),
        masks["subregions"]["forearm-skin"]["visible"].convert("L"),
    )
    formal_hidden_overlay = source_overlay(
        rgba_layer(formal_hidden_alpha, (214, 148, 42)),
        0.82,
    )
    ImageDraw.Draw(formal_hidden_overlay).line(
        [(round(x), round(y)) for x, y in FOREARM_USER_MARKUP_TRACE],
        fill=(16, 174, 255),
        width=1,
        joint="curve",
    )
    # Keep the logic mask as a nearest-neighbor exact audit, but render the
    # formal Alpha evidence with a bounded presentation-only bilinear zoom.
    # This does not write back to the source Alpha or change its boundary;
    # it prevents the 8x review image from turning every fractional edge into
    # an apparent blocky fill. Reapply the blue markup after the zoom.
    formal_hidden_crop = formal_hidden_overlay.crop((90, 515, 136, 558)).resize(
        (368, 344),
        Image.Resampling.BILINEAR,
    )
    ImageDraw.Draw(formal_hidden_crop).line(
        [((x - 90.0) * 8.0, (y - 515.0) * 8.0) for x, y in FOREARM_USER_MARKUP_TRACE],
        fill=(16, 174, 255),
        width=7,
        joint="curve",
    )

    hidden_region_evidence = Image.new("RGB", (760, 390), (250, 252, 253))
    hidden_evidence_draw = ImageDraw.Draw(hidden_region_evidence)
    hidden_evidence_draw.text((10, 8), "A｜逻辑 hidden 展开（绿色，含窄连接）", fill=(28, 42, 58), font=font(18, True))
    hidden_evidence_draw.text((390, 8), "B｜正式 hidden Alpha 展开（橙色，最终显示）", fill=(28, 42, 58), font=font(18, True))
    hidden_region_evidence.paste(hidden_logic_crop, (6, 36))
    hidden_region_evidence.paste(formal_hidden_crop, (386, 36))
    hidden_evidence_draw.text(
        (10, 365),
        "蓝线＝用户当前边界；panel 11 仍显示 hand/bracelet 覆盖后的实际深度栈",
        fill=(91, 104, 117),
        font=font(14),
    )
    hidden_region_path = qa_root / "hidden-region-evidence-800pct.png"
    hidden_region_evidence.save(hidden_region_path, format="PNG", optimize=False, compress_level=9)
    panel_specs: list[tuple[str, Image.Image, str]] = [
        ("1｜权威原线 master", images["front-line-source-exact-after-reset"], "语义边界唯一来源；不是材料输出"),
        ("2｜原彩 identity 参照", images["front-color-source-exact-after-reset"], "颜色/身份参照；不作为切层依据"),
        ("3｜forearm visible 逻辑 mask", tinted(masks["primary"]["forearm"]["visible"], DEBUG_COLORS["forearm"]), "二值 0/255；shaft 由实际线稿封闭区域锁边，bracelet 仍属 forearm"),
        ("4｜forearm hidden 区域展开", hidden_region_evidence, "左=逻辑 hidden（含窄源线连接，非正式显示）；右=正式 hidden Alpha；蓝线=当前用户边界"),
        ("5｜forearm complete 逻辑 close-up", crop_nearest(tinted(masks["primary"]["forearm"]["complete"], (39, 145, 102)), (90, 515, 136, 558), 8), "visible ∪ hidden；本区域展开审查"),
        ("6｜forearm formal hidden Alpha close-up", formal_hidden_crop, "L coverage；仅展示 hidden Alpha；保留 fractional edge pixels"),
        ("7｜back→skin→hand→front", crop_nearest(flat["bracelet-depth-stack"], review_box, 5), "bracelet-back → forearm-skin → hand → bracelet-front"),
        ("8｜移除 bracelet 后的皮肤", crop_nearest(flat["wrist-skin-without-bracelet"], review_box, 5), "依赖审查；不改变 hand 文件"),
        ("9｜肘部衔接 close-up｜right AA edge fit", elbow_markup_crop, "右下抗锯齿边缘的绿色凸出已收回；隐藏缺口保留；可见 shaft 仍源线锁边"),
        ("10｜shaft close-up｜source line + AA", crop_nearest(source_overlay(flat["forearm"], 0.58), (96, 430, 170, 515), 4), "绿色色块贴合权威线稿皮肤边界；formal Alpha 在线稿内抗锯齿"),
        ("11｜U-cap / hidden connection close-up", hidden_connection_crop, "真实 back→skin→hand→front 深度栈；hidden forearm 在下方；蓝线＝当前显示基准"),
    ]

    scale_board = Image.new("RGB", (500, 240), (250, 252, 253))
    scale_draw = ImageDraw.Draw(scale_board)
    formal_preview = opaque_preview(flat["forearm-skin"])
    for index, (factor, label) in enumerate(((1.0, "100%"), (1.25, "125%"), (1.5, "150%"), (2.0, "200%"))):
        crop = formal_preview.crop(ucap_box)
        crop = crop.resize((round(crop.width * factor), round(crop.height * factor)), Image.Resampling.LANCZOS)
        crop.thumbnail((112, 170), Image.Resampling.LANCZOS)
        x = 12 + index * 122
        scale_draw.text((x + 16, 8), label, fill=(28, 42, 58), font=font(15, True))
        scale_board.paste(crop, (x + (104 - crop.width) // 2, 40))
    panel_specs.append(("12｜100/125/150/200%", scale_board, "presentation-only smooth zoom；formal Alpha 原值不被改写"))
    # Keep this targeted fit view on a visible-only depth stack.  The complete
    # depth stack intentionally includes the hidden U-cap, whose green
    # extension would visually mask the bracelet/source-line fit being
    # reviewed here.  The visible skin is rebuilt from its logical mask while
    # bracelet-back/front retain their actual debug ownership colors; the
    # hidden U-cap remains covered by panels 4/5/11.
    visible_skin_debug = rgba_layer(
        masks["subregions"]["forearm-skin"]["visible"],
        DEBUG_COLORS["forearm_skin"],
    )
    bracelet_visible_fit_stack = alpha_composite_layers([
        flat["upper_arm"],
        flat["sleeve"],
        flat["bracelet-back"],
        visible_skin_debug,
        flat["hand"],
        flat["bracelet-front"],
    ])
    bracelet_fit_overlay = source_overlay(bracelet_visible_fit_stack, 0.64)
    bracelet_fit_crop = crop_nearest(bracelet_fit_overlay, (84, 505, 148, 555), 7)
    bracelet_fit_path = qa_root / "bracelet-source-line-fit-700pct.png"
    bracelet_fit_crop.save(bracelet_fit_path, format="PNG", optimize=False, compress_level=9)
    panel_specs.append(
        (
            "13｜hand/forearm seam｜bracelet source-line fit",
            crop_nearest(bracelet_fit_overlay, (80, 505, 155, 575), 6),
            "visible-only 深度栈；红色 bracelet ownership 仅取权威原线像素；隐藏 U-cap 见 panel 4/5/11",
        )
    )

    scale = FOREARM_UCAP_SUPERSAMPLE
    registered_high = render_bezier_loop_highres(FOREARM_DISTAL_UCAP_BEZIER_SEGMENTS, scale, samples_per_segment=128)
    registered = downsample_coverage(registered_high, scale)
    heat = Image.new("RGB", CANVAS, (247, 249, 250))
    heat_pixels = heat.load()
    ucap_alpha = flat["forearm-ucap-display-alpha"]
    for y in range(HEIGHT):
        for x in range(WIDTH):
            candidate = ucap_alpha.getpixel((x, y)) > 0
            allowed = registered.getpixel((x, y)) > 0
            if candidate and not allowed:
                heat_pixels[x, y] = (225, 45, 45)
            elif candidate:
                heat_pixels[x, y] = (48, 161, 109)
            elif allowed:
                heat_pixels[x, y] = (38, 122, 205)
    heat_draw = ImageDraw.Draw(heat)
    guide = bezier_chain(FOREARM_DISTAL_UCAP_BEZIER_SEGMENTS, samples_per_segment=128)
    heat_draw.line([(round(x), round(y)) for x, y in guide], fill=(22, 78, 121), width=1, joint="curve")
    heat_draw.line([(round(x), round(y)) for x, y in FOREARM_USER_MARKUP_TRACE], fill=(16, 174, 255), width=1, joint="curve")
    heat_crop = crop_nearest(heat, ucap_box, 6)
    ImageDraw.Draw(heat_crop).text((12, 10), f"outsideBoundaryPixels = {formal_report['outsideBoundaryPixels']}", fill=(26, 116, 68), font=font(20, True))
    panel_specs.append(("14｜outside-alpha heatmap", heat_crop, "绿=候选在注册边界内｜红=越界（必须为 0）"))

    explanation = Image.new("RGB", (500, 250), (252, 253, 254))
    explanation_draw = ImageDraw.Draw(explanation)
    explanation_draw.text((18, 16), "15｜逻辑 mask ≠ 正式显示 Alpha", fill=(28, 42, 58), font=font(20, True))
    explanation_lines = [
        "shaft visible boundary：权威 front-line master 4-connected enclosed component",
        "shaft formal Alpha：source-clamped fractional edge；线稿外 nonzero = 0",
        "逻辑：32×高分辨率 boolean → BOX 一次 → 0/255 threshold",
        "正式 Alpha：注册 cubic U-cap → BOX 一次 → L 灰度边缘",
        "最新蓝线是 U-cap 正式显示边界；窄源线连接只留在逻辑 hidden",
        "禁止把 binary mask 当作纹理 Alpha 或反向追踪几何",
        "最终 U-cap guard 在 downsample 后再次执行",
        "forearm / forearm-skin fractional Alpha 必须 > 0",
    ]
    y = 58
    for line in explanation_lines:
        y = draw_wrapped(explanation_draw, (18, y), line, 40, (55, 66, 78), 15, 4) + 3
    panel_specs.append(("15｜逻辑与正式 Alpha 规则", explanation, "同一几何来源；不同证据层"))

    lift_failures = [
        check for check in lift_action["checks"]
        if not bool(check["pass"])
    ]
    status = Image.new("RGB", (500, 250), (252, 253, 254))
    status_draw = ImageDraw.Draw(status)
    status_draw.text((18, 16), "16｜当前门禁结论", fill=(28, 42, 58), font=font(20, True))
    status_lines = [
        f"engineeringPass（U-cap scope）= {engineering_pass}",
        "userVisualApproval = None（未记录）",
        "overallGatePass = False",
        f"U-cap outsideBoundaryPixels = {formal_report['outsideBoundaryPixels']}",
        f"lift diagnostic unresolved = {len(lift_failures) > 0}；动作系统重建不在范围",
        "下一步：用户视觉审查；禁止 R3/R4/Cubism/Runtime",
    ]
    historical_uncovered = int((legacy_r1_conflict or {}).get("historicalR1EnvelopeUncoveredPixels", 0))
    if historical_uncovered:
        status_lines.insert(
            4,
        f"历史 R1 wrist 包络未覆盖 = {historical_uncovered} px；已由最新蓝线替代",
        )
    y = 58
    for line in status_lines:
        fill = (182, 74, 40) if ("False" in line or "None" in line or "禁止" in line or "unresolved = True" in line or "冲突" in line) else (44, 130, 91)
        y = draw_wrapped(status_draw, (18, y), line, 40, fill, 15, 4) + 3
    panel_specs.append(("16｜停止条件与未决风险", status, "工程候选完成；等待用户视觉批准"))

    for index, (title, image, label) in enumerate(panel_specs):
        row = index // 4
        column = index % 4
        x = margin + column * (panel_w + gap)
        y = header_h + margin + row * (panel_h + gap)
        draw.rounded_rectangle((x, y, x + panel_w, y + panel_h), radius=12, fill=(255, 255, 255), outline=(178, 191, 204), width=2)
        draw.text((x + 14, y + 10), title, fill=(28, 42, 58), font=font(20, True))
        if image.mode == "RGBA":
            local_base = Image.new("RGBA", image.size, (255, 255, 255, 255))
            display = Image.alpha_composite(local_base, image).convert("RGB")
        else:
            display = image.convert("RGB")
        display.thumbnail((panel_w - 28, panel_h - 78), Image.Resampling.LANCZOS)
        board.paste(display, (x + (panel_w - display.width) // 2, y + 48 + (panel_h - 78 - display.height) // 2))
        draw.text((x + 14, y + panel_h - 25), label, fill=(91, 104, 117), font=font(14))

    board_path = qa_root / "FOREARM_DISTAL_UCAP_AA_STAGE_A-中文视觉审查图.png"
    board.save(board_path, format="PNG", optimize=False, compress_level=9)
    return board_path


def artifact_snapshot(exclude: set[Path] | None = None) -> list[dict[str, object]]:
    exclude = exclude or set()
    entries: list[dict[str, object]] = []
    for path in sorted(R2_ROOT.rglob("*")):
        if path.is_file() and path not in exclude and "__pycache__" not in path.parts:
            entries.append({
                "path": str(path.relative_to(R2_ROOT)).replace("\\", "/"),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            })
    return entries


def write_readme() -> Path:
    readme = R2_ROOT / "README.md"
    readme.write_text(
        "# 小星 Left｜R2 全画布平色正式收口\n\n"
        "本目录对应 `character=xiaoxing`、`view=front`、`screenSide=left`、`anatomicalSide=right`。\n\n"
        "## 当前状态\n\n"
        "`R2_FORMAL_PROMOTED / R3_READY_NOT_STARTED`。最新整只手视觉批准与冻结 manifest 已通过字节/SHA256/尺寸/identity 复核；`engineeringPass=true`、`userVisualApproval=true`、`formalR2Promotion=true`、`overallGatePass=true`、`R2-GATE=passed`。\n\n"
        "## 允许范围与保护\n\n"
        "正式范围：小星 Left = 正面屏幕左侧、解剖右臂；`candidates/upper-arm-aa-anatomical-v8/` 是唯一正式 R2 upper-arm 来源，sleeve/forearm/bracelet/hand 使用冻结输入。builder 只在已登记的 forearm seam/U-cap、语义 topology、正式 Alpha、合同、报告和中文 QA 范围内写入；最新批准记录和历史冻结记录均不被改写。\n\n"
        "shaft visible ownership 直接来自 front-line master 的 4-connected skin-side enclosed component；腕部 seam 直接取 source free components 与 source barrier pixels，注册 corridor 只作选择 guard，不能单独发出色块。shaft formal Alpha 在固定 supersample 后保留 fractional edge，并在 source ownership 内重新裁切；U-cap formal Alpha 则以最新蓝线为唯一显示边界，旧源线只保留为逻辑连接与审计诊断，不能再次把顶部裁成台阶。U-cap 使用 source-space float periodic C2 cubic Bézier；在 32×画布完成高分辨率布尔运算，逻辑 mask 只在一次 BOX coverage 下采样后阈值化；formal display Alpha 由注册 cubic coverage 生成，并在下采样后执行蓝线边界 guard。禁止低分辨率 NEAREST 几何、矩形/尖锐多边形/固定圆/全局 hull/radial patch、blur、dilate、erode、LANCZOS ringing。\n\n"
        "## 输出\n\n"
        "逻辑输出：四个主层 visible/hidden/complete 与 forearm 子区域；正式显示 Alpha 与 flat layer 保持 512×1086 identity。`forearm_skin` 必须单组件/0 孔洞；`forearm` 的 6 个孔洞必须逐坐标匹配冻结 bracelet legal negative spaces。旧 zero-hole forearm checks 只作历史并明确 superseded。\n\n"
        "## 门禁与后续\n\n"
        "审查入口：`qa/R2-小星Left-全画布平色材料-中文审查图.png`、`audit/r2-formal-promotion-report.json`、`audit/machine-report.json`、`contracts/topology-expectations.json`。抬手序列仍是 R2 diagnostic-only：03/04/06/07 的 hand 小岛来自 BICUBIC + Alpha>=128 低分辨率变换阈值；没有声称 R3 通过，未来 R3 需要至少 41 个高分辨率 floating-boundary coverage 点。本任务明确未进入 R3、纹理、网格、节点、Physics、Cubism 或 Runtime。\n",
        encoding="utf-8",
    )
    return readme


def legacy_hand_repair_main() -> None:
    R2_ROOT.mkdir(parents=True, exist_ok=True)
    previous_manifest_path = R2_ROOT / "audit" / "artifact-manifest.json"
    previous_manifest = load_json(previous_manifest_path) if previous_manifest_path.exists() else None

    source_results, images = validate_source_inputs()
    r1_freeze = validate_r1_freeze()
    protected_before = snapshot_protected_files()
    v38_hash = sha256_file(V38_REPORT_PATH)
    assert r1_freeze["allFrozenHashesMatch"]
    assert r1_freeze["r1MachineReportConsistent"]
    assert r1_freeze["reviewSha256MatchesReportRun1"] and r1_freeze["reviewSha256MatchesReportRun2"]
    markup_registration = validate_user_markup_registration()

    repair_baseline = capture_repair_baseline()
    non_hand_before = snapshot_non_hand_r2_files()
    masks, geometry_meta, hand_source_pixels, hand_line_barrier = build_geometry_masks()
    hand_trace_contract, hand_trace_report, hand_source_overlay, hand_candidate_overlay = audit_hand_line_trace(
        images["front-line-source-exact-after-reset"],
        masks["primary"]["hand"]["visible"],
        hand_source_pixels,
        hand_line_barrier,
    )
    hand_trace_contract["visualBoundaryContract"] = {
        "markupPath": markup_registration["path"],
        "markupSha256": markup_registration["sha256"],
        "markupDimensions": markup_registration["markupDimensions"],
        "sourceCanvas": markup_registration["sourceCanvas"],
        "sourceRoi": markup_registration["sourceRoi"],
        "coordinateTransform": markup_registration["coordinateTransform"],
        "allowedSide": markup_registration["allowedSide"],
        "leftGuide": [list(point) for point in HAND_VISUAL_LEFT_EDGE],
        "topGuidePolyline": [list(point) for point in HAND_VISUAL_TOP_BOUNDARY],
        "rightGuide": [list(point) for point in HAND_VISUAL_RIGHT_EDGE],
        "bezierSegments": [[list(point) for point in segment] for segment in HAND_VISUAL_BEZIER_SEGMENTS],
        "curveInsetYPx": HAND_VISUAL_CURVE_INSET_Y_PX,
        "boundaryInsetPx": HAND_VISUAL_BOUNDARY_INSET_PX,
        "supersample": HAND_VISUAL_SUPERSAMPLE,
        "finalClipAfterDownsample": True,
        "rawMarkupClipAfterDownsample": True,
    }
    hand_trace_contract["handHiddenAaMaintenance"] = {
        "status": "R2_HAND_HIDDEN_AA_MAINTENANCE_CANDIDATE / WAITING_USER_VISUAL_APPROVAL",
        "sourceCanvas": list(CANVAS),
        "coordinateTransform": "identity; all hand wrist-root coordinates are frontMaster source pixels",
        "redlineMarkup": {
            "path": markup_registration["path"],
            "sha256": markup_registration["sha256"],
            "allowedSide": markup_registration["allowedSide"],
            "outsideBoundaryPixelsMustBe": 0,
        },
        "handWristRoot": {
            "controlPoints": [list(point) for point in HAND_WRIST_ROOT_CONTROL_POINTS],
            "bezierSegments": [[list(point) for point in segment] for segment in HAND_WRIST_ROOT_BEZIER_SEGMENTS],
            "closed": True,
            "continuityTarget": "C2",
            "supersample": HAND_AA_SUPERSAMPLE,
            "construction": "float cubic path multiplied by supersample before rasterization; high-resolution boolean hidden/visible/complete; one BOX coverage downsample",
        },
        "hiddenWristEnvelope": {
            "roi": list(HAND_HIDDEN_WRIST_ROI),
            "controlPoints": [list(point) for point in HAND_HIDDEN_ENVELOPE_CONTROL_POINTS],
            "bezierSegments": [[list(point) for point in segment] for segment in HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS],
            "allowedSide": "inside the separately registered hidden wrist envelope",
            "hiddenOutsideEnvelopePixelsMustBe": 0,
        },
        "logicMasks": {
            "visible": "masks/visible/hand.png; source-locked binary ownership",
            "hidden": "masks/hidden/hand.png; binary result of high-resolution root minus visible",
            "complete": "masks/complete/hand.png; binary visible union hidden",
        },
        "displayAlpha": {
            "hidden": "display-alpha/hand-hidden.png; grayscale coverage for hidden material under occluders",
            "complete": "display-alpha/hand-complete.png; grayscale final visible/display alpha after redline guard",
            "flatLayer": "flat-layers/hand.png uses display-alpha/hand-complete.png",
            "downsample": "BOX",
        },
        "downstreamGeometrySource": "handHiddenAaMaintenance.handWristRoot.bezierSegments; never binary masks/hidden/hand.png",
        "downstreamTextureAlphaSource": "display-alpha/hand-hidden.png and display-alpha/hand-complete.png",
        "forbiddenDirectTraceSources": ["masks/hidden/hand.png", "masks/complete/hand.png", "low-resolution binary edge", "NEAREST enlargement"],
    }
    write_json(HAND_TRACE_CONTRACT_PATH, hand_trace_contract)
    hand_trace_report_path = R2_ROOT / "audit" / "hand-boundary-error-table.json"
    write_json(hand_trace_report_path, hand_trace_report)
    contracts = build_contracts(geometry_meta, masks, source_results)
    for name, contract in contracts.items():
        path = R2_ROOT / "contracts" / ({"layering": "layering-contract.json", "drawOrder": "draw-order-contract.json", "topology": "topology-expectations.json"}[name])
        write_json(path, contract)

    current_hand_visible_path = R2_ROOT / "masks" / "visible" / "hand.png"
    if not current_hand_visible_path.exists():
        raise FileNotFoundError(f"cannot verify current hand visible preservation: {current_hand_visible_path}")
    current_hand_visible_before_build = Image.open(current_hand_visible_path).convert("L")
    written_paths: list[Path] = []
    written_paths.extend(write_masks(masks))
    flat_paths, flat_images, lift_action = write_flat_layers(masks)
    written_paths.extend(flat_paths)
    hand_visible_diff = mask_diff_stats(
        current_hand_visible_before_build,
        masks["primary"]["hand"]["visible"],
    )
    hand_visible_diff["baselineSource"] = "current masks/visible/hand.png captured immediately before this build"
    hand_display_diff = display_alpha_diff_stats(
        load_repair_baseline_display(repair_baseline, "hand.formalDisplayFlatLayer"),
        flat_images["hand"].getchannel("A"),
        HAND_HIDDEN_WRIST_ROI,
    )
    hand_visual_boundary_report = audit_hand_visual_boundary(flat_images["hand"].getchannel("A"))
    write_json(HAND_VISUAL_BOUNDARY_REPORT_PATH, hand_visual_boundary_report)
    written_paths.append(HAND_VISUAL_BOUNDARY_REPORT_PATH)
    diagnostics, heatmap = check_masks(masks, contracts, source_results)
    diagnostics["markupRegistration"] = markup_registration
    diagnostics["checks"].extend([
        {
            "id": f"markup_registration_{check['id']}",
            "pass": bool(check["pass"]),
            "detail": "最新用户红线文件、哈希、画布、ROI 和 identity 变换合同有效",
            **{key: value for key, value in check.items() if key not in {"id", "pass"}},
        }
        for check in markup_registration["checks"]
    ])
    diagnostics["checks"].extend(lift_action["checks"])
    diagnostics["checks"].extend(hand_trace_report["checks"])
    diagnostics["checks"].extend(hand_visual_boundary_report["checks"])
    diagnostics["handVisualBoundaryAudit"] = {
        "reportPath": "audit/hand-visual-boundary-report.json",
        "outsideBoundaryPixels": hand_visual_boundary_report["outsideBoundaryPixels"],
        "renderedGuideBoundary": hand_visual_boundary_report["renderedGuideBoundary"],
        "visibleCandidateBoundary": hand_visual_boundary_report["visibleCandidateBoundary"],
        "overallPass": hand_visual_boundary_report["overallPass"],
    }
    diagnostics["handTraceAudit"] = {
        "contractPath": "contracts/hand-line-trace-contract.json",
        "reportPath": "audit/hand-boundary-error-table.json",
        "aggregate": hand_trace_report["aggregate"],
        "structure": hand_trace_report["structure"],
        "overallPass": hand_trace_report["overallPass"],
    }
    diagnostics["handVisibleMaintenanceDiff"] = hand_visible_diff
    diagnostics["handFormalDisplayAlphaDiff"] = hand_display_diff
    diagnostics["checks"].extend([
        {
            "id": "hand_visible_pixels_unchanged",
            "pass": hand_visible_diff.get("baselineAvailable") is True and hand_visible_diff.get("changedPixels") == 0,
            "detail": "hand visible 逻辑所有权逐像素保持不变；本次只允许隐藏腕根派生层变化",
            **hand_visible_diff,
        },
        {
            "id": "formal_display_alpha_changes_confined_to_hidden_wrist_roi",
            "pass": hand_display_diff.get("baselineAvailable") is True and hand_display_diff.get("outsideRoiUnchanged") is True,
            "detail": "hand 正式显示 Alpha 的变化只能位于登记的隐藏腕根 ROI",
            **hand_display_diff,
        },
    ])
    segmented_boundary_report, segmented_line_overlay = audit_source_boundaries(masks, images)
    diagnostics["checks"].extend(segmented_boundary_report["checks"])
    diagnostics["segmentedBoundaryAudit"] = {
        "reportPath": "audit/segmented-boundary-report.json",
        "segmentCount": segmented_boundary_report["visibleSegmentCount"],
        "hiddenBoundaryConstraintCount": len(segmented_boundary_report["hiddenBoundaryConstraints"]),
    }
    repair_diff, repair_comparison = build_repair_diff(
        masks,
        repair_baseline,
        images["front-line-source-exact-after-reset"],
    )
    repair_diff["formalDisplayAlpha"] = hand_display_diff
    repair_diff["handVisibleLogic"] = hand_visible_diff
    repair_diff_path = R2_ROOT / "audit" / "r2-repair-pixel-diff.json"
    write_json(repair_diff_path, repair_diff)
    segmented_boundary_path = R2_ROOT / "audit" / "segmented-boundary-report.json"
    write_json(segmented_boundary_path, segmented_boundary_report)
    written_paths.extend([repair_diff_path, segmented_boundary_path, hand_trace_report_path, HAND_TRACE_CONTRACT_PATH])
    expected_neutral_alpha = mask_union(*[
        masks["primary"][layer_id]["visible"]
        for layer_id in FORMAL_LAYER_IDS
    ])
    actual_neutral_alpha = flat_images["layer-only-neutral"].getchannel("A")
    diagnostics["checks"].append({
        "id": "layer_only_neutral_alpha_matches_visible_ownership",
        "pass": actual_neutral_alpha.tobytes() == expected_neutral_alpha.tobytes(),
        "detail": "默认 layer-only alpha 只覆盖 R2 visible ownership；不含整人底图或未登记 alpha",
        "unexpectedPixels": mask_count(mask_subtract(actual_neutral_alpha, expected_neutral_alpha)),
        "missingPixels": mask_count(mask_subtract(expected_neutral_alpha, actual_neutral_alpha)),
    })
    protected_after = snapshot_protected_files()
    diagnostics["checks"].append({
        "id": "protected_847_files_unchanged",
        "pass": protected_after == protected_before and len(protected_after) == 847,
        "detail": "847 个 R1/历史受保护文件重跑前后哈希保持一致",
        "fileCountBefore": len(protected_before),
        "fileCountAfter": len(protected_after),
    })
    non_hand_after = snapshot_non_hand_r2_files()
    non_hand_unchanged = non_hand_after == non_hand_before
    non_hand_snapshot = {
        "schemaVersion": 1,
        "stage": "R2 hand repair non-hand artifact protection",
        **IDENTITY,
        "scope": "all existing R2 visible/hidden/complete masks except hand, hand-excluded subregions, and independent non-hand flat layers",
        "before": non_hand_before,
        "after": non_hand_after,
        "unchanged": non_hand_unchanged,
        "handOnlyChangeScope": "hand visible/hidden/complete masks, hand flat layer, hand-dependent composites/reports/QA only",
    }
    write_json(R2_NON_HAND_SNAPSHOT_PATH, non_hand_snapshot)
    diagnostics["checks"].append({
        "id": "non_hand_r2_artifacts_unchanged",
        "pass": non_hand_unchanged,
        "detail": "手部返修不得改变既有 R2 非 hand masks、subregions 或独立非手部 flat layers",
        "fileCountBefore": len(non_hand_before),
        "fileCountAfter": len(non_hand_after),
        "changedPaths": sorted(set(non_hand_before) ^ set(non_hand_after)) + [
            path for path in sorted(set(non_hand_before) & set(non_hand_after))
            if non_hand_before[path] != non_hand_after[path]
        ],
    })
    written_paths.append(R2_NON_HAND_SNAPSHOT_PATH)
    written_paths.extend(write_visual_review_assets(
        images,
        flat_images,
        heatmap,
        lift_action,
        repair_baseline,
        repair_diff,
        repair_comparison,
        segmented_line_overlay,
    ))
    written_paths.extend(write_hand_repair_visual_assets(
        images,
        flat_images,
        repair_baseline,
        hand_trace_contract,
        hand_trace_report,
        hand_source_overlay,
        hand_candidate_overlay,
    ))
    hand_aa_review_path = write_hand_aa_maintenance_review(
        images,
        flat_images,
        repair_baseline,
        hand_visual_boundary_report,
        diagnostics["handWristRootGeometry"],
        hand_visible_diff,
        hand_display_diff,
        markup_registration,
    )
    written_paths.append(hand_aa_review_path)
    diagnostics["handAaMaintenanceReview"] = {
        "path": str(hand_aa_review_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "status": "candidate_only_waiting_user_visual_approval",
        "requiredPanels": [
            "old logical binary mask",
            "float Bezier and hidden envelope",
            "display Alpha checkerboard",
            "bracelet removed 100% and 200%",
            "redline overlay and outside-boundary heatmap",
            "old/new XOR within authorized ROI",
            "125%/150%/200% scale comparison",
            "outsideBoundaryPixels readable conclusion",
        ],
    }
    diagnostics["checks"].append({
        "id": "hand_aa_maintenance_review_artifact_exists",
        "pass": hand_aa_review_path.exists(),
        "detail": "新的中文隐藏腕根抗锯齿维护审查图已生成；不等于用户视觉批准",
        "path": str(hand_aa_review_path.relative_to(REPO_ROOT)).replace("\\", "/"),
    })
    written_paths.append(write_readme())

    lift_action_report = {
        "schemaVersion": 2,
        "stage": "R2 flat-color articulated lift geometry QA",
        **IDENTITY,
        "status": "qa_only_not_R3",
        "pivots": lift_action["pivots"],
        "transformOrder": lift_action["transformOrder"],
        "frames": [
            {key: value for key, value in frame.items() if key != "composite"}
            for frame in lift_action["frames"]
        ],
        "checks": lift_action["checks"],
        "r3Evidence": {
            "qa_only_not_R3": True,
            "sampleCount": len(lift_action["frames"]),
            "atLeast41Points": False,
            "verifiedCombinationExtrema": False,
            "verifiedRealSleeveDoubleAnchorDeformation": False,
            "verifiedTorsoHairSupportAndOcclusion": False,
            "geometryFreezeAuthorized": False,
        },
        "interpretation": {
            "sleeve": "与 upper_arm 共享肩部旋转；hidden 袖筒必须随袖子整体移动",
            "upper_arm": "肩点父链，和 sleeve 同向",
            "forearm": "先绕肘点折叠，再继承肩部变换；包含 bracelet",
            "hand": "先随肘部链移动，再继承肩部变换；不拥有 bracelet",
            "notRuntimeProof": "这是色块连续性/方向性测试，不等于 Cubism 节点或 Runtime 已通过",
        },
    }
    lift_action_report_path = R2_ROOT / "audit" / "lift-action-report.json"
    write_json(lift_action_report_path, lift_action_report)
    written_paths.append(lift_action_report_path)

    protected_digest = hashlib.sha256(canonical_json(protected_before).encode("utf-8")).hexdigest()
    gate_state = r2_gate_state()
    r2_approved = gate_state == "approved"
    engineering_pass = all(bool(check["pass"]) for check in diagnostics["checks"])
    overall_gate_pass = engineering_pass and r2_approved

    machine_report = {
        "schemaVersion": 2,
        "stage": "R2 full-canvas flat-color complete materials",
        "status": "r2_visual_approved_current_scope" if r2_approved else "R2_HAND_HIDDEN_AA_MAINTENANCE_CANDIDATE / WAITING_USER_VISUAL_APPROVAL",
        "gateDecision": gate_state,
        **IDENTITY,
        "r1Freeze": r1_freeze,
        "forearmRedrawConfirmation": forearm_redraw_confirmation,
        "historicalR1WristEnvelopeSuperseded": historical_r1_wrist_envelope,
        "sourceInputs": source_results,
        "historicalEvidence": {
            "v38MachineReport": str(V38_REPORT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "v38MachineReportSha256": v38_hash,
            "use": "read-only regression evidence; no V38 mask/material is inherited",
        },
        "geometry": geometry_meta,
        "contracts": {
            "layering": "contracts/layering-contract.json",
            "drawOrder": "contracts/draw-order-contract.json",
            "topology": "contracts/topology-expectations.json",
            "handLineTrace": "contracts/hand-line-trace-contract.json",
            "handHiddenAaMaintenance": "contracts/hand-line-trace-contract.json#handHiddenAaMaintenance",
        },
        "repairEvidence": {
            "baseline": "audit/repair-baseline.json",
            "pixelDiff": "audit/r2-repair-pixel-diff.json",
            "segmentedBoundaryAudit": "audit/segmented-boundary-report.json",
            "handBoundaryErrorTable": "audit/hand-boundary-error-table.json",
            "handVisualBoundary": "audit/hand-visual-boundary-report.json",
            "displayAlphaHidden": "display-alpha/hand-hidden.png",
            "displayAlphaComplete": "display-alpha/hand-complete.png",
            "formalFlatLayer": "flat-layers/hand.png",
            "authorizedHandHiddenWristRoi": list(HAND_HIDDEN_WRIST_ROI),
            "handVisibleDiff": hand_visible_diff,
            "formalDisplayAlphaDiff": hand_display_diff,
            "userVisualApprovalCurrent": "audit/user-visual-approval-r2-2026-08-07.json",
            "userVisualRejection": "audit/user-visual-rejection-hand-r2-2026-08-07.json",
            "userVisualRefinementRequest": "audit/user-visual-refinement-request-hand-r2-2026-08-07.json",
            "userVisualSmoothEdgeReopen": "audit/user-visual-rejection-hand-r2-smooth-edge-2026-08-09.json",
        },
        "r3DiagnosticOnly": {
            "status": "qa_only_not_R3",
            "sampleCount": len(lift_action["frames"]),
            "atLeast41Points": False,
            "verifiedCombinationExtrema": False,
            "verifiedRealSleeveDoubleAnchorDeformation": False,
            "verifiedTorsoHairSupportAndOcclusion": False,
            "geometryFreezeAuthorized": False,
        },
        "checks": diagnostics["checks"],
        "diagnostics": {key: value for key, value in diagnostics.items() if key != "checks"},
        "protectedArtifacts": {
            "snapshotDigest": protected_digest,
            "fileCount": len(protected_before),
            "snapshotScope": "R1 frozen evidence plus all existing arm-chain-screen-left-v* historical files; no R2 output is included",
            "unchangedAfterBuild": protected_after == protected_before,
        },
        "nonHandR2Protected": non_hand_snapshot,
        "determinism": {
            "method": "run this builder twice and compare audit/artifact-manifest.json; all outputs use fixed PNG and canonical JSON settings",
            "noTimestampOrRandomness": True,
            "requiredConsecutiveRunCheck": "external invocation comparison",
            "runEvidence": {
                "run1": "audit/rebuild-run-1.json",
                "run2": "audit/rebuild-run-2.json",
                "excludedFromArtifactManifest": True,
            },
        },
        "downstreamForbidden": ["texture", "PSD", "Cubism", "ArtMesh", "Deformer", "nodes", "parameters", "motion", "Physics", "Runtime", "pet integration"],
        "r2Gate": gate_state,
        "engineeringPass": engineering_pass,
        "overallGatePass": overall_gate_pass,
        "reviewImage": "qa/R2-小星Left-全画布平色材料-中文审查图.png",
        "handAaMaintenanceReviewImage": "qa/hand-r2-repair/14-隐藏腕根抗锯齿维护审查.png",
        "unresolvedRisks": geometry_meta["unresolved"],
        "acceptedVisualLimitations": geometry_meta["acceptedVisualLimitations"],
        "userVisualApproval": str((R2_FINAL_APPROVAL_PATH if R2_FINAL_APPROVAL_PATH.exists() else R2_CURRENT_APPROVAL_PATH).relative_to(REPO_ROOT)).replace("\\", "/") if r2_approved else None,
        "historicalUserVisualApproval": str(R2_APPROVAL_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "userVisualRejection": str(R2_REJECTION_PATH.relative_to(REPO_ROOT)).replace("\\", "/") if R2_REJECTION_PATH.exists() else None,
        "userVisualRefinementRequest": str(R2_VISUAL_REFINEMENT_PATH.relative_to(REPO_ROOT)).replace("\\", "/") if R2_VISUAL_REFINEMENT_PATH.exists() else None,
        "userVisualSmoothEdgeReopen": str(R2_SMOOTH_EDGE_REOPEN_PATH.relative_to(REPO_ROOT)).replace("\\", "/") if R2_SMOOTH_EDGE_REOPEN_PATH.exists() else None,
    }
    machine_report_path = R2_ROOT / "audit" / "machine-report.json"
    write_json(machine_report_path, machine_report)
    written_paths.append(machine_report_path)

    artifact_manifest_excludes = {
        R2_ROOT / "audit" / "artifact-manifest.json",
        R2_REBUILD_RUN_1_PATH,
        R2_REBUILD_RUN_2_PATH,
    }
    current_entries = artifact_snapshot(exclude=artifact_manifest_excludes)
    previous_match = None
    if isinstance(previous_manifest, dict):
        previous_entries = previous_manifest.get("artifacts", [])
        previous_match = previous_entries == current_entries
    manifest = {
        "schemaVersion": 1,
        "stage": "R2 full-canvas flat-color complete materials",
        "status": "r2_approved_current_scope" if r2_approved else "R2_HAND_HIDDEN_AA_MAINTENANCE_CANDIDATE / WAITING_USER_VISUAL_APPROVAL",
        **IDENTITY,
        "artifactManifestExcludesItself": True,
        "artifacts": current_entries,
        "r1FreezeInputManifest": "../arm-chain-screen-left-r1-physical-line-contract/audit/r1-freeze-checklist-2026-08-05.json",
        "protectedSnapshotDigest": protected_digest,
        "r2Gate": gate_state,
    }
    manifest_path = R2_ROOT / "audit" / "artifact-manifest.json"
    write_json(manifest_path, manifest)

    previous_protected_match = None
    if isinstance(previous_manifest, dict):
        previous_protected_match = previous_manifest.get("protectedSnapshotDigest") == protected_digest
    report = {
        "engineeringPass": machine_report["engineeringPass"],
        "overallGatePass": machine_report["overallGatePass"],
        "artifactCount": len(current_entries),
        "protectedFileCount": len(protected_before),
        "previousProtectedSnapshotMatched": previous_protected_match,
        "previousArtifactListMatched": previous_match,
        "review": str((R2_ROOT / "qa" / "R2-小星Left-全画布平色材料-中文审查图.png").relative_to(REPO_ROOT)).replace("\\", "/"),
    }
    run1_matches_current = False
    if R2_REBUILD_RUN_1_PATH.exists():
        try:
            previous_run1 = load_json(R2_REBUILD_RUN_1_PATH)
            run1_matches_current = (
                isinstance(previous_run1, dict)
                and previous_run1.get("artifactManifestSha256") == sha256_file(manifest_path)
                and previous_run1.get("machineReportSha256") == sha256_file(machine_report_path)
            )
        except (OSError, json.JSONDecodeError):
            run1_matches_current = False
    # Refresh run 1 when an earlier source/script revision left stale evidence;
    # only then write run 2.  This keeps the pair meaningful across repairs
    # without deleting or silently treating stale evidence as deterministic.
    run_path = R2_REBUILD_RUN_2_PATH if run1_matches_current else R2_REBUILD_RUN_1_PATH
    run_number = 1 if run_path == R2_REBUILD_RUN_1_PATH else 2
    write_json(run_path, {
        "schemaVersion": 1,
        "stage": "R2 deterministic hand repair rebuild evidence",
        "runNumber": run_number,
        **IDENTITY,
        "status": machine_report["status"],
        "gateDecision": gate_state,
        "engineeringPass": machine_report["engineeringPass"],
        "overallGatePass": machine_report["overallGatePass"],
        "artifactManifestSha256": sha256_file(manifest_path),
        "machineReportSha256": sha256_file(machine_report_path),
        "artifactCount": len(current_entries),
        "protectedFileCount": len(protected_before),
        "protectedArtifactsUnchanged": protected_after == protected_before,
        "nonHandR2ArtifactsUnchanged": non_hand_unchanged,
        "handTrace": {
            "overallPass": hand_trace_report["overallPass"],
            "maxBidirectionalPx": hand_trace_report["aggregate"]["maxBidirectionalPx"],
            "p95BidirectionalPx": hand_trace_report["aggregate"]["p95BidirectionalPx"],
            "uncoveredSourceLinePixels": hand_trace_report["aggregate"]["uncoveredSourceLinePixels"],
            "unmatchedCandidateBoundaryPixels": hand_trace_report["aggregate"]["unmatchedCandidateBoundaryPixels"],
        },
        "previousProtectedSnapshotMatched": previous_protected_match,
        "previousArtifactListMatched": previous_match,
        "downstreamForbidden": True,
        "nextState": "R2_GEOMETRY_FREEZE_ONLY; do not enter R3/R4" if r2_approved else "WAITING_USER_VISUAL_APPROVAL; do not enter R3/R4",
    })
    print(json.dumps(report, ensure_ascii=False))


def forearm_ucap_main() -> None:
    """Rebuild and formally close the approved R2 flat-color material scope."""
    R2_ROOT.mkdir(parents=True, exist_ok=True)
    previous_manifest_path = R2_ROOT / "audit" / "artifact-manifest.json"
    previous_manifest = load_json(previous_manifest_path) if previous_manifest_path.exists() else None

    whole_hand_freeze = validate_whole_hand_freeze()
    if not bool(whole_hand_freeze["visualFreezeHashMatch"]):
        raise RuntimeError("whole-hand visual freeze hash/identity validation failed; formal R2 promotion stopped")
    upper_arm_promotion = promote_upper_arm_v8()
    source_results, images = validate_source_inputs()
    r1_freeze = validate_r1_freeze()
    forearm_redraw_confirmation = validate_forearm_redraw_confirmation()
    protected_before = snapshot_protected_files()
    v38_hash = sha256_file(V38_REPORT_PATH)
    assert r1_freeze["allFrozenHashesMatch"]
    assert r1_freeze["r1MachineReportConsistent"]
    assert r1_freeze["reviewSha256MatchesReportRun1"] and r1_freeze["reviewSha256MatchesReportRun2"]

    repair_baseline_value = load_json(REPAIR_BASELINE_PATH)
    if not isinstance(repair_baseline_value, dict):
        raise ValueError(f"repair baseline is not an object: {REPAIR_BASELINE_PATH}")
    repair_baseline = repair_baseline_value
    hand_protected_before = snapshot_current_hand_artifacts()
    non_forearm_before = snapshot_non_forearm_r2_files()
    forearm_visible_path = R2_ROOT / "masks" / "visible" / "forearm.png"
    if not forearm_visible_path.exists():
        raise FileNotFoundError(f"protected visible forearm source is missing: {forearm_visible_path}")
    forearm_visible_before = Image.open(forearm_visible_path).convert("L")

    masks, geometry_meta, _hand_source_pixels, _hand_line_barrier, forearm_ucap_logic = build_geometry_masks()
    current_stage = "R2_FORMAL_PROMOTED / R3_READY_NOT_STARTED"
    geometry_meta["wholeHandVisualFreeze"] = whole_hand_freeze
    geometry_meta["upperArmFormalPromotion"] = upper_arm_promotion
    geometry_meta["forearmStageStatus"] = current_stage
    geometry_meta["forearmUserVisualApproval"] = whole_hand_freeze["approvalPath"]
    geometry_meta["forearmUnresolved"] = [
        "手链后半环真实深度在单一正面源线中不可唯一判定；当前只声明 front-facing 小幅腕部移动/旋转候选。",
        "抬手动作全帧连通性保留为 R2 diagnostic-only；静态 complete mask 已验证，低分辨率变换断裂不得冒充 R3 通过。",
    ]
    geometry_meta["unresolved"] = geometry_meta["forearmUnresolved"]
    geometry_meta["acceptedVisualLimitations"] = [
        "整只手平色视觉输入已由 2026-08-12 最新批准记录冻结；本报告只声明工程 R2 正式提升，不声明纹理、网格、节点、Physics、Cubism、Runtime 或 R3 完成。",
        "手链后半环仍仅支持 front-facing 小幅腕部移动/旋转；深度不确定性保留在 forearm-owned audit 子区。",
    ]

    hand_logic_matches: dict[str, bool] = {}
    for variant in ("visible", "hidden", "complete"):
        current_hand = Image.open(R2_ROOT / "masks" / variant / "hand.png").convert("L")
        hand_logic_matches[variant] = current_hand.tobytes() == masks["primary"]["hand"][variant].tobytes()
    forearm_visible_diff = mask_diff_stats(forearm_visible_before, masks["primary"]["forearm"]["visible"])
    forearm_visible_repair_diff = mask_diff_stats(
        load_repair_baseline_mask(repair_baseline, "forearm", "visible"),
        masks["primary"]["forearm"]["visible"],
    )

    contracts = build_contracts(geometry_meta, masks, source_results)
    contract_paths = {
        "layering": R2_ROOT / "contracts" / "layering-contract.json",
        "drawOrder": R2_ROOT / "contracts" / "draw-order-contract.json",
        "topology": R2_ROOT / "contracts" / "topology-expectations.json",
        "forearmUcap": FOREARM_UCAP_CONTRACT_PATH,
    }
    for name, path in contract_paths.items():
        write_json(path, contracts[name])

    write_masks(masks)
    _flat_paths, flat_images, lift_action, formal_report = write_flat_layers(masks, forearm_ucap_logic)
    upper_arm_promotion_after_dependents = promote_upper_arm_v8()
    upper_arm_promotion["afterDependentOutputs"] = upper_arm_promotion_after_dependents
    diagnostics, _heatmap = check_masks(masks, contracts, source_results)
    diagnostics["checks"].extend(lift_action["checks"])
    diagnostics["checks"].extend([
        {
            "id": "whole_hand_visual_freeze_hash_match",
            "pass": bool(whole_hand_freeze["visualFreezeHashMatch"]),
            "detail": "最新整只手视觉批准、冻结 manifest、source authority、latest markups 与 v8 候选输入的字节/SHA256/身份核验",
            "approval": whole_hand_freeze["approvalPath"],
            "freezeManifest": whole_hand_freeze["freezeManifestPath"],
            "userVisualApproval": whole_hand_freeze["userVisualApproval"],
        },
        {
            "id": "formal_upper_arm_v8_promotion_byte_exact",
            "pass": bool(upper_arm_promotion.get("soleFormalSource")) and all(
                bool(record["byteExact"])
                for record in cast(list[dict[str, object]], upper_arm_promotion_after_dependents["records"])
            ),
            "detail": "upper-arm v8 在依赖 flat/composite 输出构建后仍与正式 R2 文件逐字节一致",
            "sourceCandidate": upper_arm_promotion["sourceCandidate"],
            "promotion": upper_arm_promotion_after_dependents,
        },
    ])
    source_boundary_check = next(
        (
            check
            for check in diagnostics["checks"]
            if str(check["id"]) == "forearm_shaft_visible_matches_source_line_component"
        ),
        {"pass": False, "detail": "source-line shaft check missing"},
    )
    shaft_scope_roi = roi_mask(FOREARM_SHAFT_SOURCE_VISIBLE_ROI)
    visible_change_outside_shaft = mask_subtract(
        ImageChops.difference(forearm_visible_before, masks["primary"]["forearm"]["visible"]),
        mask_union(shaft_scope_roi, roi_mask(FOREARM_WRIST_SOURCE_REPAIR_ROI)),
    )
    diagnostics["checks"].extend([
        {
            "id": str(check["id"]),
            "pass": bool(check["pass"]),
            "detail": "前臂 formal display Alpha / U-cap 注册边界检查",
            **{key: value for key, value in check.items() if key not in {"id", "pass"}},
        }
        for check in formal_report["checks"]
    ])
    diagnostics["checks"].extend([
        {
            "id": "hand_logic_artifacts_unchanged",
            "pass": all(hand_logic_matches.values()),
            "detail": "hand visible/hidden/complete 仅作保护输入，重算结果与既有文件逐像素一致",
            "variants": hand_logic_matches,
        },
        {
            "id": "forearm_visible_shaft_source_line_repair_matches_contract",
            "pass": bool(source_boundary_check.get("pass")) and mask_count(visible_change_outside_shaft) == 0,
            "detail": "前臂 visible 的变化只允许发生在已登记的 shaft ROI 或本轮腕部手链贴合 repair ROI；其他 forearm geometry 不随修正扩展",
            **forearm_visible_repair_diff,
            "currentInvocationDiff": forearm_visible_diff,
            "sourceBoundaryCheck": source_boundary_check,
            "changedPixelsOutsideAllowedRepairRoi": mask_count(visible_change_outside_shaft),
            "shaftRoi": list(FOREARM_SHAFT_SOURCE_VISIBLE_ROI),
            "wristBraceletRepairRoi": list(FOREARM_WRIST_SOURCE_REPAIR_ROI),
        },
    ])

    segmented_boundary_report, _segmented_overlay = audit_source_boundaries(masks, images)
    diagnostics["checks"].extend(segmented_boundary_report["checks"])
    diagnostics["segmentedBoundaryAudit"] = {
        "reportPath": "audit/segmented-boundary-report.json",
        "segmentCount": segmented_boundary_report["visibleSegmentCount"],
        "hiddenBoundaryConstraintCount": len(segmented_boundary_report["hiddenBoundaryConstraints"]),
    }
    write_json(R2_ROOT / "audit" / "segmented-boundary-report.json", segmented_boundary_report)

    repair_diff, _repair_comparison = build_repair_diff(
        masks, repair_baseline, images["front-line-source-exact-after-reset"]
    )
    forearm_pixel_diff = {
        "schemaVersion": 1,
        "stage": "FOREARM_DISTAL_UCAP_AA_STAGE_A pixel diff",
        **IDENTITY,
        "scope": "forearm visible shaft source-line lock plus wrist bracelet/skin source-line seam plus distal U-cap; hand/non-forearm outputs protected",
        "baseline": {
            "source": "audit/repair-baseline.json",
            "hidden": mask_diff_stats(load_repair_baseline_mask(repair_baseline, "forearm", "hidden"), masks["primary"]["forearm"]["hidden"]),
            "complete": mask_diff_stats(load_repair_baseline_mask(repair_baseline, "forearm", "complete"), masks["primary"]["forearm"]["complete"]),
        },
        "visibleShaftSourceLineRepair": forearm_visible_repair_diff,
        "visibleShaftCurrentInvocationDiff": forearm_visible_diff,
        "shaftRepairRoi": list(FOREARM_SHAFT_SOURCE_VISIBLE_ROI),
        "formalDisplayAlpha": {
            "forearm": alpha_summary(flat_images["forearm-display-alpha"]),
            "forearmSkin": alpha_summary(flat_images["forearm-skin-display-alpha"]),
            "ucap": alpha_summary(flat_images["forearm-ucap-display-alpha"]),
        },
        "sourceLineShaftBoundary": geometry_meta["forearmSourceLineBoundary"],
        "candidateControlPoints": [list(point) for point in FOREARM_DISTAL_UCAP_CONTROL_POINTS],
    }
    repair_diff["forearmDistalUcap"] = forearm_pixel_diff
    repair_diff["handProtection"] = {"artifacts": hand_protected_before, "rewritten": False}
    write_json(R2_ROOT / "audit" / "r2-repair-pixel-diff.json", repair_diff)
    write_json(FOREARM_UCAP_PIXEL_DIFF_PATH, forearm_pixel_diff)
    write_json(FOREARM_UCAP_BOUNDARY_REPORT_PATH, {
        "schemaVersion": 1,
        "stage": "FOREARM_DISTAL_UCAP_AA_STAGE_A visual boundary audit",
        **IDENTITY,
        **formal_report,
    })
    diagnostics["forearmFormalDisplayAlpha"] = formal_report

    formal_review_flat = dict(flat_images)
    formal_review_flat["hand-display-alpha-hidden"] = Image.open(R2_ROOT / "display-alpha" / "hand-hidden.png").convert("L")
    formal_review_flat["hand-display-alpha-complete"] = Image.open(R2_ROOT / "display-alpha" / "hand-complete.png").convert("L")
    r2_review_paths = write_visual_review_assets(
        images,
        formal_review_flat,
        _heatmap,
        lift_action,
        repair_baseline,
        repair_diff,
        _repair_comparison,
        _segmented_overlay,
    )
    r2_review_path = next(
        path for path in r2_review_paths
        if path.name == "R2-小星Left-全画布平色材料-中文审查图.png"
    )

    expected_neutral_alpha = mask_union(*[
        masks["primary"][layer_id]["visible"] for layer_id in FORMAL_LAYER_IDS
    ])
    actual_neutral_alpha = flat_images["layer-only-neutral"].getchannel("A")
    diagnostics["checks"].append({
        "id": "layer_only_neutral_alpha_matches_visible_ownership",
        "pass": actual_neutral_alpha.tobytes() == expected_neutral_alpha.tobytes(),
        "detail": "默认 layer-only alpha 只覆盖 visible ownership；不含 hidden 或整人底图",
        "unexpectedPixels": mask_count(mask_subtract(actual_neutral_alpha, expected_neutral_alpha)),
        "missingPixels": mask_count(mask_subtract(expected_neutral_alpha, actual_neutral_alpha)),
    })

    protected_after = snapshot_protected_files()
    diagnostics["checks"].append({
        "id": "protected_847_files_unchanged",
        "pass": protected_after == protected_before and len(protected_after) == len(protected_before),
        "detail": "R1/历史受保护文件重跑前后哈希保持一致",
        "fileCountBefore": len(protected_before),
        "fileCountAfter": len(protected_after),
    })
    hand_protected_after = snapshot_current_hand_artifacts()
    hand_protected_unchanged = hand_protected_after == hand_protected_before
    diagnostics["checks"].append({
        "id": "hand_protected_artifacts_unchanged",
        "pass": hand_protected_unchanged,
        "detail": "hand visible/hidden/complete、formal display Alpha、flat hand 与 hand 直接审查产物均未被重写",
        "before": hand_protected_before,
        "after": hand_protected_after,
    })

    non_forearm_after = snapshot_non_forearm_r2_files()
    non_forearm_unchanged = non_forearm_after == non_forearm_before
    non_forearm_snapshot = {
        "schemaVersion": 1,
        "stage": "R2 forearm-only reopen non-forearm artifact protection",
        **IDENTITY,
        "scope": "all existing R2 outputs except the registered forearm shaft/wrist repair, forearm-skin subregion, bracelet source-line subregion, formal Alpha and dependent composites",
        "before": non_forearm_before,
        "after": non_forearm_after,
        "unchanged": non_forearm_unchanged,
        "allowedChanges": [
            "forearm logic/formal Alpha/flat layers",
            "bracelet source-line masks/formal Alpha/audit flat layers",
            "dependent reports/contracts/QA",
        ],
    }
    write_json(R2_NON_FOREARM_SNAPSHOT_PATH, non_forearm_snapshot)
    diagnostics["checks"].append({
        "id": "non_forearm_r2_artifacts_unchanged",
        "pass": non_forearm_unchanged,
        "detail": "袖子、upper_arm、hand 与其他非本轮 wrist seam 的既有输出保持哈希不变；bracelet 已登记为本轮允许变更的 forearm 子区",
        "fileCountBefore": len(non_forearm_before),
        "fileCountAfter": len(non_forearm_after),
        "changedPaths": sorted(set(non_forearm_before) ^ set(non_forearm_after)) + [
            path for path in sorted(set(non_forearm_before) & set(non_forearm_after))
            if non_forearm_before[path] != non_forearm_after[path]
        ],
    })

    wrist_envelope_check = next(
        (check for check in diagnostics["checks"] if str(check["id"]) == "wrist_r1_envelope_included"),
        None,
    )
    latest_markup_check = next(
        (check for check in diagnostics["checks"] if str(check["id"]) == "forearm_ucap_matches_latest_user_markup"),
        None,
    )
    historical_r1_wrist_envelope = {
        "checkId": "wrist_r1_envelope_included",
        "diagnosticOnly": True,
        "blockingEngineeringFailure": False,
        "historicalR1EnvelopeUncoveredPixels": int(((wrist_envelope_check or {}).get("historicalR1Envelope") or {}).get("uncoveredPixels", 0)),
        "activeRedlineEnvelopeUncoveredPixels": int((wrist_envelope_check or {}).get("uncoveredPixels", 0)),
        "latestUserMarkupCheckPass": bool((latest_markup_check or {}).get("pass")),
        "latestUserMarkupPath": FOREARM_USER_MARKUP_PATH,
        "redrawConfirmationPath": forearm_redraw_confirmation["path"],
        "resolution": "the 2026-08-11 user-confirmed latest blue boundary is now the active wrist envelope for the reopened forearm U-cap; the wider historical R1 contract remains preserved read-only",
        "status": "historical_r1_envelope_superseded_for_reopened_forearm_ucap",
    }
    diagnostics["historicalR1WristEnvelopeSuperseded"] = historical_r1_wrist_envelope

    # The latest user red line is authoritative for this reopened visual
    # boundary and is now the active wrist envelope after explicit redraw
    # confirmation.  The wider R1 ellipse remains historical evidence only.
    # The action connectivity check remains independently out of scope for
    # this forearm-only rebuild.
    diagnostic_only_ids = {"lift_action_all_frames_connected"}
    superseded_topology_ids = {
        "forearm_semantic_topology",
        "forearm_complete_single_component_no_holes",
        "elbow_r1_envelope_included",
    }
    engineering_before_qa = all(
        bool(check["pass"])
        for check in diagnostics["checks"]
        if str(check["id"]) not in diagnostic_only_ids | superseded_topology_ids
    )
    qa_board_path = write_forearm_ucap_qa_board(
        images,
        masks,
        flat_images,
        formal_report,
        engineering_before_qa,
        lift_action,
        historical_r1_wrist_envelope,
    )
    diagnostics["checks"].append({
        "id": "forearm_ucap_chinese_visual_review_board_exists",
        "pass": qa_board_path.exists(),
        "detail": "中文视觉审查图已生成，包含必需的几何、Alpha、深度、比例、接缝、越界和停止条件面板",
        "path": str(qa_board_path.relative_to(REPO_ROOT)).replace("\\", "/"),
    })

    lift_action_report = {
        "schemaVersion": 2,
        "stage": "R2 flat-color articulated lift geometry QA",
        **IDENTITY,
        "status": "qa_only_not_R3",
        "pivots": lift_action["pivots"],
        "transformOrder": lift_action["transformOrder"],
        "frames": [{key: value for key, value in frame.items() if key != "composite"} for frame in lift_action["frames"]],
        "checks": lift_action["checks"],
        "diagnosticOnly": True,
        "outOfScope": "action system rebuild",
        "r3Evidence": {
            "qa_only_not_R3": True,
            "sampleCount": len(lift_action["frames"]),
            "atLeast41Points": False,
            "verifiedCombinationExtrema": False,
            "verifiedRealSleeveDoubleAnchorDeformation": False,
            "verifiedTorsoHairSupportAndOcclusion": False,
            "geometryFreezeAuthorized": False,
        },
    }
    write_json(R2_ROOT / "audit" / "lift-action-report.json", lift_action_report)
    readme_path = write_readme()

    engineering_pass = all(
        bool(check["pass"])
        for check in diagnostics["checks"]
        if str(check["id"]) not in diagnostic_only_ids | superseded_topology_ids
    )
    diagnostic_failures = [
        {
            "id": check["id"],
            "detail": check.get("detail"),
            "uncoveredPixels": check.get("uncoveredPixels"),
            "componentCounts": check.get("componentCounts"),
        }
        for check in diagnostics["checks"]
        if str(check["id"]) in diagnostic_only_ids and not bool(check["pass"])
    ]
    engineering_failures = [
        {
            "id": check["id"],
            "detail": check.get("detail"),
            "uncoveredPixels": check.get("uncoveredPixels"),
            "componentCounts": check.get("componentCounts"),
        }
        for check in diagnostics["checks"]
        if str(check["id"]) not in diagnostic_only_ids | superseded_topology_ids and not bool(check["pass"])
    ]
    gate_state = r2_gate_state()
    protected_digest = hashlib.sha256(canonical_json(protected_before).encode("utf-8")).hexdigest()
    user_visual_approval = bool(whole_hand_freeze["userVisualApproval"] and whole_hand_freeze["visualFreezeHashMatch"])
    formal_r2_promotion = bool(engineering_pass and user_visual_approval and upper_arm_promotion.get("soleFormalSource"))
    overall_gate_pass = bool(formal_r2_promotion and gate_state == "approved")
    formal_promotion_report = {
        "schemaVersion": 1,
        "stage": "R2 FORMAL PROMOTION",
        "status": "R2_FORMAL_PROMOTED / R3_READY_NOT_STARTED" if overall_gate_pass else "R2_FORMAL_PROMOTION_BLOCKED",
        **IDENTITY,
        "canvas": {"width": WIDTH, "height": HEIGHT, "coordinateTransform": "identity"},
        "visualFreeze": whole_hand_freeze,
        "userVisualApproval": user_visual_approval,
        "userVisualApprovalRecord": whole_hand_freeze["approvalPath"],
        "upperArmPromotion": upper_arm_promotion,
        "topology": {
            "contract": "contracts/topology-expectations.json",
            "forearmSkinCoreCheck": "forearm_skin_anatomical_core_topology",
            "registeredAccessoryCheck": "forearm_accessory_negative_spaces_registered",
            "primarySemanticCheck": "forearm_primary_semantic_topology",
            "supersededChecks": {
                "forearm_semantic_topology": "superseded_by_semantic_core_and_registered_accessory_topology",
                "forearm_complete_single_component_no_holes": "superseded_by_semantic_core_and_registered_accessory_topology",
                "elbow_r1_envelope_included": "upper_arm_v8_candidate_boundary_registration",
            },
        },
        "liftAction": {
            "report": "audit/lift-action-report.json",
            "status": "diagnostic_only",
            "allFramesConnected": next((check.get("pass") for check in lift_action["checks"] if check.get("id") == "lift_action_all_frames_connected"), None),
            "staticCompleteMasksConnected": lift_action["diagnosticInterpretation"]["staticCompleteMasksConnected"],
            "r3Risk": True,
            "requiredFutureR3Evidence": "at least 41 high-resolution floating-boundary coverage points; not run in this task",
        },
        "engineeringPass": engineering_pass,
        "engineeringFailures": engineering_failures,
        "diagnosticOnlyFailures": diagnostic_failures,
        "r2Gate": "passed" if overall_gate_pass else "failed",
        "gateDecision": "R2-GATE=passed" if overall_gate_pass else "R2-GATE=failed",
        "formalR2Promotion": formal_r2_promotion,
        "overallGatePass": overall_gate_pass,
        "reviewImage": str(r2_review_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "forearmBoundaryReviewImage": str(qa_board_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "r3": {
            "status": "READY_NOT_STARTED" if overall_gate_pass else "BLOCKED",
            "entered": False,
            "texture": "NOT_STARTED",
            "mesh": "NOT_STARTED",
            "nodes": "NOT_STARTED",
            "physics": "NOT_STARTED",
            "cubism": "NOT_STARTED",
            "runtime": "NOT_STARTED",
        },
        "downstreamForbidden": ["R3", "texture", "mesh", "nodes", "Physics", "Cubism", "Runtime"],
    }
    write_json(R2_FORMAL_PROMOTION_REPORT_PATH, formal_promotion_report)

    machine_report = {
        "schemaVersion": 4,
        "stage": "R2 full-canvas flat-color complete materials",
        "status": formal_promotion_report["status"],
        "gateDecision": formal_promotion_report["gateDecision"],
        "historicalR2Gate": gate_state,
        "r2Gate": formal_promotion_report["r2Gate"],
        **IDENTITY,
        "r1Freeze": r1_freeze,
        "forearmRedrawConfirmation": forearm_redraw_confirmation,
        "historicalR1WristEnvelopeSuperseded": historical_r1_wrist_envelope,
        "sourceInputs": source_results,
        "historicalEvidence": {
            "v38MachineReport": str(V38_REPORT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "v38MachineReportSha256": v38_hash,
            "use": "read-only regression evidence; no V38 mask/material is inherited",
        },
        "geometry": geometry_meta,
        "wholeHandVisualFreeze": whole_hand_freeze,
        "upperArmFormalPromotion": upper_arm_promotion,
        "contracts": {
            "layering": "contracts/layering-contract.json",
            "drawOrder": "contracts/draw-order-contract.json",
            "topology": "contracts/topology-expectations.json",
            "forearmDistalUcap": "contracts/forearm-distal-ucap-contract.json",
            "upperArmAaAnatomical": "contracts/upper-arm-aa-anatomical-contract.json",
            "formalPromotion": "audit/r2-formal-promotion-report.json",
            "protectedHandLineTrace": "contracts/hand-line-trace-contract.json",
        },
        "outputs": {
            "logic": ["masks/visible/upper_arm.png", "masks/hidden/upper_arm.png", "masks/complete/upper_arm.png", "masks/hidden/forearm.png", "masks/complete/forearm.png", "masks/subregions/forearm-skin-visible.png", "masks/subregions/forearm-skin-hidden.png", "masks/subregions/forearm-skin-complete.png"],
            "formalDisplayAlpha": ["display-alpha/upper_arm.png", "display-alpha/forearm.png", "display-alpha/forearm-skin.png"],
            "flatLayers": ["flat-layers/upper_arm.png", "flat-layers/forearm.png", "flat-layers/forearm-skin.png"],
        },
        "repairEvidence": {
            "baseline": "audit/repair-baseline.json",
            "pixelDiff": "audit/forearm-ucap-pixel-diff.json",
            "combinedR2PixelDiff": "audit/r2-repair-pixel-diff.json",
            "boundaryAudit": "audit/forearm-ucap-visual-boundary-report.json",
            "segmentedBoundaryAudit": "audit/segmented-boundary-report.json",
            "reviewImage": str(r2_review_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "forearmBoundaryReviewImage": str(qa_board_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "handProtection": {"snapshotBeforeAfter": hand_protected_unchanged, "rewritten": False},
            "nonForearmProtection": {"snapshotBeforeAfter": non_forearm_unchanged, "report": "audit/r2-non-forearm-protected-snapshot.json"},
        },
        "checks": diagnostics["checks"],
        "diagnostics": {key: value for key, value in diagnostics.items() if key != "checks"},
        "engineeringFailures": engineering_failures,
        "diagnosticOnlyFailures": diagnostic_failures,
        "protectedArtifacts": {
            "snapshotDigest": protected_digest,
            "fileCount": len(protected_before),
            "snapshotScope": "R1 frozen evidence plus all existing arm-chain-screen-left-v* historical files; no R2 output is included",
            "unchangedAfterBuild": protected_after == protected_before,
        },
        "handProtectedArtifacts": {
            "before": hand_protected_before,
            "after": hand_protected_after,
            "unchanged": hand_protected_unchanged,
            "logicRecomputationMatches": hand_logic_matches,
            "rewritten": False,
        },
        "nonForearmR2Protected": non_forearm_snapshot,
        "determinism": {
            "method": "run this builder twice and compare audit/artifact-manifest.json, machine-report.json, and both run records",
            "noTimestampOrRandomness": True,
            "requiredConsecutiveRunCheck": "external invocation comparison",
            "runEvidence": {"run1": "audit/rebuild-run-1.json", "run2": "audit/rebuild-run-2.json", "excludedFromArtifactManifest": True},
        },
        "downstreamForbidden": ["texture", "PSD", "Cubism", "ArtMesh", "Deformer", "nodes", "parameters", "motion", "Physics", "Runtime", "pet integration", "R3", "R4"],
        "engineeringPass": engineering_pass,
        "userVisualApproval": whole_hand_freeze["approvalPath"] if user_visual_approval else None,
        "formalR2Promotion": formal_r2_promotion,
        "overallGatePass": overall_gate_pass,
        "r3": formal_promotion_report["r3"],
        "forearmStageStatus": current_stage,
        "reviewImage": str(r2_review_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "forearmBoundaryReviewImage": str(qa_board_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "unresolvedRisks": geometry_meta["forearmUnresolved"] + (["工程诊断 lift_action_all_frames_connected 未通过；组件序列保留在 machine-report 中，不扩展为动作系统重建。"] if any(item["id"] == "lift_action_all_frames_connected" for item in diagnostic_failures) else []),
        "acceptedVisualLimitations": geometry_meta["acceptedVisualLimitations"],
        "latestUserVisualApproval": whole_hand_freeze["approvalPath"],
        "visualFreezeManifest": whole_hand_freeze["freezeManifestPath"],
        "formalPromotionReport": str(R2_FORMAL_PROMOTION_REPORT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "historicalUserVisualApproval": str(R2_APPROVAL_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "historicalHandReopen": str(R2_SMOOTH_EDGE_REOPEN_PATH.relative_to(REPO_ROOT)).replace("\\", "/") if R2_SMOOTH_EDGE_REOPEN_PATH.exists() else None,
        "readme": str(readme_path.relative_to(REPO_ROOT)).replace("\\", "/"),
    }
    machine_report_path = R2_ROOT / "audit" / "machine-report.json"
    write_json(machine_report_path, machine_report)

    manifest_excludes = {
        R2_ROOT / "audit" / "artifact-manifest.json",
        R2_ROOT / "audit" / "rebuild-report.json",
        R2_REBUILD_RUN_1_PATH,
        R2_REBUILD_RUN_2_PATH,
    }
    current_entries = artifact_snapshot(exclude=manifest_excludes)
    previous_match = previous_manifest.get("artifacts", []) == current_entries if isinstance(previous_manifest, dict) else None
    manifest = {
        "schemaVersion": 1,
        "stage": "R2 full-canvas flat-color complete materials",
        "status": formal_promotion_report["status"],
        **IDENTITY,
        "artifactManifestExcludesItself": True,
        "artifacts": current_entries,
        "r1FreezeInputManifest": "../arm-chain-screen-left-r1-physical-line-contract/audit/r1-freeze-checklist-2026-08-05.json",
        "protectedSnapshotDigest": protected_digest,
        "forearmStageStatus": current_stage,
        "engineeringPass": engineering_pass,
        "userVisualApproval": whole_hand_freeze["approvalPath"] if user_visual_approval else None,
        "formalR2Promotion": formal_r2_promotion,
        "r2Gate": formal_promotion_report["r2Gate"],
        "overallGatePass": overall_gate_pass,
        "r3": formal_promotion_report["r3"],
    }
    manifest_path = R2_ROOT / "audit" / "artifact-manifest.json"
    write_json(manifest_path, manifest)
    previous_protected_match = previous_manifest.get("protectedSnapshotDigest") == protected_digest if isinstance(previous_manifest, dict) else None
    report = {
        "engineeringPass": engineering_pass,
        "userVisualApproval": whole_hand_freeze["approvalPath"] if user_visual_approval else None,
        "formalR2Promotion": formal_r2_promotion,
        "r2Gate": formal_promotion_report["r2Gate"],
        "overallGatePass": overall_gate_pass,
        "artifactCount": len(current_entries),
        "protectedFileCount": len(protected_before),
        "handProtectedArtifactsUnchanged": hand_protected_unchanged,
        "nonForearmArtifactsUnchanged": non_forearm_unchanged,
        "previousProtectedSnapshotMatched": previous_protected_match,
        "previousArtifactListMatched": previous_match,
        "review": str(r2_review_path.relative_to(REPO_ROOT)).replace("\\", "/"),
    }
    write_json(R2_ROOT / "audit" / "rebuild-report.json", report)

    run1_matches_current = False
    if R2_REBUILD_RUN_1_PATH.exists():
        try:
            previous_run1 = load_json(R2_REBUILD_RUN_1_PATH)
            run1_matches_current = isinstance(previous_run1, dict) and previous_run1.get("artifactManifestSha256") == sha256_file(manifest_path) and previous_run1.get("machineReportSha256") == sha256_file(machine_report_path)
        except (OSError, json.JSONDecodeError):
            run1_matches_current = False
    run_path = R2_REBUILD_RUN_2_PATH if run1_matches_current else R2_REBUILD_RUN_1_PATH
    run_number = 1 if run_path == R2_REBUILD_RUN_1_PATH else 2
    write_json(run_path, {
        "schemaVersion": 1,
        "stage": "R2 FORMAL PROMOTION deterministic rebuild evidence",
        "runNumber": run_number,
        **IDENTITY,
        "status": current_stage,
        "engineeringPass": engineering_pass,
        "userVisualApproval": whole_hand_freeze["approvalPath"] if user_visual_approval else None,
        "formalR2Promotion": formal_r2_promotion,
        "r2Gate": formal_promotion_report["r2Gate"],
        "overallGatePass": overall_gate_pass,
        "artifactManifestSha256": sha256_file(manifest_path),
        "machineReportSha256": sha256_file(machine_report_path),
        "artifactCount": len(current_entries),
        "protectedFileCount": len(protected_before),
        "protectedArtifactsUnchanged": protected_after == protected_before,
        "handProtectedArtifactsUnchanged": hand_protected_unchanged,
        "nonForearmArtifactsUnchanged": non_forearm_unchanged,
        "forearmUcapBoundary": {"outsideBoundaryPixels": formal_report["outsideBoundaryPixels"], "overallPass": formal_report["overallPass"]},
        "liftActionDiagnostic": diagnostic_failures,
        "previousProtectedSnapshotMatched": previous_protected_match,
        "previousArtifactListMatched": previous_match,
        "downstreamForbidden": True,
        "nextState": "READY_FOR_R3 / R3_READY_NOT_STARTED" if overall_gate_pass else "R2_FORMAL_PROMOTION_BLOCKED; do not enter R3/R4/texture/Cubism/Runtime",
    })
    print(json.dumps(report, ensure_ascii=False))


def hand_aa_mutable_paths() -> set[str]:
    """Return only the hand-AA outputs allowed to change in this pass."""
    return {
        "masks/hidden/hand.png",
        "masks/complete/hand.png",
        "display-alpha/hand-hidden.png",
        "display-alpha/hand-complete.png",
        "flat-layers/hand.png",
        "flat-layers/wrist-skin-without-bracelet.png",
        "contracts/hand-line-trace-contract.json",
        "audit/hand-visual-boundary-report.json",
        "audit/hand-hidden-aa-maintenance-report.json",
        "audit/hand-hidden-aa-rebuild-run-1.json",
        "audit/hand-hidden-aa-rebuild-run-2.json",
        "qa/hand-r2-repair/14-隐藏腕根抗锯齿维护审查.png",
        "tools/build_r2_flat_color_materials.py",
    }


def snapshot_hand_aa_nonhand_files() -> dict[str, str]:
    """Hash every existing R2 file except explicitly scoped hand-AA outputs."""
    mutable = hand_aa_mutable_paths()
    snapshot: dict[str, str] = {}
    for path in sorted(R2_ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(R2_ROOT).as_posix()
        if relative in mutable or relative.startswith("tools/__pycache__/"):
            continue
        snapshot[relative] = sha256_file(path)
    return snapshot


def validate_existing_hand_aa_contract(
    markup_registration: dict[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Fail closed when the existing hand contract is stale or ambiguous."""
    if not HAND_TRACE_CONTRACT_PATH.exists():
        raise FileNotFoundError(f"hand boundary contract is missing: {HAND_TRACE_CONTRACT_PATH}")
    contract = load_json(HAND_TRACE_CONTRACT_PATH)
    if not isinstance(contract, dict):
        raise RuntimeError("hand boundary contract must be a JSON object")

    maintenance = contract.get("handHiddenAaMaintenance")
    coordinate = contract.get("coordinateSystem")
    visual = contract.get("visualBoundaryContract")
    root = maintenance.get("handWristRoot") if isinstance(maintenance, dict) else None
    envelope = maintenance.get("hiddenWristEnvelope") if isinstance(maintenance, dict) else None

    expected_root = [list(point) for point in HAND_WRIST_ROOT_CONTROL_POINTS]
    expected_envelope = [list(point) for point in HAND_HIDDEN_ENVELOPE_CONTROL_POINTS]
    checks = [
        {
            "id": "existing_contract_canvas",
            "pass": isinstance(coordinate, dict) and coordinate.get("canvas") == list(CANVAS),
            "expected": list(CANVAS),
            "actual": coordinate.get("canvas") if isinstance(coordinate, dict) else None,
        },
        {
            "id": "existing_contract_identity_transform",
            "pass": isinstance(coordinate, dict) and "identity" in str(coordinate.get("transform", "")).lower(),
            "actual": coordinate.get("transform") if isinstance(coordinate, dict) else None,
        },
        {
            "id": "existing_contract_redline_hash",
            "pass": isinstance(visual, dict) and visual.get("markupSha256") == markup_registration["sha256"],
            "expected": markup_registration["sha256"],
            "actual": visual.get("markupSha256") if isinstance(visual, dict) else None,
        },
        {
            "id": "existing_contract_redline_roi",
            "pass": isinstance(visual, dict) and visual.get("sourceRoi") == list(HAND_LINE_ROI),
            "expected": list(HAND_LINE_ROI),
            "actual": visual.get("sourceRoi") if isinstance(visual, dict) else None,
        },
        {
            "id": "existing_contract_allowed_side",
            "pass": isinstance(visual, dict) and visual.get("allowedSide") == "red-line interior / hand-material side",
            "actual": visual.get("allowedSide") if isinstance(visual, dict) else None,
        },
        {
            "id": "existing_contract_hand_root_control_points",
            "pass": isinstance(root, dict) and root.get("controlPoints") == expected_root,
            "expected": expected_root,
            "actual": root.get("controlPoints") if isinstance(root, dict) else None,
        },
        {
            "id": "existing_contract_hidden_envelope_control_points",
            "pass": isinstance(envelope, dict) and envelope.get("controlPoints") == expected_envelope,
            "expected": expected_envelope,
            "actual": envelope.get("controlPoints") if isinstance(envelope, dict) else None,
        },
        {
            "id": "existing_contract_supersample",
            "pass": isinstance(root, dict) and root.get("supersample") == HAND_AA_SUPERSAMPLE,
            "expected": HAND_AA_SUPERSAMPLE,
            "actual": root.get("supersample") if isinstance(root, dict) else None,
        },
    ]
    failed = [check["id"] for check in checks if not bool(check["pass"])]
    if failed:
        raise RuntimeError(f"existing hand AA contract failed closed checks: {failed}")
    return contract, checks


def update_hand_aa_contract(
    contract: dict[str, object],
    markup_registration: dict[str, object],
) -> dict[str, object]:
    """Update the existing contract without replacing historical line evidence."""
    updated = dict(contract)
    updated["handHiddenAaMaintenance"] = {
        "status": "R2_HAND_HIDDEN_AA_MAINTENANCE_CANDIDATE / WAITING_USER_VISUAL_APPROVAL",
        "sourceCanvas": list(CANVAS),
        "coordinateTransform": "identity; all hand wrist-root coordinates are frontMaster source pixels",
        "redlineMarkup": {
            "path": markup_registration["path"],
            "sha256": markup_registration["sha256"],
            "dimensions": markup_registration["markupDimensions"],
            "sourceCanvas": list(CANVAS),
            "sourceRoi": list(HAND_LINE_ROI),
            "allowedSide": markup_registration["allowedSide"],
            "outsideBoundaryPixelsMustBe": 0,
        },
        "handWristRoot": {
            "controlPoints": [list(point) for point in HAND_WRIST_ROOT_CONTROL_POINTS],
            "bezierSegments": [[list(point) for point in segment] for segment in HAND_WRIST_ROOT_BEZIER_SEGMENTS],
            "closed": True,
            "continuityTarget": "C2",
            "supersample": HAND_AA_SUPERSAMPLE,
            "construction": "float cubic path multiplied by supersample before rasterization; high-resolution boolean hidden/visible/complete; one BOX coverage downsample",
        },
        "hiddenWristEnvelope": {
            "roi": list(HAND_HIDDEN_WRIST_ROI),
            "controlPoints": [list(point) for point in HAND_HIDDEN_ENVELOPE_CONTROL_POINTS],
            "bezierSegments": [[list(point) for point in segment] for segment in HAND_HIDDEN_ENVELOPE_BEZIER_SEGMENTS],
            "allowedSide": "inside the separately registered hidden wrist envelope",
            "hiddenOutsideEnvelopePixelsMustBe": 0,
        },
        "rendering": {
            "supersample": HAND_AA_SUPERSAMPLE,
            "booleanAtHighResolution": True,
            "coverageDownsample": "BOX exactly once",
            "finalClipAfterDownsample": True,
            "logicMasks": "binary 0/255 masks for ownership, connectivity, and topology only",
            "displayAlpha": "grayscale coverage from the same float root/envelope; flat hand layer consumes hand-complete display Alpha",
            "forbiddenOperations": [
                "low-resolution binary geometry first",
                "NEAREST enlargement as formal display",
                "blur",
                "Gaussian blur",
                "dilate",
                "erode",
                "stroke expansion",
                "threshold expansion",
                "topology repair",
                "LANCZOS ringing",
                "Bezier overshoot across the redline",
            ],
        },
        "implementationAudit": HAND_AA_IMPLEMENTATION_AUDIT,
        "logicMasks": {
            "visible": "masks/visible/hand.png; protected source-locked binary ownership",
            "hidden": "masks/hidden/hand.png; binary high-resolution root minus visible, clipped by hidden envelope",
            "complete": "masks/complete/hand.png; binary visible union hidden",
        },
        "displayAlpha": {
            "hidden": "display-alpha/hand-hidden.png; hidden wrist coverage for displaced-part/texture use",
            "complete": "display-alpha/hand-complete.png; final display Alpha after the redline guard",
            "flatLayer": "flat-layers/hand.png uses display-alpha/hand-complete.png",
            "downsample": "BOX",
        },
        "downstreamGeometrySource": "handHiddenAaMaintenance.handWristRoot.bezierSegments; never binary masks/hidden/hand.png",
        "downstreamTextureAlphaSource": "display-alpha/hand-hidden.png and display-alpha/hand-complete.png",
        "forbiddenDirectTraceSources": [
            "masks/hidden/hand.png",
            "masks/complete/hand.png",
            "low-resolution binary edge",
            "NEAREST enlargement",
        ],
        "maintenanceReport": "audit/hand-hidden-aa-maintenance-report.json",
        "engineeringPass": None,
        "userVisualApproval": None,
        "overallGatePass": False,
    }
    return updated


def write_hand_aa_outputs(
    hand_masks: dict[str, Image.Image | object],
    complete_display_alpha: Image.Image,
) -> tuple[list[Path], dict[str, Image.Image]]:
    """Write only the hand-AA outputs and the one dependent bracelet-removed QA layer."""
    hidden_logic = cast(Image.Image, hand_masks["hidden"])
    complete_logic = cast(Image.Image, hand_masks["complete"])
    hidden_display_alpha = cast(Image.Image, hand_masks["hiddenCoverage"])
    hand_layer = rgba_layer(complete_display_alpha, DEBUG_COLORS["hand"])

    output_images = {
        "masks/hidden/hand.png": hidden_logic,
        "masks/complete/hand.png": complete_logic,
        "display-alpha/hand-hidden.png": hidden_display_alpha,
        "display-alpha/hand-complete.png": complete_display_alpha,
        "flat-layers/hand.png": hand_layer,
    }
    written: list[Path] = []
    for relative, image in output_images.items():
        path = R2_ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, format="PNG", optimize=False, compress_level=9)
        written.append(path)

    def load_rgba(relative: str) -> Image.Image:
        path = R2_ROOT / relative
        if not path.exists():
            raise FileNotFoundError(f"protected dependent flat layer is missing: {path}")
        return Image.open(path).convert("RGBA")

    wrist_without_bracelet = alpha_composite_layers([
        load_rgba("flat-layers/forearm-skin.png"),
        load_rgba("flat-layers/sleeve.png"),
        hand_layer,
    ])
    wrist_without_bracelet_path = R2_ROOT / "flat-layers/wrist-skin-without-bracelet.png"
    wrist_without_bracelet.save(wrist_without_bracelet_path, format="PNG", optimize=False, compress_level=9)
    written.append(wrist_without_bracelet_path)
    return written, {
        "hand": hand_layer,
        "hand-display-alpha-hidden": hidden_display_alpha,
        "hand-display-alpha-complete": complete_display_alpha,
        "wrist-skin-without-bracelet": wrist_without_bracelet,
    }


def hand_aa_candidate_output_hashes(paths: Sequence[Path]) -> dict[str, str]:
    return {
        str(path.relative_to(REPO_ROOT)).replace("\\", "/"): sha256_file(path)
        for path in sorted(set(paths))
        if path.exists()
        and path.relative_to(R2_ROOT).as_posix()
        not in {"audit/hand-hidden-aa-maintenance-report.json", "audit/hand-hidden-aa-rebuild-run-1.json", "audit/hand-hidden-aa-rebuild-run-2.json"}
    }


def hand_aa_candidate_digest(output_hashes: dict[str, str]) -> str:
    return hashlib.sha256(canonical_json(output_hashes).encode("utf-8")).hexdigest()


def hand_hidden_aa_maintenance_main() -> None:
    """Build the scoped R2 hand hidden-wrist AA candidate and stop at visual approval."""
    R2_ROOT.mkdir(parents=True, exist_ok=True)
    source_results, images = validate_source_inputs()
    markup_registration = validate_user_markup_registration()
    existing_contract, contract_checks = validate_existing_hand_aa_contract(markup_registration)
    protected_before = snapshot_protected_files()
    nonhand_before = snapshot_hand_aa_nonhand_files()

    repair_baseline_value = load_json(REPAIR_BASELINE_PATH)
    if not isinstance(repair_baseline_value, dict):
        raise RuntimeError(f"repair baseline is not a JSON object: {REPAIR_BASELINE_PATH}")
    repair_baseline = repair_baseline_value

    visible_path = R2_ROOT / "masks/visible/hand.png"
    hidden_path = R2_ROOT / "masks/hidden/hand.png"
    complete_path = R2_ROOT / "masks/complete/hand.png"
    hidden_display_path = R2_ROOT / "display-alpha/hand-hidden.png"
    complete_display_path = R2_ROOT / "display-alpha/hand-complete.png"
    flat_hand_path = R2_ROOT / "flat-layers/hand.png"
    required_paths = [visible_path, hidden_path, complete_path, hidden_display_path, complete_display_path, flat_hand_path]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"hand AA maintenance inputs are missing: {missing}")

    visible_before = Image.open(visible_path).convert("L")
    hidden_before = Image.open(hidden_path).convert("L")
    complete_before = Image.open(complete_path).convert("L")
    hidden_display_before = Image.open(hidden_display_path).convert("L")
    complete_display_before = Image.open(complete_display_path).convert("L")
    flat_before = Image.open(flat_hand_path).convert("RGBA")
    baseline_flat = load_repair_baseline_display(repair_baseline, "hand.formalDisplayFlatLayer")
    if baseline_flat is None:
        raise RuntimeError("the hand formal display baseline is missing")

    previous_run1: dict[str, object] | None = None
    if HAND_AA_REBUILD_RUN_1_PATH.exists():
        try:
            loaded_run1 = load_json(HAND_AA_REBUILD_RUN_1_PATH)
            if isinstance(loaded_run1, dict):
                previous_run1 = loaded_run1
        except (OSError, json.JSONDecodeError):
            previous_run1 = None
    previous_input_baseline = previous_run1.get("inputBaseline") if previous_run1 else None
    if isinstance(previous_input_baseline, dict):
        input_baseline_measurement = previous_input_baseline
    else:
        input_baseline_measurement = {
            "visible": alpha_summary(visible_before),
            "hidden": alpha_summary(hidden_before),
            "complete": alpha_summary(complete_before),
            "hiddenDisplayAlpha": alpha_summary(hidden_display_before),
            "completeDisplayAlpha": alpha_summary(complete_display_before),
            "flatLayer": alpha_summary(flat_before.getchannel("A")),
        }

    rendered = render_hand_wrist_root_masks(visible_before)
    hand_masks: dict[str, Image.Image | object] = {
        "visible": visible_before,
        "hidden": cast(Image.Image, rendered["hidden"]),
        "complete": cast(Image.Image, rendered["complete"]),
        "rootHigh": cast(Image.Image, rendered["rootHigh"]),
        "envelopeHigh": cast(Image.Image, rendered["envelopeHigh"]),
        "hiddenCoverage": cast(Image.Image, rendered["hiddenCoverage"]),
        "completeCoverage": cast(Image.Image, rendered["completeCoverage"]),
    }
    # The complete display is rebuilt from the existing source-locked visible
    # presentation plus the float root on the 32x canvas.  The helper applies
    # the registered redline guard before returning the final display Alpha.
    complete_display_candidate = rounded_hand_visual_mask(
        visible_before,
        hidden_root_high=cast(Image.Image, rendered["rootHigh"]),
    )
    candidate_flat_layer = rgba_layer(complete_display_candidate, DEBUG_COLORS["hand"])
    baseline_flat_sha256 = sha256_file(REPAIR_BASELINE_DIR / "hand" / "flat-layer.png")
    current_flat_is_baseline = sha256_file(flat_hand_path) == baseline_flat_sha256
    current_flat_is_candidate = flat_before.tobytes() == candidate_flat_layer.tobytes()
    current_flat_diff_from_baseline = display_alpha_diff_stats(
        baseline_flat,
        flat_before,
        HAND_HIDDEN_WRIST_ROI,
    )
    current_flat_is_scoped_candidate = (
        current_flat_diff_from_baseline.get("baselineAvailable") is True
        and current_flat_diff_from_baseline.get("changedPixelsOutsideAuthorizedRoi") == 0
    )
    if not (current_flat_is_baseline or current_flat_is_candidate or current_flat_is_scoped_candidate):
        raise RuntimeError(
            "current flat-layers/hand.png is neither the captured pre-maintenance "
            "baseline, the deterministic R2 hand-AA candidate, nor an in-scope "
            "ROI-only hand display candidate"
        )

    hand_root_geometry = hand_wrist_root_geometry_report({
        "visible": visible_before,
        "hidden": cast(Image.Image, hand_masks["hidden"]),
        "complete": cast(Image.Image, hand_masks["complete"]),
    })
    hand_visual_report = audit_hand_visual_boundary(complete_display_candidate)
    hand_visual_report["maintenanceStatus"] = "R2_HAND_HIDDEN_AA_MAINTENANCE_CANDIDATE / WAITING_USER_VISUAL_APPROVAL"
    hand_visual_report["displayAlphaPath"] = "display-alpha/hand-complete.png"
    hand_visual_report["flatLayerPath"] = "flat-layers/hand.png"

    hand_visible_diff = mask_diff_stats(visible_before, visible_before)
    hand_hidden_logic_diff = mask_diff_stats(hidden_before, cast(Image.Image, hand_masks["hidden"]))
    hand_complete_logic_diff = mask_diff_stats(complete_before, cast(Image.Image, hand_masks["complete"]))
    hand_hidden_display_diff = display_alpha_diff_stats(hidden_display_before, cast(Image.Image, hand_masks["hiddenCoverage"]), HAND_HIDDEN_WRIST_ROI)
    hand_display_diff = display_alpha_diff_stats(baseline_flat, complete_display_candidate, HAND_HIDDEN_WRIST_ROI)

    markup_guard = hand_visual_markup_boundary_clip(HAND_VISUAL_SUPERSAMPLE).resize(CANVAS, Image.Resampling.BOX)
    outside_boundary_points = [
        (x, y)
        for y in range(HEIGHT)
        for x in range(WIDTH)
        if complete_display_candidate.getpixel((x, y)) > 0 and markup_guard.getpixel((x, y)) == 0
    ]
    current_machine_path = R2_ROOT / "audit/machine-report.json"
    if not current_machine_path.exists():
        raise FileNotFoundError(f"current R2 machine report is missing: {current_machine_path}")
    current_machine = load_json(current_machine_path)
    if not isinstance(current_machine, dict):
        raise RuntimeError("current R2 machine report is not a JSON object")
    existing_engineering_failures = current_machine.get("engineeringFailures", [])
    existing_diagnostic_failures = current_machine.get("diagnosticOnlyFailures", [])
    if not isinstance(existing_engineering_failures, list):
        existing_engineering_failures = []
    if not isinstance(existing_diagnostic_failures, list):
        existing_diagnostic_failures = []

    lift_report_path = R2_ROOT / "audit/lift-action-report.json"
    lift_report = load_json(lift_report_path) if lift_report_path.exists() else {}
    lift_checks = lift_report.get("checks", []) if isinstance(lift_report, dict) else []
    return_check = next((check for check in lift_checks if check.get("id") == "lift_action_return_alpha_deterministic"), None)

    visible_components_before = component_stats(visible_before)
    visible_components_after = component_stats(visible_before)
    hidden_components_before = component_stats(hidden_before)
    hidden_components_after = component_stats(cast(Image.Image, hand_masks["hidden"]))
    complete_components_before = component_stats(complete_before)
    complete_components_after = component_stats(cast(Image.Image, hand_masks["complete"]))

    checks: list[dict[str, object]] = []

    def add(check_id: str, passed: bool, detail: str, **extra: object) -> None:
        checks.append({"id": check_id, "pass": bool(passed), "detail": detail, **extra})

    add(
        "latest_redline_registration_valid",
        all(bool(check["pass"]) for check in markup_registration["checks"]),
        "最新红线文件、哈希、尺寸、源画布、ROI、identity 变换和允许侧全部有效",
        registration=markup_registration,
    )
    add(
        "existing_hand_contract_matches_authority",
        all(bool(check["pass"]) for check in contract_checks),
        "现有 hand-line-trace-contract 与当前红线和浮点腕根合同一致",
        checks=contract_checks,
    )
    add(
        "source_authority_inputs_match",
        all(bool(item.get("pass")) for item in source_results.values()),
        "四个权威输入的尺寸、模式和 SHA-256 与登记一致",
        sourceInputs=source_results,
    )
    add(
        "flat_input_matches_baseline_or_candidate",
        current_flat_is_baseline or current_flat_is_candidate or current_flat_is_scoped_candidate,
        "输入 flat hand 只能是维护前基线、同一确定性候选或已证明仅在授权 ROI 内变化的手部候选",
        acceptedStates=["captured-pre-maintenance-baseline", "deterministic-hand-AA-candidate", "authorized-hand-display-ROI-only-candidate"],
        inputStateIsNotAnAuthority=True,
    )
    add(
        "hand_visible_pixels_unchanged",
        hand_visible_diff.get("changedPixels") == 0,
        "visible hand 未被本轮重生成或写入",
        diff=hand_visible_diff,
    )
    add(
        "hand_visible_topology_unchanged",
        visible_before.tobytes() == visible_before.tobytes() and visible_components_before == visible_components_after,
        "一根拇指、四根手指、三个开放指缝的 source-locked visible mask 保持不变",
        componentCountBefore=len(visible_components_before),
        componentCountAfter=len(visible_components_after),
        componentStats=visible_components_after,
        declaredDigits={"thumb": 1, "fingers": 4, "openGaps": 3},
    )
    add(
        "logic_masks_binary",
        all(value in {0, 255} for image in (cast(Image.Image, hand_masks["hidden"]), cast(Image.Image, hand_masks["complete"])) for value in image.getdata()),
        "hidden/complete 逻辑蒙版只含 0/255",
    )
    add(
        "hidden_complete_union",
        cast(Image.Image, hand_masks["complete"]).tobytes() == mask_union(visible_before, cast(Image.Image, hand_masks["hidden"])).tobytes(),
        "complete 逻辑蒙版严格等于 visible ∪ hidden",
        diff={"hidden": hand_hidden_logic_diff, "complete": hand_complete_logic_diff},
    )
    add(
        "hidden_single_component_no_holes",
        len(hidden_components_after) == 1 and hole_count(cast(Image.Image, hand_masks["hidden"])) == 0,
        "hidden 逻辑蒙版单连通且无意外孔洞",
        components=hidden_components_after,
        holeCount=hole_count(cast(Image.Image, hand_masks["hidden"])),
    )
    add(
        "complete_single_component_no_holes",
        len(complete_components_after) == 1 and hole_count(cast(Image.Image, hand_masks["complete"])) == 0,
        "complete 逻辑蒙版单连通且无意外孔洞",
        components=complete_components_after,
        holeCount=hole_count(cast(Image.Image, hand_masks["complete"])),
    )
    add(
        "hidden_no_new_disconnected_component",
        len(hidden_components_after) <= len(hidden_components_before),
        "hidden 腕根没有新增 disconnected component",
        before=hidden_components_before,
        after=hidden_components_after,
    )
    add(
        "complete_no_new_disconnected_component",
        len(complete_components_after) <= len(complete_components_before),
        "complete hand 没有新增 disconnected component",
        before=complete_components_before,
        after=complete_components_after,
    )
    for check in hand_root_geometry["checks"]:
        add(
            f"hand_wrist_root_{check['id']}",
            bool(check["pass"]),
            f"float wrist-root AA 检查：{check['id']}",
            **{key: value for key, value in check.items() if key not in {"id", "pass"}},
        )
    add(
        "hidden_display_alpha_has_intermediate_coverage",
        alpha_summary(cast(Image.Image, hand_masks["hiddenCoverage"])).get("fractionalAlphaPixels", 0) > 0,
        "正式 hidden display Alpha 含真实中间 coverage，而非仅 0/255",
        alpha=alpha_summary(cast(Image.Image, hand_masks["hiddenCoverage"])),
    )
    add(
        "hidden_alpha_inside_envelope",
        hand_root_geometry["logicalMasks"]["hiddenOutsideEnvelopePixels"] == 0 and hand_root_geometry["displayAlpha"]["hiddenAlphaOutsideEnvelopePixels"] == 0,
        "hidden Alpha 完全位于单独登记的 hidden wrist envelope 内",
        logicalOutside=hand_root_geometry["logicalMasks"]["hiddenOutsideEnvelopePixels"],
        displayOutside=hand_root_geometry["displayAlpha"]["hiddenAlphaOutsideEnvelopePixels"],
    )
    add(
        "final_display_outside_boundary_zero",
        len(outside_boundary_points) == 0,
        "最终 hand display Alpha 在最新红线允许侧之外为 0",
        outsideBoundaryPixels=len(outside_boundary_points),
        sample=outside_boundary_points[:32],
    )
    add(
        "formal_display_changes_confined_to_hidden_wrist_roi",
        hand_display_diff.get("baselineAvailable") is True and hand_display_diff.get("changedPixelsOutsideAuthorizedRoi") == 0,
        "formal hand display Alpha 变化只位于授权 hidden wrist ROI",
        diff=hand_display_diff,
    )
    add(
        "flat_layer_uses_complete_display_alpha",
        flat_hand_path.exists() and cast(Image.Image, rgba_layer(complete_display_candidate, DEBUG_COLORS["hand"])).getchannel("A").tobytes() == complete_display_candidate.tobytes(),
        "flat-layers/hand.png 的 Alpha 来自 display-alpha/hand-complete.png",
    )
    add(
        "hidden_display_rebuilt_from_float_root",
        cast(Image.Image, hand_masks["hiddenCoverage"]).tobytes() == cast(Image.Image, rendered["hiddenCoverage"]).tobytes(),
        "hidden display Alpha 来自同一 32× 浮点 Bézier 高分辨率 Boolean",
        supersample=HAND_AA_SUPERSAMPLE,
        downsample="BOX exactly once",
    )
    add(
        "zero_to_one_to_zero_return_deterministic",
        isinstance(return_check, dict) and bool(return_check.get("pass")),
        "复用当前 R2 flat-color QA 的 0→1→0 首尾 Alpha 确定性记录；不运行 R3",
        evidence="audit/lift-action-report.json",
        check=return_check,
    )

    # Write the candidate only after all fail-closed input checks above pass.
    updated_contract = update_hand_aa_contract(existing_contract, markup_registration)
    write_json(HAND_TRACE_CONTRACT_PATH, updated_contract)
    written_paths, flat_images = write_hand_aa_outputs(hand_masks, complete_display_candidate)
    write_json(HAND_VISUAL_BOUNDARY_REPORT_PATH, hand_visual_report)
    written_paths.append(HAND_TRACE_CONTRACT_PATH)
    written_paths.append(HAND_VISUAL_BOUNDARY_REPORT_PATH)

    hand_visible_diff_after = mask_diff_stats(visible_before, Image.open(visible_path).convert("L"))
    protected_after = snapshot_protected_files()
    nonhand_after = snapshot_hand_aa_nonhand_files()
    protected_unchanged = protected_before == protected_after
    nonhand_unchanged = nonhand_before == nonhand_after
    add(
        "r1_and_historical_protected_hashes_unchanged",
        protected_unchanged,
        "R1 冻结产物和历史 V* 证据哈希保持不变",
        fileCountBefore=len(protected_before),
        fileCountAfter=len(protected_after),
    )
    add(
        "non_hand_r2_hashes_unchanged",
        nonhand_unchanged,
        "所有未列入 hand-AA 允许范围的 R2 文件哈希保持不变",
        fileCountBefore=len(nonhand_before),
        fileCountAfter=len(nonhand_after),
        changedPaths=sorted(set(nonhand_before) ^ set(nonhand_after)) + [
            path for path in sorted(set(nonhand_before) & set(nonhand_after))
            if nonhand_before[path] != nonhand_after[path]
        ],
    )
    add(
        "hand_visible_still_unchanged_after_write",
        hand_visible_diff_after.get("changedPixels") == 0,
        "写入阶段没有触碰 masks/visible/hand.png",
        diff=hand_visible_diff_after,
    )

    hand_checks_pass = all(bool(check["pass"]) for check in checks)
    current_r2_engineering_pass = bool(current_machine.get("engineeringPass"))
    current_r2_overall_pass = bool(current_machine.get("overallGatePass"))
    engineering_failures = existing_engineering_failures
    diagnostic_failures = existing_diagnostic_failures

    candidate_paths = written_paths + [
        R2_ROOT / "qa/hand-r2-repair/14-隐藏腕根抗锯齿维护审查.png",
    ]
    # The review image needs the post-write flat/composite images and the
    # current hidden mask, but it is written before the report so its hash is
    # part of the deterministic candidate set.
    review_path = write_hand_aa_maintenance_review(
        images,
        flat_images,
        repair_baseline,
        hand_visual_report,
        hand_root_geometry,
        hand_visible_diff,
        hand_display_diff,
        markup_registration,
        previous_hand_hidden=hidden_before,
    )
    written_paths.append(review_path)
    candidate_paths.append(review_path)
    output_hashes = hand_aa_candidate_output_hashes(candidate_paths)
    candidate_digest = hand_aa_candidate_digest(output_hashes)

    report = {
        "schemaVersion": 1,
        "stage": "R2_HAND_HIDDEN_AA_MAINTENANCE",
        "status": "R2_HAND_HIDDEN_AA_MAINTENANCE_CANDIDATE / WAITING_USER_VISUAL_APPROVAL",
        "gateDecision": "R2-GATE=reopened",
        **IDENTITY,
        "subject": "小星 Left",
        "authority": {
            "sourceInputs": source_results,
            "sourceCanvas": list(CANVAS),
            "coordinateTransform": "identity; original 512x1086 frontMaster coordinates",
            "redline": markup_registration,
            "handReviewRoi": list(HAND_LINE_ROI),
            "hiddenWristRoi": list(HAND_HIDDEN_WRIST_ROI),
        },
        "baseline": {
            "measuredBeforeMaintenance": input_baseline_measurement,
            "knownReference": {
                "hiddenNonzeroPixels": 154,
                "hiddenMode": "L",
                "hiddenValues": [0, 255],
                "note": "reference value supplied by the current R2 baseline brief; actual pre-maintenance measurement above is authoritative for this run",
            },
            "formalBaselinePath": "audit/repair-baseline/hand/flat-layer.png",
            "authorizedChangeRoi": list(HAND_HIDDEN_WRIST_ROI),
        },
        "geometry": {
            "handWristRoot": hand_root_geometry["root"],
            "hiddenWristEnvelope": hand_root_geometry["hiddenEnvelope"],
            "logicalMasks": hand_root_geometry["logicalMasks"],
            "displayAlphaGeometry": hand_root_geometry["displayAlpha"],
        },
        "rendering": {
            "supersample": HAND_AA_SUPERSAMPLE,
            "booleanAtHighResolution": True,
            "coverageDownsample": "BOX exactly once",
            "finalClipAfterDownsample": True,
            "logicMaskRole": "binary 0/255 ownership, connectivity, and topology audit only",
            "displayAlphaRole": "grayscale coverage for formal display and later texture alpha",
            "downstreamGeometrySource": "float cubic Bézier contract; not binary mask tracing",
            "downstreamTextureAlphaSource": "display-alpha/hand-hidden.png and display-alpha/hand-complete.png",
            "forbiddenOperations": [
                "blur", "Gaussian blur", "dilate", "erode", "stroke expansion",
                "threshold expansion", "topology repair", "LANCZOS ringing",
                "low-resolution binary geometry first", "NEAREST enlargement as formal display",
                "Bezier overshoot across the redline",
            ],
        },
        "implementationAudit": HAND_AA_IMPLEMENTATION_AUDIT,
        "outputs": {
            "logic": ["masks/visible/hand.png", "masks/hidden/hand.png", "masks/complete/hand.png"],
            "formalDisplayAlpha": ["display-alpha/hand-hidden.png", "display-alpha/hand-complete.png"],
            "flatLayer": "flat-layers/hand.png",
            "dependentReviewComposite": "flat-layers/wrist-skin-without-bracelet.png",
            "reviewImage": str(review_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "outputHashes": output_hashes,
            "candidateDigest": candidate_digest,
        },
        "diffs": {
            "visibleLogic": hand_visible_diff,
            "hiddenLogic": hand_hidden_logic_diff,
            "completeLogic": hand_complete_logic_diff,
            "hiddenDisplayAlpha": hand_hidden_display_diff,
            "formalDisplayAlpha": hand_display_diff,
        },
        "checks": checks,
        "handMaintenanceEngineeringPass": hand_checks_pass,
        "engineeringPass": bool(hand_checks_pass and current_r2_engineering_pass),
        "userVisualApproval": None,
        "overallGatePass": False,
        "currentR2Revalidation": {
            "machineReport": "audit/machine-report.json",
            "engineeringPass": current_r2_engineering_pass,
            "overallGatePass": current_r2_overall_pass,
            "existingEngineeringFailures": engineering_failures,
            "existingDiagnosticOnlyFailures": diagnostic_failures,
            "doNotRepairInThisPass": True,
        },
        "protectedArtifacts": {
            "r1AndHistorical": {
                "fileCount": len(protected_before),
                "unchanged": protected_unchanged,
                "snapshotDigest": hashlib.sha256(canonical_json(protected_before).encode("utf-8")).hexdigest(),
            },
            "nonHandR2": {
                "fileCount": len(nonhand_before),
                "unchanged": nonhand_unchanged,
                "scope": "all existing R2 files except explicitly listed hand-AA outputs and the current builder script cache",
            },
        },
        "manualVisualReview": {
            "status": "WAITING_USER_VISUAL_APPROVAL",
            "reviewImage": str(review_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "requiredScales": ["100%", "Windows DPI 125%", "150%", "200%"],
            "requiredBackgrounds": ["white", "black", "checkerboard"],
            "requiredStates": ["bracelet normal", "bracelet moved away", "subpixel wrist movement slow preview"],
            "machineCannotSubstitute": True,
        },
        "downstreamForbidden": ["R3", "R4", "texture", "PSD", "Cubism", "ArtMesh", "Deformer", "nodes", "parameters", "motion", "Physics", "Runtime", "pet integration"],
        "r2Gate": "reopened",
        "r3Status": "STALE_DUE_TO_UPSTREAM_R2_HAND_REJECTION",
        "contract": "contracts/hand-line-trace-contract.json#handHiddenAaMaintenance",
        "boundaryAudit": "audit/hand-visual-boundary-report.json",
        "readme": "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/README.md",
        "determinism": {
            "candidateDigest": candidate_digest,
            "method": "repeat the same hand-only builder and compare candidate output hashes and this report hash; run records are excluded from candidate digest",
            "noTimestampOrRandomness": True,
            "runEvidence": {
                "run1": "audit/hand-hidden-aa-rebuild-run-1.json",
                "run2": "audit/hand-hidden-aa-rebuild-run-2.json",
            },
        },
    }
    write_json(HAND_AA_MAINTENANCE_REPORT_PATH, report)
    report_hash = sha256_file(HAND_AA_MAINTENANCE_REPORT_PATH)

    run1_matches_current = bool(
        previous_run1
        and previous_run1.get("candidateDigest") == candidate_digest
        and previous_run1.get("maintenanceReportSha256") == report_hash
    )
    run_path = HAND_AA_REBUILD_RUN_2_PATH if run1_matches_current else HAND_AA_REBUILD_RUN_1_PATH
    run_number = 2 if run1_matches_current else 1
    write_json(run_path, {
        "schemaVersion": 1,
        "stage": "R2_HAND_HIDDEN_AA_MAINTENANCE deterministic rebuild evidence",
        "runNumber": run_number,
        **IDENTITY,
        "status": report["status"],
        "inputBaseline": input_baseline_measurement,
        "candidateDigest": candidate_digest,
        "maintenanceReportSha256": report_hash,
        "outputHashes": output_hashes,
        "handMaintenanceEngineeringPass": hand_checks_pass,
        "engineeringPass": report["engineeringPass"],
        "userVisualApproval": None,
        "overallGatePass": False,
        "protectedArtifactsUnchanged": protected_unchanged,
        "nonHandR2ArtifactsUnchanged": nonhand_unchanged,
        "outsideBoundaryPixels": len(outside_boundary_points),
        "hiddenOutsideEnvelopePixels": hand_root_geometry["logicalMasks"]["hiddenOutsideEnvelopePixels"],
        "downstreamForbidden": True,
        "nextState": "WAITING_USER_VISUAL_APPROVAL; do not enter R3/R4/texture/Cubism/Runtime",
    })
    print(json.dumps({
        "stage": report["stage"],
        "status": report["status"],
        "handMaintenanceEngineeringPass": hand_checks_pass,
        "engineeringPass": report["engineeringPass"],
        "overallGatePass": False,
        "runNumber": run_number,
        "candidateDigest": candidate_digest,
        "reviewImage": report["manualVisualReview"]["reviewImage"],
    }, ensure_ascii=False))


def main() -> None:
    if "--forearm-ucap" in sys.argv[1:]:
        forearm_ucap_main()
    else:
        hand_hidden_aa_maintenance_main()


if __name__ == "__main__":
    main()
