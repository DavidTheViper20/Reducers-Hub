"""Export the current cycloidal drive configuration to DXF without the UI dialog.

Edit the PARAMETERS below to match your current slider values, then run:
    python export_current_config.py
"""

from cycloidal_drive import DriveParameters, export_scene_to_dxf

# fmt: off
PARAMETERS = DriveParameters(
    animation_frames=50,
    center_circle_radius=20,
    drive_pin_radius=1.5,
    eccentricity=2,
    pin_count=17,
    outer_pin_diameter=10,       # "Ring Pin Diameter" slider
    pin_circle_diameter=80,      # "Pin Circle Diameter" slider
)
# fmt: on

if __name__ == "__main__":
    output_path = export_scene_to_dxf(PARAMETERS, 0.0, file_name="cycloidal-drive")
    print(f"DXF exported to: {output_path}")
