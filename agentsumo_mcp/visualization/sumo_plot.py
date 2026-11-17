"""
Run SUMO's matplotlib plotting scripts (tools/visualization/*.py) headlessly.
"""

import os
import subprocess
import sys
from typing import List

from agentsumo_mcp.settings.settings import sumo_environment

PLOT_TIMEOUT = 300  # seconds


def run_sumo_plot(script_name: str, args: List[str]) -> subprocess.CompletedProcess:
    """
    Run a SUMO plotting script and wait for it to finish.

    - Uses this interpreter, so the script sees the same matplotlib/sumolib
      (a bare "python3" on PATH may be another environment, or missing)
    - Passes --blind: without it the scripts call plt.show() after saving
      and block until the window is closed
    - Captures output: this MCP server speaks JSON-RPC over stdout

    Raises:
        RuntimeError: If the script exits with a non-zero status
    """
    plot_script = sumo_environment.get_tool_path(os.path.join("visualization", script_name))

    env = os.environ.copy()
    env["SUMO_HOME"] = sumo_environment.SUMO_HOME
    env["MPLBACKEND"] = "Agg"

    result = subprocess.run(
        [sys.executable, plot_script, *args, "--blind"],
        capture_output=True, text=True, env=env, timeout=PLOT_TIMEOUT
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{script_name} failed with return code {result.returncode}: {result.stderr}"
        )
    return result
