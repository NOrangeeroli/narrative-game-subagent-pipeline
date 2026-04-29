(function () {
  "use strict";

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
  const actors = byId(data.actors);
  const enemies = byId(data.enemies);
  const encounters = byId(data.encounter_tables);
  const quests = byId(data.quests);
  const dialogues = byId(data.npc_dialogue);
  const items = byId(data.items);
  const restPoints = byId(data.rest_points);
  const shops = byId(data.shops);

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
  if (!Object.keys(maps).length) {
    maps[fallbackMap.id] = fallbackMap;
  }

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

  const state = {
    mapId: firstMapId,
    x: Number((data.start_position && data.start_position.x) || 1),
    y: Number((data.start_position && data.start_position.y) || 1),
    hero: {
      id: firstActor.id,
      name: firstActor.name || firstActor.display_name || firstActor.id,
      hp: maxHp(firstActor),
      maxHp: maxHp(firstActor),
      attack: stat(firstActor, "attack", 8),
      defense: stat(firstActor, "defense", 1),
      speed: stat(firstActor, "speed", 3)
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

  const elements = {
    title: document.getElementById("title"),
    location: document.getElementById("location"),
    map: document.getElementById("map"),
    party: document.getElementById("party"),
    questLog: document.getElementById("questLog"),
    messageLog: document.getElementById("messageLog"),
    dialogue: document.getElementById("dialogue"),
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

  function addLog(message) {
    state.log.unshift(message);
    state.log = state.log.slice(0, 6);
  }

  function tileAt(gameMap, x, y, layer, fallback) {
    const rows = gameMap.layers && Array.isArray(gameMap.layers[layer]) ? gameMap.layers[layer] : [];
    return rows[y] && rows[y][x] !== undefined ? rows[y][x] : fallback;
  }

  function isBlocked(gameMap, x, y) {
    if (x < 0 || y < 0 || x >= gameMap.width || y >= gameMap.height) {
      return true;
    }
    return Number(tileAt(gameMap, x, y, "collision", 0)) > 0;
  }

  function eventsAt(gameMap, x, y) {
    return (Array.isArray(gameMap.events) ? gameMap.events : []).filter((event) => event.x === x && event.y === y && !state.flags[`event_done:${event.id}`]);
  }

  function nearbyEvent() {
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
      if (event) {
        return event;
      }
    }
    return null;
  }

  function render() {
    const gameMap = currentMap();
    elements.title.textContent = data.title || "Playable Web RPG";
    elements.location.textContent = gameMap.title || gameMap.id;
    elements.map.style.gridTemplateColumns = `repeat(${gameMap.width}, minmax(24px, 1fr))`;
    elements.map.style.gridTemplateRows = `repeat(${gameMap.height}, minmax(24px, 1fr))`;
    const mapBackground = assetPath(gameMap.asset_id || gameMap.map_asset_id || gameMap.id);
    elements.map.style.backgroundImage = mapBackground ? `url("${encodeURI(mapBackground)}")` : "";
    elements.map.innerHTML = "";

    for (let y = 0; y < gameMap.height; y += 1) {
      for (let x = 0; x < gameMap.width; x += 1) {
        const tile = document.createElement("div");
        const ground = String(tileAt(gameMap, x, y, "ground", "grass"));
        tile.className = `tile ${ground}`;
        if (isBlocked(gameMap, x, y)) {
          tile.classList.add("blocked");
        }
        eventsAt(gameMap, x, y).forEach((event) => {
          const marker = document.createElement("div");
          marker.className = `marker ${markerClass(event)}`;
          marker.textContent = markerText(event);
          tile.appendChild(marker);
        });
        if (state.x === x && state.y === y) {
          const player = document.createElement("div");
          player.className = "marker player";
          player.textContent = "@";
          tile.appendChild(player);
        }
        elements.map.appendChild(tile);
      }
    }
    renderPanel();
    renderDialogue();
    renderBattle();
    renderEnding();
  }

  function markerClass(event) {
    const type = String(event.type || "");
    if (type === "battle" || type === "encounter") {
      return "battle-event";
    }
    if (type === "rest") {
      return "rest-event";
    }
    if (type === "pickup" || type === "item") {
      return "item-event";
    }
    if (type === "quest") {
      return "quest-event";
    }
    return "npc";
  }

  function markerText(event) {
    const type = String(event.type || "");
    if (type === "battle" || type === "encounter") return "!";
    if (type === "rest") return "+";
    if (type === "pickup" || type === "item") return "*";
    if (type === "quest") return "?";
    return "i";
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
    const questLines = Object.keys(state.quests).length
      ? Object.entries(state.quests).map(([id, status]) => `<div>${escapeHtml(id)}: ${escapeHtml(status)}</div>`).join("")
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

  function assetPath(assetId) {
    return data.assets && data.assets[assetId] ? data.assets[assetId] : "";
  }

  function firstAssetWithPrefix(prefix) {
    const refs = Array.isArray(data.asset_refs) ? data.asset_refs : [];
    return refs.find((assetId) => typeof assetId === "string" && assetId.startsWith(prefix));
  }

  function finalQuestId() {
    if (data.campaign && typeof data.campaign.final_quest_id === "string") {
      return data.campaign.final_quest_id;
    }
    if (typeof data.final_quest_id === "string") {
      return data.final_quest_id;
    }
    const major = data.campaign && Array.isArray(data.campaign.major_quest_ids) ? data.campaign.major_quest_ids : [];
    if (major.length) {
      return major[major.length - 1];
    }
    const questList = Array.isArray(data.quests) ? data.quests : [];
    return questList.length ? questList[questList.length - 1].id : null;
  }

  function completionReached() {
    const finalId = finalQuestId();
    if (finalId) {
      return state.quests[finalId] === "complete";
    }
    const questIds = Object.keys(quests);
    return questIds.length > 0 && questIds.every((id) => state.quests[id] === "complete");
  }

  function checkCompletion() {
    if (state.completed || !completionReached()) {
      return;
    }
    state.completed = true;
    addLog("Road opened.");
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

  function move(dx, dy) {
    if (state.dialogue || state.battle) return;
    const gameMap = currentMap();
    const nx = state.x + dx;
    const ny = state.y + dy;
    if (isBlocked(gameMap, nx, ny)) {
      addLog("The way is blocked.");
      render();
      return;
    }
    state.x = nx;
    state.y = ny;
    const event = eventsAt(gameMap, nx, ny)[0];
    if (event && (event.trigger === "touch" || event.type === "transfer")) {
      interact(event);
    } else {
      render();
    }
  }

  function interact(event) {
    const target = event || nearbyEvent();
    if (!target) {
      addLog("Nothing responds.");
      render();
      return;
    }
    const type = String(target.type || "npc");
    if (type === "battle" || type === "encounter") {
      startBattle(target);
      return;
    }
    if (type === "rest") {
      rest(target);
      return;
    }
    if (type === "pickup" || type === "item") {
      pickup(target);
      return;
    }
    if (type === "transfer") {
      transfer(target);
      return;
    }
    if (type === "shop") {
      talk(target, shopLines(target));
      return;
    }
    if (type === "quest") {
      acceptQuest(target);
      return;
    }
    talk(target, linesFor(target));
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

  function talk(event, rawLines) {
    const lines = rawLines.map((line) => typeof line === "string" ? { speaker: event.name || "NPC", text: line } : line);
    state.dialogue = { event, lines, index: 0 };
    if (event.quest_id && quests[event.quest_id] && !state.quests[event.quest_id]) {
      state.quests[event.quest_id] = "active";
    }
    render();
  }

  function acceptQuest(event) {
    const questId = event.quest_id || event.id;
    state.quests[questId] = event.complete ? "complete" : "active";
    talk(event, linesFor(event));
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
      }
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
    elements.dialogue.classList.remove("hidden");
  }

  function rest(event) {
    const restPoint = event.rest_point_id ? restPoints[event.rest_point_id] : null;
    const cost = Number((restPoint && restPoint.cost) || event.cost || 0);
    state.hero.hp = state.hero.maxHp;
    addLog(cost ? `Rested for ${cost}.` : "Rested and recovered.");
    if (event.once) state.flags[`event_done:${event.id}`] = true;
    render();
  }

  function pickup(event) {
    const itemId = event.item_id || "item.unknown";
    state.inventory[itemId] = (state.inventory[itemId] || 0) + Number(event.quantity || 1);
    addLog(`Got ${items[itemId] ? items[itemId].name || itemId : itemId}.`);
    state.flags[`event_done:${event.id}`] = true;
    render();
  }

  function transfer(event) {
    if (!event.target_map_id || !maps[event.target_map_id]) {
      addLog("The exit is not connected.");
      render();
      return;
    }
    state.mapId = event.target_map_id;
    state.x = Number(event.target_x || 1);
    state.y = Number(event.target_y || 1);
    addLog(`Moved to ${maps[state.mapId].title || state.mapId}.`);
    render();
  }

  function startBattle(event) {
    const enemyId = resolveEnemyId(event);
    if (!enemyId || !enemies[enemyId]) {
      addLog("No enemy is configured here.");
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
      text: `${source.name || source.id} appears.`
    };
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
      return;
    }
    const enemy = state.battle.enemy;
    elements.battleTitle.textContent = `Battle: ${enemy.name}`;
    elements.battleText.textContent = state.battle.text;
    elements.heroStats.textContent = `${state.hero.name}: HP ${Math.ceil(state.hero.hp)} / ${Math.ceil(state.hero.maxHp)}`;
    elements.enemyStats.textContent = `${enemy.name}: HP ${Math.ceil(enemy.hp)} / ${Math.ceil(enemy.maxHp)}`;
    const enemySprite = assetPath(enemy.spriteAssetId);
    elements.battleVisual.innerHTML = enemySprite ? `<img src="${encodeURI(enemySprite)}" alt="">` : "";
    const battleBackground = assetPath(state.battle.backgroundAssetId);
    elements.battleBox.style.backgroundImage = battleBackground ? `linear-gradient(rgba(26,30,25,0.72), rgba(26,30,25,0.9)), url("${encodeURI(battleBackground)}")` : "";
    elements.battle.classList.remove("hidden");
  }

  function battleAction(action) {
    if (!state.battle) return;
    const enemy = state.battle.enemy;
    if (action === "flee") {
      state.battle.text = "You backed away and reset the encounter.";
      state.battle = null;
      addLog("Fled from battle.");
      render();
      return;
    }
    if (action === "item") {
      state.hero.hp = clamp(state.hero.hp + 8, 0, state.hero.maxHp);
      state.battle.text = "Used a field ration and recovered HP.";
    } else {
      const bonus = action === "skill" ? 4 : 0;
      const damage = Math.max(1, state.hero.attack + bonus - enemy.defense * 0.5);
      enemy.hp -= damage;
      state.battle.text = `${state.hero.name} dealt ${Math.ceil(damage)} damage.`;
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
    }
    render();
  }

  function winBattle() {
    const event = state.battle.event;
    addLog(`Won against ${state.battle.enemy.name}.`);
    if (event.quest_id) {
      state.quests[event.quest_id] = "complete";
    }
    if (event.once !== false) {
      state.flags[`event_done:${event.id}`] = true;
    }
    if (event.reward_item_id) {
      state.inventory[event.reward_item_id] = (state.inventory[event.reward_item_id] || 0) + 1;
      addLog(`Got ${event.reward_item_id}.`);
    }
    state.battle = null;
    checkCompletion();
    render();
  }

  function save() {
    localStorage.setItem("web-rpg-save", JSON.stringify(state));
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
      Object.assign(state, loaded);
      checkCompletion();
      addLog("Loaded.");
    } catch (error) {
      addLog(`Load failed: ${error.message}`);
    }
    render();
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "ArrowUp" || event.key.toLowerCase() === "w") move(0, -1);
    else if (event.key === "ArrowRight" || event.key.toLowerCase() === "d") move(1, 0);
    else if (event.key === "ArrowDown" || event.key.toLowerCase() === "s") move(0, 1);
    else if (event.key === "ArrowLeft" || event.key.toLowerCase() === "a") move(-1, 0);
    else if (event.key === " " || event.key === "Enter") {
      if (state.dialogue) nextDialogue();
      else interact();
    } else {
      return;
    }
    event.preventDefault();
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

  addLog("Game loaded.");
  render();
}());
