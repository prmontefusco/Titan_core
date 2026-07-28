"""Balanço mínimo da transformação (ADR-0046, Passos 11.4 e 11.6).

O que estes testes protegem: ausência de peso de entrada nunca vira zero nem
`BALANCED` por omissão (`NOT_ASSESSED`); bases de medição incompatíveis nunca
são comparadas numericamente (`INDETERMINATE`); `declared_loss` (perda
conhecida) nunca se confunde com `unaccounted_quantity` (diferença ainda não
explicada) — a segunda é sempre calculada descontando a primeira; e, desde o
Passo 11.6, N entradas se somam exatamente pela mesma regra que já somava N
saídas (fan-in usa o mesmo cálculo que fan-out, sem lógica duplicada).
"""

from decimal import Decimal

from packages.livestock_application.transformation_service import (
    QuantifiedAmount,
    TransformationOutputSpec,
    compute_transformation_balance,
)
from packages.livestock_domain.transformation import (
    BalanceResult,
    BalanceStatus,
    TraceableItemType,
)


def _entrada(
    quantity: Decimal | None, unit: str = "kg", basis: str | None = "peso liquido"
) -> QuantifiedAmount:
    return QuantifiedAmount(quantity=quantity, unit=unit, measurement_basis=basis)


def _saida(
    quantity: Decimal | None, unit: str = "kg", basis: str | None = "peso liquido"
) -> TransformationOutputSpec:
    return TransformationOutputSpec(
        item_type=TraceableItemType.HALF_CARCASS,
        quantity=quantity,
        unit=unit,
        measurement_basis=basis,
    )


def test_sem_peso_de_entrada_produz_not_assessed() -> None:
    balanco = compute_transformation_balance(
        inputs=(_entrada(None),),
        outputs=(_saida(Decimal("100")), _saida(Decimal("100"))),
        declared_loss=None,
        tolerance=None,
    )

    assert balanco.status is BalanceStatus.NOT_ASSESSED
    assert balanco.result is BalanceResult.NOT_APPLICABLE
    assert balanco.input_total is None
    assert balanco.output_total is None


def test_sem_nenhuma_entrada_produz_not_assessed() -> None:
    """Fan-in sem entrada alguma não é um caso válido, mas o balanço não inventa."""
    balanco = compute_transformation_balance(
        inputs=(),
        outputs=(_saida(Decimal("100")), _saida(Decimal("100"))),
        declared_loss=None,
        tolerance=None,
    )

    assert balanco.status is BalanceStatus.NOT_ASSESSED
    assert balanco.result is BalanceResult.NOT_APPLICABLE


def test_saida_sem_quantidade_produz_indeterminate_sem_inventar_zero() -> None:
    balanco = compute_transformation_balance(
        inputs=(_entrada(Decimal("200"), basis="peso vivo"),),
        outputs=(_saida(Decimal("100")), _saida(None)),
        declared_loss=None,
        tolerance=None,
    )

    assert balanco.status is BalanceStatus.DECLARED
    assert balanco.result is BalanceResult.INDETERMINATE
    assert balanco.output_total is None
    assert any("sem quantidade" in motivo for motivo in balanco.reasons)


def test_unidades_incompativeis_produzem_indeterminate() -> None:
    balanco = compute_transformation_balance(
        inputs=(_entrada(Decimal("200"), basis="peso vivo"),),
        outputs=(_saida(Decimal("100"), unit="kg"), _saida(Decimal("50"), unit="lb")),
        declared_loss=None,
        tolerance=None,
    )

    assert balanco.result is BalanceResult.INDETERMINATE
    assert any("Unidades incompatíveis" in motivo for motivo in balanco.reasons)


def test_bases_de_medicao_incompativeis_nunca_viram_numero() -> None:
    """ADR-0046, item 7: peso vivo vs. peso líquido pós-sangria não se somam."""
    balanco = compute_transformation_balance(
        inputs=(_entrada(Decimal("500"), basis="peso vivo"),),
        outputs=(
            _saida(Decimal("200"), basis="peso liquido pos-sangria"),
            _saida(Decimal("190"), basis="peso liquido pos-sangria"),
        ),
        declared_loss=None,
        tolerance=None,
    )

    assert balanco.status is BalanceStatus.DECLARED
    assert balanco.result is BalanceResult.INDETERMINATE
    assert balanco.unaccounted_quantity is None
    assert any("Bases de medição incompatíveis" in motivo for motivo in balanco.reasons)


def test_balanco_exato_e_balanced() -> None:
    balanco = compute_transformation_balance(
        inputs=(_entrada(Decimal("300")),),
        outputs=(_saida(Decimal("150")), _saida(Decimal("150"))),
        declared_loss=None,
        tolerance=None,
    )

    assert balanco.status is BalanceStatus.ASSESSED
    assert balanco.result is BalanceResult.BALANCED
    assert balanco.output_total == Decimal("300")
    assert balanco.unaccounted_quantity == Decimal("0")


def test_fan_in_soma_multiplas_entradas_como_soma_multiplas_saidas() -> None:
    """Passo 11.6: duas entradas de 150kg cada fecham com duas saídas de 150kg."""
    balanco = compute_transformation_balance(
        inputs=(_entrada(Decimal("150")), _entrada(Decimal("150"))),
        outputs=(_saida(Decimal("140")), _saida(Decimal("160"))),
        declared_loss=None,
        tolerance=None,
    )

    assert balanco.status is BalanceStatus.ASSESSED
    assert balanco.result is BalanceResult.BALANCED
    assert balanco.input_total == Decimal("300")
    assert balanco.output_total == Decimal("300")


def test_declared_loss_e_descontado_antes_do_nao_explicado() -> None:
    """Perda conhecida e diferença não explicada não podem ser somadas às cegas."""
    balanco = compute_transformation_balance(
        inputs=(_entrada(Decimal("300")),),
        outputs=(_saida(Decimal("140")), _saida(Decimal("150"))),
        declared_loss=Decimal("5"),
        tolerance=None,
    )

    assert balanco.declared_loss == Decimal("5")
    # 300 - 290 - 5 = 5, nao 10: a perda declarada ja foi descontada.
    assert balanco.unaccounted_quantity == Decimal("5")


def test_diferenca_dentro_da_tolerancia() -> None:
    balanco = compute_transformation_balance(
        inputs=(_entrada(Decimal("300")),),
        outputs=(_saida(Decimal("148")), _saida(Decimal("150"))),
        declared_loss=None,
        tolerance=Decimal("3"),
    )

    assert balanco.result is BalanceResult.WITHIN_TOLERANCE


def test_diferenca_fora_da_tolerancia() -> None:
    balanco = compute_transformation_balance(
        inputs=(_entrada(Decimal("300")),),
        outputs=(_saida(Decimal("100")), _saida(Decimal("100"))),
        declared_loss=None,
        tolerance=Decimal("3"),
    )

    assert balanco.result is BalanceResult.OUTSIDE_TOLERANCE
    assert balanco.unaccounted_quantity == Decimal("100")


def test_sem_tolerancia_declarada_qualquer_diferenca_fica_fora() -> None:
    """Ausência de tolerância é lida como zero: só bate exato."""
    balanco = compute_transformation_balance(
        inputs=(_entrada(Decimal("300")),),
        outputs=(_saida(Decimal("149")), _saida(Decimal("150"))),
        declared_loss=None,
        tolerance=None,
    )

    assert balanco.result is BalanceResult.OUTSIDE_TOLERANCE
    assert balanco.tolerance is None
