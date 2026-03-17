"""
Remove "Shedевrum" watermark from grafin_original.jpg
Strategy: sample the pure-background edge pixels (far right and bottom edges)
to reconstruct a smooth gradient over the watermark area.
"""

from PIL import Image, ImageFilter
import numpy as np
import os

SRC = os.path.join(os.path.dirname(__file__), "grafin_original.jpg")
DST = os.path.join(os.path.dirname(__file__), "grafin_logo_clean.png")

img = Image.open(SRC).convert("RGB")
w, h = img.size
print("Image size: %dx%d" % (w, h))

arr = np.array(img, dtype=np.float32)

# ── Watermark region (detected from previous run) ─────────────────────────
# Raw bbox: (352,512) -> (639,616), padded generously
WX0, WY0 = 330, 495
WX1, WY1 = 639, 639   # go to full bottom-right corner

print("Repair region: (%d,%d) -> (%d,%d)" % (WX0, WY0, WX1, WY1))

patch_h = WY1 - WY0 + 1
patch_w = WX1 - WX0 + 1

# ── Sample background ─────────────────────────────────────────────────────
# The background in the bottom-right is a smooth neutral gradient.
# Best reference pixels: a narrow strip just ABOVE the watermark region
# BUT only from columns where there is no pitcher (right side of image).
# Pitcher right edge at ~x=480 at y=495, so sample x=490..639 for top strip.

# Top reference strip: 10 rows just above WY0, full column width of patch
TOP_ROWS = 10
top_strip = arr[max(0, WY0 - TOP_ROWS):WY0, WX0:WX1 + 1]   # (<=10, patch_w, 3)
if top_strip.shape[0] > 0:
    top_colors = top_strip.mean(axis=0)   # (patch_w, 3) — per-column mean
else:
    top_colors = np.full((patch_w, 3), 210.0)

# Right reference strip: 10 columns at the very right edge of the image,
# spanning the patch rows. These are guaranteed pure background.
RIGHT_COLS = 10
right_strip = arr[WY0:WY1 + 1, w - RIGHT_COLS:w]   # (patch_h, 10, 3)
right_colors = right_strip.mean(axis=1)              # (patch_h, 3) — per-row mean

# Bottom reference strip: 10 rows at very bottom of image
BOTTOM_ROWS = 10
bot_strip = arr[h - BOTTOM_ROWS:h, WX0:WX1 + 1]    # (10, patch_w, 3)
if bot_strip.shape[0] > 0:
    bot_colors = bot_strip.mean(axis=0)              # (patch_w, 3)
else:
    bot_colors = np.full((patch_w, 3), 210.0)

# ── Build patch via bilinear interpolation ───────────────────────────────
# We know the top edge colors and right edge colors.
# Interpolate: at (row, col) inside patch:
#   - from-top: top_colors[col]
#   - from-right: right_colors[row]
#   - from-bottom: bot_colors[col]
#
# Weight: distance-based blend favoring closest known edge.

rows = np.arange(patch_h, dtype=np.float32)
cols = np.arange(patch_w, dtype=np.float32)

# Relative positions [0..1]
t = rows / max(patch_h - 1, 1)   # 0 = top, 1 = bottom
u = cols / max(patch_w - 1, 1)   # 0 = left, 1 = right

# Broadcast shapes: (patch_h, patch_w, 3)
top_field = top_colors[np.newaxis, :, :]          # (1, patch_w, 3)
bot_field = bot_colors[np.newaxis, :, :]          # (1, patch_w, 3)
right_field = right_colors[:, np.newaxis, :]      # (patch_h, 1, 3)

# Blend top→bottom vertically, then blend result with right edge
vertical = top_field * (1 - t[:, np.newaxis, np.newaxis]) + \
           bot_field *      t[:, np.newaxis, np.newaxis]

# Blend left side (vertical) with right reference, weighting toward right
# (the right edge data is most reliable — pure background)
horiz_weight = u[np.newaxis, :, np.newaxis]  # 0=left, 1=right
patch = vertical * (1 - horiz_weight * 0.4) + right_field * (horiz_weight * 0.4 + 0.2)

patch = np.clip(patch, 0, 255)

# ── Paint patch ───────────────────────────────────────────────────────────
result_arr = arr.copy()
result_arr[WY0:WY1 + 1, WX0:WX1 + 1] = patch

# ── Feather the left seam (blend over 8 pixels) ──────────────────────────
FEATHER = 10
for i in range(FEATHER):
    alpha = (i + 1) / (FEATHER + 1)   # 0 = all original, 1 = all patch
    col = WX0 + i
    if col >= w:
        break
    result_arr[WY0:WY1 + 1, col] = \
        (1 - alpha) * arr[WY0:WY1 + 1, col] + alpha * patch[:, i]

# ── Feather the top seam ──────────────────────────────────────────────────
for i in range(FEATHER):
    alpha = (i + 1) / (FEATHER + 1)
    row = WY0 + i
    if row >= h:
        break
    result_arr[row, WX0:WX1 + 1] = \
        (1 - alpha) * arr[row, WX0:WX1 + 1] + alpha * patch[i, :]

# ── Light gaussian blur on repaired zone for seamless texture ────────────
result_img = Image.fromarray(result_arr.astype(np.uint8), "RGB")
box = (WX0, WY0, WX1 + 1, WY1 + 1)
repair_crop = result_img.crop(box)
repair_crop = repair_crop.filter(ImageFilter.GaussianBlur(radius=2))
result_img.paste(repair_crop, box)

result_img.save(DST, "PNG", optimize=True)
print("Saved: " + DST)
