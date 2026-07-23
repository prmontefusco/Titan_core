"""Modelo de domínio imutável para Regras de Conformidade Versionadas (ADR-0038/Passo 6.2)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from packages.shared_kernel import OrganizationId, TypedId


class SeverityLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    BLOCKING = "blocking"


class ComparisonOperator(Enum):
    """Operadores declarativos suportados pelo motor determinístico do Core."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_THAN = "less_than"
    LESS_OR_EQUAL = "less_or_equal"
    IN = "in"
    NOT_IN = "not_in"


_ORDERING_OPERATORS = frozenset(
    {
        ComparisonOperator.GREATER_THAN,
        ComparisonOperator.GREATER_OR_EQUAL,
        ComparisonOperator.LESS_THAN,
        ComparisonOperator.LESS_OR_EQUAL,
    }
)

_MEMBERSHIP_OPERATORS = frozenset({ComparisonOperator.IN, ComparisonOperator.NOT_IN})


class ConditionOutcome(Enum):
    """Resultado da checagem de uma única condição sobre o payload de um Fact."""

    SATISFIED = "satisfied"
    VIOLATED = "violated"
    KEY_MISSING = "key_missing"
    INCOMPARABLE = "incomparable"


def _is_number(value: object) -> bool:
    # bool é subclasse de int e não participa de comparação de ordem.
    return isinstance(value, int | float) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class RuleCondition:
    """Condição normativa declarativa: dado um Fact, compara uma chave do payload.

    A condição é dado, nunca código: o Core a avalia de forma determinística sem
    conhecer a vertical. Lógica normativa arbitrária pertence ao motor Wasm
    versionado do ADR-0036.
    """

    fact_type: str
    payload_key: str
    operator: ComparisonOperator
    expected_value: Any = None
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.fact_type, str) or not self.fact_type.strip():
            raise ValueError("fact_type da condição deve ser uma string não vazia.")
        if not isinstance(self.payload_key, str) or not self.payload_key.strip():
            raise ValueError("payload_key da condição deve ser uma string não vazia.")
        if not isinstance(self.operator, ComparisonOperator):
            raise TypeError("operator deve ser um ComparisonOperator válido.")

        object.__setattr__(self, "fact_type", self.fact_type.strip().lower())
        object.__setattr__(self, "payload_key", self.payload_key.strip())
        object.__setattr__(self, "description", self.description.strip())

        if self.operator in _MEMBERSHIP_OPERATORS:
            if not isinstance(self.expected_value, list | tuple):
                raise TypeError(
                    f"O operador '{self.operator.value}' exige uma lista de valores esperados."
                )
            if not self.expected_value:
                raise ValueError(
                    f"O operador '{self.operator.value}' exige ao menos um valor esperado."
                )
            object.__setattr__(self, "expected_value", tuple(self.expected_value))
        elif self.operator in _ORDERING_OPERATORS and not _is_number(self.expected_value):
            raise TypeError(f"O operador '{self.operator.value}' exige um valor esperado numérico.")

    def check(self, payload: Mapping[str, Any]) -> ConditionOutcome:
        """Avalia a condição contra o payload de um Fact, sem lançar exceção.

        Ausência de dado é lacuna explícita (`KEY_MISSING`) e tipo incompatível é
        `INCOMPARABLE`: nenhum dos dois é convertido em violação.
        """
        if self.payload_key not in payload:
            return ConditionOutcome.KEY_MISSING

        actual = payload[self.payload_key]

        if self.operator is ComparisonOperator.EQUALS:
            return self._verdict(actual == self.expected_value)
        if self.operator is ComparisonOperator.NOT_EQUALS:
            return self._verdict(actual != self.expected_value)
        if self.operator is ComparisonOperator.IN:
            return self._verdict(actual in self.expected_value)
        if self.operator is ComparisonOperator.NOT_IN:
            return self._verdict(actual not in self.expected_value)

        if not _is_number(actual):
            return ConditionOutcome.INCOMPARABLE
        if self.operator is ComparisonOperator.GREATER_THAN:
            return self._verdict(actual > self.expected_value)
        if self.operator is ComparisonOperator.GREATER_OR_EQUAL:
            return self._verdict(actual >= self.expected_value)
        if self.operator is ComparisonOperator.LESS_THAN:
            return self._verdict(actual < self.expected_value)
        return self._verdict(actual <= self.expected_value)

    def describe(self) -> str:
        """Descrição estável e legível da condição, usada nas justificativas."""
        if self.description:
            return self.description
        return f"{self.fact_type}.{self.payload_key} {self.operator.value} {self.expected_value!r}"

    def to_dict(self) -> dict[str, Any]:
        expected = (
            list(self.expected_value)
            if isinstance(self.expected_value, tuple)
            else self.expected_value
        )
        return {
            "fact_type": self.fact_type,
            "payload_key": self.payload_key,
            "operator": self.operator.value,
            "expected_value": expected,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RuleCondition":
        return cls(
            fact_type=data["fact_type"],
            payload_key=data["payload_key"],
            operator=ComparisonOperator(data["operator"]),
            expected_value=data.get("expected_value"),
            description=data.get("description", ""),
        )

    @staticmethod
    def _verdict(satisfied: bool) -> ConditionOutcome:
        return ConditionOutcome.SATISFIED if satisfied else ConditionOutcome.VIOLATED


@dataclass(frozen=True, slots=True)
class Rule:
    rule_id: TypedId
    policy_id: TypedId
    organization_id: OrganizationId
    code: str
    name: str
    description: str
    version: int = 1
    severity: SeverityLevel = SeverityLevel.BLOCKING
    normative_source: str = ""
    required_evidence_types: tuple[str, ...] = field(default_factory=tuple)
    conditions: tuple[RuleCondition, ...] = field(default_factory=tuple)
    justification: str = ""
    corrective_action: str = ""
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.rule_id.entity_type != "rule":
            raise ValueError("rule_id deve ser do tipo 'rule'.")
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ser do tipo 'policy'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("code de Rule deve ser uma string não vazia.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name de Rule deve ser uma string não vazia.")
        if not isinstance(self.description, str):
            raise TypeError("description deve ser string.")
        if not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version deve ser um número inteiro >= 1.")
        if not isinstance(self.severity, SeverityLevel):
            raise TypeError("severity deve ser um SeverityLevel válido.")
        if not isinstance(self.required_evidence_types, tuple):
            raise TypeError("required_evidence_types deve ser uma tupla.")
        if not isinstance(self.conditions, tuple):
            raise TypeError("conditions deve ser uma tupla.")
        if any(not isinstance(c, RuleCondition) for c in self.conditions):
            raise TypeError("conditions deve conter apenas RuleCondition.")
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_to < self.valid_from
        ):
            raise ValueError("valid_to não pode ser anterior a valid_from.")

    def create_next_version(
        self,
        name: str | None = None,
        description: str | None = None,
        severity: SeverityLevel | None = None,
        required_evidence_types: tuple[str, ...] | None = None,
        conditions: tuple[RuleCondition, ...] | None = None,
    ) -> "Rule":
        return Rule(
            rule_id=TypedId.new("rule"),
            policy_id=self.policy_id,
            organization_id=self.organization_id,
            code=self.code,
            name=name or self.name,
            description=description if description is not None else self.description,
            version=self.version + 1,
            severity=severity or self.severity,
            normative_source=self.normative_source,
            required_evidence_types=(
                required_evidence_types
                if required_evidence_types is not None
                else self.required_evidence_types
            ),
            conditions=conditions if conditions is not None else self.conditions,
            justification=self.justification,
            corrective_action=self.corrective_action,
            valid_from=None,
            valid_to=None,
            created_at=datetime.now(UTC),
        )

    @classmethod
    def create(
        cls,
        policy_id: TypedId,
        organization_id: OrganizationId,
        code: str,
        name: str,
        description: str = "",
        severity: SeverityLevel = SeverityLevel.BLOCKING,
        normative_source: str = "",
        required_evidence_types: tuple[str, ...] = (),
        conditions: tuple[RuleCondition, ...] = (),
        justification: str = "",
        corrective_action: str = "",
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
    ) -> "Rule":
        return cls(
            rule_id=TypedId.new("rule"),
            policy_id=policy_id,
            organization_id=organization_id,
            code=code.strip().lower(),
            name=name.strip(),
            description=description.strip(),
            version=1,
            severity=severity,
            normative_source=normative_source.strip(),
            required_evidence_types=required_evidence_types,
            conditions=conditions,
            justification=justification.strip(),
            corrective_action=corrective_action.strip(),
            valid_from=valid_from,
            valid_to=valid_to,
        )
