# PLAN — Declaração documental de GTA

**Data:** 15 de setembro de 2026
**SPEC:** `docs/specs/approved/2026-09-15-declaracao-gta-documental.md` (aprovada como está)
**Escopo:** desenho técnico exato para BUILD. Resolve a única pergunta aberta que a SPEC deixou para o
PLAN — onde a validação do payload de GTA vive e como ela se integra ao contrato de erro já existente.

---

## Decisão de desenho: validação na Presentation, antes do Application

**Achado que resolve a pergunta aberta.** `registrar_aquisicao_documental`
(`apps/api/livestock_writes.py:1046`) já tem uma armadilha para este caso: `except ValueError as error:
raise _conflito(error)` mapeia qualquer `ValueError` do Application para **409**, não 422. Isso está correto
para os usos atuais (`ValueError` ali sinaliza conflito de domínio — ex.: `HistoryCoverage` com datas
invertidas), mas "faltou o campo `gta_number` no payload" não é um conflito, é entrada malformada. Deixar a
validação de GTA propagar como `ValueError` genérico produziria `409` onde o critério de aceite da SPEC
exige `422`.

O próprio arquivo já resolve esse tipo de caso duas vezes, no mesmo padrão (`apps/api/
livestock_writes.py:1811` `_json_limitado`; `:2189-2209`, validação de enum antes do serviço): validar a
forma da entrada **na função do endpoint, antes de instanciar/chamar o serviço**, levantando `DomainProblem`
com `status_code=422` diretamente. Este PLAN segue o mesmo padrão — nenhum padrão novo é introduzido.

## Arquivos afetados

### 1. `packages/livestock_application/gta_declaration.py` (novo)

Módulo pequeno, sem I/O, só validação pura — para ser testável sem HTTP/banco. Não é um serviço (não tem
repositório, não persiste nada); é a regra de forma que a SPEC pede.

```python
"""Validacao do payload de fato importado do tipo GTA (SPEC 2026-09-15)."""

GTA_DECLARED_FACT_TYPE = "livestock.gta_declared"

REQUIRED_STRING_FIELDS = (
    "gta_number",
    "issuing_agency",
    "origin_description",
    "destination_description",
    "purpose",
)


class GtaPayloadInvalido(ValueError):
    """Payload de fato importado tipo GTA nao atende ao contrato minimo da SPEC."""

    def __init__(self, campo: str, motivo: str) -> None:
        self.campo = campo
        self.motivo = motivo
        super().__init__(f"{campo}: {motivo}")


def validar_payload_gta(payload: dict) -> None:
    """Levanta GtaPayloadInvalido no primeiro campo invalido; None se valido."""
    for campo in REQUIRED_STRING_FIELDS:
        valor = payload.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            raise GtaPayloadInvalido(campo, "obrigatorio e nao pode ser vazio.")

    estado = payload.get("issuing_state")
    if not isinstance(estado, str) or len(estado.strip()) != 2 or not estado.strip().isupper():
        raise GtaPayloadInvalido(
            "issuing_state", "deve conter exatamente 2 letras maiusculas (ex: 'MS')."
        )

    emitida_em = payload.get("issued_at")
    if not isinstance(emitida_em, str):
        raise GtaPayloadInvalido("issued_at", "obrigatorio, formato de data ISO 8601.")
    try:
        date.fromisoformat(emitida_em)
    except ValueError as error:
        raise GtaPayloadInvalido(
            "issued_at", "nao e uma data ISO 8601 valida (ex: '2026-09-10')."
        ) from error

    quantidade = payload.get("animal_count")
    if not isinstance(quantidade, int) or isinstance(quantidade, bool) or quantidade <= 0:
        raise GtaPayloadInvalido("animal_count", "deve ser um inteiro positivo.")
```

Notas de implementação:
- `isinstance(quantidade, bool)` é excluído explicitamente porque `bool` é subclasse de `int` em Python —
  `True`/`False` não podem passar como contagem válida.
- `date.fromisoformat` (não `datetime`) porque a data de emissão da GTA é uma data civil, não um instante —
  `issued_at` no payload de GTA é distinto de `occurred_at`/`imported_at` do `ImportedLivestockFact`
  (esses continuam `datetime` UTC, sem mudança).
- Campos opcionais (`sanitary_conditions`, `veterinarian_name`) não são validados aqui — a SPEC não exige
  formato para eles.

### 2. `apps/api/livestock_writes.py` — `registrar_aquisicao_documental` (linha ~1046)

Inserir validação logo após receber `corpo`, antes de montar `artifact_service`/`imported_fact_service`:

```python
for item in corpo.imported_facts:
    if item.fact_type == GTA_DECLARED_FACT_TYPE:
        try:
            validar_payload_gta(item.payload)
        except GtaPayloadInvalido as error:
            raise DomainProblem(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                reason_code="PAYLOAD_GTA_INVALIDO",
                title="Payload de GTA invalido",
                detail=str(error),
            ) from error
```

Import novo: `from packages.livestock_application.gta_declaration import (GTA_DECLARED_FACT_TYPE,
GtaPayloadInvalido, validar_payload_gta)`.

Nenhuma outra linha da função muda — o restante do fluxo (chamada ao `DocumentaryAcquisitionService`,
tratamento de `KeyError`/`ValueError` já existente) permanece intacto, porque a validação de GTA já
resolveu antes de chegar lá.

### 3. Nenhuma mudança em domínio, aplicação genérica ou persistência

Confirmado pela SPEC e reforçado aqui: `ImportedLivestockFact` (domínio), `ImportedLivestockFactService`,
`ReceivedTransferArtifactService`, `DocumentaryAcquisitionService`/`acquisition_continuity_service.py`
permanecem sem alteração — eles já são genéricos o bastante. Nenhuma migration.

### 4. `apps/validacao/declaracao_gta.py` (novo)

Roteiro executável, mesmo padrão dos demais em `apps/validacao/` (descobre Organization/animal/contraparte
sozinho, mostra requisição/resposta, explica o porquê de cada passo, sonda ambiente, suporta `--pausar`).
Passos mínimos:
1. Descobre Organization e cria (ou reaproveita) `ExternalCounterparty` e `Animal` fictícios.
2. `POST .../documentary-acquisitions` com um item `livestock.gta_declared` completo → `201`.
3. Mesma chamada faltando `gta_number` → `422 PAYLOAD_GTA_INVALIDO`, mensagem nomeando o campo.
4. Mesma chamada com `issuing_state="ms"` (minúsculo) → `422`.
5. Mesma chamada com `animal_count=0` → `422`.
6. `GET .../imported-facts` confirma o fato criado no passo 2, com `fact_type="livestock.gta_declared"`.
7. Segundo animal, mesmo `gta_number`/`bundle_digest` → `201`, sem conflito (confirma que a unicidade
   continua por animal, não por GTA).
8. Auditor (sem permissão de escrita) tentando o passo 2 → `403`.

Adicionar à lista em `apps/validacao/README.md` e à suíte `apps/validacao/fumaca.py`, seguindo o padrão já
usado para os demais roteiros.

### 5. Registrado no índice de `apps/validacao/README.md`

Uma linha nova, mesmo padrão das demais entradas.

## Testes automatizados (antes do roteiro manual)

`tests/livestock_application/test_gta_declaration.py` (novo, unitário e puro — sem fake de repositório):
- payload completo válido → sem exceção;
- cada um dos 5 campos string obrigatórios ausente/vazio, individualmente → `GtaPayloadInvalido` nomeando
  o campo certo;
- `issuing_state` ausente, com 1 letra, com 3 letras, minúsculo → `GtaPayloadInvalido`;
- `issued_at` ausente, não-string, string não-ISO → `GtaPayloadInvalido`;
- `animal_count` ausente, string, zero, negativo, `True`/`False` → `GtaPayloadInvalido`;
- campos opcionais ausentes não disparam erro.

`tests/integration/test_livestock_api_saida.py` (ou arquivo de teste HTTP equivalente já usado pelo fluxo
de `documentary-acquisitions` — confirmar nome exato no início do BUILD, não travado aqui): payload de GTA
completo → `201` e fato recuperável por `GET .../imported-facts`; campo obrigatório ausente → `422
PAYLOAD_GTA_INVALIDO` **sem** persistir nada (nem artefato, nem fato — a mesma transação que cobre os
dois); dois animais com o mesmo `gta_number` → ambos `201`; `fact_type` diferente de
`"livestock.gta_declared"` com payload arbitrário → continua `201`, sem validação nova (regressão
negativa que prova que os demais tipos de fato importado não foram afetados); isolamento por Organization;
autorização (auditor não escreve).

## Portão de verificação (antes de VERIFY/ACCEPT)

```powershell
python -m uv run --locked pytest tests/livestock_application/test_gta_declaration.py <arquivo de integracao acima>
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Sem migration nova — `alembic check` deve continuar "No new upgrade operations detected."

## Documentação a atualizar no mesmo commit do BUILD

- `docs/CHECKLIST_DE_IMPLEMENTACAO.md` — nova entrada, data do BUILD, evidência e portão (regra de
  `AGENTS.md`; a SPEC e este PLAN não substituem essa entrada, per `docs/specs/README.md`).
- `docs/specs/approved/2026-09-15-declaracao-gta-documental.md` → mover para `docs/specs/implemented/`
  quando aceito.
- `apps/validacao/README.md` — nova linha para `declaracao_gta.py`.

## Fora de escopo (reafirmado da SPEC, não reaberto aqui)

Integração estadual de e-GTA, NF-e/NT 2024.003, referência tipada de propriedade externa, reconciliação com
`AnimalMovement`/`PropertyStay`, consumo por `fact_provider.py`/`Policy`/`Rule`/elegibilidade de mercado.

## Decisão necessária

Nenhuma — este PLAN preenche a única pergunta que a SPEC deixou aberta (onde a validação vive) usando um
padrão já existente no próprio arquivo, sem introduzir mecanismo novo. Pronto para BUILD mediante
autorização.
