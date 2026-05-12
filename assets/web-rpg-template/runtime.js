(function () {
  "use strict";

  const PLAYER_SPEED = 260;
  const INTERACT_RADIUS = 96;
  const data = window.RPG_GAME_DATA || {};

  const byId = (items) => {
    const result = {};
    (Array.isArray(items) ? items : []).forEach((item) => {
      if (item && typeof item.id === "string") {
        result[item.id] = item;
      }
    });
    return result;
  };

  const maps = byId(data.maps);
  const walkableMaskCache = new Map();
  const actors = byId(data.actors);
  const enemies = byId(data.enemies);
  const encounters = byId(data.encounter_tables);
  const quests = byId(data.quests);
  const dialogues = byId(data.npc_dialogue);
  const items = byId(data.items);
  const skills = byId(data.skills);
  const restPoints = byId(data.rest_points);
  const shops = byId(data.shops);
  const entryPoints = Array.isArray(data.entry_points) ? data.entry_points.filter((entry) => entry && typeof entry.id === "string") : [];
  const battleUiShowcase = data.campaign && typeof data.campaign.battle_ui_showcase === "object" ? data.campaign.battle_ui_showcase : null;
  const pendingAudio = [];
  let currentBgmId = null;
  let currentBgm = null;
  let currentVoice = null;
  let lastVoiceKey = null;
  const BGM_VOLUME = 0.28;
  const BGM_DUCKED_VOLUME = 0.12;
  const VOICE_VOLUME = 1.0;

  const fallbackMap = {
    id: "map.start",
    title: "Start",
    coordinate_system: "pixels",
    width: 1280,
    height: 720,
    layers: {
      ground: [],
      collision: []
    },
    events: [
      { id: "npc.guide", type: "npc", x: 420, y: 330, name: "Guide", lines: ["This RPG export is running."] },
      { id: "rest.camp", type: "rest", x: 760, y: 460, name: "Camp" }
    ]
  };
  if (!Object.keys(maps).length) {
    maps[fallbackMap.id] = fallbackMap;
  }

  const maxHp = (entity) => Number((entity.stats && (entity.stats.max_hp || entity.stats.hp)) || entity.max_hp || entity.hp || 1);
  const stat = (entity, key, fallback) => Number((entity.stats && entity.stats[key]) || entity[key] || fallback);
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const slug = (value) => String(value || "").split(".").pop().split("_")[0].replace(/[^A-Za-z0-9-]/g, "_");

  const fallbackActor = {
    id: "actor.hero",
    name: "Hero",
    stats: { hp: 30, attack: 8, defense: 2, speed: 3 }
  };
  const firstMapId = data.start_map_id && maps[data.start_map_id] ? data.start_map_id : Object.keys(maps)[0];
  const defaultEntry = entryPoints[0] || {
    id: "entry.default",
    title: "Start",
    description: "",
    start_map_id: firstMapId,
    start_position: data.start_position || { x: 180, y: 520 },
    party: data.party || []
  };
  const entrySelectRequired = false;
  const startPosition = data.start_position || defaultEntry.start_position || { x: 180, y: 520 };

  function actorForParty(party) {
    const partyIds = (Array.isArray(party) ? party : []).filter((id) => actors[id]);
    return actors[partyIds[0]] || Object.values(actors)[0] || fallbackActor;
  }

  function heroFromActor(actor) {
    return {
      id: actor.id,
      name: actor.name || actor.display_name || actor.id,
      hp: maxHp(actor),
      maxHp: maxHp(actor),
      attack: stat(actor, "attack", 8),
      defense: stat(actor, "defense", 1),
      speed: stat(actor, "speed", 3),
      spriteAssetId: actor.sprite_asset_id || actor.spriteAssetId || actor.asset_id || `sprite.${slug(actor.id)}`,
      walkSheetAssetId: actor.walk_sheet_asset_id || actor.walkSheetAssetId || actor.walk_asset_id || null,
      walkFrameAssetIds: actor.walk_frame_asset_ids || actor.walkFrameAssetIds || null,
      skills: Array.isArray(actor.skills) ? actor.skills : []
    };
  }

  const firstActor = actorForParty(data.party || defaultEntry.party);

  const state = {
    entryId: null,
    entryTitle: "",
    mapId: firstMapId,
    renderedMapId: null,
    x: Number(startPosition.x || 1),
    y: Number(startPosition.y || 1),
    prevX: null,
    prevY: null,
    prevMapId: null,
    facing: "down",
    moving: false,
    cameraX: 0,
    cameraY: 0,
    keys: new Set(),
    frameRequest: 0,
    lastFrame: 0,
    walkElapsed: 0,
    walkFrame: 0,
    worldEl: null,
    avatarEl: null,
    nearbyId: null,
    showBoundaries: false,
    effects: [],
    hero: heroFromActor(firstActor),
    flags: {},
    inventory: { "item.steam_bun": 2 },
    quests: {},
    log: [],
    dialogue: null,
    battle: null,
    battleUi: null,
    completed: false,
    endingDismissed: false
  };

  const elements = {
    title: document.getElementById("title"),
    location: document.getElementById("location"),
    map: document.getElementById("map"),
    party: document.getElementById("party"),
    questLog: document.getElementById("questLog"),
    messageLog: document.getElementById("messageLog"),
    dialogue: document.getElementById("dialogue"),
    dialoguePortrait: document.getElementById("dialoguePortrait"),
    dialogueSpeaker: document.getElementById("dialogueSpeaker"),
    dialogueText: document.getElementById("dialogueText"),
    dialogueNext: document.getElementById("dialogueNext"),
    battle: document.getElementById("battle"),
    battleBox: document.getElementById("battleBox"),
    battleVisual: document.getElementById("battleVisual"),
    battleTitle: document.getElementById("battleTitle"),
    battleText: document.getElementById("battleText"),
    battleActions: document.getElementById("battleActions"),
    heroStats: document.getElementById("heroStats"),
    enemyStats: document.getElementById("enemyStats"),
    ending: document.getElementById("ending"),
    endingTitle: document.getElementById("endingTitle"),
    endingText: document.getElementById("endingText"),
    endingClose: document.getElementById("endingClose"),
    battleUiBtn: document.getElementById("battleUiBtn"),
    battleUiShowcase: document.getElementById("battleUiShowcase"),
    battleUiTitle: document.getElementById("battleUiTitle"),
    battleUiText: document.getElementById("battleUiText"),
    battleUiFlow: document.getElementById("battleUiFlow"),
    battleUiFeatures: document.getElementById("battleUiFeatures"),
    battleUiPreview: document.getElementById("battleUiPreview"),
    battleUiRoute: document.getElementById("battleUiRoute"),
    battleUiMap: document.getElementById("battleUiMap"),
    battleUiCombatants: document.getElementById("battleUiCombatants"),
    battleUiStats: document.getElementById("battleUiStats"),
    battleUiLog: document.getElementById("battleUiLog"),
    battleUiActions: document.getElementById("battleUiActions"),
    battleUiLink: document.getElementById("battleUiLink"),
    battleUiReset: document.getElementById("battleUiReset"),
    battleUiClose: document.getElementById("battleUiClose"),
    boundaryBtn: document.getElementById("boundaryBtn"),
    saveBtn: document.getElementById("saveBtn"),
    loadBtn: document.getElementById("loadBtn"),
    entrySelect: document.getElementById("entrySelect"),
    entryTitle: document.getElementById("entryTitle"),
    entryText: document.getElementById("entryText"),
    entryOptions: document.getElementById("entryOptions")
  };

  const touchControlKeys = new Set();

  function focusGameSurface() {
    if (!elements.map) return;
    try {
      elements.map.focus({ preventScroll: true });
    } catch (_error) {
      elements.map.focus();
    }
  }

  function setControlKey(key, active) {
    if (!key) return;
    if (active) {
      state.keys.add(key);
      touchControlKeys.add(key);
    } else {
      state.keys.delete(key);
      touchControlKeys.delete(key);
    }
  }

  function clearControlKeys() {
    touchControlKeys.forEach((key) => state.keys.delete(key));
    touchControlKeys.clear();
  }

  function appendTouchControls() {
    if (!elements.map) return;
    if (elements.map.querySelector(".touch-controls")) return;

    const controls = document.createElement("div");
    controls.className = "touch-controls";
    controls.setAttribute("aria-label", "Movement controls");
    [
      ["arrowup", "up", "^", "Move up"],
      ["arrowleft", "left", "<", "Move left"],
      ["arrowright", "right", ">", "Move right"],
      ["arrowdown", "down", "v", "Move down"]
    ].forEach(([key, direction, label, aria]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `touch-control touch-control-${direction}`;
      button.dataset.controlKey = key;
      button.setAttribute("aria-label", aria);
      button.textContent = label;
      controls.appendChild(button);
    });
    controls.querySelectorAll("button").forEach((button) => {
      const key = button.dataset.controlKey;
      const activate = (event) => {
        event.preventDefault();
        event.stopPropagation();
        focusGameSurface();
        setControlKey(key, true);
      };
      const release = (event) => {
        event.preventDefault();
        event.stopPropagation();
        setControlKey(key, false);
      };
      button.addEventListener("pointerdown", activate);
      button.addEventListener("pointerup", release);
      button.addEventListener("pointerleave", release);
      button.addEventListener("pointercancel", release);
      button.addEventListener("contextmenu", (event) => event.preventDefault());
    });
    elements.map.appendChild(controls);
  }

  function setupInputSurface() {
    if (!elements.map) return;
    elements.map.tabIndex = 0;
    elements.map.setAttribute("role", "application");
    elements.map.addEventListener("pointerdown", focusGameSurface);
    appendTouchControls();
    window.setTimeout(focusGameSurface, 0);
  }

  function currentMap() {
    return maps[state.mapId] || maps[Object.keys(maps)[0]] || fallbackMap;
  }

  function assetPath(assetId) {
    return assetId && data.assets && data.assets[assetId] ? data.assets[assetId] : "";
  }

  function generatedAssetKey(fileRef) {
    const name = String(fileRef || "").split("/").pop() || "";
    return name.replace(/\.[^.]+$/, "");
  }

  function generatedFilePath(fileRef) {
    if (typeof fileRef !== "string" || !fileRef) return "";
    if (/^(?:https?:|data:|blob:)/i.test(fileRef)) return fileRef;
    const normalized = fileRef
      .replace(/^workspace\/generated-assets\//, "")
      .replace(/^assets\//, "");
    const mapped = data.assets && (data.assets[fileRef] || data.assets[normalized] || data.assets[generatedAssetKey(normalized)]);
    if (mapped) return mapped;
    return `assets/${normalized}`;
  }

  function attemptPlay(audio) {
    const playback = audio.play();
    if (playback && typeof playback.catch === "function") {
      playback.catch(() => {
        if (!audio.__rpgStopped && !pendingAudio.includes(audio)) pendingAudio.push(audio);
      });
    }
  }

  function resumePendingAudio() {
    const waiting = pendingAudio.splice(0, pendingAudio.length);
    waiting.forEach((audio) => {
      if (!audio.__rpgStopped) attemptPlay(audio);
    });
  }

  function playAudioAsset(assetId, options) {
    const path = assetPath(assetId);
    if (!path) return null;
    const audio = new Audio(path);
    audio.loop = Boolean(options && options.loop);
    audio.volume = Number((options && options.volume) ?? 1);
    audio.__rpgStopped = false;
    attemptPlay(audio);
    return audio;
  }

  function stopAudio(audio) {
    if (!audio) return;
    audio.__rpgStopped = true;
    audio.pause();
    try {
      audio.currentTime = 0;
    } catch (_error) {
      // Some browsers disallow resetting a not-yet-loaded audio element.
    }
  }

  function setBgmDucked(ducked) {
    if (currentBgm) currentBgm.volume = ducked ? BGM_DUCKED_VOLUME : BGM_VOLUME;
  }

  function playBgm(assetId) {
    if (!assetId || !assetPath(assetId)) return;
    if (currentBgmId === assetId && currentBgm) return;
    stopAudio(currentBgm);
    currentBgmId = assetId;
    currentBgm = playAudioAsset(assetId, { loop: true, volume: currentVoice ? BGM_DUCKED_VOLUME : BGM_VOLUME });
  }

  function playSfx(assetId, volume = 0.78) {
    if (!assetId || !assetPath(assetId)) return;
    playAudioAsset(assetId, { loop: false, volume });
  }

  function playMapBgm(gameMap) {
    const assetId = gameMap.bgm_asset_id || (data.campaign && data.campaign.bgm_asset_id) || firstAssetWithPrefix("bgm.");
    if (assetId) playBgm(assetId);
  }

  function stopVoice() {
    stopAudio(currentVoice);
    currentVoice = null;
    setBgmDucked(false);
  }

  function playVoiceForLine(line) {
    const assetId = line && line.voice_asset_id;
    if (!assetId) {
      stopVoice();
      lastVoiceKey = null;
      return;
    }
    const key = `${state.dialogue ? state.dialogue.event.id : "dialogue"}:${state.dialogue ? state.dialogue.index : 0}:${assetId}`;
    if (key === lastVoiceKey) return;
    stopVoice();
    lastVoiceKey = key;
    currentVoice = playAudioAsset(assetId, { loop: false, volume: VOICE_VOLUME });
    if (currentVoice) {
      currentVoice.addEventListener("playing", () => setBgmDucked(true), { once: true });
      currentVoice.addEventListener("ended", () => setBgmDucked(false), { once: true });
    }
  }

  function motionAssetPath(assetId) {
    return assetPath(assetId ? `motion.${assetId}.idle` : "");
  }

  function mapVideoPath(gameMap) {
    const mapAssetId = gameMap.asset_id || gameMap.map_asset_id || gameMap.id;
    return assetPath(mapAssetId ? `bgv.${mapAssetId}.loop` : "");
  }

  function firstAssetWithPrefix(prefix) {
    const refs = Array.isArray(data.asset_refs) ? data.asset_refs : [];
    return refs.find((assetId) => typeof assetId === "string" && assetId.startsWith(prefix));
  }

  function addLog(message) {
    state.log.unshift(message);
    state.log = state.log.slice(0, 7);
  }

  function queueFloat(text, tone = "good") {
    state.effects.push({ text, tone });
  }

  function flashMap(tone = "good") {
    elements.map.classList.remove("map-flash-good", "map-flash-hit", "map-flash-travel");
    void elements.map.offsetWidth;
    elements.map.classList.add(`map-flash-${tone}`);
    window.setTimeout(() => elements.map.classList.remove(`map-flash-${tone}`), 380);
  }

  function worldWidth(gameMap) {
    return Number(gameMap.width || 0);
  }

  function worldHeight(gameMap) {
    return Number(gameMap.height || 0);
  }

  function coordToPx(value) {
    return Number(value || 0);
  }

  function pointInPolygon(points, x, y) {
    let inside = false;
    for (let i = 0, j = points.length - 1; i < points.length; j = i, i += 1) {
      const xi = Number(points[i][0]);
      const yi = Number(points[i][1]);
      const xj = Number(points[j][0]);
      const yj = Number(points[j][1]);
      const hit = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / ((yj - yi) || 1e-9) + xi;
      if (hit) inside = !inside;
    }
    return inside;
  }

  function shapeContains(shape, x, y) {
    if (!shape || typeof shape !== "object") return false;
    if (shape.type === "polygon" && Array.isArray(shape.points)) {
      return pointInPolygon(shape.points, x, y);
    }
    if (shape.type === "rect") {
      return x >= Number(shape.x) && x <= Number(shape.x) + Number(shape.w) && y >= Number(shape.y) && y <= Number(shape.y) + Number(shape.h);
    }
    return false;
  }

  function isShapeBlocked(gameMap, x, y) {
    const shapes = Array.isArray(gameMap.collision_shapes) ? gameMap.collision_shapes : [];
    return shapes.some((shape) => shapeContains(shape, x, y));
  }

  function maskRefForMap(gameMap) {
    if (!gameMap || typeof gameMap !== "object") return "";
    if (typeof gameMap.walkable_mask_ref === "string") return gameMap.walkable_mask_ref;
    const source = gameMap.boundary_source && typeof gameMap.boundary_source === "object" ? gameMap.boundary_source : null;
    return source && typeof source.mask_ref === "string" ? source.mask_ref : "";
  }

  function ensureWalkableMask(gameMap) {
    const maskRef = maskRefForMap(gameMap);
    if (!maskRef) return null;
    const key = `${gameMap.id || "map"}:${maskRef}`;
    const cached = walkableMaskCache.get(key);
    if (cached) return cached;

    const entry = { status: "loading", canvas: null, context: null, width: 0, height: 0 };
    walkableMaskCache.set(key, entry);
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth || image.width;
      canvas.height = image.naturalHeight || image.height;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context || !canvas.width || !canvas.height) {
        entry.status = "error";
        return;
      }
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      entry.canvas = canvas;
      entry.context = context;
      entry.width = canvas.width;
      entry.height = canvas.height;
      entry.status = "ready";
      render();
    };
    image.onerror = () => {
      entry.status = "error";
    };
    image.src = generatedFilePath(maskRef);
    return entry;
  }

  function isMaskWalkable(gameMap, x, y) {
    const mask = ensureWalkableMask(gameMap);
    if (!mask || mask.status !== "ready" || !mask.context) return null;
    const mapWidth = worldWidth(gameMap) || mask.width;
    const mapHeight = worldHeight(gameMap) || mask.height;
    const px = clamp(Math.round((x / mapWidth) * (mask.width - 1)), 0, mask.width - 1);
    const py = clamp(Math.round((y / mapHeight) * (mask.height - 1)), 0, mask.height - 1);
    const pixel = mask.context.getImageData(px, py, 1, 1).data;
    return pixel[3] > 0 && (pixel[0] + pixel[1] + pixel[2]) / 3 >= 128;
  }

  function playerFootX(x) {
    return x;
  }

  function playerFootY(y) {
    return y;
  }

  function isBlocked(gameMap, x, y) {
    const footX = x;
    const footY = y;
    if (footX < 0 || footY < 0 || footX >= gameMap.width || footY >= gameMap.height) {
      return true;
    }
    const maskWalkable = isMaskWalkable(gameMap, footX, footY);
    if (maskWalkable !== null) return !maskWalkable;
    return isShapeBlocked(gameMap, footX, footY);
  }

  function entryAllows(event) {
    if (!event || typeof event !== "object") return true;
    const allowed = [];
    if (typeof event.entry_point_id === "string") allowed.push(event.entry_point_id);
    if (Array.isArray(event.entry_point_ids)) {
      event.entry_point_ids.forEach((id) => {
        if (typeof id === "string") allowed.push(id);
      });
    }
    return !state.entryId || allowed.length === 0 || allowed.includes(state.entryId);
  }

  function conditionPasses(conditions) {
    if (!conditions || typeof conditions !== "object") return true;
    if (conditions.entry_id && conditions.entry_id !== state.entryId) return false;
    if (Array.isArray(conditions.entry_ids) && !conditions.entry_ids.includes(state.entryId)) return false;
    if (conditions.flags) {
      for (const [key, value] of Object.entries(conditions.flags)) {
        if (state.flags[key] !== value) return false;
      }
    }
    if (conditions.quests) {
      for (const [key, value] of Object.entries(conditions.quests)) {
        if (state.quests[key] !== value) return false;
      }
    }
    if (conditions.inventory) {
      for (const [key, value] of Object.entries(conditions.inventory)) {
        if (Number(state.inventory[key] || 0) < Number(value)) return false;
      }
    }
    return true;
  }

  function weightedPick(items) {
    const candidates = (Array.isArray(items) ? items : []).filter((item) => conditionPasses(item.conditions));
    if (!candidates.length) return null;
    const total = candidates.reduce((sum, item) => sum + Math.max(0, Number(item.weight || 1)), 0) || candidates.length;
    let roll = Math.random() * total;
    for (const item of candidates) {
      roll -= Math.max(0, Number(item.weight || 1));
      if (roll <= 0) return item;
    }
    return candidates[candidates.length - 1];
  }

  function chooseOutcome(event) {
    if (!Array.isArray(event.outcomes)) return null;
    if (typeof event.trigger_chance === "number" && Math.random() > event.trigger_chance) {
      return {
        id: `${event.id}.quiet`,
        lines: event.miss_lines || [`${event.name || "Something"} gives no clear answer this time.`],
      };
    }
    return weightedPick(event.outcomes);
  }

  function applyNumberDelta(target, values) {
    if (!values || typeof values !== "object") return;
    Object.entries(values).forEach(([key, value]) => {
      target[key] = Number(target[key] || 0) + Number(value || 0);
    });
  }

  function applyOutcome(outcome, event) {
    if (!outcome || typeof outcome !== "object") return;
    applyKeyValueSet(state.flags, outcome.set_flags);
    applyKeyValueSet(state.flags, outcome.flags);
    applyKeyValueSet(state.quests, outcome.quest_updates);
    applyNumberDelta(state.inventory, outcome.inventory_delta);
    if (outcome.reward_item_id) {
      state.inventory[outcome.reward_item_id] = (state.inventory[outcome.reward_item_id] || 0) + Number(outcome.reward_quantity || 1);
      queueFloat(`+ ${outcome.reward_item_id}`, "good");
    }
    if (outcome.complete_quest_id) {
      state.quests[outcome.complete_quest_id] = "complete";
      queueFloat(`${outcome.complete_quest_id}: complete`, "good");
    }
    if (outcome.activate_quest_id && !state.quests[outcome.activate_quest_id]) {
      state.quests[outcome.activate_quest_id] = "active";
      queueFloat(`${outcome.activate_quest_id}: active`, "good");
    }
    if (outcome.hero_hp_delta) {
      state.hero.hp = clamp(state.hero.hp + Number(outcome.hero_hp_delta), 1, state.hero.maxHp);
    }
    if (outcome.set_entry_id || outcome.entry_point_id) {
      setEntryPoint(outcome.set_entry_id || outcome.entry_point_id);
    }
    if (outcome.ending_id) {
      state.flags[`ending:${outcome.ending_id}`] = true;
      state.flags.ending_ready = true;
    }
    if (outcome.log) addLog(outcome.log);
    if (event && outcome.once !== false && event.once) state.flags[`event_done:${event.id}`] = true;
  }

  function eventsAt(gameMap, x, y) {
    const radius = INTERACT_RADIUS;
    return (Array.isArray(gameMap.events) ? gameMap.events : []).filter((event) => (
      Math.hypot(Number(event.x) - x, Number(event.y) - y) <= radius &&
      !state.flags[`event_done:${event.id}`] &&
      entryAllows(event)
    ));
  }

  function nearbyEvent() {
    const gameMap = currentMap();
    return eventsAt(gameMap, state.x, state.y)
      .map((event) => ({ event, distance: Math.hypot(Number(event.x) - state.x, Number(event.y) - state.y) }))
      .sort((a, b) => a.distance - b.distance)[0]?.event || null;
  }

  function render() {
    const gameMap = currentMap();
    const mapChanged = state.renderedMapId !== gameMap.id || !state.worldEl;
    playMapBgm(gameMap);
    elements.title.textContent = data.title || "Playable Web RPG";
    elements.location.textContent = gameMap.title || gameMap.id;
    elements.map.classList.toggle("show-boundaries", Boolean(state.showBoundaries));
    if (elements.boundaryBtn) {
      elements.boundaryBtn.textContent = state.showBoundaries ? "Walls: On" : "Walls: Off";
      elements.boundaryBtn.setAttribute("aria-pressed", state.showBoundaries ? "true" : "false");
    }
    let world = state.worldEl;
    if (mapChanged) {
      elements.map.innerHTML = "";
      world = createMapWorld(gameMap);
      elements.map.appendChild(world);
      state.worldEl = world;
    }

    clearDynamicLayers(world);
    const eventLayer = document.createElement("div");
    eventLayer.className = "event-layer";
    renderEvents(gameMap, eventLayer);
    world.appendChild(eventLayer);

    if (state.showBoundaries) {
      renderBoundaryLayer(gameMap, world);
    }

    const avatarLayer = document.createElement("div");
    avatarLayer.className = "avatar-layer";
    renderAvatar(avatarLayer);
    world.appendChild(avatarLayer);

    clearMapOverlays();
    appendTouchControls();
    renderInteractionHint();
    flushFloatingText();
    applyCamera(world, gameMap, mapChanged);
    state.renderedMapId = gameMap.id;
    state.nearbyId = nearbyEvent()?.id || null;

    renderPanel();
    renderDialogue();
    renderBattle();
    renderBattleUiShowcase();
    renderEnding();
    renderEntrySelect();
  }

  function createMapWorld(gameMap) {
    const world = document.createElement("div");
    world.className = "map-world";
    world.classList.add("pixel-coordinate-map");
    world.style.setProperty("--tile-size", "1px");
    world.style.width = `${worldWidth(gameMap)}px`;
    world.style.height = `${worldHeight(gameMap)}px`;
    const mapBackground = mapBackgroundPath(gameMap);
    world.style.backgroundImage = mapBackground ? `url("${encodeURI(mapBackground)}")` : "";
    world.classList.toggle("dynamic-still-map", Boolean(mapBackground));
    const mapVideo = mapVideoPath(gameMap);
    if (mapVideo) {
      world.classList.remove("dynamic-still-map");
      const isVideo = /\.(mp4|webm|ogg)(?:[?#].*)?$/i.test(mapVideo);
      if (isVideo) {
        const video = document.createElement("video");
        video.className = "dynamic-map-media";
        video.src = mapVideo;
        video.autoplay = true;
        video.muted = true;
        video.loop = true;
        video.playsInline = true;
        video.setAttribute("aria-hidden", "true");
        world.appendChild(video);
      } else {
        const image = document.createElement("img");
        image.className = "dynamic-map-media";
        image.src = mapVideo;
        image.alt = "";
        image.setAttribute("aria-hidden", "true");
        world.appendChild(image);
      }
    }

    return world;
  }

  function clearDynamicLayers(world) {
    if (!world) return;
    world.querySelectorAll(".event-layer, .avatar-layer, .boundary-layer").forEach((node) => node.remove());
  }

  function clearMapOverlays() {
    elements.map.querySelectorAll(".interaction-hint, .float-text").forEach((node) => node.remove());
  }

  function renderEvents(gameMap, layer) {
    const focus = nearbyEvent();
    (Array.isArray(gameMap.events) ? gameMap.events : []).forEach((event) => {
      if (state.flags[`event_done:${event.id}`] || !entryAllows(event)) {
        return;
      }
      const marker = document.createElement("div");
      const type = String(event.type || "npc");
      marker.className = `event-sprite ${markerClass(event)}${focus && focus.id === event.id ? " nearby" : ""}`;
      const markerX = Number(event.x);
      const markerY = Number(event.y);
      marker.style.left = `${coordToPx(markerX)}px`;
      marker.style.top = `${coordToPx(markerY)}px`;
      const eventAsset = eventAssetId(event);
      const sprite = motionAssetPath(eventAsset) || assetPath(eventAsset);
      if (sprite) {
        marker.classList.add("has-image");
        const img = document.createElement("img");
        img.src = sprite;
        img.alt = "";
        marker.appendChild(img);
      } else {
        marker.textContent = markerText(type);
      }
      layer.appendChild(marker);
    });
  }

  function renderMaskBoundaryLayer(gameMap, world) {
    const maskRef = maskRefForMap(gameMap);
    if (!maskRef) return false;
    const mask = ensureWalkableMask(gameMap);
    if (!mask || mask.status !== "ready" || !mask.context) return false;
    const canvas = document.createElement("canvas");
    canvas.className = "boundary-layer boundary-mask-layer";
    canvas.width = mask.width;
    canvas.height = mask.height;
    const context = canvas.getContext("2d");
    if (context) {
      const source = mask.context.getImageData(0, 0, mask.width, mask.height);
      const output = context.createImageData(mask.width, mask.height);
      for (let index = 0; index < source.data.length; index += 4) {
        const walkable = source.data[index + 3] > 0 && (source.data[index] + source.data[index + 1] + source.data[index + 2]) / 3 >= 128;
        if (walkable) {
          output.data[index] = 0;
          output.data[index + 1] = 255;
          output.data[index + 2] = 255;
          output.data[index + 3] = 80;
        }
      }
      context.putImageData(output, 0, 0);
    }
    world.appendChild(canvas);
    return true;
  }

  function renderShapeBoundaryLayer(gameMap, world) {
    const shapes = Array.isArray(gameMap.collision_shapes) ? gameMap.collision_shapes : [];
    if (!shapes.length) return false;
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("class", "boundary-layer");
    svg.setAttribute("viewBox", `0 0 ${worldWidth(gameMap)} ${worldHeight(gameMap)}`);
    svg.setAttribute("width", `${worldWidth(gameMap)}`);
    svg.setAttribute("height", `${worldHeight(gameMap)}`);
    shapes.forEach((shape) => {
      let node = null;
      if (shape.type === "polygon" && Array.isArray(shape.points)) {
        node = document.createElementNS(namespace, "polygon");
        node.setAttribute("points", shape.points.map((point) => `${coordToPx(point[0])},${coordToPx(point[1])}`).join(" "));
      } else if (shape.type === "rect") {
        node = document.createElementNS(namespace, "rect");
        node.setAttribute("x", `${coordToPx(shape.x)}`);
        node.setAttribute("y", `${coordToPx(shape.y)}`);
        node.setAttribute("width", `${coordToPx(shape.w)}`);
        node.setAttribute("height", `${coordToPx(shape.h)}`);
      }
      if (node) {
        node.setAttribute("data-boundary-id", shape.id || "");
        svg.appendChild(node);
      }
    });
    world.appendChild(svg);
    return true;
  }

  function renderBoundaryLayer(gameMap, world) {
    renderMaskBoundaryLayer(gameMap, world);
    renderShapeBoundaryLayer(gameMap, world);
  }

  function renderAvatar(layer) {
    const avatar = document.createElement("div");
    avatar.className = `avatar facing-${state.facing}${state.moving ? " walking" : ""}`;
    const gameMap = currentMap();
    const startX = state.moving && state.prevMapId === state.mapId && Number.isFinite(state.prevX) ? state.prevX : state.x;
    const startY = state.moving && state.prevMapId === state.mapId && Number.isFinite(state.prevY) ? state.prevY : state.y;
    avatar.style.left = `${coordToPx(playerFootX(startX))}px`;
    avatar.style.top = `${coordToPx(playerFootY(startY))}px`;

    const body = document.createElement("div");
    body.className = "avatar-body";
    const sprite = assetPath(state.hero.spriteAssetId);
    const idleMotion = motionAssetPath(state.hero.spriteAssetId);
    if (!state.moving && idleMotion) {
      const img = document.createElement("img");
      img.className = "avatar-sprite";
      img.src = idleMotion;
      img.alt = "";
      body.appendChild(img);
    } else if (state.hero.walkFrameAssetIds) {
      const img = document.createElement("img");
      img.className = "avatar-walk-frame";
      img.alt = "";
      body.appendChild(img);
    } else if (assetPath(state.hero.walkSheetAssetId)) {
      const sheet = document.createElement("div");
      sheet.className = "avatar-walk-sheet";
      sheet.style.backgroundImage = `url("${encodeURI(assetPath(state.hero.walkSheetAssetId))}")`;
      body.appendChild(sheet);
    } else if (sprite) {
      const img = document.createElement("img");
      img.className = "avatar-sprite";
      img.src = sprite;
      img.alt = "";
      body.appendChild(img);
    } else {
      const token = document.createElement("div");
      token.className = "avatar-token";
      token.textContent = "@";
      body.appendChild(token);
    }
    avatar.appendChild(body);
    layer.appendChild(avatar);
    state.avatarEl = avatar;
    updateAvatarFrame();
  }

  function applyCamera(world, gameMap, immediate) {
    const viewportWidth = elements.map.clientWidth || 900;
    const viewportHeight = elements.map.clientHeight || 600;
    const mapWorldWidth = worldWidth(gameMap);
    const mapWorldHeight = worldHeight(gameMap);
    const playerCenterX = coordToPx(playerFootX(state.x));
    const playerCenterY = coordToPx(playerFootY(state.y));
    const targetX = clamp(playerCenterX - viewportWidth / 2, 0, Math.max(0, mapWorldWidth - viewportWidth));
    const targetY = clamp(playerCenterY - viewportHeight / 2, 0, Math.max(0, mapWorldHeight - viewportHeight));

    state.cameraX = targetX;
    state.cameraY = targetY;
    world.style.transform = `translate(${-targetX}px, ${-targetY}px)`;
  }

  function markerClass(event) {
    const type = String(event.type || "");
    if (type === "battle" || type === "encounter") return "battle-event";
    if (type === "rest") return "rest-event";
    if (type === "pickup" || type === "item") return "item-event";
    if (type === "quest") return "quest-event";
    if (type === "shop") return "shop-event";
    if (type === "transfer") return "transfer-event";
    return "npc";
  }

  function markerText(type) {
    if (type === "battle" || type === "encounter") return "!";
    if (type === "rest") return "+";
    if (type === "pickup" || type === "item") return "*";
    if (type === "quest") return "?";
    if (type === "shop") return "$";
    if (type === "transfer") return ">";
    return "i";
  }

  function eventAssetId(event) {
    if (!event || typeof event !== "object") return null;
    if (typeof event.sprite_asset_id === "string") return event.sprite_asset_id;
    if (typeof event.asset_id === "string") return event.asset_id;
    const type = String(event.type || "");
    if ((type === "battle" || type === "encounter") && event.enemy_id && enemies[event.enemy_id]) {
      return enemies[event.enemy_id].sprite_asset_id || enemies[event.enemy_id].asset_id || event.enemy_id;
    }
    if ((type === "pickup" || type === "item") && event.item_id && items[event.item_id]) {
      return items[event.item_id].icon_asset_id || items[event.item_id].asset_id || `icon.item.${slug(event.item_id)}`;
    }
    if (type === "npc" || type === "shop" || type === "quest") {
      const eventSlug = slug(event.id);
      const candidate = `sprite.${eventSlug}`;
      if (assetPath(candidate)) return candidate;
    }
    return null;
  }

  function eventLabel(event) {
    if (!event) return "";
    return event.name || event.title || event.id || "Interact";
  }

  function renderInteractionHint() {
    if (
      state.dialogue ||
      state.battle ||
      state.battleUi ||
      (state.completed && !state.endingDismissed) ||
      (entrySelectRequired && !state.entryId)
    ) {
      return;
    }
    const event = nearbyEvent();
    const hint = document.createElement("div");
    hint.className = "interaction-hint";
    hint.textContent = event ? `Space / Enter: ${eventLabel(event)}` : "Move near a person or place to interact";
    elements.map.appendChild(hint);
  }

  function flushFloatingText() {
    const effects = state.effects.splice(0);
    effects.forEach((effect, index) => {
      const label = document.createElement("div");
      label.className = `float-text ${effect.tone || "good"}`;
      label.textContent = effect.text;
      label.style.top = `${42 + index * 6}%`;
      elements.map.appendChild(label);
    });
  }

  function renderPanel() {
    const hpRatio = clamp(state.hero.hp / state.hero.maxHp, 0, 1) * 100;
    const entryLine = state.entryTitle ? `<div>${escapeHtml(state.entryTitle)}</div>` : "";
    const gameMap = currentMap();
    const worldLine = gameMap.world_title || gameMap.world_id || gameMap.region || "";
    elements.party.innerHTML = `
      <section class="panel-section">
        <h2>${escapeHtml(state.hero.name)}</h2>
        ${entryLine}
        ${worldLine ? `<div>${escapeHtml(worldLine)}</div>` : ""}
        <div>HP ${Math.ceil(state.hero.hp)} / ${Math.ceil(state.hero.maxHp)}</div>
        <div class="meter"><span style="width:${hpRatio}%"></span></div>
        <div>ATK ${state.hero.attack} DEF ${state.hero.defense}</div>
      </section>
    `;
    const questIds = Object.keys(quests);
    const questLines = questIds.length
      ? questIds.map((id) => `<div>${escapeHtml(quests[id].title || id)}: ${escapeHtml(state.quests[id] || "locked")}</div>`).join("")
      : "<div>No active quests</div>";
    elements.questLog.innerHTML = `<section class="panel-section"><h2>Quests</h2>${questLines}</section>`;
    const logLines = state.log.length ? state.log.map((line) => `<div>${escapeHtml(line)}</div>`).join("") : "<div>Find someone to talk to.</div>";
    elements.messageLog.innerHTML = `<section class="panel-section"><h2>Log</h2>${logLines}</section>`;
  }

  function renderEntrySelect() {
    if (!elements.entrySelect) return;
    if (!entrySelectRequired || state.entryId) {
      elements.entrySelect.classList.add("hidden");
      return;
    }
    elements.entryTitle.textContent = data.campaign && data.campaign.entry_title ? data.campaign.entry_title : "Choose an Entry Point";
    elements.entryText.textContent = data.campaign && data.campaign.entry_text ? data.campaign.entry_text : "Choose the perspective that controls your start location, role, and active story triggers.";
    elements.entryOptions.innerHTML = "";
    entryPoints.forEach((entry) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "entry-option";
      button.dataset.entryId = entry.id;
      button.innerHTML = `<strong>${escapeHtml(entry.title || entry.id)}</strong><span>${escapeHtml(entry.description || "")}</span>`;
      elements.entryOptions.appendChild(button);
    });
    elements.entrySelect.classList.remove("hidden");
  }

  function applyKeyValueSet(target, values) {
    if (!values || typeof values !== "object") return;
    Object.entries(values).forEach(([key, value]) => {
      target[key] = value;
    });
  }

  function setEntryPoint(entryId) {
    if (!entryId || state.entryId === entryId) return;
    const entry = entryPoints.find((item) => item.id === entryId);
    state.entryId = entryId;
    state.entryTitle = entry ? entry.title || entry.id : entryId;
    if (entry) {
      applyKeyValueSet(state.flags, entry.initial_flags);
      applyKeyValueSet(state.inventory, entry.initial_inventory);
      (Array.isArray(entry.initial_quests) ? entry.initial_quests : []).forEach((questId) => {
        if (typeof questId === "string" && !state.quests[questId]) state.quests[questId] = "active";
      });
      if (entry.initial_quest_states && typeof entry.initial_quest_states === "object") {
        applyKeyValueSet(state.quests, entry.initial_quest_states);
      }
    }
    addLog(`Route opened: ${state.entryTitle}`);
    queueFloat(state.entryTitle, "good");
  }

  function selectEntry(entryId) {
    const entry = entryPoints.find((item) => item.id === entryId) || defaultEntry;
    const entryPosition = entry.start_position || data.start_position || { x: 1, y: 1 };
    const actor = actorForParty(entry.party || data.party);
    state.entryId = entry.id;
    state.entryTitle = entry.title || entry.id;
    state.mapId = entry.start_map_id && maps[entry.start_map_id] ? entry.start_map_id : firstMapId;
    state.x = Number(entryPosition.x || 1);
    state.y = Number(entryPosition.y || 1);
    state.prevX = null;
    state.prevY = null;
    state.prevMapId = null;
    state.renderedMapId = null;
    state.cameraX = 0;
    state.cameraY = 0;
    state.hero = heroFromActor(actor || fallbackActor);
    state.flags = {};
    state.inventory = {};
    state.quests = {};
    state.log = [];
    state.dialogue = null;
    state.battle = null;
    state.completed = false;
    state.endingDismissed = false;
    applyKeyValueSet(state.flags, entry.initial_flags);
    applyKeyValueSet(state.inventory, entry.initial_inventory);
    (Array.isArray(entry.initial_quests) ? entry.initial_quests : []).forEach((questId) => {
      if (typeof questId === "string") state.quests[questId] = "active";
    });
    if (entry.initial_quest_states && typeof entry.initial_quest_states === "object") {
      applyKeyValueSet(state.quests, entry.initial_quest_states);
    }
    addLog(`Entry: ${entry.title || entry.id}`);
    flashMap("travel");
    render();
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
      "'": "&#39;"
    }[char]));
  }

  function updateAvatarPosition() {
    if (!state.avatarEl) return;
    const gameMap = currentMap();
    state.avatarEl.style.left = `${coordToPx(playerFootX(state.x))}px`;
    state.avatarEl.style.top = `${coordToPx(playerFootY(state.y))}px`;
    state.avatarEl.className = `avatar facing-${state.facing}${state.moving ? " walking" : ""}`;
    updateAvatarFrame();
  }

  function directionRow() {
    if (state.facing === "left") return 1;
    if (state.facing === "right") return 2;
    if (state.facing === "up") return 3;
    return 0;
  }

  function updateAvatarFrame() {
    if (!state.avatarEl) return;
    const frameImage = state.avatarEl.querySelector(".avatar-walk-frame");
    const col = state.moving ? state.walkFrame : 0;
    const row = directionRow();
    if (frameImage && state.hero.walkFrameAssetIds) {
      const direction = state.facing === "left" || state.facing === "right" || state.facing === "up" ? state.facing : "down";
      const frames = Array.isArray(state.hero.walkFrameAssetIds[direction]) ? state.hero.walkFrameAssetIds[direction] : [];
      const assetId = frames[col] || frames[0];
      const framePath = assetPath(assetId);
      if (framePath) frameImage.src = framePath;
      return;
    }
    const sheet = state.avatarEl.querySelector(".avatar-walk-sheet");
    if (!sheet) return;
    sheet.style.backgroundPosition = `${col * (100 / 3)}% ${row * (100 / 3)}%`;
  }

  function updateCameraPosition() {
    if (!state.worldEl) return;
    applyCamera(state.worldEl, currentMap(), false);
  }

  function setFacing(dx, dy) {
    if (Math.abs(dx) > Math.abs(dy)) state.facing = dx > 0 ? "right" : "left";
    else if (dy) state.facing = dy > 0 ? "down" : "up";
  }

  function updateMovement(dt) {
    if (state.dialogue || state.battle || state.completed && !state.endingDismissed) {
      state.moving = false;
      updateAvatarPosition();
      return;
    }
    let dx = 0;
    let dy = 0;
    if (state.keys.has("arrowleft") || state.keys.has("a")) dx -= 1;
    if (state.keys.has("arrowright") || state.keys.has("d")) dx += 1;
    if (state.keys.has("arrowup") || state.keys.has("w")) dy -= 1;
    if (state.keys.has("arrowdown") || state.keys.has("s")) dy += 1;
    state.moving = Boolean(dx || dy);
    if (!state.moving) {
      state.walkElapsed = 0;
      state.walkFrame = 0;
      updateAvatarPosition();
      return;
    }
    state.walkElapsed += dt;
    state.walkFrame = Math.floor(state.walkElapsed / 0.13) % 4;
    const length = Math.hypot(dx, dy) || 1;
    dx /= length;
    dy /= length;
    setFacing(dx, dy);
    const gameMap = currentMap();
    const step = PLAYER_SPEED * dt;
    const nx = state.x + dx * step;
    const ny = state.y + dy * step;
    state.prevX = state.x;
    state.prevY = state.y;
    state.prevMapId = state.mapId;
    if (!isBlocked(gameMap, nx, state.y)) state.x = nx;
    if (!isBlocked(gameMap, state.x, ny)) state.y = ny;
    updateAvatarPosition();
    updateCameraPosition();
    const touchEvent = nearbyEvent();
    const nextNearbyId = touchEvent?.id || null;
    if (nextNearbyId !== state.nearbyId) {
      render();
      return;
    }
    if (touchEvent && touchEvent.trigger === "touch" && Math.hypot(Number(touchEvent.x) - state.x, Number(touchEvent.y) - state.y) <= INTERACT_RADIUS * 0.36) {
      interact(touchEvent);
    }
  }

  function animationFrame(now) {
    const last = state.lastFrame || now;
    state.lastFrame = now;
    updateMovement(Math.min(0.05, (now - last) / 1000));
    state.frameRequest = window.requestAnimationFrame(animationFrame);
  }

  function startLoop() {
    if (state.frameRequest) return;
    state.lastFrame = performance.now();
    state.frameRequest = window.requestAnimationFrame(animationFrame);
  }

  function interact(event) {
    const target = event || nearbyEvent();
    if (!target) {
      playSfx("sfx.ui.error");
      queueFloat("Nothing here", "hit");
      render();
      return;
    }
    const outcome = chooseOutcome(target);
    const type = String(target.type || "npc");
    if (type === "story" || type === "choice") {
      playSfx("sfx.story.choice");
    } else if (!["battle", "encounter", "rest", "pickup", "item", "transfer"].includes(type)) {
      playSfx("sfx.ui.interact", 0.48);
    }
    if (type === "battle" || type === "encounter") return startBattle(target);
    if (type === "rest") return rest(target);
    if (type === "pickup" || type === "item") return pickup(target);
    if (type === "transfer") return transfer(target);
    if (type === "shop") return talk(target, outcome && outcome.lines ? outcome.lines : shopLines(target), outcome);
    if (type === "quest") return acceptQuest(target, outcome);
    talk(target, outcome && outcome.lines ? outcome.lines : linesFor(target), outcome);
  }

  function linesFor(event) {
    if (Array.isArray(event.lines)) return event.lines;
    const dialogue = event.dialogue_id ? dialogues[event.dialogue_id] : null;
    if (dialogue && Array.isArray(dialogue.lines)) return dialogue.lines;
    if (dialogue && Array.isArray(dialogue.beats)) return dialogue.beats.map((beat) => beat.text || beat.line || String(beat));
    return [`${event.name || "Someone"} has nothing more to say.`];
  }

  function shopLines(event) {
    const shop = event.shop_id ? shops[event.shop_id] : null;
    const wares = shop && Array.isArray(shop.items) ? shop.items.join(", ") : "basic supplies";
    return [`${event.name || "Shop"} offers ${wares}.`, "Trading is represented as dialogue in this MVP runtime."];
  }

  function talk(event, rawLines, outcome = null) {
    const lines = rawLines.map((line) => typeof line === "string" ? { speaker: event.name || "NPC", text: line } : line);
    playSfx("sfx.dialogue.open");
    state.dialogue = { event, lines, index: 0, outcome };
    if (event.quest_id && quests[event.quest_id] && !state.quests[event.quest_id]) {
      state.quests[event.quest_id] = "active";
      playSfx("sfx.quest.update");
      queueFloat(`${quests[event.quest_id].title || event.quest_id}: active`, "good");
    }
    render();
  }

  function acceptQuest(event, outcome = null) {
    const questId = event.quest_id || event.id;
    state.quests[questId] = event.complete ? "complete" : "active";
    playSfx("sfx.quest.update");
    talk(event, outcome && outcome.lines ? outcome.lines : linesFor(event), outcome);
    queueFloat(`${quests[questId] ? quests[questId].title || questId : questId}: ${state.quests[questId]}`, "good");
    addLog(`${questId} updated.`);
    checkCompletion();
  }

  function nextDialogue() {
    if (!state.dialogue) return;
    state.dialogue.index += 1;
    if (state.dialogue.index >= state.dialogue.lines.length) {
      const event = state.dialogue.event;
      if (event.once) {
        state.flags[`event_done:${event.id}`] = true;
      }
      if (event.complete_quest_id) {
        state.quests[event.complete_quest_id] = "complete";
        queueFloat(`${event.complete_quest_id}: complete`, "good");
      }
      applyOutcome(state.dialogue.outcome, event);
      state.dialogue = null;
      stopVoice();
      checkCompletion();
    }
    render();
  }

  function renderDialogue() {
    if (!state.dialogue) {
      elements.dialogue.classList.add("hidden");
      stopVoice();
      return;
    }
    const line = state.dialogue.lines[state.dialogue.index] || {};
    elements.dialogueSpeaker.textContent = line.speaker || state.dialogue.event.name || "NPC";
    elements.dialogueText.textContent = line.text || String(line);
    playVoiceForLine(line);
    const portrait = assetPath(eventAssetId(state.dialogue.event));
    elements.dialoguePortrait.innerHTML = portrait ? `<img src="${encodeURI(portrait)}" alt="">` : "";
    elements.dialogue.classList.remove("hidden");
  }

  function rest(event) {
    const restPoint = event.rest_point_id ? restPoints[event.rest_point_id] : null;
    const cost = Number((restPoint && restPoint.cost) || event.cost || 0);
    state.hero.hp = state.hero.maxHp;
    addLog(cost ? `Rested for ${cost}.` : "Rested and recovered.");
    playSfx("sfx.rest.recover");
    queueFloat("HP restored", "good");
    flashMap("good");
    if (event.once) state.flags[`event_done:${event.id}`] = true;
    render();
  }

  function pickup(event) {
    const itemId = event.item_id || "item.unknown";
    state.inventory[itemId] = (state.inventory[itemId] || 0) + Number(event.quantity || 1);
    const label = items[itemId] ? items[itemId].name || itemId : itemId;
    addLog(`Got ${label}.`);
    playSfx("sfx.pickup.item");
    queueFloat(`+ ${label}`, "good");
    flashMap("good");
    state.flags[`event_done:${event.id}`] = true;
    render();
  }

  function transfer(event) {
    if (!event.target_map_id || !maps[event.target_map_id]) {
      playSfx("sfx.ui.error");
      queueFloat("Exit is not connected", "hit");
      render();
      return;
    }
    state.mapId = event.target_map_id;
    state.x = Number(event.target_x || 1);
    state.y = Number(event.target_y || 1);
    state.prevX = null;
    state.prevY = null;
    state.moving = false;
    state.renderedMapId = null;
    state.cameraX = 0;
    state.cameraY = 0;
    addLog(`Moved to ${maps[state.mapId].title || state.mapId}.`);
    playSfx("sfx.transfer.portal");
    queueFloat(maps[state.mapId].title || state.mapId, "good");
    flashMap("travel");
    render();
  }

  function startBattle(event) {
    const enemyId = resolveEnemyId(event);
    if (!enemyId || !enemies[enemyId]) {
      playSfx("sfx.ui.error");
      queueFloat("No enemy configured", "hit");
      render();
      return;
    }
    const source = enemies[enemyId];
    state.battle = {
      event,
      turn: 1,
      phase: "player",
      heroFocus: 1,
      enemyFocus: 0,
      heroGuard: false,
      enemyGuard: false,
      lastAction: "",
      enemy: enemyFromSource(source),
      backgroundAssetId: event.battle_background_asset_id || firstAssetWithPrefix("battlebg."),
      text: `${source.name || source.id} 现身，战斗开始。`,
      damageText: "",
      hitFlash: false
    };
    playSfx("sfx.battle.start", 0.84);
    flashMap("hit");
    render();
  }

  function resolveEnemyId(event) {
    if (event.enemy_id && enemies[event.enemy_id]) return event.enemy_id;
    const encounter = event.encounter_id ? encounters[event.encounter_id] : null;
    const candidates = encounter ? (encounter.enemies || encounter.enemy_ids || []) : [];
    for (const candidate of candidates) {
      if (typeof candidate === "string" && enemies[candidate]) return candidate;
      if (candidate && enemies[candidate.enemy_id]) return candidate.enemy_id;
    }
    return Object.keys(enemies)[0];
  }

  function enemyFromSource(source) {
    return {
      id: source.id,
      name: source.name || source.id,
      hp: maxHp(source),
      maxHp: maxHp(source),
      attack: stat(source, "attack", 5),
      defense: stat(source, "defense", 0),
      speed: stat(source, "speed", 1),
      spriteAssetId: source.sprite_asset_id || source.asset_id || source.id,
      skills: Array.isArray(source.skills) ? source.skills : [],
      pattern: Array.isArray(source.pattern) ? source.pattern : ["attack", "guard", "attack", "skill"]
    };
  }

  function renderBattle() {
    if (elements.battle) elements.battle.classList.add("hidden");
    if (!state.battle) {
      if (elements.battleVisual) elements.battleVisual.innerHTML = "";
      if (elements.battleBox) {
        elements.battleBox.style.backgroundImage = "";
        elements.battleBox.classList.remove("hit-shake");
      }
      if (elements.battleUiShowcase && elements.battleUiShowcase.dataset.mode === "real") {
        elements.battleUiShowcase.classList.add("hidden");
        elements.battleUiShowcase.classList.remove("battle-ui-real");
        delete elements.battleUiShowcase.dataset.mode;
        clearRealBattleBounds();
      }
      return;
    }
    if (elements.battleUiShowcase) {
      elements.battleUiShowcase.dataset.mode = "real";
      elements.battleUiShowcase.classList.add("battle-ui-real");
      elements.battleUiShowcase.classList.remove("hidden");
      syncRealBattleBounds();
    }
  }

  function renderBattleUiShowcase() {
    if (!elements.battleUiBtn) return;
    if (!battleUiShowcase && !state.battle) {
      elements.battleUiBtn.hidden = true;
      return;
    }
    elements.battleUiBtn.hidden = false;
    if (!elements.battleUiShowcase || elements.battleUiShowcase.classList.contains("hidden")) return;
    const previewPath = assetPath(battleUiShowcase && battleUiShowcase.preview_asset_id);
    const isRealBattle = Boolean(state.battle);
    if (!isRealBattle) ensureBattleUiState();
    const gameMap = currentMap();
    const battle = isRealBattle ? state.battle : state.battleUi;
    const enemy = battle.enemy;
    const heroSprite = motionAssetPath(state.hero.spriteAssetId) || assetPath(state.hero.spriteAssetId);
    const enemySprite = motionAssetPath(enemy.spriteAssetId) || assetPath(enemy.spriteAssetId);
    const battleBackground = isRealBattle ? mapBackgroundPath(gameMap) : "";
    const battleDynamicBackground = isRealBattle ? mapVideoPath(gameMap) : "";
    elements.battleUiTitle.textContent = isRealBattle ? `Sengoku Era Battle: ${enemy.name}` : ((battleUiShowcase && battleUiShowcase.title) || "Battle UI");
    elements.battleUiText.textContent = isRealBattle
      ? "地图事件已切入独立 Sengoku Era 战斗界面。胜利、撤退或失败恢复后会回到原地图。"
      : (battleUiShowcase && battleUiShowcase.description) || "";
    elements.battleUiFlow.innerHTML = isRealBattle
      ? `<button type="button" class="active">Map flow -> Battle loop -> Return</button>`
      : entryPoints.map((entry) => (
        `<button type="button" class="${entry.id === state.entryId ? "active" : ""}" data-battle-ui-entry="${escapeHtml(entry.id)}">
          ${escapeHtml(entry.title || entry.id)}
        </button>`
      )).join("");
    elements.battleUiFeatures.innerHTML = (battleUiShowcase && Array.isArray(battleUiShowcase.features) ? battleUiShowcase.features : [])
      .map((feature) => `<li>${escapeHtml(feature)}</li>`)
      .join("");
    renderBattleBackground(battleBackground || previewPath, battleDynamicBackground, isRealBattle);
    elements.battleUiRoute.textContent = `Starter / Entry: ${state.entryTitle || defaultEntry.title || defaultEntry.id}`;
    elements.battleUiMap.textContent = `Map: ${gameMap.title || gameMap.id}`;
    elements.battleUiCombatants.innerHTML = `
      <div class="battle-ui-unit">
        ${heroSprite ? `<img src="${encodeURI(heroSprite)}" alt="">` : ""}
        <strong>${escapeHtml(state.hero.name)}</strong>
      </div>
      <div class="battle-ui-versus">VS</div>
      <div class="battle-ui-unit">
        ${enemySprite ? `<img src="${encodeURI(enemySprite)}" alt="">` : ""}
        <strong>${escapeHtml(enemy.name)}</strong>
      </div>
    `;
    elements.battleUiStats.innerHTML = `
      <div class="battle-ui-stat-card">
        ${battleStatusBlock(`${state.hero.name} Lv.1`, state.hero.hp, state.hero.maxHp, battle.heroFocus, battle.heroGuard)}
        <div>ATK ${state.hero.attack} / DEF ${state.hero.defense} / SPD ${state.hero.speed}</div>
      </div>
      <div class="battle-ui-stat-card">
        ${battleStatusBlock(enemy.name, enemy.hp, enemy.maxHp, battle.enemyFocus, battle.enemyGuard)}
        <div>ATK ${enemy.attack} / DEF ${enemy.defense} / SPD ${enemy.speed}</div>
      </div>
    `;
    elements.battleUiLog.textContent = battle.text;
    renderBattleUiActions(isRealBattle);
    if (battleUiShowcase && battleUiShowcase.source_url) {
      elements.battleUiLink.href = battleUiShowcase.source_url;
      elements.battleUiLink.hidden = false;
    } else {
      elements.battleUiLink.hidden = true;
    }
    if (elements.battleUiReset) elements.battleUiReset.hidden = isRealBattle;
    if (elements.battleUiClose) elements.battleUiClose.hidden = isRealBattle;
    if (isRealBattle) {
      syncRealBattleBounds();
      state.battle.hitFlash = false;
      state.battle.lastAction = "";
      state.battle.damageText = "";
    }
  }

  function mapBackgroundPath(gameMap) {
    return assetPath(gameMap.asset_id || gameMap.map_asset_id || gameMap.id);
  }

  function renderBattleBackground(fallbackPath, dynamicPath, isRealBattle) {
    if (!elements.battleUiPreview) return;
    elements.battleUiPreview.innerHTML = "";
    elements.battleUiPreview.style.backgroundImage = fallbackPath
      ? `linear-gradient(rgba(12, 14, 12, 0.10), rgba(12, 14, 12, 0.18)), url("${encodeURI(fallbackPath)}")`
      : "";
    if (!isRealBattle || !dynamicPath) return;
    const isVideo = /\.(mp4|webm|ogg)(?:[?#].*)?$/i.test(dynamicPath);
    const media = document.createElement(isVideo ? "video" : "img");
    media.className = "battle-ui-dynamic-bg";
    media.setAttribute("aria-hidden", "true");
    if (isVideo) {
      media.src = dynamicPath;
      media.autoplay = true;
      media.muted = true;
      media.loop = true;
      media.playsInline = true;
    } else {
      media.src = dynamicPath;
      media.alt = "";
    }
    elements.battleUiPreview.appendChild(media);
  }

  function syncRealBattleBounds() {
    if (!elements.battleUiShowcase || !elements.map) return;
    const rect = elements.map.getBoundingClientRect();
    elements.battleUiShowcase.style.setProperty("--battle-left", `${rect.left}px`);
    elements.battleUiShowcase.style.setProperty("--battle-top", `${rect.top}px`);
    elements.battleUiShowcase.style.setProperty("--battle-width", `${rect.width}px`);
    elements.battleUiShowcase.style.setProperty("--battle-height", `${rect.height}px`);
  }

  function clearRealBattleBounds() {
    if (!elements.battleUiShowcase) return;
    ["--battle-left", "--battle-top", "--battle-width", "--battle-height"].forEach((name) => {
      elements.battleUiShowcase.style.removeProperty(name);
    });
  }

  function ensureBattleUiState(force = false) {
    if (!force && state.battleUi && state.battleUi.enemy && state.battleUi.enemy.hp > 0) return;
    const enemyId = battleUiShowcase && battleUiShowcase.default_enemy_id && enemies[battleUiShowcase.default_enemy_id]
      ? battleUiShowcase.default_enemy_id
      : Object.keys(enemies)[0];
    const source = enemies[enemyId] || Object.values(enemies)[0] || { id: "enemy.training", name: "Training Foe", stats: { hp: 20, attack: 6, defense: 2, speed: 2 } };
    state.battleUi = {
      turn: 1,
      heroFocus: 1,
      enemyFocus: 0,
      heroGuard: false,
      enemyGuard: false,
      enemy: enemyFromSource(source),
      text: `${source.name || source.id} 进入 Sengoku battle screen。全局 HP / ATK 已同步。`,
      damageText: "",
      hitFlash: false
    };
  }

  function renderBattleUiActions(isRealBattle = false) {
    if (!elements.battleUiActions || (!state.battleUi && !state.battle)) return;
    const skill = activeHeroSkill();
    const skillLabel = skill ? `${skill.name || "Skill"} (${Number(skill.focus_cost || 0)}气)` : "Skill";
    const rationCount = Number(state.inventory["item.steam_bun"] || 0);
    const actions = [
      ["attack", "斩击"],
      ["skill", skillLabel],
      ["guard", "防御"],
      ["item", `热馍 x${rationCount}`],
      [isRealBattle ? "flee" : "map", isRealBattle ? "撤退" : "回到地图"],
    ];
    elements.battleUiActions.innerHTML = actions.map(([id, label]) => (
      `<button data-battle-ui-action="${id}" type="button">${escapeHtml(label)}</button>`
    )).join("");
  }

  function openBattleUiShowcase() {
    if (!battleUiShowcase || !elements.battleUiShowcase) return;
    elements.battleUiShowcase.dataset.mode = "demo";
    elements.battleUiShowcase.classList.remove("battle-ui-real");
    clearRealBattleBounds();
    elements.battleUiShowcase.classList.remove("hidden");
    renderBattleUiShowcase();
  }

  function closeBattleUiShowcase() {
    if (!elements.battleUiShowcase) return;
    if (elements.battleUiShowcase.dataset.mode === "real" && state.battle) return;
    elements.battleUiShowcase.classList.add("hidden");
    elements.battleUiShowcase.classList.remove("battle-ui-real");
    delete elements.battleUiShowcase.dataset.mode;
    clearRealBattleBounds();
  }

  function battleUiAction(action) {
    if (state.battle) {
      battleAction(action === "map" ? "flee" : action);
      return;
    }
    if (action === "map") {
      closeBattleUiShowcase();
      return;
    }
    ensureBattleUiState();
    const battle = state.battleUi;
    const enemy = battle.enemy;
    battle.heroGuard = false;
    battle.enemyGuard = false;
    if (action === "item") {
      const rationId = "item.steam_bun";
      if (Number(state.inventory[rationId] || 0) > 0) {
        state.inventory[rationId] -= 1;
        const heal = Math.ceil(state.hero.maxHp * 0.32);
        state.hero.hp = clamp(state.hero.hp + heal, 0, state.hero.maxHp);
        battle.heroFocus = clamp(battle.heroFocus + 1, 0, 3);
        battle.text = `Sengoku UI: ${state.hero.name} 使用热馍，恢复 ${heal} HP。`;
      } else {
        battle.heroGuard = true;
        battle.heroFocus = clamp(battle.heroFocus + 1, 0, 3);
        battle.text = "Sengoku UI: 没有热馍，自动转入防御。";
      }
    } else if (action === "guard") {
      battle.heroGuard = true;
      battle.heroFocus = clamp(battle.heroFocus + 1, 0, 3);
      battle.text = `Sengoku UI: ${state.hero.name} 防御，气势上升。`;
    } else {
      const skill = action === "skill" ? activeHeroSkill() : null;
      const cost = Number((skill && skill.focus_cost) || 0);
      if (skill && battle.heroFocus < cost) {
        battle.text = `Sengoku UI: 气势不足，无法施展 ${skill.name || skill.id}。`;
        render();
        return;
      }
      if (skill) battle.heroFocus = clamp(battle.heroFocus - cost, 0, 3);
      const damage = battleDamage(state.hero.attack, enemy.defense, Number((skill && skill.power) || 0), battle.enemyGuard);
      enemy.hp -= damage;
      battle.heroFocus = clamp(battle.heroFocus + (skill ? 0 : 1), 0, 3);
      battle.text = skill
        ? `Sengoku UI: ${state.hero.name} 施展 ${skill.name || "技能"}，造成 ${Math.ceil(damage)} 伤害。`
        : `Sengoku UI: ${state.hero.name} 斩击，造成 ${Math.ceil(damage)} 伤害。`;
    }
    if (enemy.hp <= 0) {
      addLog(`Sengoku UI defeated ${enemy.name}.`);
      ensureBattleUiState(true);
      state.battleUi.text = `Sengoku UI: ${enemy.name} 被击破，战斗循环已重置到下一回合演示。`;
      render();
      return;
    }
    battleUiEnemyTurn();
    if (state.hero.hp <= 0) {
      state.hero.hp = Math.ceil(state.hero.maxHp * 0.35);
      battle.text += ` ${state.hero.name} 倒下后以 ${state.hero.hp} HP 回到地图流程。`;
    }
    render();
  }

  function battleUiEnemyTurn() {
    const battle = state.battleUi;
    const enemy = battle.enemy;
    const action = enemy.pattern[(battle.turn - 1) % enemy.pattern.length] || "attack";
    if (action === "guard") {
      battle.enemyGuard = true;
      battle.enemyFocus = clamp(battle.enemyFocus + 1, 0, 3);
      battle.text += ` ${enemy.name} 防御。`;
    } else {
      const enemySkill = action === "skill" ? enemySkillFor(enemy) : null;
      const power = Number((enemySkill && enemySkill.power) || (action === "skill" ? 3 : 0));
      const damage = battleDamage(enemy.attack, state.hero.defense, power, battle.heroGuard);
      state.hero.hp -= damage;
      battle.enemyFocus = clamp(battle.enemyFocus + (action === "skill" ? 0 : 1), 0, 3);
      battle.text += enemySkill
        ? ` ${enemy.name} 使出 ${enemySkill.name || "技能"}，全局 HP 减少 ${Math.ceil(damage)}。`
        : ` ${enemy.name} 反击，全局 HP 减少 ${Math.ceil(damage)}。`;
    }
    battle.turn += 1;
  }

  function battleAction(action) {
    if (!state.battle) return;
    const enemy = state.battle.enemy;
    if (action === "flee") {
      if (elements.battleUiShowcase) {
        elements.battleUiShowcase.classList.add("hidden");
        elements.battleUiShowcase.classList.remove("battle-ui-real");
        delete elements.battleUiShowcase.dataset.mode;
        clearRealBattleBounds();
      }
      state.battle = null;
      addLog("Fled from battle.");
      playSfx("sfx.battle.flee");
      queueFloat("Fled", "hit");
      render();
      return;
    }
    state.battle.heroGuard = false;
    state.battle.enemyGuard = false;
    if (action === "item") {
      const rationId = "item.steam_bun";
      playSfx("sfx.battle.item");
      if (Number(state.inventory[rationId] || 0) > 0) {
        state.inventory[rationId] -= 1;
        const heal = Math.ceil(state.hero.maxHp * 0.32);
        state.hero.hp = clamp(state.hero.hp + heal, 0, state.hero.maxHp);
        state.battle.heroFocus = clamp(state.battle.heroFocus + 1, 0, 3);
        state.battle.text = `使用热馍，恢复 ${heal} HP，并稳住气势。`;
        state.battle.damageText = `+${heal}`;
      } else {
        state.battle.text = "没有热馍可用，只能咬牙防守。";
        state.battle.heroGuard = true;
        state.battle.heroFocus = clamp(state.battle.heroFocus + 1, 0, 3);
      }
    } else if (action === "guard") {
      playSfx("sfx.battle.guard");
      state.battle.heroGuard = true;
      state.battle.heroFocus = clamp(state.battle.heroFocus + 1, 0, 3);
      state.battle.text = `${state.hero.name} 架势下沉，准备承受下一击。`;
    } else {
      const skill = action === "skill" ? activeHeroSkill() : null;
      const cost = Number((skill && skill.focus_cost) || 0);
      if (skill && state.battle.heroFocus < cost) {
        playSfx("sfx.ui.error");
        state.battle.text = `气势不足，无法施展 ${skill.name || skill.id}。`;
        render();
        return;
      }
      playSfx(skill ? "sfx.battle.skill" : "sfx.battle.attack");
      if (skill) state.battle.heroFocus = clamp(state.battle.heroFocus - cost, 0, 3);
      const power = Number((skill && skill.power) || 0);
      const damage = battleDamage(state.hero.attack, enemy.defense, power, state.battle.enemyGuard);
      enemy.hp -= damage;
      state.battle.heroFocus = clamp(state.battle.heroFocus + (skill ? 0 : 1), 0, 3);
      state.battle.text = skill
        ? `${state.hero.name} 施展 ${skill.name || "技能"}，造成 ${Math.ceil(damage)} 伤害。`
        : `${state.hero.name} 发动斩击，造成 ${Math.ceil(damage)} 伤害。`;
      state.battle.damageText = `-${Math.ceil(damage)}`;
      state.battle.hitFlash = true;
    }
    if (enemy.hp <= 0) {
      winBattle();
      return;
    }
    enemyTurn();
    if (state.hero.hp <= 0) {
      state.hero.hp = Math.ceil(state.hero.maxHp * 0.35);
      if (elements.battleUiShowcase) {
        elements.battleUiShowcase.classList.add("hidden");
        elements.battleUiShowcase.classList.remove("battle-ui-real");
        delete elements.battleUiShowcase.dataset.mode;
        clearRealBattleBounds();
      }
      state.battle = null;
      addLog("Defeated, then recovered at low HP.");
      playSfx("sfx.battle.defeat");
      queueFloat("Recovered", "hit");
    }
    render();
  }

  function renderBattleStats() {
    const battle = state.battle;
    const enemy = battle.enemy;
    elements.heroStats.innerHTML = battleStatusBlock(state.hero.name, state.hero.hp, state.hero.maxHp, battle.heroFocus, battle.heroGuard);
    elements.enemyStats.innerHTML = battleStatusBlock(enemy.name, enemy.hp, enemy.maxHp, battle.enemyFocus, battle.enemyGuard);
  }

  function battleStatusBlock(name, hp, max, focus, guarding) {
    const ratio = clamp(hp / max, 0, 1) * 100;
    return `
      <strong>${escapeHtml(name)}</strong>
      <div>HP ${Math.ceil(hp)} / ${Math.ceil(max)}${guarding ? " · Guard" : ""}</div>
      <div class="battle-hp"><span style="width:${ratio}%"></span></div>
      <div class="battle-focus">${"●".repeat(focus)}${"○".repeat(3 - focus)}</div>
    `;
  }

  function renderBattleActions() {
    if (!elements.battleActions || !state.battle) return;
    const skill = activeHeroSkill();
    const skillLabel = skill ? `${skill.name || "Skill"} (${Number(skill.focus_cost || 0)}气)` : "Skill";
    const rationCount = Number(state.inventory["item.steam_bun"] || 0);
    const actions = [
      ["attack", "斩击"],
      ["skill", skillLabel],
      ["guard", "防御"],
      ["item", `热馍 x${rationCount}`],
      ["flee", "撤退"],
    ];
    elements.battleActions.innerHTML = actions.map(([id, label]) => (
      `<button data-action="${id}" type="button">${escapeHtml(label)}</button>`
    )).join("");
  }

  function activeHeroSkill() {
    const ids = Array.isArray(state.hero.skills) ? state.hero.skills : [];
    return ids.map((id) => skills[id]).find(Boolean) || null;
  }

  function enemyTurn() {
    const battle = state.battle;
    const enemy = battle.enemy;
    const action = enemy.pattern[(battle.turn - 1) % enemy.pattern.length] || "attack";
    if (action === "guard") {
      battle.enemyGuard = true;
      battle.enemyFocus = clamp(battle.enemyFocus + 1, 0, 3);
      battle.text += ` ${enemy.name} 收势防御。`;
    } else {
      const enemySkill = action === "skill" ? enemySkillFor(enemy) : null;
      const power = Number((enemySkill && enemySkill.power) || (action === "skill" ? 3 : 0));
      const damage = battleDamage(enemy.attack, state.hero.defense, power, battle.heroGuard);
      state.hero.hp -= damage;
      playSfx("sfx.battle.enemy_hit");
      battle.enemyFocus = clamp(battle.enemyFocus + (action === "skill" ? 0 : 1), 0, 3);
      battle.text += enemySkill
        ? ` ${enemy.name} 使出 ${enemySkill.name || "妖术"}，造成 ${Math.ceil(damage)} 伤害。`
        : ` ${enemy.name} 反击，造成 ${Math.ceil(damage)} 伤害。`;
      battle.lastAction = "enemy-hit";
    }
    battle.turn += 1;
  }

  function enemySkillFor(enemy) {
    const ids = Array.isArray(enemy.skills) ? enemy.skills : [];
    return ids.map((id) => skills[id]).find(Boolean) || null;
  }

  function battleDamage(attack, defense, power, guarded) {
    const guardScale = guarded ? 0.52 : 1;
    const momentum = state.battle ? 1 + Math.min(0.18, state.battle.turn * 0.015) : 1;
    return Math.max(1, (Number(attack) + Number(power) - Number(defense) * 0.55) * guardScale * momentum);
  }

  function winBattle() {
    const event = state.battle.event;
    addLog(`Won against ${state.battle.enemy.name}.`);
    playSfx("sfx.battle.victory", 0.86);
    queueFloat("Victory", "good");
    if (event.quest_id) {
      state.quests[event.quest_id] = "complete";
      queueFloat(`${quests[event.quest_id] ? quests[event.quest_id].title || event.quest_id : event.quest_id}: complete`, "good");
    }
    if (event.once !== false) {
      state.flags[`event_done:${event.id}`] = true;
    }
    if (event.reward_item_id) {
      state.inventory[event.reward_item_id] = (state.inventory[event.reward_item_id] || 0) + 1;
      addLog(`Got ${event.reward_item_id}.`);
      queueFloat(`+ ${event.reward_item_id}`, "good");
    }
    applyOutcome(weightedPick(event.win_outcomes), event);
    if (elements.battleUiShowcase) {
      elements.battleUiShowcase.classList.add("hidden");
      elements.battleUiShowcase.classList.remove("battle-ui-real");
      delete elements.battleUiShowcase.dataset.mode;
      clearRealBattleBounds();
    }
    state.battle = null;
    checkCompletion();
    render();
  }

  function finalQuestId() {
    if (data.campaign && typeof data.campaign.final_quest_id === "string") return data.campaign.final_quest_id;
    if (typeof data.final_quest_id === "string") return data.final_quest_id;
    const major = data.campaign && Array.isArray(data.campaign.major_quest_ids) ? data.campaign.major_quest_ids : [];
    if (major.length) return major[major.length - 1];
    const questList = Array.isArray(data.quests) ? data.quests : [];
    return questList.length ? questList[questList.length - 1].id : null;
  }

  function completionReached() {
    if (state.flags.ending_ready) return true;
    const finalId = finalQuestId();
    if (finalId) return state.quests[finalId] === "complete";
    const questIds = Object.keys(quests);
    return questIds.length > 0 && questIds.every((id) => state.quests[id] === "complete");
  }

  function checkCompletion() {
    if (state.completed || !completionReached()) return;
    state.completed = true;
    addLog("Road opened.");
    queueFloat("Quest Complete", "good");
  }

  function renderEnding() {
    if (!state.completed || state.endingDismissed || state.dialogue || state.battle) {
      elements.ending.classList.add("hidden");
      return;
    }
    const campaign = data.campaign || {};
    const ending = resolveEnding();
    elements.endingTitle.textContent = ending.title || campaign.ending_title || "Quest Complete";
    elements.endingText.textContent = ending.text || campaign.ending_text || "The final objective is complete. The road ahead is open.";
    elements.ending.classList.remove("hidden");
  }

  function resolveEnding() {
    const endings = Array.isArray(data.campaign && data.campaign.endings) ? data.campaign.endings : [];
    for (const ending of endings) {
      if (conditionPasses(ending.conditions)) return ending;
      if (ending.id && state.flags[`ending:${ending.id}`]) return ending;
    }
    return {
      id: "default",
      title: data.campaign && data.campaign.ending_title,
      text: data.campaign && data.campaign.ending_text,
    };
  }

  function save() {
    const { keys, frameRequest, worldEl, avatarEl, ...serializable } = state;
    localStorage.setItem("web-rpg-save", JSON.stringify({ ...serializable, effects: [] }));
    addLog("Saved.");
    render();
  }

  function load() {
    const raw = localStorage.getItem("web-rpg-save");
    if (!raw) {
      addLog("No save found.");
      render();
      return;
    }
    try {
      const loaded = JSON.parse(raw);
      Object.assign(state, loaded, { effects: [], keys: new Set(), frameRequest: state.frameRequest, worldEl: null, avatarEl: null });
      checkCompletion();
      addLog("Loaded.");
    } catch (error) {
      addLog(`Load failed: ${error.message}`);
    }
    render();
  }

  document.addEventListener("keydown", (event) => {
    const key = event.key.toLowerCase();
    if (["arrowup", "arrowright", "arrowdown", "arrowleft", "w", "a", "s", "d"].includes(key)) {
      state.keys.add(key);
    } else if (event.key === " " || event.key === "Enter") {
      if (state.dialogue) nextDialogue();
      else interact();
    } else {
      return;
    }
    event.preventDefault();
  });

  document.addEventListener("keyup", (event) => {
    state.keys.delete(event.key.toLowerCase());
  });
  window.addEventListener("blur", clearControlKeys);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) clearControlKeys();
  });
  document.addEventListener("pointerdown", resumePendingAudio, true);
  document.addEventListener("keydown", resumePendingAudio, true);
  setupInputSurface();

  elements.dialogueNext.addEventListener("click", nextDialogue);
  elements.endingClose.addEventListener("click", () => {
    state.endingDismissed = true;
    render();
  });
  if (elements.boundaryBtn) {
    elements.boundaryBtn.addEventListener("click", () => {
      state.showBoundaries = !state.showBoundaries;
      render();
    });
  }
  if (elements.battleUiBtn) {
    elements.battleUiBtn.addEventListener("click", openBattleUiShowcase);
  }
  if (elements.battleUiFlow) {
    elements.battleUiFlow.addEventListener("click", (event) => {
      const button = event.target.closest("[data-battle-ui-entry]");
      if (!button) return;
      selectEntry(button.dataset.battleUiEntry);
      ensureBattleUiState(true);
      if (elements.battleUiShowcase) {
        elements.battleUiShowcase.dataset.mode = "demo";
        elements.battleUiShowcase.classList.remove("battle-ui-real");
        clearRealBattleBounds();
        elements.battleUiShowcase.classList.remove("hidden");
      }
      render();
    });
  }
  if (elements.battleUiActions) {
    elements.battleUiActions.addEventListener("click", (event) => {
      const button = event.target.closest("[data-battle-ui-action]");
      if (button) battleUiAction(button.dataset.battleUiAction);
    });
  }
  if (elements.battleUiReset) {
    elements.battleUiReset.addEventListener("click", () => {
      ensureBattleUiState(true);
      render();
    });
  }
  if (elements.battleUiClose) {
    elements.battleUiClose.addEventListener("click", closeBattleUiShowcase);
  }
  elements.saveBtn.addEventListener("click", save);
  elements.loadBtn.addEventListener("click", load);
  if (elements.battleActions) {
    elements.battleActions.addEventListener("click", (event) => {
      const button = event.target.closest("[data-action]");
      if (button) battleAction(button.dataset.action);
    });
  }
  if (elements.entryOptions) {
    elements.entryOptions.addEventListener("click", (event) => {
      const button = event.target.closest("[data-entry-id]");
      if (button) selectEntry(button.dataset.entryId);
    });
  }

  window.addEventListener("resize", render);
  window.addEventListener("scroll", () => {
    if (state.battle && elements.battleUiShowcase && elements.battleUiShowcase.dataset.mode === "real") {
      syncRealBattleBounds();
    }
  }, { passive: true });
  addLog("Game loaded.");
  render();
  startLoop();
}());
