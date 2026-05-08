(function () {
  "use strict";

  const DEFAULT_TILE = 48;
  const MOVE_MS = 150;
  const data = window.RPG_GAME_DATA || {};

  const byId = (items) => {
    const result = {};
    (Array.isArray(items) ? items : []).forEach((item) => {
      if (item && typeof item.id === "string") result[item.id] = item;
    });
    return result;
  };

  const maps = byId(data.maps);
  const actors = byId(data.actors);
  const enemies = byId(data.enemies);
  const encounters = byId(data.encounter_tables);
  const quests = byId(data.quests);
  const dialogues = byId(data.npc_dialogue);
  const items = byId(data.items);
  const restPoints = byId(data.rest_points);
  const shops = byId(data.shops);
  const keys = {};
  const images = {};

  const fallbackMap = {
    id: "map.start",
    title: "Start",
    width: 10,
    height: 8,
    layers: {
      ground: Array.from({ length: 8 }, () => Array.from({ length: 10 }, () => "grass")),
      collision: Array.from({ length: 8 }, (_, y) => Array.from({ length: 10 }, (_, x) => (x === 0 || y === 0 || x === 9 || y === 7 ? 1 : 0)))
    },
    events: [
      { id: "npc.guide", type: "npc", x: 3, y: 3, name: "Guide", lines: ["This RPG export is running."] },
      { id: "rest.camp", type: "rest", x: 6, y: 4, name: "Camp" }
    ]
  };
  if (!Object.keys(maps).length) maps[fallbackMap.id] = fallbackMap;

  const firstMapId = data.start_map_id && maps[data.start_map_id] ? data.start_map_id : Object.keys(maps)[0];
  const partyIds = (Array.isArray(data.party) ? data.party : []).filter((id) => actors[id]);
  const firstActor = actors[partyIds[0]] || Object.values(actors)[0] || {
    id: "actor.hero",
    name: "Hero",
    stats: { hp: 30, attack: 8, defense: 2, speed: 3 }
  };

  const maxHp = (entity) => Number((entity.stats && (entity.stats.max_hp || entity.stats.hp)) || entity.max_hp || entity.hp || 1);
  const stat = (entity, key, fallback) => Number((entity.stats && entity.stats[key]) || entity[key] || fallback);
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const slug = (value) => String(value || "").split(".").pop().split("_")[0].replace(/[^A-Za-z0-9-]/g, "_");

  const state = {
    mapId: firstMapId,
    x: Number((data.start_position && data.start_position.x) || 1),
    y: Number((data.start_position && data.start_position.y) || 1),
    px: null,
    py: null,
    facing: "down",
    moving: false,
    moveStart: 0,
    fromPx: 0,
    fromPy: 0,
    toPx: 0,
    toPy: 0,
    targetX: 0,
    targetY: 0,
    pendingTouch: false,
    lastBlockedAt: 0,
    effects: [],
    hero: {
      id: firstActor.id,
      name: firstActor.name || firstActor.display_name || firstActor.id,
      hp: maxHp(firstActor),
      maxHp: maxHp(firstActor),
      attack: stat(firstActor, "attack", 8),
      defense: stat(firstActor, "defense", 1),
      speed: stat(firstActor, "speed", 3),
      spriteAssetId: firstActor.sprite_asset_id || firstActor.spriteAssetId || firstActor.asset_id || `sprite.${slug(firstActor.id)}`
    },
    flags: {},
    inventory: {},
    quests: {},
    log: [],
    dialogue: null,
    battle: null,
    completed: false,
    endingDismissed: false
  };

  const view = {
    mapId: null,
    canvas: null,
    ctx: null,
    hint: null,
    propCacheMapId: null,
    propCache: [],
    animationStarted: false
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
    heroStats: document.getElementById("heroStats"),
    enemyStats: document.getElementById("enemyStats"),
    ending: document.getElementById("ending"),
    endingTitle: document.getElementById("endingTitle"),
    endingText: document.getElementById("endingText"),
    endingClose: document.getElementById("endingClose"),
    saveBtn: document.getElementById("saveBtn"),
    loadBtn: document.getElementById("loadBtn")
  };

  function currentMap() {
    return maps[state.mapId] || maps[Object.keys(maps)[0]] || fallbackMap;
  }

  function sceneFor(gameMap) {
    return gameMap && gameMap.scene && typeof gameMap.scene === "object" ? gameMap.scene : {};
  }

  function tileSize(gameMap) {
    const tile = Number(sceneFor(gameMap).tile || DEFAULT_TILE);
    return Number.isFinite(tile) && tile >= 16 ? tile : DEFAULT_TILE;
  }

  function assetPath(assetId) {
    return assetId && data.assets && data.assets[assetId] ? data.assets[assetId] : "";
  }

  function firstAssetWithPrefix(prefix) {
    const refs = Array.isArray(data.asset_refs) ? data.asset_refs : [];
    return refs.find((assetId) => typeof assetId === "string" && assetId.startsWith(prefix));
  }

  function runtimeImage(assetId) {
    const path = assetPath(assetId);
    if (!path) return null;
    if (!images[assetId]) {
      const img = new Image();
      images[assetId] = { img, loaded: false, failed: false };
      img.onload = () => { images[assetId].loaded = true; };
      img.onerror = () => { images[assetId].failed = true; };
      img.src = path;
    }
    return images[assetId].loaded ? images[assetId].img : null;
  }

  function assetBounds(assetId, img) {
    const bounds = data.asset_bounds && data.asset_bounds[assetId];
    if (bounds && Number(bounds.sw) > 0 && Number(bounds.sh) > 0) {
      return {
        sx: Number(bounds.sx) || 0,
        sy: Number(bounds.sy) || 0,
        sw: Number(bounds.sw),
        sh: Number(bounds.sh)
      };
    }
    return { sx: 0, sy: 0, sw: img.width, sh: img.height };
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

  function tileAt(gameMap, x, y, layer, fallback) {
    const rows = gameMap.layers && Array.isArray(gameMap.layers[layer]) ? gameMap.layers[layer] : [];
    return rows[y] && rows[y][x] !== undefined ? rows[y][x] : fallback;
  }

  function isBlocked(gameMap, x, y) {
    if (x < 0 || y < 0 || x >= gameMap.width || y >= gameMap.height) return true;
    return Number(tileAt(gameMap, x, y, "collision", 0)) > 0;
  }

  function eventsAt(gameMap, x, y) {
    return (Array.isArray(gameMap.events) ? gameMap.events : []).filter((event) => event.x === x && event.y === y && !state.flags[`event_done:${event.id}`]);
  }

  function facingTile() {
    const delta = { down: [0, 1], up: [0, -1], left: [-1, 0], right: [1, 0] }[state.facing] || [0, 1];
    return [state.x + delta[0], state.y + delta[1]];
  }

  function rectContains(rect, x, y) {
    return x >= Number(rect.x) && y >= Number(rect.y) && x < Number(rect.x) + Number(rect.w || 1) && y < Number(rect.y) + Number(rect.h || 1);
  }

  function currentTouchEvent() {
    const gameMap = currentMap();
    return eventsAt(gameMap, state.x, state.y).find((event) => event.trigger === "touch" || event.type === "transfer") || null;
  }

  function facingEvent() {
    const gameMap = currentMap();
    const [tx, ty] = facingTile();
    return eventsAt(gameMap, tx, ty)[0] || null;
  }

  function nearbyEventFallback() {
    const gameMap = currentMap();
    const points = [
      [state.x, state.y],
      [state.x, state.y - 1],
      [state.x + 1, state.y],
      [state.x, state.y + 1],
      [state.x - 1, state.y]
    ];
    for (const point of points) {
      const event = eventsAt(gameMap, point[0], point[1])[0];
      if (event) return event;
    }
    return null;
  }

  function sceneProps(gameMap) {
    if (view.propCacheMapId === gameMap.id) return view.propCache;
    const scene = sceneFor(gameMap);
    if (Array.isArray(scene.props) && scene.props.length) {
      view.propCache = scene.props.map((prop, index) => ({
        ...prop,
        id: prop.id || `scene.prop.${index + 1}`,
        w: Number(prop.w || 1),
        h: Number(prop.h || 1),
        x: Number(prop.x || 0),
        y: Number(prop.y || 0)
      }));
    } else {
      view.propCache = layerProps(gameMap);
    }
    view.propCacheMapId = gameMap.id;
    return view.propCache;
  }

  function layerProps(gameMap) {
    const props = [];
    const layers = gameMap.layers || {};
    ["objects", "overlay"].forEach((layerName) => {
      const rows = Array.isArray(layers[layerName]) ? layers[layerName] : [];
      rows.forEach((row, y) => {
        if (!Array.isArray(row)) return;
        row.forEach((token, x) => {
          const value = String(token || "");
          if (!value || value === "." || value === "0") return;
          props.push({
            id: `layer.${layerName}.${x}.${y}`,
            asset_id: decorationAssetId(value),
            asset: value.replace(/^mapprop\./, ""),
            x,
            y,
            w: 1,
            h: 1,
            blocking: false,
            layer: layerName === "overlay" ? "overlay" : "object"
          });
        });
      });
    });
    return props;
  }

  function facingProp() {
    const gameMap = currentMap();
    const [tx, ty] = facingTile();
    const candidates = sceneProps(gameMap).filter((prop) => {
      const done = prop.event_id && state.flags[`event_done:${prop.event_id}`];
      const canInteract = prop.interaction || prop.lines || prop.item_id || prop.event_id;
      return !done && canInteract && rectContains(prop, tx, ty);
    });
    candidates.sort((a, b) => (Number(b.y) + Number(b.h || 1)) - (Number(a.y) + Number(a.h || 1)));
    return candidates[0] ? { ...candidates[0], __sceneProp: true } : null;
  }

  function interactionTarget() {
    return currentTouchEvent() || facingEvent() || facingProp() || nearbyEventFallback();
  }

  function ensureCanvas(gameMap) {
    const tile = tileSize(gameMap);
    const width = gameMap.width * tile;
    const height = gameMap.height * tile;
    if (view.mapId === gameMap.id && view.canvas) return;
    elements.map.innerHTML = "";
    const canvas = document.createElement("canvas");
    canvas.className = "scene-canvas";
    canvas.width = width;
    canvas.height = height;
    canvas.setAttribute("aria-label", gameMap.title || gameMap.id || "RPG map");
    const hint = document.createElement("div");
    hint.className = "interaction-hint";
    elements.map.appendChild(canvas);
    elements.map.appendChild(hint);
    view.mapId = gameMap.id;
    view.canvas = canvas;
    view.ctx = canvas.getContext("2d");
    view.hint = hint;
    view.propCacheMapId = null;
    syncPixelPosition();
  }

  function syncPixelPosition() {
    const tile = tileSize(currentMap());
    state.px = state.x * tile;
    state.py = state.y * tile;
    state.fromPx = state.px;
    state.fromPy = state.py;
    state.toPx = state.px;
    state.toPy = state.py;
    state.targetX = state.x;
    state.targetY = state.y;
  }

  function render() {
    const gameMap = currentMap();
    elements.title.textContent = data.title || "Playable Web RPG";
    elements.location.textContent = gameMap.title || gameMap.id;
    ensureCanvas(gameMap);
    renderInteractionHint();
    flushFloatingText();
    renderPanel();
    renderDialogue();
    renderBattle();
    renderEnding();
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

  function decorationAssetId(token) {
    const value = String(token || "");
    if (!value || value === "." || value === "0") return null;
    if (value.startsWith("mapprop.")) return value;
    return `mapprop.${value}`;
  }

  function propAssetId(prop) {
    if (typeof prop.asset_id === "string") return prop.asset_id;
    return decorationAssetId(prop.asset);
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
    if (event.__sceneProp) return event.name || event.asset || "Inspect";
    if (event.quest_id && quests[event.quest_id]) return quests[event.quest_id].title || event.name || event.quest_id;
    if (event.item_id && items[event.item_id]) return items[event.item_id].name || event.name || event.item_id;
    return event.name || event.title || event.id || "Interact";
  }

  function renderInteractionHint() {
    if (!view.hint) return;
    const target = interactionTarget();
    view.hint.textContent = target ? `Space / Enter: ${eventLabel(target)}` : "Face something to interact";
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
    elements.party.innerHTML = `
      <section class="panel-section">
        <h2>${escapeHtml(state.hero.name)}</h2>
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

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
      "'": "&#39;"
    }[char]));
  }

  function tryMove(dx, dy, facing) {
    if (state.dialogue || state.battle || state.moving) return;
    state.facing = facing;
    const now = performance.now();
    const gameMap = currentMap();
    const nx = state.x + dx;
    const ny = state.y + dy;
    if (isBlocked(gameMap, nx, ny)) {
      if (now - state.lastBlockedAt > 260) {
        queueFloat("Blocked", "hit");
        flashMap("hit");
        render();
        state.lastBlockedAt = now;
      }
      return;
    }
    const tile = tileSize(gameMap);
    state.fromPx = state.px;
    state.fromPy = state.py;
    state.toPx = nx * tile;
    state.toPy = ny * tile;
    state.targetX = nx;
    state.targetY = ny;
    state.x = nx;
    state.y = ny;
    state.moveStart = now;
    state.moving = true;
    state.pendingTouch = true;
  }

  function pollMove() {
    if (keys.arrowup || keys.w) tryMove(0, -1, "up");
    else if (keys.arrowright || keys.d) tryMove(1, 0, "right");
    else if (keys.arrowdown || keys.s) tryMove(0, 1, "down");
    else if (keys.arrowleft || keys.a) tryMove(-1, 0, "left");
  }

  function tryMoveForKey(key) {
    if (key === "arrowup" || key === "w") return tryMove(0, -1, "up");
    if (key === "arrowright" || key === "d") return tryMove(1, 0, "right");
    if (key === "arrowdown" || key === "s") return tryMove(0, 1, "down");
    if (key === "arrowleft" || key === "a") return tryMove(-1, 0, "left");
    return null;
  }

  function updateMovement(now) {
    if (state.px === null || state.py === null) syncPixelPosition();
    if (state.dialogue || state.battle) return;
    if (state.moving) {
      const t = (now - state.moveStart) / MOVE_MS;
      if (t >= 1) {
        state.px = state.toPx;
        state.py = state.toPy;
        state.moving = false;
        if (state.pendingTouch) {
          state.pendingTouch = false;
          const event = currentTouchEvent();
          if (event) interact(event);
        }
      } else {
        state.px = state.fromPx + (state.toPx - state.fromPx) * t;
        state.py = state.fromPy + (state.toPy - state.fromPy) * t;
      }
      return;
    }
    pollMove();
  }

  function interact(explicitTarget) {
    const target = explicitTarget || interactionTarget();
    if (!target) {
      queueFloat("Nothing here", "hit");
      render();
      return;
    }
    if (target.__sceneProp) return interactProp(target);
    const type = String(target.type || "npc");
    if (type === "battle" || type === "encounter") return startBattle(target);
    if (type === "rest") return rest(target);
    if (type === "pickup" || type === "item") return pickup(target);
    if (type === "transfer") return transfer(target);
    if (type === "shop") return talk(target, shopLines(target));
    if (type === "quest") return acceptQuest(target);
    talk(target, linesFor(target));
  }

  function interactProp(prop) {
    if (prop.item_id) {
      return pickup({
        id: prop.event_id || prop.id,
        type: "pickup",
        item_id: prop.item_id,
        quantity: prop.quantity || 1,
        name: prop.name
      });
    }
    const lines = Array.isArray(prop.lines) && prop.lines.length ? prop.lines : [prop.interaction || `${prop.name || "It"} has nothing more to say.`];
    return talk({
      id: prop.event_id || prop.id,
      type: "scene_prop",
      name: prop.name || "Inspect",
      asset_id: prop.asset_id,
      once: prop.once,
      complete_quest_id: prop.complete_quest_id
    }, lines);
  }

  function linesFor(event) {
    if (Array.isArray(event.lines)) return event.lines;
    const dialogue = event.dialogue_id ? dialogues[event.dialogue_id] : null;
    if (dialogue && Array.isArray(dialogue.lines)) return dialogue.lines;
    if (dialogue && Array.isArray(dialogue.beats)) return dialogue.beats.map((beat) => beat.text || beat.line || String(beat));
    if (event.quest_id && quests[event.quest_id]) {
      const quest = quests[event.quest_id];
      return [{ speaker: quest.title || event.name || "Quest", text: quest.summary || quest.description || "A new objective is now active." }];
    }
    if (event.item_id && items[event.item_id]) {
      const item = items[event.item_id];
      return [{ speaker: item.name || event.name || "Item", text: item.description || "This may be useful later." }];
    }
    return [`${event.name || "Someone"} has nothing more to say.`];
  }

  function shopLines(event) {
    const shop = event.shop_id ? shops[event.shop_id] : null;
    const wares = shop && Array.isArray(shop.items) ? shop.items.join(", ") : "basic supplies";
    return [`${event.name || "Shop"} offers ${wares}.`, "Trading is represented as dialogue in this MVP runtime."];
  }

  function questExists(questId) {
    return typeof questId === "string" && Boolean(quests[questId]);
  }

  function questLabel(questId) {
    return questExists(questId) ? quests[questId].title || questId : questId;
  }

  function activateQuest(questId) {
    if (!questExists(questId)) return false;
    if (!state.quests[questId]) {
      state.quests[questId] = "active";
      queueFloat(`${questLabel(questId)}: active`, "good");
    }
    return true;
  }

  function completeQuest(questId) {
    if (!questExists(questId)) return false;
    if (state.quests[questId] !== "complete") {
      state.quests[questId] = "complete";
      queueFloat(`${questLabel(questId)}: complete`, "good");
    }
    return true;
  }

  function talk(event, rawLines) {
    const lines = rawLines.map((line) => typeof line === "string" ? { speaker: event.name || "NPC", text: line } : line);
    state.dialogue = { event, lines, index: 0 };
    if (event.quest_id && !state.quests[event.quest_id]) {
      if (event.complete) completeQuest(event.quest_id);
      else activateQuest(event.quest_id);
    }
    render();
  }

  function acceptQuest(event) {
    const questId = event.quest_id || event.id;
    if (event.complete || event.complete_quest_id === questId) completeQuest(questId);
    else activateQuest(questId);
    talk(event, linesFor(event));
    addLog(`${questId} updated.`);
    checkCompletion();
  }

  function nextDialogue() {
    if (!state.dialogue) return;
    state.dialogue.index += 1;
    if (state.dialogue.index >= state.dialogue.lines.length) {
      const event = state.dialogue.event;
      if (event.once) state.flags[`event_done:${event.id}`] = true;
      if (event.complete_quest_id) completeQuest(event.complete_quest_id);
      state.dialogue = null;
      checkCompletion();
    }
    render();
  }

  function renderDialogue() {
    if (!state.dialogue) {
      elements.dialogue.classList.add("hidden");
      return;
    }
    const line = state.dialogue.lines[state.dialogue.index] || {};
    elements.dialogueSpeaker.textContent = line.speaker || state.dialogue.event.name || "NPC";
    elements.dialogueText.textContent = line.text || String(line);
    const portrait = assetPath(eventAssetId(state.dialogue.event));
    elements.dialoguePortrait.innerHTML = portrait ? `<img src="${encodeURI(portrait)}" alt="">` : "";
    elements.dialogue.classList.remove("hidden");
  }

  function rest(event) {
    const restPoint = event.rest_point_id ? restPoints[event.rest_point_id] : null;
    const cost = Number((restPoint && restPoint.cost) || event.cost || 0);
    state.hero.hp = state.hero.maxHp;
    addLog(cost ? `Rested for ${cost}.` : "Rested and recovered.");
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
    queueFloat(`+ ${label}`, "good");
    flashMap("good");
    state.flags[`event_done:${event.id}`] = true;
    render();
  }

  function transfer(event) {
    if (!event.target_map_id || !maps[event.target_map_id]) {
      queueFloat("Exit is not connected", "hit");
      render();
      return;
    }
    if (event.complete_quest_id) completeQuest(event.complete_quest_id);
    if (event.quest_id && event.complete) completeQuest(event.quest_id);
    state.mapId = event.target_map_id;
    state.x = Number(event.target_x || 1);
    state.y = Number(event.target_y || 1);
    state.moving = false;
    state.pendingTouch = false;
    view.mapId = null;
    syncPixelPosition();
    addLog(`Moved to ${maps[state.mapId].title || state.mapId}.`);
    queueFloat(maps[state.mapId].title || state.mapId, "good");
    flashMap("travel");
    checkCompletion();
    render();
  }

  function startBattle(event) {
    const enemyId = resolveEnemyId(event);
    if (!enemyId || !enemies[enemyId]) {
      queueFloat("No enemy configured", "hit");
      render();
      return;
    }
    const source = enemies[enemyId];
    state.battle = {
      event,
      enemy: {
        id: source.id,
        name: source.name || source.id,
        hp: maxHp(source),
        maxHp: maxHp(source),
        attack: stat(source, "attack", 5),
        defense: stat(source, "defense", 0),
        speed: stat(source, "speed", 1),
        spriteAssetId: source.sprite_asset_id || source.asset_id || source.id
      },
      backgroundAssetId: event.battle_background_asset_id || firstAssetWithPrefix("battlebg."),
      text: `${source.name || source.id} appears.`,
      damageText: "",
      hitFlash: false
    };
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

  function renderBattle() {
    if (!state.battle) {
      elements.battle.classList.add("hidden");
      elements.battleVisual.innerHTML = "";
      elements.battleBox.style.backgroundImage = "";
      elements.battleBox.classList.remove("hit-shake");
      return;
    }
    const enemy = state.battle.enemy;
    elements.battleTitle.textContent = `Battle: ${enemy.name}`;
    elements.battleText.textContent = state.battle.text;
    elements.heroStats.textContent = `${state.hero.name}: HP ${Math.ceil(state.hero.hp)} / ${Math.ceil(state.hero.maxHp)}`;
    elements.enemyStats.textContent = `${enemy.name}: HP ${Math.ceil(enemy.hp)} / ${Math.ceil(enemy.maxHp)}`;
    const enemySprite = assetPath(enemy.spriteAssetId);
    elements.battleVisual.className = `battle-visual${state.battle.hitFlash ? " hit-flash" : ""}`;
    elements.battleVisual.innerHTML = enemySprite ? `<img src="${encodeURI(enemySprite)}" alt="">` : "";
    const battleBackground = assetPath(state.battle.backgroundAssetId);
    elements.battleBox.style.backgroundImage = battleBackground ? `linear-gradient(rgba(26,30,25,0.72), rgba(26,30,25,0.9)), url("${encodeURI(battleBackground)}")` : "";
    elements.battleBox.querySelectorAll(".battle-damage").forEach((node) => node.remove());
    elements.battleBox.classList.remove("hit-shake");
    if (state.battle.hitFlash) {
      void elements.battleBox.offsetWidth;
      elements.battleBox.classList.add("hit-shake");
    }
    if (state.battle.damageText) {
      const damage = document.createElement("div");
      damage.className = "battle-damage";
      damage.textContent = state.battle.damageText;
      elements.battleBox.appendChild(damage);
    }
    elements.battle.classList.remove("hidden");
    state.battle.hitFlash = false;
    state.battle.damageText = "";
  }

  function battleAction(action) {
    if (!state.battle) return;
    const enemy = state.battle.enemy;
    if (action === "flee") {
      state.battle = null;
      addLog("Fled from battle.");
      queueFloat("Fled", "hit");
      render();
      return;
    }
    if (action === "item") {
      state.hero.hp = clamp(state.hero.hp + 8, 0, state.hero.maxHp);
      state.battle.text = "Used a field ration and recovered HP.";
      state.battle.damageText = "+8";
    } else {
      const bonus = action === "skill" ? 4 : 0;
      const damage = Math.max(1, state.hero.attack + bonus - enemy.defense * 0.5);
      enemy.hp -= damage;
      state.battle.text = `${state.hero.name} dealt ${Math.ceil(damage)} damage.`;
      state.battle.damageText = `-${Math.ceil(damage)}`;
      state.battle.hitFlash = true;
    }
    if (enemy.hp <= 0) {
      winBattle();
      return;
    }
    const enemyDamage = Math.max(1, enemy.attack - state.hero.defense * 0.5);
    state.hero.hp -= enemyDamage;
    state.battle.text += ` ${enemy.name} dealt ${Math.ceil(enemyDamage)} damage.`;
    if (state.hero.hp <= 0) {
      state.hero.hp = Math.ceil(state.hero.maxHp * 0.35);
      state.battle = null;
      addLog("Defeated, then recovered at low HP.");
      queueFloat("Recovered", "hit");
    }
    render();
  }

  function winBattle() {
    const event = state.battle.event;
    addLog(`Won against ${state.battle.enemy.name}.`);
    queueFloat("Victory", "good");
    if (event.quest_id) {
      completeQuest(event.quest_id);
    }
    if (event.once !== false) state.flags[`event_done:${event.id}`] = true;
    if (event.reward_item_id) {
      state.inventory[event.reward_item_id] = (state.inventory[event.reward_item_id] || 0) + 1;
      addLog(`Got ${event.reward_item_id}.`);
      queueFloat(`+ ${event.reward_item_id}`, "good");
    }
    state.battle = null;
    checkCompletion();
    render();
  }

  function finalQuestId() {
    if (questExists(data.final_quest_id)) return data.final_quest_id;
    if (data.campaign && questExists(data.campaign.final_quest_id)) return data.campaign.final_quest_id;
    const major = data.campaign && Array.isArray(data.campaign.major_quest_ids) ? data.campaign.major_quest_ids : [];
    for (let index = major.length - 1; index >= 0; index -= 1) {
      if (questExists(major[index])) return major[index];
    }
    const questList = Array.isArray(data.quests) ? data.quests : [];
    return questList.length ? questList[questList.length - 1].id : null;
  }

  function completionReached() {
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
    elements.endingTitle.textContent = campaign.ending_title || "Quest Complete";
    elements.endingText.textContent = campaign.ending_text || "The final objective is complete. The road ahead is open.";
    elements.ending.classList.remove("hidden");
  }

  function drawFallbackTile(ctx, ground, x, y, tile) {
    const colors = {
      water: "#426f7c",
      path: "#8c7853",
      bridge: "#725334",
      sand: "#aa966a",
      stone: "#5b635b",
      wood: "#775333",
      floor: "#6d6c5a",
      wall: "#30352f",
      grass: "#4d6b42"
    };
    ctx.fillStyle = colors[ground] || colors.grass;
    ctx.fillRect(x * tile, y * tile, tile, tile);
  }

  function terrainTileCell(ground) {
    return {
      grass: [0, 0],
      path: [1, 0],
      water: [2, 0],
      bridge: [3, 0],
      sand: [0, 1],
      stone: [1, 1],
      wood: [2, 1],
      floor: [3, 1],
      wall: [0, 2]
    }[ground] || [0, 0];
  }

  function tilesetAssetId(gameMap) {
    const scene = sceneFor(gameMap);
    return scene.tileset_asset_id || gameMap.tileset_asset_id || firstAssetWithPrefix("tileset.");
  }

  function terrainAssetId(gameMap, ground) {
    const scene = sceneFor(gameMap);
    const sceneTerrain = scene.terrain_asset_ids || {};
    const mapTerrain = gameMap.terrain_asset_ids || {};
    return sceneTerrain[ground] || mapTerrain[ground] || null;
  }

  function drawTerrainTile(ctx, image, x, y, tile) {
    ctx.drawImage(image, 0, 0, image.width, image.height, x * tile, y * tile, tile, tile);
  }

  function drawTexturedTile(ctx, tileset, ground, x, y, tile) {
    const [cellX, cellY] = terrainTileCell(ground);
    const sourceCols = 4;
    const sourceRows = 3;
    const sourceW = Math.floor(tileset.width / sourceCols);
    const sourceH = Math.floor(tileset.height / sourceRows);
    const sx = Math.min(cellX, sourceCols - 1) * sourceW;
    const sy = Math.min(cellY, sourceRows - 1) * sourceH;
    ctx.drawImage(tileset, sx, sy, sourceW, sourceH, x * tile, y * tile, tile, tile);
  }

  function drawGroundGrid(ctx, gameMap, tile) {
    const scene = sceneFor(gameMap);
    const terrainIds = scene.terrain_asset_ids || gameMap.terrain_asset_ids || null;
    const tileset = terrainIds ? null : runtimeImage(tilesetAssetId(gameMap));
    for (let y = 0; y < gameMap.height; y += 1) {
      for (let x = 0; x < gameMap.width; x += 1) {
        const ground = String(tileAt(gameMap, x, y, "ground", "grass"));
        const terrainImage = runtimeImage(terrainAssetId(gameMap, ground));
        if (terrainImage) drawTerrainTile(ctx, terrainImage, x, y, tile);
        else if (tileset) drawTexturedTile(ctx, tileset, ground, x, y, tile);
        else drawFallbackTile(ctx, ground, x, y, tile);
      }
    }
  }

  function drawCollisionOverlay(ctx, gameMap, tile) {
    const scene = sceneFor(gameMap);
    if (scene.terrain_asset_ids || gameMap.terrain_asset_ids || runtimeImage(tilesetAssetId(gameMap))) return;
    ctx.fillStyle = "rgba(28, 31, 27, 0.45)";
    for (let y = 0; y < gameMap.height; y += 1) {
      for (let x = 0; x < gameMap.width; x += 1) {
        const ground = String(tileAt(gameMap, x, y, "ground", ""));
        if (isBlocked(gameMap, x, y) && ground !== "water") {
          ctx.fillRect(x * tile, y * tile, tile, tile);
        }
      }
    }
  }

  function drawMapBase(ctx, gameMap, tile) {
    const worldW = gameMap.width * tile;
    const worldH = gameMap.height * tile;
    ctx.fillStyle = "#0e0c0a";
    ctx.fillRect(0, 0, worldW, worldH);
    const hasGround = gameMap.layers && Array.isArray(gameMap.layers.ground);
    if (hasGround) {
      drawGroundGrid(ctx, gameMap, tile);
      drawCollisionOverlay(ctx, gameMap, tile);
      return;
    }
    const scene = sceneFor(gameMap);
    const mapAssetId = scene.map_asset_id || gameMap.map_asset_id || gameMap.asset_id || gameMap.id;
    const mapImage = runtimeImage(mapAssetId);
    if (mapImage) {
      ctx.drawImage(mapImage, 0, 0, mapImage.width, mapImage.height, 0, 0, worldW, worldH);
      return;
    }
    for (let y = 0; y < gameMap.height; y += 1) {
      for (let x = 0; x < gameMap.width; x += 1) {
        drawFallbackTile(ctx, String(tileAt(gameMap, x, y, "ground", "grass")), x, y, tile);
      }
    }
  }

  function drawBoundedImage(ctx, img, bounds, dx, dy, dw, dh) {
    ctx.drawImage(img, bounds.sx, bounds.sy, bounds.sw, bounds.sh, dx, dy, dw, dh);
  }

  function drawProp(ctx, prop, tile) {
    const assetId = propAssetId(prop);
    const img = runtimeImage(assetId);
    const boxW = Number(prop.w || 1) * tile;
    const boxH = Number(prop.h || 1) * tile;
    if (!img) {
      ctx.fillStyle = "rgba(20, 24, 20, 0.58)";
      ctx.fillRect(Number(prop.x) * tile + boxW * 0.2, Number(prop.y) * tile + boxH * 0.2, boxW * 0.6, boxH * 0.6);
      return;
    }
    const bounds = assetBounds(assetId, img);
    const scale = Math.min(boxW / bounds.sw, boxH / bounds.sh) * Number(prop.render_scale || 1);
    const dw = bounds.sw * scale;
    const dh = bounds.sh * scale;
    const dx = Number(prop.x) * tile + (boxW - dw) / 2;
    const dy = Number(prop.y) * tile + (prop.layer === "floor_decor" ? (boxH - dh) / 2 : boxH - dh);
    drawBoundedImage(ctx, img, bounds, dx, dy, dw, dh);
  }

  function drawEvent(ctx, event, tile, focused) {
    const assetId = eventAssetId(event);
    const img = runtimeImage(assetId);
    const cx = (Number(event.x) + 0.5) * tile;
    const footY = (Number(event.y) + 0.88) * tile;
    if (img) {
      const bounds = assetBounds(assetId, img);
      const scale = Math.min((tile * 1.32) / bounds.sw, (tile * 1.56) / bounds.sh);
      const dw = bounds.sw * scale;
      const dh = bounds.sh * scale;
      drawBoundedImage(ctx, img, bounds, cx - dw / 2, footY - dh, dw, dh);
    } else {
      ctx.beginPath();
      ctx.fillStyle = markerFill(event);
      ctx.strokeStyle = focused ? "#f7dfa0" : "rgba(255,255,255,0.62)";
      ctx.lineWidth = 2;
      ctx.arc(cx, footY - tile * 0.42, tile * 0.26, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "#151713";
      ctx.font = `700 ${Math.max(13, tile * 0.28)}px system-ui`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(markerText(String(event.type || "npc")), cx, footY - tile * 0.42);
    }
    if (focused) {
      ctx.strokeStyle = "rgba(247, 223, 160, 0.92)";
      ctx.lineWidth = 3;
      ctx.strokeRect((Number(event.x) + 0.12) * tile, (Number(event.y) + 0.12) * tile, tile * 0.76, tile * 0.76);
    }
  }

  function markerFill(event) {
    const cls = markerClass(event);
    return {
      "battle-event": "#d96f62",
      "rest-event": "#7eb47a",
      "item-event": "#d7cd7c",
      "quest-event": "#d7cd7c",
      "shop-event": "#d7cd7c",
      "transfer-event": "#d7cd7c",
      npc: "#86a6d8"
    }[cls] || "#86a6d8";
  }

  function drawAvatar(ctx, tile) {
    const img = runtimeImage(state.hero.spriteAssetId);
    const cx = state.px + tile * 0.5;
    const footY = state.py + tile * 0.94;
    if (!img) {
      ctx.beginPath();
      ctx.fillStyle = "#e0b85e";
      ctx.arc(cx, footY - tile * 0.42, tile * 0.28, 0, Math.PI * 2);
      ctx.fill();
      return;
    }
    if (img.width >= 512 && Math.abs(img.width - img.height) < 4) {
      const cells = { down: [0, 0], left: [1, 0], right: [0, 1], up: [1, 1] };
      const cell = cells[state.facing] || cells.down;
      const cellW = Math.floor(img.width / 2);
      const cellH = Math.floor(img.height / 2);
      const ew = tile * 1.2;
      const eh = tile * 1.55;
      ctx.drawImage(img, cell[0] * cellW, cell[1] * cellH, cellW, cellH, cx - ew / 2, footY - eh, ew, eh);
      return;
    }
    const bounds = assetBounds(state.hero.spriteAssetId, img);
    const scale = Math.min((tile * 1.28) / bounds.sw, (tile * 1.72) / bounds.sh);
    const dw = bounds.sw * scale;
    const dh = bounds.sh * scale;
    ctx.save();
    if (state.facing === "left") {
      ctx.translate(cx, 0);
      ctx.scale(-1, 1);
      drawBoundedImage(ctx, img, bounds, -dw / 2, footY - dh, dw, dh);
    } else {
      drawBoundedImage(ctx, img, bounds, cx - dw / 2, footY - dh, dw, dh);
    }
    ctx.restore();
  }

  function drawScene(now) {
    const gameMap = currentMap();
    ensureCanvas(gameMap);
    updateMovement(now);
    renderInteractionHint();
    const ctx = view.ctx;
    const tile = tileSize(gameMap);
    if (!ctx) return;
    ctx.imageSmoothingEnabled = false;
    drawMapBase(ctx, gameMap, tile);
    const focused = interactionTarget();
    const drawables = [];
    sceneProps(gameMap).forEach((prop) => {
      if (prop.layer === "floor_decor") drawProp(ctx, prop, tile);
      else drawables.push({ y: Number(prop.y) + Number(prop.h || 1), draw: () => drawProp(ctx, prop, tile) });
    });
    (Array.isArray(gameMap.events) ? gameMap.events : []).forEach((event) => {
      if (state.flags[`event_done:${event.id}`]) return;
      drawables.push({ y: Number(event.y) + 0.86, draw: () => drawEvent(ctx, event, tile, focused && focused.id === event.id) });
    });
    drawables.push({ y: (state.py / tile) + 0.9, draw: () => drawAvatar(ctx, tile) });
    drawables.sort((a, b) => a.y - b.y);
    drawables.forEach((item) => item.draw());
  }

  function animationLoop(now) {
    drawScene(now);
    window.requestAnimationFrame(animationLoop);
  }

  function save() {
    const snapshot = { ...state, effects: [], moving: false, pendingTouch: false };
    localStorage.setItem("web-rpg-save", JSON.stringify(snapshot));
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
      Object.assign(state, loaded, { effects: [], moving: false, pendingTouch: false });
      view.mapId = null;
      syncPixelPosition();
      checkCompletion();
      addLog("Loaded.");
    } catch (error) {
      addLog(`Load failed: ${error.message}`);
    }
    render();
  }

  document.addEventListener("keydown", (event) => {
    const key = event.key.toLowerCase();
    if (event.key === " " || event.key === "Enter") {
      if (state.dialogue) nextDialogue();
      else interact();
      event.preventDefault();
      return;
    }
    if (["arrowup", "arrowright", "arrowdown", "arrowleft", "w", "a", "s", "d"].includes(key)) {
      keys[key] = true;
      tryMoveForKey(key);
      event.preventDefault();
    }
  });

  document.addEventListener("keyup", (event) => {
    keys[event.key.toLowerCase()] = false;
  });

  elements.dialogueNext.addEventListener("click", nextDialogue);
  elements.endingClose.addEventListener("click", () => {
    state.endingDismissed = true;
    render();
  });
  elements.saveBtn.addEventListener("click", save);
  elements.loadBtn.addEventListener("click", load);
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => battleAction(button.dataset.action));
  });

  window.addEventListener("resize", render);
  addLog("Game loaded.");
  render();
  if (!view.animationStarted) {
    view.animationStarted = true;
    window.requestAnimationFrame(animationLoop);
  }
}());
