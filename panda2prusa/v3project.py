"""PrusaSlicer 3.x native project format (``Metadata/PrusaSlicer3_project.json``).

PrusaSlicer 3.x opens a 3MF through its new project loader when the model's
``Application`` metadata is a 3.x version; that loader reads this JSON file and
never reads ``Metadata/Slic3r_PE.config``. The JSON pins the project to a printer
hardware configuration (``preset.hw_config``) and to the selected presets
(``preset.printer/print/tools/materials``). Both are validated structurally on
load (``is_valid<HwPrinterConfig>`` / ``load_preset_metadata`` in the v3 source),
and an empty ``hw_config.config_id`` makes the file degrade to geometry-only
(``FileLoadingLogic::convert_to_project``). There is no generic/neutral mode in
the format - a v3 project is by design tied to a printer configuration.

The identity embedded below is the Prusa XL+ 5T (5x 0.4 HF) as saved by
PrusaSlicer 3.0.0-alpha13 (reference: ``out_diamondback_v8_v3_prusa.3mf`` in the
repo root). It is printer-*model*-level identity, not machine-level: the
per-machine ``physical_printer`` entry is deliberately not written. The
``configuration`` section is pure values and travels to any installation; only
the preset labels may fail to resolve on a different machine.

To re-derive the constants after a v3 update: save any project in PrusaSlicer 3.x
and copy ``preset`` from its ``Metadata/PrusaSlicer3_project.json``.
"""

from __future__ import annotations

import copy
from typing import Dict, List, Optional, Sequence, Tuple

from .prusa_config import VECTOR_TYPES, PrusaConfig, option_type, unescape_strings

V3_PROJECT_FILE = "Metadata/PrusaSlicer3_project.json"
V3_APPLICATION = "PrusaSlicer-3.0.0"
LEGACY_APPLICATION = "PrusaSlicer-2.9.7"

# -- v3 FFF domain: which settings live in which configuration location --------
# Key sets as written by PrusaSlicer 3.0.0-alpha13 (see module docstring). A key
# may appear in several locations: print_settings holds the scalar default and
# toolprint_settings / filament_settings hold the per-tool / per-filament vector.
# Unknown keys fall through to print_settings, where v3 ignores them (ExtraKey
# issues are non-fatal and not surfaced).

TOOL_KEYS = frozenset((
    "bottom_solid_layers", "bottom_solid_min_thickness", "bridge_acceleration",
    "bridge_flow_ratio", "bridge_speed", "brim_separation", "default_acceleration",
    "deretract_speed", "dont_support_bridges", "elefant_foot_compensation",
    "enable_dynamic_overhang_speeds", "external_perimeter_acceleration",
    "external_perimeter_extrusion_width", "external_perimeter_speed",
    "external_perimeters_first", "extra_perimeters", "extrusion_width",
    "fill_density", "fill_pattern", "first_layer_acceleration",
    "first_layer_acceleration_over_raft", "first_layer_extrusion_width",
    "first_layer_height", "first_layer_infill_speed", "first_layer_solid_infill_speed",
    "first_layer_speed", "first_layer_speed_over_raft", "gap_fill_enabled",
    "gap_fill_speed", "gcode_resolution", "infill_acceleration", "infill_anchor",
    "infill_anchor_max", "infill_every_layers", "infill_extrusion_width",
    "infill_overlap", "infill_speed", "max_layer_height", "max_print_speed",
    "max_volumetric_extrusion_rate_slope_negative", "max_volumetric_extrusion_rate_slope_positive",
    "max_volumetric_speed", "min_bead_width", "min_feature_size", "min_layer_height",
    "only_retract_when_crossing_perimeters", "over_bridge_speed", "overhang_speed_0",
    "overhang_speed_1", "overhang_speed_2", "overhang_speed_3", "overhangs",
    "perimeter_acceleration", "perimeter_extrusion_width", "perimeter_speed",
    "perimeters", "raft_contact_distance", "raft_expansion", "raft_first_layer_density",
    "raft_first_layer_expansion", "retract_before_travel", "retract_before_wipe",
    "retract_layer_change", "retract_length", "retract_length_toolchange",
    "retract_lift", "retract_lift_above", "retract_lift_below",
    "retract_restart_extra", "retract_restart_extra_toolchange", "retract_speed",
    "seam_position", "small_perimeter_speed", "solid_infill_acceleration",
    "solid_infill_extrusion_width", "solid_infill_speed", "support_material_angle",
    "support_material_bottom_contact_distance", "support_material_bottom_interface_layers",
    "support_material_closing_radius", "support_material_contact_distance",
    "support_material_enforce_layers", "support_material_extrusion_width",
    "support_material_first_layer_density", "support_material_first_layer_expansion",
    "support_material_interface_contact_loops", "support_material_interface_layers",
    "support_material_interface_pattern", "support_material_interface_spacing",
    "support_material_interface_speed", "support_material_pattern",
    "support_material_spacing", "support_material_speed", "support_material_style",
    "support_material_synchronize_layers", "support_material_threshold",
    "support_material_with_sheath", "support_material_xy_spacing", "support_tree_angle",
    "support_tree_angle_slow", "support_tree_branch_diameter",
    "support_tree_branch_diameter_angle", "support_tree_branch_distance",
    "support_tree_tip_diameter", "support_tree_top_rate", "thick_bridges",
    "top_infill_extrusion_width", "top_one_perimeter_type",
    "top_solid_infill_acceleration", "top_solid_infill_speed", "top_solid_layers",
    "top_solid_min_thickness", "travel_acceleration", "travel_max_lift",
    "travel_ramping_lift", "travel_short_distance_acceleration", "travel_slope",
    "travel_speed", "travel_speed_z", "wipe", "wipe_tower_bridging",
    "wipe_tower_extra_spacing",
))

PRINT_KEYS_V3 = frozenset((
    "arc_fitting", "automatic_extrusion_widths", "automatic_infill_combination",
    "automatic_infill_combination_max_layer_height", "avoid_crossing_curled_overhangs",
    "avoid_crossing_perimeters", "avoid_crossing_perimeters_max_detour",
    "bed_temperature_extruder", "bottom_fill_pattern", "bottom_solid_layers",
    "bottom_solid_min_thickness", "bridge_acceleration", "bridge_angle",
    "bridge_flow_ratio", "bridge_speed", "brim_separation", "brim_type", "brim_width",
    "complete_objects", "custom_parameters_print", "default_acceleration",
    "default_material", "default_tool_print", "deretract_speed", "dont_support_bridges",
    "draft_shield", "elefant_foot_compensation", "enable_dynamic_overhang_speeds",
    "ensure_vertical_shell_thickness", "external_perimeter_acceleration",
    "external_perimeter_extrusion_width", "external_perimeter_speed",
    "external_perimeters_first", "extra_perimeters", "extra_perimeters_on_overhangs",
    "extrusion_width", "fill_angle", "fill_density", "fill_pattern",
    "first_layer_acceleration", "first_layer_acceleration_over_raft",
    "first_layer_external_perimeter_speed", "first_layer_extrusion_width",
    "first_layer_gap_fill_speed", "first_layer_height", "first_layer_infill_speed",
    "first_layer_perimeter_speed", "first_layer_solid_infill_speed", "first_layer_speed",
    "first_layer_speed_over_raft", "first_layer_support_material_speed",
    "first_layer_top_solid_infill_speed", "fuzzy_skin", "fuzzy_skin_point_dist",
    "fuzzy_skin_thickness", "gap_fill_enabled", "gap_fill_speed", "gcode_comments",
    "gcode_label_objects", "gcode_resolution", "gcode_substitutions",
    "infill_acceleration", "infill_anchor", "infill_anchor_max", "infill_every_layers",
    "infill_extruder", "infill_extrusion_width", "infill_first", "infill_overlap",
    "infill_speed", "interface_shells", "interlocking_beam",
    "interlocking_beam_layer_count", "interlocking_beam_width",
    "interlocking_boundary_avoidance", "interlocking_depth", "interlocking_orientation",
    "ironing", "ironing_flowrate", "ironing_spacing", "ironing_speed", "ironing_type",
    "layer_height", "max_layer_height", "max_print_speed",
    "max_volumetric_extrusion_rate_slope_negative",
    "max_volumetric_extrusion_rate_slope_positive", "max_volumetric_speed",
    "min_bead_width", "min_feature_size", "min_layer_height", "min_skirt_length",
    "mmu_segmented_region_interlocking_depth", "mmu_segmented_region_max_width",
    "notes", "only_one_perimeter_first_layer", "only_retract_when_crossing_perimeters",
    "ooze_prevention", "output_filename_format", "over_bridge_speed", "overhang_speed_0",
    "overhang_speed_1", "overhang_speed_2", "overhang_speed_3", "overhangs",
    "perimeter_acceleration", "perimeter_extruder", "perimeter_extrusion_width",
    "perimeter_generator", "perimeter_speed", "perimeters", "post_process",
    "raft_contact_distance", "raft_expansion", "raft_first_layer_density",
    "raft_first_layer_expansion", "raft_layers", "resolution", "retract_before_travel",
    "retract_before_wipe", "retract_layer_change", "retract_length",
    "retract_length_toolchange", "retract_lift", "retract_lift_above",
    "retract_lift_below", "retract_restart_extra", "retract_restart_extra_toolchange",
    "retract_speed", "scarf_seam_entire_loop", "scarf_seam_length",
    "scarf_seam_max_segment_length", "scarf_seam_on_inner_perimeters",
    "scarf_seam_only_on_smooth", "scarf_seam_placement", "scarf_seam_start_height",
    "seam_gap_distance", "seam_position", "single_extruder_multi_material_priming",
    "skirt_distance", "skirt_height", "skirts", "slice_closing_radius", "slicing_mode",
    "small_perimeter_speed", "solid_infill_acceleration", "solid_infill_below_area",
    "solid_infill_every_layers", "solid_infill_extruder", "solid_infill_extrusion_width",
    "solid_infill_speed", "spiral_vase", "staggered_inner_seams",
    "standby_temperature_delta", "support_material", "support_material_angle",
    "support_material_auto", "support_material_bottom_contact_distance",
    "support_material_bottom_interface_layers", "support_material_buildplate_only",
    "support_material_closing_radius", "support_material_contact_distance",
    "support_material_enforce_layers", "support_material_extruder",
    "support_material_extrusion_width", "support_material_first_layer_density",
    "support_material_first_layer_expansion",
    "support_material_interface_contact_loops", "support_material_interface_extruder",
    "support_material_interface_layers", "support_material_interface_pattern",
    "support_material_interface_spacing", "support_material_interface_speed",
    "support_material_pattern", "support_material_spacing", "support_material_speed",
    "support_material_style", "support_material_synchronize_layers",
    "support_material_threshold", "support_material_with_sheath",
    "support_material_xy_spacing", "support_tree_angle", "support_tree_angle_slow",
    "support_tree_branch_diameter", "support_tree_branch_diameter_angle",
    "support_tree_branch_diameter_double_wall", "support_tree_branch_distance",
    "support_tree_tip_diameter", "support_tree_top_rate", "thick_bridges", "thin_walls",
    "toolchange_ordering", "top_fill_pattern", "top_infill_extrusion_width",
    "top_one_perimeter_type", "top_solid_infill_acceleration", "top_solid_infill_speed",
    "top_solid_layers", "top_solid_min_thickness", "travel_acceleration",
    "travel_lift_before_obstacle", "travel_max_lift", "travel_ramping_lift",
    "travel_short_distance_acceleration", "travel_slope", "travel_speed",
    "travel_speed_z", "wall_distribution_count", "wall_transition_angle",
    "wall_transition_filter_deviation", "wall_transition_length", "wipe", "wipe_tower",
    "wipe_tower_acceleration", "wipe_tower_bridging", "wipe_tower_brim_width",
    "wipe_tower_cone_angle", "wipe_tower_deretraction_spread_ratio",
    "wipe_tower_extra_flow", "wipe_tower_extra_spacing", "wipe_tower_extruder",
    "wipe_tower_max_purge_speed", "wipe_tower_no_sparse_layers", "wipe_tower_width",
    "xy_size_compensation",
))

FILAMENT_KEYS_V3 = frozenset((
    "bed_temperature", "bridge_fan_speed", "chamber_minimal_temperature",
    "chamber_temperature", "cooling", "cooling_perimeter_transition_distance",
    "cooling_slowdown_logic", "custom_parameters_filament", "disable_fan_first_layers",
    "enable_dynamic_fan_speeds", "end_filament_gcode", "extrusion_multiplier",
    "fan_always_on", "fan_below_layer_time", "filament_abrasive", "filament_colour",
    "filament_cooling_final_speed", "filament_cooling_initial_speed",
    "filament_cooling_moves", "filament_cost", "filament_density",
    "filament_diameter", "filament_flush_speed", "filament_flush_volume",
    "filament_infill_max_crossing_speed", "filament_infill_max_speed",
    "filament_loading_speed", "filament_loading_speed_start",
    "filament_max_volumetric_speed", "filament_minimal_purge_on_wipe_tower",
    "filament_multitool_ramming", "filament_multitool_ramming_flow",
    "filament_multitool_ramming_volume", "filament_notes", "filament_purge_multiplier",
    "filament_ramming_initial_delay", "filament_ramming_parameters",
    "filament_ramming_temperature_delta", "filament_shrinkage_compensation_xy",
    "filament_shrinkage_compensation_z", "filament_soluble", "filament_spool_weight",
    "filament_stamping_distance", "filament_stamping_loading_speed",
    "filament_toolchange_delay", "filament_type", "filament_unloading_speed",
    "filament_unloading_speed_start", "filament_vendor", "first_layer_bed_temperature",
    "first_layer_temperature", "full_fan_speed_layer", "idle_temperature",
    "max_fan_speed", "min_fan_speed", "min_print_speed", "overhang_fan_speed_0",
    "overhang_fan_speed_1", "overhang_fan_speed_2", "overhang_fan_speed_3",
    "pressure_advance", "pressure_advance_value", "retract_before_wipe",
    "retract_length", "retract_length_toolchange", "retract_lift",
    "slowdown_below_layer_time", "start_filament_gcode", "temperature",
    "travel_max_lift", "travel_ramping_lift", "travel_slope", "wipe",
))

PRINTER_KEYS_V3 = frozenset((
    "autoemit_temperature_commands", "bed_custom_model", "bed_custom_texture",
    "bed_shape", "before_layer_gcode", "between_objects_gcode", "binary_gcode",
    "color_change_gcode", "cooling_tube_length", "cooling_tube_retraction",
    "custom_parameters_printer", "default_print", "enable_pressure_advance_during_ramming",
    "end_gcode", "extra_loading_move", "extruder_clearance_height",
    "extruder_clearance_radius", "extruder_offset", "filament_change_time",
    "gcode_flavor", "high_current_on_filament_swap", "layer_gcode",
    "machine_limits_usage", "machine_max_acceleration_e",
    "machine_max_acceleration_extruding", "machine_max_acceleration_retracting",
    "machine_max_acceleration_travel", "machine_max_acceleration_x",
    "machine_max_acceleration_y", "machine_max_acceleration_z",
    "machine_max_feedrate_e", "machine_max_feedrate_x", "machine_max_feedrate_y",
    "machine_max_feedrate_z", "machine_max_jerk_e", "machine_max_jerk_x",
    "machine_max_jerk_y", "machine_max_jerk_z", "machine_max_junction_deviation",
    "machine_min_extruding_rate", "machine_min_travel_rate", "max_print_height",
    "multimaterial_purging", "parking_pos_retraction", "pause_print_gcode",
    "prefer_clockwise_movements", "printer_model", "printer_notes",
    "printer_technology", "printer_variant", "printer_vendor", "remaining_times",
    "silent_mode", "single_extruder_multi_material", "start_gcode",
    "stuck_filament_detection", "template_custom_gcode", "thumbnails",
    "thumbnails_format", "toolchange_gcode", "use_firmware_retraction",
    "use_relative_e_distances", "use_volumetric_e", "used_filament_compensation",
    "variable_layer_height", "z_offset",
))

PROJECT_KEYS_V3 = frozenset((
    "extruder_colour", "wiping_volumes_matrix", "wiping_volumes_use_custom_matrix",
))

# print_settings keys that are genuinely vectors in v3 (all others are scalar
# there, even when the 2.9.7 schema marks them as per-extruder vectors).
PRINT_VECTOR_KEYS = frozenset(("gcode_substitutions", "post_process"))

# Preset bookkeeping / dependency keys: not settings, and v3 has no place for
# them in the configuration (they live in the preset metadata instead).
STRIP_KEYS = frozenset((
    "printer_settings_id", "print_settings_id", "filament_settings_id",
    "physical_printer_settings_id", "inherits", "inherits_cummulative",
    "default_filament_profile", "default_print_profile",
    "compatible_printers", "compatible_printers_condition",
    "compatible_printers_condition_cummulative", "compatible_prints",
    "compatible_prints_condition", "compatible_prints_condition_cummulative",
))

# -- printer identity (Prusa XL+ 5T, 5x 0.4 HF; see module docstring) ----------

_HW_CONFIG_TEMPLATE = {
    "base_model": "XL",
    "bed_model": "xl_bed.stl",
    "bed_texture": "xlp.svg",
    "config_id": "bb489cd3-8a47-4faf-bb53-5039a865636e",
    "config_name": "Prusa XL+ 5T 0.4 HF, 0.4 HF, 0.4 HF, 0.4 HF, 0.4 HF",
    "config_short_name": "Prusa XL+ 5T 0.4 HF, 0.4 HF, 0.4 HF, 0.4 HF, 0.4 HF",
    "features": {
        "auxiliary_travel_anchor_x": 0.5,
        "auxiliary_travel_anchor_y": 1.0,
        "bed_segments_x": 4.0,
        "bed_segments_y": 4.0,
        "input_shaper": True,
        "multi_extruder": True,
        "planetary_gearbox": True,
        "supports_025_nozzle": True,
        "supports_03_nozzle": True,
        "supports_04_nozzle": True,
        "supports_05_nozzle": True,
        "supports_06_nozzle": True,
        "supports_08_nozzle": True,
        "supports_high_flow_nozzle": True,
        "supports_mmu2s": False,
        "supports_mmu3_32bit": False,
        "supports_mmu3_8bit": False,
        "supports_mmu_025_nozzle": False,
        "supports_mmu_03_nozzle": False,
        "supports_mmu_04_nozzle": False,
        "supports_mmu_05_nozzle": False,
        "supports_mmu_06_nozzle": False,
        "supports_mmu_08_nozzle": False,
        "supports_non_high_flow_nozzle": True,
        "supports_tool_preheating": True,
    },
    "legacy_printer_model": "XLP5T",
    "model": "XLP",
    "printer_id": "xl+",
    "repo_id": "prusa-research-fff",
    "repo_version": "1.0.21",
    "sheet": {"features": {"cold": False}, "id": "satin", "name": "Satin", "type": "satin"},
    "technology": "fff",
    "template_id": "xl+5t",
    "thumbnail": "XLP5T_thumbnail.svg",
    "tool_count": 5,
    "tools": {
        "0": {"features": {"nozzle_diameter": 0.4, "nozzle_high_flow": True}, "id": "0.4HF",
              "material_package_instance": {}, "name": "0.4 HF",
              "slicer_material": {"features": {}, "id": "a4a4e96d-6da4-422f-ae7a-3f01a00fb465",
                                  "type": "PLA"},
              "type": "print_head"},
        "1": {"features": {"nozzle_diameter": 0.4, "nozzle_high_flow": True}, "id": "0.4HF",
              "material_package_instance": {}, "name": "0.4 HF",
              "slicer_material": {"features": {}, "id": "cdcbc99b-a2b1-416c-9f6b-3c17b8461b14",
                                  "type": "PLA"},
              "type": "print_head"},
        "2": {"features": {"nozzle_diameter": 0.4, "nozzle_high_flow": True}, "id": "0.4HF",
              "material_package_instance": {}, "name": "0.4 HF",
              "slicer_material": {"features": {}, "id": "9a3ddccd-891a-4ebe-b008-ce3ccb3cdf74",
                                  "type": "PLA"},
              "type": "print_head"},
        "3": {"features": {"nozzle_diameter": 0.4, "nozzle_high_flow": True}, "id": "0.4HF",
              "material_package_instance": {}, "name": "0.4 HF",
              "slicer_material": {"features": {}, "id": "7f6b3a24-4025-45b3-a4b4-476f568682fa",
                                  "type": "PLA"},
              "type": "print_head"},
        "4": {"features": {"nozzle_diameter": 0.4, "nozzle_high_flow": True}, "id": "0.4HF",
              "material_package_instance": {}, "name": "0.4 HF",
              "slicer_material": {"features": {}, "id": "de0d3395-4cdf-4b35-bbc9-c69565061487",
                                  "type": "PETG"},
              "type": "print_head"},
    },
    "vendor_id": "PrusaResearch",
}

_XL_CONDITIONS = ['printer.model == "XLP" and printer.base_model == "XL"']
_TOOL_CONDITIONS = _XL_CONDITIONS + ["tool.nozzle_diameter == 0.4", "tool.nozzle_high_flow"]

_PRESET_TEMPLATE = {
    "printer": {
        "conditions": _XL_CONDITIONS,
        "id": "3de87048-cfe5-4393-a8c3-783fa4f70948",
        "name": "Prusa XL+ 5T HF0.4 nozzle",
        "root_id": "ec2a6d3d-12c4-4482-a044-41011bd22b9f",
    },
    "print": {
        "conditions": _XL_CONDITIONS,
        "id": "46773c3d-90d8-4981-a8a2-463030cbcf5b",
        "name": "0.20mm Balanced \u2605 @XL+ HF0.4",
        "root_id": "ec357907-cfb2-4c9a-98e7-689c9e4e9067",
    },
    "tools": [{
        "conditions": _TOOL_CONDITIONS,
        "id": "91c59e44-bd13-4535-93e3-2779d702caea",
        "name": "0.20mm Balanced \u2605 @XL+ HF0.4",
        "root_id": "4ee39846-bac3-4f78-a6c2-6c858c4a40ee",
    }],
    "materials": [
        {"conditions": _TOOL_CONDITIONS, "id": "a4a4e96d-6da4-422f-ae7a-3f01a00fb465",
         "name": "Elegoo PLA @XL+ HF0.4", "root_id": "24f31d63-63bc-4fad-a059-5af9edf23b78"},
        {"conditions": _TOOL_CONDITIONS, "id": "cdcbc99b-a2b1-416c-9f6b-3c17b8461b14",
         "name": "Generic PLA @XL+ HF0.4", "root_id": "82ca2f76-0869-4ce4-977a-5252d1a68fcd"},
        {"conditions": _TOOL_CONDITIONS, "id": "9a3ddccd-891a-4ebe-b008-ce3ccb3cdf74",
         "name": "Generic PLA @XL+ HF0.4", "root_id": "de362a36-203e-452f-a0cc-2746fd7252aa"},
        {"conditions": _TOOL_CONDITIONS, "id": "7f6b3a24-4025-45b3-a4b4-476f568682fa",
         "name": "Sunlu PLA @XL+ HF0.4", "root_id": "798f3ced-2b61-47bc-a573-1088df1ff272"},
        {"conditions": _TOOL_CONDITIONS, "id": "de0d3395-4cdf-4b35-bbc9-c69565061487",
         "name": "Generic PETG @XL+ HF0.4", "root_id": "0b7471bb-1a1d-492a-9a1a-c7ef145e00f8"},
    ],
}


def _hw_config(n_tools: int) -> dict:
    hw = copy.deepcopy(_HW_CONFIG_TEMPLATE)
    hw["tool_count"] = n_tools
    hw["tools"] = {str(i): hw["tools"][str(i)] for i in range(min(n_tools, 5))}
    name = "Prusa XL+ 5T " + ", ".join(["0.4 HF"] * n_tools)
    hw["config_name"] = name
    hw["config_short_name"] = name
    return hw


def _preset(n_tools: int) -> dict:
    p = copy.deepcopy(_PRESET_TEMPLATE)
    p["tools"] = p["tools"] * n_tools
    p["materials"] = p["materials"][: max(1, min(n_tools, len(p["materials"])))]
    return p


# -- value conversion (2.9.7 serialized text -> v3 typed JSON) -----------------

def _floatorpercent(text: str) -> dict:
    t = text.strip()
    if t.endswith("%"):
        return {"is_percent": True, "value": float(t[:-1])}
    return {"is_percent": False, "value": float(t)}


def _unescape_single(text: str) -> str:
    """A scalar string value: unescape backslash sequences in place.

    2.9.7 stores scalar strings unquoted (``start_gcode = M17 ; wait\\n...``), so
    ``;`` is part of the value and only backslash escapes (``\\n``, ``\\r``, ``\\"``,
    ``\\\\``) are transformed; surrounding quotes, when present, are stripped.
    """
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            i += 1
            c = text[i]
            c = "\r" if c == "r" else "\n" if c == "n" else c
        out.append(c)
        i += 1
    s = "".join(out)
    if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s


def scalar_json(key: str, text: str):
    """One element of a serialized value as a JSON value, per the option type."""
    t = (text or "").strip()
    typ = option_type(key)
    if t == "nil":
        return None
    if key == "support_material":
        # v3 changed this from a bool to an enum ("none" / "enforcers_only" /
        # "everywhere"); a wrong type would make v3 drop the value and fall back
        # to the preset default (supports off), so map it explicitly.
        return "everywhere" if t == "1" else "none"
    if t == "":
        if typ in ("bool", "bools"):
            return False
        if typ in ("int", "ints", "float", "floats"):
            return 0
        if typ in ("percent", "percents", "floatorpercent", "floatsorpercents"):
            return {"is_percent": False, "value": 0.0}
        if typ == "points":
            return [0.0, 0.0]
        return ""
    if typ in ("bool", "bools"):
        return t == "1"
    if typ in ("int", "ints"):
        return int(float(t))
    if typ in ("float", "floats"):
        return float(t)
    if typ in ("percent", "percents"):
        return {"is_percent": True, "value": float(t.rstrip("%"))}
    if typ in ("floatorpercent", "floatsorpercents"):
        return _floatorpercent(t)
    if typ == "points":
        x, _, y = t.partition("x")
        return [float(x), float(y)]
    if typ == "string":
        return _unescape_single(t)
    if typ == "strings":
        vals = unescape_strings(t)
        return vals[0] if vals else ""
    # enum / enums / unknown: keep the text verbatim
    return t


def _split_elements(key: str, text: str) -> List[str]:
    """A serialized value as element strings (at least one)."""
    if option_type(key) == "strings":
        vals = unescape_strings(text or "")
    else:
        vals = [v.strip() for v in (text or "").split(",")]
        if vals == [""]:
            vals = []
    return vals or [""]


def vector_json(key: str, text: str, n: int) -> list:
    """A per-tool / per-filament value: exactly ``n`` JSON values (pad/truncate)."""
    vals = _split_elements(key, text)
    if len(vals) < n:
        vals = vals + [vals[-1]] * (n - len(vals))
    else:
        vals = vals[:n]
    return [scalar_json(key, v) for v in vals]


def full_vector_json(key: str, text: str) -> list:
    """A vector kept at its natural length (printer vectors, print gcode lists)."""
    return [scalar_json(key, v) for v in _split_elements(key, text)]


def _first_element(key: str, text: str) -> str:
    # A scalar ``string`` is one value: commas are data (G-code), not separators.
    # Only vector types (``floats`` etc.) are split to take the first entry.
    if option_type(key) == "string":
        return (text or "").strip()
    return _split_elements(key, text)[0]


# -- the configuration pack -----------------------------------------------------

def build_configuration(cfg: PrusaConfig, n_tools: int) -> dict:
    """The v3 ``configuration`` section: five location boxes, tool/filament
    vectorized to ``n_tools`` entries, print/printer scalar (or natural-length
    vectors where v3 keeps them as vectors)."""
    printer_box: Dict[str, object] = {}
    print_box: Dict[str, object] = {}
    tool_box: Dict[str, object] = {}
    filament_box: Dict[str, object] = {}
    project_box: Dict[str, object] = {}
    for key, text in cfg.items():
        if key in STRIP_KEYS:
            continue
        if key in TOOL_KEYS:
            tool_box[key] = vector_json(key, text, n_tools)
        if key in FILAMENT_KEYS_V3:
            filament_box[key] = vector_json(key, text, n_tools)
        if key in PRINT_KEYS_V3:
            if key in PRINT_VECTOR_KEYS:
                print_box[key] = full_vector_json(key, text)
            else:
                print_box[key] = scalar_json(key, _first_element(key, text))
        if key in PRINTER_KEYS_V3:
            if option_type(key) in VECTOR_TYPES:
                printer_box[key] = full_vector_json(key, text)
            else:
                printer_box[key] = scalar_json(key, _first_element(key, text))
        if key in PROJECT_KEYS_V3:
            if key == "wiping_volumes_use_custom_matrix":
                project_box[key] = scalar_json(key, text)
            else:
                project_box[key] = full_vector_json(key, text)
        elif key not in (TOOL_KEYS | FILAMENT_KEYS_V3 | PRINT_KEYS_V3 | PRINTER_KEYS_V3 | PROJECT_KEYS_V3):
            # Unknown to the v3 domain (2.9.7-only option): v3 ignores extra keys
            # non-fatally, so park it in print_settings rather than dropping it.
            print_box[key] = scalar_json(key, _first_element(key, text))
    # v3 requires the technology in printer_settings; our configs always carry it,
    # but guarantee it so a config without it still loads.
    printer_box.setdefault("printer_technology", "FFF")
    return {
        "filament_settings": filament_box,
        "print_settings": print_box,
        "printer_settings": printer_box,
        "project_settings": project_box,
        "toolprint_settings": tool_box,
    }


# -- the whole project file ------------------------------------------------------

def build_project_json(
    cfg: PrusaConfig,
    objects: Sequence[Tuple[int, int]],
    n_tools: int,
    wipe_tower: Optional[Tuple[float, float, float]] = None,
) -> dict:
    """The ``Metadata/PrusaSlicer3_project.json`` document.

    ``objects`` is a list of ``(3MF object id, default extruder)`` pairs;
    ``wipe_tower`` is ``(x, y, rotation_deg)`` or None. The per-machine
    ``physical_printer`` entry is deliberately omitted (it is optional on load).
    """
    tower = None
    if wipe_tower:
        x, y, rot = wipe_tower
        tower = {"x": x, "y": y, "rotation_angle": rot}
    preset = _preset(n_tools)
    return {
        "objects": [
            {"id": oid, "object_settings": {"extruder": ext}} for oid, ext in objects
        ],
        "project": {"id": "", "version": 1},
        "config_containers": [
            {
                "beds": [{
                    "custom_gcode": None,
                    "position_x": 0.0,
                    "position_y": 0.0,
                    "wipe_tower": tower,
                }],
                "configuration": build_configuration(cfg, n_tools),
                "preset": {
                    "hw_config": _hw_config(n_tools),
                    "printer": preset["printer"],
                    "print": preset["print"],
                    "tools": preset["tools"],
                    "materials": preset["materials"],
                },
            }
        ],
    }
