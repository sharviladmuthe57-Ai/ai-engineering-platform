/* Lightweight SVG editor. Project coordinates remain metres, independent of view transforms. */
(() => {
  const COLORS = {db:"#f85149", light:"#ffd166", fan:"#3fb950", switch:"#1a85ff", switch2:"#5dade2", outlet:"#e8594f", outlet2:"#ff7b72", ac:"#c678dd", exhaust:"#52d273", tv:"#58a6ff", wifi:"#9b7fe8", default:"#c9d1d9"};
  const TYPE_LABELS = {ceiling_light:"Light", ceiling_fan:"Fan", switch_1way:"Switch", outlet_2pin:"Socket"};
  let state, selectedId = null, addType = null, imageSize = null, camera = {zoom:1, x:0, y:0}, drag = null, pan = null;

  const el = id => document.getElementById(id);
  const escapeHtml = value => String(value ?? "—").replace(/[&<>"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[char]));
  const svg = () => el("editor-canvas");
  const scale = () => Number(state?.scale_m_per_px) || .01;

  async function request(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Editor request failed");
    return data;
  }

  function setStatus(message, error = false) {
    const target = el("editor-status");
    if (target) { target.textContent = message; target.style.color = error ? "var(--red)" : "var(--muted)"; }
  }

  async function openEditor(jobId) {
    if (!jobId) return;
    setStatus("Loading editable project…");
    try {
      state = await request(`/project/${encodeURIComponent(jobId)}`);
      el("editor-title").textContent = `⚡ ${state.project_name || "Editable Electrical Canvas"}`;
      const editorUrl = new URL(window.location.href);
      editorUrl.searchParams.set("editor_job", jobId);
      window.history.replaceState(null, "", editorUrl);
      selectedId = null; addType = null; camera = {zoom:1, x:0, y:0};
      await loadBackground();
      el("editor-section").style.display = "block";
      el("editor-section").scrollIntoView({behavior:"smooth"});
      setStatus(`Revision ${state.revision_number} · ${state.edited ? "edited" : "generated"}`);
    } catch (error) { setStatus(error.message, true); }
  }

  function loadBackground() {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => { imageSize = {width:image.naturalWidth, height:image.naturalHeight}; render(); resolve(); };
      image.onerror = () => reject(new Error("Architectural background could not be loaded"));
      image.src = state.architecture_image_url;
    });
  }

  function projectToCanvas(position) {
    return [Number(position[0]) / scale(), imageSize.height - Number(position[1]) / scale()];
  }
  function canvasToProject(point) { return [point[0] * scale(), (imageSize.height - point[1]) * scale()]; }
  function screenPoint(event) {
    const point = svg().createSVGPoint(); point.x = event.clientX; point.y = event.clientY;
    const screen = point.matrixTransform(svg().getScreenCTM().inverse()); return [screen.x, screen.y];
  }
  function canvasPoint(event) { const point = screenPoint(event); return [(point[0] - camera.x) / camera.zoom, (point[1] - camera.y) / camera.zoom]; }
  function roomAt(position) {
    return state.rooms.find(room => position[0] >= room.x && position[0] <= room.x + room.width && position[1] >= room.y && position[1] <= room.y + room.height);
  }
  function selected() { return state?.components.find(component => component.id === selectedId); }

  function render() {
    if (!state || !imageSize) return;
    const node = svg();
    node.setAttribute("viewBox", `0 0 ${imageSize.width} ${imageSize.height}`);
    const roomsVisible = el("editor-room-toggle")?.checked;
    const routeMarkup = state.routes.map(route => `<polyline class="route" points="${route.waypoints.map(projectToCanvas).map(point => point.join(",")).join(" ")}"/>`).join("");
    const roomMarkup = roomsVisible ? state.rooms.map(room => {
      const [x, y] = projectToCanvas([room.x, room.y + room.height]);
      return `<rect class="room-boundary" x="${x}" y="${y}" width="${room.width / scale()}" height="${room.height / scale()}"/>`;
    }).join("") : "";
    const components = state.components.map(componentMarkup).join("");
    node.innerHTML = `<g id="editor-camera" transform="translate(${camera.x} ${camera.y}) scale(${camera.zoom})"><image href="${state.architecture_image_url}" x="0" y="0" width="${imageSize.width}" height="${imageSize.height}"/><g>${roomMarkup}</g><g>${routeMarkup}</g><g>${components}</g></g>`;
    renderProperties(); renderBoq(); bindSvgEvents();
  }

  function componentMarkup(component) {
    const [x, y] = projectToCanvas(component.pos);
    const selectedClass = component.id === selectedId ? " selected" : "";
    const color = COLORS[component.symbol] || COLORS.default;
    const db = component.comp_id === "db";
    const glyph = db ? `<rect class="glyph" x="-8" y="-8" width="16" height="16" rx="2"/>` : `<circle class="glyph" r="6"/>`;
    const letter = escapeHtml((component.symbol || component.comp_id || "?").slice(0, 1).toUpperCase());
    return `<g class="component${selectedClass}" data-component-id="${escapeHtml(component.id)}" transform="translate(${x} ${y})" style="color:${color}"><circle class="selection-ring" r="12"/>${glyph}<text class="component-label" y="3">${letter}</text></g>`;
  }

  function renderProperties() {
    const component = selected();
    const host = el("editor-properties");
    if (!component) { host.innerHTML = '<div class="editor-empty">Select a component to inspect or move it.</div>'; return; }
    host.innerHTML = `<dl><dt>ID</dt><dd>${escapeHtml(component.id)}</dd><dt>Type</dt><dd>${escapeHtml(component.label)}</dd><dt>Room</dt><dd>${escapeHtml(component.room_id)}</dd><dt>Position</dt><dd>${Number(component.pos[0]).toFixed(2)}, ${Number(component.pos[1]).toFixed(2)} m</dd><dt>Source</dt><dd>${escapeHtml(component.position_source || "generated")}</dd><dt>Placement</dt><dd>${escapeHtml(component.placement_method || "generated")}</dd></dl><div class="editor-action-row" style="margin-top:14px"><button class="btn editor-danger" id="editor-delete" ${component.comp_id === "db" ? "disabled" : ""}>Delete</button></div>`;
    el("editor-delete")?.addEventListener("click", deleteSelected);
  }

  function renderBoq() {
    const rows = (state.bom || []).map(item => `<tr><td>${escapeHtml(item.item)}</td><td>${escapeHtml(item.qty)}</td><td>${escapeHtml(item.unit)}</td></tr>`).join("");
    el("editor-boq").innerHTML = `<div class="section-title">Live BOQ · ${Number(state.total_wire_m || 0).toFixed(2)}m wire</div><table><thead><tr><th>Item</th><th>Qty</th><th>Unit</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  function bindSvgEvents() {
    const node = svg();
    node.onpointerdown = onPointerDown; node.onpointermove = onPointerMove; node.onpointerup = onPointerUp; node.onpointercancel = onPointerUp;
    node.onwheel = onWheel;
  }
  function onPointerDown(event) {
    const target = event.target.closest("[data-component-id]");
    if (target) {
      selectedId = target.dataset.componentId; addType = null; updatePalette(); render();
      if (selected()?.comp_id !== "db") {
        drag = {id:selectedId, start:screenPoint(event), moved:false};
        svg().setPointerCapture(event.pointerId);
      }
      return;
    }
    const point = canvasPoint(event);
    if (addType) { addAt(point); return; }
    selectedId = null; render();
    pan = {point:screenPoint(event), camera:{...camera}}; svg().setPointerCapture(event.pointerId);
  }
  function onPointerMove(event) {
    const point = canvasPoint(event);
    if (drag) {
      const screen = screenPoint(event);
      if (Math.hypot(screen[0] - drag.start[0], screen[1] - drag.start[1]) < 3 && !drag.moved) return;
      drag.moved = true;
      const group = svg().querySelector(`[data-component-id="${CSS.escape(drag.id)}"]`);
      if (group) group.setAttribute("transform", `translate(${point[0]} ${point[1]})`);
    } else if (pan) {
      const screen = screenPoint(event);
      camera.x = pan.camera.x + screen[0] - pan.point[0];
      camera.y = pan.camera.y + screen[1] - pan.point[1];
      svg().querySelector("#editor-camera")?.setAttribute("transform", `translate(${camera.x} ${camera.y}) scale(${camera.zoom})`);
    }
  }
  async function onPointerUp(event) {
    if (drag) {
      const {id, moved} = drag; drag = null;
      if (moved) {
        await moveSelected(id, canvasToProject(canvasPoint(event)));
      }
      return;
    }
    pan = null;
  }
  function onWheel(event) {
    event.preventDefault(); const point = screenPoint(event); const next = Math.max(.35, Math.min(5, camera.zoom * (event.deltaY < 0 ? 1.12 : .89)));
    camera.x = point[0] - ((point[0] - camera.x) / camera.zoom) * next; camera.y = point[1] - ((point[1] - camera.y) / camera.zoom) * next; camera.zoom = next;
    svg().querySelector("#editor-camera")?.setAttribute("transform", `translate(${camera.x} ${camera.y}) scale(${camera.zoom})`);
  }

  async function moveSelected(id, position) {
    try {
      setStatus("Updating route and BOQ…");
      state = await request(`/project/${state.job_id}/components/${encodeURIComponent(id)}`, {method:"PATCH", headers:{"Content-Type":"application/json"}, body:JSON.stringify({position})});
      setStatus(`Revision ${state.revision_number} · route and BOQ updated`); render();
    } catch (error) { setStatus(error.message, true); render(); }
  }
  async function addAt(canvasPosition) {
    const position = canvasToProject(canvasPosition); const room = roomAt(position);
    if (!room) { setStatus("Choose a point inside a detected room", true); return; }
    try {
      setStatus("Adding component and route…");
      state = await request(`/project/${state.job_id}/components`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({component_type:addType, room_id:room.id, position})});
      selectedId = state.components[state.components.length - 1].id; addType = null; updatePalette(); setStatus(`Revision ${state.revision_number} · component added`); render();
    } catch (error) { setStatus(error.message, true); }
  }
  async function deleteSelected() {
    const component = selected(); if (!component || !confirm(`Delete ${component.label}?`)) return;
    try {
      state = await request(`/project/${state.job_id}/components/${encodeURIComponent(component.id)}`, {method:"DELETE"}); selectedId = null; setStatus(`Revision ${state.revision_number} · component deleted`); render();
    } catch (error) { setStatus(error.message, true); }
  }
  async function saveProject() {
    try { state = await request(`/project/${state.job_id}/save`, {method:"POST"}); setStatus(`Saved · revision ${state.revision_number}`); render(); }
    catch (error) { setStatus(error.message, true); }
  }
  async function resetProject() {
    if (!confirm("Restore the generated electrical design? Current edits will be removed.")) return;
    try { state = await request(`/project/${state.job_id}/reset`, {method:"POST"}); selectedId = null; addType = null; updatePalette(); setStatus(`Reset to generated design · revision ${state.revision_number}`); render(); }
    catch (error) { setStatus(error.message, true); }
  }
  function fitView() { camera = {zoom:1, x:0, y:0}; render(); }
  function updatePalette() { document.querySelectorAll(".editor-tool[data-component-type]").forEach(button => button.classList.toggle("active", button.dataset.componentType === addType)); }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".editor-tool[data-component-type]").forEach(button => button.addEventListener("click", () => { addType = addType === button.dataset.componentType ? null : button.dataset.componentType; selectedId = null; updatePalette(); render(); setStatus(addType ? `Click inside a room to add ${TYPE_LABELS[addType]}` : "Add mode cancelled"); }));
    el("editor-save")?.addEventListener("click", saveProject); el("editor-reset")?.addEventListener("click", resetProject); el("editor-fit")?.addEventListener("click", fitView); el("editor-room-toggle")?.addEventListener("change", render);
    const requested = new URLSearchParams(window.location.search).get("editor_job"); if (requested) openEditor(requested);
  });
  window.openEditor = openEditor;
})();
