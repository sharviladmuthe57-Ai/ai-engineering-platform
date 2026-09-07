/* Lightweight SVG editor. Project coordinates remain metres, independent of view transforms. */
(() => {
  const COLORS = {db:"#b86351", light:"#a67921", fan:"#408570", switch:"#407994", switch2:"#407994", outlet:"#b86351", outlet2:"#b86351", ac:"#408570", exhaust:"#408570", tv:"#407994", wifi:"#407994", default:"#66786c"};
  const TYPE_LABELS = {ceiling_light:"Light", ceiling_fan:"Fan", switch_1way:"Switch", outlet_2pin:"Socket"};
  let state, selectedId = null, addType = null, imageSize = null, camera = {zoom:1, x:0, y:0}, drag = null, pan = null, busy = false;

  const el = id => document.getElementById(id);
  const escapeHtml = value => String(value ?? "—").replace(/[&<>"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[char]));
  const svg = () => el("editor-canvas");
  const scale = () => Number(state?.scale_m_per_px) || .01;

  async function request(url, options = {}) {
    busy = true;
    document.querySelector(".editor-shell")?.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(url, options);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Could not update the drawing. Please try again.");
      return data;
    } finally {
      busy = false;
      document.querySelector(".editor-shell")?.setAttribute("aria-busy", "false");
    }
  }

  function setStatus(message, error = false) {
    const target = el("editor-status");
    if (target) { target.textContent = message; target.classList.toggle("error", error); }
  }

  async function openEditor(jobId) {
    if (!jobId) return;
    setStatus("Loading editable project…");
    try {
      state = await request(`/project/${encodeURIComponent(jobId)}`);
      el("editor-title").textContent = state.project_name || "Electrical drawing";
      const editorUrl = new URL(window.location.href);
      editorUrl.searchParams.set("editor_job", jobId);
      window.history.replaceState(null, "", editorUrl);
      selectedId = null; addType = null; camera = {zoom:1, x:0, y:0};
      await loadBackground();
      el("editor-section").style.display = "block";
      el("editor-section").scrollIntoView({behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
      setStatus(state.edited ? "Your edits are ready" : "Ready to edit");
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
  function roomName(roomId) {
    const room = state.rooms.find(item => item.id === roomId);
    if (!room) return "Building";
    const name = String(room.name || room.type || "Room").replace(/_/g, " ");
    const peers = state.rooms.filter(item => (item.name || item.type || "Room") === (room.name || room.type || "Room"));
    const suffix = peers.length > 1 ? ` ${peers.findIndex(item => item.id === roomId) + 1}` : "";
    return name.replace(/\b\w/g, char => char.toUpperCase()) + suffix;
  }

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
    return `<g class="component${selectedClass}" data-component-id="${escapeHtml(component.id)}" transform="translate(${x} ${y})" style="color:${color}" role="button" tabindex="0" aria-label="${escapeHtml(component.label)} in ${escapeHtml(roomName(component.room_id))}"><title>${escapeHtml(component.label)} · drag to move</title><circle class="hit-area" r="12"/><circle class="selection-ring" r="12"/>${glyph}<text class="component-label" y="3">${letter}</text></g>`;
  }

  function renderProperties() {
    const component = selected();
    const host = el("editor-properties");
    if (!component) { host.innerHTML = '<div class="editor-empty"><svg class="empty-pointer" viewBox="0 0 24 24" aria-hidden="true"><path d="m5 3 14 9-7 1-4 6z"/></svg><h3>Select an item</h3><p>Click an electrical point to inspect it. Drag it to move it.</p></div>'; return; }
    const advancedOpen = el("editor-advanced")?.open;
    host.innerHTML = `<h3>${escapeHtml(TYPE_LABELS[component.comp_id] || component.label)}</h3><p>${escapeHtml(roomName(component.room_id))}</p><p class="selection-position">Position: ${Number(component.pos[0]).toFixed(2)}, ${Number(component.pos[1]).toFixed(2)} m</p><button class="editor-button editor-delete" id="editor-delete" ${component.comp_id === "db" ? "disabled" : ""}>Delete item</button><details class="editor-advanced" id="editor-advanced" ${advancedOpen ? "open" : ""}><summary>Advanced details</summary><dl><dt>Component ID</dt><dd>${escapeHtml(component.id)}</dd><dt>Room ID</dt><dd>${escapeHtml(component.room_id)}</dd><dt>Source</dt><dd>${escapeHtml(component.position_source || "generated")}</dd><dt>Placement</dt><dd>${escapeHtml(component.placement_method || "generated")}</dd><dt>Revision</dt><dd>${state.revision_number}</dd></dl></details>`;
    el("editor-delete")?.addEventListener("click", deleteSelected);
  }

  function renderBoq() {
    const open = el("editor-full-boq")?.open;
    const rows = (state.bom || []).map(item => `<tr><td>${escapeHtml(item.item)}</td><td>${escapeHtml(item.qty)}</td><td>${escapeHtml(item.unit)}</td></tr>`).join("");
    const count = predicate => state.components.filter(component => predicate(component.comp_id)).length;
    const summary = [[count(id => id === "ceiling_light"), "Lights"], [count(id => id === "ceiling_fan"), "Fans"], [count(id => id.startsWith("switch_")), "Switches"], [count(id => id.startsWith("outlet_")), "Sockets"]];
    el("editor-boq").innerHTML = `<h3>Quantities <span>Live BOQ</span></h3><div class="boq-summary">${summary.map(([qty,label]) => `<div><strong data-quantity="${label.toLowerCase()}">${qty}</strong><span>${label}</span></div>`).join("")}</div><div class="editor-wire"><span>Estimated wire</span><strong data-wire-total>${Number(state.total_wire_m || 0).toFixed(2)} <small>m</small></strong></div><details class="boq-details" id="editor-full-boq" ${open ? "open" : ""}><summary>View full BOQ</summary><div><table><thead><tr><th>Item</th><th>Qty</th><th>Unit</th></tr></thead><tbody>${rows}</tbody></table></div></details>`;
  }

  function bindSvgEvents() {
    const node = svg();
    node.onpointerdown = onPointerDown; node.onpointermove = onPointerMove; node.onpointerup = onPointerUp;
    node.onpointercancel = () => { drag = null; pan = null; node.classList.remove("is-dragging"); render(); };
    node.onkeydown = event => {
      const component = event.target.closest("[data-component-id]");
      if (component && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); selectedId = component.dataset.componentId; addType = null; updatePalette(); renderProperties(); render(); }
    };
    node.onwheel = onWheel;
  }
  function onPointerDown(event) {
    if (busy) return;
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
      svg().classList.add("is-dragging");
      const group = svg().querySelector(`[data-component-id="${CSS.escape(drag.id)}"]`);
      if (group) {
        group.setAttribute("transform", `translate(${point[0]} ${point[1]})`);
        const position = canvasToProject(point);
        const room = state.rooms.find(item => item.id === selected().room_id);
        const valid = room && position[0] >= room.x && position[0] <= room.x + room.width && position[1] >= room.y && position[1] <= room.y + room.height;
        group.classList.toggle("invalid", !valid);
      }
    } else if (pan) {
      const screen = screenPoint(event);
      camera.x = pan.camera.x + screen[0] - pan.point[0];
      camera.y = pan.camera.y + screen[1] - pan.point[1];
      svg().querySelector("#editor-camera")?.setAttribute("transform", `translate(${camera.x} ${camera.y}) scale(${camera.zoom})`);
    }
  }
  async function onPointerUp(event) {
    svg().classList.remove("is-dragging");
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
      setStatus("Route + quantities updated ✓"); render();
    } catch (error) { setStatus(error.message, true); render(); }
  }
  async function addAt(canvasPosition) {
    const position = canvasToProject(canvasPosition); const room = roomAt(position);
    if (!room) { setStatus("Choose a point inside a room on the drawing", true); return; }
    try {
      setStatus("Adding component and route…");
      state = await request(`/project/${state.job_id}/components`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({component_type:addType, room_id:room.id, position})});
      selectedId = state.components[state.components.length - 1].id; addType = null; updatePalette(); setStatus("Item added · routes + quantities updated ✓"); render();
    } catch (error) { setStatus(error.message, true); }
  }
  async function deleteSelected() {
    if (busy) return;
    const component = selected(); if (!component || !confirm(`Delete ${component.label}?`)) return;
    try {
      state = await request(`/project/${state.job_id}/components/${encodeURIComponent(component.id)}`, {method:"DELETE"}); selectedId = null; setStatus("Item deleted · quantities updated ✓"); render();
    } catch (error) { setStatus(error.message, true); }
  }
  async function saveProject() {
    if (busy) return;
    try { state = await request(`/project/${state.job_id}/save`, {method:"POST"}); setStatus("Saved ✓"); render(); }
    catch (error) { setStatus(error.message, true); }
  }
  async function resetProject() {
    if (busy) return;
    if (!confirm("Restore the generated electrical design? Current edits will be removed.")) return;
    try { state = await request(`/project/${state.job_id}/reset`, {method:"POST"}); selectedId = null; addType = null; updatePalette(); setStatus("Original generated drawing restored"); render(); }
    catch (error) { setStatus(error.message, true); }
  }
  function fitView() { camera = {zoom:1, x:0, y:0}; render(); setStatus("Drawing fitted to view"); }
  function updatePalette() {
    document.querySelectorAll(".editor-tool[data-component-type]").forEach(button => {
      const active = button.dataset.componentType === addType;
      button.classList.toggle("active", active); button.setAttribute("aria-pressed", String(active));
    });
    svg()?.classList.toggle("add-mode", !!addType);
    el("editor-instruction").innerHTML = addType ? `<strong>Click inside a room to place a ${TYPE_LABELS[addType].toLowerCase()}.</strong> Choose the tool again to cancel.` : "<strong>Click an item to select it. Drag to move.</strong> Choose + Add to place a new one.";
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".editor-tool[data-component-type]").forEach(button => button.addEventListener("click", () => { if (busy) return; addType = addType === button.dataset.componentType ? null : button.dataset.componentType; selectedId = null; updatePalette(); render(); setStatus(addType ? `Adding ${TYPE_LABELS[addType].toLowerCase()}` : "Ready to edit"); }));
    el("editor-add-toggle")?.addEventListener("click", () => { const palette = el("editor-palette"); palette.hidden = !palette.hidden; el("editor-add-toggle").setAttribute("aria-expanded", String(!palette.hidden)); if (palette.hidden) { addType = null; updatePalette(); } });
    el("editor-save")?.addEventListener("click", saveProject); el("editor-reset")?.addEventListener("click", resetProject); el("editor-fit")?.addEventListener("click", fitView); el("editor-room-toggle")?.addEventListener("change", render);
    const requested = new URLSearchParams(window.location.search).get("editor_job"); if (requested) openEditor(requested);
  });
  window.openEditor = openEditor;
})();
