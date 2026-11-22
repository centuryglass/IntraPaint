"""Finding, and later installing, the Stable Diffusion backends IntraPaint can generate with.

Detection modules import no Qt, `Config` or `Cache`: their functions block, take everything they need as parameters,
and are run by the caller in an `AsyncTask`. `managed_comfyui` is the exception: it owns a running process on the main
thread.
"""
