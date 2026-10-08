"""One questions file per object (jobs/<object>/questions.md), merged from versioned spec reports.

Each question keeps a stable id across spec versions. The user's answers are never lost: a row is
matched by its geometry key, its Answer cell is kept, and a question that a newer spec no longer
raises stays in the file as `gone <version>`. Do not use `|` inside an answer.
"""
COLUMNS = ["ID", "Status", "First", "Last", "Priority", "Kind", "Levels", "Wall", "Depth m", "Length m",
           "Facade share", "Heights m", "At (x, y)", "Answer"]
INTRO = """Merged by `dt spec merge-questions` from the versioned `<spec>.report.json` files. Each row is
geometry that is not over the full storey height, so it does not change the level contour (user
decision 2026-10-08). Write the answer in the last column; ids are stable across spec versions.
Status: open, answered, or gone <version> when a newer spec no longer raises it (answers kept)."""


def _key(kind, levels, wall, heights, at):
    return "|".join([kind, levels, wall, heights, at])


def _cells(q):
    def show(v, fmt=str):
        return "—" if v is None else fmt(v)
    return {"Priority": q["priority"], "Kind": q["kind"], "Levels": ", ".join(q["levels"]),
            "Wall": show(q["wall"]), "Depth m": show(q["depth_m"]), "Length m": show(q["length_m"]),
            "Facade share": show(q["facade_share"], lambda s: f"{s:.1%}"),
            "Heights m": show(q["heights_m"], lambda h: f"{h[0]:.2f}–{h[1]:.2f}"),
            "At (x, y)": show(q["at"], lambda a: f"{a[0]:.1f}, {a[1]:.1f}")}


def parse(text):
    """Rows of an existing questions file, in order."""
    rows = []
    for line in text.splitlines():
        if line.startswith("| Q"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == len(COLUMNS):
                rows.append(dict(zip(COLUMNS, cells)))
    return rows


def merge(text, spec_id, version, questions):
    """New questions-file text: existing rows updated by this version's questions, new ones appended."""
    rows = parse(text or "")
    index = {_key(r["Kind"], r["Levels"], r["Wall"], r["Heights m"], r["At (x, y)"]): r for r in rows}
    seen = set()
    for q in questions:
        cells = _cells(q)
        key = _key(cells["Kind"], cells["Levels"], cells["Wall"], cells["Heights m"], cells["At (x, y)"])
        seen.add(key)
        row = index.get(key)
        if row is None:
            row = {"ID": f"Q{len(rows) + 1:03d}", "First": version, "Answer": ""}
            rows.append(row)
            index[key] = row
        row.update(cells, Last=version)
    for key, row in index.items():
        answered = bool(row.get("Answer"))
        row["Status"] = "answered" if answered else ("open" if key in seen else f"gone {version}")
    lines = [f"# Questions — {spec_id}", "", INTRO, "",
             "| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    lines += ["| " + " | ".join(row.get(c, "") for c in COLUMNS) + " |" for row in rows]
    return "\n".join(lines) + "\n"
