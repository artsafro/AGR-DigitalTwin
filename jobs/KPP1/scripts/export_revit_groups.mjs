// Export KPP1 Revit element groups to FBX through the RevitBridge pipe (agr_export_fbx), one FBX per group.
// Usage: node export_revit_groups.mjs <elements.json> <out_dir> [group,group...]
// elements.json: {"OST_Walls": [{id, name, typeId}], ...} paged from revit-http revit_list_elements.
// Groups go by element id: agr_export_fbx exports the WHOLE model when a category name is unknown.
// Does not save the RVT (savedDocument=false is checked).
import fs from "node:fs";
import { callBridge } from "file:///C:/Users/artsafro/tools/revit-bridge-mcp/src/bridgeClient.js";

const [elementsPath, outDir, only] = process.argv.slice(2);
const d = JSON.parse(fs.readFileSync(elementsPath, "utf8"));
const ids = (cats, f = () => true) => cats.flatMap((c) => (d[c] || []).filter(f).map((e) => e.id));
const inner = (e) => /^ADSK_Внутренняя/.test(e.name);
const curt = (e) => e.name.includes("Витраж") || e.name.startsWith("ADSK_Обрамление");
const groups = {
  walls_ext: ids(["OST_Walls"], (e) => !inner(e) && !curt(e)),
  walls_int: ids(["OST_Walls"], inner),
  curtain: [...ids(["OST_Walls"], curt), ...ids(["OST_CurtainWallPanels", "OST_CurtainWallMullions"])],
  openings: ids(["OST_Doors", "OST_Windows"]),
  floors: ids(["OST_Floors"]),
  roofs: ids(["OST_Roofs"]),
  generic: ids(["OST_GenericModel"]),
  stairs_rails_equip: ids(["OST_Stairs", "OST_StairsRuns", "OST_StairsLandings", "OST_StairsStringerCarriage",
    "OST_StairsRailing", "OST_StairsRailingBaluster", "OST_RailingTopRail", "OST_MechanicalEquipment",
    "OST_SpecialityEquipment", "OST_DuctTerminal"]),
};
fs.mkdirSync(outDir, { recursive: true });
for (const [name, list] of Object.entries(groups)) {
  if (only && !only.split(",").includes(name)) continue;
  if (!list.length) { console.log(name, "empty"); continue; }
  const r = await callBridge("agr_export_fbx", { confirm: true, folder: outDir, name, elementIds: list }, { timeoutMs: 900000 });
  const ok = r.ok && r.data?.savedDocument === false;
  console.log(name, list.length, ok ? `ok ${r.data.bytes} B, ${r.data.elementCount} el` : JSON.stringify(r.error || r.data));
}
