"""Vocabulário básico de autoridade e método de emissão de Decision."""

from enum import StrEnum


class DecisionEmissionMethod(StrEnum):
    AUTOMATED = "AUTOMATED"
    HUMAN = "HUMAN"
