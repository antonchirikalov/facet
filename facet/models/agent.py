"""Agent package format — ``agent.yaml``.

What the generator reads: ``name``, ``description``, ``needs`` (tools), ``skills``
(document-type profiles). ``consumes``/``produces`` are kept as documentation of the agent's
contract — the ports themselves are wired by the workflow script's task(), never by this
package — and ``defaults.timeout_s`` is a note for the script author. The risk tiers and the
graph validator of the refract compiler are gone with the compiler.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_PORT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
# A skill is named by its directory under `.claude/skills/`, and Claude Code spells those
# with hyphens, like agent slugs.
_SKILL_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_BASE_CAPABILITIES = frozenset({"read", "edit", "vision", "bash", "webfetch"})


class Port(BaseModel):
    """A consumes/produces port: documentation of the contract, not wiring."""

    model_config = ConfigDict(extra="forbid")

    port: str
    type: str
    optional: bool = False

    @field_validator("port")
    @classmethod
    def _port_name(cls, v: str) -> str:
        if not _PORT_RE.match(v):
            raise ValueError(f"invalid port name: {v!r}")
        return v


class AgentDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timeout_s: int = 3600


class AgentSpec(BaseModel):
    """``agent.yaml`` — one agent of ``library/agents/``."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: int
    description: str = ""
    consumes: list[Port] = Field(default_factory=list)
    produces: list[Port] = Field(default_factory=list)
    needs: list[str] = Field(default_factory=list)
    # Document-type profiles preloaded into the agent's context at spawn (facet SPEC §6).
    # The writer and the critic of one type name the same profile, so they read one
    # contract instead of two drifting copies.
    skills: list[str] = Field(default_factory=list)
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise ValueError(f"invalid agent name: {v!r}")
        return v

    @field_validator("needs")
    @classmethod
    def _capabilities(cls, v: list[str]) -> list[str]:
        for cap in v:
            if cap in _BASE_CAPABILITIES:
                continue
            if cap.startswith("mcp:") and len(cap) > len("mcp:"):
                continue
            raise ValueError(f"unknown capability: {cap!r}")
        return v

    @field_validator("skills")
    @classmethod
    def _skills(cls, v: list[str]) -> list[str]:
        for skill in v:
            if not _SKILL_RE.match(skill):
                raise ValueError(f"invalid skill name: {skill!r}")
        if len(set(v)) != len(v):
            raise ValueError(f"duplicate skill: {v!r}")
        return v

    @property
    def ref(self) -> str:
        """Library reference string, e.g. ``source_processor@1``."""
        return f"{self.name}@{self.version}"
