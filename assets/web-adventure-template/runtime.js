(function () {
  "use strict";

  const manifest = window.NARRATIVE_ADVENTURE || {};
  const branchGraph = manifest.branch_graph || {};
  const bindings = manifest.bindings || {};
  const state = clone(manifest.initial_state || {});

  const canvas = document.getElementById("game-canvas");
  const ctx = canvas.getContext("2d");
  const gameTitle = document.getElementById("game-title");
  const levelTitle = document.getElementById("level-title");
  const levelSummary = document.getElementById("level-summary");
  const actionPrompt = document.getElementById("action-prompt");
  const endingPanel = document.getElementById("ending-panel");
  const endingKicker = document.getElementById("ending-kicker");
  const endingTitle = document.getElementById("ending-title");
  const endingBody = document.getElementById("ending-body");
  const restartButton = document.getElementById("restart");
  const endingRestart = document.getElementById("ending-restart");

  const levelById = new Map(asArray(manifest.levels).map((level) => [level.level_id, level]));
  const nodeById = new Map(asArray(branchGraph.nodes).map((node) => [node.id, node]));
  const edgeById = new Map(asArray(branchGraph.edges).map((edge) => [edge.id, edge]));
  const interactionById = new Map(asArray(manifest.interactions).map((interaction) => [interaction.interaction_id, interaction]));
  const edgeBindingById = new Map(asArray(bindings.edge_bindings).map((binding) => [binding.edge_id, binding]));
  const nodeBindingById = new Map(asArray(bindings.node_bindings).map((binding) => [binding.node_id, binding]));
  const nodeToLevel = new Map(asArray(bindings.node_bindings).map((binding) => [binding.node_id, binding.level_id]));
  const endingByNode = new Map(asArray(bindings.ending_bindings).map((ending) => [ending.terminal_node_id, ending]));
  const endingCatalogByNode = new Map(asArray(manifest.ending_catalog).map((ending) => [ending.node_id, ending]));
  const interactionsByLevel = new Map();

  asArray(manifest.interactions).forEach((interaction) => {
    const list = interactionsByLevel.get(interaction.level_id) || [];
    list.push(interaction);
    interactionsByLevel.set(interaction.level_id, list);
  });

  let viewport = { width: 960, height: 540, scale: 48, cameraX: 0 };
  let currentNodeId = branchGraph.start_node_id || manifest.unity_runtime?.start_node_id;
  let currentLevelId = nodeToLevel.get(currentNodeId) || manifest.world_map?.start_level_id || manifest.unity_runtime?.start_level_id;
  let currentLevel = levelById.get(currentLevelId) || asArray(manifest.levels)[0] || {};
  let activeInteraction = null;
  let lastTime = 0;
  let ended = false;
  const pressed = new Set();
  const player = {
    x: 2,
    y: 1.5,
    facing: 1,
  };

  gameTitle.textContent = branchGraph.title || manifest.world_map?.title || "横版冒险";
  restartButton.addEventListener("click", restart);
  endingRestart.addEventListener("click", restart);
  window.addEventListener("resize", resizeCanvas);
  window.addEventListener("keydown", handleKeyDown);
  window.addEventListener("keyup", handleKeyUp);
  document.querySelectorAll("[data-control]").forEach(bindControlButton);

  resizeCanvas();
  enterNode(currentNodeId || asArray(branchGraph.nodes)[0]?.id);
  requestAnimationFrame(loop);

  function clone(value) {
    return JSON.parse(JSON.stringify(value || {}));
  }

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function text(value, fallback) {
    if (typeof value === "string" && value.trim()) return value.trim();
    return fallback || "";
  }

  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    viewport.width = Math.max(320, Math.floor(rect.width));
    viewport.height = Math.max(240, Math.floor(rect.height));
    canvas.width = Math.floor(viewport.width * dpr);
    canvas.height = Math.floor(viewport.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function handleKeyDown(event) {
    if (event.code === "ArrowLeft" || event.code === "KeyA") {
      pressed.add("left");
      event.preventDefault();
    } else if (event.code === "ArrowRight" || event.code === "KeyD") {
      pressed.add("right");
      event.preventDefault();
    } else if (event.code === "Space" || event.code === "KeyE" || event.code === "Enter") {
      if (!event.repeat) triggerActiveInteraction();
      event.preventDefault();
    }
  }

  function handleKeyUp(event) {
    if (event.code === "ArrowLeft" || event.code === "KeyA") pressed.delete("left");
    if (event.code === "ArrowRight" || event.code === "KeyD") pressed.delete("right");
  }

  function bindControlButton(button) {
    const control = button.dataset.control;
    const release = (event) => {
      if (control !== "action") pressed.delete(control);
      event.preventDefault();
    };
    button.addEventListener("pointerdown", (event) => {
      if (control === "action") {
        triggerActiveInteraction();
      } else {
        pressed.add(control);
      }
      event.preventDefault();
    });
    button.addEventListener("pointerup", release);
    button.addEventListener("pointercancel", release);
    button.addEventListener("pointerleave", release);
  }

  function restart() {
    Object.keys(state).forEach((key) => delete state[key]);
    Object.assign(state, clone(manifest.initial_state || {}));
    ended = false;
    endingPanel.hidden = true;
    enterNode(branchGraph.start_node_id || manifest.unity_runtime?.start_node_id || asArray(branchGraph.nodes)[0]?.id);
  }

  function enterNode(nodeId) {
    if (!nodeId) return;
    currentNodeId = nodeId;
    currentLevelId = nodeToLevel.get(nodeId) || currentLevelId;
    currentLevel = levelById.get(currentLevelId) || currentLevel || {};
    const spawn = asArray(currentLevel.spawn_points)[0] || {};
    player.x = Number(spawn.x || 2);
    player.y = floorYAt(player.x) + 0.5;
    activeInteraction = null;
    updateHud();
    if (isTerminalNode(nodeId) || currentLevel.is_terminal) {
      showEnding(nodeId);
    }
  }

  function updateHud() {
    const node = nodeById.get(currentNodeId) || {};
    levelTitle.textContent = text(currentLevel.title, currentLevelId || "");
    levelSummary.textContent = text(currentLevel.summary, text(node.summary, node.title || ""));
  }

  function isTerminalNode(nodeId) {
    const node = nodeById.get(nodeId) || {};
    return node.is_terminal === true || node.node_type === "terminal" || endingByNode.has(nodeId);
  }

  function showEnding(nodeId) {
    ended = true;
    const node = nodeById.get(nodeId) || {};
    const binding = endingByNode.get(nodeId) || {};
    const catalog = endingCatalogByNode.get(nodeId) || {};
    const endingId = binding.ending_id || catalog.ending_id || node.ending_id || node.variant_of_ending_id || "ending";
    endingKicker.textContent = endingId;
    endingTitle.textContent = text(node.title, text(catalog.title, binding.ending_variant_id || endingId));
    endingBody.textContent = text(node.summary, text(currentLevel.summary, "The route reaches its ending."));
    endingPanel.hidden = false;
  }

  function loop(timestamp) {
    const dt = Math.min(0.05, (timestamp - lastTime) / 1000 || 0);
    lastTime = timestamp;
    update(dt);
    render();
    requestAnimationFrame(loop);
  }

  function update(dt) {
    if (!ended) {
      const speed = 5.2;
      let direction = 0;
      if (pressed.has("left")) direction -= 1;
      if (pressed.has("right")) direction += 1;
      if (direction !== 0) {
        player.facing = direction;
        player.x += direction * speed * dt;
      }
      const walk = walkBounds();
      player.x = clamp(player.x, walk.min, walk.max);
      player.y = floorYAt(player.x) + 0.5;
      activeInteraction = nearestAvailableInteraction();
    }
    updatePrompt();
    updateCamera();
  }

  function walkBounds() {
    const surfaces = asArray(currentLevel.walkable_surfaces);
    if (!surfaces.length) return { min: 1, max: Number(currentLevel.dimensions?.width || 34) - 1 };
    let min = Infinity;
    let max = -Infinity;
    surfaces.forEach((surface) => {
      const from = surface.from || {};
      const to = surface.to || {};
      min = Math.min(min, Number(from.x || 0), Number(to.x || 0));
      max = Math.max(max, Number(from.x || 0), Number(to.x || 0));
    });
    if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return { min: 1, max: Number(currentLevel.dimensions?.width || 34) - 1 };
    return { min: min + 0.4, max: max - 0.4 };
  }

  function floorYAt(x) {
    let best = null;
    asArray(currentLevel.walkable_surfaces).forEach((surface) => {
      const from = surface.from || {};
      const to = surface.to || {};
      const x1 = Number(from.x || 0);
      const x2 = Number(to.x || 0);
      if (x >= Math.min(x1, x2) - 0.2 && x <= Math.max(x1, x2) + 0.2) {
        best = Number(from.y || to.y || 1);
      }
    });
    return best == null ? 1 : best;
  }

  function currentNodeInteractions() {
    return asArray(interactionsByLevel.get(currentLevelId)).filter((interaction) => {
      if (interaction.source_node_id && interaction.source_node_id !== currentNodeId) return false;
      return true;
    });
  }

  function nearestAvailableInteraction() {
    let nearest = null;
    let bestDistance = Infinity;
    currentNodeInteractions().forEach((interaction) => {
      if (!interactionPasses(interaction)) return;
      const position = interaction.position || {};
      const radius = Number(interaction.activation?.radius || 2);
      const dx = Number(position.x || 0) - player.x;
      const dy = Number(position.y || 1.5) - player.y;
      const distance = Math.hypot(dx, dy);
      if (distance <= radius && distance < bestDistance) {
        nearest = interaction;
        bestDistance = distance;
      }
    });
    return nearest;
  }

  function updatePrompt() {
    if (ended) {
      actionPrompt.hidden = true;
      return;
    }
    if (activeInteraction) {
      actionPrompt.textContent = activeInteraction.label || activeInteraction.feedback?.caption || "互动";
      actionPrompt.hidden = false;
    } else {
      actionPrompt.hidden = true;
    }
  }

  function triggerActiveInteraction() {
    if (ended || !activeInteraction) return;
    const interaction = activeInteraction;
    const completion = interaction.completion || {};
    const edgeId = completion.edge_id;
    const edge = edgeById.get(edgeId) || {};
    const edgeBinding = edgeBindingById.get(edgeId) || {};
    if (!interactionPasses(interaction)) return;
    const writes = asArray(completion.state_writes).length
      ? completion.state_writes
      : (asArray(edgeBinding.effects).length ? edgeBinding.effects : edge.effects);
    applyWrites(writes);
    const targetNodeId = completion.target_node_id || edgeBinding.target_node_id || edge.to;
    if (targetNodeId) enterNode(targetNodeId);
  }

  function interactionPasses(interaction) {
    const completion = interaction.completion || {};
    const edge = edgeById.get(completion.edge_id) || {};
    const edgeBinding = edgeBindingById.get(completion.edge_id) || {};
    const conditions = []
      .concat(asArray(interaction.activation?.conditions))
      .concat(asArray(edge.conditions))
      .concat(asArray(edgeBinding.conditions));
    return conditions.every(conditionPasses);
  }

  function normalizeStateValue(value) {
    if (value === "true") return true;
    if (value === "false") return false;
    if (value === "null") return null;
    if (Array.isArray(value)) return value.map(normalizeStateValue);
    if (typeof value === "string" && value.trim() !== "" && !Number.isNaN(Number(value))) {
      return Number(value);
    }
    return value;
  }

  function conditionPasses(condition) {
    const id = condition && (condition.state_variable_id || condition.state_id || condition.id);
    if (!condition || !id) return true;
    const actual = state[id];
    const expected = normalizeStateValue(condition.value);
    switch (condition.operator) {
      case "!=":
      case "not_equals":
        return actual !== expected;
      case "in":
      case "one_of":
        return Array.isArray(expected) ? expected.includes(actual) : actual === expected;
      case "not_in":
      case "not_one_of":
        return Array.isArray(expected) ? !expected.includes(actual) : actual !== expected;
      case "contains":
      case "includes":
        if (Array.isArray(actual)) return actual.includes(expected);
        if (typeof actual === "string") return actual.includes(String(expected));
        return false;
      case "not_contains":
      case "excludes":
        if (Array.isArray(actual)) return !actual.includes(expected);
        if (typeof actual === "string") return !actual.includes(String(expected));
        return true;
      case "exists":
        return actual !== undefined && actual !== null && actual !== "";
      case "not_exists":
        return actual === undefined || actual === null || actual === "";
      case ">":
      case "greater_than":
        return Number(actual) > Number(expected);
      case ">=":
      case "greater_than_or_equal":
        return Number(actual) >= Number(expected);
      case "<":
      case "less_than":
        return Number(actual) < Number(expected);
      case "<=":
      case "less_than_or_equal":
        return Number(actual) <= Number(expected);
      case "==":
      case "equals":
      default:
        return actual === expected;
    }
  }

  function applyWrites(writes) {
    asArray(writes).forEach((write) => {
      if (!write || typeof write !== "object") return;
      const id = write.state_variable_id || write.state_id || write.id;
      if (!id) return;
      const value = normalizeStateValue(write.value);
      const operation = write.operation || write.op || "set";
      if (operation === "increment") {
        state[id] = Number(state[id] || 0) + Number(value || 1);
      } else if (operation === "decrement") {
        state[id] = Number(state[id] || 0) - Number(value || 1);
      } else if (operation === "append") {
        state[id] = Array.isArray(state[id]) ? state[id].concat([value]) : [value];
      } else if (operation === "append_unique") {
        const existing = Array.isArray(state[id]) ? state[id].slice() : (state[id] == null || state[id] === "" ? [] : [state[id]]);
        if (!existing.includes(value)) existing.push(value);
        state[id] = existing;
      } else if (operation === "set_if_unset") {
        if (state[id] === undefined || state[id] === null || state[id] === "") state[id] = value;
      } else if (operation === "set_if_unset_or_unformed") {
        if (state[id] === undefined || state[id] === null || state[id] === "" || state[id] === "unformed" || state[id] === "unstarted") state[id] = value;
      } else if (operation === "remove") {
        state[id] = Array.isArray(state[id]) ? state[id].filter((item) => item !== value) : state[id];
      } else if (operation === "clear") {
        state[id] = Array.isArray(state[id]) ? [] : null;
      } else {
        state[id] = value;
      }
    });
  }

  function updateCamera() {
    const width = Number(currentLevel.dimensions?.width || 34);
    const viewWorldWidth = viewport.width < 700 ? 12 : 18;
    viewport.scale = viewport.width / viewWorldWidth;
    viewport.cameraX = clamp(player.x - viewWorldWidth * 0.46, 0, Math.max(0, width - viewWorldWidth));
  }

  function worldToScreen(x, y) {
    const sx = (x - viewport.cameraX) * viewport.scale;
    const sy = viewport.height - 58 - y * viewport.scale;
    return { x: sx, y: sy };
  }

  function render() {
    drawBackground();
    drawLevelGeometry();
    drawExits();
    drawInteractions();
    drawPlayer();
    drawForegroundVignette();
  }

  function drawBackground() {
    const palette = paletteForRegion(currentLevel.region_id || currentLevel.level_id || "");
    const gradient = ctx.createLinearGradient(0, 0, viewport.width, viewport.height);
    gradient.addColorStop(0, palette.sky);
    gradient.addColorStop(0.54, palette.mid);
    gradient.addColorStop(1, palette.ground);
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, viewport.width, viewport.height);

    ctx.save();
    ctx.globalAlpha = 0.28;
    ctx.fillStyle = palette.accent;
    for (let i = 0; i < 8; i += 1) {
      const x = ((i * 260 - viewport.cameraX * 18) % (viewport.width + 260)) - 130;
      const y = viewport.height * (0.28 + (i % 3) * 0.08);
      ctx.beginPath();
      ctx.ellipse(x, y, 150 + (i % 4) * 24, 36 + (i % 2) * 16, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();

    ctx.save();
    ctx.globalAlpha = 0.42;
    for (let layer = 0; layer < 3; layer += 1) {
      ctx.fillStyle = layer === 0 ? palette.shadow : layer === 1 ? palette.mid : palette.ground;
      ctx.beginPath();
      ctx.moveTo(0, viewport.height);
      const offset = -((viewport.cameraX * (10 + layer * 8)) % 180);
      for (let x = offset - 80; x <= viewport.width + 140; x += 90) {
        const height = 82 + ((x + layer * 37) % 70);
        ctx.lineTo(x, viewport.height - 110 - height - layer * 26);
        ctx.lineTo(x + 90, viewport.height - 104 - layer * 18);
      }
      ctx.lineTo(viewport.width, viewport.height);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  }

  function drawLevelGeometry() {
    const palette = paletteForRegion(currentLevel.region_id || "");
    asArray(currentLevel.walkable_surfaces).forEach((surface) => {
      const from = surface.from || {};
      const to = surface.to || {};
      const a = worldToScreen(Number(from.x || 0), Number(from.y || 1));
      const b = worldToScreen(Number(to.x || 0), Number(to.y || 1));
      const x = Math.min(a.x, b.x);
      const width = Math.max(16, Math.abs(b.x - a.x));
      ctx.fillStyle = palette.floor;
      ctx.fillRect(x, a.y, width, 20);
      ctx.fillStyle = "rgba(255, 255, 255, 0.16)";
      ctx.fillRect(x, a.y, width, 3);
      ctx.fillStyle = "rgba(0, 0, 0, 0.16)";
      ctx.fillRect(x, a.y + 18, width, 48);
    });
  }

  function drawExits() {
    asArray(currentLevel.exits).forEach((exit) => {
      const position = exit.position || {};
      const point = worldToScreen(Number(position.x || 0), Number(position.y || 1.5));
      ctx.save();
      ctx.translate(point.x, point.y);
      ctx.fillStyle = "rgba(236, 213, 158, 0.22)";
      ctx.strokeStyle = "rgba(255, 239, 196, 0.54)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      roundedRect(-18, -46, 36, 52, 8);
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    });
  }

  function drawInteractions() {
    currentNodeInteractions().forEach((interaction) => {
      const available = interactionPasses(interaction);
      const position = interaction.position || {};
      const point = worldToScreen(Number(position.x || 0), Number(position.y || 1.5));
      const active = activeInteraction && activeInteraction.interaction_id === interaction.interaction_id;
      const color = interactionColor(interaction.kind, available, active);
      ctx.save();
      ctx.translate(point.x, point.y);
      ctx.globalAlpha = available ? 1 : 0.36;
      ctx.fillStyle = color.fill;
      ctx.strokeStyle = color.stroke;
      ctx.lineWidth = active ? 4 : 2;
      ctx.beginPath();
      ctx.arc(0, -20, active ? 15 : 12, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = color.stroke;
      ctx.beginPath();
      ctx.moveTo(0, -7);
      ctx.lineTo(-7, 6);
      ctx.lineTo(7, 6);
      ctx.closePath();
      ctx.fill();
      if (active) drawInteractionLabel(interaction.label || interaction.kind || "互动");
      ctx.restore();
    });
  }

  function drawInteractionLabel(label) {
    const safeLabel = String(label).slice(0, 32);
    ctx.font = "700 13px Inter, system-ui, sans-serif";
    const width = Math.min(260, ctx.measureText(safeLabel).width + 24);
    ctx.fillStyle = "rgba(20, 23, 23, 0.88)";
    ctx.strokeStyle = "rgba(255, 255, 255, 0.22)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    roundedRect(-width / 2, -62, width, 30, 8);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#fff6df";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(safeLabel, 0, -47, width - 14);
  }

  function drawPlayer() {
    const point = worldToScreen(player.x, player.y);
    ctx.save();
    ctx.translate(point.x, point.y);
    ctx.scale(player.facing, 1);
    ctx.fillStyle = "rgba(0, 0, 0, 0.26)";
    ctx.beginPath();
    ctx.ellipse(0, 14, 17, 5, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#7a3d43";
    ctx.beginPath();
    roundedRect(-10, -31, 20, 38, 7);
    ctx.fill();
    ctx.fillStyle = "#f0d3b1";
    ctx.beginPath();
    ctx.arc(0, -42, 11, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#422b25";
    ctx.beginPath();
    ctx.arc(-2, -46, 12, Math.PI * 0.94, Math.PI * 1.96);
    ctx.fill();
    ctx.strokeStyle = "#ecd6b9";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(9, -20);
    ctx.lineTo(18, -14);
    ctx.stroke();
    ctx.restore();
  }

  function drawForegroundVignette() {
    const gradient = ctx.createRadialGradient(viewport.width / 2, viewport.height * 0.42, viewport.width * 0.2, viewport.width / 2, viewport.height * 0.5, viewport.width * 0.74);
    gradient.addColorStop(0, "rgba(0, 0, 0, 0)");
    gradient.addColorStop(1, "rgba(0, 0, 0, 0.34)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, viewport.width, viewport.height);
  }

  function interactionColor(kind, available, active) {
    const colors = {
      listen: ["#6fb2d8", "#e7f7ff"],
      open: ["#d4a84d", "#fff0b8"],
      talk: ["#a775c8", "#f2d9ff"],
      tend_garden: ["#6fae72", "#e8ffda"],
      pick_up: ["#d6855b", "#ffe1ca"],
      wait_or_hide: ["#8c9aa1", "#f2f5ef"],
      inspect: ["#67a892", "#e6fff5"],
    };
    const pair = colors[kind] || colors.inspect;
    return {
      fill: available ? pair[0] : "#5b5d61",
      stroke: active ? "#ffffff" : pair[1],
    };
  }

  function roundedRect(x, y, width, height, radius) {
    const r = Math.min(radius, Math.abs(width) / 2, Math.abs(height) / 2);
    if (typeof ctx.roundRect === "function") {
      ctx.roundRect(x, y, width, height, r);
      return;
    }
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + width - r, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + r);
    ctx.lineTo(x + width, y + height - r);
    ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
    ctx.lineTo(x + r, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
  }

  function paletteForRegion(regionId) {
    const id = String(regionId || "").toLowerCase();
    if (id.includes("garden")) {
      return {
        sky: "#557d8b",
        mid: "#2f5045",
        ground: "#624f38",
        accent: "#e0c66d",
        shadow: "#172725",
        floor: "#5c6b3e",
      };
    }
    if (id.includes("colin") || id.includes("room")) {
      return {
        sky: "#3b4451",
        mid: "#553e48",
        ground: "#4a342b",
        accent: "#d0b18a",
        shadow: "#1a1b21",
        floor: "#5a4638",
      };
    }
    if (id.includes("moor") || id.includes("arrival")) {
      return {
        sky: "#6f8792",
        mid: "#556a54",
        ground: "#6a5945",
        accent: "#d5b45f",
        shadow: "#293134",
        floor: "#6e6b48",
      };
    }
    if (id.includes("india") || id.includes("bungalow")) {
      return {
        sky: "#8b725c",
        mid: "#72584b",
        ground: "#3c3f45",
        accent: "#e5b75f",
        shadow: "#26242a",
        floor: "#6b5440",
      };
    }
    return {
      sky: "#56616f",
      mid: "#3f4c4c",
      ground: "#483c35",
      accent: "#d6c58f",
      shadow: "#1a1d20",
      floor: "#5f5547",
    };
  }
}());
