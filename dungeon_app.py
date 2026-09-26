import json
import os
import random
import threading
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("env.txt", override=True)

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from openai import OpenAI
from pydantic import BaseModel, Field

app = FastAPI()
client = OpenAI(base_url="https://openrouter.ai/api/v1")

MODEL = "openai/gpt-4o-mini"

SAVE_PATH = Path("data/dungeon_save.json")
LOCK = threading.Lock()
GAME_STATE = None

# ---------------------------------------------------------------------------
# Content tables
# ---------------------------------------------------------------------------

ITEMS = {
    "rusty_shiv": {"name": "Rusty Shiv", "type": "weapon", "power": 8,
                   "description": "It's seen better days. So have you."},
    "frying_pan": {"name": "Cast-Iron Frying Pan", "type": "weapon", "power": 8,
                   "description": "Sponsor-provided. Surprisingly good in a fight."},
    "auctioneer_gavel": {"name": "Auctioneer's Gavel", "type": "weapon", "power": 13,
                          "description": "SOLD! To the guy who just won this fight."},
    "sewer_boots": {"name": "Sewer Boots", "type": "armor", "def": 3,
                    "description": "Waterproof. Mostly."},
    "static_charm": {"name": "Static Charm", "type": "trinket", "crit_bonus": 0.08,
                      "description": "Crackles faintly. Makes your hits meaner."},
    "patchup_potion": {"name": "Patch-Up Potion", "type": "consumable", "heal": 15,
                        "description": "Tastes like a Band-Aid. Works like one too."},
}

SKILLS = {
    "basic_attack": {"name": "Basic Attack", "unlock_level": 1, "mana_cost": 0, "cooldown": 0, "damage_mult": 1.0},
    "power_slap": {"name": "Power Slap", "unlock_level": 1, "mana_cost": 0, "cooldown": 2, "damage_mult": 1.6},
    "cats_distraction": {"name": "Cat's Distraction", "unlock_level": 1, "mana_cost": 5, "cooldown": 3},
    "adrenaline_surge": {"name": "Adrenaline Surge", "unlock_level": 2, "mana_cost": 10, "cooldown": 4, "heal": 12},
    "improvised_throw": {"name": "Improvised Throw", "unlock_level": 3, "mana_cost": 0, "cooldown": 3,
                          "damage_mult": 2.0},
}

CURSES = {
    "glass_jaw": {"name": "Glass Jaw", "description": "Your max HP took a permanent hit.", "hp_max_delta": -8},
    "product_placement_debt": {"name": "Product Placement Debt",
                                "description": "You owe the sponsors. Gold trickles away each floor.",
                                "gold_per_floor": -10},
}

BOONS = {
    "fan_favorite": {"name": "Fan Favorite", "description": "The crowd loves you. +10% XP earned.",
                      "xp_mult": 1.10},
    "lucky_paw": {"name": "Lucky Paw", "description": "Your cat rubbed off on you. +8% crit chance.",
                  "crit_bonus": 0.08},
    "iron_stomach": {"name": "Iron Stomach", "description": "Whatever that was, you're stronger for it. +2 END.",
                      "stat_delta": {"end": 2}},
}

MONSTERS = {
    "rat_bot_swarm": {"name": "Rat-Bot Swarm", "hp": 16, "power": 3, "def": 0, "agi": 8,
                       "xp_reward": 16, "gold_range": [2, 6], "loot_table": [("patchup_potion", 0.35)]},
    "sewer_jelly": {"name": "Sewer Jelly", "hp": 26, "power": 4, "def": 1, "agi": 2,
                     "xp_reward": 22, "gold_range": [3, 8],
                     "loot_table": [("sewer_boots", 0.35), ("patchup_potion", 0.25)]},
    "plumbing_warden": {"name": "The Plumbing Warden", "hp": 46, "power": 7, "def": 2, "agi": 4,
                         "xp_reward": 40, "gold_range": [15, 25],
                         "loot_table": [("frying_pan", 1.0), ("patchup_potion", 0.5)],
                         "boss": True},
    "bargain_golem": {"name": "Bargain Golem", "hp": 40, "power": 6, "def": 4, "agi": 2,
                       "xp_reward": 30, "gold_range": [10, 18],
                       "loot_table": [("static_charm", 0.35), ("patchup_potion", 0.25)]},
    "con_artist_sprite": {"name": "Con-Artist Sprite", "hp": 24, "power": 5, "def": 1, "agi": 12,
                           "xp_reward": 26, "gold_range": [8, 16],
                           "loot_table": [("patchup_potion", 0.4)], "steals_gold": True},
    "the_auctioneer": {"name": "The Auctioneer", "hp": 62, "power": 8, "def": 4, "agi": 6,
                        "xp_reward": 60, "gold_range": [25, 40],
                        "loot_table": [("auctioneer_gavel", 1.0), ("static_charm", 0.4), ("patchup_potion", 0.5)],
                        "boss": True},
    "feedback_wisp": {"name": "Feedback Wisp", "hp": 32, "power": 5, "def": 1, "agi": 9,
                       "xp_reward": 34, "gold_range": [12, 20],
                       "loot_table": [("static_charm", 0.35), ("patchup_potion", 0.25)], "drains_mana": True},
    "rerun_wraith": {"name": "Rerun Wraith", "hp": 36, "power": 6, "def": 2, "agi": 5,
                      "xp_reward": 36, "gold_range": [12, 22], "loot_table": [("patchup_potion", 0.4)]},
    "the_producer": {"name": "The Producer", "hp": 85, "power": 9, "def": 5, "agi": 7,
                      "xp_reward": 120, "gold_range": [50, 80],
                      "loot_table": [("patchup_potion", 0.6), ("static_charm", 0.5)], "boss": True,
                      "final_boss": True},
}

FLOORS = [
    {"theme": "The Neon Sewer Arena", "encounters": ["rat_bot_swarm", "sewer_jelly"],
     "boss": "plumbing_warden", "shop": ["frying_pan", "sewer_boots", "patchup_potion"]},
    {"theme": "The Gilded Arena", "encounters": ["bargain_golem", "con_artist_sprite"],
     "boss": "the_auctioneer", "shop": ["static_charm", "patchup_potion"]},
    {"theme": "The Static Wastes", "encounters": ["feedback_wisp", "rerun_wraith"],
     "boss": "the_producer", "shop": ["patchup_potion", "static_charm"]},
]

SHOP_PRICES = {"frying_pan": 30, "sewer_boots": 20, "patchup_potion": 12, "static_charm": 40}

CATALOG = {
    "items": {iid: {"name": d["name"], "type": d["type"], "description": d.get("description", "")}
              for iid, d in ITEMS.items()},
    "skills": {sid: {"name": d["name"], "mana_cost": d.get("mana_cost", 0), "cooldown": d.get("cooldown", 0)}
               for sid, d in SKILLS.items()},
    "curses": {cid: {"name": d["name"], "description": d["description"]} for cid, d in CURSES.items()},
    "boons": {bid: {"name": d["name"], "description": d["description"]} for bid, d in BOONS.items()},
    "monsters": {mid: {"name": d["name"]} for mid, d in MONSTERS.items()},
}

SYSTEM_PROMPT = """You are the narration voice for THE PROGRAM, a reality-TV game show broadcast from \
inside a monster-infested dungeon. You never decide what happens - a separate system already resolved \
the numbers. Your only job is to narrate, in character, what the given EVENT(S) mean.

Always respond in exactly this format, one line per voice, nothing else:
ANNOUNCER: <1-3 punchy, snarky, game-show-host sentences reacting to the event(s). Call the player \
"Contestant." Refer to the dungeon as "the Program" or "the Descent." Dark humor is fine; over-the-top \
show-biz energy is the goal. You may use at most one bracketed sound cue like [AIR HORN] or [CROWD GASPS].
CAT: <0-1 short, dry, self-serving sentence from the Contestant's cat companion - only include this line \
if the cat would plausibly react. Omit it entirely otherwise. When the event list includes a \
"cat_assist" entry, the cat actually helped in the fight - narrate that as a real action, not just banter.

Hard rules:
- Never state, imply, or invent any number (damage, HP, gold, XP, chance) that is not already present in \
the EVENT(S) or STATE given to you.
- Never invent items, monsters, or outcomes beyond what's described in the EVENT(S).
- Keep it short - this is one beat in an ongoing broadcast, not a scene.
- Never break the ANNOUNCER:/CAT: line format, and never add any other lines or headers.
"""

OPENING_LINE = ("Ladies, gentlemen, and things that used to be either: welcome back to THE PROGRAM! "
                "Our next Contestant stumbles in wearing nothing but boxers and a bad attitude, flanked "
                "by one deeply unimpressed cat. Let's see how far boxers-and-bravado gets him. Floor One... GO!")

STAGE_ORDER = ["encounter_1", "encounter_2", "boss", "reward"]
CAT_ASSIST_CHANCE = 0.35


# ---------------------------------------------------------------------------
# Combat math
# ---------------------------------------------------------------------------

def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def compute_hit_chance(att_agi, def_agi):
    return clamp(0.75 + 0.02 * (att_agi - def_agi), 0.25, 0.95)


def compute_crit_chance(att_luck, crit_bonus=0.0):
    return clamp(0.05 + 0.01 * att_luck + crit_bonus, 0.0, 0.9)


def resolve_hit(att_power, att_str, att_agi, att_luck, def_def, def_agi,
                 dmg_mult=1.0, crit_bonus=0.0, hit_chance_penalty=0.0):
    hit_chance = clamp(compute_hit_chance(att_agi, def_agi) - hit_chance_penalty, 0.05, 0.95)
    if random.random() >= hit_chance:
        return {"hit": False, "damage": 0, "crit": False}
    base = att_power * (1 + att_str / 50) * dmg_mult
    raw = base * random.uniform(0.85, 1.15)
    is_crit = random.random() < compute_crit_chance(att_luck, crit_bonus)
    if is_crit:
        raw *= 1.5
    damage = max(1, round(raw - def_def))
    return {"hit": True, "damage": damage, "crit": is_crit}


def get_weapon_power(player):
    weapon = player["equipped"].get("weapon")
    return ITEMS[weapon].get("power", 3) if weapon else 3


def get_armor_def(player):
    armor = player["equipped"].get("armor")
    return ITEMS[armor].get("def", 0) if armor else 0


def get_crit_bonus(player):
    bonus = 0.0
    trinket = player["equipped"].get("trinket")
    if trinket:
        bonus += ITEMS[trinket].get("crit_bonus", 0.0)
    for boon_id in player["boons"]:
        bonus += BOONS[boon_id].get("crit_bonus", 0.0)
    return bonus


def get_xp_mult(player):
    mult = 1.0
    for boon_id in player["boons"]:
        mult *= BOONS[boon_id].get("xp_mult", 1.0)
    return mult


# ---------------------------------------------------------------------------
# Game state helpers
# ---------------------------------------------------------------------------

def new_game():
    global GAME_STATE
    now = datetime.now(timezone.utc).isoformat()
    GAME_STATE = {
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "turn_number": 0,
        "status": "in_progress",
        "player": {
            "name": "The Guy in Boxers",
            "level": 1, "xp": 0, "xp_to_next": 25,
            "hp": 40, "hp_max": 40, "mana": 10, "mana_max": 10, "gold": 20,
            "stats": {"str": 5, "agi": 5, "end": 5, "int": 5, "luck": 5},
            "equipped": {"weapon": "rusty_shiv", "armor": None, "trinket": None},
            "inventory": [{"id": "patchup_potion", "qty": 3}],
            "skills": ["basic_attack", "power_slap", "cats_distraction"],
            "skill_cooldowns": {"power_slap": 0, "cats_distraction": 0},
            "curses": [],
            "boons": [],
        },
        "dungeon": {"floor": 1, "floor_theme": FLOORS[0]["theme"], "stage": "encounter_1", "whim_used": False},
        "combat": None,
        "narration_log": [{"turn": 0, "speaker": "announcer", "text": OPENING_LINE}],
    }
    save_state()


def save_state():
    SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SAVE_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w") as f:
        json.dump(GAME_STATE, f, indent=2)
    os.replace(tmp_path, SAVE_PATH)


def load_or_init():
    global GAME_STATE
    if SAVE_PATH.exists():
        try:
            with SAVE_PATH.open() as f:
                loaded = json.load(f)
            if "player" in loaded and "dungeon" in loaded and "narration_log" in loaded:
                GAME_STATE = loaded
                return
        except (json.JSONDecodeError, KeyError):
            pass
    new_game()


def grant_item(player, item_id):
    item = ITEMS[item_id]
    if item["type"] in ("weapon", "armor", "trinket"):
        player["equipped"][item["type"]] = item_id
    else:
        entry = next((e for e in player["inventory"] if e["id"] == item_id), None)
        if entry:
            entry["qty"] += 1
        else:
            player["inventory"].append({"id": item_id, "qty": 1})
    return item["name"]


def check_level_up(player, events):
    stat_cycle = ["str", "agi", "end", "int", "luck"]
    while player["xp"] >= player["xp_to_next"]:
        player["xp"] -= player["xp_to_next"]
        player["level"] += 1
        player["xp_to_next"] = round(40 * player["level"] ** 1.3)
        player["hp_max"] += 8
        player["mana_max"] += 4
        player["hp"] = player["hp_max"]
        player["mana"] = player["mana_max"]
        stat_to_grow = stat_cycle[(player["level"] - 1) % len(stat_cycle)]
        player["stats"][stat_to_grow] += 2
        events.append({"type": "level_up", "level": player["level"], "stat_grown": stat_to_grow})
        for sid, sdef in SKILLS.items():
            if sdef["unlock_level"] == player["level"] and sid not in player["skills"]:
                player["skills"].append(sid)
                player["skill_cooldowns"][sid] = 0
                events.append({"type": "skill_unlocked", "skill": sdef["name"]})


def advance_stage(state, events):
    dungeon = state["dungeon"]
    idx = STAGE_ORDER.index(dungeon["stage"])
    dungeon["stage"] = STAGE_ORDER[idx + 1]
    if dungeon["stage"] == "reward":
        dungeon["whim_used"] = False
    events.append({"type": "stage_change", "stage": dungeon["stage"]})


def handle_monster_death(state, events):
    player = state["player"]
    combat = state["combat"]
    monster = MONSTERS[combat["monster_id"]]
    xp = round(monster["xp_reward"] * get_xp_mult(player))
    gold = random.randint(*monster["gold_range"])
    player["gold"] += gold
    player["xp"] += xp
    loot_names = []
    for item_id, chance in monster.get("loot_table", []):
        if random.random() < chance:
            loot_names.append(grant_item(player, item_id))
    events.append({"type": "monster_defeated", "monster_name": monster["name"],
                    "xp_gained": xp, "gold_gained": gold, "loot": loot_names})
    check_level_up(player, events)
    state["combat"] = None
    advance_stage(state, events)


def run_monster_turn(state, events):
    player = state["player"]
    combat = state["combat"]
    monster = MONSTERS[combat["monster_id"]]

    if random.random() < CAT_ASSIST_CHANCE:
        assist_dmg = random.randint(2, 4)
        combat["monster_hp"] = max(0, combat["monster_hp"] - assist_dmg)
        events.append({"type": "cat_assist", "damage": assist_dmg,
                        "monster_hp_remaining": combat["monster_hp"]})
        if combat["monster_hp"] <= 0:
            handle_monster_death(state, events)
            return

    hit_penalty = combat.pop("monster_hit_penalty", 0.0)
    result = resolve_hit(monster["power"], 0, monster["agi"], 0,
                          get_armor_def(player), player["stats"]["agi"],
                          hit_chance_penalty=hit_penalty)
    ev = {"type": "monster_attack", "monster_name": monster["name"],
          "hit": result["hit"], "damage": result["damage"], "crit": result["crit"]}
    if result["hit"]:
        player["hp"] = max(0, player["hp"] - result["damage"])
        if monster.get("steals_gold"):
            stolen = min(player["gold"], random.randint(1, 5))
            player["gold"] -= stolen
            ev["gold_stolen"] = stolen
        if monster.get("drains_mana"):
            drained = min(player["mana"], 3)
            player["mana"] -= drained
            ev["mana_drained"] = drained
    events.append(ev)
    combat["round"] += 1
    if player["hp"] <= 0:
        state["status"] = "defeat"
        events.append({"type": "defeat"})


def handle_explore(state, events):
    dungeon = state["dungeon"]
    if state["combat"] is not None or dungeon["stage"] not in ("encounter_1", "encounter_2", "boss"):
        events.append({"type": "action_failed", "reason": "nothing to explore right now"})
        return
    floor = FLOORS[dungeon["floor"] - 1]
    if dungeon["stage"] == "encounter_1":
        monster_id = floor["encounters"][0]
    elif dungeon["stage"] == "encounter_2":
        monster_id = floor["encounters"][1]
    else:
        monster_id = floor["boss"]
    m = MONSTERS[monster_id]
    state["combat"] = {"active": True, "monster_id": monster_id, "monster_hp": m["hp"],
                        "monster_hp_max": m["hp"], "round": 1, "monster_hit_penalty": 0.0,
                        "phase_2_triggered": False}
    events.append({"type": "encounter_start", "monster_name": m["name"], "boss": m.get("boss", False)})


def handle_combat_action(state, action_type, payload, events):
    player = state["player"]
    combat = state["combat"]
    monster = MONSTERS[combat["monster_id"]]
    skill_id = "basic_attack" if action_type == "attack" else payload.get("skill_id")
    if skill_id not in SKILLS:
        events.append({"type": "action_failed", "reason": "unknown skill"})
        return
    skill = SKILLS[skill_id]

    for sid, cd in list(player["skill_cooldowns"].items()):
        if cd > 0:
            player["skill_cooldowns"][sid] = cd - 1

    if skill_id != "basic_attack":
        if player["skill_cooldowns"].get(skill_id, 0) > 0 or player["mana"] < skill.get("mana_cost", 0):
            events.append({"type": "action_failed", "reason": "skill not ready"})
            return
        player["mana"] -= skill.get("mana_cost", 0)
        player["skill_cooldowns"][skill_id] = skill["cooldown"]

    monster_defeated = False
    buff_mult = combat.pop("player_buff_mult", 1.0)

    if skill_id == "cats_distraction":
        combat["monster_hit_penalty"] = 0.25
        events.append({"type": "skill_used", "skill": skill["name"]})
    elif skill_id == "adrenaline_surge":
        heal = skill["heal"]
        player["hp"] = min(player["hp_max"], player["hp"] + heal)
        combat["player_buff_mult"] = 1.3
        events.append({"type": "skill_used", "skill": skill["name"], "heal": heal})
    else:
        item_consumed = None
        if skill_id == "improvised_throw":
            item_id = payload.get("item_id")
            entry = next((e for e in player["inventory"] if e["id"] == item_id), None)
            if not entry:
                events.append({"type": "action_failed", "reason": "no item to throw"})
                return
            entry["qty"] -= 1
            if entry["qty"] <= 0:
                player["inventory"].remove(entry)
            item_consumed = ITEMS[item_id]["name"]
        dmg_mult = skill.get("damage_mult", 1.0) * buff_mult
        result = resolve_hit(get_weapon_power(player), player["stats"]["str"], player["stats"]["agi"],
                              player["stats"]["luck"], monster["def"], monster["agi"],
                              dmg_mult=dmg_mult, crit_bonus=get_crit_bonus(player))
        ev = {"type": "player_attack", "skill": skill["name"], "hit": result["hit"],
              "damage": result["damage"], "crit": result["crit"]}
        if item_consumed:
            ev["item_thrown"] = item_consumed
        events.append(ev)
        if result["hit"]:
            combat["monster_hp"] = max(0, combat["monster_hp"] - result["damage"])
            if combat["monster_hp"] <= 0:
                monster_defeated = True

    if monster_defeated:
        handle_monster_death(state, events)
    else:
        if (monster.get("final_boss") and combat["monster_hp"] <= combat["monster_hp_max"] / 2
                and not combat.get("phase_2_triggered")):
            combat["phase_2_triggered"] = True
            events.append({"type": "phase_change", "monster_name": monster["name"]})
        run_monster_turn(state, events)


def handle_use_item(state, payload, events):
    player = state["player"]
    item_id = payload.get("item_id")
    entry = next((e for e in player["inventory"] if e["id"] == item_id), None)
    if not entry or ITEMS.get(item_id, {}).get("type") != "consumable":
        events.append({"type": "action_failed", "reason": "item not available"})
        return
    item = ITEMS[item_id]
    heal = item.get("heal", 0)
    player["hp"] = min(player["hp_max"], player["hp"] + heal)
    entry["qty"] -= 1
    if entry["qty"] <= 0:
        player["inventory"].remove(entry)
    events.append({"type": "item_used", "item": item["name"], "heal": heal})
    if state["combat"] and state["combat"].get("active"):
        run_monster_turn(state, events)


def handle_shop_buy(state, payload, events):
    player = state["player"]
    dungeon = state["dungeon"]
    if dungeon["stage"] != "reward":
        events.append({"type": "action_failed", "reason": "no shop open"})
        return
    item_id = payload.get("item_id")
    floor = FLOORS[dungeon["floor"] - 1]
    price = SHOP_PRICES.get(item_id)
    if price is None or item_id not in floor["shop"] or player["gold"] < price:
        events.append({"type": "action_failed", "reason": "can't afford or unavailable"})
        return
    player["gold"] -= price
    name = grant_item(player, item_id)
    events.append({"type": "shop_buy", "item": name, "price": price})


def handle_shop_whim(state, events):
    player = state["player"]
    dungeon = state["dungeon"]
    if dungeon["stage"] != "reward" or dungeon.get("whim_used"):
        events.append({"type": "action_failed", "reason": "whim already used"})
        return
    dungeon["whim_used"] = True
    if random.random() < 0.8:
        pool = [b for b in BOONS if b not in player["boons"]] or list(BOONS.keys())
        boon_id = random.choice(pool)
        player["boons"].append(boon_id)
        for k, v in BOONS[boon_id].get("stat_delta", {}).items():
            player["stats"][k] += v
        events.append({"type": "sponsor_whim", "result": "boon", "name": BOONS[boon_id]["name"],
                        "description": BOONS[boon_id]["description"]})
    else:
        pool = [c for c in CURSES if c not in player["curses"]] or list(CURSES.keys())
        curse_id = random.choice(pool)
        player["curses"].append(curse_id)
        if "hp_max_delta" in CURSES[curse_id]:
            player["hp_max"] = max(10, player["hp_max"] + CURSES[curse_id]["hp_max_delta"])
            player["hp"] = min(player["hp"], player["hp_max"])
        events.append({"type": "sponsor_whim", "result": "curse", "name": CURSES[curse_id]["name"],
                        "description": CURSES[curse_id]["description"]})


def handle_shop_leave(state, events):
    dungeon = state["dungeon"]
    player = state["player"]
    if dungeon["stage"] != "reward":
        events.append({"type": "action_failed", "reason": "no shop open"})
        return
    if dungeon["floor"] >= 3:
        state["status"] = "victory"
        events.append({"type": "victory"})
        return
    for curse_id in player["curses"]:
        delta = CURSES[curse_id].get("gold_per_floor")
        if delta:
            player["gold"] = max(0, player["gold"] + delta)
    dungeon["floor"] += 1
    dungeon["floor_theme"] = FLOORS[dungeon["floor"] - 1]["theme"]
    dungeon["stage"] = "encounter_1"
    events.append({"type": "floor_advance", "floor": dungeon["floor"], "theme": dungeon["floor_theme"]})


def compute_choices(state):
    if state["status"] != "in_progress":
        return []
    dungeon = state["dungeon"]
    player = state["player"]
    combat = state["combat"]
    choices = []
    if combat and combat.get("active"):
        choices.append("attack")
        for skill_id in player["skills"]:
            if skill_id == "basic_attack":
                continue
            skill = SKILLS[skill_id]
            if player["skill_cooldowns"].get(skill_id, 0) != 0:
                continue
            if player["mana"] < skill.get("mana_cost", 0):
                continue
            if skill_id == "improvised_throw" and not player["inventory"]:
                continue
            choices.append(f"skill:{skill_id}")
    elif dungeon["stage"] == "reward":
        floor = FLOORS[dungeon["floor"] - 1]
        for item_id in floor["shop"]:
            if SHOP_PRICES.get(item_id, 10 ** 9) <= player["gold"]:
                choices.append(f"shop_buy:{item_id}")
        if not dungeon.get("whim_used"):
            choices.append("shop_whim")
        choices.append("shop_leave")
    else:
        choices.append("explore")
    for entry in player["inventory"]:
        if entry["qty"] > 0 and ITEMS[entry["id"]]["type"] == "consumable":
            choices.append(f"use_item:{entry['id']}")
    return choices


def build_state_slice(state):
    player = state["player"]
    dungeon = state["dungeon"]
    combat = state["combat"]
    slice_ = {
        "player_hp": player["hp"], "player_hp_max": player["hp_max"],
        "player_mana": player["mana"], "player_mana_max": player["mana_max"],
        "player_level": player["level"], "floor": dungeon["floor"],
        "floor_theme": dungeon["floor_theme"], "stage": dungeon["stage"],
    }
    if combat:
        m = MONSTERS[combat["monster_id"]]
        slice_["monster_name"] = m["name"]
        slice_["monster_hp"] = combat["monster_hp"]
        slice_["monster_hp_max"] = combat["monster_hp_max"]
    return slice_


def parse_narration(text):
    lines = []
    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("ANNOUNCER:"):
            lines.append({"speaker": "announcer", "text": line.split(":", 1)[1].strip()})
        elif upper.startswith("CAT:"):
            lines.append({"speaker": "cat", "text": line.split(":", 1)[1].strip()})
        else:
            lines.append({"speaker": "announcer", "text": line})
    if not lines:
        lines = [{"speaker": "announcer", "text": text.strip() or "..."}]
    return lines


def narrate(events, state_slice):
    if not events:
        return []
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"EVENT(S):\n{json.dumps(events)}\n\nCURRENT STATE:\n{json.dumps(state_slice)}"},
    ]
    try:
        response = client.chat.completions.create(model=MODEL, messages=messages, max_tokens=220)
        text = response.choices[0].message.content or ""
    except Exception as e:
        text = f"ANNOUNCER: [SIGNAL LOST] The Program apologizes for the technical difficulties. ({e})"
    return parse_narration(text)


def build_response(state):
    return {
        "status": state["status"],
        "player": state["player"],
        "dungeon": state["dungeon"],
        "combat": state["combat"],
        "pending_choices": compute_choices(state),
        "narration": state["narration_log"][-12:],
        "turn_number": state["turn_number"],
    }


load_or_init()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

class ActionRequest(BaseModel):
    type: str
    payload: dict = Field(default_factory=dict)


@app.get("/state")
def get_state():
    return build_response(GAME_STATE)


@app.post("/action")
def action(req: ActionRequest):
    with LOCK:
        state = GAME_STATE
        if state["status"] != "in_progress":
            return build_response(state)

        events = []
        if req.type == "explore":
            handle_explore(state, events)
        elif req.type in ("attack", "skill"):
            if not state["combat"] or not state["combat"].get("active"):
                events.append({"type": "action_failed", "reason": "not in combat"})
            else:
                handle_combat_action(state, req.type, req.payload, events)
        elif req.type == "use_item":
            handle_use_item(state, req.payload, events)
        elif req.type == "shop_buy":
            handle_shop_buy(state, req.payload, events)
        elif req.type == "shop_whim":
            handle_shop_whim(state, events)
        elif req.type == "shop_leave":
            handle_shop_leave(state, events)
        elif req.type == "banter":
            text = req.payload.get("text", "").strip()
            if text:
                events.append({"type": "banter", "player_said": text})
        else:
            events.append({"type": "action_failed", "reason": "unknown action"})

        state["turn_number"] += 1
        state["updated_at"] = datetime.now(timezone.utc).isoformat()

        for line in narrate(events, build_state_slice(state)):
            state["narration_log"].append({"turn": state["turn_number"], "speaker": line["speaker"],
                                            "text": line["text"]})
        state["narration_log"] = state["narration_log"][-40:]

        save_state()
        return build_response(state)


@app.post("/new_game")
def new_game_endpoint():
    with LOCK:
        new_game()
        return build_response(GAME_STATE)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>THE PROGRAM</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0b0c10;
    --panel: #14161d;
    --panel-edge: #2a2e3a;
    --ink: #e8e8f0;
    --ink-soft: #9a9db0;
    --neon-pink: #ff3d81;
    --neon-cyan: #35e6d6;
    --neon-gold: #ffcf4d;
    --danger: #ff5b5b;
    --good: #4ddc8a;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; background: var(--bg); color: var(--ink);
    font-family: "IBM Plex Mono", monospace; padding: 16px;
  }
  h1, h2, h3 { font-family: "Bebas Neue", sans-serif; letter-spacing: 0.04em; margin: 0; }
  .titlebar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .titlebar h1 { font-size: 2rem; color: var(--neon-pink); text-shadow: 0 0 10px rgba(255,61,129,0.5); }
  .new-game-btn {
    background: var(--panel); color: var(--ink-soft); border: 1px solid var(--panel-edge);
    padding: 8px 14px; border-radius: 4px; cursor: pointer; font-family: "IBM Plex Mono", monospace;
  }
  .new-game-btn:hover { border-color: var(--neon-pink); color: var(--ink); }
  .layout { display: grid; grid-template-columns: 300px 1fr; gap: 14px; }
  @media (max-width: 800px) { .layout { grid-template-columns: 1fr; } }
  .panel {
    background: var(--panel); border: 1px solid var(--panel-edge); border-radius: 8px; padding: 14px;
  }
  .bar-row { margin-bottom: 8px; }
  .bar-label { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--ink-soft); margin-bottom: 3px; }
  .bar-outer { background: #1e2129; border-radius: 6px; height: 10px; overflow: hidden; }
  .bar-inner { height: 100%; border-radius: 6px; transition: width 0.3s ease; }
  #xpBar { background: var(--neon-gold); }
  #hpBar { background: var(--danger); }
  #manaBar { background: var(--neon-cyan); }
  #monsterBar { background: var(--neon-pink); }
  .stat-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin: 10px 0; }
  .stat { background: #1e2129; border-radius: 4px; padding: 6px 2px; text-align: center; }
  .stat-key { display: block; font-size: 0.65rem; color: var(--ink-soft); }
  .stat-val { display: block; font-size: 1.1rem; color: var(--neon-cyan); }
  .section-title { font-size: 0.7rem; color: var(--ink-soft); text-transform: uppercase; letter-spacing: 0.1em; margin: 12px 0 4px; }
  ul.plain { list-style: none; margin: 0; padding: 0; font-size: 0.85rem; }
  ul.plain li { padding: 3px 0; border-bottom: 1px dashed #23262f; }
  .tag-row { display: flex; flex-wrap: wrap; gap: 6px; }
  .tag { font-size: 0.7rem; padding: 3px 8px; border-radius: 12px; cursor: help; }
  .tag.curse { background: rgba(255,91,91,0.15); color: var(--danger); border: 1px solid var(--danger); }
  .tag.boon { background: rgba(77,220,138,0.15); color: var(--good); border: 1px solid var(--good); }
  .center { display: flex; flex-direction: column; min-width: 0; }
  #floorBanner {
    background: linear-gradient(90deg, rgba(255,61,129,0.15), rgba(53,230,214,0.15));
    border: 1px solid var(--panel-edge); border-radius: 6px; padding: 8px 12px; margin-bottom: 10px;
    font-family: "Bebas Neue", sans-serif; font-size: 1.1rem; letter-spacing: 0.05em; color: var(--neon-cyan);
  }
  #combatBox { background: var(--panel); border: 1px solid var(--neon-pink); border-radius: 8px; padding: 10px 14px; margin-bottom: 10px; display: none; }
  #monsterName { font-family: "Bebas Neue", sans-serif; font-size: 1.2rem; color: var(--neon-pink); }
  #log {
    flex: 1; min-height: 320px; max-height: 440px; overflow-y: auto; background: var(--panel);
    border: 1px solid var(--panel-edge); border-radius: 8px; padding: 12px; margin-bottom: 10px;
  }
  .line { margin-bottom: 8px; line-height: 1.4; font-size: 0.92rem; }
  .line.announcer { color: var(--ink); }
  .line.announcer::before { content: "\\1F4E3 "; }
  .line.cat { color: var(--neon-gold); font-style: italic; font-size: 0.85rem; }
  .line.cat::before { content: "\\1F408 "; }
  #actions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
  .action-btn {
    background: var(--panel); border: 1px solid var(--neon-cyan); color: var(--neon-cyan);
    padding: 8px 14px; border-radius: 4px; cursor: pointer; font-family: "IBM Plex Mono", monospace; font-size: 0.85rem;
  }
  .action-btn:hover { background: var(--neon-cyan); color: #06282a; }
  .composer { display: flex; gap: 8px; }
  .composer input {
    flex: 1; padding: 8px 10px; background: #1e2129; border: 1px solid var(--panel-edge); border-radius: 4px;
    color: var(--ink); font-family: "IBM Plex Mono", monospace;
  }
  .composer button {
    background: var(--neon-pink); color: #2a0714; border: none; padding: 8px 16px; border-radius: 4px;
    cursor: pointer; font-family: "IBM Plex Mono", monospace;
  }
  #overlay {
    display: none; position: fixed; inset: 0; background: rgba(6,7,10,0.9); z-index: 10;
    align-items: center; justify-content: center; flex-direction: column; gap: 16px;
  }
  #overlayText { font-family: "Bebas Neue", sans-serif; font-size: 2rem; color: var(--neon-gold); text-align: center; padding: 0 20px; }
</style>
</head>
<body>
  <div class="titlebar">
    <h1>THE PROGRAM</h1>
    <button class="new-game-btn" id="newGameBtn">Start New Descent</button>
  </div>
  <div class="layout">
    <aside class="panel">
      <h3 id="charName">-</h3>
      <div id="levelVal" style="color: var(--neon-gold); margin-bottom: 8px;">-</div>
      <div class="bar-row">
        <div class="bar-label"><span>XP</span></div>
        <div class="bar-outer"><div class="bar-inner" id="xpBar" style="width:0%"></div></div>
      </div>
      <div class="bar-row">
        <div class="bar-label"><span>HP</span><span id="hpText"></span></div>
        <div class="bar-outer"><div class="bar-inner" id="hpBar" style="width:0%"></div></div>
      </div>
      <div class="bar-row">
        <div class="bar-label"><span>MANA</span><span id="manaText"></span></div>
        <div class="bar-outer"><div class="bar-inner" id="manaBar" style="width:0%"></div></div>
      </div>
      <div class="stat-grid" id="statsGrid"></div>
      <div>Gold: <span id="goldVal" style="color: var(--neon-gold);">0</span></div>
      <div class="section-title">Equipped</div>
      <ul class="plain" id="equipList"></ul>
      <div class="section-title">Inventory</div>
      <ul class="plain" id="inventoryList"></ul>
      <div class="section-title">Skills</div>
      <ul class="plain" id="skillsList"></ul>
      <div class="section-title">Curses</div>
      <div class="tag-row" id="curseList"></div>
      <div class="section-title">Boons</div>
      <div class="tag-row" id="boonList"></div>
    </aside>
    <section class="center">
      <div id="floorBanner">-</div>
      <div id="combatBox">
        <div id="monsterName">-</div>
        <div class="bar-outer"><div class="bar-inner" id="monsterBar" style="width:0%"></div></div>
        <div id="monsterText" style="font-size: 0.8rem; color: var(--ink-soft); margin-top: 3px;"></div>
      </div>
      <div id="log"></div>
      <div id="actions"></div>
      <form class="composer" id="banterForm">
        <input id="banterInput" autocomplete="off" placeholder="Heckle the announcer, talk to your cat..." aria-label="Banter" />
        <button type="submit">Send</button>
      </form>
    </section>
  </div>
  <div id="overlay">
    <div id="overlayText">-</div>
    <button class="new-game-btn" id="overlayNewGameBtn">Start New Descent</button>
  </div>

<script>
  const CATALOG = __CATALOG_JSON__;
  const SHOP_PRICES = __SHOP_PRICES_JSON__;
  let lastData = null;

  function setBar(id, val, max) {
    const pct = max > 0 ? Math.max(0, Math.min(100, (val / max) * 100)) : 0;
    document.getElementById(id).style.width = pct + "%";
  }

  function labelFor(choice) {
    if (choice === "attack") return "Attack";
    if (choice === "explore") return "Explore";
    if (choice === "shop_leave") return "Leave Shop";
    if (choice === "shop_whim") return "Sponsor's Whim (free)";
    const parts = choice.split(":");
    if (parts[0] === "skill") return CATALOG.skills[parts[1]].name;
    if (parts[0] === "use_item") return "Use " + CATALOG.items[parts[1]].name;
    if (parts[0] === "shop_buy") return "Buy " + CATALOG.items[parts[1]].name + " (" + SHOP_PRICES[parts[1]] + "g)";
    return choice;
  }

  function render(data) {
    lastData = data;
    const p = data.player;
    document.getElementById("charName").textContent = p.name;
    document.getElementById("levelVal").textContent = "Lv " + p.level;
    setBar("xpBar", p.xp, p.xp_to_next);
    setBar("hpBar", p.hp, p.hp_max);
    setBar("manaBar", p.mana, p.mana_max);
    document.getElementById("hpText").textContent = p.hp + " / " + p.hp_max;
    document.getElementById("manaText").textContent = p.mana + " / " + p.mana_max;
    document.getElementById("goldVal").textContent = p.gold;

    const statsEl = document.getElementById("statsGrid");
    statsEl.innerHTML = "";
    ["str", "agi", "end", "int", "luck"].forEach(function (k) {
      const div = document.createElement("div");
      div.className = "stat";
      div.innerHTML = "<span class=\\"stat-key\\">" + k.toUpperCase() + "</span><span class=\\"stat-val\\">" + p.stats[k] + "</span>";
      statsEl.appendChild(div);
    });

    const eq = document.getElementById("equipList");
    eq.innerHTML = "";
    ["weapon", "armor", "trinket"].forEach(function (slot) {
      const id = p.equipped[slot];
      const name = id ? CATALOG.items[id].name : "(none)";
      const li = document.createElement("li");
      li.textContent = slot.toUpperCase() + ": " + name;
      eq.appendChild(li);
    });

    const inv = document.getElementById("inventoryList");
    inv.innerHTML = "";
    p.inventory.forEach(function (entry) {
      const item = CATALOG.items[entry.id];
      const li = document.createElement("li");
      li.title = item.description;
      li.textContent = item.name + " x" + entry.qty;
      inv.appendChild(li);
    });

    const sk = document.getElementById("skillsList");
    sk.innerHTML = "";
    p.skills.forEach(function (sid) {
      const s = CATALOG.skills[sid];
      const cd = p.skill_cooldowns[sid] || 0;
      const li = document.createElement("li");
      li.textContent = s.name + (s.mana_cost ? " (" + s.mana_cost + " MP)" : "") + (cd > 0 ? " [CD " + cd + "]" : "");
      sk.appendChild(li);
    });

    const curseEl = document.getElementById("curseList");
    curseEl.innerHTML = "";
    p.curses.forEach(function (cid) {
      const c = CATALOG.curses[cid];
      const span = document.createElement("span");
      span.className = "tag curse";
      span.title = c.description;
      span.textContent = c.name;
      curseEl.appendChild(span);
    });

    const boonEl = document.getElementById("boonList");
    boonEl.innerHTML = "";
    p.boons.forEach(function (bid) {
      const b = CATALOG.boons[bid];
      const span = document.createElement("span");
      span.className = "tag boon";
      span.title = b.description;
      span.textContent = b.name;
      boonEl.appendChild(span);
    });

    document.getElementById("floorBanner").textContent =
      "FLOOR " + data.dungeon.floor + " of 3 \\u2014 " + data.dungeon.floor_theme +
      (data.dungeon.stage === "boss" && !data.combat ? " \\u2014 BOSS AHEAD" : "");

    const combatBox = document.getElementById("combatBox");
    if (data.combat) {
      combatBox.style.display = "block";
      const mname = CATALOG.monsters[data.combat.monster_id].name;
      document.getElementById("monsterName").textContent = mname;
      setBar("monsterBar", data.combat.monster_hp, data.combat.monster_hp_max);
      document.getElementById("monsterText").textContent = data.combat.monster_hp + " / " + data.combat.monster_hp_max;
    } else {
      combatBox.style.display = "none";
    }

    const log = document.getElementById("log");
    log.innerHTML = "";
    data.narration.forEach(function (entry) {
      const div = document.createElement("div");
      div.className = "line " + entry.speaker;
      div.textContent = entry.text;
      log.appendChild(div);
    });
    log.scrollTop = log.scrollHeight;

    const actions = document.getElementById("actions");
    actions.innerHTML = "";
    data.pending_choices.forEach(function (choice) {
      const btn = document.createElement("button");
      btn.className = "action-btn";
      btn.textContent = labelFor(choice);
      btn.addEventListener("click", function () { doAction(choice); });
      actions.appendChild(btn);
    });

    const overlay = document.getElementById("overlay");
    if (data.status === "victory" || data.status === "defeat") {
      overlay.style.display = "flex";
      document.getElementById("overlayText").textContent =
        data.status === "victory" ? "YOU SURVIVED THE PROGRAM!" : "THE PROGRAM THANKS YOU FOR YOUR SERVICE.";
    } else {
      overlay.style.display = "none";
    }
  }

  function sendAction(type, payload) {
    fetch("action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: type, payload: payload || {} }),
    })
      .then(function (r) { return r.json(); })
      .then(render);
  }

  function doAction(choice) {
    let type = choice;
    let payload = {};
    if (choice.includes(":")) {
      const parts = choice.split(":");
      if (parts[0] === "skill") {
        type = "skill";
        payload = { skill_id: parts[1] };
        if (parts[1] === "improvised_throw") {
          if (!lastData.player.inventory.length) return;
          payload.item_id = lastData.player.inventory[0].id;
        }
      } else if (parts[0] === "use_item") {
        type = "use_item";
        payload = { item_id: parts[1] };
      } else if (parts[0] === "shop_buy") {
        type = "shop_buy";
        payload = { item_id: parts[1] };
      }
    }
    sendAction(type, payload);
  }

  document.getElementById("banterForm").addEventListener("submit", function (e) {
    e.preventDefault();
    const input = document.getElementById("banterInput");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    sendAction("banter", { text: text });
  });

  function startNewGame() {
    if (!confirm("Start a new Descent? This wipes your current run.")) return;
    fetch("new_game", { method: "POST" })
      .then(function (r) { return r.json(); })
      .then(render);
  }
  document.getElementById("newGameBtn").addEventListener("click", startNewGame);
  document.getElementById("overlayNewGameBtn").addEventListener("click", startNewGame);

  fetch("state").then(function (r) { return r.json(); }).then(render);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    html = HTML_TEMPLATE.replace("__CATALOG_JSON__", json.dumps(CATALOG)).replace(
        "__SHOP_PRICES_JSON__", json.dumps(SHOP_PRICES)
    )
    return HTMLResponse(html)
