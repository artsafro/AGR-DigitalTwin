# Material IDs are a reading scheme; UDIM tiles and slots are assigned on export

Status: accepted (2026-10-08, plan grilling Q4).

Inside the working model, material IDs follow group ranges (`docs/HARNESS_PLAN.md` §6:
1–5 facade, 6–10 reveals, 11–15 openings, …), and an unused group leaves its range empty.
This scheme exists so an agent or a person can read the model. It is not the delivery
numbering: the regulation requires VPM UDIM tiles 1001..1100 without gaps and glass only
in 1001 (V008, reg p. 31, 39), and one slot until more than 100 tiles (reg p. 30 §4.3-4.4).
Export therefore renumbers material IDs into dense UDIM tiles / atlas regions and slots by
the regulation, and **glass always goes to 1001**, whatever its material ID.

Considered: shifting the ranges so glass is ID 1 (keeps ID = tile, but breaks again at the
first empty group); dropping the ranges (loses readability of the working model).
