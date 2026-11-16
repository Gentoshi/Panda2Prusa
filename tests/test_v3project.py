"""PrusaSlicer 3.x native project file (panda2prusa.v3project).

Unit tests for the value conversion and the JSON structure, plus a fast
writer round-trip on a tiny synthetic project (no sample files needed).
"""

import json
import os
import zipfile

import pytest

from panda2prusa import v3project
from panda2prusa.prusa_config import PrusaConfig

from test_plates import make_project

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(_HERE, "out_diamondback_v8_v3_prusa.3mf")


# -- value conversion -----------------------------------------------------------

def test_scalar_json_types():
    assert v3project.scalar_json("perimeters", "3") == 3
    assert v3project.scalar_json("layer_height", "0.2") == 0.2
    assert v3project.scalar_json("binary_gcode", "1") is True
    assert v3project.scalar_json("binary_gcode", "0") is False
    assert v3project.scalar_json("fill_density", "20%") == {"is_percent": True, "value": 20.0}
    assert v3project.scalar_json("avoid_crossing_perimeters_max_detour", "20%") == {
        "is_percent": True, "value": 20.0
    }
    assert v3project.scalar_json("avoid_crossing_perimeters_max_detour", "0.42") == {
        "is_percent": False, "value": 0.42
    }
    assert v3project.scalar_json("bed_shape", "0x0") == [0.0, 0.0]
    assert v3project.scalar_json("seam_position", "rear") == "rear"
    assert v3project.scalar_json("retract_length", "nil") is None
    assert v3project.scalar_json("notes", '"hello world"') == "hello world"
    # scalar strings are unquoted in 2.9.7: ';' is data, backslash escapes expand
    assert v3project.scalar_json(
        "start_gcode", 'M17 ; enable steppers\\nM862.3 P "XLP" ; check'
    ) == 'M17 ; enable steppers\nM862.3 P "XLP" ; check'
    assert v3project.scalar_json("printer_notes", "a\\nb") == "a\nb"
    # scalar strings keep their commas (v3 print/printer scalars take the whole value)
    assert v3project._first_element("start_gcode", 'M17 ; x\\nM217 Z{max(zhop, 2.0)}') == 'M17 ; x\\nM217 Z{max(zhop, 2.0)}'
    assert v3project._first_element("retract_length", "0.8,1.2") == "0.8"
    assert v3project.scalar_json(
        "output_filename_format", '"[input_filename]_[timestamp]"'
    ) == "[input_filename]_[timestamp]"
    # v3 turned support_material from a bool into an enum
    assert v3project.scalar_json("support_material", "1") == "everywhere"
    assert v3project.scalar_json("support_material", "0") == "none"
    assert v3project.vector_json("support_material", "1", 3) == ["everywhere"] * 3


def test_vector_json_pads_and_truncates():
    assert v3project.vector_json("bed_temperature", "60,65", 4) == [60, 65, 65, 65]
    assert v3project.vector_json("bed_temperature", "60,65,70,75", 2) == [60, 65]
    assert v3project.vector_json("filament_colour", '"Prusament PLA";PLA', 3) == [
        "Prusament PLA", "PLA", "PLA"
    ]
    assert v3project.full_vector_json("bed_shape", "0x0,360x0,360x360,0x360") == [
        [0.0, 0.0], [360.0, 0.0], [360.0, 360.0], [0.0, 360.0]
    ]


# -- configuration routing -------------------------------------------------------

def _cfg():
    return PrusaConfig({
        "perimeters": "3",
        "fill_density": "8%",
        "layer_height": "0.2",
        "bed_shape": "0x0,360x0,360x360,0x360",
        "filament_colour": "#111111;#222222",
        "bed_temperature": "60,65",
        "gcode_substitutions": '"a";"b"',
        "wipe_tower": "1",
        "printer_technology": "FFF",
        "printer_settings_id": "Prusa XL+ 5T HF0.4",
        "print_settings_id": "0.20mm Balanced",
        "filament_settings_id": "PLA;PLA",
        "some_297_only_option": "x",
    })


def test_build_configuration_routing():
    cfg = v3project.build_configuration(_cfg(), 4)
    tool, print_box, printer, filament, project = (
        cfg["toolprint_settings"], cfg["print_settings"], cfg["printer_settings"],
        cfg["filament_settings"], cfg["project_settings"],
    )
    # per-tool keys are vectorized to n_tools
    assert tool["perimeters"] == [3, 3, 3, 3]
    assert tool["fill_density"] == [{"is_percent": True, "value": 8.0}] * 4
    # per-filament keys too
    assert filament["filament_colour"] == ["#111111", "#222222", "#222222", "#222222"]
    assert filament["bed_temperature"] == [60, 65, 65, 65]
    # print keys are scalar (first element) except the gcode lists
    assert print_box["perimeters"] == 3
    assert print_box["fill_density"] == {"is_percent": True, "value": 8.0}
    assert print_box["layer_height"] == 0.2
    assert print_box["wipe_tower"] is True
    assert print_box["gcode_substitutions"] == ["a", "b"]
    # printer keys keep their natural vector length
    assert printer["bed_shape"] == [[0.0, 0.0], [360.0, 0.0], [360.0, 360.0], [0.0, 360.0]]
    assert printer["printer_technology"] == "FFF"
    # preset bookkeeping keys are stripped everywhere
    flat = set(tool) | set(print_box) | set(printer) | set(filament) | set(project)
    assert not (flat & set(v3project.STRIP_KEYS))
    # unknown 2.9.7-only keys are parked in print_settings, not dropped
    assert print_box["some_297_only_option"] == "x"


def test_printer_technology_guaranteed():
    cfg = v3project.build_configuration(PrusaConfig({"perimeters": "3"}), 1)
    assert cfg["printer_settings"]["printer_technology"] == "FFF"


# -- project structure -----------------------------------------------------------

def test_build_project_json_invariants():
    j = v3project.build_project_json(_cfg(), [(1, 1), (2, 3)], 4, (213.2, 232.9, 0.0))
    assert j["project"] == {"id": "", "version": 1}
    assert j["objects"] == [
        {"id": 1, "object_settings": {"extruder": 1}},
        {"id": 2, "object_settings": {"extruder": 3}},
    ]
    cc = j["config_containers"][0]
    assert "physical_printer" not in cc  # per-machine identity is never written
    hw = cc["preset"]["hw_config"]
    assert hw["config_id"]  # empty id makes v3 drop the file to geometry-only
    assert hw["tool_count"] == 4
    assert len(hw["tools"]) == 4
    assert len(cc["preset"]["tools"]) == 4
    assert len(cc["preset"]["materials"]) == 4
    bed = cc["beds"][0]
    assert bed["wipe_tower"] == {"x": 213.2, "y": 232.9, "rotation_angle": 0.0}


def test_build_project_json_no_wipe_tower():
    j = v3project.build_project_json(_cfg(), [(1, 1)], 2)
    assert j["config_containers"][0]["beds"][0]["wipe_tower"] is None
    assert j["config_containers"][0]["preset"]["hw_config"]["tool_count"] == 2


# -- key sets vs the reference file (PrusaSlicer 3.0.0-alpha13) -------------------

@pytest.mark.skipif(not os.path.exists(REF), reason="reference v3 file not present")
def test_key_sets_cover_reference():
    """Every (location, key) the reference writes must be in our key sets, so a
    config round-trips through the same locations PrusaSlicer itself uses."""
    with zipfile.ZipFile(REF) as z:
        ref = json.loads(z.read(v3project.V3_PROJECT_FILE).decode("utf-8"))
    ref_cfg = ref["config_containers"][0]["configuration"]
    ours = v3project.build_configuration(_cfg(), 4)
    expected = {
        "toolprint_settings": v3project.TOOL_KEYS,
        "print_settings": v3project.PRINT_KEYS_V3,
        "filament_settings": v3project.FILAMENT_KEYS_V3,
        "printer_settings": v3project.PRINTER_KEYS_V3,
        "project_settings": v3project.PROJECT_KEYS_V3,
    }
    for loc, keys in expected.items():
        missing = set(ref_cfg[loc]) - keys
        assert not missing, f"{loc}: keys missing from {loc} set: {sorted(missing)}"
    # and our builder emits exactly the five locations v3 expects
    assert set(ours) == set(expected)


# -- writer round-trip -------------------------------------------------------------

def _write(tmp_path, **kwargs):
    from panda2prusa.reader import read_bambu_3mf
    from panda2prusa.translate import MODE_BAMBU, TargetPresets
    from panda2prusa.writer import write_prusa_3mf

    src = make_project(str(tmp_path / "in.3mf"), [(1, 1, 1, 0, 0), (2, 1, 2, 20, 0)])
    project = read_bambu_3mf(src)
    out = str(tmp_path / "out.3mf")
    stats = write_prusa_3mf(
        project, out,
        target=TargetPresets(mode=MODE_BAMBU),
        translate_settings=True,
        **kwargs,
    )
    return out, stats


def test_writer_default_is_legacy(tmp_path):
    out, stats = _write(tmp_path)
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        assert v3project.V3_PROJECT_FILE not in names
        model = z.read("3D/3dmodel.model").decode()
        assert f'name="Application">{v3project.LEGACY_APPLICATION}' in model


def test_writer_v3_native(tmp_path):
    out, stats = _write(tmp_path, v3_native=True)
    assert stats.settings_written
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        assert v3project.V3_PROJECT_FILE in names
        # legacy files are still written, so 2.9 keeps working
        assert "Metadata/Slic3r_PE.config" in names
        model = z.read("3D/3dmodel.model").decode()
        assert f'name="Application">{v3project.V3_APPLICATION}' in model
        j = json.loads(z.read(v3project.V3_PROJECT_FILE).decode("utf-8"))
    cc = j["config_containers"][0]
    hw = cc["preset"]["hw_config"]
    assert hw["config_id"]
    assert hw["tool_count"] == stats.extruders
    assert len(j["objects"]) == stats.objects_written
    assert {o["id"] for o in j["objects"]} == {1, 2}
    # per-object default extruder comes from the object-level setting
    by_id = {o["id"]: o["object_settings"]["extruder"] for o in j["objects"]}
    assert by_id[1] == 1 and by_id[2] == 2


def test_writer_v3_native_without_settings_falls_back(tmp_path):
    from panda2prusa.reader import read_bambu_3mf
    from panda2prusa.writer import write_prusa_3mf

    src = make_project(str(tmp_path / "in.3mf"), [(1, 1, 1, 0, 0)])
    project = read_bambu_3mf(src)
    out = str(tmp_path / "out.3mf")
    stats = write_prusa_3mf(project, out, translate_settings=False, v3_native=True)
    assert any("v3 native" in w for w in stats.warnings)
    with zipfile.ZipFile(out) as z:
        assert v3project.V3_PROJECT_FILE not in set(z.namelist())
        model = z.read("3D/3dmodel.model").decode()
        assert f'name="Application">{v3project.LEGACY_APPLICATION}' in model
