# Loading indicator designs

Each subfolder is one loading design. In a sprite-sheet folder, each PNG is one variant, and every variant is a separate
option in the loading indicator's random pick (`src/ui/loading/loading_designs.py`). Invalid files are skipped with a
logged warning.

## Folders

- **`diffusion_ring/`:** one design, whose PNGs are the images it resolves, one per loop, in random order. Each is a
  clean ring, square, on a transparent background, and all share one size. Noise is mixed in at draw time, so the
  image is only the fully resolved frame. Images change while the ring is pure noise, so every image is drawn through
  the alpha channel of the first one (alphabetically); other images' alpha is ignored. Keep the ring outside the
  central message rectangle (54% by 26% of the side, centered).
- **Any other folder:** a sprite-sheet design named after the folder (`pixel_orbit` shows as "Pixel Orbit"). Each PNG
  is a grid of square frames, played left to right and then top to bottom, looping from the last frame back to the
  first.

Frames are drawn at a whole-number multiple of their size, without smoothing, and over both light and dark themes.

## Options

An optional JSON file with the same name as a PNG (`ember.json` beside `ember.png`) overrides its defaults for a sprite sheet:

| Key           | Applies to    | Default                                 |
|---------------|---------------|-----------------------------------------|
| `frame_size`  | sprite sheets | `72`                                    |
| `frame_count` | sprite sheets | every cell in the grid                  |
| `duration_ms` | sprite sheets | `2400`                                  |

`frame_count` is for a sheet whose last row isn't full.

## Tools

- `python scripts/render_loading_assets.py` renders the starting variants, `diffusion_ring/color_wheel.png` and
  `pixel_orbit/ember.png`. They work as restyle templates.
- `python scripts/preview_loading_widget.py` previews any design and variant.
