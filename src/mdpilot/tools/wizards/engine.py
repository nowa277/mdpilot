"""Pure-logic wizard engine — parses YAML manifests and builds tool arguments.

Maps wizard user-inputs to actual @tool function parameters, handling the
structural differences between manifest step types and function signatures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mdpilot.tools.input_configs import render_config
from mdpilot.tools.wizards.schema import (
    WizardManifest,
    WizardStep,
    WizardStepOption,
    WizardInfo,
    WizardResult,
)


# ---------------------------------------------------------------------------
# Built-in manifest directory
# ---------------------------------------------------------------------------

_BUILTIN_DIR = Path(__file__).parent / "manifests"


# ---------------------------------------------------------------------------
# WizardEngine
# ---------------------------------------------------------------------------

class WizardEngine:
    """Loads wizard manifests and builds tool-call arguments.

    User-level manifests in ``~/.mdpilot/wizards/`` take precedence over
    built-in ones when filenames collide.
    """

    def __init__(self, manifest_dir: Path | None = None) -> None:
        self._user_dir = manifest_dir  # user-specified override dir
        self._cache: dict[str, WizardManifest] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, tool_name: str) -> WizardManifest:
        """Parse the YAML manifest for *tool_name* and return a WizardManifest.

        Raises:
            FileNotFoundError: If no manifest exists for the tool.
        """
        if tool_name in self._cache:
            return self._cache[tool_name]

        path = self._find_manifest(tool_name)
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        manifest = WizardManifest.model_validate(raw)
        self._cache[tool_name] = manifest
        return manifest

    def _find_manifest(self, tool_name: str) -> Path:
        """Locate the manifest file for a tool, checking both directories."""
        for directory in self._scan_dirs():
            path = directory / f"{tool_name}.yaml"
            if path.is_file():
                return path
        raise FileNotFoundError(f"No manifest found for '{tool_name}'")

    def _scan_dirs(self) -> list[Path]:
        """Return manifest directories in precedence order (user overrides first)."""
        dirs: list[Path] = []
        if self._user_dir:
            dirs.append(self._user_dir)
        dirs.append(_BUILTIN_DIR)
        return dirs

    def list_wizards(self) -> list[WizardInfo]:
        """Return info for all available wizards."""
        results: list[WizardInfo] = []
        seen: set[str] = set()

        for directory in self._scan_dirs():
            if not directory.is_dir():
                continue
            for file in sorted(directory.glob("*.yaml")):
                name = file.stem
                if name in seen:
                    continue
                seen.add(name)
                try:
                    with open(file, "r", encoding="utf-8") as fh:
                        raw = yaml.safe_load(fh)
                    manifest = WizardManifest.model_validate(raw)
                    results.append(
                        WizardInfo(
                            name=manifest.tool,
                            display=manifest.display,
                            description=manifest.description,
                        )
                    )
                except Exception:
                    continue

        return results

    def is_wizard_command(self, tool_name: str) -> bool:
        """Return True if ``tool_name`` has an associated wizard manifest."""
        try:
            self._find_manifest(tool_name)
            return True
        except FileNotFoundError:
            return False

    # ------------------------------------------------------------------
    # Argument building
    # ------------------------------------------------------------------

    def build_arguments(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert user selections from a wizard dialog into tool function arguments.

        Each tool requires specific mapping because manifest step ids do not always
        match the underlying @tool function parameter names.

        pdb4amber:
          input_pdb step  → input_pdb param
          operations multi_select:
              "reduce"      → reduce=True
              "add_missing" → add_missing_atoms=True
            (nohyd and dry have no corresponding pdb4amber_run param — dropped)
          output step     → output param

        tleap:
          Generates a tLEaP input script from input_pdb / forcefield / solvent /
          ion_concentration steps and passes it as the input_script param.

        sander:
          prmtop step   → prmtop param
          inpcrd step   → inpcrd param
          engine step   → use_pmemd param (auto/sander/pmemd)
          nproc step    → nproc param (int)
          run_type step → auto-generates input_config from standard templates
                          (minimize/heating/equilibration/production). Falls
                          back to _wizard_run_type for unknown run types.

        cpptraj:
          Generates a cpptraj input script from prmtop / trajectory / analysis
          steps and passes it as the input_script param.

        antechamber:
          input_file step      → input_file param
          input_format step    → input_format param
          charge_method step   → charge_method param
          net_charge step      → net_charge param (int)
          atom_type step       → atom_type param
          run_parmchk step     → run_parmchk param (bool)
        """
        tool_name = manifest.tool

        if tool_name == "pdb4amber":
            return self._build_pdb4amber_args(manifest, user_inputs)
        elif tool_name == "tleap":
            return self._build_tleap_args(manifest, user_inputs)
        elif tool_name == "sander":
            return self._build_sander_args(manifest, user_inputs)
        elif tool_name == "cpptraj":
            return self._build_cpptraj_args(manifest, user_inputs)
        elif tool_name == "antechamber":
            return self._build_antechamber_args(manifest, user_inputs)
        else:
            return self._build_generic_args(manifest, user_inputs)

    def _build_pdb4amber_args(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> dict[str, Any]:
        args: dict[str, Any] = {}

        for step in manifest.steps:
            if step.type == "file_picker":
                val = self.get_step_value(manifest, step.id, user_inputs)
                if val is not None:
                    args["input_pdb"] = val

            elif step.type == "multi_select" and step.id == "operations":
                selected_ids: list[str] = list(user_inputs.get("operations", []))
                # Map to actual pdb4amber_run function params
                if "reduce" in selected_ids:
                    args["reduce"] = True
                if "add_missing" in selected_ids:
                    args["add_missing_atoms"] = True
                # nohyd and dry have no corresponding pdb4amber_run param — skipped

            elif step.type == "text_input" and step.id == "output":
                val = self.get_step_value(manifest, step.id, user_inputs)
                if val and str(val).strip():
                    args["output"] = val

        return args

    def _build_tleap_args(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> dict[str, Any]:
        input_pdb: str | None = None
        forcefield_value: str | None = None
        water_model: str = "opc3"
        solvent_box: str = "solvateoct"
        buffer_distance: str = "10.0"
        ion_conc: str = "0.15"
        ligand_file: str | None = None
        ligand_frcmod: str | None = None

        for step in manifest.steps:
            if step.type == "file_picker":
                val = self.get_step_value(manifest, step.id, user_inputs)
                if not val:
                    continue
                if step.id == "input_pdb":
                    input_pdb = str(val)
                elif step.id == "ligand_file":
                    ligand_file = str(val)
                elif step.id == "ligand_frcmod":
                    ligand_frcmod = str(val)
            elif step.type == "single_select" and step.options:
                selected_id = user_inputs.get(step.id)
                if selected_id:
                    for opt in step.options:
                        if opt.id == selected_id:
                            if step.id == "forcefield":
                                forcefield_value = opt.value
                            elif step.id == "water_model":
                                water_model = opt.value if opt.value else selected_id
                            elif step.id == "solvent_box":
                                solvent_box = opt.value if opt.value else selected_id
                            break
            elif step.type == "text_input":
                val = self.get_step_value(manifest, step.id, user_inputs)
                if val and str(val).strip():
                    if step.id == "ion_concentration":
                        ion_conc = str(val).strip()
                    elif step.id == "buffer_distance":
                        buffer_distance = str(val).strip()

        # --- Build tLEaP input script ---
        lines: list[str] = []

        # 1. Force field
        if forcefield_value:
            lines.append(f"source {forcefield_value}")

        # 2. Water model source (separate from force field)
        water_sources = {
            "opc3": "leaprc.water.opc3",
            "opc": "leaprc.water.opc",
            "tip3p": "leaprc.water.tip3p",
            "tip4pew": "leaprc.water.tip4pew",
        }
        water_source = water_sources.get(water_model)
        if water_source:
            lines.append(f"source {water_source}")

        # 3. Ion parameters (Li-Merz 12-6-4 for OPC3)
        if water_model == "opc3":
            lines.append("source leaprc.ionslm_1264_opc3")
        elif water_model == "opc":
            lines.append("source leaprc.ionslm_1264_opc")

        # 4. Load ligand if provided
        ligand_name = ""
        if ligand_file:
            ligand_name = Path(ligand_file).stem
            if ligand_frcmod:
                lines.append(f"loadamberparams {Path(ligand_frcmod).name}")
            lines.append(f"MOL = loadmol2 {Path(ligand_file).name}")

        # 5. Load protein
        pdb_name = ""
        pdb_stem = ""
        if input_pdb:
            pdb_name = Path(input_pdb).name
            pdb_stem = Path(input_pdb).stem
            lines.append(f"{pdb_stem} = loadPdb {pdb_name}")

        # 6. Combine protein + ligand if both present
        if pdb_name and ligand_name:
            lines.append(f"complex = combine {{{pdb_stem} MOL}}")
            mol_var = "complex"
        elif pdb_name:
            mol_var = pdb_stem
        elif ligand_name:
            mol_var = "MOL"
        else:
            mol_var = ""

        # 7. Solvate
        if mol_var and water_model != "none" and solvent_box:
            # Water box commands by model
            water_boxes = {
                "opc3": "OPC3BOX",
                "opc": "OPCBOX",
                "tip3p": "TIP3PBOX",
                "tip4pew": "TIP4PEWBOX",
            }
            box_name = water_boxes.get(water_model, "OPC3BOX")
            if solvent_box == "solvateoct":
                lines.append(f"solvateoct {mol_var} {box_name} {buffer_distance}")
            else:
                lines.append(f"solvatebox {mol_var} {box_name} {buffer_distance}")

            # 8. Add ions (neutralize first, then add concentration)
            lines.append(f"addIons2 {mol_var} Na+ 0")
            lines.append(f"addIons2 {mol_var} Cl- 0")
            # Add salt concentration
            try:
                conc = float(ion_conc)
                if conc > 0:
                    lines.append(f"addIons2 {mol_var} Na+ {conc}")
                    lines.append(f"addIons2 {mol_var} Cl- {conc}")
            except (ValueError, TypeError):
                pass

        # 9. Save
        if mol_var:
            lines.append(f"saveAmberParm {mol_var} {mol_var}.prmtop {mol_var}.inpcrd")

        lines.append("quit")

        return {"input_script": "\n".join(lines)}

    def _build_sander_args(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> dict[str, Any]:
        args: dict[str, Any] = {}

        for step in manifest.steps:
            if step.type == "file_picker":
                val = self.get_step_value(manifest, step.id, user_inputs)
                if val:
                    if step.id == "prmtop":
                        args["prmtop"] = val
                    elif step.id == "inpcrd":
                        args["inpcrd"] = val
            elif step.type == "single_select" and step.id == "engine":
                selected_id = user_inputs.get("engine")
                if selected_id == "sander":
                    args["use_pmemd"] = False
                elif selected_id == "pmemd":
                    args["use_pmemd"] = True
                # "auto" → use_pmemd stays at default (False)
            elif step.type == "text_input" and step.id == "nproc":
                val = self.get_step_value(manifest, step.id, user_inputs)
                if val is not None:
                    try:
                        args["nproc"] = int(str(val))
                    except (ValueError, TypeError):
                        pass

        # Auto-generate input_config from run_type using standard templates.
        # This closes the wizard gap: user selects "minimize" → we produce
        # a valid min.in &cntrl namelist automatically.
        run_type = user_inputs.get("run_type")
        if run_type and "input_config" not in user_inputs:
            config_text = render_config(run_type)
            if config_text is not None:
                args["input_config"] = config_text
            else:
                # Unknown run_type — flag for LLM to generate
                args["_wizard_run_type"] = run_type

        return args

    def _build_cpptraj_args(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> dict[str, Any]:
        prmtop: str | None = None
        trajectory: str | None = None
        selected_ids: list[str] = []

        for step in manifest.steps:
            if step.type == "file_picker":
                val = self.get_step_value(manifest, step.id, user_inputs)
                if val:
                    if step.id == "prmtop":
                        prmtop = str(val)
                    elif step.id == "trajectory":
                        trajectory = str(val)
            elif step.type == "multi_select" and step.id == "analysis":
                selected_ids = list(user_inputs.get("analysis", []))

        # Generate cpptraj input script
        lines: list[str] = []
        if prmtop:
            lines.append(f"parm {prmtop}")
        if trajectory:
            traj_name = Path(trajectory).name
            lines.append(f"trajin {traj_name}")

        analysis_commands = {
            "rmsd": "rms first !@CA",
            "rmsf": "atomicfluct !@CA byres",
            "hbond": "hbond",
            "distance": "distance :1 :2",
            "dihedral": "dihedral :1 :2 :3 :4",
            "cluster": "cluster hieragglo d 5.0 avgout clusters.dat",
            "pca": "runanalysis pca evecs # .mw pcaModes.dat",
        }
        for a_id in selected_ids:
            cmd = analysis_commands.get(a_id)
            if cmd:
                lines.append(cmd)

        lines.append("run")
        lines.append("quit")

        return {"input_script": "\n".join(lines)}

    def _build_antechamber_args(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> dict[str, Any]:
        args: dict[str, Any] = {}

        for step in manifest.steps:
            if step.type == "file_picker" and step.id == "input_file":
                val = self.get_step_value(manifest, step.id, user_inputs)
                if val:
                    args["input_file"] = val

            elif step.type == "single_select" and step.options:
                selected_id = user_inputs.get(step.id)
                if selected_id:
                    for opt in step.options:
                        if opt.id == selected_id:
                            args[step.id] = opt.value
                            break

            elif step.type == "text_input":
                val = self.get_step_value(manifest, step.id, user_inputs)
                if val is not None and step.id == "net_charge":
                    try:
                        args["net_charge"] = int(str(val))
                    except (ValueError, TypeError):
                        pass

            elif step.type == "toggle":
                val = self.get_step_value(manifest, step.id, user_inputs)
                if val is not None:
                    args[step.id] = bool(val)

        return args

    def _build_generic_args(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Fallback for tools without specific handling."""
        args: dict[str, Any] = {}
        for step in manifest.steps:
            if step.type == "command_preview":
                continue
            val = self.get_step_value(manifest, step.id, user_inputs)
            if val is None:
                continue
            if step.type == "single_select" and step.options:
                for opt in step.options:
                    if opt.id == val:
                        args[step.id] = opt.value
                        break
                else:
                    args[step.id] = val
            elif step.type == "multi_select" and isinstance(val, list):
                args[step.id] = [opt.value for opt in (step.options or []) if opt.id in val]
            else:
                args[step.id] = val
        return args

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_step_value(
        self, manifest: WizardManifest, step_id: str, user_inputs: dict[str, Any]
    ) -> Any | None:
        """Resolve the effective value for a step from user inputs.

        Returns the user-provided value if present, otherwise the step default.
        Returns None if the step has no user input and no default.
        """
        if step_id in user_inputs:
            return user_inputs[step_id]
        for step in manifest.steps:
            if step.id == step_id:
                return step.default
        return None

    # ------------------------------------------------------------------
    # Command preview
    # ------------------------------------------------------------------

    def build_command_preview(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> str:
        """Generate a human-readable preview of what the wizard will execute.

        Produces natural-language descriptions, not raw CLI strings.
        """
        tool_name = manifest.tool

        if tool_name == "pdb4amber":
            return self._preview_pdb4amber(manifest, user_inputs)
        elif tool_name == "tleap":
            return self._preview_tleap(manifest, user_inputs)
        elif tool_name == "sander":
            return self._preview_sander(manifest, user_inputs)
        elif tool_name == "cpptraj":
            return self._preview_cpptraj(manifest, user_inputs)
        elif tool_name == "antechamber":
            return self._preview_antechamber(manifest, user_inputs)
        else:
            return self._preview_generic(manifest, user_inputs)

    def _preview_pdb4amber(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> str:
        parts: list[str] = ["pdb4amber 预处理"]

        input_pdb = self.get_step_value(manifest, "input_pdb", user_inputs)
        if input_pdb:
            parts.append(f"  输入文件: {Path(str(input_pdb)).name}")

        selected_ops: list[str] = list(user_inputs.get("operations", []))
        if selected_ops:
            labels = {
                "nohyd": "去除所有氢原子",
                "dry": "去除所有水分子",
                "reduce": "用 Reduce 添加氢原子",
                "add_missing": "补全缺失重原子",
            }
            for op_id in selected_ops:
                parts.append(f"  操作: {labels.get(op_id, op_id)}")

        output_val = self.get_step_value(manifest, "output", user_inputs)
        if output_val and str(output_val).strip():
            parts.append(f"  输出文件: {output_val}")
        elif input_pdb:
            parts.append(f"  输出文件: {Path(str(input_pdb)).stem}_clean.pdb")

        return "\n".join(parts)

    def _preview_tleap(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> str:
        parts: list[str] = ["tLEaP 系统构建"]

        input_pdb = self.get_step_value(manifest, "input_pdb", user_inputs)
        if input_pdb:
            parts.append(f"  PDB 文件: {Path(str(input_pdb)).name}")

        for step in manifest.steps:
            if step.id == "forcefield":
                selected_id = user_inputs.get("forcefield")
                for opt in (step.options or []):
                    if opt.id == selected_id:
                        parts.append(f"  力场: {opt.label}")
                        break
            elif step.id == "water_model":
                selected_id = user_inputs.get("water_model")
                for opt in (step.options or []):
                    if opt.id == selected_id:
                        parts.append(f"  水模型: {opt.label}")
                        break

        ligand_file = self.get_step_value(manifest, "ligand_file", user_inputs)
        if ligand_file:
            parts.append(f"  配体: {Path(str(ligand_file)).name}")

        ion_val = self.get_step_value(manifest, "ion_concentration", user_inputs)
        if ion_val:
            parts.append(f"  离子浓度: {ion_val} M")

        return "\n".join(parts)

    def _preview_sander(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> str:
        parts: list[str] = ["sander/pmemd 分子动力学模拟"]

        prmtop = self.get_step_value(manifest, "prmtop", user_inputs)
        if prmtop:
            parts.append(f"  拓扑文件: {Path(str(prmtop)).name}")

        inpcrd = self.get_step_value(manifest, "inpcrd", user_inputs)
        if inpcrd:
            parts.append(f"  坐标文件: {Path(str(inpcrd)).name}")

        for step in manifest.steps:
            if step.id == "run_type":
                selected_id = user_inputs.get("run_type")
                for opt in (step.options or []):
                    if opt.id == selected_id:
                        parts.append(f"  运行类型: {opt.label}")
                        break
            elif step.id == "engine":
                selected_id = user_inputs.get("engine")
                for opt in (step.options or []):
                    if opt.id == selected_id:
                        parts.append(f"  计算引擎: {opt.label}")
                        break

        nproc = self.get_step_value(manifest, "nproc", user_inputs)
        if nproc:
            parts.append(f"  MPI 进程数: {nproc}")

        # Show generated input_config preview
        run_type = user_inputs.get("run_type")
        if run_type:
            from mdpilot.tools.input_configs import render_config
            config_text = render_config(run_type)
            if config_text:
                # Show first 5 lines of config as preview
                config_lines = config_text.splitlines()[:5]
                parts.append("")
                parts.append("  生成的配置 (预览):")
                for cl in config_lines:
                    parts.append(f"    {cl}")
                if len(config_text.splitlines()) > 5:
                    parts.append(f"    ... ({len(config_text.splitlines())} 行)")

        return "\n".join(parts)

    def _preview_cpptraj(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> str:
        parts: list[str] = ["cpptraj 轨迹分析"]

        prmtop = self.get_step_value(manifest, "prmtop", user_inputs)
        if prmtop:
            parts.append(f"  拓扑文件: {Path(str(prmtop)).name}")

        trajectory = self.get_step_value(manifest, "trajectory", user_inputs)
        if trajectory:
            parts.append(f"  轨迹文件: {Path(str(trajectory)).name}")

        selected_ids: list[str] = list(user_inputs.get("analysis", []))
        if selected_ids:
            labels = {
                "rmsd": "RMSD (均方根偏差)",
                "rmsf": "RMSF (均方根涨落)",
                "hbond": "氢键分析",
                "distance": "距离/角度测量",
                "dihedral": "二面角分析",
                "cluster": "聚类分析",
                "pca": "主成分分析 (PCA)",
            }
            for a_id in selected_ids:
                parts.append(f"  分析: {labels.get(a_id, a_id)}")

        return "\n".join(parts)

    def _preview_antechamber(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> str:
        parts: list[str] = ["antechamber 配体参数化"]

        input_file = self.get_step_value(manifest, "input_file", user_inputs)
        if input_file:
            parts.append(f"  输入文件: {Path(str(input_file)).name}")

        for step in manifest.steps:
            if step.type == "single_select" and step.options:
                selected_id = user_inputs.get(step.id)
                for opt in step.options:
                    if opt.id == selected_id:
                        parts.append(f"  {step.label}: {opt.label}")
                        break
            elif step.type == "text_input":
                val = self.get_step_value(manifest, step.id, user_inputs)
                if val is not None:
                    parts.append(f"  {step.label}: {val}")
            elif step.type == "toggle":
                val = self.get_step_value(manifest, step.id, user_inputs)
                if val is not None:
                    parts.append(f"  {step.label}: {'是' if val else '否'}")

        return "\n".join(parts)

    def _preview_generic(
        self, manifest: WizardManifest, user_inputs: dict[str, Any]
    ) -> str:
        parts: list[str] = [manifest.display]
        for step in manifest.steps:
            if step.type == "command_preview":
                continue
            val = self.get_step_value(manifest, step.id, user_inputs)
            if val is not None:
                parts.append(f"  {step.label}: {val}")
        return "\n".join(parts)