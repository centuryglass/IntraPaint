# Non-destructive layer persistence & foreign-ORA preservation (A3 / OQ10)

**Question (OQ10):** IntraPaint loses information when round-tripping ORA files authored elsewhere,
and text layers get flattened. Design an approach for persisting non-destructive layer types (text
via SVG or ORA XML extension, plus a future `SVGLayer`) and preserving non-standard tags/files from
foreign ORA archives, following the `TextLayer` "convert to image" pattern.

Substrate: `_codebase_map.md` §4 (layers, translation, undo), `_decisions_ledger.md`. Primary code:
`src/image/open_raster.py`, `src/image/layers/text_layer.py`, `src/image/text_rect.py`,
`src/image/layers/{layer,transform_layer,image_layer,layer_group}.py`,
`src/image/layers/image_stack.py` (`load_layer_stack`, `create_layer`).

---

## 0. TL;DR

Two independent losses, one shared fix shape.

1. **Text layers flatten on save.** `save_ora_image` routes `TextLayer` through `encode_image_layer`
   (open_raster.py:122, 182) — it writes only the rendered PNG. `parse_image_element` always builds
   an `ImageLayer` (open_raster.py:345). The `TextRect` (which already has `serialize()`/
   `deserialize()`, text_rect.py:79-99) is never written, so reload can't reconstruct a `TextLayer`.
2. **Foreign ORA data is dropped.** `read_ora_image` extracts to a tmpdir, reads only the tags it
   knows, and discards the rest; `save_ora_image` rebuilds the archive **from scratch** and renames
   every layer file to `{name}_{id}.png`. Any unknown layer attribute, unknown XML element, or extra
   file (Krita's `mimetype` extras, `animation/`, `.kra`-ish sidecars, custom `composite-op`, a
   foreign app's private namespace) never survives a load→save.

**The fix is one mechanism used twice:** give layers an *opaque side-channel* — structured extra
data that the ORA layer knows how to carry but the rest of the app ignores — and route both
IntraPaint's own non-destructive types (text now, SVG later) and foreign apps' unknown data through
it. Text persistence is a **thin producer** of that side-channel; foreign preservation is a
**passthrough** producer of it. Both reuse the existing `extended_data.xml` extension channel
(open_raster.py:35, 218-234) so we don't invent a second parallel format.

Recommendation: **store text as serialized `TextRect` in an ORA XML extension, not as SVG.** Keep
SVG as the *interchange export* format, not the *source of truth*. Generalize the `TextLayer`
"convert to image" pattern (`confirm_or_cancel_render_to_image` + `replace_with_image_layer`,
text_layer.py:58-70, 144-165) into a small `NonDestructiveLayer` contract that a future `SVGLayer`
and the foreign-passthrough layer both satisfy. UI-and-I/O only; no model/undo/config-schema changes
beyond additive layer types and Cache keys.

---

## 1. Verified current behavior

### 1.1 The ORA writer/reader as it stands

The format already has **two XML files**: the spec-standard `stack.xml`, and IntraPaint's own
`extended_data.xml` (open_raster.py:35). The extended file is where IntraPaint already parks
non-standard data today:

- **Per-layer transform** — a full 3×3 `QTransform` plus a `src_untransformed` PNG, keyed by the
  layer's standard `src` path (open_raster.py:144-158, 286-302). This exists precisely because the
  ORA spec only has integer `x`/`y` position, so a rotated/scaled layer would lose its transform in
  a foreign viewer; IntraPaint writes a **flattened, positioned PNG for compatibility** *and* an
  **untransformed PNG + matrix for itself.** That is exactly the dual-representation pattern OQ10
  wants, already proven in the codebase.
- **`alpha-locked`** — another IntraPaint-only boolean (open_raster.py:97, 148-149).
- **`metadata`** — a top-level free-string blob for generation parameters (open_raster.py:102,
  230-231).

So the writer already knows how to: (a) emit a spec-clean flattened PNG for interop, and (b) emit a
richer sidecar keyed by `src`. **Text and foreign-passthrough are new *clients* of this same
channel, not a new channel.**

### 1.2 Why text flattens (confirmed)

`encode_image_layer` accepts `ImageLayer | TextLayer` and, for either, calls
`layer.transformed_image()` and writes the resulting PNG (open_raster.py:122-142). For a `TextLayer`
that PNG is `TextRect.render_to_image()` — the rasterized text. The `TextRect` itself is never
serialized into either XML file. On read, `parse_image_element` unconditionally constructs
`ImageLayer(layer_image, '')` (open_raster.py:345). Result: **every save→load turns text into
pixels**, silently, with no prompt (unlike the explicit editing-time flatten, which at least
confirms). This is strictly worse than the interactive path.

`TextRect.serialize()` already produces a compact JSON string of everything needed to reconstruct
the layer (font via `QFont.toString()`, colors as `#AARRGGBB`, size, alignment, fill flag, scale
mode — text_rect.py:86-99), and `deserialize()` round-trips it (text_rect.py:79-84). **The data we
need to persist already has a serializer.** The only missing piece is writing that string into the
archive and branching on it at load.

### 1.3 Why foreign data is dropped (confirmed)

- **Unknown layer attributes:** `_parse_common_attributes` reads only name/visibility/locked/
  opacity/composite (open_raster.py:304-326). Any other attribute on a `<layer>`/`<stack>` element
  is read-and-forgotten.
- **Unknown elements / namespaces:** `parse_stack_element` `continue`s past any child whose tag
  isn't `stack`/`layer` (open_raster.py:373-374). Foreign namespaced elements vanish.
- **Extra archive files:** `read_ora_image` extracts everything to a tmpdir (open_raster.py:277-278)
  then reads only the files referenced by tags it understands. The tmpdir — and every unreferenced
  file in it — is dropped when the function returns. Nothing is retained on the `ImageStack`.
- **The rename problem:** even a file that *is* referenced is re-emitted by the writer under a new
  name `data/{name}_{id}.png` (open_raster.py:137), so a foreign app's stable `src` paths and its
  internal cross-references (e.g. a `<text>`/animation element pointing at `data/layer3.png`) break
  on the round-trip even when the bytes survive.

Net: IntraPaint is a **lossy re-encoder** of foreign ORA, not a round-tripper.

---

## 2. Design principles

1. **Interop first, richness second — never one *or* the other.** Always write the spec-clean
   flattened PNG + standard attributes (so GIMP/Krita/MyPaint open the file correctly), *and* write
   the non-destructive source into the extension channel. This is exactly what the transform
   extension already does; text/SVG/foreign-data follow suit. A foreign viewer sees a normal raster
   layer; IntraPaint sees the editable source.
2. **One opaque side-channel, many producers.** Don't special-case "text" in the ORA writer. Define
   a neutral per-layer "extension payload" (attributes + files) that any layer can contribute, and
   let each layer type populate it. Text is one producer; the foreign-passthrough carrier is
   another; `SVGLayer` will be a third. The writer/reader stay generic.
3. **Generalize the `TextLayer` flatten pattern, don't fork it.** Every non-destructive layer needs
   the same three behaviors text already has: *render to a raster* (`get_qimage`), *refuse direct
   pixel edits until converted* (`set_qimage`/`cut_masked` raise, text_layer.py:120-122, 167-169),
   and *convert-with-confirmation* (`confirm_or_cancel_render_to_image` +
   `replace_with_image_layer`). Hoist these into a shared contract so `SVGLayer` and the foreign
   carrier inherit them instead of re-implementing.
4. **Preserve, don't interpret.** For foreign data IntraPaint doesn't understand, the goal is
   *byte-faithful passthrough*, not comprehension. Carry it opaquely and re-emit it; never try to
   parse or "upgrade" it.
5. **Graceful degradation.** A missing/corrupt extension payload must fall back to the flattened PNG
   (which is always present), exactly as the transform extension already falls back to `x`/`y`
   position (open_raster.py:349-355). Opening an IntraPaint ORA in an old IntraPaint build, or with
   the extension stripped, must still yield a valid image.

---

## 3. The mechanism: a per-layer extension payload

Introduce a small, format-agnostic record produced/consumed at the layer boundary:

```
class LayerORAExtension:               # in a new src/image/layers/layer_ora_extension.py
    attributes: dict[str, str]         # extra attrs to set on this layer's <layer>/<stack> element
    files: dict[str, bytes]            # archive-relative path -> bytes, written verbatim
    child_xml: list[Element]           # unknown child elements to re-insert (foreign passthrough)
```

Two new (optional) hooks on the `Layer` base contract (`src/image/layers/layer.py`):

```
def write_ora_extension(self, data_dir: str, layer_src: str) -> Optional[LayerORAExtension]:
    """Return non-standard ORA data for this layer, or None. Default: None."""

@classmethod
def try_load_ora_extension(cls, element, extension, load_ctx) -> Optional['Layer']:
    """If this layer type recognizes the extension payload, build and return the layer; else None."""
```

The ORA **writer** becomes: build the standard element + flattened PNG for *every* layer (unchanged),
then call `write_ora_extension`; merge any returned `attributes` onto the element, stage `files` into
the archive, and record `child_xml`/attributes into `extended_data.xml` keyed by `src` (extending the
loop at open_raster.py:222-234). The **reader** becomes a small **registry walk**: for each element,
try each registered non-destructive loader (`TextLayer.try_load_ora_extension`, later
`SVGLayer...`); the first that claims it wins; if none claim it, fall back to today's `ImageLayer`
path (open_raster.py:328-356) — but now *also* attach any leftover unknown attributes/children/files
to a **foreign-passthrough carrier** (§5) so they survive re-save.

This keeps `open_raster.py` free of per-type conditionals: it orchestrates a registry, and each layer
type owns its own serialization. It mirrors the config system's data-driven ethos (A4) and the
generator registry pattern — no `isinstance` ladder in the I/O layer. (Note: today's writer *does*
`isinstance`-branch on `LayerGroup` vs image/text at open_raster.py:178-183; that stays, but the
non-standard part moves behind the hook.)

---

## 4. Text layer persistence — **ORA XML extension, not SVG**

### 4.1 Recommendation

Persist the `TextLayer` as its **serialized `TextRect`** in the extension channel, alongside the
always-written flattened PNG. Concretely, `TextLayer.write_ora_extension` returns:

- `attributes = {}` (nothing non-standard needs to live on the spec element), and
- one file `data/{name}_{id}-text.json` containing `text_rect.serialize()`,
  recorded in `extended_data.xml` as e.g. `text-src="data/..._-text.json"` on the extended `<layer>`
  entry (same keying as `src_untransformed`, open_raster.py:290, 296).

On load, `TextLayer.try_load_ora_extension` sees `text-src`, reads the JSON, calls
`TextRect.deserialize(...)`, constructs `TextLayer(text_rect)`, applies the common attributes and the
transform (reusing the existing transform-extension load path), and returns it. If `text-src` is
absent or the JSON fails to parse → return `None` → the layer loads as a normal `ImageLayer` from the
flattened PNG. **Lossless for IntraPaint, invisible to foreign apps, degrades cleanly.**

Because the flattened PNG is still the `src`, the *positioned raster* is what any other editor shows —
identical to today. We add editability, we don't change interop rendering.

### 4.2 Why not SVG-as-source-of-truth

The prompt offers "text via SVG **or** ORA XML extension." SVG is the wrong *storage* choice here,
for four concrete reasons:

1. **Lossy in the direction that matters.** IntraPaint text is a `TextRect`: a Qt `QFont`
   (`toString()` captures family, point size, weight, italics, style-name, hinting, stretch,
   letter-spacing…), a Qt alignment flag, an auto-scale *mode* (`bounds→text`/`text→bounds`,
   text_rect.py:27-29, 198-207), and a fill-background toggle. Mapping that to SVG `<text>` and back
   is a lossy, ambiguous translation (SVG has no notion of Qt's auto-scale modes; font matching
   across the SVG font model and `QFont.fromString` is not round-trip-exact). JSON of the actual
   `TextRect` is **exact by construction** — it's the same object the app edits.
2. **We already have the serializer.** `TextRect.serialize/deserialize` exist, are tested by use, and
   are the format the text tool round-trips through. Reusing them is near-zero new surface. An SVG
   path is a whole new bidirectional converter to write, test, and keep in sync with `TextRect`.
3. **The `src` PNG is already the interop artifact.** The reason to want SVG — "another app can read
   it" — is already served by the flattened PNG for viewing. Editable interchange of *text* between
   arbitrary editors via ORA is not a real workflow (Krita stores text as its own SVG-in-`.kra`;
   MyPaint/GIMP don't read foreign text layers). Optimizing storage for a interchange path nobody
   walks costs us fidelity on the path everybody walks (IntraPaint→IntraPaint).
4. **SVG is better as an *export*, not a *store*.** Offer "Export text layer as SVG" (and, later,
   SVG-based `SVGLayer` import) as a **separate feature** if desired. Keep the persisted source of
   truth as the native `TextRect`. This cleanly separates "how IntraPaint remembers its own work"
   from "how IntraPaint exchanges with other tools."

**Decision:** text → `TextRect` JSON in the ORA extension channel. SVG stays a possible export/import
convenience, decoupled from persistence.

### 4.3 Guarding the silent flatten

Even with persistence, there's a residual risk: saving to a **non-ORA** format (PNG/JPG), or the user
deliberately exporting flat, still rasterizes. That's correct and expected — but the *silent* ORA
flatten that happens today when the extension is somehow unavailable should be made observable.
Reuse the existing confirmation machinery (`confirm_or_cancel_render_to_image`, text_layer.py:58-70)
only where a *destructive edit* forces it — saving to ORA now never flattens, so no new prompt is
needed there. No behavior regression; we simply stop losing data.

---

## 5. Foreign-ORA preservation (unknown tags & files)

The goal: **load→save is byte-faithful for everything IntraPaint doesn't model.** Two sub-problems:
capturing foreign data on load, and re-emitting it on save without the rename breaking references.

### 5.1 Capture on load

Extend `read_ora_image` to, for each element it processes:

- collect **unrecognized attributes** (everything not in the known set) into `extension.attributes`;
- collect **unrecognized child elements** (the `continue` branch, open_raster.py:373-374) into
  `extension.child_xml`;
- retain the **raw bytes of every archive file not consumed** by a known-layer `src`/extension, plus
  the bytes of foreign layers' `src` files, into a stack-level `foreign_files: dict[str, bytes]`.

Attach the per-layer `attributes`/`child_xml` to the layer object (a new optional
`layer.foreign_ora_data` slot, ignored by everything except the ORA writer). Keep `foreign_files` and
the **original `stack.xml` verbatim** on the `ImageStack` (a new `ImageStack.source_ora_archive`
opaque record, populated only when the loaded file was ORA). Nothing else in the app reads these; they
are pure passthrough ballast.

### 5.2 The identity / rename problem

The blocker is that the writer renames files and rebuilds XML, so foreign `src` references rot. Fix
with a **stable identity mapping**:

- On load, record for each layer the **original `src`** string from the foreign `stack.xml`.
- On save, when a layer carries foreign data, **preserve its original `src` filename** instead of
  minting `{name}_{id}.png` (write the flattened/updated PNG to the original path). Then any foreign
  `child_xml` or `foreign_files` that referenced that path stays valid.
- For foreign files with no owning layer (e.g. an `animation/` dir, a foreign `mergedimage` variant,
  private sidecars), copy the bytes into the new archive **at their original paths** verbatim.
- Re-attach each layer's `extension.attributes` onto its emitted element and re-insert `child_xml`
  as children — round-tripping the foreign namespace elements unchanged.

**Conflict policy:** if IntraPaint *edited* a foreign layer (content changed), its flattened PNG is
rewritten (bytes differ, path preserved) and any foreign extension that *described the old pixels*
(e.g. a foreign vector source) is now stale. Two honest options, gated by a Cache preference:
(a) **preserve** the foreign source verbatim and accept that the foreign app may re-render from stale
vectors (default: **preserve**, matching "don't interpret"), or (b) **drop** foreign extensions for
layers IntraPaint modified and keep them only for untouched layers (safer for correctness, loses
foreign editability). Track a per-layer `modified_since_load` bit to make this decision; unmodified
layers are always preserved verbatim. Surface the choice once, at save, only when a conflict exists.

### 5.3 The foreign non-destructive carrier

For a foreign layer that is *itself* non-destructive in the source app (e.g. Krita text/vector), the
flattened PNG is the safe render and the foreign source rides along as opaque `child_xml`/files.
Expose this to the user through the **same "convert to image" idiom**: the layer is presented as a
locked, non-editable "imported (App X)" layer; the panel offers **"Flatten to image layer"** which
drops the foreign payload and yields a plain `ImageLayer` (identical UX to `replace_with_image_layer`,
text_layer.py:144-165). The user never edits foreign vectors in place (we can't), but they explicitly
choose when to discard the passthrough — no silent loss.

---

## 6. Generalizing the "convert to image" pattern

Hoist the three behaviors `TextLayer` already implements into a mixin/base so text, the future
`SVGLayer`, and the foreign carrier share them:

```
class NonDestructiveLayer(TransformLayer):     # src/image/layers/non_destructive_layer.py
    # 1. Renders to raster on demand — subclass provides get_qimage().
    # 2. Refuses direct pixel mutation until converted:
    def set_qimage(self, image): raise RuntimeError(CONVERT_FIRST_MSG)
    def cut_masked(self, mask):  raise RuntimeError(CONVERT_FIRST_MSG)
    # 3. Convert-with-confirmation, reusing the existing helpers:
    #    confirm_or_cancel_render_to_image()  (already static on TextLayer -> move here)
    #    copy_as_image_layer() / replace_with_image_layer()  (generalize: render via get_qimage)
    # 4. ORA hooks (default raises NotImplementedError to force subclasses to define persistence)
    def write_ora_extension(...): ...
```

`TextLayer` becomes `NonDestructiveLayer` + `text_rect` state + the JSON producer/consumer from §4.
`copy_as_image_layer`/`replace_with_image_layer` are already type-agnostic apart from the `ImageLayer`
construction (text_layer.py:135-165) — they lift cleanly. The `confirm_or_cancel_render_to_image`
call sites (filter.py:261, image_stack.py:432/962/1045/1173, image_stack_utils.py:82) already collect
*text* layers by `isinstance(layer, TextLayer)`; widen those predicates to
`isinstance(layer, NonDestructiveLayer)` so every destructive operation prompts for **any**
non-destructive type, not just text. That single predicate change is what makes `SVGLayer` and the
foreign carrier "just work" against the existing flatten-gate.

## 7. Future `SVGLayer` — how it slots in

`SVGLayer` is then almost free:

- State: the SVG document (string/`bytes`) + a `QSvgRenderer` for `get_qimage()`.
- Persistence: `write_ora_extension` writes the `.svg` file into `data/` and references it via an
  `svg-src` extension attribute (exact analogue of `text-src`). `try_load_ora_extension` sees
  `svg-src`, loads the SVG, builds the layer. **Bonus interop:** SVG is a first-class ORA-friendly
  asset; a foreign app that understands the reference could even use it. Register its loader in the
  same registry the reader walks.
- Behavior: inherits the flatten-gate and convert-to-image from `NonDestructiveLayer` unchanged.

The point of the §3 registry is precisely that adding `SVGLayer` touches **only** `SVGLayer` +
registry registration — not `open_raster.py`'s control flow.

---

## 8. Round-trip guarantees & test plan

Testable invariants (fit A1's golden/characterization tiers; build on the `IntraPaintTestCase` base):

1. **Text round-trip is lossless.** Build a stack with a `TextLayer` (non-trivial font, alignment,
   auto-scale mode, transform) → `save_ora_image` → `read_ora_image` → assert the reloaded layer is a
   `TextLayer` and `reloaded.text_rect == original.text_rect` (`TextRect.__eq__` exists,
   text_rect.py:70-77) and the transform matches.
2. **Legacy/degraded read.** An ORA whose `text-src` is missing or corrupt loads as an `ImageLayer`
   from the flattened PNG (no exception, pixels intact) — asserts the fallback path.
3. **Foreign passthrough is byte-faithful.** Fixture: a small Krita/GIMP-authored `.ora` with a
   custom attribute, a foreign namespaced child element, and an extra archive file. Load→save→reopen
   the *foreign* file; assert the unknown attribute, child element, and extra file bytes are present
   and unchanged, and standard layers still render (compare `mergedimage` golden).
4. **Interop rendering unchanged.** The flattened `src` PNG and `mergedimage` for an IntraPaint text
   layer are pixel-identical before and after adding persistence (guards against the extension
   accidentally changing the raster path).
5. **Flatten-gate coverage.** Every `confirm_or_cancel_render_to_image` call site prompts for an
   `SVGLayer`/foreign carrier stub, not just `TextLayer` (widened predicate).

Fixtures: check in a couple of tiny hand-authored foreign `.ora` files under `test/resources/`. Keep
them minimal (a few px) so they don't inflate CI.

---

## 9. Risks & edge cases

- **`QFont.toString()`/`fromString()` portability.** Font state is persisted as Qt's own string.
  Round-trips within IntraPaint are exact; across Qt versions/platforms font *matching* may differ if
  the exact family is absent — but that's a rendering-substitution issue identical to today's
  behavior, not a data-loss one. The stored spec is faithful; only the substituted glyphs vary.
- **`layer.id` in filenames vs foreign `src` preservation.** The rename that gives IntraPaint layers
  stable unique names is what breaks foreign references. §5.2 resolves this by preserving the
  *original* `src` only for layers carrying foreign data; IntraPaint-native layers keep the
  `{name}_{id}` scheme. Two naming policies coexist, keyed by provenance.
- **Edited foreign layers (§5.2 conflict).** The one genuinely lossy corner: you cannot both edit a
  foreign vector layer's pixels in IntraPaint and keep its foreign vector source coherent. Made
  explicit (preserve-vs-drop preference + per-layer `modified_since_load`), never silent.
- **Archive bloat.** Preserving foreign files + untransformed PNGs + text JSON grows the archive. The
  format is `ZIP_STORED` (uncompressed, open_raster.py:238) — consider `ZIP_DEFLATED` for the text/
  XML/foreign-XML members (small, highly compressible) while leaving PNGs stored. Minor, optional.
- **Security of passthrough XML.** Re-emitting foreign `child_xml` verbatim means we serialize
  attacker-influenced XML. Use `ElementTree` write (no external entity expansion on write) and never
  *evaluate* foreign content; treat it as opaque. Loading already uses `ElementTree().parse` — ensure
  it's not resolving external entities (Python's default `ElementTree` doesn't, but confirm no
  network/DTD fetch). This is a preserve-don't-interpret guardrail, not a new attack surface beyond
  "we opened the file at all."
- **Group (`<stack>`) foreign data.** Groups can carry foreign attributes/children too; the extension
  hooks apply to `LayerGroup` as well (`write_ora_extension` on the group, foreign children preserved
  under the stack element).

---

## 10. Scope & files touched

Additive and contained; no model/undo/config-schema redesign.

- **New:** `src/image/layers/layer_ora_extension.py` (the payload record + loader registry),
  `src/image/layers/non_destructive_layer.py` (hoisted base), optional
  `src/image/layers/svg_layer.py` (future, out of scope for the first landing).
- **`src/image/open_raster.py`:** writer calls `write_ora_extension` per layer and stages
  attributes/files/child-XML into `extended_data.xml`/archive; reader walks the loader registry, then
  falls back to `ImageLayer` + foreign-passthrough capture; preserve original `src` for foreign
  layers; retain unconsumed archive files + verbatim source `stack.xml`.
- **`src/image/layers/layer.py`:** two optional no-op hooks (`write_ora_extension`,
  `try_load_ora_extension`) + an optional `foreign_ora_data` slot.
- **`src/image/layers/text_layer.py`:** reparent onto `NonDestructiveLayer`; implement the two hooks
  (produce/consume `TextRect` JSON). Move `confirm_or_cancel_render_to_image`,
  `copy_as_image_layer`, `replace_with_image_layer`, `set_qimage`/`cut_masked` guards to the base.
- **`src/image/layers/image_stack.py`:** optional `source_ora_archive` slot; widen the
  `isinstance(..., TextLayer)` flatten-gate predicates (image_stack.py:432/962/1045/1173,
  image_stack_utils.py:82, filter.py:261) to `NonDestructiveLayer`.
- **Config (data-driven, per §"Config system"):** optional `Cache` keys for the foreign-conflict
  preference (preserve/drop) and an "export text as SVG" toggle if that feature is added.
- **UI:** a "Flatten to image layer" action + an "imported (foreign)" locked-layer affordance in the
  layer panel (reuses the text-convert flow); all new strings via the `TR_ID`/`_tr()` pattern.
- **Tests:** the five invariants in §8 + tiny foreign `.ora` fixtures.

**Phasing.** P1: text persistence (§4) — highest value, smallest surface, uses existing serializer;
ship alone. P2: the `NonDestructiveLayer` hoist + widened flatten-gate (§6). P3: foreign passthrough
(§5) — most complex, needs the identity mapping + conflict policy + fixtures. P4 (optional/future):
`SVGLayer` (§7) and SVG export. P1 fixes the more common, more embarrassing bug (your own text dies on
save) before the harder foreign-round-trip work.

---

## 11. Feeds / dependencies

- **Independent** of the rendering (R1), transform (A2), and selection (OQ4) work — touches I/O and
  layer types only. No overlap with the tiled-composite substrate.
- **Aligns with A1 (testing):** the round-trip invariants are natural characterization/golden tests;
  the foreign fixtures belong in `test/resources/`.
- **Feeds OQ2 (editor-norm synthesis):** "loses text/foreign layer data on save" is a concrete
  norm-conformance gap (Krita/GIMP/Photoshop all preserve their own non-destructive layers and most
  preserve foreign metadata) worth citing there rather than re-deriving.
