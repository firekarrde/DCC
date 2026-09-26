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
    "scrap_pipe": {"name": "Scrap Pipe", "type": "weapon", "power": 10,
                   "description": "Tutorial-tunnel plumbing. Somebody left it right where you needed it."},
    "bigboi_boxers": {"name": "Enchanted BigBoi Boxers", "type": "armor", "def": 2,
                       "description": "The only thing you're wearing. Turns out that's enough to matter."},
    "crawler_ration": {"name": "Crawler Ration", "type": "consumable", "heal": 25,
                        "description": "Sponsor-issued nutrient paste. Tastes like regret, works like magic."},
    "mana_tonic": {"name": "Mana Toast", "type": "consumable", "mana": 15,
                    "description": "Fizzy, blue, and faintly radioactive-tasting. Refills a solid chunk of mana."},
    "field_ration_supreme": {"name": "Field Ration Supreme", "type": "consumable", "heal": 60,
                               "description": "The good stuff. Sponsors only send this once you're worth the airtime."},
    "greater_mana_tonic": {"name": "Greater Mana Tonic", "type": "consumable", "mana": 35,
                             "description": "Tastes like the first one, but it hits like a freight train."},
    "goblin_pass_tattoo": {"name": "Goblin Pass Tattoo", "type": "trinket", "crit_bonus": 0.05,
                             "description": "A crude tattoo that lets goblins mistake you for one of their own, sort of."},
    "goblin_war_axe": {"name": "Goblin War Chieftain's Axe", "type": "weapon", "power": 16,
                         "description": "Still warm. You earned this one the hard way."},
    "bigboi_boxers_upgraded": {"name": "Upgraded BigBoi Boxers", "type": "armor", "def": 7,
                                 "description": "Reinforced after the Krakaren incident. They charge a Protective Shell now."},
    "gorgons_lucky_pebble": {"name": "Gorgon's Lucky Pebble", "type": "trinket", "crit_bonus": 0.07,
                               "description": "Smooth, gray, and probably not a real pebble. Very lucky, though."},
    "bigboi_boxers_supreme": {"name": "Supreme BigBoi Boxers", "type": "armor", "def": 12,
                                "description": "The Over City tailors outdid themselves. These are basically a personality now."},
    "dungeon_anarchists_cookbook": {"name": "Dungeon Anarchist's Cookbook", "type": "trinket", "crit_bonus": 0.08,
                                       "description": "A hidden guide passed down from earlier crawlers, dog-eared and stained."},
    "demon_engine_piston": {"name": "Demon Engine Piston", "type": "weapon", "power": 26,
                              "description": "Ripped straight from the Iron Tangle's worst train. Still hisses steam."},
    "rockards_ring_of_sniping": {"name": "Rockard's Ring of Sniping", "type": "trinket", "crit_bonus": 0.10,
                                    "description": "Named after someone who is, notably, not you. Works great anyway."},
    "krakenbone_harpoon": {"name": "Krakenbone Harpoon", "type": "weapon", "power": 34,
                              "description": "Carved from something you'd rather not think about. Still dripping."},
    "shrink_wand": {"name": "Shrink Wand", "type": "trinket", "crit_bonus": 0.11,
                      "description": "Point, click, regret. Mostly used on hunters who had it coming."},
    "imogens_scepter": {"name": "Queen Imogen's Scepter", "type": "weapon", "power": 42,
                          "description": "A country boss's scepter. It remembers being swung. A lot."},
    "earth_hobby_potion": {"name": "Earth Hobby Potion", "type": "consumable", "heal": 45,
                             "description": "Grants a fleeting mastery of Cesta Punta. Mostly just heals a lot, honestly."},
}

SKILLS = {
    "basic_attack": {"name": "Basic Attack", "unlock_level": 1, "mana_cost": 0, "cooldown": 0, "damage_mult": 1.0,
                      "description": "A standard hit with your equipped weapon. No cost, no cooldown."},
    "powerful_strike": {"name": "Powerful Strike", "unlock_level": 1, "mana_cost": 0, "cooldown": 2, "damage_mult": 1.6,
                          "description": "A heavier swing for 60% more damage than a basic attack. 2-round cooldown."},
    "donuts_diversion": {"name": "Donut's Diversion", "unlock_level": 1, "mana_cost": 5, "cooldown": 3,
                          "heal": 10,
                          "description": "Donut launches a real distraction: the enemy's next attack completely misses, and you patch yourself up for 10 HP while it's busy. Costs 5 mana, 3-round cooldown."},
    "protective_shell": {"name": "Protective Shell", "unlock_level": 2, "mana_cost": 10, "cooldown": 4, "heal": 12,
                          "description": "Your Boxers charge up: heals you for 12 HP and boosts your next attack's damage by 30%. Costs 10 mana, 4-round cooldown."},
    "smush": {"name": "Smush", "unlock_level": 2, "mana_cost": 8, "cooldown": 3, "damage_mult": 1.4,
              "description": "A crushing blow for 40% more damage, and 50% more on top of that against a badly wounded enemy. Costs 8 mana, 3-round cooldown."},
    "iron_punch": {"name": "Iron Punch", "unlock_level": 3, "mana_cost": 6, "cooldown": 3, "damage_mult": 1.3,
                   "def_pierce": 0.5,
                   "description": "A gauntleted punch that shrugs off half the target's defense. 30% bonus damage. Costs 6 mana, 3-round cooldown."},
    "bomb_toss": {"name": "Bomb Toss", "unlock_level": 4, "mana_cost": 0, "cooldown": 3,
                  "damage_mult": 2.0,
                  "description": "Hurl an item from your inventory (Goblin Dynamite, if you've got it) for a heavy burst of damage. Consumes the item. 3-round cooldown."},
}

CURSES = {
    "glass_jaw": {"name": "Glass Jaw", "description": "Your max HP took a permanent hit.", "hp_max_delta": -8},
    "sponsor_debt": {"name": "Sponsor Debt",
                      "description": "You owe the show's sponsors. Gold trickles away each floor.",
                      "gold_per_floor": -10},
}

BOONS = {
    "fan_favorite": {"name": "Fan Favorite", "description": "The viewers love you. +10% XP earned.",
                      "xp_mult": 1.10},
    "donuts_luck": {"name": "Donut's Luck", "description": "Some of Donut's luck rubbed off on you. +8% crit chance.",
                    "crit_bonus": 0.08},
    "iron_stomach": {"name": "Iron Stomach", "description": "Whatever that was, you're stronger for it. +2 END.",
                      "stat_delta": {"end": 2}},
}

MONSTERS = {
    # Floor 1 -- The Tutorial
    "goblin": {"name": "Goblin", "hp": 18, "power": 4, "def": 1, "agi": 6,
               "xp_reward": 18, "gold_range": [3, 8], "loot_table": [("crawler_ration", 0.25)]},
    "murder_dozer": {"name": "Murder Dozer", "hp": 24, "power": 5, "def": 2, "agi": 3,
                      "xp_reward": 22, "gold_range": [4, 10], "loot_table": [("crawler_ration", 0.2)]},
    "bad_llama": {"name": "Bad Llama", "hp": 20, "power": 4, "def": 0, "agi": 9,
                  "xp_reward": 20, "gold_range": [3, 9], "loot_table": [("crawler_ration", 0.2)]},
    "troglodyte": {"name": "Troglodyte", "hp": 26, "power": 5, "def": 2, "agi": 4,
                   "xp_reward": 24, "gold_range": [5, 10], "loot_table": [("mana_tonic", 0.2)]},
    "the_hoarder": {"name": "The Hoarder", "hp": 42, "power": 7, "def": 3, "agi": 5,
                     "xp_reward": 42, "gold_range": [18, 28], "loot_table": [("goblin_pass_tattoo", 0.5)]},
    "the_juicer": {"name": "The Juicer", "hp": 44, "power": 8, "def": 2, "agi": 6,
                    "xp_reward": 44, "gold_range": [18, 28], "loot_table": [("crawler_ration", 0.4)]},
    "ball_of_swine": {"name": "Ball of Swine", "hp": 50, "power": 7, "def": 4, "agi": 3,
                       "xp_reward": 48, "gold_range": [20, 30], "loot_table": [("mana_tonic", 0.3)]},
    "goblin_war_chieftain": {"name": "Goblin War Chieftain", "hp": 70, "power": 9, "def": 4, "agi": 5,
                              "xp_reward": 70, "gold_range": [30, 45],
                              "loot_table": [("goblin_war_axe", 1.0)], "boss": True},

    # Floor 2 -- Second Floor Sprawl
    "brindle_grub": {"name": "Brindle Grub", "hp": 30, "power": 5, "def": 1, "agi": 5,
                      "xp_reward": 30, "gold_range": [8, 14], "loot_table": [("crawler_ration", 0.25)]},
    "danger_dingo": {"name": "Danger Dingo", "hp": 34, "power": 6, "def": 1, "agi": 10,
                      "xp_reward": 32, "gold_range": [8, 14], "loot_table": [("crawler_ration", 0.2)]},
    "mind_horror": {"name": "Mind Horror", "hp": 32, "power": 6, "def": 2, "agi": 6,
                     "xp_reward": 34, "gold_range": [10, 16], "loot_table": [("mana_tonic", 0.2)]},
    "feral_clurichaun": {"name": "Feral Clurichaun", "hp": 30, "power": 5, "def": 1, "agi": 8,
                          "xp_reward": 30, "gold_range": [8, 14],
                          "loot_table": [("crawler_ration", 0.25)], "steals_gold": True},
    "laminak": {"name": "Laminak", "hp": 28, "power": 5, "def": 3, "agi": 4,
                "xp_reward": 30, "gold_range": [8, 14], "loot_table": [("mana_tonic", 0.2)]},
    "kobold": {"name": "Kobold", "hp": 26, "power": 4, "def": 1, "agi": 7,
               "xp_reward": 26, "gold_range": [6, 12], "loot_table": [("crawler_ration", 0.2)]},
    "rage_elemental": {"name": "Rage Elemental", "hp": 78, "power": 11, "def": 3, "agi": 5,
                        "xp_reward": 85, "gold_range": [35, 50], "loot_table": [("crawler_ration", 0.4)]},
    "ralph_the_frenzied_gerbil": {"name": "Ralph the Frenzied Gerbil", "hp": 60, "power": 9, "def": 2, "agi": 14,
                                   "xp_reward": 70, "gold_range": [28, 40],
                                   "loot_table": [("gorgons_lucky_pebble", 0.5)]},
    "krakaren_clone": {"name": "Krakaren Clone", "hp": 110, "power": 13, "def": 5, "agi": 5,
                        "xp_reward": 130, "gold_range": [55, 75],
                        "loot_table": [("bigboi_boxers_upgraded", 1.0)], "boss": True},

    # Floor 3 -- The Over City
    "circus_lemur": {"name": "Circus Lemur", "hp": 34, "power": 6, "def": 1, "agi": 12,
                      "xp_reward": 40, "gold_range": [10, 18], "loot_table": [("crawler_ration", 0.25)]},
    "giraffe_rider": {"name": "Giraffe Rider", "hp": 40, "power": 7, "def": 2, "agi": 6,
                       "xp_reward": 44, "gold_range": [12, 20], "loot_table": [("crawler_ration", 0.2)]},
    "undead_performer": {"name": "Undead Circus Performer", "hp": 38, "power": 7, "def": 3, "agi": 5,
                          "xp_reward": 42, "gold_range": [10, 18], "loot_table": [("mana_tonic", 0.2)]},
    "heather_the_bear": {"name": "Heather the Bear", "hp": 95, "power": 12, "def": 4, "agi": 4,
                          "xp_reward": 110, "gold_range": [40, 60],
                          "loot_table": [("earth_hobby_potion", 0.4)]},
    "ringmaster_grimaldi": {"name": "Ringmaster Grimaldi", "hp": 150, "power": 15, "def": 6, "agi": 6,
                             "xp_reward": 190, "gold_range": [70, 100],
                             "loot_table": [("bigboi_boxers_supreme", 1.0)], "boss": True},

    # Floor 4 -- The Iron Tangle
    "drek": {"name": "Drek", "hp": 44, "power": 8, "def": 3, "agi": 6,
             "xp_reward": 48, "gold_range": [14, 24], "loot_table": [("field_ration_supreme", 0.2)]},
    "psycho_sticker": {"name": "Psycho Sticker", "hp": 40, "power": 7, "def": 2, "agi": 8,
                        "xp_reward": 46, "gold_range": [14, 22], "loot_table": [("field_ration_supreme", 0.2)]},
    "jikininki": {"name": "Jikininki", "hp": 46, "power": 8, "def": 3, "agi": 5,
                  "xp_reward": 50, "gold_range": [16, 24], "loot_table": [("greater_mana_tonic", 0.2)]},
    "cave_mudge_bonker": {"name": "Cave Mudge Bonker", "hp": 42, "power": 7, "def": 4, "agi": 4,
                           "xp_reward": 46, "gold_range": [14, 22], "loot_table": [("field_ration_supreme", 0.2)]},
    "shock_chomper": {"name": "Shock Chomper", "hp": 44, "power": 8, "def": 2, "agi": 9,
                       "xp_reward": 48, "gold_range": [15, 24],
                       "loot_table": [("greater_mana_tonic", 0.2)], "drains_mana": True},
    "gore_gore": {"name": "Gore-Gore the Mantaur Engineer", "hp": 105, "power": 14, "def": 5, "agi": 5,
                   "xp_reward": 140, "gold_range": [50, 70],
                   "loot_table": [("dungeon_anarchists_cookbook", 0.5)]},
    "regenerating_gnoll": {"name": "The Regenerating Gnoll", "hp": 90, "power": 12, "def": 4, "agi": 6,
                            "xp_reward": 120, "gold_range": [45, 65],
                            "loot_table": [("field_ration_supreme", 0.4)]},
    "krakaren_clone_lesser": {"name": "Krakaren Clone", "hp": 100, "power": 13, "def": 5, "agi": 5,
                               "xp_reward": 125, "gold_range": [45, 65],
                               "loot_table": [("greater_mana_tonic", 0.4)]},
    "the_demon_mother": {"name": "The Demon Mother", "hp": 200, "power": 17, "def": 7, "agi": 6,
                          "xp_reward": 260, "gold_range": [90, 130],
                          "loot_table": [("demon_engine_piston", 1.0)], "boss": True},

    # Floor 5 -- The Bubbles
    "dromedarian": {"name": "Dromedarian", "hp": 50, "power": 9, "def": 3, "agi": 6,
                     "xp_reward": 60, "gold_range": [18, 28], "loot_table": [("field_ration_supreme", 0.2)]},
    "bactrian": {"name": "Bactrian", "hp": 54, "power": 9, "def": 4, "agi": 5,
                 "xp_reward": 62, "gold_range": [18, 28], "loot_table": [("field_ration_supreme", 0.2)]},
    "dirigible_gnome": {"name": "Dirigible Gnome", "hp": 46, "power": 8, "def": 2, "agi": 10,
                         "xp_reward": 58, "gold_range": [16, 26], "loot_table": [("greater_mana_tonic", 0.2)]},
    "changeling": {"name": "Changeling", "hp": 48, "power": 9, "def": 3, "agi": 8,
                   "xp_reward": 60, "gold_range": [18, 28], "loot_table": [("greater_mana_tonic", 0.2)]},
    "denise_goose_mother": {"name": "Denise the Feral Goose Mother", "hp": 110, "power": 15, "def": 5, "agi": 6,
                             "xp_reward": 150, "gold_range": [55, 80],
                             "loot_table": [("field_ration_supreme", 0.4)]},
    "giant_sand_ooze": {"name": "Giant Sand Ooze", "hp": 120, "power": 14, "def": 6, "agi": 3,
                         "xp_reward": 155, "gold_range": [55, 80],
                         "loot_table": [("greater_mana_tonic", 0.4)]},
    "orthrus": {"name": "Orthrus", "hp": 160, "power": 18, "def": 6, "agi": 7,
                "xp_reward": 210, "gold_range": [75, 100],
                "loot_table": [("rockards_ring_of_sniping", 0.5)]},
    "emberus": {"name": "Emberus", "hp": 165, "power": 19, "def": 5, "agi": 6,
                "xp_reward": 220, "gold_range": [80, 105],
                "loot_table": [("field_ration_supreme", 0.5)]},
    "lusca": {"name": "Lusca", "hp": 260, "power": 20, "def": 8, "agi": 6,
              "xp_reward": 320, "gold_range": [110, 150],
              "loot_table": [("krakenbone_harpoon", 1.0)], "boss": True},

    # Floor 6 -- The Hunting Grounds
    "hunter": {"name": "Hunter", "hp": 60, "power": 11, "def": 4, "agi": 9,
               "xp_reward": 80, "gold_range": [25, 40], "loot_table": [("field_ration_supreme", 0.25)]},
    "dinosaur": {"name": "Dinosaur", "hp": 70, "power": 13, "def": 3, "agi": 6,
                 "xp_reward": 85, "gold_range": [25, 40], "loot_table": [("field_ration_supreme", 0.2)]},
    "odious_creeper": {"name": "Odious Creeper", "hp": 56, "power": 10, "def": 3, "agi": 7,
                        "xp_reward": 75, "gold_range": [22, 36], "loot_table": [("greater_mana_tonic", 0.2)]},
    "shambling_berserker": {"name": "Shambling Berserker", "hp": 64, "power": 12, "def": 2, "agi": 5,
                             "xp_reward": 80, "gold_range": [24, 38], "loot_table": [("greater_mana_tonic", 0.2)]},
    "vrah_the_lead_hunter": {"name": "Vrah, the Lead Hunter", "hp": 180, "power": 20, "def": 6, "agi": 10,
                              "xp_reward": 240, "gold_range": [90, 120],
                              "loot_table": [("shrink_wand", 0.5)]},
    "queen_imogen": {"name": "Queen Imogen", "hp": 340, "power": 24, "def": 9, "agi": 7,
                      "xp_reward": 450, "gold_range": [150, 200],
                      "loot_table": [("imogens_scepter", 1.0)], "boss": True, "final_boss": True},
}

TRAPS = {
    "rot_sticker_trap": {"name": "Rot Sticker Trap", "hp_loss": [6, 12]},
    "suspicious_wall_rune": {"name": "Suspicious Wall Rune", "hp_loss": [8, 15]},
    "pestiferous_vine_snare": {"name": "Pestiferous Vine Snare", "hp_loss": [10, 18]},
    "runaway_handcart": {"name": "Runaway Handcart", "hp_loss": [12, 20]},
    "collapsing_bubble_seal": {"name": "Collapsing Bubble Seal", "hp_loss": [14, 22]},
    "poachers_snare": {"name": "Poacher's Snare", "gold_loss": [15, 30]},
}

RESTS = {
    "tutorial_safe_room": {"name": "Tutorial Safe Room", "heal_pct": [0.2, 0.3]},
    "meadow_lark_alcove": {"name": "Meadow Lark Alcove", "heal_pct": [0.2, 0.3]},
    "npc_diner": {"name": "NPC Diner", "heal_pct": [0.2, 0.3]},
    "parked_rail_car": {"name": "Parked Rail Car", "heal_pct": [0.2, 0.3]},
    "bubble_airlock_lounge": {"name": "Bubble Airlock Lounge", "heal_pct": [0.2, 0.3]},
    "abandoned_hunting_blind": {"name": "Abandoned Hunting Blind", "heal_pct": [0.2, 0.3]},
}

TREASURES = {
    "ring_cache": {"name": "Ring Cache", "gold_range": [8, 15],
                   "loot_table": [("goblin_pass_tattoo", 0.4)]},
    "scratch_card_cache": {"name": "Scratch Card Cache", "gold_range": [15, 30],
                            "loot_table": [("gorgons_lucky_pebble", 0.35)]},
    "boxers_upgrade_cache": {"name": "Boxers Upgrade Cache", "gold_range": [18, 32],
                              "loot_table": [("bigboi_boxers_supreme", 0.5)]},
    "cookbook_cache": {"name": "Cookbook Cache", "gold_range": [20, 35],
                        "loot_table": [("dungeon_anarchists_cookbook", 0.4)]},
    "quadrant_supply_cache": {"name": "Quadrant Supply Cache", "gold_range": [25, 40],
                               "loot_table": [("rockards_ring_of_sniping", 0.35)]},
    "battle_rattle_cache": {"name": "Battle Rattle Patch Cache", "gold_range": [30, 50],
                             "loot_table": [("shrink_wand", 0.4)]},
}

ROOM_WEIGHTS = {"fight": 4, "elite": 1, "trap": 1.5, "rest": 1, "treasure": 1.5}
ORDINAL_LABELS = ["The First Passage", "The Second Passage", "The Third Passage"]

FLOORS = [
    {
        "theme": "The Tutorial",
        "monster_pool": ["goblin", "murder_dozer", "bad_llama", "troglodyte"],
        "elite_pool": ["the_hoarder", "the_juicer", "ball_of_swine"],
        "boss": "goblin_war_chieftain",
        "trap_pool": ["rot_sticker_trap"], "rest_pool": ["tutorial_safe_room"],
        "treasure_pool": ["ring_cache"],
        "path_hints": {
            "fight": ["You hear scratching and cackling from a side tunnel."],
            "elite": ["A larger shadow moves behind the rubble - something big is guarding this stretch."],
            "trap": ["Sticky notes are plastered on the walls ahead. They're humming faintly."],
            "rest": ["A door marked with a crawler's chalk sigil - someone's guild outpost."],
            "treasure": ["A glint of something shiny wedged in the collapsed section."],
        },
        "shop": ["crawler_ration", "mana_tonic", "goblin_pass_tattoo"],
    },
    {
        "theme": "Second Floor Sprawl",
        "monster_pool": ["brindle_grub", "danger_dingo", "mind_horror", "feral_clurichaun", "laminak", "kobold"],
        "elite_pool": ["rage_elemental", "ralph_the_frenzied_gerbil"],
        "boss": "krakaren_clone",
        "trap_pool": ["suspicious_wall_rune"], "rest_pool": ["meadow_lark_alcove"],
        "treasure_pool": ["scratch_card_cache"],
        "path_hints": {
            "fight": ["Something skitters just past the edge of your light."],
            "elite": ["The ground itself seems to be breathing nearby."],
            "trap": ["Fresh graffiti on the wall, still dripping."],
            "rest": ["A quiet balcony overlooking the sprawl below."],
            "treasure": ["A torn scratch-card lottery booth, unlooted so far."],
        },
        "shop": ["crawler_ration", "mana_tonic", "gorgons_lucky_pebble"],
    },
    {
        "theme": "The Over City",
        "monster_pool": ["circus_lemur", "giraffe_rider", "undead_performer"],
        "elite_pool": ["heather_the_bear"],
        "boss": "ringmaster_grimaldi",
        "trap_pool": ["pestiferous_vine_snare"], "rest_pool": ["npc_diner"],
        "treasure_pool": ["boxers_upgrade_cache"],
        "path_hints": {
            "fight": ["Circus music drifts from around the corner, off-key and wrong."],
            "elite": ["A tent flap billows - something large is pacing inside."],
            "trap": ["Vines snake across the cobblestones here, twitching."],
            "rest": ["A diner sign flickers, half its neon letters dead."],
            "treasure": ["A prize booth, abandoned mid-carnival."],
        },
        "shop": ["crawler_ration", "mana_tonic", "earth_hobby_potion"],
    },
    {
        "theme": "The Iron Tangle",
        "monster_pool": ["drek", "psycho_sticker", "jikininki", "cave_mudge_bonker", "shock_chomper"],
        "elite_pool": ["gore_gore", "regenerating_gnoll", "krakaren_clone_lesser"],
        "boss": "the_demon_mother",
        "trap_pool": ["runaway_handcart"], "rest_pool": ["parked_rail_car"],
        "treasure_pool": ["cookbook_cache"],
        "path_hints": {
            "fight": ["Rails hum with an approaching engine, or something imitating one."],
            "elite": ["A hulking silhouette works on a stalled train car."],
            "trap": ["An unmanned handcart rattles somewhere close, gaining speed."],
            "rest": ["A parked passenger car, doors wedged open, oddly peaceful."],
            "treasure": ["A conductor's satchel, left behind in the rush."],
        },
        "shop": ["field_ration_supreme", "greater_mana_tonic", "dungeon_anarchists_cookbook"],
    },
    {
        "theme": "The Bubbles",
        "monster_pool": ["dromedarian", "bactrian", "dirigible_gnome", "changeling"],
        "elite_pool": ["denise_goose_mother", "giant_sand_ooze", "orthrus", "emberus"],
        "boss": "lusca",
        "trap_pool": ["collapsing_bubble_seal"], "rest_pool": ["bubble_airlock_lounge"],
        "treasure_pool": ["quadrant_supply_cache"],
        "path_hints": {
            "fight": ["Something large moves beyond the dome's curved wall."],
            "elite": ["A shadow far too big for anything friendly circles overhead."],
            "trap": ["The bubble's seal groans under the water pressure."],
            "rest": ["An airlock lounge, quiet and dry, oddly untouched."],
            "treasure": ["A supply crate wedged against the quadrant wall."],
        },
        "shop": ["field_ration_supreme", "greater_mana_tonic", "rockards_ring_of_sniping"],
    },
    {
        "theme": "The Hunting Grounds",
        "monster_pool": ["hunter", "dinosaur", "odious_creeper", "shambling_berserker"],
        "elite_pool": ["vrah_the_lead_hunter"],
        "boss": "queen_imogen",
        "trap_pool": ["poachers_snare"], "rest_pool": ["abandoned_hunting_blind"],
        "treasure_pool": ["battle_rattle_cache"],
        "path_hints": {
            "fight": ["Underbrush rustles - hunted or hunter, hard to say yet."],
            "elite": ["A trophy rack nearby suggests this hunter is very good at their job."],
            "trap": ["A snare line, near-invisible, strung low across the path."],
            "rest": ["An abandoned blind, camouflage netting still intact."],
            "treasure": ["A cache someone buried in a hurry and never came back for."],
        },
        "shop": ["field_ration_supreme", "greater_mana_tonic", "shrink_wand"],
    },
]

SHOP_PRICES = {
    "crawler_ration": 15, "mana_tonic": 15, "goblin_pass_tattoo": 40,
    "gorgons_lucky_pebble": 55, "earth_hobby_potion": 30,
    "field_ration_supreme": 35, "greater_mana_tonic": 35,
    "dungeon_anarchists_cookbook": 70, "rockards_ring_of_sniping": 90, "shrink_wand": 110,
}

CATALOG = {
    "items": {iid: {"name": d["name"], "type": d["type"], "description": d.get("description", "")}
              for iid, d in ITEMS.items()},
    "skills": {sid: {"name": d["name"], "mana_cost": d.get("mana_cost", 0), "cooldown": d.get("cooldown", 0),
                      "description": d.get("description", "")}
               for sid, d in SKILLS.items()},
    "curses": {cid: {"name": d["name"], "description": d["description"]} for cid, d in CURSES.items()},
    "boons": {bid: {"name": d["name"], "description": d["description"]} for bid, d in BOONS.items()},
    "monsters": {mid: {"name": d["name"]} for mid, d in MONSTERS.items()},
}

SYSTEM_PROMPT = """You are the narration voice for THE DUNGEON CRAWLER CARL SHOW, a reality-TV \
broadcast beamed across the galaxy from inside an alien-run dungeon. You never decide what happens - a \
separate system already resolved the numbers. Your only job is to narrate, in character, what the given \
EVENT(S) mean.

Always respond in exactly this format, one line per voice, nothing else:
ANNOUNCER: <1-3 punchy, snarky, over-the-top game-show-host sentences reacting to the event(s). Call \
the player "Carl" or "Crawler." Refer to the dungeon as "the dungeon," "the Crawl," or "the Show." Dark \
humor is fine; huge show-biz energy is the goal. You may use at most one bracketed sound cue like \
[AIR HORN] or [CROWD GASPS].
CAT: <0-1 short sentence from Donut, Carl's cat, who is haughty, food-and-attention-obsessed, refers to \
herself in the third person or as "Princess Donut," and is quietly a real combat asset despite the \
attitude - only include this line if she'd plausibly react, omit it otherwise. When the event list \
includes a "cat_assist" entry, Donut actually helped in the fight - narrate that as a real action, not \
just banter.

Hard rules:
- Never state, imply, or invent any number (damage, HP, gold, XP, chance) that is not already present in \
the EVENT(S) or STATE given to you.
- Never invent items, monsters, or outcomes beyond what's described in the EVENT(S).
- Keep it short - this is one beat in an ongoing broadcast, not a scene.
- Never break the ANNOUNCER:/CAT: line format, and never add any other lines or headers.
"""

OPENING_LINE = ("Ladies, gentlemen, and things that used to be either: welcome back to THE DUNGEON "
                "CRAWLER CARL SHOW! Our next Crawler stumbles in wearing nothing but his Enchanted "
                "BigBoi Boxers and a bad attitude, flanked by one deeply unimpressed cat who insists on "
                "being called Princess Donut. Let's see how far boxers-and-bravado gets him. Floor One... GO!")

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
        "version": 2,
        "created_at": now,
        "updated_at": now,
        "turn_number": 0,
        "status": "in_progress",
        "player": {
            "name": "Carl",
            "level": 1, "xp": 0, "xp_to_next": 25,
            "hp": 40, "hp_max": 40, "mana": 10, "mana_max": 10, "gold": 20,
            "stats": {"str": 5, "agi": 5, "end": 5, "int": 5, "luck": 5},
            "equipped": {"weapon": "scrap_pipe", "armor": "bigboi_boxers", "trinket": None},
            "inventory": [{"id": "crawler_ration", "qty": 3}],
            "skills": ["basic_attack", "powerful_strike", "donuts_diversion"],
            "skill_cooldowns": {"powerful_strike": 0, "donuts_diversion": 0},
            "curses": [],
            "boons": [],
        },
        "dungeon": {"floor": 1, "floor_theme": FLOORS[0]["theme"], "stage": "path_select",
                    "room_index": 0, "rooms_required": random.randint(3, 4),
                    "pending_paths": [], "whim_used": False},
        "combat": None,
        "narration_log": [{"turn": 0, "speaker": "announcer", "text": OPENING_LINE}],
    }
    generate_path_options(GAME_STATE)
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
            if (loaded.get("version") == 2 and "player" in loaded
                    and "dungeon" in loaded and "narration_log" in loaded):
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


def generate_path_options(state, events=None):
    dungeon = state["dungeon"]
    floor = FLOORS[dungeon["floor"] - 1]
    room_types = list(ROOM_WEIGHTS.keys())
    weights = [ROOM_WEIGHTS[t] for t in room_types]
    n = random.choice([2, 3])
    chosen = random.choices(room_types, weights=weights, k=n)
    for _ in range(5):
        if len(set(chosen)) > 1:
            break
        chosen = random.choices(room_types, weights=weights, k=n)
    options = []
    for i, room_type in enumerate(chosen):
        hint = random.choice(floor["path_hints"][room_type])
        options.append({"room_type": room_type, "label": ORDINAL_LABELS[i], "hint": hint})
    dungeon["pending_paths"] = options
    if events is not None:
        events.append({"type": "path_options", "options": [{"hint": o["hint"]} for o in options]})


def advance_room(state, events):
    dungeon = state["dungeon"]
    dungeon["room_index"] += 1
    if dungeon["room_index"] >= dungeon["rooms_required"]:
        dungeon["stage"] = "boss"
        events.append({"type": "stage_change", "stage": "boss"})
    else:
        dungeon["stage"] = "path_select"
        generate_path_options(state, events)


def handle_monster_death(state, events):
    player = state["player"]
    dungeon = state["dungeon"]
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
    if monster.get("boss"):
        dungeon["stage"] = "reward"
        dungeon["whim_used"] = False
        events.append({"type": "stage_change", "stage": "reward"})
    else:
        advance_room(state, events)


def handle_choose_path(state, payload, events):
    dungeon = state["dungeon"]
    if dungeon["stage"] != "path_select" or state["combat"] is not None:
        events.append({"type": "action_failed", "reason": "no path to choose"})
        return
    idx = payload.get("option_index")
    paths = dungeon.get("pending_paths", [])
    if not isinstance(idx, int) or idx < 0 or idx >= len(paths):
        events.append({"type": "action_failed", "reason": "invalid path"})
        return
    option = paths[idx]
    dungeon["pending_paths"] = []
    floor = FLOORS[dungeon["floor"] - 1]
    room_type = option["room_type"]

    if room_type in ("fight", "elite"):
        pool = floor["monster_pool"] if room_type == "fight" else floor["elite_pool"]
        monster_id = random.choice(pool)
        m = MONSTERS[monster_id]
        state["combat"] = {"active": True, "monster_id": monster_id, "monster_hp": m["hp"],
                            "monster_hp_max": m["hp"], "round": 1,
                            "phase_2_triggered": False}
        events.append({"type": "encounter_start", "monster_name": m["name"],
                        "boss": False, "elite": room_type == "elite"})
    elif room_type == "trap":
        trap = TRAPS[random.choice(floor["trap_pool"])]
        ev = {"type": "trap_triggered", "trap_name": trap["name"]}
        if "hp_loss" in trap:
            loss = random.randint(*trap["hp_loss"])
            state["player"]["hp"] = max(0, state["player"]["hp"] - loss)
            ev["hp_lost"] = loss
        if "gold_loss" in trap:
            loss = min(state["player"]["gold"], random.randint(*trap["gold_loss"]))
            state["player"]["gold"] -= loss
            ev["gold_lost"] = loss
        events.append(ev)
        if state["player"]["hp"] <= 0:
            state["status"] = "defeat"
            events.append({"type": "defeat"})
            return
        advance_room(state, events)
    elif room_type == "rest":
        rest = RESTS[random.choice(floor["rest_pool"])]
        player = state["player"]
        missing = player["hp_max"] - player["hp"]
        heal = round(missing * random.uniform(*rest["heal_pct"]))
        player["hp"] = min(player["hp_max"], player["hp"] + heal)
        events.append({"type": "rest_stop", "rest_name": rest["name"], "heal": heal})
        advance_room(state, events)
    elif room_type == "treasure":
        treasure = TREASURES[random.choice(floor["treasure_pool"])]
        player = state["player"]
        gold = random.randint(*treasure["gold_range"])
        player["gold"] += gold
        loot_names = []
        for item_id, chance in treasure.get("loot_table", []):
            if random.random() < chance:
                loot_names.append(grant_item(player, item_id))
        events.append({"type": "treasure_found", "treasure_name": treasure["name"],
                        "gold": gold, "loot": loot_names})
        advance_room(state, events)


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

    if combat.pop("monster_stunned", False):
        events.append({"type": "monster_distracted", "monster_name": monster["name"]})
        combat["round"] += 1
        return

    result = resolve_hit(monster["power"], 0, monster["agi"], 0,
                          get_armor_def(player), player["stats"]["agi"])
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
    if state["combat"] is not None or dungeon["stage"] != "boss":
        events.append({"type": "action_failed", "reason": "nothing to explore right now"})
        return
    floor = FLOORS[dungeon["floor"] - 1]
    monster_id = floor["boss"]
    m = MONSTERS[monster_id]
    state["combat"] = {"active": True, "monster_id": monster_id, "monster_hp": m["hp"],
                        "monster_hp_max": m["hp"], "round": 1,
                        "phase_2_triggered": False}
    events.append({"type": "encounter_start", "monster_name": m["name"], "boss": True})


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

    if skill_id == "donuts_diversion":
        heal = skill.get("heal", 0)
        player["hp"] = min(player["hp_max"], player["hp"] + heal)
        combat["monster_stunned"] = True
        events.append({"type": "skill_used", "skill": skill["name"], "heal": heal})
    elif skill_id == "protective_shell":
        heal = skill["heal"]
        player["hp"] = min(player["hp_max"], player["hp"] + heal)
        combat["player_buff_mult"] = 1.3
        events.append({"type": "skill_used", "skill": skill["name"], "heal": heal})
    else:
        item_consumed = None
        if skill_id == "bomb_toss":
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
        if skill_id == "smush" and combat["monster_hp"] <= combat["monster_hp_max"] * 0.3:
            dmg_mult *= 1.5
        effective_def = monster["def"] * (1 - skill.get("def_pierce", 0.0))
        result = resolve_hit(get_weapon_power(player), player["stats"]["str"], player["stats"]["agi"],
                              player["stats"]["luck"], effective_def, monster["agi"],
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
    mana_restore = item.get("mana", 0)
    player["hp"] = min(player["hp_max"], player["hp"] + heal)
    player["mana"] = min(player["mana_max"], player["mana"] + mana_restore)
    entry["qty"] -= 1
    if entry["qty"] <= 0:
        player["inventory"].remove(entry)
    ev = {"type": "item_used", "item": item["name"]}
    if heal:
        ev["heal"] = heal
    if mana_restore:
        ev["mana_restored"] = mana_restore
    events.append(ev)
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
    if dungeon["floor"] >= 6:
        state["status"] = "victory"
        events.append({"type": "victory"})
        return
    for curse_id in player["curses"]:
        delta = CURSES[curse_id].get("gold_per_floor")
        if delta:
            player["gold"] = max(0, player["gold"] + delta)
    dungeon["floor"] += 1
    dungeon["floor_theme"] = FLOORS[dungeon["floor"] - 1]["theme"]
    dungeon["room_index"] = 0
    dungeon["rooms_required"] = random.randint(3, 4)
    dungeon["stage"] = "path_select"
    events.append({"type": "floor_advance", "floor": dungeon["floor"], "theme": dungeon["floor_theme"]})
    generate_path_options(state, events)


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
            if skill_id == "bomb_toss" and not player["inventory"]:
                continue
            choices.append(f"skill:{skill_id}")
    elif dungeon["stage"] == "path_select":
        for i in range(len(dungeon.get("pending_paths", []))):
            choices.append(f"choose_path:{i}")
    elif dungeon["stage"] == "boss":
        choices.append("explore")
    elif dungeon["stage"] == "reward":
        floor = FLOORS[dungeon["floor"] - 1]
        for item_id in floor["shop"]:
            if SHOP_PRICES.get(item_id, 10 ** 9) <= player["gold"]:
                choices.append(f"shop_buy:{item_id}")
        if not dungeon.get("whim_used"):
            choices.append("shop_whim")
        choices.append("shop_leave")
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
        elif req.type == "choose_path":
            handle_choose_path(state, req.payload, events)
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
  [data-tip] { position: relative; cursor: help; }
  [data-tip]::after {
    content: attr(data-tip);
    position: absolute; bottom: 125%; left: 0;
    background: #1e2129; border: 1px solid var(--panel-edge); color: var(--ink);
    padding: 6px 10px; border-radius: 6px; font-size: 0.72rem; line-height: 1.35;
    white-space: normal; width: max-content; max-width: 220px; text-align: left;
    opacity: 0; visibility: hidden; pointer-events: none; transition: opacity 0.1s ease;
    z-index: 50; box-shadow: 0 4px 14px rgba(0,0,0,0.45);
  }
  [data-tip]:hover::after { opacity: 1; visibility: visible; }
  .action-btn[data-tip] { cursor: pointer; }
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
    if (parts[0] === "choose_path") return lastData.dungeon.pending_paths[parseInt(parts[1])].label;
    return choice;
  }

  function titleFor(choice) {
    if (choice === "attack") return CATALOG.skills.basic_attack.description || "";
    const parts = choice.split(":");
    if (parts[0] === "skill") return (CATALOG.skills[parts[1]] || {}).description || "";
    if (parts[0] === "use_item") return (CATALOG.items[parts[1]] || {}).description || "";
    if (parts[0] === "shop_buy") return (CATALOG.items[parts[1]] || {}).description || "";
    if (parts[0] === "choose_path") return lastData.dungeon.pending_paths[parseInt(parts[1])].hint;
    return "";
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
      if (id) li.dataset.tip = CATALOG.items[id].description;
      eq.appendChild(li);
    });

    const inv = document.getElementById("inventoryList");
    inv.innerHTML = "";
    p.inventory.forEach(function (entry) {
      const item = CATALOG.items[entry.id];
      const li = document.createElement("li");
      if (item.description) li.dataset.tip = item.description;
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
      if (s.description) li.dataset.tip = s.description;
      sk.appendChild(li);
    });

    const curseEl = document.getElementById("curseList");
    curseEl.innerHTML = "";
    p.curses.forEach(function (cid) {
      const c = CATALOG.curses[cid];
      const span = document.createElement("span");
      span.className = "tag curse";
      span.dataset.tip = c.description;
      span.textContent = c.name;
      curseEl.appendChild(span);
    });

    const boonEl = document.getElementById("boonList");
    boonEl.innerHTML = "";
    p.boons.forEach(function (bid) {
      const b = CATALOG.boons[bid];
      const span = document.createElement("span");
      span.className = "tag boon";
      span.dataset.tip = b.description;
      span.textContent = b.name;
      boonEl.appendChild(span);
    });

    document.getElementById("floorBanner").textContent =
      "FLOOR " + data.dungeon.floor + " of 6 \\u2014 " + data.dungeon.floor_theme +
      (data.dungeon.stage === "boss" && !data.combat ? " \\u2014 BOSS AHEAD" :
       data.dungeon.stage === "path_select" ? " \\u2014 Room " + (data.dungeon.room_index + 1) + "/" + data.dungeon.rooms_required : "");

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
      const tip = titleFor(choice);
      if (tip) btn.dataset.tip = tip;
      btn.addEventListener("click", function () { doAction(choice); });
      actions.appendChild(btn);
    });

    const overlay = document.getElementById("overlay");
    if (data.status === "victory" || data.status === "defeat") {
      overlay.style.display = "flex";
      document.getElementById("overlayText").textContent =
        data.status === "victory" ? "YOU SURVIVED THE CRAWL!" : "THE SHOW REGRETS TO INFORM YOU: YOU DIED.";
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
      } else if (parts[0] === "choose_path") {
        type = "choose_path";
        payload = { option_index: parseInt(parts[1]) };
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
    if (!confirm("Start a new Crawl? This wipes your current run.")) return;
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
