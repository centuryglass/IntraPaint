# Brief — OQ5: replace `src/api` with the `sd-api-standalone` library

Paste this as the prompt for a **cold session (Opus)** that has read access to **both** repos:
- IntraPaint: `/home/anthony/Workspace/ML/IntraPaint`
- The library: `/home/anthony/Workspace/ML/sd-api-standalone` (separate git repo, package
  `intrapaint_api`)

---

```
TASK: Plan the cleanest replacement of IntraPaint's src/api with the standalone library.

Answer this, in full-report depth:
"I've got a WIP independent API wrapper library at ../sd-api-standalone. What would be the
cleanest way to replace the existing src/api with that library? You're allowed to recommend
changes to both IntraPaint and that library itself."

Also fold in the backend-strategy question (per the decisions ledger's leaning): ComfyUI is
trending toward being the default backend and A1111/Forge toward lower priority — factor that
into the migration (e.g. don't over-invest in preserving A1111-only paths).

REQUIRED READING FIRST:
- IntraPaint: doc/analysis+plans/_codebase_map.md (§5 generation backends), _decisions_ledger.md,
  architecture_review.md §5 (api-swap position), concurrency_model.md (A5 — the threading contract
  the library must fit).
- Library: ../sd-api-standalone/README.md and ../sd-api-standalone/CLAUDE.md, then survey the
  intrapaint_api package and its tests/ (a1111 + comfyui generation, controlnet, metadata, async,
  auth). Recent commits added a "backend-agnostic async generation handle" — understand it; it's
  the crux (see below).

METHOD:
1. Inventory the current seam in IntraPaint:
   - What src/api actually provides: comfyui/ (ComfyNodeGraph + DiffusionWorkflowBuilder + node
     classes), webui/ (request/response bodies), controlnet/ (backend-agnostic CN model), and the
     webservice HTTP layers (webservice.py, a1111_webservice.py, comfyui_webservice.py).
   - How it's consumed: the generator classes in src/controller/image_generation/
     (sd_generator, sd_comfyui_generator, sd_webui_generator) — this is THE seam the swap turns on.
     Map exactly what each generator calls into src/api.
2. Inventory the library's public API:
   - Its backend-agnostic generation/async handle, its ComfyUI + A1111 clients, controlnet
     support, metadata handling, auth. What is its data-type boundary — does it depend on
     PySide6/QImage, or PIL/bytes/numpy? (This determines how much adapting IntraPaint needs.)
3. Gap analysis (produce a table): for each src/api capability IntraPaint relies on, does the
   library cover it, partially cover it, or not? Note mismatches in: workflow building
   (does the library subsume DiffusionWorkflowBuilder / ComfyNodeGraph, letting src/api/comfyui be
   deleted?), the ControlNet model, image/metadata types, progress/preview streaming, and auth.
4. Migration strategy: recommend the cleanest path — a thin adapter behind the existing generator
   interface vs. rebinding generators directly to intrapaint_api vs. a staged backend-by-backend
   swap. State what gets deleted from src/api, what stays, and what must be ADDED to the library.
5. Recommend changes to BOTH repos explicitly (the user invited this).

CRUX — reconcile async models (do not skip):
IntraPaint's threading contract (concurrency_model.md, A5): all image-model/config/undo/UI mutation
happens on the GUI thread; workers only produce data and hand back via a signal whose sender has
main-thread affinity (that's why AsyncTask is safe). The library has its OWN "backend-agnostic
async generation handle." Determine how the library delivers progress/results (callbacks? its own
threads? asyncio? a poll handle?) and specify how that maps onto IntraPaint's main-thread rule
WITHOUT reintroducing off-main-thread model/UI mutation. This mapping is the make-or-break of a
clean swap — give it its own section with a concrete recommended integration pattern.

DELIVERABLE — write to: doc/analysis+plans/api_library_swap.md   (in the IntraPaint repo)
Structure:
1. Summary verdict (is the swap clean/feasible now, and the single biggest obstacle).
2. Current seam (what generators call into src/api).
3. Library capability survey (API surface, async model, data-type boundary, maturity).
4. Gap analysis table (src/api need -> library coverage: full / partial / missing).
5. Async-model reconciliation (the crux section above) with a concrete integration pattern.
6. Migration strategy (adapter vs direct; what to delete / keep / add; staged plan).
7. Recommended changes to the LIBRARY (its own subsection) and to INTRAPAINT.
8. Backend strategy (ComfyUI default, A1111/Forge downgrade) as it affects scope.
9. Testing (both repos have suites — how to validate the swap; what the pure builders make easy).
10. Risks + sequencing, and the hand-off to OQ3 (backend auto-install builds on whatever
    client/backend this standardizes on).

GUARDRAILS:
- Analysis only — do not modify code in EITHER repo. The library is a separate git repo; respect
  its boundary (recommendations, not edits).
- Cite evidence as file:line in both repos. Mark anything inferred as [inferred].
- If the library is missing something src/api needs, say so plainly and put it in the
  "changes to the library" section rather than papering over it.
- Update the shared docs when done: _decisions_ledger.md (record the migration decision +
  backend-strategy call), _execution_plan.md (mark OQ5 done; note OQ3 is now unblocked),
  README.md (index the new report).

MODEL / EXECUTION: Opus, cold session with read access to both repos. No warm IntraPaint context
needed — the committed reports above carry it.
```

## Notes for whoever kicks this off
- This report **unblocks OQ3** (backend auto-install) — that report will build on whichever
  client/backend the swap standardizes on, so run OQ5 before OQ3.
- The library being a **separate git repo** matters: recommended library changes are proposals for
  that repo, not edits to make here. Keep the two change-sets clearly separated in §7.
- Good Sonnet-vs-Opus call: keep this on **Opus** — it's a consequential cross-repo architecture
  decision with a subtle threading-reconciliation core, not a survey.
</content>
