#!/usr/bin/env python3
"""
AgentSUMO Output Cleaner

Cleans files inside the output folder the MCP server writes to
(AGENTSUMO_MCP_OUTPUT_BASE, or the current directory, + "output").
uploads/ (user files), vehicle_types.add.xml and the tracked .gitkeep
files are preserved.
"""

import shutil

from agentsumo_mcp.utils.path_utils import get_working_directory

OUTPUT_DIR = get_working_directory() / "output"

# Agent state restored at startup; stale once the outputs are gone
STATE_FILE = OUTPUT_DIR / ".agentsumo_state.json"

# Files to preserve
PRESERVE_FILES = {
    "vehicle_types.add.xml",
    ".gitkeep",
}

# Subfolders to clean
CLEAN_FOLDERS = [
    "networks",
    "trips",
    "simulations",
    "analysis",
    "reports",
    "visualizations",
    "additional",
]


def clean_output():
    """Clean the output folder."""
    if not OUTPUT_DIR.exists():
        print("Output folder does not exist.")
        return

    deleted_count = 0
    preserved_count = 0

    for folder_name in CLEAN_FOLDERS:
        folder = OUTPUT_DIR / folder_name
        if not folder.exists():
            continue

        for file in folder.iterdir():
            if file.name in PRESERVE_FILES:
                preserved_count += 1
                print(f"  Preserved {folder_name}/{file.name}")
            elif file.is_file():
                file.unlink()
                deleted_count += 1
            elif file.is_dir():
                shutil.rmtree(file)
                deleted_count += 1

    if STATE_FILE.exists():
        STATE_FILE.unlink()
        deleted_count += 1

    print(f"\nCleanup complete. {deleted_count} deleted, {preserved_count} preserved.")


if __name__ == "__main__":
    print("AgentSUMO Output Cleaner")
    print("=" * 40)
    print(f"Target: {OUTPUT_DIR}")
    print()

    response = input("Clean the output folder? (y/N): ").strip().lower()
    if response == "y":
        clean_output()
    else:
        print("Cancelled.")
