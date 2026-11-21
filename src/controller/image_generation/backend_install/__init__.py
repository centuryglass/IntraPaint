"""Finding, and later installing, the Stable Diffusion backends IntraPaint can generate with.

Modules here import no Qt, `Config` or `Cache`: their functions block, take everything they need as parameters, and
are run by the caller in an `AsyncTask`.
"""
