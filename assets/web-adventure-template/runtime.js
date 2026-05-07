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
  const edgeBindingById = new Map(asArray(bindings.edge_bindings).map((binding) => [binding.edge_id, binding]));
  const nodeToLevel = new Map(asArray(bindings.node_bindings).map((binding) => [binding.node_id, binding.level_id]));
  const endingByNode = new Map(asArray(bindings.ending_bindings).map((ending) => [ending.terminal_node_id, ending]));
  const endingCatalogByNode = new Map(asArray(manifest.ending_catalog).map((ending) => [ending.node_id, ending]));
  const interactionsByLevel = new Map();
  const interactionOrdinalById = new Map();

  asArray(manifest.interactions).forEach((interaction) => {
    const list = interactionsByLevel.get(interaction.level_id) || [];
    interactionOrdinalById.set(interaction.interaction_id, list.length);
    list.push(interaction);
    interactionsByLevel.set(interaction.level_id, list);
  });

  let viewport = {
    width: 960,
    height: 540,
    scale: 48,
    cameraX: 0,
    cameraY: 0,
    viewWorldWidth: 18,
    viewWorldHeight: 9,
  };
  let currentNodeId = branchGraph.start_node_id || manifest.unity_runtime?.start_node_id;
  let currentLevelId = nodeToLevel.get(currentNodeId) || manifest.world_map?.start_level_id || manifest.unity_runtime?.start_level_id;
  let currentLevel = levelById.get(currentLevelId) || asArray(manifest.levels)[0] || {};
  let activeInteraction = null;
  let moveTarget = null;
  let lastTime = 0;
  let ended = false;
  const toast = { text: "", timer: 0 };
  const pressed = new Set();
  const player = {
    x: 2,
    y: 2,
    facing: 1,
    step: 0,
  };

  gameTitle.textContent = branchGraph.title || manifest.world_map?.title || "横版冒险";
  restartButton.addEventListener("click", restart);
  endingRestart.addEventListener("click", restart);
  window.addEventListener("resize", resizeCanvas);
  window.addEventListener("keydown", handleKeyDown);
  window.addEventListener("keyup", handleKeyUp);
  canvas.addEventListener("pointerdown", handlePointerDown);
  document.querySelectorAll("[data-control]").forEach(bindControlButton);

  resizeCanvas();
  enterNode(currentNodeId || asArray(branchGraph.nodes)[0]?.id);
  requestAnimationFrame(loop);

  window.__webAdventureDebug = {
    state,
    player,
    get currentNodeId() {
      return currentNodeId;
    },
    get currentLevelId() {
      return currentLevelId;
    },
    interactById(id) {
      const interaction = currentNodeInteractions().find((candidate) => candidate.interaction_id === id);
      if (!interaction) throw new Error(`Unknown interaction in current level: ${id}`);
      activeInteraction = interaction;
      triggerActiveInteraction();
    },
    setPlayer(x, y) {
      if (!blockedAt(x, y)) {
        player.x = x;
        player.y = y;
      }
    },
  };

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
    const handled = [
      "ArrowLeft",
      "ArrowRight",
      "ArrowUp",
      "ArrowDown",
      "KeyA",
      "KeyD",
      "KeyW",
      "KeyS",
      "Space",
      "KeyE",
      "Enter",
    ].includes(event.code);
    if (handled) event.preventDefault();
    if (event.code === "ArrowLeft" || event.code === "KeyA") pressed.add("left");
    else if (event.code === "ArrowRight" || event.code === "KeyD") pressed.add("right");
    else if (event.code === "ArrowUp" || event.code === "KeyW") pressed.add("up");
    else if (event.code === "ArrowDown" || event.code === "KeyS") pressed.add("down");
    else if ((event.code === "Space" || event.code === "KeyE" || event.code === "Enter") && !event.repeat) triggerActiveInteraction();
  }

  function handleKeyUp(event) {
    if (event.code === "ArrowLeft" || event.code === "KeyA") pressed.delete("left");
    if (event.code === "ArrowRight" || event.code === "KeyD") pressed.delete("right");
    if (event.code === "ArrowUp" || event.code === "KeyW") pressed.delete("up");
    if (event.code === "ArrowDown" || event.code === "KeyS") pressed.delete("down");
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
        moveTarget = null;
      }
      event.preventDefault();
    });
    button.addEventListener("pointerup", release);
    button.addEventListener("pointercancel", release);
    button.addEventListener("pointerleave", release);
  }

  function handlePointerDown(event) {
    if (ended) return;
    const world = screenToWorld(event.clientX, event.clientY);
    const clicked = currentNodeInteractions()
      .filter(interactionPasses)
      .find((interaction) => {
        const position = interactionPosition(interaction);
        return Math.hypot(position.x - world.x, position.y - world.y) <= interactionRadius(interaction);
      });
    if (clicked) {
      const position = interactionPosition(clicked);
      if (Math.hypot(position.x - player.x, position.y - player.y) <= interactionRadius(clicked)) {
        activeInteraction = clicked;
        triggerActiveInteraction();
      } else {
        moveTarget = approachPoint(clicked);
      }
      event.preventDefault();
      return;
    }
    if (!blockedAt(world.x, world.y)) moveTarget = world;
  }

  function restart() {
    Object.keys(state).forEach((key) => delete state[key]);
    Object.assign(state, clone(manifest.initial_state || {}));
    ended = false;
    moveTarget = null;
    toast.text = "";
    toast.timer = 0;
    endingPanel.hidden = true;
    enterNode(branchGraph.start_node_id || manifest.unity_runtime?.start_node_id || asArray(branchGraph.nodes)[0]?.id);
  }

  function enterNode(nodeId) {
    if (!nodeId) return;
    currentNodeId = nodeId;
    currentLevelId = nodeToLevel.get(nodeId) || currentLevelId;
    currentLevel = levelById.get(currentLevelId) || currentLevel || {};
    const spawn = asArray(currentLevel.spawn_points)[0] || {};
    const walk = primaryWalkRect();
    player.x = clamp(Number(spawn.x || walk.x + 1), walk.x + 0.35, walk.x + walk.w - 0.35);
    player.y = clamp(Number(spawn.y || walk.y + walk.h * 0.35), walk.y + 0.35, walk.y + walk.h - 0.35);
    activeInteraction = null;
    moveTarget = null;
    updateHud();
    updateCamera();
    if (isTerminalNode(nodeId) || currentLevel.is_terminal) showEnding(nodeId);
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
    if (toast.timer > 0) toast.timer = Math.max(0, toast.timer - dt);
    if (!ended) {
      const intent = movementIntent();
      const speed = 5.4;
      const dx = intent.x * speed * dt;
      const dy = intent.y * speed * dt;
      if (dx || dy) {
        if (dx !== 0) player.facing = dx < 0 ? -1 : 1;
        player.step += dt * 9;
        tryMove(dx, dy);
      } else {
        player.step = 0;
      }
      activeInteraction = nearestAvailableInteraction();
    }
    updatePrompt();
    updateCamera();
  }

  function movementIntent() {
    let x = (pressed.has("right") ? 1 : 0) - (pressed.has("left") ? 1 : 0);
    let y = (pressed.has("up") ? 1 : 0) - (pressed.has("down") ? 1 : 0);
    if (!x && !y && moveTarget) {
      const dx = moveTarget.x - player.x;
      const dy = moveTarget.y - player.y;
      const distance = Math.hypot(dx, dy);
      if (distance < 0.16) {
        moveTarget = null;
        return { x: 0, y: 0 };
      }
      x = dx / distance;
      y = dy / distance;
    } else if (x || y) {
      moveTarget = null;
    }
    const length = Math.hypot(x, y);
    if (length > 1) {
      x /= length;
      y /= length;
    }
    return { x, y };
  }

  function tryMove(dx, dy) {
    if (dx && !blockedAt(player.x + dx, player.y)) player.x += dx;
    if (dy && !blockedAt(player.x, player.y + dy)) player.y += dy;
  }

  function primaryWalkRect() {
    return walkRects()[0] || { x: 1, y: 1, w: 10, h: 4 };
  }

  function walkRects() {
    const explicit = asArray(currentLevel.walk_bounds)
      .map(normalizeRect)
      .filter(Boolean);
    if (explicit.length) return explicit;
    const dimensions = currentLevel.dimensions || {};
    const width = Number(dimensions.width || 34);
    const height = Number(dimensions.height || 8);
    const surfaces = asArray(currentLevel.walkable_surfaces);
    if (surfaces.length) {
      let minX = Infinity;
      let maxX = -Infinity;
      let baseY = Infinity;
      surfaces.forEach((surface) => {
        const from = surface.from || {};
        const to = surface.to || {};
        const x1 = Number(from.x || 0);
        const x2 = Number(to.x || 0);
        minX = Math.min(minX, x1, x2);
        maxX = Math.max(maxX, x1, x2);
        baseY = Math.min(baseY, Number(from.y || to.y || 1));
      });
      if (Number.isFinite(minX) && Number.isFinite(maxX)) {
        const y = Number.isFinite(baseY) ? baseY : 1;
        return [{ x: minX, y, w: Math.max(1, maxX - minX), h: Math.max(2.4, Math.min(5.4, height - y - 0.6)) }];
      }
    }
    return [{ x: 1, y: 1, w: Math.max(3, width - 2), h: Math.max(2.4, height - 2) }];
  }

  function blockerRects() {
    return []
      .concat(asArray(currentLevel.blockers))
      .concat(asArray(currentLevel.collision_blocks))
      .concat(asArray(currentLevel.collision).filter((entry) => entry.blocking === true || entry.role === "blocker"))
      .map(normalizeRect)
      .filter(Boolean);
  }

  function normalizeRect(rect) {
    if (!rect || typeof rect !== "object") return null;
    const x = Number(rect.x);
    const y = Number(rect.y);
    const w = Number(rect.w ?? rect.width);
    const h = Number(rect.h ?? rect.height);
    if (![x, y, w, h].every(Number.isFinite) || w <= 0 || h <= 0) return null;
    return { x, y, w, h, id: rect.id || rect.surface_id || rect.blocker_id };
  }

  function playerFootRect(x = player.x, y = player.y) {
    return { x: x - 0.24, y: y - 0.14, w: 0.48, h: 0.28 };
  }

  function rectsOverlap(a, b) {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  }

  function rectContainsFoot(rect, foot) {
    return foot.x >= rect.x && foot.y >= rect.y && foot.x + foot.w <= rect.x + rect.w && foot.y + foot.h <= rect.y + rect.h;
  }

  function blockedAt(x, y) {
    const foot = playerFootRect(x, y);
    if (!walkRects().some((rect) => rectContainsFoot(rect, foot))) return true;
    return blockerRects().some((rect) => rectsOverlap(foot, rect));
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
      const position = interactionPosition(interaction);
      const distance = Math.hypot(position.x - player.x, position.y - player.y);
      const priority = Number(interaction.priority || interaction.display?.priority || 0);
      const bestPriority = Number(nearest?.priority || nearest?.display?.priority || 0);
      if (distance <= interactionRadius(interaction) && (distance < bestDistance || priority > bestPriority)) {
        nearest = interaction;
        bestDistance = distance;
      }
    });
    return nearest;
  }

  function interactionRadius(interaction) {
    return Number(interaction.activation?.radius || interaction.display?.radius || 1.35);
  }

  function interactionPosition(interaction) {
    const displayPosition = interaction.display?.position || interaction.display_position;
    const raw = displayPosition || interaction.position || {};
    let x = Number(raw.x);
    let y = Number(raw.y);
    const walk = primaryWalkRect();
    if (!Number.isFinite(x)) x = walk.x + walk.w * 0.5;
    if (!Number.isFinite(y)) y = walk.y + walk.h * 0.5;
    if (!displayPosition && y <= walk.y + 0.75 && walk.h > 2.2) {
      const ordinal = interactionOrdinalById.get(interaction.interaction_id) || 0;
      const rowFractions = [0.32, 0.58, 0.78, 0.44];
      y = walk.y + walk.h * rowFractions[ordinal % rowFractions.length];
      if (ordinal > 0 && Math.abs(x - (Number(interaction.position?.x) || x)) < 0.01) {
        x = clamp(x + ((ordinal % 2 === 0 ? -1 : 1) * Math.min(3.2, walk.w * 0.16)), walk.x + 0.8, walk.x + walk.w - 0.8);
      }
    }
    return {
      x: clamp(x, walk.x + 0.45, walk.x + walk.w - 0.45),
      y: clamp(y, walk.y + 0.45, walk.y + walk.h - 0.45),
    };
  }

  function approachPoint(interaction) {
    const position = interactionPosition(interaction);
    const radius = interactionRadius(interaction);
    const candidates = [
      { x: position.x, y: position.y - radius * 0.72 },
      { x: position.x - radius * 0.72, y: position.y },
      { x: position.x + radius * 0.72, y: position.y },
      { x: position.x, y: position.y + radius * 0.72 },
    ];
    return candidates
      .filter((candidate) => !blockedAt(candidate.x, candidate.y))
      .sort((a, b) => Math.hypot(a.x - player.x, a.y - player.y) - Math.hypot(b.x - player.x, b.y - player.y))[0] || position;
  }

  function updatePrompt() {
    if (ended) {
      actionPrompt.hidden = true;
      return;
    }
    if (activeInteraction) {
      actionPrompt.textContent = verbForInteraction(activeInteraction);
      actionPrompt.hidden = false;
    } else if (toast.timer > 0 && toast.text) {
      actionPrompt.textContent = toast.text;
      actionPrompt.hidden = false;
    } else {
      actionPrompt.hidden = true;
    }
  }

  function verbForInteraction(interaction) {
    const role = interactionRole(interaction);
    const label = interaction.label || interaction.feedback?.caption || interaction.kind || "互动";
    if (role === "npc") return `交谈：${label}`;
    if (role === "item") return `拾取：${label}`;
    if (role === "door") return `打开：${label}`;
    if (role === "garden") return `照料：${label}`;
    if (role === "sound") return `聆听：${label}`;
    return `查看：${label}`;
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
    toast.text = interaction.feedback?.caption || interaction.label || "互动完成";
    toast.timer = 1.2;
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
    if (typeof value === "string" && value.trim() !== "" && !Number.isNaN(Number(value))) return Number(value);
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
    const dimensions = currentLevel.dimensions || {};
    const width = Number(dimensions.width || 34);
    const height = Number(dimensions.height || 8);
    viewport.viewWorldWidth = viewport.width < 700 ? 11.5 : 17.5;
    viewport.scale = viewport.width / viewport.viewWorldWidth;
    viewport.viewWorldHeight = viewport.height / viewport.scale;
    viewport.cameraX = clamp(player.x - viewport.viewWorldWidth * 0.5, 0, Math.max(0, width - viewport.viewWorldWidth));
    viewport.cameraY = clamp(player.y - viewport.viewWorldHeight * 0.43, 0, Math.max(0, height - viewport.viewWorldHeight));
  }

  function worldToScreen(x, y) {
    const sx = (x - viewport.cameraX) * viewport.scale;
    const sy = viewport.height - (y - viewport.cameraY) * viewport.scale - 38;
    return { x: sx, y: sy };
  }

  function screenToWorld(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    const sx = ((clientX - rect.left) / rect.width) * viewport.width;
    const sy = ((clientY - rect.top) / rect.height) * viewport.height;
    return {
      x: viewport.cameraX + sx / viewport.scale,
      y: viewport.cameraY + (viewport.height - sy - 38) / viewport.scale,
    };
  }

  function render() {
    drawBackground();
    drawLevelGeometry();
    drawExits();
    const renderables = currentNodeInteractions()
      .filter(interactionPasses)
      .map((interaction) => ({
        type: "interaction",
        sortY: interactionPosition(interaction).y,
        interaction,
      }));
    renderables.push({ type: "player", sortY: player.y });
    renderables.sort((a, b) => b.sortY - a.sortY);
    renderables.forEach((item) => {
      if (item.type === "player") drawPlayer();
      else drawInteractionObject(item.interaction);
    });
    drawInteractionMarkers();
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
    ctx.globalAlpha = 0.24;
    ctx.fillStyle = palette.accent;
    for (let i = 0; i < 8; i += 1) {
      const x = ((i * 260 - viewport.cameraX * 18) % (viewport.width + 260)) - 130;
      const y = viewport.height * (0.24 + (i % 3) * 0.08) + viewport.cameraY * 7;
      ctx.beginPath();
      ctx.ellipse(x, y, 150 + (i % 4) * 24, 36 + (i % 2) * 16, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();

    ctx.save();
    ctx.globalAlpha = 0.34;
    for (let layer = 0; layer < 3; layer += 1) {
      ctx.fillStyle = layer === 0 ? palette.shadow : layer === 1 ? palette.mid : palette.ground;
      ctx.beginPath();
      ctx.moveTo(0, viewport.height);
      const offset = -((viewport.cameraX * (10 + layer * 8)) % 180);
      for (let x = offset - 80; x <= viewport.width + 140; x += 90) {
        const height = 82 + ((x + layer * 37) % 70);
        ctx.lineTo(x, viewport.height - 110 - height - layer * 26 + viewport.cameraY * 5);
        ctx.lineTo(x + 90, viewport.height - 104 - layer * 18 + viewport.cameraY * 5);
      }
      ctx.lineTo(viewport.width, viewport.height);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  }

  function drawLevelGeometry() {
    const palette = paletteForRegion(currentLevel.region_id || "");
    walkRects().forEach((rect) => {
      const bottomLeft = worldToScreen(rect.x, rect.y);
      const topRight = worldToScreen(rect.x + rect.w, rect.y + rect.h);
      const x = Math.min(bottomLeft.x, topRight.x);
      const y = Math.min(bottomLeft.y, topRight.y);
      const w = Math.abs(topRight.x - bottomLeft.x);
      const h = Math.abs(bottomLeft.y - topRight.y);
      const floorGradient = ctx.createLinearGradient(0, y, 0, y + h);
      floorGradient.addColorStop(0, palette.floor);
      floorGradient.addColorStop(1, palette.ground);
      ctx.fillStyle = floorGradient;
      ctx.fillRect(x, y, w, h);
      ctx.save();
      ctx.globalAlpha = 0.12;
      ctx.strokeStyle = "#fff8df";
      ctx.lineWidth = 1;
      for (let line = y + 18; line < y + h; line += 28) {
        ctx.beginPath();
        ctx.moveTo(x, line);
        ctx.lineTo(x + w, line);
        ctx.stroke();
      }
      ctx.restore();
    });

    blockerRects().forEach((rect) => {
      const bottomLeft = worldToScreen(rect.x, rect.y);
      const topRight = worldToScreen(rect.x + rect.w, rect.y + rect.h);
      ctx.fillStyle = "rgba(45, 37, 31, 0.42)";
      ctx.fillRect(Math.min(bottomLeft.x, topRight.x), Math.min(bottomLeft.y, topRight.y), Math.abs(topRight.x - bottomLeft.x), Math.abs(bottomLeft.y - topRight.y));
    });
  }

  function drawExits() {
    asArray(currentLevel.exits).forEach((exit) => {
      const position = exit.position || {};
      const point = worldToScreen(Number(position.x || primaryWalkRect().x + primaryWalkRect().w - 0.8), Number(position.y || primaryWalkRect().y + primaryWalkRect().h * 0.5));
      ctx.save();
      ctx.translate(point.x, point.y);
      ctx.fillStyle = "rgba(236, 213, 158, 0.22)";
      ctx.strokeStyle = "rgba(255, 239, 196, 0.54)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      roundedRect(-18, -54, 36, 58, 8);
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    });
  }

  function drawInteractionObject(interaction) {
    const position = interactionPosition(interaction);
    const point = worldToScreen(position.x, position.y);
    const role = interactionRole(interaction);
    const active = activeInteraction && activeInteraction.interaction_id === interaction.interaction_id;
    ctx.save();
    ctx.translate(point.x, point.y);
    drawObjectShadow(active ? 19 : 15);
    if (role === "npc") drawNpc(interaction, active);
    else if (role === "door") drawDoor(interaction, active);
    else if (role === "garden") drawGardenProp(interaction, active);
    else if (role === "sound") drawSoundProp(interaction, active);
    else drawItemProp(interaction, active);
    ctx.restore();
  }

  function drawObjectShadow(radius) {
    ctx.save();
    ctx.globalAlpha = 0.24;
    ctx.fillStyle = "#111";
    ctx.beginPath();
    ctx.ellipse(0, 8, radius, 6, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function drawNpc(interaction, active) {
    const colors = interactionColor(interaction.kind, true, active);
    ctx.fillStyle = colors.fill;
    ctx.beginPath();
    roundedRect(-11, -36, 22, 34, 7);
    ctx.fill();
    ctx.fillStyle = "#ead1b2";
    ctx.beginPath();
    ctx.arc(0, -45, 10, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = colors.stroke;
    ctx.fillRect(-13, -20, 26, 4);
  }

  function drawDoor(interaction, active) {
    const colors = interactionColor(interaction.kind, true, active);
    ctx.fillStyle = colors.fill;
    ctx.strokeStyle = colors.stroke;
    ctx.lineWidth = active ? 3 : 2;
    ctx.beginPath();
    roundedRect(-17, -48, 34, 54, 5);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#fff3bf";
    ctx.beginPath();
    ctx.arc(8, -20, 3, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawGardenProp(interaction, active) {
    const colors = interactionColor(interaction.kind, true, active);
    ctx.fillStyle = colors.fill;
    for (let i = 0; i < 5; i += 1) {
      ctx.beginPath();
      ctx.ellipse(-16 + i * 8, -14 - (i % 2) * 7, 10, 16, 0.3 * (i - 2), 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = active ? "#f8e69a" : colors.stroke;
    ctx.fillRect(-20, -4, 40, 8);
  }

  function drawSoundProp(interaction, active) {
    const colors = interactionColor(interaction.kind, true, active);
    ctx.strokeStyle = colors.stroke;
    ctx.lineWidth = active ? 4 : 3;
    for (let i = 0; i < 3; i += 1) {
      ctx.beginPath();
      ctx.arc(0, -18, 10 + i * 9, -0.8, 0.8);
      ctx.stroke();
    }
    ctx.fillStyle = colors.fill;
    ctx.beginPath();
    ctx.arc(-8, -18, 8, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawItemProp(interaction, active) {
    const colors = interactionColor(interaction.kind, true, active);
    ctx.fillStyle = colors.fill;
    ctx.strokeStyle = colors.stroke;
    ctx.lineWidth = active ? 3 : 2;
    ctx.beginPath();
    roundedRect(-15, -28, 30, 26, 5);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = active ? "#ffffff" : colors.stroke;
    ctx.beginPath();
    ctx.moveTo(0, -36);
    ctx.lineTo(8, -26);
    ctx.lineTo(0, -18);
    ctx.lineTo(-8, -26);
    ctx.closePath();
    ctx.fill();
  }

  function drawInteractionMarkers() {
    currentNodeInteractions().forEach((interaction) => {
      if (!interactionPasses(interaction)) return;
      const position = interactionPosition(interaction);
      const point = worldToScreen(position.x, position.y);
      const active = activeInteraction && activeInteraction.interaction_id === interaction.interaction_id;
      const pulse = Math.sin(performance.now() * 0.004 + position.x) * 0.5 + 0.5;
      ctx.save();
      ctx.translate(point.x, point.y);
      ctx.globalAlpha = active ? 1 : 0.36 + pulse * 0.24;
      ctx.fillStyle = active ? "#fff7cc" : "#f0c45c";
      ctx.beginPath();
      ctx.moveTo(0, -72);
      ctx.lineTo(7, -62);
      ctx.lineTo(0, -52);
      ctx.lineTo(-7, -62);
      ctx.closePath();
      ctx.fill();
      if (active) drawInteractionLabel(verbForInteraction(interaction));
      ctx.restore();
    });
  }

  function drawInteractionLabel(label) {
    const safeLabel = String(label).slice(0, 34);
    ctx.font = "700 13px Inter, system-ui, sans-serif";
    const width = Math.min(300, ctx.measureText(safeLabel).width + 24);
    ctx.fillStyle = "rgba(20, 23, 23, 0.88)";
    ctx.strokeStyle = "rgba(255, 255, 255, 0.22)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    roundedRect(-width / 2, -108, width, 30, 8);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#fff6df";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(safeLabel, 0, -93, width - 14);
  }

  function drawPlayer() {
    const point = worldToScreen(player.x, player.y);
    const bob = Math.sin(player.step) * 2;
    ctx.save();
    ctx.translate(point.x, point.y + bob);
    ctx.scale(player.facing, 1);
    drawObjectShadow(17);
    ctx.fillStyle = "#7a3d43";
    ctx.beginPath();
    roundedRect(-10, -34, 20, 40, 7);
    ctx.fill();
    ctx.fillStyle = "#f0d3b1";
    ctx.beginPath();
    ctx.arc(0, -46, 11, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#422b25";
    ctx.beginPath();
    ctx.arc(-2, -50, 12, Math.PI * 0.94, Math.PI * 1.96);
    ctx.fill();
    ctx.strokeStyle = "#ecd6b9";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(9, -22);
    ctx.lineTo(18, -16);
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

  function interactionRole(interaction) {
    const explicit = interaction.target_kind || interaction.display?.target_kind || interaction.display?.role;
    if (explicit) return explicit;
    const kind = String(interaction.kind || "").toLowerCase();
    if (kind === "talk") return "npc";
    if (kind === "pick_up") return "item";
    if (kind === "open") return "door";
    if (kind === "tend_garden") return "garden";
    if (kind === "listen") return "sound";
    return "item";
  }

  function interactionColor(kind, available, active) {
    const colors = {
      listen: ["#6fb2d8", "#e7f7ff"],
      open: ["#95673c", "#fff0b8"],
      talk: ["#8f67b2", "#f2d9ff"],
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
