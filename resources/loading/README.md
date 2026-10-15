# Loading indicator designs

Each subfolder is one loading design, and each PNG in it is one variant of that design. Every variant is a separate
option in the loading indicator's random pick (`src/ui/loading/loading_designs.py`), so adding a file adds an option.
Invalid files are skipped with a logged warning.

## Folders

- **`diffusion_ring/`:** each PNG is one clean ring, square, on a transparent background. Noise is mixed in at draw
  time, so the image is only the fully resolved frame. Keep the ring outside the central message rectangle (54% by
  26% of the side, centered).
- **Any other folder:** a sprite-sheet design named after the folder (`pixel_orbit` shows as "Pixel Orbit"). Each PNG
  is a grid of square frames, played left to right and then top to bottom, looping from the last frame back to the
  first.

Frames are drawn at a whole-number multiple of their size, without smoothing, and over both light and dark themes.

## Options

An optional JSON file with the same name as a PNG (`ember.json` beside `ember.png`) overrides its defaults:

| Key           | Applies to    | Default                                 |
|---------------|---------------|-----------------------------------------|
| `frame_size`  | sprite sheets | `72`                                    |
| `frame_count` | sprite sheets | every cell in the grid                  |
| `duration_ms` | both          | `2400` for sprite sheets, `5000` for diffusion rings |

`frame_count` is for a sheet whose last row isn't full.

## Tools

- `python scripts/render_loading_assets.py` renders the starting variants, `diffusion_ring/color_wheel.png` and
  `pixel_orbit/ember.png`. They work as restyle templates.
- `python scripts/preview_loading_widget.py` previews any design and variant.
