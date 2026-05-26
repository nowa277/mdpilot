"""Pydantic v2 models for wizard manifest validation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WizardStepOption(BaseModel):
    """A single option within a single_select or multi_select step."""

    model_config = ConfigDict(strict=True)

    id: str
    label: str
    value: Any = None
    flag: str | None = None
    description: str | None = None


class WizardStep(BaseModel):
    """A single step in a wizard dialog."""

    model_config = ConfigDict(strict=True)

    id: str
    type: Literal[
        "file_picker",
        "single_select",
        "multi_select",
        "text_input",
        "toggle",
        "command_preview",
    ]
    label: str
    required: bool = True
    default: Any = None
    hint: str | None = None
    filter: str | None = None
    options: list[WizardStepOption] | None = None
    placeholder: str | None = None
    depends_on: str | None = None
    show_when: Any = None


class WizardManifest(BaseModel):
    """A complete wizard manifest for a single tool."""

    model_config = ConfigDict(strict=True)

    tool: str
    display: str
    description: str
    steps: list[WizardStep] = Field(default_factory=list)


class WizardInfo(BaseModel):
    """Lightweight info about a wizard for listing."""

    model_config = ConfigDict(strict=True)

    name: str
    display: str
    description: str


class WizardResult(BaseModel):
    """Result returned after a wizard completes and arguments are built."""

    model_config = ConfigDict(strict=True)

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    command_preview: str = ""
