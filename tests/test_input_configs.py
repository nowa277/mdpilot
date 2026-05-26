"""Tests for input_configs — sander/pmemd input configuration templates."""

from __future__ import annotations

import pytest

from mdpilot.tools.input_configs import (
    MINIMIZE,
    HEATING,
    EQUILIBRATION,
    PRODUCTION,
    MINIMIZE_NO_RESTRRAINT,
    TEMPLATES,
    get_template,
    render_config,
    list_config_templates,
)


class TestTemplateRegistry:
    def test_all_standard_templates_registered(self):
        assert "minimize" in TEMPLATES
        assert "heating" in TEMPLATES
        assert "equilibration" in TEMPLATES
        assert "production" in TEMPLATES
        assert "minimize_unrestrained" in TEMPLATES

    def test_get_template_returns_correct_object(self):
        tmpl = get_template("minimize")
        assert tmpl is MINIMIZE

    def test_get_template_unknown_returns_none(self):
        assert get_template("nonexistent") is None

    def test_list_config_templates(self):
        result = list_config_templates()
        assert len(result) == 5
        categories = {r["category"] for r in result}
        assert "minimize" in categories
        assert "heating" in categories
        assert "equilibration" in categories
        assert "production" in categories


class TestMinimizeTemplate:
    def test_renders_valid_namelist(self):
        output = MINIMIZE.render()
        assert "Minimization" in output
        assert "&cntrl" in output
        assert "/" in output
        assert "imin=1" in output
        assert "maxcyc=10000" in output
        assert "ncyc=5000" in output
        assert "ntr=1" in output
        assert "restraintmask=" in output

    def test_override_maxcyc(self):
        output = MINIMIZE.render(maxcyc=5000)
        assert "maxcyc=5000" in output
        assert "maxcyc=10000" not in output

    def test_remove_restraints(self):
        output = MINIMIZE.render(restraint_wt=None)
        assert "ntr=" not in output
        assert "restraintmask=" not in output

    def test_custom_restraint_mask(self):
        output = MINIMIZE.render(restraintmask="@CA")
        assert "restraintmask='@CA'" in output


class TestHeatingTemplate:
    def test_renders_valid_namelist(self):
        output = HEATING.render()
        assert "imin=0" in output
        assert "irest=0" in output
        assert "ntx=1" in output
        assert "nstlim=50000" in output
        assert "temp0=300.0" in output
        assert "tempi=0.0" in output
        assert "ntt=3" in output

    def test_override_target_temp(self):
        output = HEATING.render(temp0=310.0)
        assert "temp0=310.0" in output


class TestProductionTemplate:
    def test_renders_long_md(self):
        output = PRODUCTION.render()
        assert "nstlim=50000000" in output
        assert "ntb=2" in output
        assert "ntp=1" in output
        assert "ntpr=5000" in output

    def test_override_nstlim(self):
        output = PRODUCTION.render(nstlim=100000)
        assert "nstlim=100000" in output


class TestRenderConfigFunction:
    def test_renders_minimize(self):
        result = render_config("minimize")
        assert result is not None
        assert "&cntrl" in result
        assert "imin=1" in result

    def test_renders_heating_with_overrides(self):
        result = render_config("heating", temp0=350.0)
        assert "temp0=350.0" in result

    def test_returns_none_for_unknown(self):
        result = render_config("custom_run")
        assert result is None

    def test_all_templates_have_valid_namelist(self):
        for name in TEMPLATES:
            result = render_config(name)
            assert result is not None, f"Template {name} returned None"
            assert "&cntrl" in result, f"Template {name} missing &cntrl"
            assert "/" in result, f"Template {name} missing /"
