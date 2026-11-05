# Summary background asset provenance

Date: 2026-11-05.

## Method and scope

Generated with the built-in ImageGen tool (`image_gen.imagegen`), one call per asset, with `transparent_background: false`. No fallback CLI or live integration was used. These are decorative generated raster backgrounds, not evidence of accounting functionality or real results.

Visual source: `assets/design/dashboard-f-mockup.png`, supplied as a style reference in every call. The selected visual direction and original Orbix Studio reference are documented in `docs/design/dashboard-direction.md`. Only the corresponding summary-card background was requested; no UI content was requested or extracted.

The generated originals are preserved at their default local paths below. Project PNGs are byte-for-byte copies, without cropping, recoloring, resizing, or other postprocessing. ImageGen returned approximately 2.64:1 wide images rather than the requested approximate 900x340; these support rendering at approximately 330x126 CSS pixels.

## Assets

| Asset | Pixel dimensions | SHA-256 |
| --- | --- | --- |
| `apps/web/public/assets/summary-completed.png` | 2041x770 | `e1bbcf4963ec622e9cbcd7bb88af80397ebd200b5a8e212cc4bdb6d81e892811` |
| `apps/web/public/assets/summary-waiting.png` | 2033x774 | `8cbc7451f8e666c331571aa38ae1c56265ddf4a9c17a1a378560cb0e1bcff79c` |
| `apps/web/public/assets/summary-blocked.png` | 2038x771 | `2c7a262088c485f2003bf970d305e15d526ca363760300a55bb4aa57d701202a` |

### Completed

Project path: `apps/web/public/assets/summary-completed.png`.

Preserved original: `C:/Users/Admin/.codex/generated_images/01a1ad04-7db3-7480-98ba-6104836ec86e/exec-cada7e57-920a-4d0c-a041-6f340cf894d2.png`.

Full prompt:

```text
Use case: stylized-concept. Asset type: background-only PNG artwork for a dashboard summary card. Input image is a style reference only: match ONLY the background inside the first Completed summary card of the supplied dashboard mockup. Generate a separate standalone edge-to-edge wide background, approx 900x340 (2.65:1 aspect) or closest supported wide format. Soft blurred iridescent satin color field: pale blue/cyan across the upper portion, a soft purple diagonal highlight near upper middle blending into a brighter but restrained cyan blue band toward upper right. Extremely subtle defocused diagonal satin light streaks at right. Fade smoothly to nearly pure white throughout the lower half, leaving the bottom third essentially white. Restrained pastel saturation, airy luminous smooth gradients, no sharp folds or objects. No text, numbers, icons, borders, cards, rounded corners, UI, shadows, watermark or surrounding mockup. Just the full rectangular background artwork; opaque white base.
```

### Waiting for client

Project path: `apps/web/public/assets/summary-waiting.png`.

Preserved original: `C:/Users/Admin/.codex/generated_images/01a1ad04-7db3-7480-98ba-6104836ec86e/exec-5c811d01-1f71-47de-a2f9-cbafc0e3cb5b.png`.

Full prompt:

```text
Use case: stylized-concept. Asset type: background-only PNG artwork for a dashboard summary card. Input image is a style reference only: match ONLY the background inside the middle Waiting for client summary card of the supplied dashboard mockup. Generate a separate standalone edge-to-edge wide background, approx 900x340 (2.65:1 aspect) or closest supported wide format. Soft blurred iridescent satin color field: pastel cyan turquoise on upper left, pale creamy center, soft peach orange on upper right. Very subtle defocused diagonal satin light streaks at right. Fade smoothly to nearly pure white throughout the lower half, leaving the bottom third essentially white. Match the restrained pastel saturation and distribution in the reference, airy luminous smooth gradients, no sharp folds or objects. No text, numbers, icons, borders, cards, rounded corners, UI, shadows, watermark or surrounding mockup. Just the full rectangular background artwork; opaque white base.
```

### Blocked

Project path: `apps/web/public/assets/summary-blocked.png`.

Preserved original: `C:/Users/Admin/.codex/generated_images/01a1ad04-7db3-7480-98ba-6104836ec86e/exec-2054e5a3-73f1-445d-86ee-2214651d8293.png`.

Full prompt:

```text
Use case: stylized-concept. Asset type: background-only PNG artwork for a dashboard summary card. Input image is a style reference only: match ONLY the background inside the third Blocked summary card of the supplied dashboard mockup. Generate a separate standalone edge-to-edge wide background, approx 900x340 (2.65:1 aspect) or closest supported wide format. Soft blurred iridescent satin color field: dusty pink and mauve on upper left, blending through pale peach near center to soft peach yellow on upper right. Very subtle defocused diagonal satin light streaks at far right. Fade smoothly to nearly pure white throughout the lower half, leaving the bottom third essentially white. Match the restrained pastel saturation and distribution in the reference, airy luminous smooth gradients, no sharp folds or objects. No text, numbers, icons, borders, cards, rounded corners, UI, shadows, watermark or surrounding mockup. Just the full rectangular background artwork; opaque white base.
```

## Verification and limits

The reference and all three generated images were visually inspected. Outputs contain soft pastel color fields fading toward white below, with the specified blue/purple, cyan/peach, and mauve/yellow palettes. No visible text, numbers, icons, borders, cards, or watermarks appear. PNG format, dimensions, and hashes were checked locally. The satin effect is subtle and blurred; these are generated approximations of the reference backgrounds, not a claim of pixel-exact reproduction.

No source code, package files, browser, Outline document, or external integration was changed. Parent owns integration and final browser QA, including crop behavior and readability behind actual UI content. Original files are local generation artifacts and are not additional repository deliverables.
