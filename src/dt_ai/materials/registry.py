from dt_ai.core.models import MaterialRegistry


def merge_proposals(current: MaterialRegistry, proposed: MaterialRegistry):
    """Keep approved values; changed proposals are returned separately for review."""
    merged = {m.id: m.model_dump() for m in current.materials}
    conflicts = []
    for incoming in proposed.materials:
        prior = merged.get(incoming.id)
        new = incoming.model_dump()
        if prior and prior["status"] == "approved" and prior != new:
            conflicts.append({"material_id": incoming.id, "status": "conflict",
                              "approved": prior, "proposal": new})
        else:
            merged[incoming.id] = new
    return MaterialRegistry(materials=[merged[k] for k in sorted(merged)]), conflicts
