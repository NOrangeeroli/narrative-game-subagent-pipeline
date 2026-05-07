# AdventureCompilerReviewer

Reviews compiled adventure artifacts and validator reports.

Inputs are the complete adventure artifact set plus validation, export, and
playtest reports.

Rules:

- Treat missing bindings, blocked spatial paths, impossible state gates, and
  ending mismatches as blocking.
- Route findings to the responsible role: genre, world, level, interaction,
  binder, asset, or runtime.
- Do not repair by weakening V3 ending or path-closure guarantees.
