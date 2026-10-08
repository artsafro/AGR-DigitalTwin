// Read the active Revit document for the spec extractor (issue #10). READ ONLY: the model is
// never changed or saved.
//
//   node tools/source/measure_spec_revit.mjs <revit-data.json>
//
// Writes levels and, for walls, windows, doors and roofs, the bounding box (feet), the wall
// length, width (type) and system family, and the roof volume, through the revit-http MCP route (docs/agents/CAPABILITIES.md).
// Neither MCP route exposes wall location lines, so geometry comes from bounding boxes; the
// conversion (dt_ai.spec.revit) refuses walls that do not run along X or Y (user decision
// 2026-10-08). Server path: REVIT_MCP_SERVER, default the workstation install.
import fs from 'node:fs';

const SERVER = process.env.REVIT_MCP_SERVER || 'C:/Users/artsafro/INTERACTIVE_TOUR/RevitMCPServer/dist/index.js';
const SDK = process.env.REVIT_MCP_SDK || 'C:/Users/artsafro/INTERACTIVE_TOUR/RevitMCPServer/node_modules/@modelcontextprotocol/sdk/dist/esm';
const out = process.argv[2];
if (!out) throw new Error('usage: node measure_spec_revit.mjs <revit-data.json>');
if (fs.existsSync(out)) throw new Error(`refusing to overwrite ${out}; use a new versioned path`);

const {Client} = await import(`file:///${SDK}/client/index.js`);
const {StdioClientTransport} = await import(`file:///${SDK}/client/stdio.js`);
const client = new Client({name: 'measure-spec-revit', version: '0.1.0'});
await client.connect(new StdioClientTransport({command: process.execPath, args: [SERVER],
  env: {...process.env, REVIT_MCP_VERSION: '2025', REVIT_MCP_PORT: process.env.REVIT_MCP_PORT || '7891'}, stderr: 'pipe'}));

async function call(name, args = {}) {
  const r = await client.callTool({name, arguments: args}, undefined, {timeout: 240000});
  const text = (r.content || []).map(c => c.text || '').join('');
  const body = JSON.parse(text);
  if (r.isError || body.ok === false) throw new Error(`${name}: ${text.slice(0, 300)}`);
  return body.data ?? body;
}

async function all(category) {
  const ids = [];
  for (let offset = 0; ; ) {
    const page = await call('revit_list_elements', {category, onlyInstances: true, limit: 1000, offset});
    ids.push(...page.elements.map(e => e.id));
    if (!page.hasMore) return ids;
    offset = page.nextOffset;
  }
}

const param = (info, ...names) => (info.parameters || []).find(p => names.includes(p.name));
try {
  const doc = await call('revit_get_document_info');
  if (doc.isModified) console.warn('WARNING: the document reports unsaved changes; reading anyway, never saving');
  const levels = (await call('revit_list_levels')).levels.map(l => ({name: l.name, elev_m: l.elevationMeters}));
  const elements = [], widths = {};
  for (const category of ['OST_Walls', 'OST_Windows', 'OST_Doors', 'OST_Roofs']) {
    for (const id of await all(category)) {
      const info = await call('revit_get_element_info', {id});
      if (!info.boundingBox) continue;
      const e = {id, category, type: (param(info, 'Тип', 'Type') || {}).valueString ?? info.name,
                 bbox_ft: info.boundingBox};
      if (category === 'OST_Walls') {
        e.length_ft = (param(info, 'Длина', 'Length') || {}).value ?? null;
        e.family = (param(info, 'Семейство', 'Family') || {}).valueString ?? null;   // system family: basic / curtain
        if (info.typeId != null && !(info.typeId in widths))                          // wall width is a type parameter
          widths[info.typeId] = (param(await call('revit_get_element_info', {id: info.typeId}), 'Толщина', 'Width') || {}).value ?? null;
        e.width_ft = widths[info.typeId] ?? null;
      }
      if (category === 'OST_Roofs') e.volume_ft3 = (await call('revit_get_element_geometry', {id})).volumeCubicFeet;
      elements.push(e);
    }
  }
  const after = await call('revit_get_document_info');
  fs.writeFileSync(out, JSON.stringify({kind: 'revit-data', source: 'revit', document: doc.title, path: doc.pathName,
    modified_before: doc.isModified, modified_after: after.isModified, units: 'ft', levels, elements}));
  console.log(`MEASURE-SPEC-REVIT ${elements.length} elements, ${levels.length} levels -> ${out}`);
} finally {
  await client.close();
}
