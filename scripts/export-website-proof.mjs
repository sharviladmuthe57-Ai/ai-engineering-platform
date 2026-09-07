/** Export real prototype evidence without changing any job or engineering behavior. */
import { readFileSync, writeFileSync, mkdirSync, copyFileSync } from 'node:fs';
import vm from 'node:vm';
import sharp from 'sharp';

const jobId = process.argv[2] || '5d982950';
if (!/^[a-f0-9]+$/.test(jobId)) throw new Error('Expected a local completed job id');
const job = JSON.parse(readFileSync(`jobs/${jobId}.json`, 'utf8'));
const state = structuredClone(job.project_state);
if (!state?.components?.length) throw new Error('Job has no real editable state');
const planPath = `uploads/${jobId}.png`;
const { width, height } = await sharp(planPath).metadata();
mkdirSync('public/product', { recursive: true });
mkdirSync('src/data', { recursive: true });
copyFileSync(planPath, 'public/product/electrical-input.png');
const evidence = {
  source: `Completed prototype job ${jobId}`, width, height,
  scale: state.scale_m_per_px, revision: state.revision_number,
  rooms: state.rooms.map(({ id, name, x, y, width, height }) => ({ id, name, x, y, width, height })),
  components: state.components.map(({ id, label, symbol, comp_id, pos }) => ({ id, label, symbol, comp_id, pos })),
  routes: state.routes.map(({ waypoints }) => ({ waypoints })),
  bom: state.bom.map(({ item, qty, unit }) => ({ item, qty, unit })),
  totalWire: state.total_wire_m,
};
writeFileSync('src/data/demo-project.json', JSON.stringify(evidence));

// Run the existing editor's actual rendering functions against a minimal DOM.
// This is a static export of the product, not a redesigned/fabricated workspace.
state.architecture_image_url = './electrical-input.png';
const nodes = new Map();
const getNode = (id) => {
  if (!nodes.has(id)) nodes.set(id, { innerHTML: '', attributes: {}, checked: true,
    setAttribute(k, v) { this.attributes[k] = v; }, addEventListener() {} });
  return nodes.get(id);
};
const context = {
  document: { getElementById: getNode, addEventListener() {}, querySelectorAll: () => [] },
  window: {},
};
const source = readFileSync('static/editor.js', 'utf8').replace('window.openEditor = openEditor;',
  'window.exportProof = (s, size) => { state = s; imageSize = size; selectedId = s.components.find(c => c.comp_id !== "db").id; render(); };');
vm.runInNewContext(source, context);
context.window.exportProof(state, { width, height });
const original = readFileSync('static/index.html', 'utf8');
const baseCss = original.match(/<style>([\s\S]*?)<\/style>/)[1];
const editorCss = readFileSync('static/editor.css', 'utf8');
let shell = original.slice(original.indexOf('<div class="editor-shell">'), original.indexOf('\n</div>\n\n<script>'));
shell = shell.replace(/<svg id="editor-canvas"[^>]*><\/svg>/,
  `<svg id="editor-canvas" class="editor-canvas" viewBox="0 0 ${width} ${height}" aria-label="Real electrical plan with components and routes">${getNode('editor-canvas').innerHTML}</svg>`)
  .replace('<div id="editor-properties" class="editor-properties"></div>', `<div class="editor-properties">${getNode('editor-properties').innerHTML}</div>`)
  .replace('<div id="editor-boq" class="editor-boq"></div>', `<div class="editor-boq">${getNode('editor-boq').innerHTML}</div>`)
  .replace('Ready to edit', 'Product snapshot · editing available in the local prototype')
  .replace(/<button /g, '<button disabled tabindex="-1" ')
  .replace('<input type="checkbox"', '<input disabled checked type="checkbox"');
writeFileSync('public/product/editor-v1.html', `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Actual Editable 2D Canvas V1 — static product export</title><style>${baseCss}\n${editorCss}\nbody{min-height:0}.editor-shell{border:0;border-radius:0}.editor-canvas-wrap{height:500px}@media(max-width:700px){.editor-canvas-wrap{height:370px}}</style><body>${shell}</body></html>`);
console.log(`Exported actual editor: ${evidence.components.length} components, ${evidence.routes.length} routes, ${evidence.bom.length} BOQ lines. No local paths or credentials included.`);
