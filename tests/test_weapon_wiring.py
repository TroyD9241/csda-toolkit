"""Tests for weapon models and weapon name normalization."""

import pytest
from csda_toolkit.ingest.bundle import _normalize_item_name, _ITEM_NAME_TO_WEAPON_KEY
from csda_toolkit.parsing.constants import WEAPON_CATEGORY, weapon_category


class TestWeaponNormalization:
    """Test _normalize_item_name handles all CS2 item purchase names."""

    def test_all_purchase_item_names_covered(self):
        """Every item_name from item_purchase event maps to a weapon_key."""
        # Known item names from demoparser2 item_purchase events
        item_names = [
            "AK-47", "AWP", "Desert Eagle", "FAMAS", "Five-SeveN",
            "Flashbang", "Galil AR", "HE Grenade", "Incendiary Grenade",
            "Kevlar & Helmet", "Kevlar Vest", "M4A1-S", "M4A4",
            "MP9", "Molotov", "P250", "Smoke Grenade", "Tec-9", "Zeus x27",
        ]
        for name in item_names:
            result = _normalize_item_name(name)
            assert result != "", f"{name} normalized to empty string"
            assert " " not in result, f"{name} → '{result}' still contains spaces"

    def test_grenade_names(self):
        assert _normalize_item_name("Flashbang") == "flashbang"
        assert _normalize_item_name("HE Grenade") == "he_grenade"
        assert _normalize_item_name("Smoke Grenade") == "smoke_grenade"
        assert _normalize_item_name("Molotov") == "molotov"
        assert _normalize_item_name("Incendiary Grenade") == "incendiary"
        assert _normalize_item_name("Decoy Grenade") == "decoy"
        assert _normalize_item_name("Tactical Awareness Grenade") == "tag_grenade"

    def test_armor_names(self):
        assert _normalize_item_name("Kevlar & Helmet") == "kevlar_helmet"
        assert _normalize_item_name("Kevlar Vest") == "kevlar"

    def test_utility_names(self):
        assert _normalize_item_name("Defuse Kit") == "defuse_kit"

    def test_weapon_names(self):
        assert _normalize_item_name("AK-47") == "ak_47"
        assert _normalize_item_name("M4A4") == "m4a4"
        assert _normalize_item_name("M4A1-S") == "m4a1_s"
        assert _normalize_item_name("AWP") == "awp"
        assert _normalize_item_name("Galil AR") == "galil_ar"
        assert _normalize_item_name("FAMAS") == "famas"
        assert _normalize_item_name("SG 553") == "sg_553"
        assert _normalize_item_name("SSG 08") == "ssg_08"
        assert _normalize_item_name("Tec-9") == "tec_9"
        assert _normalize_item_name("P250") == "p250"
        assert _normalize_item_name("Desert Eagle") == "desert_eagle"
        assert _normalize_item_name("Zeus x27") == "zeus_x27"
        assert _normalize_item_name("C4 Explosive") == "c4"

    def test_pistol_names(self):
        assert _normalize_item_name("Five-SeveN") == "five_seven"
        assert _normalize_item_name("Glock-18") == "glock_18"
        assert _normalize_item_name("Dual Berettas") == "dual_berettas"
        assert _normalize_item_name("P2000") == "hkp2000"
        assert _normalize_item_name("CZ75 Auto") == "cz75_auto"
        assert _normalize_item_name("Roteador") == "revolver"


class TestWeaponCategory:
    """Test WEAPON_CATEGORY covers all expected weapons."""

    def test_pistols_categorized(self):
        pistols = ["desert_eagle", "glock_18", "p250", "tec_9", "hkp2000", "five_seven", "revolver", "cz75_auto"]
        for w in pistols:
            assert weapon_category(w) == "pistol", f"{w} should be pistol"

    def test_rifles_categorized(self):
        rifles = ["ak_47", "m4a4", "m4a1_s", "aug", "sg_553", "galil_ar", "famas"]
        for w in rifles:
            assert weapon_category(w) == "rifle", f"{w} should be rifle"

    def test_snipers_categorized(self):
        for w in ["awp", "ssg_08", "scar_20", "g3sg1"]:
            assert weapon_category(w) == "sniper", f"{w} should be sniper"

    def test_smgs_categorized(self):
        for w in ["mp9", "mp7", "mp5_sd", "mac_10", "p90", "pp_bizon", "ump_45"]:
            assert weapon_category(w) == "smg", f"{w} should be smg"

    def test_grenades_categorized(self):
        for w in ["flashbang", "he_grenade", "smoke_grenade", "molotov", "decoy", "incendiary", "tag_grenade"]:
            assert weapon_category(w) == "grenade", f"{w} should be grenade"

    def test_armor_categorized(self):
        assert weapon_category("kevlar") == "armor"
        assert weapon_category("kevlar_helmet") == "armor"

    def test_utility_categorized(self):
        assert weapon_category("defuse_kit") == "utility"

    def test_explosive_categorized(self):
        assert weapon_category("c4") == "explosive"

    def test_equipment_categorized(self):
        assert weapon_category("zeus_x27") == "equipment"
        assert weapon_category("taser") == "equipment"

    def test_melee_categorized(self):
        for w in ["bayonet", "karambit", "gut_knife", "flip_knife", "m9_bayonet", "classic_knife"]:
            assert weapon_category(w) == "melee", f"{w} should be melee"

    def test_gloves_categorized(self):
        for w in ["sporty_gloves", "motorcycle_gloves", "specialist_gloves", "studded_hydra_gloves"]:
            assert weapon_category(w) == "gloves", f"{w} should be gloves"

    def test_unknown_weapon_returns_unknown(self):
        assert weapon_category("not_a_weapon") == "unknown"
        assert weapon_category("") == "unknown"


class TestWeaponKeyMapping:
    """Test _ITEM_NAME_TO_WEAPON_KEY is complete for all purchase names."""

    def test_all_keys_unique(self):
        # Multiple purchase item names can legitimately map to the same weapon key.
        # Known duplicates: "HE Grenade" and "High Explosive Grenade" → "he_grenade"
        KNOWN_DUPLICATES = {
            ("HE Grenade", "High Explosive Grenade", "he_grenade"),
        }
        known_pairs = {(n1, n2) for n1, n2, _ in KNOWN_DUPLICATES} | {(n2, n1) for n1, n2, _ in KNOWN_DUPLICATES}
        from csda_toolkit.parsing.constants import WEAPON_DEFINDEX_TO_NAME
        valid_keys = set(WEAPON_DEFINDEX_TO_NAME.values())
        seen: dict[str, str] = {}
        for item_name, weapon_key in _ITEM_NAME_TO_WEAPON_KEY.items():
            if weapon_key in seen and (item_name, seen[weapon_key]) not in known_pairs:
                assert False, (
                    f"Weapon key '{weapon_key}' mapped from multiple item names: "
                    f"'{seen[weapon_key]}' and '{item_name}'"
                )
            seen.setdefault(weapon_key, item_name)

    def test_no_empty_values(self):
        for k, v in _ITEM_NAME_TO_WEAPON_KEY.items():
            assert v != "", f"Empty weapon_key for item_name '{k}'"
