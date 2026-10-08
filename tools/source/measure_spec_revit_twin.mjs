// Export the active Revit document per storey band for the spec extractor (issue #29). The
// Revit model is never changed or saved; files are written only into a new folder.
//
//   node tools/source/measure_spec_revit_twin.mjs <out-folder>
//
// Calls the TwinPack commands of the revit-http add-in (docs/agents/CAPABILITIES.md):
// twin_floor_manifest (bands, levels, coordinates), then twin_export_floor for every band with
// exterior elements (floor.json + reference.obj in <out-folder>/band-<n>/), and writes
// <out-folder>/twin-data.json, the index `dt spec extract --dump` reads. The document's
// modified flag is recorded before and after. Server: REVIT_MCP_SERVER_DIR, default the
// workstation install.
import fs from 'node:fs';
import path from 'node:path';

const DIR = process.env.REVIT_MCP_SERVER_DIR || 'C:/Users/artsafro/INTERACTIVE_TOUR/RevitMCPServer';
process.env.REVIT_MCP_VERSION = process.env.REVIT_MCP_VERSION || '2025';
process.env.REVIT_MCP_PORT = process.env.REVIT_MCP_PORT || '7891';
// every wall function: interior walls close shafts through the roof; only exterior walls can be attachments
const WALL_FUNCTIONS = ['Exterior', 'Interior', 'Foundation', 'Retaining', 'Soffit', 'CoreShaft'];
const out = process.argv[2];
if (!out) throw new Error('usage: node measure_spec_revit_twin.mjs <out-folder>');
if (fs.existsSync(out)) throw new Error(`refusing to write into existing ${out}; use a new versioned folder`);
const {callRevit} = await import(`file:///${DIR}/dist/revitClient.js`);

async function call(cmd, params = {}) {
  const r = await callRevit(cmd, params);
  if (!r.ok) throw new Error(`${cmd}: ${JSON.stringify(r.error ?? r).slice(0, 300)}`);
  return r.data;
}

const before = await call('get_document_info');
const manifest = await call('twin_floor_manifest');
const bands = manifest.bands.filter(b => Object.entries(b.exteriorElements).some(([k, n]) => k !== 'floor' && n > 0));
fs.mkdirSync(out, {recursive: true});
const index = [];
for (const b of bands) {
  const dir = `band-${b.band}`;
  const abs = path.resolve(out, dir);
  fs.mkdirSync(abs);
  const r = await call('twin_export_floor', {band: b.band, outDir: abs, wallFunctions: WALL_FUNCTIONS});
  index.push({band: b.band, level: b.level, elevation: b.elevation, bottom: b.bottom, top: b.top, dir, counts: r.counts});
}
const after = await call('get_document_info');
fs.writeFileSync(path.join(out, 'twin-data.json'), JSON.stringify({
  kind: 'revit-twin', source: 'revit', document: before.title, path: before.pathName,
  modified_before: before.isModified, modified_after: after.isModified, coordinates: manifest.coordinates,
  bands: index}, null, 1));
console.log(`MEASURE-SPEC-REVIT-TWIN ${index.length} bands -> ${out}; modified ${before.isModified} -> ${after.isModified}`);
