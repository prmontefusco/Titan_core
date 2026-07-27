# ADR-0045 — Importação e Reconciliação de Qualificações de Estabelecimento

**Status:** PENDENTE  
**Data de criação:** 27 de julho de 2026  
**Autores:** Claude Code, Paulo Roberto Montefusco  

## Problema

Qualificações de estabelecimento (p. ex., `exportacao-china`, `processamento-basico`, `frigorífico-certificado`) hoje são cadastradas manualmente. O Marco 17.3 deixa as avaliações de elegibilidade por mercado dependentes dessas declarações, mas sem fonte versio nada que permita auditoria, rastreamento de mudança ou reconciliação.

**Cenário crítico:** um frigorífico perde a certificação de exportação para a China. Na API do Titan, o administrador remove manualmente a qualificação. Semanas depois, não há registro de quando foi perdida, quem a revogou ou por qual motivo — impossível distinguir entre auditoria e ocultação.

**Consequência para a elegibilidade:** a matriz mostra `ELEGIVEL` com base numa qualificação que era válida no dia do embarque mas foi revogada meses depois. O dossiê não captura a mudança porque ela é mutação sem rastreabilidade.

## Restrições

1. **Versão**: conforme ADR-0043, cada qualificação deve ser `RuleAdoption` com `valid_from`, `valid_to`, `normative_source`.
2. **Isolamento**: qualificações de estabelecimento pertencem à Organization (isolamento RLS).
3. **Idempotência**: importação da mesma fonte múltiplas vezes não duplica registros.
4. **Rastreabilidade**: dossiê do Marco 7.5 deve capturar qual qualificação estava vigente no instante da decisão.
5. **Cobertura**: deve suportar múltiplas fontes e múltiplos tipos de qualificação.

## Solução

### 1. Tipagem de Qualificação como `RuleAdoption`

Qualificação de estabelecimento não é um fato avulso. É **regra adotada pela Organization** — exatamente como a regra de carência por mercado ou a exigência sanitária.

```
EstablishmentQualification:
  - establishment_id: UUID
  - qualification_type: "exportacao-china" | "frigorífico-certificado" | ...
  - valid_from: datetime
  - valid_to: datetime | null
  - normative_source: "MAPA" | "FRIGORÍFICO" | "IMPORTADOR" | ...
  - source_document_id: UUID  # aponta para artefato recebido (ADR-0042)
```

É `RuleAdoption` para a finalidade de `market_eligibility`, com a diferença de que a adoção diz respeito a **qualificação do estabelecimento**, não a **comportamento**.

### 2. Origem da Importação

As qualificações vêm de **três fontes possíveis**:

#### 2a. **MAPA** — Ministério da Agricultura
Listagem oficial de frigoríficos habilitados à exportação. Hoje não pública de forma versio nada. Quando estiver, será consumida via provider externo (similar ao `Titan_geodata` do 17.2).

#### 2b. **Frigorífico** — Conforme contratos operacionais
Um frigorífico parceiro fornece lista de seus estabelecimentos de origem qualificados para fornecimento (cabanhas de seleção, fazendas integradas, parceiros autoriza dos). Entrada via API, com assinatura e versão.

#### 2c. **Importador** — Certificações de destino
Um comprador europeu fornece lista de fornecedores que já auditou e qualificou (p. ex., "frigoríficos de Ponta Porã habilitados para exportação à UE"). Consolida-se como conhecimento recebido, com proveniência `IMPORTADOR` e confiança condicionada a verificação.

### 3. Artefato de Transferência

Conforme ADR-0042, cada importação gera um `Artifact` que viaja dentro do dossiê:

```
Artifact:
  - type: "QUALIFICACAO_ESTABELECIMENTO_MAPA" | "QUALIFICACAO_ESTABELECIMENTO_FRIGORÍFICO"
  - received_from: Organization | null (null = fonte oficial)
  - captured_at: datetime
  - source_id: string (referência na fonte original, p. ex. número de portaria)
  - coverage_period_start: datetime
  - coverage_period_end: datetime | null
  - data_hash: string
```

### 4. Fluxo de Importação e Reconciliação

```
1. [A cada ciclo, ex. 1x/mês]
   API externa (MAPA, frigorífico) fornece lista versio nada

2. [Validação]
   - Assinatura (se de terceiro)
   - Versão (se anterior já existe, compara)
   - Integridade (campos obrigatórios, datas coerentes)

3. [Reconciliação]
   - Qualificações na versão anterior: marcadas como `valid_to = hoje - 1 dia`
   - Qualificações na nova: criadas com `valid_from = hoje`, `valid_to = null`
   - Qualificações que saíram da lista: `valid_to` atribuído

4. [Gravação]
   - Operação idempotente: mesma versão da fonte importada 2x segue
   - Tudo em transação: falha na reconciliação reverte tudo
   - Artefato gravado como testemunha

5. [Dossiê]
   - Quando elegibilidade for avaliada, dossiê cria snapshot das
     qualificações vigentes naquele instante
```

### 5. Implementação Mínima — Marco 17.3a

**Escopo:** suportar importação manual de qualificações (arquivo JSON versionado fornecido pelo administrador ou frigorífico).

**Fora do escopo:** integração automática com MAPA ou importador (requer provider, que é decisão futura).

#### Entidades

- `EstablishmentQualification` — já existe em `packages/livestock_domain/establishment_qualification.py`
- `EstablishmentQualificationImport` — novo, registro de cada importação com hash e versão
- `ImportResult` — novo, relatório de o que foi criado, atualizado, revogado

#### Serviço

```python
# packages/livestock_application/establishment_qualification_import_service.py

class EstablishmentQualificationImportService:
    def import_qualifications(
        self,
        organization_id: OrganizationId,
        qualifications: list[EstablishmentQualificationInput],
        source_type: QualificationSourceType,
        source_version: str,
        artifact_id: ArtifactId | None,
    ) -> ImportResult:
        """
        Importa lista versio nada de qualificações.
        
        - Válida formato e datas
        - Reconcilia com versão anterior (marca revogadas, cria novas)
        - Devolve relatório de mudanças
        - Cria audit entry
        
        Idempotente: mesma source_version importada 2x não duplica.
        """
```

#### API

```python
# apps/api/livestock_writes.py (adicionar)

@router.post("/v1/establishments/qualifications/import")
async def import_establishment_qualifications(
    organization: CurrentOrganization,
    request: ImportQualificationsRequest,
) -> ImportResult:
    """
    Importa lista versio nada de qualificações de estabelecimento.
    
    POST /v1/establishments/qualifications/import
    {
        "source_type": "FRIGORÍFICO",
        "source_version": "2026-07-27T00:00Z",
        "artifact_id": "...",  # opcional
        "qualifications": [
            {
                "establishment_id": "...",
                "qualification_type": "exportacao-china",
                "valid_from": "2026-07-27",
                "valid_to": null,
                "normative_source": "FRIGORÍFICO"
            }
        ]
    }
    
    Response (200):
    {
        "imported": 42,
        "revoked": 3,
        "unchanged": 15,
        "rejected": 0,
        "errors": [],
        "source_version": "...",
        "applied_at": "..."
    }
    """
```

#### Teste de Validação Manual

```bash
python -m apps.validacao.importacao_qualificacao_estabelecimento --pausar
```

Roteiro:
1. Importar lista manual de qualificações com fontes diferentes
2. Verificar versio namento e `valid_from`/`valid_to`
3. Reimportar versão anterior → reconciliação e revogação
4. Verificar dossiê captura qual qualificação estava vigente
5. Testar idempotência: importação 2x da mesma versão

---

## Próximos Passos

- **ADR-0046** (futuro): Integração com MAPA via provider externo versionado
- **ADR-0047** (futuro): Notificação e auditoria de revogação de qualificação
- **Marco 17.4**: Carência por mercado (prazo de medicamento varia por país)

## Referências

- **ADR-0041**: Elegibilidade por finalidade
- **ADR-0042**: Contraparte externa e artefato recebido
- **ADR-0043**: Governança e versionamento de regras
- **ADR-0026**: Georreferenciamento e conformidade territorial
- **Passo 7.5**: Dossiê e reprodutibilidade
