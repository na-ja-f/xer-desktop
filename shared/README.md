# shared

TypeScript types generated from `engine`'s Pydantic schemas, per the Engineering
Foundation Guide (section 1). The renderer imports types from here instead of
hand-authoring duplicates of the engine's response shapes.

Codegen tooling (Pydantic → TS, wired into CI so a schema change that breaks
the UI fails CI rather than a demo) is scoped to B-256, not this ticket —
this folder exists now so downstream tickets have somewhere to put it.
