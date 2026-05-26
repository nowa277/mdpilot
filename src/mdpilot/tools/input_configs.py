"""Standard sander/pmemd input configuration templates.

Each template generates a valid sander ``&cntrl`` namelist for a specific
MD stage.  Templates can be customised via keyword arguments; sensible
AMBER defaults (ff19SB + OPC3 + Langevin thermostat) are pre-filled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #

@dataclass
class InputConfigTemplate:
    """A reusable sander input configuration template."""

    name: str
    description: str
    category: str  # minimize / heating / equilibration / production
    defaults: dict[str, Any] = field(default_factory=dict)

    def render(self, **overrides: Any) -> str:
        """Render the template into a sander-compatible input string.

        User-provided *overrides* take precedence over stored defaults.
        Boolean / None values that are not part of the namelist are
        silently ignored.
        """
        params = {**self.defaults, **overrides}

        # Build title line
        title = params.pop("title", self.name)

        # Extract non-namelist keys
        restraint_mask = params.pop("restraintmask", "@CA,C,O,N")
        restraint_wt = params.pop("restraint_wt", None)

        # Build namelist lines
        lines = [f"{title}", " &cntrl"]

        # Sorted for deterministic output
        for key in sorted(params):
            val = params[key]
            if val is None:
                continue
            if isinstance(val, bool):
                lines.append(f"  {key}={','.join(['.TRUE.' if val else '.FALSE.'])},")
                lines[-1] = f"  {key}={'.TRUE.' if val else '.FALSE.'},"
            elif isinstance(val, float):
                lines.append(f"  {key}={val},")
            elif isinstance(val, int):
                lines.append(f"  {key}={val},")
            elif isinstance(val, str):
                lines.append(f"  {key}={val},")

        # Restraints (only if restraint_wt is explicitly provided)
        if restraint_wt is not None:
            lines.append(f"  ntr=1,")
            lines.append(f"  restraintmask='{restraint_mask}',")
            lines.append(f"  restraint_wt={restraint_wt},")

        lines.append(" /")
        return "\n".join(lines)


# ------------------------------------------------------------------ #
# Built-in templates
# ------------------------------------------------------------------ #

MINIMIZE = InputConfigTemplate(
    name="Minimization",
    description="Energy minimization (steepest descent + conjugate gradient)",
    category="minimize",
    defaults={
        "title": "Minimization",
        "imin": 1,
        "maxcyc": 10000,
        "ncyc": 5000,
        "cut": 10.0,
        "ntb": 1,
        "restraintmask": "@CA,C,O,N",
        "restraint_wt": 5.0,
    },
)

HEATING = InputConfigTemplate(
    name="Heating 0-300K over 100ps",
    description="Heat from 0K to 300K over 100ps (NVT, Langevin)",
    category="heating",
    defaults={
        "title": "Heating 0-300K over 100ps",
        "imin": 0,
        "irest": 0,
        "ntx": 1,
        "nstlim": 50000,
        "dt": 0.002,
        "ntf": 2,
        "ntc": 2,
        "cut": 10.0,
        "ntb": 1,
        "ntt": 3,
        "gamma_ln": 2.0,
        "temp0": 300.0,
        "tempi": 0.0,
        "restraintmask": "@CA,C,O,N",
        "restraint_wt": 5.0,
        "ntpr": 500,
        "ntwx": 500,
    },
)

EQUILIBRATION = InputConfigTemplate(
    name="NPT Equilibration 1ns",
    description="NPT equilibration at 300K for 1ns",
    category="equilibration",
    defaults={
        "title": "NPT Equilibration 1ns",
        "imin": 0,
        "irest": 1,
        "ntx": 5,
        "nstlim": 500000,
        "dt": 0.002,
        "ntf": 2,
        "ntc": 2,
        "cut": 10.0,
        "ntb": 2,
        "pres0": 1.0,
        "ntp": 1,
        "ntt": 3,
        "gamma_ln": 2.0,
        "temp0": 300.0,
        "ntpr": 1000,
        "ntwx": 1000,
    },
)

PRODUCTION = InputConfigTemplate(
    name="Production MD 100ns",
    description="Production MD run (100ns, NPT)",
    category="production",
    defaults={
        "title": "Production MD 100ns",
        "imin": 0,
        "irest": 1,
        "ntx": 5,
        "nstlim": 50000000,
        "dt": 0.002,
        "ntf": 2,
        "ntc": 2,
        "cut": 10.0,
        "ntb": 2,
        "pres0": 1.0,
        "ntp": 1,
        "ntt": 3,
        "gamma_ln": 2.0,
        "temp0": 300.0,
        "ntpr": 5000,
        "ntwx": 5000,
    },
)

MINIMIZE_NO_RESTRRAINT = InputConfigTemplate(
    name="Minimization (no restraints)",
    description="Full unrestrained energy minimization",
    category="minimize",
    defaults={
        "title": "Minimization (no restraints)",
        "imin": 1,
        "maxcyc": 5000,
        "ncyc": 2500,
        "cut": 10.0,
        "ntb": 1,
    },
)


# ------------------------------------------------------------------ #
# Registry
# ------------------------------------------------------------------ #

TEMPLATES: dict[str, InputConfigTemplate] = {
    "minimize": MINIMIZE,
    "heating": HEATING,
    "equilibration": EQUILIBRATION,
    "production": PRODUCTION,
    "minimize_unrestrained": MINIMIZE_NO_RESTRRAINT,
}


def get_template(run_type: str) -> InputConfigTemplate | None:
    """Look up an input-config template by run type."""
    return TEMPLATES.get(run_type)


def render_config(run_type: str, **overrides: Any) -> str | None:
    """Render a standard input config for the given run type.

    Returns ``None`` if no template exists for the run type.
    """
    tmpl = TEMPLATES.get(run_type)
    if tmpl is None:
        return None
    return tmpl.render(**overrides)


def list_config_templates() -> list[dict[str, str]]:
    """Return metadata for all available templates."""
    return [
        {
            "name": name,
            "description": tmpl.description,
            "category": tmpl.category,
        }
        for name, tmpl in TEMPLATES.items()
    ]
