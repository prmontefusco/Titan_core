# Checklist de Implementação — Titan

**Atualizado em:** 6 de agosto de 2026
**Fonte dos passos e do estado operacional:** este documento é a única fonte — `docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md` foi consolidado aqui e removido em 6 de agosto de 2026 (ver nota abaixo).
**Próximo passo planejado:** adequações de conformidade da ADR-0048 antes de usar o motor atual como base de novas capacidades regulatórias. A redação da ADR-0049 pode prosseguir, mas não declara conformidade integral antes dessas adequações.

> **Consolidação documental em 6 de agosto de 2026.** Este checklist parava no Passo 17.2 e escondia duas frentes inteiras de trabalho já concluídas: a conformidade sanitária vitalícia (`LIV-C01` a `LIV-C09`, `POST-LIV-01`, `POST-LIV-02A` — Marco 18) e o primeiro produto de frontend do Livestock (`LIVESTOCK_PRODUCT_EXECUTION_PACKAGE.md`, Ondas 0–5 — Marco 19). Ambos foram incorporados como entradas de primeira classe (ver Marcos 18 e 19, antes de "Notas de rumo"). `docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md` foi removido: sua divisão de papéis com este checklist ("plano define passos, checklist registra status") havia colapsado na prática, e é exatamente esse tipo de fronteira teórica entre documentos que causou a bifurcação. Os critérios de conclusão, riscos/controles e regra de interrupção que ainda valiam migraram para a seção "Protocolo e critérios de conclusão" abaixo.

> **Atualização documental em 30/07/2026:** as ADRs `0050` a `0055` devem ser
> tratadas como **ACEITAS**, e o documento
> `docs/architecture-specification/TITAN_ARCHITECTURE_PRINCIPLES.md` passa a
> ser usado como **documento norteador complementar**. Nenhum desses
> documentos revoga `DOMAIN.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md` ou o
> checklist; eles refinam a interpretação arquitetural para os próximos
> incrementos.

> **Validação operacional FUNAI concluída em 04/08/2026.** A vertical Livestock
> agora possui leitura técnica de sobreposição territorial FUNAI por
> propriedade (`GET /v1/livestock/properties/{property_id}/territorial-overlaps/funai`),
> fato governável `livestock.territorial.funai`, template
> `rule-sobreposicao-funai` publicado no catálogo e roteiro executável
> `apps/validacao/funai.py` **rodado com 5/5 passos aprovados** contra API real,
> Keycloak real e `Titan_geodata` real. O caso validado para o imóvel
> `MS-5006606-3DCF573FEF1E44B9972057BD4C932A9E` respondeu `SEM_RESTRICAO`,
> `feature_count = 0` e `gaps = []`, comprovando também o comportamento
> esperado quando a camada `FUNAI_TI` está carregada no provider, mas não há
> interseção materializada em `layers` para a fazenda consultada.
>
> **Próximo passo explícito desta frente:** deliberadamente **não** foi
> amarrado nenhum `MarketProfile` padrão a essa regra ainda. A capacidade
> técnica está fechada; falta apenas decisão normativa explícita sobre qual
> mercado deve consumir `rule-sobreposicao-funai` por padrão e com qual efeito
> comercial.

> **Ponto de parada em 30/07/2026 (ADR-0052/0054/0055):** o Core avançou além
> do estado descrito acima para a trilha de decisões explicáveis. A Fase 1 da
> ADR-0050 já havia sido concluída; agora a governança de decisão possui
> persistência real para `DecisionProposal`, `DecisionReview`,
> `DecisionOverride` e `ContestationRecord` (migration `20260730_0062`), o
> `Dossier` passou a carregar a seção `governance` quando essa trilha existir,
> e o fluxo humano já valida aprovações múltiplas mínimas e impede reutilizar o
> mesmo revisor para satisfazer mais de uma aprovação. Na frente temporal, o
> `FactSnapshot` passou a declarar `knowledge_limitations` quando a reprodução
> histórica depende de `recorded_at` ou `observed_at` como aproximação de
> `known_at`, e o `HistoricalReproduction` agora separa **divergência real** de
> **limitação temporal declarada**. Isso fortalece a honestidade da ADR-0052,
> mas **não** fecha ainda a modelagem completa de `known_at` contextual,
> `accepted_at` e demais tempos do eixo de conhecimento.

## Protocolo e critérios de conclusão

**Migrado de `docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md` em 6 de agosto de 2026**, antes de sua remoção — o protocolo por passo (reler documentos de autoridade, escopo único, diff revisável, rodar testes/Ruff/Mypy relacionados) já está coberto por `AGENTS.md`/`DEVELOPMENT.md` e não foi duplicado aqui; só o que era específico deste checklist migrou.

### Critérios de conclusão por marco (Marcos 0–10)

| Marco | Evidência de conclusão |
|---|---|
| 0 | Documentos de autoridade coerentes e decisões aprovadas |
| 1 | Ambiente reproduzível, health check e CI verde |
| 2 | Contratos universais determinísticos, sem termos pecuários |
| 3 | Autenticação, papéis e isolamento comprovados com duas Organizations |
| 4 | Histórico append-only, adulteração detectável, checkpoints, prova temporal, idempotência e concorrência testadas |
| 5 | Evidências imutáveis, assinaturas por perfil, rotação de chaves e proveniência reconstruível |
| 6 | Decisão reproduzível e explicável a partir de política versionada |
| 7 | Genealogia, não conformidade, recall, dossiê, verificação externa e sincronização comprovados sem vertical |
| 8 | Identidade, movimentação e lotes pecuários com histórico temporal |
| 9 | Fluxo farmacológico bloqueia, corrige e reavalia sem apagar o passado |
| 10 | Vertical usa o Core sem contaminá-lo; API e dossiê são verificáveis |

Marcos 11 em diante (expansões pós-MVP) não têm critério tabelado — cada um é decomposto e validado no seu próprio registro abaixo.

### Riscos e controles

| Risco | Controle no plano |
|---|---|
| Escopo grande demais | Um incremento vertical coeso; dividir quando responsabilidades ou riscos forem independentes |
| Core contaminado pela vertical | Contrato de provider e teste arquitetural |
| Dado de uma Organization exposto a outra | Testes negativos desde Identity & Access e em todo endpoint |
| "Imutabilidade" apenas convencional | Append-only, correções vinculadas e verificador de integridade |
| Relógio local apresentado como prova temporal | Instante observado separado de timestamp externo validado |
| TSA indisponível causar carimbo fabricado ou perda | Checkpoint pendente, retry e provider equivalente sem retroatividade |
| Chave privada armazenada junto aos dados | KeyProvider e armazenamento protegido externo ao banco e ao código |
| Rotação ou comprometimento apagar validade histórica | `key_id`, certificados públicos preservados, revogação e análise de impacto |
| Certificado self-signed apresentado como qualificado | Profiles explícitos e trust anchor declarado em cada verificação |
| Integridade ou assinatura confundida com verdade | Resultado explica escopo criptográfico e nunca certifica conteúdo material |
| ICP-Brasil apresentada como qualificação automática na UE | Perfil por jurisdição, Trusted Lists aplicáveis e revisão jurídica |
| Decisão impossível de reproduzir | Snapshots, serialização canônica, versões e hashes |
| Regra regulatória incorreta | Fonte normativa, aprovação humana, vigência e testes de borda |
| Dependência prematura de integração/hardware | Entrada manual e adaptadores somente quando necessários |
| Complexidade excessiva | Diff revisável; contratos genéricos só entram quando exigidos pelo incremento atual |
| "Gratuito" confundido com custo zero | Inventário de licenças e registro dos custos inevitáveis de infraestrutura e operação |
| Gratuidade incompatível com confiança acreditada | Core gratuito com providers substituíveis; serviços qualificados são opcionais e têm custo registrado |
| Core abstrato sem prova | Providers falsos, provas de contrato e cenário genérico completo antes da vertical |
| Divergência documental | Marco 0 obrigatório e releitura antes de cada passo |
| Validação manual subjetiva | Roteiro observável com resultados esperados em cada entrega |

### Regra de interrupção

O trabalho deve parar imediatamente quando:

- houver conflito entre documento de autoridade e código;
- uma regra necessária não existir em `DOMAIN.md`;
- critérios de aceitação estiverem ambíguos;
- o incremento misturar funcionalidades ou responsabilidades independentes;
- surgir alteração de API pública não aprovada;
- uma dependência nova não tiver justificativa;
- um teste relacionado falhar;
- Ruff ou Mypy falhar;
- a validação manual for reprovada.

Após a interrupção, deve-se apresentar evidências e solicitar uma decisão; nunca escolher silenciosamente.

## Adequações obrigatórias da ADR-0048

> **ADR-0048 aceita em 29/07/2026.** O Core e a matriz de elegibilidade já possuem implementações parciais de `FactSnapshot`, `Evaluation`, `DecisionReason` e `Decision`, mas ainda não satisfazem todos os critérios da arquitetura de decisões explicáveis e reproduzíveis. Os itens abaixo não bloqueiam a redação da ADR-0049; bloqueiam apenas alegações de conformidade integral ou de emissão regulatória oficial pelo caminho automático atual.

| Item | Estado | Objetivo e critério de aceite |
|---|---|---|
| **T1 — Proveniência no hash de `FactSnapshot`** | CONCLUÍDO | `FactSnapshot.create()` passou a usar representação canônica versionada e o `snapshot_hash` já cobre `source_reference`; alterar a proveniência muda a identidade do snapshot, com testes cobrindo a regressão. |
| **T2 — Temporalidade de conhecimento** | PARCIAL | `Fact`, `FactSnapshot` e `HistoricalReproduction` já distinguem `reference_time` de `knowledge_cutoff`, excluem conhecimento posterior do snapshot e registram `knowledge_limitations` quando a reprodução depende de fallback por `recorded_at`/`observed_at`. Ainda falta a modelagem completa de `known_at` contextual, `accepted_at` e demais tempos do eixo de conhecimento para alegar conformidade integral. |
| **T3 — Autoridade e método de emissão** | CONCLUÍDO | `DecisionAuthorityProfile` foi implementado, persistido e encadeado à `Decision`; emissão automática agora recusa `Evaluation` inelegível e ausência/invalidade de autoridade com código estruturado, e o dossiê já preserva perfil, referência e método de emissão. |
| **T4 — Proposta para revisão humana** | PARCIAL | `DecisionProposal`, `DecisionReview`, persistência de governança e emissão humana com aprovações mínimas já existem; `Decision` automática não é mais emitida quando a `Evaluation` pede revisão humana. Ainda falta um caller de produção que crie a proposta automaticamente no caminho recusado da API/vertical e trate o fluxo ponta a ponta sem exceção técnica. |

### Testes obrigatórios de não regressão

- `REVISAO_HUMANA_NECESSARIA` não pode emitir `Decision` automática;
- ausência de autoridade não pode emitir `Decision`;
- alteração de `source_reference` deve alterar `snapshot_hash`;
- reprodução histórica não pode usar conhecimento posterior.

Os quatro itens devem ser implementados em incrementos separados, com testes focados e roteiro executável caso a alteração exponha comportamento observável pela API.

> **Nota de numeração:** a numeração deste checklist havia divergido do `PLANO_DE_IMPLEMENTACAO_VALIDADO.md`, que é a autoridade. Os registros do Marco 9 abaixo seguem a numeração do **PLANO**: 9.1 Medication e MedicationBatch, 9.2 VeterinaryPrescription, 9.3 TreatmentApplication, 9.4 WithdrawalPeriod, 9.5 elegibilidade farmacológica, 9.6 avaliação de lote. A entrega anterior rotulada "9.1 — Agregadores de Medicamentos e Prescrições" cobriu, na prática, o Medication do PLANO-9.1 **e** o VeterinaryPrescription do PLANO-9.2; o MedicationBatch que faltava no PLANO-9.1 foi entregue depois.

> **Nota sobre o 10.1a e o 10.1b:** o PLANO define um único Passo 10.1 (Timeline Livestock). Ele foi dividido em dois na execução, com aprovação do responsável, porque a timeline pressupõe eventos que a vertical ainda não emitia — o **10.1a** faz a vertical emitir, o **10.1b** entrega a consulta cronológica que o PLANO descreve. A divisão é de execução, não de escopo: o 10.1 do PLANO só estará cumprido ao fim do 10.1b.

> **Nota de retomada em 26/07/2026:** o checklist estava defasado em relação ao código. Desde a última consolidação, o backend avançou além do Marco 12: genealogia, reprodução, saída do rebanho, governança de regras, matriz de elegibilidade por mercado, exigibilidade sanitária mínima, prescrição veterinária e autorização de tratamento por prescrição de animal ou lote já foram implementadas e commitadas. Este documento passa a refletir o estado real do backend e ordena os próximos incrementos por criticidade.

> **Ponto de parada em 26/07/2026:** a continuidade da ADR-0042 ficou validada até o ponto em que fato importado alimenta a elegibilidade farmacológica. O roteiro `apps.validacao.fato_importado` passou após a correção do dossiê para contribuição importada (`757370e fix(livestock): montar dossie com fato importado`). Para retomar, começar pela matriz de elegibilidade explicável por mercado: cada célula deve dizer mercado, regra/adoption/version, resultado, motivos, lacunas, requisitos e ação corretiva. Em seguida, criar um roteiro executável de simulação comercial que percorra fazenda → animal → histórico/tratamento/importação → frigorífico → elegibilidade por China/EUA/UE.

> **Nota de revisão em 27/07/2026:** a matriz avançou em três pontos críticos: falha fechada quando o mercado não declara carência própria, substituição auditável de adoção governada e finalidade de mercado canonizada por `Value Object`. Isso reduz risco comercial e desalinha menos a implementação da ADR-0044. Ainda assim, o status continua parcial em relação à tese completa da ADR-0041: a avaliação segue projetando uma decisão farmacológica base para múltiplos mercados, sem `REAVALIACAO_NECESSARIA`, sem sujeito secundário exercitado e sem decisão independente por finalidade.

> **Ponto de parada em 27/07/2026:** a matriz passou a exercitar sujeito secundário de forma auditável no caso da China. O endpoint aceita `slaughterhouse_counterparty_id`, a célula chinesa só promove `ELEGIVEL` quando existe frigorífico selecionado e qualificação explícita do estabelecimento para `exportacao-china`, e essa qualificação fica registrada como dado append-only próprio. O roteiro `apps/validacao/simulacao_comercial.py` já percorre esse fluxo fim a fim. Na retomada, o próximo passo natural é substituir o cadastro manual dessa qualificação por importação ou reconciliação com fonte externa versionada.

> **Revisão arquitetural em 27/07/2026 (pós-implementação):** ADR-0045 foi prototipada e depois revisada. A primeira versão incorretamente tipava `EstablishmentQualification` como `RuleAdoption`, violando ADR-0043. Decisão: `RuleAdoption` permanece representando a adoção de uma regra normativa, enquanto `EstablishmentQualificationAssertion` representa fato temporal verificável ("estabelecimento X possui habilitação Y segundo fonte Z, observado em data W"). Segunda correção: reconciliação não inventa `effective_until` — quando uma qualificação sai de lista, cria-se `Assertion` com `status=UNKNOWN` e `confidence=BAIXA`, registrando que mudança ocorreu mas data exata é desconhecida. Isso mantém rastreabilidade e honestidade temporal. A prototipagem em `EstablishmentQualificationImportService` servirá como base, mas a implementação será refatorada para criar `AssertionAssertion` (não `RuleAdoption`). A arquitetura resultante (Regra → Fato → Evaluation → Decision → Dossier) alinha-se com ADR-0041/0042/0043/0044 e especializa NR-7 (Assertion como conceito).

> **Validação em 27/07/2026 (fim da sessão):** Responsável identificou 4 correções críticas antes de aceitar ADR-0045: (1) UNKNOWN não resulta em REJEITADO; resulta em INDETERMINADO (conforme ADR-0041). (2) Ausência em lista só tem significado se `SourceCoverage` declarar COMPLETE_SNAPSHOT — adicionar `snapshot_semantics` obrigatório. (3) Eliminar ALTO/MÉDIO/BAIXO; usar `ConfidenceLevel` canônico. (4) Formalizar effective time (quando ocorreu) vs knowledge time (quando soube) para reprodução histórica vs auditoria retrospectiva. Também: `source_artifact_id` obrigatório para importações externas (invariante de domínio). ADR-0045 fica em PENDENTE até refatoração com essas correções. Prototipagem de `EstablishmentQualificationImportService` foi consolidada em 7 commits, com 756/756 testes passando.

> **ADR-0045 aceita em 27/07/2026, após três rodadas de revisão arquitetural.** Terceira rodada corrigiu: definição de `COMPLETE_SNAPSHOT` (ausência habilita significado, mas não decide — a Policy decide); introdução de `SourceArtifact` como entidade própria carregando `source_version`/hash/cobertura, com Assertion apenas referenciando `source_artifact_id`; `ConfidenceLevel` deixa de ser campo do payload HTTP e passa a ser computado pelo Titan a partir da proveniência; exemplo `UNKNOWN + INFORMED` corrigido para não violar a obrigatoriedade de artefato. Documento também registra um padrão emergente a observar (não generalizar ainda): modelagem bitemporal (`effective_*` = valid time; `observed_at`/`recorded_at` = knowledge time), útil para qualquer fato cuja verdade no mundo diverge de quando o Titan tomou conhecimento dela (CAR retroativo, embargo, status sanitário, documento cancelado). **Próximo passo: refatorar a implementação prototipada (`EstablishmentQualificationImportService`) conforme a arquitetura final desta ADR.**

> **ADR-0045 implementada em 27/07/2026, commit `112aa70`, e alinhada ao fluxo manual em 29/07/2026.** Prototipagem anterior removida e substituída por `QualificationSourceArtifact`/`SourceCoverage` (`packages/livestock_domain/qualification_source_artifact.py`), `EstablishmentQualificationAssertion`/`AssertionStatus` (`packages/livestock_domain/establishment_qualification_assertion.py`), e `QualificationAssertionImportService` com `compute_confidence()` computando a confiança a partir do contexto de chamada (`packages/livestock_application/qualification_assertion_import_service.py`). Duas tabelas novas com RLS forçado na migration `20260727_0056`. Endpoint `POST /v1/livestock/establishments/qualification-assertions/import` sem campo `confidence` no payload. O endpoint manual de qualificação continua existindo por compatibilidade operacional, mas agora também grava `QualificationSourceArtifact` + `EstablishmentQualificationAssertion`, e a elegibilidade passa a preferir essa trilha bitemporal como fonte de decisão; o modelo legado fica como fallback de compatibilidade, não como fonte paralela preferencial. Testes cobrem reconciliação com cobertura, distinção entre reprodução histórica e auditoria retrospectiva, além da convergência manual→assertion.

> **Investigação do item 1 concluída em 27/07/2026, commit `90d3eba`.** Achado estrutural: `tests/integration/test_livestock_api_leitura.py` tem `pytestmark = skipif(not DATABASE_URL, ...)` — sem `TITAN_DATABASE_URL` configurada, os 3 testes de matriz de mercado eram pulados em silêncio, e isso vinha acontecendo desde que os testes foram escritos. A linha do checklist que citava um desses testes como evidência de item `CONCLUÍDO` (27/07, "falha fechada sem carência declarada") nunca havia rodado de verdade contra PostgreSQL. Três bugs de fixture, nenhum em código de produção: (1) `_criar_policy_de_regra` criava a `Policy` como `draft` e nunca publicava — `PolicyEvaluationService` recusa avaliar draft desde o commit fundacional do motor (Marco 6), então isso nunca poderia ter funcionado; (2) o perfil da UE tem dois requisitos (carência + rastreabilidade, este último adicionado no commit `09d3417`) mas o helper só adotava regra para carência, e como `AUSENTE` tem precedência sobre `INDETERMINADO` na agregação, o requisito sem adoção mascarava o resultado que o teste queria exercitar; (3) a regra fictícia de carência declarava `required_evidence_types=["livestock.treatment_applied"]`, um tipo de fato que só existe via importação externa (ADR-0042) e que o cenário nunca produz — a regra real de produção (`build_eligibility_rule`, `eligibility.py`) não declara nenhum. Corrigidos os três; **932/932 testes passando**, zero pulados com o banco configurado corretamente.

> **Investigação do item 2 concluída em 27/07/2026 (sem alteração de código).** O checklist marcava "Não iniciado", mas o mecanismo de avaliação independente por mercado já existe e está em produção: `MarketEligibilityService._requirement_result` cria `Evaluation`/`Decision` própria por requisito (não uma decisão farmacológica única projetada em colunas), sujeito secundário funciona (`dependent_subject_key`, testado com o frigorífico da China), e `MarketProjectionStatus.REAVALIACAO_NECESSARIA` já existe com lógica em `_projection_status_from_policies` e cobertura de teste unitário (`test_market_eligibility.py:626-631`). Confirmado também que não há caminho de produção alternativo: o único call site (`apps/api/livestock_queries.py:325`) sempre popula os parâmetros que ativam `use_independent_evaluation=True`. **O que falta de fato é pequeno**: um teste de integração/E2E que exercite `REAVALIACAO_NECESSARIA` via API real (hoje só testado na unidade). Item reclassificado de "Não iniciado" para "Implementado, falta cobertura E2E de reavaliação normativa".

> **Item 3 (simulação comercial) validado e concluído em 27/07/2026, commit `f504614`.** Rodado de ponta a ponta contra Docker (PostgreSQL, Keycloak) e API reais — não apenas testes automatizados. Três bugs reais, todos nos roteiros executáveis, nenhum em código de produção: (1) `_preparar_regras_de_mercado` (`apps/validacao/matriz_elegibilidade_mercados.py`, compartilhado pelos dois roteiros) criava as Policy como `draft` e nunca publicava — mesmo padrão do item 1, corrigido com `publish_policy()`; (2) a regra de carência declarava `required_evidence_types=("livestock.treatment_applied",)`, um `fact_type` que nunca aparece como `Fact` isolado no snapshot (o `fact_provider.py` só o usa para compor o payload interno de `livestock.withdrawal`), prendendo a regra em `INDETERMINADO` para sempre mesmo com o fato importado corretamente — removido, espelhando `build_eligibility_rule` (produção), que não declara nenhum; (3) só depois de corrigir os dois anteriores apareceu um terceiro bug, de aritmética de datas: `simulacao_comercial.py` importava um tratamento 30 dias antes da transferência com `withdrawal_period_days=45`, deixando o animal genuinamente em carência no dia da avaliação (30 < 45) — a regra respondia `NAO_ELEGIVEL` corretamente, mas o roteiro esperava `ELEGIVEL`; ajustado para 60 dias. Com os três corrigidos, `matriz_elegibilidade_mercados` (4/4 passos) e `simulacao_comercial` (11/11 passos) passam integralmente, incluindo matriz China/EUA/UE lado a lado, qualificação de estabelecimento, reavaliação com sujeito escolhido, saída por abate, listagem histórica e negação de permissão ao auditor.

> **Item 4 (exigibilidade sanitária como regra governada) — mecanismo concluído em 27/07/2026, commit `82ade66`.** Investigação prévia mostrou que `SanitaryRequirementService` era uma capacidade completamente à parte da governança (vocabulário próprio `ATENDIDA`/`AUSENTE`/`INDETERMINADA`, sem `Policy`/`RuleVersion`/`RuleAdoption`, endpoint isolado que a matriz de mercado nunca consultava). Duas opções foram apresentadas ao responsável antes de qualquer código: (A) atalho especial-casado dentro de `market_eligibility.py`; (B) espelhar exatamente o padrão já usado para habilitação de estabelecimento — `fact_type` novo por campanha + regra governada normal. **Opção B escolhida.** Implementado: `sanitary_requirement_fact_type(campaign_code)` em `fact_provider.py`, emitindo um `Fact` por campanha sanitária conhecida da organização (reaproveitando `SanitaryRequirementService`, sem duplicar sua lógica); `SANITARY_RULE_CODE` novo em `market_eligibility.py`, só a constante — confirmado que nenhuma mudança na máquina de avaliação foi necessária, porque `use_independent_evaluation` já está sempre ativo em produção e aceita qualquer `rule_code` novo. **Deliberadamente não feito agora, por decisão do responsável:** nenhum `MarketProfile` foi amarrado a uma campanha específica — isso é decisão normativa real (qual mercado exige qual vacina/campanha), não deste mecanismo, e ficaria inventado se eu escolhesse. 5 testes novos, smoke test manual dos dois roteiros aprovados (4/4 e 11/11) confirmando que o wiring novo em `_eligibility_components` não regride nada. Próximo aprofundamento: adotar uma regra sanitária real para um mercado, quando houver decisão normativa que a sustente.

> **Item 6 (hardening de API) concluído em 27/07/2026, commit `77eba12`.** Análise sistemática do OpenAPI real (72 operações, servidor rodando) mostrou que o contrato de erro já estava consistente — `(401, 403, 404, 409, 422)` presentes em 69 das 72 operações, exceções todas justificadas (verificação hermética pública por desenho, endpoints técnicos). De 4 endpoints inicialmente sinalizados sem paginação, 2 eram falso-positivo descoberto na investigação: `/animals/{id}/descendants` retorna só crias diretas, e `/animals/{id}/reproductive-events` é o histórico de uma única fêmea — ambos naturalmente limitados pela biologia, paginação ali seria engenharia sem necessidade real. Corrigidos apenas os 2 com risco genuíno de crescimento sem teto: `GET /rule-governance/rule-identities/{id}/timeline` (cresce a cada ação de governança ao longo dos anos) e `GET /livestock/dossiers?subject_id=` (cada avaliação gera um dossiê novo, pode acumular indefinidamente). Mudança de contrato: a timeline de regras deixa de devolver lista nua e passa a `{items, limit, offset, has_more}`, como as demais listagens paginadas — dois testes de integração e o roteiro `governanca_regras.py` ajustados. Smoke test manual dos três roteiros aprovados (`governanca_regras` 6/6, `matriz_elegibilidade_mercados` 4/4, `simulacao_comercial` 11/11) confirma que nada regrediu. Descrições ausentes no Swagger (40 das 72 operações têm `summary` mas não `description`) ficaram deliberadamente de fora — é trabalho de redação sem risco funcional, não arquitetura.

> **Item 7 (corte do MVP) concluído em 27/07/2026 — `docs/CORTE_MVP_BACKEND.md`.** Resumo executivo do que está dentro (Core, ciclo de vida do animal, farmacovigilância, campanhas sanitárias, governança de regras, elegibilidade por mercado, proveniência externa, API HTTP com 72 operações, seis roteiros de validação aprovados) e do que está deliberadamente fora (amarração mercado→campanha sanitária, avaliação territorial de camadas de terceiro, importação automática de qualificação de estabelecimento, fornecedor indireto ponta a ponta, rastreabilidade de produto/EPCIS, autoria de regra por administrador não-programador, âncora temporal por documento de terceiro, frontend). Inclui tabela de riscos conhecidos (relógio de dispositivo como prova temporal, fornecedor indireto sem GTA, autoria de regra concentrada em desenvolvedor, modelo de receita indefinido, `Assertion` como padrão emergente não generalizado, cobertura E2E de `REAVALIACAO_NECESSARIA`) e ordem de próximos marcos por valor comercial, não por dependência técnica. O documento não substitui o checklist — é a leitura de cima para baixo; o checklist continua sendo a fonte de verdade passo a passo.

> **ADR-0046 (Marco 11 — transformação industrial e rastreabilidade de produto) aceita em 28/07/2026, após duas rodadas de revisão arquitetural.** `docs/adr/0046-transformacao-industrial-e-rastreabilidade-de-produto.md`. Decisões centrais: contrato de `TransformationEvent` nasce N→M (listas de entrada/saída sempre, mesmo N=1) mas o primeiro cenário provado é fan-out 1→N — fan-in fica para o Marco 11b; abate e desossa são `TransformationEvent`s distintos, não um evento composto; `TransformationEvent` é a fonte autoritativa dos seus participantes, `UniversalRelation` é só projeção navegável (nunca fonte concorrente), replicando o padrão já usado em `reference_projection`; quem pode ser entrada/saída é decisão do `process_type` da vertical, não do Core; `TransformationBalance` é opcional e pode ficar `INDETERMINATE`/`NOT_ASSESSED` — nunca conservação silenciosa, e `declared_loss` (perda conhecida) nunca se confunde com `unaccounted_quantity` (diferença inexplicada); `AnimalExit` e `TransformationEvent` são conceitos distintos, com a dívida semântica de `AnimalExit(ABATE)` ("destinado" vs. "confirmado") explicitamente registrada e **não** resolvida nesta ADR. **Correção bloqueante da segunda rodada:** abate ocorre tipicamente no frigorífico, uma Organization distinta da fazenda — `SlaughterService` não pode orquestrar `AnimalExit` (Organization fazenda) e `TransformationEvent` (Organization frigorífico) na mesma transação; o caso inter-organizacional segue o protocolo já estabelecido pela ADR-0042 (contraparte externa + continuidade de proveniência), e `TransformationEvent(SLAUGHTER)` só pode ser declarado por quem tem representação local autorizada do animal recebido. 15 invariantes estruturais formalizados. Refinamentos finais pós-aceite: regras assimétricas de `INPUT`/`OUTPUT` explicitadas dentro de `TransformationParticipant` (output sempre cria sujeito novo, input nunca cria), seção "Não objetivos desta ADR" (embalagem logística, AggregationEvent/AssociationEvent/ObjectEvent do EPCIS, EPCIS completo, otimização de processo, estoque), diagrama conceitual da cadeia (Animal → AnimalExit → TransformationEvent → fan-out → TraceableItem → UniversalRelation → RecallService → Dossier) e nota distinguindo `TransformationEvent` (fato persistente do domínio) do `DomainEvent` do mecanismo append-only do Core, homônimos por convenção EPCIS, não pelo mecanismo do Titan. Decomposição proposta: 11.1 (esta ADR) a 11.7 (correção de evento publicado).

> **Passo 11.2 (fan-out real de abate) implementado e validado em 28/07/2026.** `packages/livestock_domain/transformation.py` (`ProcessType`, `ParticipantRole`, `ConsumptionMode`, `TraceableItemType`, `TransformationParticipant`, `TraceableItem`, `TransformationBalance`, `TransformationEvent`, com todos os invariantes estruturais da ADR-0046 validados em `__post_init__`); `packages/livestock_application/transformation_service.py` (`SlaughterService.register_slaughter`, fan-out mínimo de 2 saídas, exige `AnimalExit(ABATE)` já registrada antes da transformação — `AnimalNaoAbatido` —, recusa reaproveitar o mesmo animal como entrada duas vezes — `AnimalJaTransformado`, lida consultando a própria projeção `transformation.input_of` em vez de repositório dedicado); duas tabelas novas (`transformation_events`, `traceable_items`) com RLS forçado, migration `20260728_0057`; endpoint `POST /v1/livestock/transformations/slaughter` (só escrita — consulta de `TraceableItem` fica para 11.3/11.5, deliberadamente fora deste incremento); permissão `LIVESTOCK_TRANSFORMATION.REGISTRAR` nova. 34 testes novos (domínio + aplicação, com fakes) cobrindo fan-out mínimo, fronteira de Organization, dupla transformação e papéis assimétricos INPUT/OUTPUT — 806 testes totais aprovados, Ruff, Ruff format e Mypy (473 arquivos) limpos, `alembic upgrade head` e `alembic check` sem divergência. **Validação manual em 8/8 passos** via roteiro executável (`apps/validacao/transformacao_industrial.py`) contra API, PostgreSQL e Keycloak reais: propriedade de origem, propriedade do frigorífico (mesma Organization), animal, recusa de transformação sem saída ABATE (409), recusa de fan-out insuficiente pelo próprio contrato HTTP (422, `Field(min_length=2)`), saída ABATE, transformação com fan-out real (2 `TraceableItem` criados a partir de 1 animal), e recusa de reaproveitar o mesmo animal (409). **Achado paralelo, não bloqueante:** `tests/integration/test_authorization_postgresql.py::test_role_grant_and_revocation_change_effective_permissions_without_direct_user_link` trava indefinidamente quando a suíte completa roda contra PostgreSQL real — reproduzido isoladamente, sem lock de banco nem uso de CPU durante a trava; pré-existente e sem relação com este incremento; sinalizado como tarefa separada.

> **Passo 11.3 (timeline e recall de `TraceableItem`) implementado e validado em 28/07/2026.** `LivestockTimelineService.item_timeline()` novo (`packages/livestock_application/timeline_service.py`): o item não tem histórico próprio (nenhuma correção existe ainda, Passo 11.7) — toda a linha do tempo vem da `TransformationEvent` em que ele participa, descoberta pela mesma projeção `UniversalRelation` que o Passo 11.2 grava (`transformation.input_of`/`output_of`), sem tabela nova. `animal_timeline()` estendido pelo mesmo mecanismo, para que a transformação que consumiu o animal também apareça na história dele — o mesmo fato citado dos dois lados, nunca duplicado (mesmo princípio do parto na genealogia). Dois endpoints novos de recall (`GET /v1/livestock/traceable-items/{item_id}/recall` e `GET /v1/livestock/animals/{animal_id}/recall`), primeira exposição HTTP de `RecallService` (Passo 7.4) na vertical Livestock — reaproveitado sem alteração, com `direction=AMBAS` (necessário porque toda relação de transformação aponta do participante para o evento, nunca o contrário; alcançar "o outro lado" sempre exige combinar saída e entrada no nó do evento) e `relation_types` restrito ao grafo de transformação. Permissão nova `LIVESTOCK_TRACEABILITY.LER`, distinta de `TIMELINE_LER` pelo mesmo motivo que separou `ANIMAL_LER_GENEALOGIA` de `ANIMAL_LER`. **Achado durante a validação manual, não um defeito:** num grafo em estrela (1 evento com 1 entrada e 2 saídas), a travessia `AMBAS` reexplora o centro a partir de cada folha já visitada, e `RecallService` declara isso `ciclo_detectado` — o que torna `status=inconclusivo` por definição (`core_domain/recall.py`: "qualquer lacuna torna o resultado inconclusivo, sem exceção"), mesmo quando todos os 4 nós do grafo foram visitados e o alvo foi genuinamente alcançado. Comportamento correto e esperado para fan-out/fan-in, não uma lacuna de cobertura real; o roteiro de validação foi ajustado para conferir alcance por caminho, não o status agregado. 2 testes novos de timeline (unitários, com fakes) — 808 testes totais aprovados, Ruff, Ruff format e Mypy (474 arquivos) limpos; nenhuma migration nova, reaproveita as tabelas do Passo 11.2. **Validação manual em 11/11 passos** via roteiro executável (`apps/validacao/transformacao_industrial.py`, estendido do Passo 11.2) contra API, PostgreSQL e Keycloak reais, incluindo travessia retrospectiva (item → transformação → animal) e prospectiva (animal → transformação → os dois itens).

> **Passo 11.4 (balanço mínimo) implementado e validado em 28/07/2026.** `compute_transformation_balance()` novo (`packages/livestock_application/transformation_service.py`), função pura: sem peso de entrada declarado, produz `NOT_ASSESSED`/`NOT_APPLICABLE` — nunca zero nem `BALANCED` por omissão (mesmo princípio da ADR-0040); saída sem quantidade ou unidades incompatíveis entre entrada e saídas produzem `DECLARED`/`INDETERMINATE`; bases de medição incompatíveis (ex.: peso vivo vs. peso líquido pós-sangria) nunca são comparadas numericamente — item 7 da ADR-0046, `INDETERMINATE` sempre, jamais um número inventado; com peso e bases compatíveis, calcula `ASSESSED` com `BALANCED`/`WITHIN_TOLERANCE`/`OUTSIDE_TOLERANCE` conforme a tolerância declarada (ausência de tolerância é lida como zero — só bate exato). `declared_loss` (perda conhecida) é descontado antes de calcular `unaccounted_quantity` (diferença ainda não explicada) — as duas nunca são somadas às cegas. `SlaughterService.register_slaughter` ganhou `input_quantity`/`input_unit`/`input_measurement_basis`/`declared_loss`/`tolerance` opcionais e agora sempre anexa um `TransformationBalance` ao evento (nunca `None` bruto); `TransactionalTransformationEventRepository` deixou de gravar `balance=None` fixo e passou a serializar/desserializar o balanço via JSONB, sem migration nova (a coluna já existia, criada mas não usada desde o Passo 11.2). Endpoint `POST /v1/livestock/transformations/slaughter` expõe os cinco campos novos e devolve o balanço completo na resposta. 15 testes novos (9 unitários da função pura, 3 de validação de domínio de `TransformationBalance`, 2 de conexão no `SlaughterService`, mais a extensão do roteiro) — 823 testes totais aprovados, Ruff, Ruff format e Mypy (475 arquivos) limpos; nenhuma migration nova. **Validação manual em 17/17 passos** via roteiro executável (`apps/validacao/transformacao_industrial.py`, estendido dos Passos 11.2/11.3) contra API, PostgreSQL e Keycloak reais: transformação com 300kg de entrada e duas saídas de 150kg na mesma base produz `BALANCED`; transformação sem peso de entrada produz `NOT_ASSESSED`.

> **Bug real encontrado e corrigido durante a validação do Passo 11.4, com origem no Passo 11.2.** `alembic check` reportava remoção das tabelas `transformation_events`/`traceable_items` e do índice `ix_traceable_items_transformation` — não porque devessem ser removidas, mas porque `packages/livestock_infrastructure/persistence/transformation_repository.py` nunca havia sido importado por `packages/livestock_infrastructure/persistence/__init__.py`. Sem esse import, as `Table(...)` do módulo nunca executavam, e as duas tabelas nunca chegavam à `MetaData` compartilhada que o Alembic usa para comparar contra o banco — o autogenerate as via como "não fazem parte do modelo" e propunha removê-las, embora existissem de verdade desde a migration `20260728_0057`. **Isto esteve quebrado desde o Passo 11.2**; a validação daquele passo (e do 11.3) rodou `alembic check` em segundo plano e confiou na notificação de conclusão sem ler o conteúdo da saída — o mesmo tipo de falha de verificação que o item 1 da fila já havia exposto em outra frente nesta sessão. Corrigido: import de `transformation_repository` acrescentado a `persistence/__init__.py` e a `packages/core_infrastructure/persistence/migrations/env.py` (mesmo padrão dos demais módulos da vertical); o índice, que só existia na migration e não na definição SQLAlchemy da tabela, foi declarado também em `traceable_items_table`. `alembic check` agora responde "No new upgrade operations detected." Nenhuma migration nova foi necessária — o banco já estava correto, só a metadata Python é que não enxergava as tabelas.

> **Passo 11.5 (API e dossiê do `TraceableItem`) implementado e validado em 28/07/2026.** Dois endpoints novos em `apps/api/livestock_queries.py`: `GET /v1/livestock/traceable-items/{item_id}` (identidade mínima — tipo, rótulo, transformação criadora) e `GET /v1/livestock/traceable-items/{item_id}/dossier` (agregado único reunindo a transformação que criou o item com seu balanço, a relação quantitativa declarada — quantidade/unidade/base de medição do próprio item dentro do evento —, a linha do tempo, as origens alcançadas por recall com cobertura/lacunas, e as evidências citadas pela transformação, resolvidas via `evidence_content()` do Core, reaproveitado sem alteração). **Não é o Dossier do Core**: aquele exige uma `Decision`, e nenhuma regra ainda avalia `TraceableItem` — este é um documento de leitura próprio da vertical, montado a partir de dados já existentes, sem nenhuma gravação nova. Reaproveita integralmente os mecanismos dos Passos 11.2-11.4 (`item_timeline`, `_executar_recall_de_transformacao`, `TransformationEvent.balance`) sem alterar nenhum deles — o dossiê é composição, não mecanismo novo.
>
> **Achado durante a validação manual, corrigido antes do commit:** a rota `/dossier` foi gateada inicialmente com `DOSSIER_LER`, a mesma permissão do Dossier do Core — mas `DOSSIER_LER` é deliberadamente excluída do papel `OPERADOR_PECUARIO` ("o dossiê fica de fora — a prova é do auditor"), uma separação que faz sentido para o documento de decisão do Core, mas não para este agregado: o dossiê do item não expõe nada que o operador não possa já obter via `/timeline` e `/recall` (ambas sob `TIMELINE_LER`/`TRACEABILITY_LER`, que o operador tem), só reúne num lugar só. Corrigido para exigir `TIMELINE_LER`, a mesma permissão do detalhe e da timeline do item. Nenhum teste automatizado pegou isso — só apareceu ao rodar o roteiro com o usuário operador real, reforçando por que a validação manual continua sendo parte do portão, e não um complemento opcional.
>
> **Validação manual em 19/19 passos** via roteiro executável (`apps/validacao/transformacao_industrial.py`, estendido dos Passos 11.2-11.4) contra API, PostgreSQL e Keycloak reais: detalhe do item confere `item_type`; dossiê confere `balance.result=BALANCED`, `quantitative.quantity="150.000"`, `timeline.entry_count>=1` e `origins` alcançando o animal de origem — tudo num único documento. Ruff, Ruff format e Mypy (475 arquivos) limpos, 823 testes automatizados aprovados, nenhuma migration nova.

> **Passo 11.6 (fan-in real de desossa) implementado e validado em 28/07/2026.** `DeboningService` novo (`packages/livestock_application/transformation_service.py`), registrando `TransformationEvent(DEBONING)` com duas ou mais entradas rastreáveis (`CARCASS`/`HALF_CARCASS`, já produzidas por um `SLAUGHTER` anterior) e uma ou mais saídas novas. **Refatoração que precedeu o serviço, justificada pela segunda ocorrência real (NR-7):** `SlaughterOutputSpec` renomeado para `TransformationOutputSpec` (mesma forma, agora compartilhada entre os dois processos); `compute_transformation_balance()` generalizado para somar N entradas (`QuantifiedAmount`) pela mesma regra que já somava N saídas — fan-in usa exatamente o mesmo cálculo do fan-out, sem lógica duplicada; `_project_relations` e a guarda de reaproveitamento (`_ja_usado_como_entrada`) viraram funções de módulo compartilhadas pelos dois serviços, em vez de métodos duplicados. Perfil do processo (item 6 da ADR): só `CARCASS`/`HALF_CARCASS` são aceitos como entrada de `DEBONING` — decisão do serviço, não do Core. Endpoint novo `POST /v1/livestock/transformations/deboning`, reaproveitando a permissão `LIVESTOCK_TRANSFORMATION.REGISTRAR` (mesma capacidade, processo diferente — não é um verbo novo). A projeção em estrela do Passo 11.2 (toda entrada e toda saída aponta para o mesmo evento, nunca uma para a outra) já bastava para o fan-in preservar o **conjunto** de origens sem inventar correspondência 1:1 (invariante 15) — nenhuma alteração em `RelationService`/`RecallService` foi necessária. 26 testes novos (9 do `DeboningService`, 2 de balanço fan-in, atualização dos 9 testes de balanço existentes para a nova assinatura) — 834 testes totais aprovados, Ruff, Ruff format e Mypy (476 arquivos) limpos, nenhuma migration nova (processo é só um valor de string numa coluna já existente). **Validação manual em 24/24 passos** via roteiro executável (`apps/validacao/transformacao_industrial.py`, estendido dos Passos 11.2-11.5) contra API, PostgreSQL e Keycloak reais: fan-in insuficiente recusado pelo contrato HTTP (422); fan-in real com as duas meias-carcaças do Passo 11.2 (201); reaproveitamento de entrada recusado (409); tipo de entrada não permitido recusado (409, um `CUT_BATCH` não serve de entrada); e recall a partir do item criado pela desossa alcançando `visited_nodes=7` — as duas meias-carcaças (fan-in) e, mais fundo no grafo, o animal original do abate, provando a cadeia completa animal → abate → desossa sem nenhuma alteração no mecanismo de travessia. **Próximo passo: decidir com o responsável se inicia o Passo 11.7 (correção de evento publicado) — último item da decomposição do Marco 11.**

> **ADR-0047 (correção de `TransformationEvent` publicado, Passo 11.7) aceita em 28/07/2026, após três rodadas de revisão arquitetural.** `docs/adr/0047-correcao-de-transformationevent-publicado.md`. Segue o precedente de correção de `TreatmentApplication` (Marco 9): a correção nunca edita o original, cria um `TransformationEvent` novo e completo apontando para o original via `corrects_transformation_id`. Decisões centrais que vão além do precedente do Marco 9, porque `TransformationEvent` cria `TraceableItem`s que podem já ter sido consumidos a jusante: (1) estado derivado `CURRENT`/`SUPERSEDED` — nunca armazenado, calculado por busca reversa de `corrects_transformation_id`; um item cujo evento criador está `SUPERSEDED` não pode ser entrada de nova transformação, mas continua totalmente consultável; (2) cadeia de correção linear — `UNIQUE(corrects_transformation_id)` no banco (múltiplos `NULL` permitidos) impede bifurcação estruturalmente, e a guarda de serviço recusa corrigir um evento que não seja o leaf atual da cadeia; (3) entradas removidas por uma correção ficam livres automaticamente, sem contabilidade extra — consequência direta do estado derivado, não uma regra separada; (4) "consumida a jusante" definida com precisão (só bloqueia se o consumidor está `CURRENT`, olhando somente as saídas do leaf sendo corrigido) — correção em cascata fica recusada, não resolvida, dívida registrada como a ADR-0046 já fez com `AnimalExit(ABATE)`; (5) `correction_reason` obrigatório em toda correção. **Correção bloqueante da segunda rodada:** `CURRENT`/`SUPERSEDED` não é absoluto — formalizadas duas funções distintas, `operational_status_now` (guardas de escrita, sempre "agora") e `status_as_known_at(known_until)` (reconstrução histórica, considerando só correções com `recorded_at <= known_until`), reaproveitando o eixo bitemporal da ADR-0045 sem mecanismo novo (o `TimelineCutoff.known_until` já existente já resolve isso). **Correção bloqueante da terceira rodada, a mais importante:** protocolo de concorrência explícito — a `UNIQUE` sozinha impede duas correções concorrentes do mesmo evento, mas não impede uma correção concorrendo com o consumo de suas saídas; toda escrita (registro normal e correção) precisa bloquear (`SELECT ... FOR UPDATE`) os sujeitos envolvidos em ordem determinística (evento alvo → entradas por id → saídas por id), revalidar disponibilidade depois do bloqueio, e persistir evento + itens novos + projeções numa única transação atômica. `RecallService`/`LivestockTimelineService` não são alterados (continuam leitura histórica completa); a vertical passa a anotar o estado derivado em cada nó exposto, e o dossiê do item ganha `transformation.status`. Nenhum código escrito ainda — puramente arquitetural.

> **Passo 11.7 (correção de `TransformationEvent` publicado) implementado e validado em 28/07/2026, conforme ADR-0047.** `TransformationEvent` ganhou `corrects_transformation_id`/`correction_reason` (dupla guarda no `__post_init__`: `entity_type` correto, evento não corrige a si mesmo, `correction_reason` obrigatório sse há correção) — `packages/livestock_domain/transformation.py`, mais o enum `TransformationStatus` (`CURRENT`/`SUPERSEDED`, vocabulário puro, sem lógica de cálculo). Migration `20260728_0058` acrescenta as duas colunas com `UNIQUE(corrects_transformation_id)` (múltiplos `NULL` permitidos — invariante 7) e FK auto-referenciada; `get_correction_of()` novo no repositório (busca reversa O(1), a UNIQUE garante no máximo um resultado). **Porta de bloqueio isolada** (`TransformationLockPort` em `transformation_service.py`, implementação `TransactionalTransformationLock` em `transformation_locking.py`, nova) — deliberadamente fora dos ports de leitura/escrita existentes para não alargar o raio de mudança sobre as dezenas de fakes que já os implementam; `lock_transformation_event`/`lock_traceable_item`/`lock_animal` via `SELECT ... FOR UPDATE`, provados a serializar duas transações concorrentes contra Postgres real (não só simulados). `SlaughterService`/`DeboningService` refatorados: `register_*` e o novo `correct_*` delegam a um método privado `_persist` compartilhado, que agora bloqueia (evento alvo → entradas por id → saídas do evento corrigido por id, ordem determinística) **antes** de qualquer leitura de decisão — a única leitura pós-bloqueio já serve como revalidação, sem duplicar as checagens. `operational_status_now()` novo (função de módulo, não método) resolve `CURRENT`/`SUPERSEDED` por busca reversa; `_ja_usado_como_entrada` ganhou `excluding_event_id` (reafirmar a mesma entrada do evento corrigido não dispara falso-positivo, item 7); `_guard_saida_nao_consumida_a_jusante` nova (compartilhada pelos dois serviços) recusa corrigir uma origem cuja saída já foi consumida por um evento `CURRENT` (item 9); `AlvoDeCorrecaoNaoEhVigente` (leaf-only, item 4) e `SaidaConsumidaAJusante` (item 9) são as exceções novas. Dois endpoints novos (`POST /v1/livestock/transformations/{slaughter,deboning}/{event_id}/corrections`); `TransformacaoResponse`/`DesossaResponse` ganharam `corrects_transformation_id`/`correction_reason`. Anotação de estado derivado na leitura (item 10): `TransformacaoResumoResponse` (dossiê) ganhou `status`/`corrected_by_transformation_id`, computados com `operational_status_now` no momento da consulta; `RecallPassoResponse` ganhou `de_status`/`para_status` por nó (`transformation_event` calcula direto, `traceable_item` delega ao status do evento que o criou) — `RecallService`/`LivestockTimelineService` do Core permanecem inalterados, a anotação é responsabilidade só da vertical (`livestock_queries.py`), como a ADR exigiu. 173 testes novos entre domínio, aplicação (unitários com fakes, incluindo o cenário completo de correção reafirmando entrada, recusa de leaf não vigente, recusa de saída consumida a jusante) e integração (bloqueio pessimista provado com `ThreadPoolExecutor`+`Barrier` contra Postgres real) — 1007 testes totais aprovados, Ruff e Mypy (479 arquivos) limpos, `alembic upgrade head` e `alembic check` sem divergência. **Validação manual em 28/28 passos** via roteiro executável (`apps/validacao/transformacao_industrial.py`, estendido dos Passos 11.2-11.6) contra API, PostgreSQL e Keycloak reais: correção reafirmando a mesma entrada (201, `corrects_transformation_id` preenchido), dossiê do item **original** passando a mostrar `transformation.status=SUPERSEDED` com `corrected_by_transformation_id` apontando para a correção (o item nunca foi editado nem removido), recusa de corrigir o evento que já não é o leaf da cadeia (409), e recusa de corrigir a transformação de abate do Passo 11.2 porque suas duas saídas já viraram entrada da desossa vigente do Passo 11.6 (409) — a prova de concorrência do item 5 da ADR fechou o **Marco 11 completo**.

> **Validação manual da trilha de elegibilidade orientada a mercado concluída em 30/07/2026, sem alteração de código nesta etapa.** Os cinco roteiros executáveis da trilha comercial (`apps/validacao/perfis_mercado.py`, `mercados_orientados.py`, `explicacao_comercial.py`, `matriz_elegibilidade_mercados.py`, `mercados_orientados_lote.py`) rodaram de ponta a ponta contra API, PostgreSQL e Keycloak reais — todos os passos verdes, nenhum 500. Comportamento comercial coerente: EUA elegível, China condicionada até escolher/qualificar o frigorífico (libera depois de qualificado), UE bloqueada por embargo ambiental sem regra/evidência publicada.
>
> **Três divergências de linguagem/compreensão registradas e corrigidas** (categoria "melhoria", não bug de regra): terminologia inconsistente no mesmo payload — o resumo do mercado condicionado dizia "estabelecimento **exigido**" mas o `gap`/`why` subjacente dizia "estabelecimento **escolhido**" (`market_eligibility.py`); narrativa de mercado `AUSENTE` usava o verbo errado, "não pode ser **comparado**" em vez de "avaliado" (`livestock_queries.py`, animal e lote); `affected_animal_ids` vinha preenchido com todos os animais do lote quando o bloqueio era uma pendência do mercado como um todo (estabelecimento não escolhido) e não uma diferença entre animais — corrigido para vir vazio nesse caso.
>
> **Um bug real e mais sério, encontrado ao rodar a suíte de integração completa (não só os arquivos citados no portão do incremento):** a política de RLS da migration `20260729_0059` (embargo ambiental, criada em 29-30/07/2026) referenciava `current_setting('app.current_organization_id', ...)` — uma variável que não existe em nenhum outro lugar do projeto; a convenção em todas as ~50 migrations anteriores é `titan.organization_id` (`ORGANIZATION_CONTEXT_SETTING` em `organizations.py`). Isso tornava `property_environmental_embargo_assertions` **invisível para qualquer leitura sob role restrita** (não-superusuário) — não se manifestava rodando a API local manualmente porque `titan` é superusuário e ignora RLS por padrão, mas quebrava exatamente o teste de integração desenhado para provar isolamento entre organizações sob role sem `BYPASSRLS`. Corrigida a migration (`titan.organization_id`, padrão `NULLIF(..., '')::uuid` dos demais) e reaplicada via `alembic downgrade` até antes dela seguido de `upgrade head`.
>
> **Um segundo padrão de bug, também real, em três testes de integração do Core e no script de demonstração:** `tests/integration/test_core_proof_postgresql.py`, `test_decision_postgresql.py`, `test_dossier_postgresql.py` e `apps/demo/__main__.py` salvavam uma `Decision` sem antes persistir o `DecisionAuthorityProfile` que ela referencia — FK nova do item T3 da ADR-0048 (`20260730_0060_add_decision_authority_profile.py`, também de hoje). Os quatro pontos corrigidos (persistindo o perfil antes da decisão, com `TransactionalDecisionAuthorityProfileRepository`); o de `apps/demo/__main__.py` era o mais sério dos quatro, porque não é só teste — é o script de demonstração que quebraria com 500 se alguém o rodasse contra o schema atual, já que nunca foi atualizado para passar o `authority_profile_repository` que os endpoints da API HTTP já usam desde a sanitização de hoje.
>
> **Portão completo após as correções:** 1053 testes aprovados (todos, incluindo os arquivos de integração que exigem `TITAN_DATABASE_URL` e antes ficavam pulados em silêncio nesse fluxo de trabalho), Ruff check e Ruff format limpos, Mypy limpo (493 arquivos), `alembic check` sem divergência. Os cinco roteiros manuais foram reexecutados depois de reiniciar a API com o código corrigido — continuam 100% verdes. Working tree ainda não commitado (commit adiado por decisão do responsável). **Próximo passo:** concluir a leitura de produto do MVP e decidir o congelamento de escopo.

> **Leitura de produto aprovada e escopo do MVP congelado em 30/07/2026, por decisão do responsável.** A pergunta "um operador consegue entender para onde pode vender, por que não pode, e o que falta para liberar?" foi respondida com **sim** para os três mercados validados hoje (China, EUA, UE), com a ressalva registrada de que a cobertura não se estende ainda aos itens T1/T2/T4 da ADR-0048 nem a cenários fora do roteiro comercial.
>
> **Congelamento:** entram no fechamento do MVP a trilha comercial orientada a mercado (5 roteiros validados), o mecanismo de embargo ambiental do IBAMA (ver `docs/CORTE_MVP_BACKEND.md`, seção "Embargo ambiental do IBAMA") e a infraestrutura de `DecisionAuthorityProfile` (T3 da ADR-0048) já com a persistência corrigida. `docs/CORTE_MVP_BACKEND.md` — atualizado hoje para refletir que o item 2 ("Avaliação territorial") deixou de ser "inteiramente fora": a camada IBAMA está dentro, FUNAI/PRODES/MapBiomas continuam fora — passa a ser a fonte de verdade de escopo congelado. A partir de agora, só entra mudança de código nas áreas congeladas se for correção de bug real, quebra de fluxo ou texto que impeça uso; ideia nova, generalização e expansão de escopo vão para depois do fechamento.
>
> **Backlog curto de últimos ajustes registrado:** validar manualmente o endpoint `POST /v1/livestock/properties/{property_id}/environmental-embargoes/ibama/assertions` contra o provider `Titan_geodata` real (hoje só exercitado por escrita direta no repositório, em teste); nenhum outro achado de linguagem pendente da validação de hoje. **Próximo passo:** ciclo de acabamento (item 7 da fila) — mensagens de erro, nomes de campo ambíguos, roteiros frágeis, consistência entre respostas parecidas.

> **Ciclo de acabamento (item 7) concluído em 30/07/2026.** Achado adicional: o campo `top_gaps` (`AvaliacaoMercadosResponse`/`AvaliacaoMercadosLoteResponse`) tinha nome ambíguo — sugeria uma seleção "top N" por importância, mas é a lista completa e deduplicada de lacunas por mercado, sem ranking nenhum. Renomeado para `market_gaps` em `apps/api/livestock_queries.py`, no roteiro `mercados_orientados.py` e no teste de integração correspondente — mudança de contrato de baixo risco porque não existe frontend consumindo ainda. Nenhuma outra fragilidade encontrada nos 5 roteiros nem inconsistência adicional entre respostas parecidas dentro do escopo congelado. Portão completo revalidado depois da mudança (1053 testes, Ruff, Ruff format, Mypy, `alembic check` limpos — as primeiras 4 falhas + 1 erro observadas numa rodada foram confirmadas como contenção de conexão por rodar `alembic check` em paralelo com o pytest, não regressão real: os 5 testes reexecutados isolados passaram, e a suíte completa rodada sem concorrência também passou). Roteiros manuais reexecutados contra a API reiniciada — 100% verdes.
>
> **Commit do incremento criado em 30/07/2026** (`c75d7c9`, branch `main`, 4 commits à frente de `origin/main`, não enviado): as correções de RLS, persistência de autoridade decisória, linguagem da trilha comercial e a renomeação de `top_gaps` para `market_gaps`, junto com a documentação do congelamento de escopo.
>
> **Fechamento do MVP preparado em 30/07/2026** — ver `docs/CORTE_MVP_BACKEND.md`, seção "Fechamento do MVP (30/07/2026)": fluxos prontos e validados de ponta a ponta (5 roteiros comerciais), riscos residuais explícitos (cobertura do embargo IBAMA via HTTP real pendente; suíte de integração pulada em silêncio sem `TITAN_DATABASE_URL` já mascarou dois bugs reais nesta sessão — risco estrutural agora registrado na tabela de riscos conhecidos, não só um incidente pontual) e o que fica para a próxima fase (tudo já listado em "O que está fora do MVP", sem mudança). **Este é o ponto de fechamento funcional do incremento de elegibilidade orientada a mercado.**

> **Início da implementação das ADRs 0050–0055 em 30/07/2026, por decisão e autorização explícita do responsável para modificar o Core.** As seis ADRs (todas ACEITAS em 29/07/2026) formalizam os itens T1–T4 pendentes da ADR-0048 (proveniência no hash, temporalidade, autoridade decisória, revisão humana) mais determinismo de execução (ADR-0050) e verificação formal do dossiê (ADR-0055). Três agentes de exploração leram as seis ADRs contra o código atual e confirmaram: `DOMAIN.md` já formaliza `DecisionAuthorityProfile`/`DecisionProposal`/`DecisionReview`/`DecisionChallenge` etc. para ADR-0053/0054 (o código é que precisa alcançar a especificação); `CanonicalSerializer` já existente (`packages/shared_kernel/serialization.py`) é reaproveitável para o hash canônico da ADR-0051, hoje usando `json.dumps` cru; `DecisionService.decide()` hoje converte `Evaluation` em `Decision` automática e incondicionalmente, inclusive quando `EvaluationOutcome` pede revisão humana — violação direta da ADR-0053. Plano registrado em seis fases (uma por ADR, na ordem de dependência que as próprias ADRs declaram), cada uma com portão completo e commit próprio. Fase 4 (ADR-0053) vai tocar `livestock_application/eligibility.py`/`market_eligibility.py` — o código do MVP recém-congelado — porque emitir `Decision` automática sob `REVISAO_HUMANA_NECESSARIA` é quebra de contrato real, coberta pela própria regra do congelamento.
>
> **Fase 1/6 (ADR-0050 — execução determinística e isolada) implementada e validada em 30/07/2026.** Novo `packages/core_domain/rule_execution.py`: `TechnicalFailureCategory` (vocabulário de aplicação, não enum persistido — a própria ADR-0050 §11 diz que persistência genérica exigiria definição própria no DOMAIN.md), `RuleExecutionContext` (contrato delimitado por execução — também não é entidade persistida nesta fase, ADR-0050 §6 é explícita), `RuleExecutionFailure` (exceção classificada, nunca produz `RuleResult`). `RuleEvaluationEngine.evaluate()` (`packages/core_application/evaluation_service.py`) passou a: (1) recusar com `RESOURCE_LIMIT` quando `max_conditions_evaluated` (novo campo opcional, `None` preserva o comportamento de sempre) é excedido — limite determinístico real, não simulado; (2) classificar qualquer exceção não prevista como `RUNTIME_ERROR` estruturado em vez de propagar crua; (3) detectar conflito de evidência a nível da própria Rule (antes só existia a nível de Policy via `EvidenceInconsistencyDetector`), produzindo `INDETERMINADA` quando há fatos genuinamente simultâneos (mesmo `observed_at`) com valores divergentes na chave que a condição lê. **Achado durante a implementação, corrigido antes do commit:** a primeira versão comparava valores entre *quaisquer* fatos do mesmo tipo, e quebrou `test_condition_uses_latest_fact_of_its_type` — um teste existente que tem dois fatos do mesmo tipo com valores diferentes **em instantes diferentes** (fato mais antigo dizia "rejected", mais novo diz "approved"), que é evolução temporal normal (o mesmo critério de `get_latest_fact_by_type`), não contradição. Corrigido para só considerar conflito fatos com `observed_at` idêntico — genuinamente simultâneos. Deliberadamente fora desta fase (ADR-0050 §4/§22): runtime Wasm (ADR-0036, não solicitada), modelo de unidades/dimensionalidade, DSL de autoria de regras, persistência formal do recibo de execução (fica para a Fase 2, quando `context_hash` existir de verdade). 15 testes novos (`tests/core_domain/test_rule_execution.py` novo, `tests/application/test_evaluation_service.py` estendido) — 1068 testes totais aprovados, zero regressão nos 1053 anteriores, Ruff check, Ruff format e Mypy (496 arquivos) limpos, `alembic check` sem divergência (esperado: fase sem migration). **Próximo passo: Fase 2/6 (ADR-0051 — snapshot canônico e proveniência no hash).**
>
> **Commit da Fase 1/6 criado em 30/07/2026** (`b78eb56`, branch `main`, não enviado a `origin`).
>
> **Fase 2/6 (ADR-0051 — snapshot canônico, identidade criptográfica e proveniência) implementada e validada em 30/07/2026.** Nova função `canonicalize_for_hash` (`packages/shared_kernel/serialization.py`, exportada em `shared_kernel/__init__.py`): converte recursivamente `float` para `Decimal` via texto (nunca via construtor binário) antes de serializar, porque `CanonicalSerializer` recusa `float` de propósito e payloads de vertical (peso, medição) legitimamente carregam floats. `FactSnapshot.create()` (`packages/core_domain/facts.py`) trocou `hashlib.sha256(json.dumps(...))` cru por `CanonicalPayload(schema="titan.fact_snapshot", ...)` — mesma cobertura de campos de antes (incluindo `source_reference`, que já participava do hash), agora com serialização canônica, determinística e versionada de verdade. `packages/core_domain/evaluation.py` ganhou `compute_context_hash()` (Policy/Rules/motor/finalidade — a identidade da *semântica* aplicada) separado de `compute_evaluation_hash()` (que passa a receber `context_hash` já computado em vez de reembutir `policy_id`/`policy_version`/`engine_version`/`purpose` crus); `Evaluation` ganhou o campo `context_hash` (sem default — toda Evaluation nova declara as duas identidades complementares da ADR-0051 §3) e `is_reproducible()` passou a conferir as duas identidades, não só uma. `compute_decision_hash()` (`packages/core_domain/decision.py`) parou de reembutir `policy_id`/`policy_version`/`engine_version` — já cobertos transitivamente por `evaluation_hash`/`context_hash`, duplicá-los faria a mesma informação valer por duas identidades diferentes (ADR-0051 §11). Migration `20260730_0061` adiciona `context_hash` em `evaluations`; as 719 linhas históricas já existentes no banco local foram marcadas com o sentinela `"0"*64` (nunca um digest SHA-256 real) em vez de um hash forjado, para que `is_reproducible()` responda honestamente "não" para Evaluations gravadas antes deste contrato existir — nenhuma reescreve identidade histórica (ADR-0051 §14). `DOMAIN.md` (v1.19 → v1.20): nova entrada `FactSnapshot` e a entrada `Evaluation` passou a citar explicitamente as duas Digests complementares. 4 testes novos de `canonicalize_for_hash` (`tests/shared_kernel/test_serialization.py`) — 1072 testes totais aprovados, zero regressão nos 1068 anteriores (toda a suíte de integração real contra Postgres também passou, confirmando que o novo `snapshot_hash`/`evaluation_hash`/`decision_hash` está corretamente encadeado ponta a ponta), Ruff check, Ruff format e Mypy (496 arquivos) limpos, `alembic check` sem divergência. **Próximo passo: Fase 3/6 (ADR-0052 — temporalidade válida vs. conhecimento histórico).**
>
> **Commit da Fase 2/6 criado em 30/07/2026** (`0b04422`, branch `main`, não enviado a `origin`).
>
> **Fase 3/6 (ADR-0052 — temporalidade válida, registro e conhecimento histórico) implementada e validada em 30/07/2026, com escopo deliberadamente contido.** Investigação prévia mostrou que boa parte do vocabulário temporal já existia (`Fact.known_at`/`recorded_at`/`discovered_at`, `FactSnapshot.reference_time`/`knowledge_cutoff` já filtram por conhecimento em `FactSnapshot.create`) e que `DOMAIN.md` já formaliza `HistoricalReproduction`, `HistoricalComplianceAssessment`, `CurrentReevaluation` e `CounterfactualSimulation` — só nenhuma tinha implementação de código. Decisão de escopo: implementar apenas `HistoricalReproduction` nesta fase — é a que tem contrato mais preciso e testável ("reexecução de snapshot, Policy, Rules e motor originais para verificar reprodutibilidade técnica; produz relatório imutável; Evaluation e Decision originais não são substituídas") e não depende de infraestrutura ainda inexistente (seleção de Policy "vigente à época", que `HistoricalComplianceAssessment` exigiria, ou premissas hipotéticas, que `CounterfactualSimulation` exigiria). Considerei também adicionar `reference_time`/`knowledge_cutoff` como campos próprios de `Evaluation`, mas descartei: já são acessíveis via `evaluation.fact_snapshot.effective_reference_time()`/`effective_knowledge_cutoff()`, e duplicá-los como campos novos (exigindo migration) seria redundância sem ganho real, não o que a ADR-0052 §11 pede.
>
> Novo `packages/core_domain/historical_reproduction.py` (`ReproductionReport`, imutável, com `__post_init__` garantindo que "sem divergência" e "com divergência registrada" nunca ficam inconsistentes entre si) e `packages/core_application/historical_reproduction_service.py` (`HistoricalReproductionService.reproduce()`): reexecuta exatamente as Rules e versões que `evaluation.rule_versions` registrou sobre o `fact_snapshot` já preservado — nunca consulta fato, Policy ou conhecimento atual —, recalcula `context_hash`/`evaluation_hash`/`outcome` e compara com o que a Evaluation original tem gravado. Recusa reprodução com conjunto de Rules diferente do original (a mais, a menos, ou versão trocada) com `ValueError`, porque isso seria `CounterfactualSimulation` (regras diferentes), um conceito distinto que esta fase não implementa. Persistência do relatório foi deliberadamente deixada de fora: nenhum caller precisa consultá-lo ainda, e criar uma tabela sem uso concreto seria antecipar infraestrutura. Nenhuma mudança em `DOMAIN.md` — `HistoricalReproduction` já estava formalizado. 12 testes novos (`tests/core_domain/test_historical_reproduction_domain.py`, `tests/application/test_historical_reproduction_service.py`, incluindo um teste que adultera deliberadamente o `evaluation_hash` de uma Evaluation via `dataclasses.replace` e confirma que o relatório detecta e descreve a divergência sem alterar a Evaluation original) — 1084 testes totais aprovados, zero regressão, Ruff check, Ruff format e Mypy (500 arquivos) limpos, `alembic check` sem divergência (esperado: fase sem migration). **Próximo passo: Fase 4/6 (ADR-0053 — autoridade decisória e emissão de Decision) — vai tocar `livestock_application/eligibility.py`/`market_eligibility.py`, o código do MVP recém-congelado, conforme já sinalizado.**
>
> **Commit da Fase 3/6 criado em 30/07/2026** (`f9ef374`, branch `main`, não enviado a `origin`).
>
> **Fase 4/6 (ADR-0053 — autoridade decisória, competência e emissão de Decision) implementada e validada em 30/07/2026, com escopo revisado para baixo em relação ao anunciado.** Ao planejar o registro na Fase 0, eu havia sinalizado que esta fase tocaria `livestock_application/eligibility.py`/`market_eligibility.py` (código do MVP recém-congelado). Na implementação, reconsiderei: fazer isso exigiria decidir, sem pedido explícito do responsável, o que a API HTTP deveria responder quando uma Decision é recusada (hoje não existe `DecisionProposal` real para onde encaminhar esse caso — isso é a Fase 5). Decidi então **não tocar nenhum código de vertical nesta fase** — o gate novo entra em `DecisionService.decide()` (usado por todos), mas nenhum caller de produção precisou mudar, porque nenhum deles hoje aciona os outcomes que o gate bloqueia (verificado empiricamente, não só por leitura de código: rodei a suíte completa, incluindo toda a integração contra Postgres real que exercita as rotas de elegibilidade, depois de aplicar a mudança — zero regressão). Achado relevante da investigação: `EvaluationOutcome.REVISAO_HUMANA_NECESSARIA` e `VALIDACAO_EXTERNA_PENDENTE` **não têm nenhum produtor real no Core hoje** — `aggregate_outcome()` nunca os retorna; só `EVIDENCIA_CONFLITANTE` é genuinamente alcançável (via `EvidenceInconsistencyDetector`). Isso reduziu bastante o risco real de travar algo em produção.
>
> **O que foi construído:** `DecisionEmissionRefusalCode` (vocabulário estruturado da ADR-0053 §11: `AUTHORITY_NOT_FOUND`, `AUTHORITY_EXPIRED`, `AUTHORITY_OUT_OF_SCOPE`, `REVIEW_REQUIRED`, `SEGREGATION_VIOLATION`, `EVALUATION_NOT_ELIGIBLE`) e `DecisionEmissionRefused` (`packages/core_domain/decision_governance.py`), **subclasse de `ValueError`** de propósito — preserva todo `pytest.raises(ValueError, match=...)` já escrito contra `DecisionService.decide()` sem precisar tocar um teste sequer para os casos que já existiam. `decide()` (`packages/core_application/decision_service.py`) ganhou um portão novo, o primeiro a ser checado depois da verificação de reprodutibilidade: `EvaluationOutcome` em `{EVIDENCIA_CONFLITANTE, VALIDACAO_EXTERNA_PENDENTE, REVISAO_HUMANA_NECESSARIA}` recusa emissão com `REVIEW_REQUIRED` em vez de silenciosamente virar `DecisionResult.INDETERMINADA` — a violação central que a ADR-0053 §3/§10 proíbe ("Evaluation não se converte automaticamente em Decision"). Os três `ValueError` de recusa de autoridade que já existiam (organization/purpose/vigência) passaram a carregar código estruturado (`AUTHORITY_OUT_OF_SCOPE`/`AUTHORITY_EXPIRED`), mensagem de texto preservada exatamente.
>
> **Gaps residuais registrados, não escondidos:** nenhum `DecisionEngine` coordenador foi criado (ADR-0053 §9) — o portão vive dentro do `DecisionService` existente, mais simples e sem componente novo, mas sem a resolução server-side de perfil que a ADR-0053 descreve. `DecisionAuthorityProfile` continua com formato pobre (sem Subject/território/jurisdição/segregação) e continua sendo fabricado ad-hoc pelo caller (`automated_decision_authority()` em `eligibility.py`/`market_eligibility.py`) em vez de resolvido a partir de um perfil publicado — isso é o antipadrão que a ADR-0053 rejeita explicitamente, e permanece assim. Nenhum `DecisionProposal` real é criado quando a emissão é recusada — hoje só uma exceção é lançada; a Fase 5 (ADR-0054) é onde isso ganha um destino de verdade. Vertical (`eligibility.py`/`market_eligibility.py`) não foi tocada: continua chamando `DecisionService.decide()` direto, sem tratar `DecisionEmissionRefused` — seguro hoje porque nenhum outcome bloqueado é alcançável na prática, mas fica marcado como trabalho pendente para quando `REVISAO_HUMANA_NECESSARIA` ganhar um produtor real em alguma regra.
>
> 6 testes novos (`tests/application/test_decision_service.py` estendido, incluindo os três outcomes bloqueados via `pytest.mark.parametrize`, um teste confirmando que a Evaluation original nunca é alterada pela recusa, e um teste confirmando os códigos estruturados das recusas de autoridade já existentes) — 1090 testes totais aprovados, zero regressão (suíte completa, incluindo toda a integração contra Postgres real das rotas de elegibilidade do MVP congelado), Ruff check, Ruff format e Mypy (500 arquivos) limpos, `alembic check` sem divergência (esperado: fase sem migration). **Próximo passo: Fase 5/6 (ADR-0054 — DecisionProposal, revisão humana, aprovação e override).**

> **Commit da Fase 4/6 criado em 30/07/2026** (`09ea7bc`, branch `main`, não enviado a `origin`).

> **Fase 5/6 (ADR-0054 — DecisionProposal, revisão humana, aprovação e emissão) implementada e validada em 30/07/2026, com persistência deliberadamente fora de escopo.** `DecisionService.decide()` (`packages/core_application/decision_service.py`) ganhou o parâmetro `method: DecisionEmissionMethod = AUTOMATED`: o portão de elegibilidade da Fase 4 (`_INELIGIBLE_FOR_AUTOMATIC_EMISSION`) agora só bloqueia quando `method is AUTOMATED` — é exatamente o humano que resolve, via revisão, a pendência que bloquearia o caminho automático (ADR-0054 §3). `authority_profile.can_issue_at()` passou a receber `expected_method=method` em vez de assumir `AUTOMATED` fixo, e `Decision`/`compute_decision_hash()` passaram a registrar o `method` recebido em vez de sempre `AUTOMATED`. `_derive_result`/`_build_reasons` foram promovidos a públicos (`derive_result`/`build_reasons`) para que `DecisionGovernanceService` reaproveite exatamente a mesma derivação que `decide()` usaria — evita duplicar a lógica de tradução Evaluation→resultado em dois lugares que poderiam divergir.

> `DecisionProposal` (`packages/core_domain/decision_governance.py`) foi **redesenhada**, não estendida: a forma antiga (`status`/`reviewed_at`/`reviewer_authority_id` embutidos na proposta) não tinha nenhum caller de produção, então a troca foi segura. A forma nova é uma fotografia imutável derivada da Evaluation (`evaluation_id`, `evaluation_hash`, `proposed_result`, `proposed_reasons`, `purpose`, `created_at`) sem nenhum campo de estado de revisão — rastrear "foi revisada, por quem, com que conclusão" é trabalho de um objeto separado, `DecisionReview` (novo, com `ReviewConclusion` em `APROVA`/`REJEITA`/`DEVOLVE`), consistente com o modelo mais rico que `DOMAIN.md` já formalizava para a ADR-0054. `DecisionGovernanceService` (`packages/core_application/decision_governance_service.py`, reescrito) ganhou três operações novas: `create_proposal()` (exige `evaluation.is_reproducible()`, deriva `proposed_result`/`proposed_reasons` via `DecisionService` em vez de aceitá-los como parâmetro — a proposta nunca é escolha de quem chama), `record_review()` (só exige que a autoridade revisora pertença à mesma Organization da proposta — autoridade de revisar não implica autoridade de emitir, ADR-0053 invariante 7) e `emit_after_approval()` (revalida que a review referencia exatamente esta proposta, que a proposta referencia exatamente esta Evaluation **pelo hash, não só pelo id** — detecta Evaluation trocada/mutada desde a criação da proposta — e que a conclusão é `APROVA`; só então chama `decide(..., method=HUMAN)`). `apply_override()`/`file_contestation()` (ADR-0016 antiga) não foram tocados.

> **Gaps residuais registrados, não escondidos:** nenhuma persistência real para `DecisionProposal`/`DecisionReview` (`repository: DecisionGovernanceRepositoryPort | None = None`, sem migration nova) — sem tabela, não há como impedir dupla revisão da mesma proposta, nem existe `DecisionEngine` coordenador acionando este fluxo a partir de uma emissão automática recusada; a concorrência otimista que a ADR-0054 §9 descreve também fica de fora, porque depende da persistência que ainda não existe. `DecisionOverride` continua sem produzir uma `Decision` real (só o registro de override em si), e `ReviewAssessment`/`ReviewEvidenceSubmission` (também já formalizados em `DOMAIN.md`) não foram implementados — nenhum caller de produção usa este fluxo ainda, e criar infraestrutura para eles sem uso concreto seria antecipar trabalho, mesmo raciocínio das fases anteriores. Nenhuma mudança em `DOMAIN.md` — o modelo já estava formalizado; o trabalho desta fase foi só código alcançando a especificação.

> 10 testes novos (`tests/application/test_decision_governance_service.py`, novo arquivo, cobrindo o ciclo completo proposta→revisão→emissão: derivação correta de resultado/razões, recusa de Evaluation não reproduzível, revisão feliz e recusa por Organization divergente, emissão feliz produzindo `Decision` com `emission_method=HUMAN`, `REJEITA`/`DEVOLVE` nunca emitindo via `pytest.mark.parametrize`, review referenciando proposta errada, proposta referenciando Evaluation errada, e hash de Evaluation obsoleto detectado) mais o teste existente de `tests/application/test_decision_governance.py` corrigido para o novo formato de `DecisionProposal` — 1100 testes totais aprovados, zero regressão (suíte completa, incluindo toda a integração contra Postgres real), Ruff check, Ruff format e Mypy (501 arquivos) limpos, `alembic check` sem divergência (esperado: fase sem migration). **Próximo passo: Fase 6/6 (ADR-0055 — dossiê verificável, assinatura unificada e validação independente).**

> **Commit da Fase 5/6 criado em 30/07/2026** (`9f21874`, branch `main`, não enviado a `origin`).

> **Fase 6/6 (ADR-0055 — dossiê verificável, assinatura e validação independente) implementada e validada em 30/07/2026, com escopo deliberadamente reduzido a duas lacunas concretas.** A investigação prévia mostrou que a maior parte do que a ADR-0055 pede já existe e é madura: `Dossier` (`packages/core_domain/dossier.py`) já é imutável, autocontido, versionado e verificável offline via `dossier_hash`; `VerificationBundle`/`BundleManifest`/`ValidationReport`/`BundleVerifier` (`packages/core_domain/verification.py`, ADR-0010) já implementam verificação por dimensões (nunca um booleano único), material ausente vira `INDETERMINADA` nunca `VALIDA`, e o verificador nunca consulta rede silenciosamente. Não havia necessidade de recriar nenhum desses contratos — a ADR-0055 §17.2 rejeita explicitamente manifesto paralelo. Duas lacunas concretas, já antecipadas no planejamento da Fase 0, foram fechadas:

> **1. Cadeia de autoridade/emissão ausente do Dossier (ADR-0055 §6):** `Decision` já carrega `authority_profile_id`/`authority_reference`/`emission_method` desde a Fase 4/5, mas `DossierService._build_document()` nunca os copiava para a seção `decision` do documento — um leitor externo via um resultado sem saber quem decidiu, sob qual perfil, por qual método. Campo aditivo, `DOSSIER_DOCUMENT_VERSION` 3→4 (um leitor da versão 3 continua encontrando tudo que esperava).

> **2. `Signature` sem alvo normativo estruturado (ADR-0055 §8, invariantes 27-29):** a investigação da Fase 0 já havia sinalizado dois modelos de assinatura não unificados (`CryptographicSignature` em `crypto.py`, usada por Evidence; `SignatureMaterial` em `verification.py`, usada pelo `VerificationBundle`) e nenhum com alvo estruturado — só um campo `signed_digest: str` solto, sem declarar tipo do objeto, domínio semântico ou finalidade. Escopo contido ao `SignatureMaterial` (o modelo relevante para bundle/dossiê, que é do que esta ADR trata) — `CryptographicSignature` de Evidence é outro subsistema (ADR-0038), fora do escopo desta ADR. Novo `SignaturePurpose` (StrEnum: `EMISSAO`/`REVISAO`/`APROVACAO`/`SELO_TEMPORAL`/`PRESERVACAO` — os cinco escopos distintos que a ADR-0055 §8 lista como não intercambiáveis) e `SignatureTarget` (`target_type`, `target_identifier`, `domain`, `contract_version`, `purpose`), ambos em `packages/core_domain/verification.py`. `SignatureMaterial.signed_digest: str` foi **substituído** por `signature_target: SignatureTarget` — não adicionado ao lado, para não duplicar a mesma identidade em dois campos (mesma disciplina da Fase 2 contra redundância de identidade). `BundleVerifier._check_signature()` ganhou uma checagem nova antes de comparar o digest: `signature_target.target_type` precisa ser `"bundle_manifest"`, senão `INVALIDA` — fecha o invariante 28 ("assinatura de objeto não se estende implicitamente a objetos relacionados") de forma executável, não só declarativa. `VerificationBundleService.build_from_dossier()` continua rebindando o alvo para o manifesto real (que só existe depois de montado), preservando a `purpose` que o chamador declarou.

> **Gaps residuais registrados, não escondidos:** `NormativeBasisSnapshot` (mencionado no roteiro original da Fase 0) não foi criado — a Policy e as Rules já viajam por extenso no documento do Dossier (`_build_document` já copia `policy`/`rules` completos), então o ganho concreto de um objeto adicional não ficou claro sem um caso de uso real que o consumisse; nenhuma vertical pede isso hoje. `CryptographicSignature` (Evidence, ADR-0038) não ganhou `SignatureTarget` — permanece como estava, é outro subsistema. `DecisionProposal`/`DecisionReview`/`DecisionOverride` da ADR-0054 ainda não aparecem na seção `decision` do Dossier (a ADR-0055 §6 os lista como "quando existentes" — hoje nenhum caller de produção cria propostas/revisões reais, então não há material para incluir; fica para quando a Fase 5 ganhar um caller real). Nenhum `ValidationReport` novo por dimensões de redaction/preservação foi criado — o `BundleVerifier` existente já cobre estrutura, serialização, integridade, assinatura, tempo, revogação e cobertura; redaction como derivado com nova identidade (ADR-0055 §12) não foi implementada, pois nenhum caller pede divulgação seletiva hoje. Verificador independente como CLI/pacote standalone (ADR-0055 §18 "test vectors e testes de verificador independente") não foi criado — a suíte de testes já exercita `BundleVerifier` de ponta a ponta com pacotes serializados/desserializados (`test_bundle_travels_and_is_verified_without_titan`), mas não há um binário ou pacote publicável fora do Core ainda.

> Novo `tests/core_domain/test_verification_domain.py` (8 testes: construção válida de `SignatureTarget`, cada validação de `__post_init__`, e os cinco `SignaturePurpose` distintos) e um teste novo em `tests/application/test_verification_bundle.py` (`test_signature_targeting_a_different_object_type_is_invalid`, cobrindo o invariante 28 diretamente) mais os testes de `test_dossier_service.py` estendidos com as asserções da cadeia de autoridade. Os 5 sites de construção de `SignatureMaterial` em produção e testes (`verification_service.py` ×2, `test_verification_api.py`, `test_verification_bundle.py` ×2, `test_core_proof_postgresql.py`) foram atualizados para `signature_target` estruturado, incluindo a integração real contra Postgres. `DOMAIN.md` (v1.20 → v1.21): a entrada `Signature`, que era um stub de duas linhas, ganhou a formalização de `SignatureTarget`/`SignaturePurpose` e dos invariantes de não-transferência entre objetos assinados. 19 testes novos — 1109 testes totais aprovados, zero regressão, Ruff check, Ruff format e Mypy (503 arquivos) limpos, `alembic check` sem divergência (esperado: fase sem migration, nenhuma tabela nova).

> **Encerramento do roteiro de seis fases (ADRs 0050-0055).** Todas as seis ADRs aceitas em 29/07/2026 têm implementação contida e validada no Core, cada uma com portão completo, entrada própria neste checklist e commit isolado. O que ficou deliberadamente de fora de cada fase está documentado nela mesma, não escondido — é trabalho real para quando um caller de produção precisar dele, não uma pretensão de conformidade integral com as seis ADRs.

> **Abertura do backlog pós-MVP em 30/07/2026.** Com o MVP funcionalmente fechado e congelado, o trabalho seguinte deixa de ser uma fila única e passa a ser governado por **duas trilhas explícitas**, para não misturar estabilização arquitetural com expansão de produto.
>
> **Trilha A — Saneamento do Core (prioridade inicial).** Entram aqui apenas itens que aumentam corretude, robustez, auditabilidade e aderência ao desenho já aceito, sem ampliar escopo comercial. Ordem inicial recomendada: (1) fechar a borda de produção da ADR-0054, ligando a recusa automática ao fluxo real de `DecisionProposal`/revisão na API ou vertical chamadora; (2) decidir o escopo restante da ADR-0052 (`known_at` contextual, `accepted_at` e tempos correlatos) em vez de deixá-lo implícito; (3) criar o roteiro executável do embargo IBAMA via caminho HTTP real contra o provider `Titan_geodata`; (4) continuar removendo riscos operacionais de ambiente que possam mascarar regressões de integração.
>
> **Trilha B — Evolução de Produto (depois da estabilização mínima).** Entram aqui apenas capacidades novas com ganho de valor para operador, auditor ou cliente, sem reabrir o corte do MVP já aceito. Ordem inicial recomendada: (1) avaliação territorial além do primeiro corte de IBAMA; (2) integração real de qualificação de estabelecimento por fonte externa versionada; (3) frontend sobre contratos já congelados; (4) demais ampliações regulatórias e comerciais fora do escopo do MVP.
>
> **Regra de governança desta fase:** item da Trilha B não puxa automaticamente item da Trilha A, e vice-versa. Cada novo incremento deve declarar em qual trilha entra, qual risco reduz ou qual valor agrega, e por que merece precedência sobre os demais.
>
> **Frentes escolhidas pelo responsável em 30/07/2026.** Ficam formalmente abertas para a fase pós-MVP as seguintes frentes, nesta ordem lógica de leitura e priorização: **Trilha A:** (1) fechar a borda de produção da ADR-0054; (2) completar ou decidir explicitamente o escopo residual da ADR-0052; (3) criar o roteiro executável do embargo IBAMA via HTTP real; **Trilha B:** (4) avaliação territorial; (5) integração externa real de qualificação de estabelecimento; (6) frontend. Nenhuma dessas frentes reabre o MVP já aceito; elas passam a compor o backlog da fase seguinte.

> **Mapeamento do provider territorial consolidado em 03/08/2026.** O `Titan_geodata` local evoluiu além do contrato originalmente consumido pelo Titan. Leitura direta do código e dos testes do provider (`C:\programing\Titan_geodata\backend\app\api\v1\endpoints\sicar.py`, `C:\programing\Titan_geodata\backend\app\services\sicar_service.py`, `C:\programing\Titan_geodata\backend\tests\test_sicar.py`) confirmou dois endpoints novos relevantes para a Trilha B: `GET /api/v1/sicar/farm`, que aceita **ou** `cod_imovel` **ou** `lat`/`lng` e devolve payload consolidado com `lookup`, `property`, `layers` e `coverage`; e `GET /api/v1/sicar/farm/timeline`, que aceita o mesmo lookup e devolve série anual por camada temporal. Camadas já exercitadas nos testes do provider: `TB_PRODES`, `TB_DETER` e `IBAMA_EMBARGOS`. O timeline devolve, por ano, pelo menos `feature_count`, `source_area_hectares`, `overlap_area_hectares` e `version_ids`, além de `source`, `layer`, `year_from`, `year_to` e `property_area_hectares` no envelope.

> **Direção recomendada a partir desse achado (03/08/2026).** Não estender `PropertyEnvironmentalEmbargoAssertion` para tudo. A trilha territorial deve nascer sobre dois contratos distintos do provider: (1) **snapshot territorial consolidado** via `farm`, para lookup do imóvel e sobreposições/camadas atuais; (2) **timeline territorial** via `farm/timeline`, para fenômenos cuja pergunta correta é temporal, não apenas espacial. Ordem sugerida de implementação no Titan: **B1.** adaptar o adapter geodata para entender `farm` como nova entrada principal, preservando `lookup`, `coverage`, `version_ids` e metadados necessários à auditoria; **B2.** introduzir contrato interno separado para timeline territorial; **B3.** iniciar a trilha temporal por `PRODES`, depois `DETER`, porque esses já nascem alinhados à pergunta regulatória certa; **B4.** só então modelar `FUNAI` e a evolução do `IBAMA` no novo desenho, sem reusar indevidamente o vocabulário de `environmental_embargo` para toda restrição territorial.
>
> **Frente ativa a partir de 30/07/2026:** iniciar pela **ADR-0054 na borda de produção**, por ser a intervenção com melhor relação entre risco reduzido e impacto estrutural imediato. Critério de saída esperado: uma chamada real de API ou vertical deixa de apenas receber `DecisionEmissionRefused` e passa a produzir/encaminhar a `DecisionProposal` de revisão humana de forma operacional, auditável e testada ponta a ponta.
>
> **Fechamento parcial da frente ADR-0054 em 30/07/2026.** O primeiro corte operacional da borda de produção foi saneado: `eligibility.py` e `market_eligibility.py` agora preservam a `Evaluation`, criam `DecisionProposal` real via `DecisionGovernanceService` e interrompem a emissão automática quando o Core recusa com `REVIEW_REQUIRED`; `apps/api/livestock_queries.py` converte esse caso em `409 application/problem+json` com `reason_code="REVISAO_HUMANA_NECESSARIA"`, `evaluation_id`, `proposal_id` e `proposal_result`, em vez de deixar o fluxo cair em `500`. Evidência automática: testes de serviço (`tests/livestock_application/test_eligibility_service.py`, `tests/livestock_application/test_market_eligibility.py`) verdes, teste de integração PostgreSQL/API (`tests/integration/test_livestock_api_leitura.py`) validando ponta a ponta que um snapshot conflitante (`EVIDENCIA_CONFLITANTE`) abre proposta persistida e retorna `409` estável ao cliente.
>
> **Próxima frente ativa a partir de 30/07/2026:** **ADR-0052 residual**, para decidir e registrar explicitamente o que falta do eixo temporal de conhecimento (`known_at` contextual, `accepted_at` e tempos correlatos) antes de expandir novas capacidades regulatórias sobre premissas temporais implícitas.
>
> **Saneamento mínimo da ADR-0052 iniciado em 30/07/2026.** O Core passa a tratar `accepted_at` de forma **explícita no contrato de `Fact`**, mas ainda não como critério completo de seleção histórica ou admissibilidade normativa. Decisão deliberada desta fase: quando `accepted_at` não existir, o snapshot e a reprodução histórica declaram essa ausência como limitação material ("a admissibilidade normativa deste material não foi verificada pelo Core"), em vez de presumir aceitação por proximidade com `recorded_at`, `known_at` ou `observed_at`. Isso reduz ambiguidade sem introduzir ainda a modelagem contextual completa de conhecimento que a ADR-0052 admite para Organization/finalidade/autorização.
>
> **Fechamento parcial adicional da ADR-0052 em 30/07/2026.** A mesma limitação temporal agora sobe também para a superfície operacional de auditoria já entregue: o `Dossier` passou a expor no bloco `evaluation` tanto o `knowledge_cutoff` efetivo quanto as `knowledge_limitations` do `FactSnapshot`, em vez de deixá-las apenas embutidas no snapshot bruto. Com isso, a ausência de `accepted_at` fica visível para operador, auditor e reprodutor do artefato sem exigir leitura estrutural de baixo nível. Evidência automática: `tests/application/test_dossier_service.py`, `tests/application/test_historical_reproduction_service.py` e `tests/core_domain/test_fact_domain.py` verdes em 30/07/2026, com `ruff check` focado nesses arquivos também verde.
>
> **Fechamento operacional adicional da ADR-0052 em 03/08/2026.** A limitação temporal deixou de ficar restrita ao `FactSnapshot`, à reprodução histórica e ao `Dossier`: as respostas operacionais da API que já devolvem `evaluation_id` (`POST /animals/{animal_id}/eligibility`, `POST /lots/{lot_id}/eligibility`, `POST /animals/{animal_id}/eligibility/market-matrix`, `POST /market-eligibility/evaluations`) agora também publicam `knowledge_cutoff` e `knowledge_limitations`. O mesmo vale para o `409 REVISAO_HUMANA_NECESSARIA`, que passa a devolver essas informações junto da proposta aberta. Isso não implementa a modelagem contextual completa de `known_at`/`accepted_at`, mas fecha a honestidade operacional do backend: o caller já consegue enxergar, no contrato de resposta mais usado, quando a avaliação depende de aproximação temporal ou quando a admissibilidade normativa não foi verificada pelo Core. Evidência automática em 03/08/2026: `ruff check` verde em `apps/api/livestock_queries.py`; `tests/api/test_core_public_surface.py` verde; asserções de integração adicionadas em `tests/integration/test_livestock_api_leitura.py`, pendentes apenas de reexecução com `TITAN_DATABASE_URL` configurada.
>
> **Frente seguinte aberta em 30/07/2026: roteiro executável do embargo IBAMA via HTTP real.** O atalho de banco usado em `apps/validacao/matriz_elegibilidade_mercados.py` não serve para fechar o risco residual do MVP, porque ele injeta a assertion direto no repositório e não exercita o caminho real `GET/POST /v1/livestock/properties/{property_id}/environmental-embargoes/ibama`. Para isso foi criado o roteiro dedicado `apps/validacao/embargo_ibama.py`, que: (1) cria a própria propriedade de validação; (2) registra uma geometria declarada; (3) consulta a avaliação espacial atual do provider; (4) congela a assertion via HTTP; (5) relê o histórico gravado; (6) prova que o auditor não pode gravar nova assertion. Validação automática do script em 30/07/2026: `ruff check apps/validacao/embargo_ibama.py` verde e compilação Python (`python -m uv run --locked python -m compileall apps/validacao/embargo_ibama.py`) verde. **Pendente para fechamento da frente:** executar o roteiro contra API + Keycloak + provider `Titan_geodata` realmente configurados e registrar o resultado manual.
>
> **Validação manual do embargo IBAMA via HTTP real concluída em 30/07/2026.** O roteiro `apps/validacao/embargo_ibama.py` foi executado contra API real, Keycloak real e `Titan_geodata` real configurado, com **todos os 6 passos aprovados**: criação da propriedade de validação, registro da geometria, leitura da avaliação espacial atual, gravação da assertion auditável via `POST /environmental-embargoes/ibama/assertions`, releitura do histórico e negação correta ao auditor sem permissão de escrita. Durante a rodada, o roteiro expôs um defeito real no adapter HTTP (`Content-Type` ausente no `POST` espacial do IBAMA), corrigido em `packages/livestock_infrastructure/geodata/car_client.py` e coberto por teste em `tests/livestock_infrastructure/test_car_client.py` antes da reexecução verde. **Resultado:** o risco residual “embargo ambiental do IBAMA sem roteiro manual via HTTP real” deixa de permanecer aberto como lacuna não exercitada.
>
> **Encerramento do ciclo em 30/07/2026.** Ficam registrados como fechados neste dia: (1) saneamento da borda de produção da ADR-0054 para abrir `DecisionProposal` real em casos de revisão humana obrigatória; (2) saneamento mínimo da ADR-0052, tornando `accepted_at` explícito no contrato de `Fact` e visível também no `Dossier`; (3) criação e execução verde do roteiro executável do embargo IBAMA via HTTP real, com correção do defeito encontrado no adapter geoespacial durante a validação manual.
>
> **Próximos passos recomendados ao retomar.** Ordem sugerida para o próximo ciclo: (1) consolidar este fechamento em commit próprio da frente pós-MVP já saneada; (2) decidir se a Trilha A continua pela ADR-0052 residual — agora num corte menor e explícito de regra temporal restante — ou se prioriza outra estabilização operacional; (3) somente depois voltar a discutir abertura da Trilha B (avaliação territorial ampliada, integração externa real de qualificação e frontend), sem misturar expansão de produto com saneamento do Core.











## Como manter este checklist

Ao finalizar cada passo:

1. marcar a implementação e as validações automáticas aplicáveis;
2. registrar data, arquivos e comandos usados como evidência;
3. manter a validação manual pendente até a manifestação do responsável;
4. após aprovação manual, marcar o passo como concluído e atualizar o próximo passo;
5. registrar reprovação ou ressalva sem apagar o resultado anterior.

Estados utilizados:

- `[ ]` não iniciado ou validação pendente;
- `[x]` concluído ou validação aprovada;
- `IMPLEMENTADO` pronto para validação manual;
- `EM ANDAMENTO` passo dividido em subtarefas, com pelo menos uma em execução ou validação;
- `CONCLUÍDO` implementação validada;
- `BLOQUEADO` impedimento registrado;
- `NÃO INICIADO` nenhum trabalho realizado.

## Visão geral

| Passo | Entrega | Estado | Validação manual |
|---|---|---|---|
| 0.1–0.4 | Definições de fronteira, linguagem, ADRs e comandos | CONCLUÍDO | Aprovada |
| 1.1–1.6 | Workspace, qualidade, FastAPI, Docker, PostgreSQL e CI | CONCLUÍDO | Aprovada |
| 2.1–2.4 | Primitivas técnicas do Core (ID, tempo, serialização, payload) | CONCLUÍDO | Aprovada |
| 3.1–3.7 | Identidade, autorização, RLS, OIDC e isolamento | CONCLUÍDO | Aprovada |
| 4.1–4.9D | Auditoria, Outbox, Inbox, Checkpoints, Idempotência e Workers | CONCLUÍDO | Aprovada |
| 5.1–5.8 | Evidence, criptografia, assinaturas e Provenance | CONCLUÍDO | Aprovada |
| 6.1–6.6 | Policy, Rule, Evaluation e Decision explicável | CONCLUÍDO | Aprovada |
| 7.1–7.10 | Relações, recall, dossiê, bundle, sync e prova do Core | CONCLUÍDO (incluindo 7.8 e 7.9) | Aprovada |
| 8.0–8.6 | Fundação Titan Livestock | CONCLUÍDO | Aprovada |
| 9.1–9.6 | Medicamentos, prescrição, tratamento, carência e elegibilidade farmacológica | CONCLUÍDO | Pendente consolidar validação manual |
| 10.1–10.6 | Demonstração vertical verificável, timeline, dossiê e API operacional | CONCLUÍDO | Pendente consolidar validação manual do 10.6 |
| 11–12 | API Livestock completa para validação técnica e fluxos operacionais | CONCLUÍDO | Pendente rodada manual final |
| 13 | Ciclo de vida do animal: saída, genealogia e reprodução | CONCLUÍDO | Pendente rodada manual final |
| NR-4 / ADR-0043 | Governança e linha do tempo imutável de regras | CONCLUÍDO | Aprovada em 26/07/2026 |
| NR-4 / ADR-0044 | Matriz de elegibilidade por mercado com regras governadas | CONCLUÍDO | Validado contra PostgreSQL real em 27/07/2026 (`90d3eba`); avaliação independente por mercado confirmada em produção, falta só cobertura E2E de `REAVALIACAO_NECESSARIA` |
| NR-4 sanitário | Campanhas sanitárias, exigibilidade mínima, prescrição e tratamento autorizado | CONCLUÍDO | Aprovada em 26/07/2026 |
| ADR-0042a | Contraparte externa local e saída com destino estruturado | CONCLUÍDO | Aprovada em 26/07/2026 |
| ADR-0042b | Artefato recebido e lacuna de cobertura | CONCLUÍDO | Aprovada em 26/07/2026 |
| ADR-0042c | Fato importado com autoria, origem, confiança e artefato fonte | CONCLUÍDO | Aprovada em 26/07/2026 |
| ADR-0042d | Fato importado alimentando elegibilidade farmacológica | CONCLUÍDO | Aprovada em 26/07/2026 |

## Fila atual do backend

Esta fila substitui a indicação antiga "validar Marco 12 e iniciar o frontend". O frontend deve começar somente depois de o backend principal abaixo estar validado ou conscientemente congelado para demonstração.

| Ordem | Criticidade | Incremento | Motivo | Estado atual | Critério de saída |
|---|---|---|---|---|---|
| 1 | Concluída | Leitura completa da matriz por regra governada | A resposta comercial precisa explicar destino, regra, versão, adoção, lacuna e ação corretiva | **CONCLUÍDO em 27/07/2026 (`90d3eba`)**, validado contra PostgreSQL real | Cada célula da matriz expõe adoption/version/reasons/gaps/requirements de forma suficiente para auditoria e UI, incluindo quando a causa vier de fato importado, sem reaproveitar carência entre mercados |
| 2 | Baixa (cobertura) | Avaliação realmente independente por mercado | A ADR-0041/0044 só se cumpre por inteiro quando cada finalidade puder divergir por regra, vigência e sujeito próprios | **Implementado e em produção** (reclassificado em 27/07/2026, sem alteração de código); falta apenas teste E2E de `REAVALIACAO_NECESSARIA` | Existe teste de integração exercitando `REAVALIACAO_NECESSARIA` via API real, não só unitário |
| 3 | Concluída | Roteiro de simulação comercial até frigorífico | Demonstração precisa mostrar a cadeia completa, da fazenda ao destino de mercado, sem colagem manual de IDs | **CONCLUÍDO em 27/07/2026 (`f504614`)**, validado contra PostgreSQL e Keycloak reais: 11/11 passos aprovados | Um roteiro cria fazendas, animais, histórico, tratamento/importação, lote/frigorífico e imprime China/EUA/UE com motivos comparáveis |
| 4 | Concluída (mecanismo) | Requisitos sanitários e medicamentos/vacinas como regras adotáveis | Hoje há campanha, prescrição e tratamento; falta transformar obrigações sanitárias em regra governada por mercado | **Mecanismo CONCLUÍDO em 27/07/2026 (`82ade66`)** — `sanitary_requirement_fact_type` + `SANITARY_RULE_CODE`; nenhum `MarketProfile` amarrado a campanha ainda (decisão normativa deliberadamente adiada) | Regras governadas conseguem exigir campanha, vacinação/tratamento, prescrição ou evidência sanitária |
| 5 | Média | Continuidade de proveniência e lacuna auditável (ADR-0042) | Elegibilidade para mercados e fornecedor indireto dependem de cadeia além da própria Organization | Contraparte externa, saída estruturada, artefato recebido, fato importado e uso na elegibilidade aprovados em 26/07/2026 | Próximo aprofundamento só quando a matriz precisar expor cobertura/lacuna com maior detalhe por mercado |
| 6 | Concluída | Hardening de API antes do frontend | Reduz retrabalho de UI em contratos instáveis | **CONCLUÍDO em 27/07/2026 (`77eba12`)** — contrato de erro já estava consistente (69/72 operações); paginação corrigida nos 2 endpoints com risco real de crescimento sem teto | Revisar OpenAPI, permissões, erros, paginação e respostas dos endpoints Livestock mais usados |
| 7 | Concluída | Documentar corte MVP do backend | Ajuda a decidir o que fica fora sem parecer esquecido | **CONCLUÍDO em 27/07/2026** — `docs/CORTE_MVP_BACKEND.md` | Lista explícita de incluído, excluído, riscos e próximos marcos |
| 8 | Baixa neste momento | Frontend técnico/produto | Interface depende de contratos e narrativa do backend | Aguardando backend congelado | Iniciar somente após os itens 1-3 ou decisão explícita de protótipo |

## Registro consolidado dos incrementos recentes

| Data | Incremento | Estado | Evidência principal |
|---|---|---|---|
| 24/07/2026 | API mínima do fluxo farmacológico e roteiro de validação | CONCLUÍDO | `89ebf7d feat(api): api minima do fluxo farmacologico e roteiro de validacao` |
| 26/07/2026 | Governança Core de regras, versionamento, publicação e adoção | CONCLUÍDO | ADR-0043; `apps/api/core_rule_governance.py`; `apps/validacao/governanca_regras.py`; roteiro aprovado em 26/07/2026 |
| 26/07/2026 | Contraparte externa local e saída com destino estruturado | CONCLUÍDO | ADR-0042; `apps/validacao/contraparte_externa.py`; roteiro de 5 passos aprovado em 26/07/2026 |
| 26/07/2026 | Artefato recebido e lacuna de cobertura | CONCLUÍDO | ADR-0042; `apps/validacao/artefato_transferencia.py`; roteiro aprovado em 26/07/2026 |
| 26/07/2026 | Fato importado preservando autoria e artefato fonte | CONCLUÍDO | ADR-0042; `apps/validacao/fato_importado.py`; roteiro aprovado em 26/07/2026 |
| 26/07/2026 | Fato importado alimentando elegibilidade farmacológica | CONCLUÍDO | `50f9b22 feat(livestock): usar fato importado na elegibilidade`; `757370e fix(livestock): montar dossie com fato importado`; roteiro aprovado em 26/07/2026 |
| 26/07/2026 | Matriz de elegibilidade por mercado de destino | CONCLUÍDO | ADR-0044; `packages/livestock_application/market_eligibility.py`; `apps/validacao/matriz_elegibilidade_mercados.py`; roteiro aprovado em 26/07/2026 |
| 26/07/2026 | Requisitos por perfil de mercado e diferenciação UE/China/EUA | IMPLEMENTADO | `880882e feat(livestock): suportar requisitos por perfil de mercado`; `09d3417 feat(livestock): diferenciar requisito de rastreabilidade na UE` |
| 27/07/2026 | Falha fechada quando o mercado não declara carência própria | CONCLUÍDO | `tests/integration/test_livestock_api_leitura.py::test_matriz_de_mercado_falha_fechado_sem_carencia_declarada_por_mercado`; `apps/api/livestock_queries.py`; `packages/livestock_application/market_eligibility.py` |
| 27/07/2026 | Substituição auditável de adoção governada | CONCLUÍDO | `packages/core_application/rule_governance_service.py`; `apps/api/core_rule_governance.py`; migration `20260727_0054_rule_adoptions_partial_unique_active.py` |
| 27/07/2026 | Finalidade de mercado canonizada por Value Object | CONCLUÍDO | `packages/livestock_application/market_eligibility.py`; `apps/validacao/matriz_elegibilidade_mercados.py`; `tests/livestock_application/test_market_eligibility.py` |
| 27/07/2026 | Simulação comercial ponta a ponta até o frigorífico | IMPLEMENTADO | `apps/validacao/simulacao_comercial.py`; `tests/unit/test_validacao_simulacao_comercial.py` |
| 26/07/2026 | Exigibilidade sanitária mínima | CONCLUÍDO | `5bc1cc7 feat(livestock): avaliar exigibilidade sanitaria minima`; `apps/validacao/exigibilidade_sanitaria_minima.py`; roteiro aprovado em 26/07/2026 |
| 26/07/2026 | Prescrição veterinária operável pela API | CONCLUÍDO | `57ad5c0 feat(livestock): expor prescricoes veterinarias`; `apps/validacao/prescricao_veterinaria.py`; roteiro aprovado em 26/07/2026 |
| 26/07/2026 | Prescrição validando medicamento, animal e lote no tratamento | CONCLUÍDO | `f9bf4b7 feat(livestock): validar prescricao no tratamento`; `f55b007 feat(livestock): autorizar tratamento por prescricao de lote` |

## Roteiros de validação manual aprovados

Rodados em 26/07/2026 com stack local, API e Keycloak ativos, após nova semeadura para atualizar permissões:

```powershell
python -m uv run --locked python -m apps.validacao.governanca_regras --pausar
python -m uv run --locked python -m apps.validacao.matriz_elegibilidade_mercados --pausar
python -m uv run --locked python -m apps.validacao.exigibilidade_sanitaria_minima --pausar
python -m uv run --locked python -m apps.validacao.prescricao_veterinaria --pausar
python -m uv run --locked python -m apps.validacao.fato_importado --pausar
```

O aceite desses roteiros fecha o backend já implementado para demonstração. Nova falha real em regra, permissão, isolamento ou contrato volta para a fila como incremento de alta criticidade.


## Registro dos passos executados

### Passo 0.1 — Confirmar fronteira do Titan Core

- [x] Entrega concluída.
- [x] Revisão documental realizada.
- [x] Validação manual aprovada.
- **Estado:** CONCLUÍDO.
- **Evidências:** `VISION.md`, `DOMAIN.md` e histórico de aprovação do plano.

### Passo 0.2 — Consolidar linguagem do domínio

- [x] Entrega concluída.
- [x] Revisão documental realizada.
- [x] Validação manual aprovada.
- **Estado:** CONCLUÍDO.
- **Evidências:** `DOMAIN.md` versão 1.19 e histórico de aprovação.

### Passo 0.3 — Resolver arquitetura e registrar ADRs

- [x] Entrega concluída.
- [x] ADRs 0001 a 0029 revisadas e aceitas.
- [x] Validação manual aprovada.
- **Estado:** CONCLUÍDO.
- **Evidências:** `ARCHITECTURE.md` versão 1.32 e `docs/adr/`.

### Passo 0.4 — Tornar comandos de desenvolvimento reproduzíveis

- [x] Entrega concluída.
- [x] Comandos e disponibilidade documentados.
- [x] Validação manual aprovada.
- **Estado:** CONCLUÍDO.
- **Evidências:** `DEVELOPMENT.md`.

### Passo 1.1 — Criar o workspace Python mínimo

- [x] `.python-version` criado com Python 3.12.10.
- [x] `pyproject.toml` criado sem dependências de runtime.
- [x] `uv.lock` criado.
- [x] `uv` fixado em 0.11.30.
- [x] Lockfile verificado com `python -m uv lock --check`.
- [x] Ambiente sincronizado com `python -m uv sync --locked`.
- [x] Python efetivo validado como 3.12.10.
- [x] TOML validado.
- [x] Ausência de `apps/`, `packages/`, `tests/` e `infra/` confirmada.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `.python-version`, `pyproject.toml`, `uv.lock`, `README.md`, `DEVELOPMENT.md` e `docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md`.
- **Risco residual:** futuras atualizações de Python ou `uv` devem ser deliberadas e acompanhadas de novo lockfile.

### Passo 1.2 — Configurar qualidade Python

- [x] pytest 9.1.1 adicionado como dependência de desenvolvimento para executar testes.
- [x] Ruff 0.15.22 adicionado como dependência de desenvolvimento para lint e formatação.
- [x] Mypy 2.3.0 adicionado como dependência de desenvolvimento para análise estática.
- [x] Versões diretas fixadas e dependências transitivas registradas em `uv.lock`.
- [x] Configurações mínimas registradas em `pyproject.toml`.
- [x] Teste de sanidade do manifesto criado.
- [x] Verificador arquitetural inicial criado para impedir dependência de packages em apps e do Core em verticais.
- [x] `python -m uv lock --check` executado com sucesso.
- [x] `python -m uv run --locked pytest` executado: 3 testes aprovados.
- [x] `python -m uv run --locked ruff check .` executado com sucesso.
- [x] `python -m uv run --locked ruff format --check .` executado com sucesso.
- [x] `python -m uv run --locked mypy` executado sem erros em 2 arquivos.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `pyproject.toml`, `uv.lock`, `tests/test_smoke.py`, `tests/architecture/test_dependency_boundaries.py` e `DEVELOPMENT.md`.
- **Risco residual:** os verificadores cobrem somente as fronteiras que já podem ser expressas; novos módulos exigirão ampliação incremental dos alvos e regras.

### Passo 1.3 — Criar aplicação FastAPI com health check

- [x] FastAPI 0.139.2 adicionada para composição HTTP.
- [x] Uvicorn 0.51.0 adicionado para execução ASGI local.
- [x] HTTPX2 2.7.0 adicionado somente ao grupo de desenvolvimento para testes HTTP.
- [x] Aplicação executável criada em `apps/api` sem regras de domínio.
- [x] `GET /health` criado fora de `/api/v1` como exceção técnica da ADR-0027.
- [x] Resposta saudável limitada a `{"status":"ok"}`.
- [x] Rota inexistente retorna RFC 9457 em `application/problem+json`.
- [x] OpenAPI identifica o health check com a tag `técnico`.
- [x] Testes relacionados aprovados.
- [x] Suíte completa aprovada: 6 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 6 arquivos.
- [x] Servidor iniciado pelo comando oficial e consultado com `curl.exe`.
- [x] Processo temporário encerrado após a validação.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `apps/api/main.py`, `tests/api/test_health.py`, `pyproject.toml`, `uv.lock` e `DEVELOPMENT.md`.
- **Risco residual:** o health check comprova apenas que o processo responde; dependências externas serão acrescentadas e verificadas somente nos passos de infraestrutura.

### Passo 1.4A — PostgreSQL com PostGIS local

- [x] Docker 29.6.1 e Docker Compose 5.3.0 verificados.
- [x] Imagem oficial `postgis/postgis:18-3.6` fixada também por digest.
- [x] PostgreSQL limitado a `127.0.0.1` por padrão.
- [x] Banco, usuário, senha e porta substituíveis por variáveis de ambiente.
- [x] Credenciais padrão identificadas como exclusivamente locais.
- [x] Volume nomeado persistente montado no caminho do PostgreSQL 18.
- [x] Health check com `pg_isready` configurado.
- [x] `docker compose config` validado.
- [x] Testes estruturais do Compose criados e aprovados.
- [x] Container iniciado e estado `healthy` confirmado.
- [x] PostgreSQL 18.4 confirmado no container.
- [x] PostGIS 3.6.4 confirmado no banco inicial.
- [x] Persistência comprovada após `docker compose down` e novo `up`.
- [x] Marcador técnico temporário removido.
- [x] Container e rede encerrados sem excluir o volume.
- [x] Suíte completa aprovada: 8 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 7 arquivos.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `compose.yaml`, `tests/infrastructure/test_compose_config.py`, `DEVELOPMENT.md` e volume local `titan_postgres_data`.
- **Risco residual:** credenciais padrão são adequadas somente ao desenvolvimento local; o health check comprova disponibilidade do banco, não migrations, RLS ou conexão da aplicação, que pertencem ao Passo 1.5.

### Passo 1.4B — MongoDB local para futuro GridFS

- [x] ADR-0004 relida e limites de responsabilidade confirmados.
- [x] Docker Official Image `mongo:8.0.26-noble` fixada também por digest.
- [x] Linha estável MongoDB 8.0 escolhida em vez das linhas rápidas.
- [x] MongoDB limitado a `127.0.0.1` por padrão.
- [x] Banco inicial, usuário root, senha e porta substituíveis por variáveis de ambiente.
- [x] Autenticação habilitada desde a inicialização.
- [x] Escrita sem credenciais rejeitada pelo MongoDB.
- [x] Volume nomeado persistente montado em `/data/db`.
- [x] Health check autenticado com `mongosh` configurado.
- [x] `docker compose config` validado.
- [x] Testes estruturais do Compose ampliados e aprovados.
- [x] Container iniciado e estado `healthy` confirmado.
- [x] MongoDB 8.0.26 confirmado no container.
- [x] Persistência comprovada após `docker compose down` e novo `up`.
- [x] Coleção e documento técnicos temporários removidos.
- [x] Container e rede encerrados sem excluir o volume.
- [x] PostgreSQL permaneceu parado durante a validação desta subtarefa.
- [x] Suíte completa aprovada: 10 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 7 arquivos.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `compose.yaml`, `tests/infrastructure/test_compose_config.py`, `DEVELOPMENT.md` e volume local `titan_mongo_data`.
- **Riscos residuais:** GridFS e driver ainda não foram implementados; credenciais padrão servem somente ao desenvolvimento; a licença SSPL do MongoDB exige avaliação antes de eventual oferta comercial hospedada.

### Passo 1.4C — Keycloak como OIDC Provider local

- [x] ADR-0028 criada, aceita e vinculada à arquitetura.
- [x] Keycloak 26.7.0 fixado por versão e digest.
- [x] PostgreSQL 18.4 exclusivo do provider fixado por versão e digest.
- [x] Estado do provider separado do banco autoritativo do Titan.
- [x] Banco do provider sem porta publicada no host.
- [x] Keycloak publicado apenas em `127.0.0.1` por padrão.
- [x] Configurações e credenciais locais substituíveis por variáveis de ambiente.
- [x] Readiness na porta de gerenciamento interna configurada.
- [x] Dependência do banco condicionada a `service_healthy`.
- [x] `docker compose config` validado.
- [x] Testes estruturais do Compose ampliados: 7 testes relacionados aprovados.
- [x] Container iniciado e estado `healthy` confirmado.
- [x] Keycloak 26.7.0 confirmado no container.
- [x] Discovery OIDC, issuer, authorization endpoint e JWKS confirmados.
- [x] Credencial de cliente inexistente rejeitada com HTTP 401.
- [x] Persistência do realm administrativo comprovada após `down`/`up`.
- [x] Container e rede encerrados sem excluir o volume.
- [x] Suíte completa aprovada: 13 testes.
- [x] Ruff lint aprovado e formatação aplicada ao teste alterado.
- [x] Mypy aprovado em 7 arquivos.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `compose.yaml`, `tests/infrastructure/test_compose_config.py`, `docs/adr/0028-keycloak-como-oidc-provider-inicial.md`, `DEVELOPMENT.md` e volume local `titan_keycloak_postgres_data`.
- **Riscos residuais:** `start-dev`, HTTP e credenciais padrão são exclusivamente locais; realm e clientes Titan, PKCE, MFA, TLS, hardening, alta disponibilidade, backup e integração com a API não foram implementados nesta subtarefa.

## Próximo passo

### Passo 1.4D — RabbitMQ como Message Broker local

- [x] ADR-0029 aceita e vinculada à arquitetura.
- [x] RabbitMQ 4.3.3 com management fixado por versão e digest.
- [x] AMQP e management limitados a `127.0.0.1` por padrão.
- [x] Usuário, senha, vhost e portas substituíveis por variáveis de ambiente.
- [x] Usuário e vhost locais dedicados, sem uso da conta `guest` pela aplicação.
- [x] Hostname estável e volume nomeado configurados.
- [x] Health check verifica processo ativo e ausência de alarmes locais.
- [x] `docker compose config` validado.
- [x] Testes estruturais do Compose ampliados: 9 testes relacionados aprovados.
- [x] RabbitMQ 4.3.3 e vhost `titan` confirmados.
- [x] Acesso autenticado à API de management retornou HTTP 200.
- [x] Credencial inválida foi rejeitada com HTTP 401.
- [x] Publicação persistente foi roteada para topologia técnica temporária.
- [x] Requeue produziu redelivery da mesma mensagem.
- [x] Queue durável permaneceu disponível após `down`/`up`.
- [x] Exchange e queue técnicas temporárias foram removidas.
- [x] Containers e rede encerrados sem excluir o volume.
- [x] Suíte completa aprovada: 15 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 7 arquivos.
- [x] Validação manual do responsável, incluindo interface de administração.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `compose.yaml`, `tests/infrastructure/test_compose_config.py`, `docs/adr/0029-rabbitmq-como-message-broker-inicial.md`, `DEVELOPMENT.md` e volume local `titan_rabbitmq_data`.
- **Riscos residuais:** o nó único local não oferece alta disponibilidade; TLS, quorum queues, topologia funcional, publisher, Outbox, dead-letter, workers e integração Python pertencem a passos posteriores.

O Passo 1.4D foi aprovado. A próxima subtarefa de infraestrutura local é Valkey. A decisão do executor de workers permanece separada.

### Passo 1.4E — Valkey para cache efêmero local

- [x] ADR-0025 relida e limites de responsabilidade confirmados.
- [x] Valkey 9.1.0 fixado por versão e digest da imagem mantida pelo projeto.
- [x] Serviço limitado a `127.0.0.1` por padrão.
- [x] Senha, porta e limite de dataset substituíveis por variáveis de ambiente.
- [x] Autenticação obrigatória desde a inicialização.
- [x] Acesso sem credencial rejeitado com `NOAUTH`.
- [x] Health check autenticado com `valkey-cli ping`.
- [x] Dataset limitado a 128 MB por padrão.
- [x] Política de eviction `allkeys-lfu` configurada.
- [x] RDB e AOF desativados explicitamente.
- [x] Nenhum volume associado ao serviço.
- [x] `docker compose config` validado.
- [x] Testes estruturais do Compose ampliados: 11 testes relacionados aprovados.
- [x] Valkey 9.1.0 e resposta `PONG` confirmados.
- [x] Configurações efetivas de memória, eviction e persistência verificadas.
- [x] Chave técnica temporária criada e consultada.
- [x] Perda total confirmada após remoção e recriação do container.
- [x] Container temporário removido ao final.
- [x] Suíte completa aprovada: 17 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 7 arquivos.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `compose.yaml`, `tests/infrastructure/test_compose_config.py`, `docs/adr/0025-valkey-para-cache-e-coordenacao-efemera.md` e `DEVELOPMENT.md`.
- **Riscos residuais:** não existem CacheProfile, integração Python, TLS, ACL nominal, Sentinel, Cluster ou réplica; o standalone local não representa topologia produtiva.

O Passo 1.4E e o Passo 1.4 completo foram aprovados. O próximo incremento é o Passo 1.5 — migrations e conexão PostgreSQL.

## Comandos para testar o Passo 1.4E

```text
docker compose config
docker compose up --detach --wait valkey
docker compose ps
docker compose exec --no-TTY valkey valkey-server --version
docker compose exec --no-TTY valkey sh -c 'VALKEYCLI_AUTH="$VALKEY_PASSWORD" valkey-cli ping'
docker compose exec --no-TTY valkey sh -c 'VALKEYCLI_AUTH="$VALKEY_PASSWORD" valkey-cli CONFIG GET maxmemory maxmemory-policy save appendonly'
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
docker compose rm --stop --force valkey
```

Resultado esperado: Valkey 9.1.0 saudável, `PONG` autenticado, `maxmemory` de 134217728 bytes, `allkeys-lfu`, `appendonly no`, `save` vazio e nenhuma chave preservada após recriar o container.

### Passo 1.5 — Configurar migrations e conexão PostgreSQL

- [x] SQLAlchemy 2.0.51 aprovado e fixado no manifesto e lockfile.
- [x] Alembic 1.18.5 aprovado e fixado no manifesto e lockfile.
- [x] Psycopg 3.3.4 com distribuição binária aprovado e fixado.
- [x] Adapter criado em `packages/core_infrastructure/persistence`.
- [x] URL obtida exclusivamente de `TITAN_DATABASE_URL`, sem fallback silencioso.
- [x] Backend restrito a PostgreSQL e driver restrito a Psycopg.
- [x] Credencial omitida da representação de `DatabaseSettings`.
- [x] Engine configurado com verificação de conexão antes do checkout.
- [x] Função técnica de conexão executa `SELECT 1`.
- [x] Alembic configurado sem URL ou secret no repositório.
- [x] Migration `20260721_0001` criada sem tabela de negócio.
- [x] Estrutura técnica classificada como global e sem dado de domínio.
- [x] Seis testes unitários relacionados aprovados.
- [x] Banco descartável `titan_migration_validation` criado para a validação.
- [x] Conexão real ao PostgreSQL confirmada.
- [x] `upgrade head` aplicado com revisão `20260721_0001`.
- [x] Somente a tabela técnica `alembic_version` foi criada.
- [x] `downgrade base` executado e estado de versão zerado.
- [x] Migration reaplicada até `head`.
- [x] Banco descartável removido após a validação.
- [x] Container PostgreSQL de teste removido sem excluir o volume principal.
- [x] Suíte completa aprovada: 23 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 14 arquivos.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `pyproject.toml`, `uv.lock`, `alembic.ini`, `packages/core_infrastructure/persistence/`, `tests/infrastructure/test_database.py` e `DEVELOPMENT.md`.
- **Riscos residuais:** não há Session, repositório, endpoint dependente do banco, papéis separados de migration/runtime ou tabela protegida; essas capacidades serão introduzidas somente com consumidor e módulo owner reais.

## Comandos para testar o Passo 1.5

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked alembic current
python -m uv run --locked alembic downgrade base
python -m uv run --locked alembic current
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
docker compose rm --stop --force postgres
```

Resultado esperado: `current` mostra `20260721_0001 (head)` após upgrade, fica vazio após downgrade e retorna ao head após reaplicação. O banco possui apenas `alembic_version` até a primeira migration de módulo.

### Passo 1.6 — Configurar CI mínimo

- [x] GitHub Actions aprovado como plataforma.
- [x] Workflow único criado em `.github/workflows/quality.yml`.
- [x] Execução configurada para `push` e `pull_request`.
- [x] Runner fixado em `ubuntu-24.04`.
- [x] Timeout do job limitado a 15 minutos.
- [x] Concorrência obsoleta da mesma referência cancelável.
- [x] Permissão global limitada a `contents: read`.
- [x] Checkout configurado sem persistir credencial.
- [x] `actions/checkout`, `actions/setup-python` e `astral-sh/setup-uv` fixados por SHA.
- [x] Python obtido de `.python-version`.
- [x] uv fixado em 0.11.30.
- [x] Cache limitado ao lockfile.
- [x] Lockfile verificado antes da sincronização.
- [x] Testes e verificações arquiteturais incluídos.
- [x] Ruff lint e formatação incluídos.
- [x] Mypy incluído.
- [x] Workflow sem deploy, publicação, banco externo ou secrets.
- [x] Dois testes estruturais do workflow aprovados.
- [x] Suíte completa aprovada: 25 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 15 arquivos.
- [x] Execução bem-sucedida observada no GitHub Actions.
- [x] Falha intencional controlada observada em branch de teste.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências locais:** `.github/workflows/quality.yml`, `tests/infrastructure/test_ci_workflow.py` e `DEVELOPMENT.md`.
- **Evidências remotas:** execução bem-sucedida `29865934822`; falha controlada `29866081574` na etapa de testes; branch temporária removida após a validação.
- **Riscos residuais:** o teste controlado comprovou o bloqueio no `pytest`, mas não exercitou falhas isoladas de Ruff ou Mypy.

## Como validar o Passo 1.6

1. publicar ou conectar o repositório a um remoto GitHub autorizado;
2. enviar uma branch de teste e abrir um pull request;
3. confirmar que o job `Testes e análise estática` termina verde;
4. em outra alteração temporária da branch, introduzir uma asserção deliberadamente incorreta;
5. confirmar que o job falha no pytest;
6. remover a falha, reenviar e confirmar retorno ao estado verde;
7. não incorporar a falha controlada à branch principal.

### Passo 2.1 — Identificadores tipados e referências

- [x] Pacote real `packages/shared_kernel` criado sem camadas vazias.
- [x] `TypedId` opaco, imutável e associado a tipo lógico canônico.
- [x] `OrganizationId` distinto dos demais identificadores.
- [x] UUID nulo, texto inválido e tipo lógico não canônico rejeitados.
- [x] `UniversalReference` imutável com ID tipado, Organization opcional e versão do contrato.
- [x] Organization sem tipo específico rejeitada em runtime.
- [x] Versão do contrato inválida rejeitada.
- [x] Nenhuma dependência de framework, persistência, app ou vertical adicionada.
- [x] 15 testes relacionados aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/shared_kernel/` e `tests/shared_kernel/test_identifiers_and_references.py`.
- **Riscos residuais:** tipos lógicos ainda não possuem catálogo central; ele deve surgir apenas quando consumidores reais exigirem vocabulário controlado adicional.

## Como validar o Passo 2.1

```text
.venv\Scripts\python.exe -m pytest -q tests/shared_kernel/test_identifiers_and_references.py
.venv\Scripts\python.exe -m pytest -q tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff check packages/shared_kernel tests/shared_kernel
.venv\Scripts\python.exe -m ruff format --check packages/shared_kernel tests/shared_kernel
.venv\Scripts\python.exe -m mypy packages/shared_kernel tests/shared_kernel
```

Resultado esperado: 15 testes aprovados, Ruff sem erros, quatro arquivos já formatados e Mypy sem problemas.

### Passo 2.2 — Relógio e datas

- [x] Contrato `Clock` injetável criado sem dependência externa.
- [x] `SystemClock` retorna instante consciente de timezone em UTC.
- [x] `FixedClock` permite congelamento determinístico em testes.
- [x] Instantes sem timezone ou fora de UTC são rejeitados.
- [x] `RecordTimestamps` distingue `occurred_at` de `recorded_at`.
- [x] Captura do registro utiliza somente o relógio injetado.
- [x] Objetos temporais são imutáveis.
- [x] Nenhuma prova temporal externa é inferida do relógio local.
- [x] 22 testes relacionados aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/shared_kernel/temporal.py` e `tests/shared_kernel/test_temporal.py`.
- **Riscos residuais:** precisão e fonte temporal avançadas pertencem aos perfis e aos passos de timestamp independente; este incremento garante somente representação UTC e injeção do relógio observado pelo Titan.

## Como validar o Passo 2.2

```text
.venv\Scripts\python.exe -m pytest -q tests/shared_kernel/test_temporal.py
.venv\Scripts\python.exe -m pytest -q tests/shared_kernel tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff check packages/shared_kernel tests/shared_kernel
.venv\Scripts\python.exe -m ruff format --check packages/shared_kernel tests/shared_kernel
.venv\Scripts\python.exe -m mypy packages/shared_kernel tests/shared_kernel
```

Resultado esperado: 7 testes temporais e 22 testes relacionados aprovados, Ruff sem erros, seis arquivos já formatados e Mypy sem problemas.

### Passo 2.3 — Serialização canônica

- [x] `CanonicalSerializer` versionado como `titan-json-v1`.
- [x] Envelope inclui explicitamente a versão da serialização.
- [x] Ordem de mapas não altera os bytes produzidos.
- [x] Ordem de listas permanece semanticamente significativa.
- [x] Texto e chaves são normalizados em Unicode NFC.
- [x] Colisão de chaves após normalização é rejeitada.
- [x] Inteiros, decimais, booleanos, nulos, textos e timestamps possuem representação tipada.
- [x] Decimais equivalentes produzem a mesma representação.
- [x] Timestamps exigem representação UTC explícita.
- [x] Floats, decimais não finitos, chaves não textuais, ciclos e tipos desconhecidos são rejeitados.
- [x] Hashes calculados sobre bytes equivalentes são idênticos.
- [x] Nenhuma cadeia de hashes ou assinatura foi antecipada.
- [x] 36 testes relacionados aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/shared_kernel/serialization.py` e `tests/shared_kernel/test_serialization.py`.
- **Riscos residuais:** `titan-json-v1` suporta somente o subconjunto tipado aprovado; novos tipos exigem evolução deliberada e não podem alterar o significado da versão existente.

## Como validar o Passo 2.3

```text
.venv\Scripts\python.exe -m pytest -q tests/shared_kernel/test_serialization.py
.venv\Scripts\python.exe -m pytest -q tests/shared_kernel tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff check packages/shared_kernel tests/shared_kernel
.venv\Scripts\python.exe -m ruff format --check packages/shared_kernel tests/shared_kernel
.venv\Scripts\python.exe -m mypy packages/shared_kernel tests/shared_kernel
```

Resultado esperado: 14 testes de serialização e 36 testes relacionados aprovados, Ruff sem erros, oito arquivos já formatados e Mypy sem problemas.

### Passo 2.4 — Contrato de evento de domínio

- [x] Pacote real `packages/core_domain` criado sem camadas vazias.
- [x] `DomainEvent` imutável com identidade tipada.
- [x] Organization obrigatória e coerente com a referência do agregado.
- [x] Versões do agregado, evento, contrato e payload validadas.
- [x] Ocorrência e registro preservados separadamente em UTC.
- [x] Actor e Source preservados como referências tipadas.
- [x] Correlação obrigatória e causação opcional tipadas.
- [x] Payload mínimo convertido obrigatoriamente em bytes canônicos versionados.
- [x] Payload original mutável não altera o snapshot capturado.
- [x] Chaves evidentes de secrets e credenciais são rejeitadas.
- [x] Construção de payload diretamente por bytes arbitrários é impedida.
- [x] Teste arquitetural impede framework, app, infraestrutura e vertical no Core Domain.
- [x] 14 testes do contrato e 51 testes relacionados aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_domain/events.py`, `tests/core_domain/test_domain_event.py` e `tests/architecture/test_dependency_boundaries.py`.
- **Riscos residuais:** minimização semântica e detecção de dados pessoais dependem dos schemas e Policies futuros; a lista defensiva de chaves proibidas não substitui classificação de dados.

## Como validar o Passo 2.4

```text
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_domain_event.py
.venv\Scripts\python.exe -m pytest -q tests/core_domain tests/shared_kernel tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff check packages/core_domain packages/shared_kernel tests/core_domain tests/shared_kernel tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff format --check packages/core_domain packages/shared_kernel tests/core_domain tests/shared_kernel tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m mypy packages/core_domain packages/shared_kernel tests/core_domain tests/shared_kernel tests/architecture/test_dependency_boundaries.py
```

Resultado esperado: 14 testes do contrato e 51 testes relacionados aprovados, Ruff sem erros, 12 arquivos já formatados e Mypy sem problemas.

### Passo 3.1 — Organization

- [x] Modelo `Organization` imutável criado no Core Domain.
- [x] Modelo contém somente identidade estável aprovada, sem atributos inventados.
- [x] Identificador diferente de `OrganizationId` é rejeitado.
- [x] Schema modular `core_identity` criado por migration.
- [x] Tabela `organizations` classificada como `PROTECTED` e atribuída ao módulo owner.
- [x] `organization_id` e `record_owner_organization_id` usam UUID e são obrigatórios.
- [x] Constraint garante que o registro inicial da Organization é auto-owned.
- [x] RLS e `FORCE ROW LEVEL SECURITY` habilitados.
- [x] Policies independentes de `SELECT` e `INSERT` negam contexto ausente ou divergente.
- [x] Acesso público ao schema e à tabela é revogado.
- [x] Contexto usa `set_config(..., true)` e exige transação ativa.
- [x] Repository cria e consulta Organization sem expor SQL ao Domain.
- [x] Migration aditiva `20260721_0002` possui downgrade validado.
- [x] Teste PostgreSQL com role temporária sem `BYPASSRLS` comprovou isolamento.
- [x] Upgrade, downgrade e reaplicação concluídos; banco terminou em `20260721_0002 (head)`.
- [x] `alembic check` confirmou metadata e schema sem operações pendentes.
- [x] Catálogo confirmou RLS, FORCE RLS, classificação, policies e zero linhas residuais.
- [x] 23 testes sem banco e um teste PostgreSQL relacionados aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_domain/organizations.py`, `packages/core_infrastructure/persistence/organizations.py`, migration `20260721_0002`, testes de domínio, contrato e integração.
- **Riscos residuais:** a role de runtime produtiva e seus grants serão provisionados por configuração operacional própria; o teste usa role transacional temporária. Organization ainda não possui Application use case nem API, que pertencem a passos posteriores.

## Como validar o Passo 3.1

```powershell
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_organization.py tests/infrastructure/test_organization_persistence_contract.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_organization_postgresql.py
.venv\Scripts\python.exe -m alembic downgrade 20260721_0001
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_domain packages/core_infrastructure/persistence tests/core_domain tests/infrastructure/test_organization_persistence_contract.py tests/integration/test_organization_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_domain packages/core_infrastructure/persistence tests/core_domain tests/infrastructure/test_organization_persistence_contract.py tests/integration/test_organization_postgresql.py
```

Resultado esperado: seis testes de domínio/contrato e um teste PostgreSQL aprovados; migration retorna a `20260721_0002 (head)` após downgrade/upgrade; Ruff e Mypy não apresentam problemas. O teste PostgreSQL reverte a role e as Organizations temporárias.

### Passo 3.2 — User

- [x] ADR 0030 registra a Organization operadora como owner do `User` global.
- [x] Modelo `User` imutável criado com identidade tipada e owner obrigatório.
- [x] Senha, token, segredo, credencial e Permission direta não integram o modelo nem a persistência.
- [x] Tabela `core_identity.users` classificada como `PROTECTED`.
- [x] Chave estrangeira exige uma Organization owner existente.
- [x] RLS e `FORCE ROW LEVEL SECURITY` habilitados com negação por padrão.
- [x] Repository cria e consulta User somente em transação ativa.
- [x] Duplicidade, owner inexistente e contexto divergente são rejeitados pelos testes.
- [x] Migration aditiva `20260721_0003` possui downgrade validado.
- [x] Banco terminou em `20260721_0003 (head)` e `alembic check` não encontrou divergências.
- [x] 11 testes sem banco e um teste PostgreSQL aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** ADR 0030, `packages/core_domain/users.py`, `packages/core_infrastructure/persistence/users.py`, migration `20260721_0003` e testes de domínio, contrato e integração.
- **Riscos residuais:** a seleção segura da Organization operadora será responsabilidade do futuro caso de uso e de configuração confiável; Membership, identidade OIDC e API permanecem fora deste incremento.

## Como validar o Passo 3.2

```powershell
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_user.py tests/infrastructure/test_user_persistence_contract.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_user_postgresql.py
.venv\Scripts\python.exe -m alembic downgrade 20260721_0002
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_domain/users.py packages/core_infrastructure/persistence/users.py tests/core_domain/test_user.py tests/infrastructure/test_user_persistence_contract.py tests/integration/test_user_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_domain/users.py packages/core_infrastructure/persistence/users.py tests/core_domain/test_user.py tests/infrastructure/test_user_persistence_contract.py tests/integration/test_user_postgresql.py
```

Resultado esperado: oito testes de domínio/contrato e um teste PostgreSQL aprovados; migration retorna a `20260721_0003 (head)` após downgrade/upgrade; Ruff e Mypy não apresentam problemas. O teste PostgreSQL reverte a role, a Organization e o User temporários.

### Passo 3.3 — Membership

- [x] Modelo `Membership` imutável criado como vínculo humano temporal.
- [x] Owner do registro é obrigatoriamente a própria Organization vinculada.
- [x] Status utiliza vocabulário controlado em português.
- [x] Intervalo temporal UTC é semiaberto e rejeita término anterior ou igual ao início.
- [x] Origem e Actor concedente são preservados por referências tipadas.
- [x] Roles e Permissions não foram antecipadas neste incremento.
- [x] Tabela `core_identity.memberships` classificada como `PROTECTED`.
- [x] Chaves estrangeiras exigem User e Organizations existentes.
- [x] Constraints protegem owner, intervalo e status.
- [x] RLS e `FORCE ROW LEVEL SECURITY` habilitados com negação por padrão.
- [x] Repository cria, consulta e lista vínculos válidos sob contexto transacional.
- [x] Mesmo User foi associado a duas Organizations sem permitir leitura cruzada.
- [x] Migration aditiva `20260721_0004` possui downgrade validado.
- [x] Banco terminou em `20260721_0004 (head)` e `alembic check` não encontrou divergências.
- [x] 12 testes sem banco e um teste PostgreSQL aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_domain/memberships.py`, `packages/core_infrastructure/persistence/memberships.py`, migration `20260721_0004` e testes de domínio, contrato e integração.
- **Riscos residuais:** transições de estado, substituição histórica e atribuição temporal de Roles exigem casos de uso próprios; a presença de Membership válido não constitui Authorization isoladamente.

## Como validar o Passo 3.3

```powershell
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_membership.py tests/infrastructure/test_membership_persistence_contract.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_membership_postgresql.py
.venv\Scripts\python.exe -m alembic downgrade 20260721_0003
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_domain/memberships.py packages/core_infrastructure/persistence/memberships.py tests/core_domain/test_membership.py tests/infrastructure/test_membership_persistence_contract.py tests/integration/test_membership_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_domain/memberships.py packages/core_infrastructure/persistence/memberships.py tests/core_domain/test_membership.py tests/infrastructure/test_membership_persistence_contract.py tests/integration/test_membership_postgresql.py
```

Resultado esperado: nove testes de domínio/contrato e um teste PostgreSQL aprovados; migration retorna a `20260721_0004 (head)` após downgrade/upgrade; Ruff e Mypy não apresentam problemas. O teste PostgreSQL reverte todos os registros e a role temporária.

### Passo 3.4 — Role e Permission

- [x] ADR 0031 registra ownership e atribuição de papéis.
- [x] Permission canônica pertence ao `REFERENCE_CATALOG` da Organization operadora.
- [x] Role imutável pertence à Organization que a define.
- [x] Role referencia somente Permissions canônicas existentes.
- [x] MembershipRoleAssignment vincula Membership e Role da mesma Organization.
- [x] MembershipRoleRevocation remove efeito de forma append-only.
- [x] Nenhum contrato ou tabela atribui Permission diretamente ao User.
- [x] Resolução temporal exclui atribuições futuras, expiradas ou revogadas.
- [x] Tabelas organizacionais são `PROTECTED` com RLS e `FORCE RLS`.
- [x] Atribuição entre Organizations é rejeitada por constraint estrutural.
- [x] Migration `20260721_0005` possui downgrade validado.
- [x] Banco terminou em `20260721_0005 (head)` e `alembic check` não encontrou divergências.
- [x] 11 testes sem banco e um teste PostgreSQL aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** ADR 0031, `packages/core_domain/authorization.py`, `packages/core_infrastructure/persistence/authorization.py`, migration `20260721_0005` e testes relacionados.
- **Riscos residuais:** o bootstrap dos códigos canônicos e perfis mínimos pertence ao Passo 3.7; autoridade dos Actors concedente e revogador será validada na Application; Role não substitui Authorization por operação.

## Como validar o Passo 3.4

```powershell
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_authorization.py tests/infrastructure/test_authorization_persistence_contract.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_authorization_postgresql.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_domain/authorization.py packages/core_infrastructure/persistence/authorization.py tests/core_domain/test_authorization.py tests/infrastructure/test_authorization_persistence_contract.py tests/integration/test_authorization_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_domain/authorization.py packages/core_infrastructure/persistence/authorization.py tests/core_domain/test_authorization.py tests/infrastructure/test_authorization_persistence_contract.py tests/integration/test_authorization_postgresql.py
```

Resultado esperado: oito testes de domínio/contrato e um teste PostgreSQL aprovados; banco em `20260721_0005 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados.

### Passo 3.5 — Autenticação com OIDC Provider

- [x] PyJWT com suporte criptográfico adicionado e fixado no lockfile.
- [x] Realm local `titan` importável sem User ou segredo real.
- [x] Resource Server `titan-api` separado do cliente público `titan-swagger`.
- [x] Swagger configurado com Authorization Code e PKCE S256.
- [x] Implicit Flow e Password Grant desabilitados no cliente Swagger.
- [x] Audience `titan-api` emitida somente no Access Token.
- [x] Claim de finalidade `token_use=access` ausente no ID Token.
- [x] Validador usa issuer e audience exatos e allowlist `RS256`.
- [x] Assinatura, expiração, issued-at, subject, tipo e finalidade são validados.
- [x] ID Token, token adulterado, expirado ou destinado a outro recurso são rejeitados.
- [x] Infrastructure produz `AuthenticatedPrincipal` sem token bruto.
- [x] Rota `/technical/authentication` exige Bearer Access Token.
- [x] Token ausente retorna `401` com `WWW-Authenticate: Bearer`.
- [x] Discovery e JWKS do Keycloak real foram consultados com sucesso.
- [x] Credencial inválida foi rejeitada pelo token endpoint com `401`.
- [x] 25 testes relacionados aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** ADRs 0005 e 0028, `config/keycloak/titan-realm.json`, `packages/core_infrastructure/authentication.py`, `apps/api/main.py` e testes de autenticação/configuração.
- **Riscos residuais:** `start-dev` e HTTP são exclusivamente locais; User de teste deve ser criado manualmente no Keycloak e nunca versionado; vínculo persistente de ExternalIdentity e Authorization por Organization pertencem aos próximos incrementos; indisponibilidade, rotação e cache JWKS exigem testes operacionais adicionais antes de produção.

## Como validar o Passo 3.5

```powershell
docker compose up --detach --wait keycloak
curl.exe http://127.0.0.1:8080/realms/titan/.well-known/openid-configuration
curl.exe http://127.0.0.1:8080/realms/titan/protocol/openid-connect/certs
$env:TITAN_OIDC_ISSUER = "http://localhost:8080/realms/titan"
$env:TITAN_OIDC_AUDIENCE = "titan-api"
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_authentication.py tests/infrastructure/test_oidc_access_token.py tests/api/test_oidc_authentication.py tests/api/test_health.py tests/infrastructure/test_compose_config.py
.venv\Scripts\python.exe -m ruff check apps/api/main.py packages/core_domain/authentication.py packages/core_infrastructure/authentication.py tests/core_domain/test_authentication.py tests/infrastructure/test_oidc_access_token.py tests/api/test_oidc_authentication.py tests/infrastructure/test_compose_config.py
.venv\Scripts\python.exe -m mypy apps/api/main.py packages/core_domain/authentication.py packages/core_infrastructure/authentication.py tests/core_domain/test_authentication.py tests/infrastructure/test_oidc_access_token.py tests/api/test_oidc_authentication.py tests/infrastructure/test_compose_config.py
```

Resultado esperado: Keycloak saudável; discovery do issuer `http://localhost:8080/realms/titan`; JWKS com chaves; 26 testes relacionados aprovados; Ruff e Mypy sem problemas.

### Passo 3.6 — Isolamento por Organization

- [x] `ExternalIdentity` canônica usa `(issuer, subject)` e referencia User interno.
- [x] Email, nome, username, token e senha não integram o vínculo externo.
- [x] `OrganizationContext` é imutável e não contém token bruto.
- [x] Organization solicitada é tratada como entrada não confiável.
- [x] Application resolve identidade externa antes de consultar Membership.
- [x] Exatamente uma Membership válida é exigida para o contexto humano.
- [x] Roles e Permissions efetivas são calculadas após validar Membership.
- [x] Subject desconhecido e Organization sem vínculo falham com negação indistinguível.
- [x] Adapter PostgreSQL define internamente o contexto RLS da operadora e da Organization solicitada.
- [x] Tabela `external_identities` é `PROTECTED`, com RLS e `FORCE RLS`.
- [x] `(issuer, subject)` possui unicidade estrutural.
- [x] Migration `20260721_0006` possui downgrade validado.
- [x] Banco terminou em `20260721_0006 (head)` e `alembic check` não encontrou divergências.
- [x] Teste PostgreSQL comprovou acesso permitido e negação em outra Organization.
- [x] Teste arquitetural protege Application contra dependência de Infrastructure e apps.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_domain/organization_context.py`, `packages/core_application/organization_context.py`, `packages/core_infrastructure/organization_context.py`, migration `20260721_0006` e testes relacionados.
- **Riscos residuais:** suspensão/relink de ExternalIdentity exige caso de uso append-only próprio; ServiceIdentity e AuthorizationGrant ainda não integram este fluxo; finalidade e recurso serão adicionados quando existir caso de uso protegido concreto.

## Como validar o Passo 3.6

```powershell
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_organization_context.py tests/application/test_organization_context_service.py tests/infrastructure/test_organization_context_persistence_contract.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_organization_context_postgresql.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_domain/organization_context.py packages/core_application packages/core_infrastructure/organization_context.py packages/core_infrastructure/persistence/external_identities.py
.venv\Scripts\python.exe -m mypy packages/core_domain/organization_context.py packages/core_application packages/core_infrastructure/organization_context.py packages/core_infrastructure/persistence/external_identities.py
```

Resultado esperado: dez testes sem banco e um teste PostgreSQL aprovados; banco em `20260721_0006 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados.

### Passo 3.7 — Perfis mínimos de bootstrap

- [x] ADR-0032 limita o bootstrap à Organization operadora.
- [x] Identifiers da Organization e da autoridade são configuração explícita.
- [x] Ambiente usa vocabulário controlado em português.
- [x] Perfil e versão são estáveis e registrados.
- [x] Recibo imutável registra origem, autoridade, ambiente, instante e resultado.
- [x] Execução repetida retorna `JA_APLICADO` sem duplicar registros.
- [x] Bootstrap não cria User, ExternalIdentity, Membership, Role ou Permission.
- [x] Configuração divergente falha fechada.
- [x] Tabela `bootstrap_receipts` é `PROTECTED`, com RLS e `FORCE RLS`.
- [x] Migration `20260721_0007` possui downgrade validado.
- [x] Banco terminou em `20260721_0007 (head)` e `alembic check` não encontrou divergências.
- [x] Testes relacionados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** ADR-0032, `apps/bootstrap`, `packages/core_infrastructure/bootstrap.py`, migration `20260721_0007` e testes relacionados.
- **Riscos residuais:** o comando exige credencial administrativa; provisionamento de User, Membership, Role, Permission e demais perfis permanece negado até casos de uso próprios; o recibo comprova a aplicação registrada, não a guarda operacional da credencial usada.

## Como validar o Passo 3.7

Use Identifiers fictícios e estáveis exclusivos do seu ambiente local:

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
$env:TITAN_OPERATOR_ORGANIZATION_ID = "20000000-0000-4000-8000-000000000001"
$env:TITAN_BOOTSTRAP_AUTHORITY_ACTOR_ID = "20000000-0000-4000-8000-000000000002"
$env:TITAN_ENVIRONMENT = "DESENVOLVIMENTO"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m apps.bootstrap
.venv\Scripts\python.exe -m apps.bootstrap
.venv\Scripts\python.exe -m pytest -q tests/infrastructure/test_bootstrap.py tests/integration/test_bootstrap_postgresql.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check apps/bootstrap packages/core_infrastructure/bootstrap.py tests/infrastructure/test_bootstrap.py tests/integration/test_bootstrap_postgresql.py
.venv\Scripts\python.exe -m mypy apps/bootstrap packages/core_infrastructure/bootstrap.py tests/infrastructure/test_bootstrap.py tests/integration/test_bootstrap_postgresql.py
```

Resultado esperado: a primeira execução do comando retorna `APLICADO`; a segunda retorna `JA_APLICADO`; seis testes passam; o banco está em `20260721_0007 (head)`; Alembic, Ruff e Mypy não apresentam problemas. Se esse ambiente já tiver sido inicializado com os mesmos valores, ambas as execuções podem retornar `JA_APLICADO`.

### Passo 4.1 — Registro append-only

- [x] Application expõe somente registro append e consulta de versões.
- [x] `DomainEvent` preserva Organization, agregado, autoria, Source, correlação e payload canônico.
- [x] PostgreSQL mantém sequência contínua por agregado.
- [x] Lacuna ou versão repetida produz `VERSAO_DE_AGREGADO_CONFLITANTE`.
- [x] Consulta retorna eventos em ordem de versão do agregado.
- [x] Tabela `core_audit.domain_events` é `PROTECTED`, com RLS e `FORCE RLS`.
- [x] Papel de runtime sem `BYPASSRLS` não atravessa Organizations.
- [x] Papel de runtime possui somente `SELECT` e `INSERT` no teste controlado.
- [x] `UPDATE`, `DELETE` e `TRUNCATE` são recusados pelo PostgreSQL.
- [x] Hash anterior/atual não foi antecipado e permanece no Passo 4.2.
- [x] Migration `20260721_0008` possui downgrade validado.
- [x] Banco terminou em `20260721_0008 (head)` e `alembic check` não encontrou divergências.
- [x] 23 testes relacionados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_application/event_log.py`, `packages/core_infrastructure/persistence/events.py`, migration `20260721_0008` e testes relacionados.
- **Riscos residuais:** cadeia criptográfica pertence ao Passo 4.2; correção, idempotência e concorrência simultânea pertencem respectivamente aos Passos 4.5, 4.6 e 4.7; privilégios definitivos do papel de produção ainda dependem do provisionamento operacional desse papel.

## Como validar o Passo 4.1

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_domain_event.py tests/application/test_event_log_service.py tests/infrastructure/test_event_persistence_contract.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_domain_events_postgresql.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application packages/core_infrastructure/persistence/events.py tests/application/test_event_log_service.py tests/infrastructure/test_event_persistence_contract.py tests/integration/test_domain_events_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application packages/core_infrastructure/persistence/events.py tests/application/test_event_log_service.py tests/infrastructure/test_event_persistence_contract.py tests/integration/test_domain_events_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_application packages/core_infrastructure/persistence/events.py tests/application/test_event_log_service.py tests/infrastructure/test_event_persistence_contract.py tests/integration/test_domain_events_postgresql.py
```

Resultado esperado: 21 testes sem banco e dois testes PostgreSQL aprovados; banco em `20260721_0008 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados. O segundo teste PostgreSQL tenta e confirma a recusa de `UPDATE`, `DELETE` e `TRUNCATE` sob papel de runtime restrito.

### Passo 4.2 — Cadeia de hashes

- [x] Cadeia possui escopo por agregado e não atravessa Organizations.
- [x] Perfil `titan-event-chain` e versão `1` são explícitos.
- [x] Algoritmo `SHA-256` e serialização `titan-json-v1` são explícitos.
- [x] Hash cobre bytes canônicos completos do evento e hash anterior.
- [x] Primeiro elo exige hash anterior ausente; elos posteriores exigem 32 bytes.
- [x] Evento e elo de integridade são persistidos na mesma transação.
- [x] Elo anterior ausente produz `ELO_ANTERIOR_INDISPONIVEL`, nunca validade presumida.
- [x] Verificador funciona sem banco, segredo ou provider externo.
- [x] Verificador distingue `VALIDA`, `INVALIDA` e `INDETERMINADA`.
- [x] Adulteração identifica exatamente a posição divergente.
- [x] Perfil não suportado produz `PERFIL_NAO_SUPORTADO`.
- [x] Tabela `core_audit.domain_event_integrity` é `PROTECTED`, com RLS e `FORCE RLS`.
- [x] Papel de runtime não pode alterar, apagar ou truncar elos.
- [x] Migration `20260721_0009` possui downgrade validado.
- [x] Banco terminou em `20260721_0009 (head)` e `alembic check` não encontrou divergências.
- [x] 27 testes relacionados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_integrity/event_chain.py`, `packages/core_infrastructure/persistence/events.py`, migration `20260721_0009` e testes relacionados.
- **Riscos residuais:** a cadeia interna detecta divergências, mas ainda não possui checkpoint ou âncora externa; um administrador capaz de reescrever toda a cadeia só será confrontado por prova preservada fora dela nos Passos 4.3 e 4.4; eventos anteriores sem elo permanecem material insuficiente.

## Como validar o Passo 4.2

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_integrity/test_event_chain.py tests/core_domain/test_domain_event.py tests/infrastructure/test_event_persistence_contract.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_domain_events_postgresql.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_integrity packages/core_infrastructure/persistence/events.py tests/core_integrity/test_event_chain.py tests/infrastructure/test_event_persistence_contract.py tests/integration/test_domain_events_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_integrity packages/core_infrastructure/persistence/events.py tests/core_integrity/test_event_chain.py tests/infrastructure/test_event_persistence_contract.py tests/integration/test_domain_events_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_integrity packages/core_infrastructure/persistence/events.py tests/core_integrity/test_event_chain.py tests/infrastructure/test_event_persistence_contract.py tests/integration/test_domain_events_postgresql.py
```

Resultado esperado: 25 testes sem banco e dois testes PostgreSQL aprovados; banco em `20260721_0009 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados. Os testes independentes confirmam determinismo, adulteração na posição exata e perfil não suportado como indeterminado.

### Passo 4.3 — Checkpoint verificável

- [x] Checkpoint ancora a cabeça completa de uma cadeia desde a sequência 1.
- [x] RecordOwnerOrganization e agregado do escopo são explícitos.
- [x] IDs, sequências e hashes dos eventos cobertos são preservados em ordem.
- [x] Primeira e última sequência, contagem, hash inicial e final são protegidos.
- [x] Perfil `titan-integrity-checkpoint` versão `1` é explícito.
- [x] Digest `SHA-256` cobre escopo, conjunto, algoritmos, versões, produtor e instante observado.
- [x] Application constrói e persiste o checkpoint uma única vez.
- [x] Verificador funciona sem banco, segredo ou estado mutável do Titan.
- [x] Verificador detecta omissão, alteração de digest, escopo divergente e perfil incompatível.
- [x] Prova inicial utiliza a cadeia completa; Merkle não foi antecipada.
- [x] Checkpoint não cria timestamp nem prova temporal externa.
- [x] Tabelas de checkpoint são `PROTECTED`, com RLS e `FORCE RLS`.
- [x] Papel de runtime não pode alterar, apagar ou truncar checkpoints.
- [x] Migration `20260721_0010` possui downgrade validado.
- [x] Banco terminou em `20260721_0010 (head)` e `alembic check` não encontrou divergências.
- [x] 16 testes relacionados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_integrity/checkpoint.py`, `packages/core_application/integrity_checkpoint.py`, `packages/core_infrastructure/persistence/checkpoints.py`, migration `20260721_0010` e testes relacionados.
- **Riscos residuais:** a prova de inclusão inicial exige fornecer a cadeia completa; Merkle depende de volume e decisão futura; o instante observado não é prova temporal independente; TSA e TemporalAnchor pertencem ao Passo 4.4.

## Como validar o Passo 4.3

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_integrity/test_checkpoint.py tests/core_integrity/test_event_chain.py tests/application/test_integrity_checkpoint_service.py tests/infrastructure/test_checkpoint_persistence_contract.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_checkpoints_postgresql.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_integrity packages/core_application packages/core_infrastructure/persistence/checkpoints.py tests/core_integrity/test_checkpoint.py tests/application/test_integrity_checkpoint_service.py tests/infrastructure/test_checkpoint_persistence_contract.py tests/integration/test_checkpoints_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_integrity packages/core_application packages/core_infrastructure/persistence/checkpoints.py tests/core_integrity/test_checkpoint.py tests/application/test_integrity_checkpoint_service.py tests/infrastructure/test_checkpoint_persistence_contract.py tests/integration/test_checkpoints_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_integrity packages/core_application packages/core_infrastructure/persistence/checkpoints.py tests/core_integrity/test_checkpoint.py tests/application/test_integrity_checkpoint_service.py tests/infrastructure/test_checkpoint_persistence_contract.py tests/integration/test_checkpoints_postgresql.py
```

Resultado esperado: 15 testes sem banco e um teste PostgreSQL aprovados; banco em `20260721_0010 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados. Os testes confirmam cobertura exata, omissão detectada, digest adulterado, escopo divergente e perfil incompatível como indeterminado.

### Passo 4.4 — TimestampProvider

- [x] Porta substituível definida na Application.
- [x] Tentativa, validação e âncora temporal são registros append-only distintos.
- [x] Indisponibilidade e resultado desconhecido permanecem explícitos e recuperáveis.
- [x] Provider falso é identificado como sintético e restrito ao desenvolvimento.
- [x] Assinatura, imprint, policy, nonce, autoridade, cadeia e validade são validados.
- [x] Token inválido, indeterminado ou de outro checkpoint nunca cria `TemporalAnchor`.
- [x] Tabelas são `PROTECTED`, com RLS e `FORCE RLS`.
- [x] Migration `20260721_0011` aplicada e `alembic check` sem divergências.
- [x] 11 testes relacionados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável: 11 testes, Alembic, Ruff e Mypy aprovados.
- **Estado:** CONCLUÍDO E APROVADO.
- **Riscos residuais:** o provider falso não implementa RFC 3161, não possui confiança pública e não produz efeito jurídico; TSA real e seu perfil exigem decisão posterior aprovada.

## Como validar o Passo 4.4

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_timestamping_service.py tests/infrastructure/test_timestamp_persistence_contract.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application/timestamping.py packages/core_infrastructure/fake_timestamp.py packages/core_infrastructure/persistence/timestamping.py tests/application/test_timestamping_service.py tests/infrastructure/test_timestamp_persistence_contract.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/timestamping.py packages/core_infrastructure/fake_timestamp.py packages/core_infrastructure/persistence/timestamping.py tests/application/test_timestamping_service.py tests/infrastructure/test_timestamp_persistence_contract.py
.venv\Scripts\python.exe -m mypy packages/core_application/timestamping.py packages/core_infrastructure/fake_timestamp.py packages/core_infrastructure/persistence/timestamping.py tests/application/test_timestamping_service.py tests/infrastructure/test_timestamp_persistence_contract.py
```

Resultado esperado: 11 testes aprovados; banco em `20260721_0011 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados.

### Passo 4.5 — Correção sem sobrescrita

- [x] `Correction` é um novo `DomainEvent` imutável no agregado original.
- [x] Evento corrigido é referenciado por `causation_id` e pelo payload canônico.
- [x] Justificativa, `ChangeKind`, versão original e novo conteúdo são preservados.
- [x] Correção exige versão posterior e nunca altera o payload original.
- [x] Application coordena construção e append sem conhecer PostgreSQL.
- [x] Event store preserva timeline ordenada e encadeamento de integridade.
- [x] PostgreSQL retorna original e correção como dois registros distintos.
- [x] Idempotência, projeção corrente e concorrência adicional não foram antecipadas.
- [x] 8 testes focados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável: todos os testes aprovados.
- **Estado:** CONCLUÍDO E APROVADO.
- **Riscos residuais:** a resolução da versão corrente, idempotência e concorrência pertencem aos passos seguintes; neste incremento, a timeline preserva e explica a correção sem escolher automaticamente seus efeitos downstream.

## Como validar o Passo 4.5

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_correction.py tests/application/test_correction_service.py tests/integration/test_correction_postgresql.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff check packages/core_domain/corrections.py packages/core_application/corrections.py packages/core_domain/__init__.py packages/core_application/__init__.py tests/core_domain/test_correction.py tests/application/test_correction_service.py tests/integration/test_correction_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_domain/corrections.py packages/core_application/corrections.py packages/core_domain/__init__.py packages/core_application/__init__.py tests/core_domain/test_correction.py tests/application/test_correction_service.py tests/integration/test_correction_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_domain/corrections.py packages/core_application/corrections.py tests/core_domain/test_correction.py tests/application/test_correction_service.py tests/integration/test_correction_postgresql.py
```

Resultado esperado: 8 testes aprovados; Ruff e Mypy aprovados. O teste PostgreSQL confirma a timeline `registro_criado → registro_corrigido`, a preservação do original e o encadeamento dos hashes.

### Passo 4.6 — Idempotência

- [x] Identidade semântica inclui principal, Organization, Purpose, operação e Digest da intenção.
- [x] Primeira execução adquire o registro e compromete efeito e resultado na mesma transação.
- [x] Retry equivalente recupera exatamente o resultado canônico sem repetir o handler.
- [x] Mesma chave com intenção diferente produz conflito estável em português.
- [x] Operação sem resultado recuperável permanece desconhecida e não é reexecutada automaticamente.
- [x] PostgreSQL é autoritativo; Valkey não participa da garantia.
- [x] Registro é `PROTECTED`, possui RLS e escopo único por identidade semântica.
- [x] Transição no banco permite somente `EM_PROCESSAMENTO → CONCLUIDA` sem mudar identidade.
- [x] Migration `20260722_0012` possui downgrade.
- [x] 9 testes sem banco, Ruff e Mypy aprovados.
- [x] Migration, integração PostgreSQL e `alembic check`: 10 testes aprovados; downgrade/upgrade validado; banco em `20260722_0012 (head)`.
- [x] Validação manual do responsável.
- **Estado:** CONCLUÍDO E APROVADO.
- **Riscos residuais:** retenção operacional ainda será definida por perfil futuro; resultado desconhecido exige reconciliação, não repetição automática; concorrência otimista de agregados pertence ao Passo 4.7.

## Como validar o Passo 4.6

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_idempotency_service.py tests/infrastructure/test_idempotency_persistence_contract.py tests/integration/test_idempotency_postgresql.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application/idempotency.py packages/core_infrastructure/persistence/idempotency.py packages/core_application/__init__.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py tests/application/test_idempotency_service.py tests/infrastructure/test_idempotency_persistence_contract.py tests/integration/test_idempotency_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/idempotency.py packages/core_infrastructure/persistence/idempotency.py packages/core_application/__init__.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py tests/application/test_idempotency_service.py tests/infrastructure/test_idempotency_persistence_contract.py tests/integration/test_idempotency_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_application/idempotency.py packages/core_infrastructure/persistence/idempotency.py tests/application/test_idempotency_service.py tests/infrastructure/test_idempotency_persistence_contract.py tests/integration/test_idempotency_postgresql.py
```

Resultado esperado: 10 testes aprovados; banco em `20260722_0012 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados. A repetição equivalente executa o efeito uma vez e a intenção divergente produz conflito.

### Passo 4.7 — Concorrência otimista

- [x] `aggregate_version` permanece a versão forte e sequencial do agregado.
- [x] Conflito possui contrato estável na Application e código público em português.
- [x] Infrastructure preserva compatibilidade com `EventAppendConflict`.
- [x] Lock transacional serializa concorrentes do mesmo agregado.
- [x] Constraint única impede versões duplicadas como defesa adicional.
- [x] Duas transações concorrentes partindo da mesma versão aceitam somente uma alteração.
- [x] Alteração obsoleta falha explicitamente sem last-write-wins.
- [x] Timeline final contém somente as versões `[1, 2]`, sem perda silenciosa.
- [x] Nenhuma migration ou API HTTP foi antecipada.
- [x] 8 testes relacionados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável.
- **Estado:** CONCLUÍDO E APROVADO.
- **Riscos residuais:** ETag e `If-Match` serão adicionados somente quando existir endpoint mutável correspondente; retry automático não resolve conflito de negócio e exige nova leitura e reavaliação.

## Como validar o Passo 4.7

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m pytest -q tests/application/test_optimistic_concurrency.py tests/integration/test_optimistic_concurrency_postgresql.py tests/integration/test_domain_events_postgresql.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff check packages/core_application/concurrency.py packages/core_application/__init__.py packages/core_infrastructure/persistence/events.py tests/application/test_optimistic_concurrency.py tests/integration/test_optimistic_concurrency_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/concurrency.py packages/core_application/__init__.py packages/core_infrastructure/persistence/events.py tests/application/test_optimistic_concurrency.py tests/integration/test_optimistic_concurrency_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_application/concurrency.py packages/core_infrastructure/persistence/events.py tests/application/test_optimistic_concurrency.py tests/integration/test_optimistic_concurrency_postgresql.py
```

Resultado esperado: 8 testes aprovados; Ruff e Mypy aprovados. O teste concorrente retorna exatamente uma `ACEITA` e um conflito, mantendo apenas uma versão 2.

### Passo 4.8A — Transactional Outbox

- [x] `OutboxMessage` é contrato técnico de Application e não substitui `DomainEvent`.
- [x] Semântica distingue Domain Event, Integration Event, Command e Job.
- [x] Envelope preserva contrato, versão, Organization, Actor, produtor, correlação e causação.
- [x] Payload é canônico, versionado e classificado; credenciais continuam proibidas.
- [x] Event e OutboxMessage são gravados na mesma transação PostgreSQL.
- [x] Falha na Outbox reverte o Event da mesma operação.
- [x] Mensagem nasce `PENDENTE` e permanece imutável neste incremento.
- [x] Tabela é `PROTECTED`, com RLS e sem políticas de update ou delete.
- [x] Migration `20260722_0013` possui downgrade validado.
- [x] 9 testes relacionados, Ruff, Mypy e `alembic check` aprovados.
- [x] Validação manual do responsável: todos os testes aprovados.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** publisher, claim/lease, confirmação RabbitMQ, resultado desconhecido, consumer/worker, Inbox e replay.
- **Riscos residuais:** mensagem pendente ainda não é publicada; estados operacionais de publicação serão registros separados para não alterar o envelope original.

## Como validar o Passo 4.8A

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/integration/test_outbox_postgresql.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application/outbox.py packages/core_application/__init__.py packages/core_infrastructure/persistence/outbox.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/integration/test_outbox_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/outbox.py packages/core_application/__init__.py packages/core_infrastructure/persistence/outbox.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/integration/test_outbox_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_application/outbox.py packages/core_infrastructure/persistence/outbox.py tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/integration/test_outbox_postgresql.py
```

Resultado esperado: 9 testes aprovados; banco em `20260722_0013 (head)`; Alembic, Ruff e Mypy aprovados. O teste de falha confirma que não permanece Event sem OutboxMessage.

### Passo 4.8B — Publisher da Outbox

- [x] Dependência `pika` adicionada ao manifesto e ao lockfile após aprovação.
- [x] Application define contrato broker-neutral para publisher.
- [x] Publisher registra aceite do broker separadamente de consumo.
- [x] Resultado desconhecido permanece recuperável e republicável com o mesmo `message_id`.
- [x] Estado operacional de publicação fica em tabelas separadas da `OutboxMessage` original.
- [x] Claim de publicação possui lease recuperável.
- [x] Adapter RabbitMQ fica restrito à Infrastructure.
- [x] Validação manual do responsável: aprovado.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** consumer/worker, Inbox, DLQ/quarentena funcional, replay operacional e topologia definitiva de filas de negócio.
- **Riscos residuais:** a confirmação positiva prova aceite pelo broker conforme configuração local, não recebimento ou processamento por consumidor; falhas de transporte podem deixar resultado desconhecido e exigir retry/reconciliação.

### Passo 4.8C — Consumer, Inbox no PostgreSQL e Worker Executável (`apps/worker`)

- [x] ADR-0038 criada, refinada com Opção A e aprovada.
- [x] Schema `core_messaging` criado via migration Alembic (`20260722_0015_create_core_messaging_inbox.py`).
- [x] RLS isolada por `Organization` configurada nas tabelas `inbox_messages`, `inbox_delivery_attempts` e `inbox_conflicts`.
- [x] Tabela `untrusted_message_quarantine` criada para quarentena pré-tenant minimizada sem RLS.
- [x] Core Application expandido com `IncomingMessageEnvelope`, digest semântico `titan-json-v1`, portas e enums.
- [x] `TransactionalInboxRepository` implementado no Core Infrastructure com transação única e RLS transacional.
- [x] Transação de controle separada para agendamento de retry em caso de aborto da transação de processamento.
- [x] Adapter `RabbitMQPikaConsumer` implementado com `prefetch_count=1`, ACK pós-commit e graceful shutdown.
- [x] Executável `apps/worker/main.py` implementado com suporte aos sinais `SIGINT`/`SIGTERM`.
- [x] Suíte de testes (197/197), Ruff, Mypy e Alembic check aprovados.
- [x] Validação manual do responsável: aprovado.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** topologia final de mensageria com múltiplas filas por vertical, UI/CLI de reconciliação e replay de Dead Letter Queue.
- **Riscos residuais:** instabilidade de rede no broker pode causar cancelamento temporário da subscrição de consumo, sendo tratada pelo ciclo de reconexão do worker.

### Passo 4.9A — Reconciliação operacional da Outbox

- [x] Estruturas `OutboxHealthSummary` (sem payload) e `OutboxReconciliationReport` criadas em `core_application`.
- [x] Porta `OutboxReconciliationRepositoryPort` e caso de uso `OutboxReconciliationService` implementados em `core_application`.
- [x] Repositório `TransactionalOutboxReconciliationRepository` implementado via SQLAlchemy Core em `core_infrastructure`.
- [x] Varredura `release_expired_claims()` atua exclusivamente em `outbox_publication_state` limpando claims expirados (`LEASE_EXPIRADA`) para re-elegibilidade por `claim_next()`.
- [x] Suíte de testes (200/200), Ruff, Mypy e Alembic check aprovados.
- [x] Validação manual do responsável: aprovado.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** Inbox, quarentena, replay de consumo e `apps/worker`.
- **Riscos residuais:** nenhuma nova tabela ou coluna foi criada; a liberação atua somente sobre a tabela de estado operacional mantendo a `OutboxMessage` original intacta.

### Passo 4.9B — Inbox e ConsumerReceipt

- [x] Contratos e exceções de consumo `TransientConsumptionError` e `PermanentConsumptionError` em `core_application`.
- [x] Deduplicação determinística com digest semântico `titan-json-v1` UTF-8 NFC.
- [x] Repositório `TransactionalInboxRepository` no PostgreSQL com suporte a `PROCESSED`, `DUPLICATE_RECOVERED` e `CONFLICT_DETECTED` (tabela `core_messaging.inbox_conflicts`).
- [x] Suíte de testes (202/202), Ruff, Mypy e Alembic check aprovados.
- [x] Validação manual do responsável: aprovado.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** Replay de consumo autorizado por operador e CLI do worker.
- **Riscos residuais:** mensagens com digest divergente geram registro forense em `inbox_conflicts` sem re-executar a aplicação.

### Passo 4.9C — Replay e quarentena

- [x] Estruturas `QuarantinedMessageRecord`, `ReplayRequest` e `ReplayResult` criadas em `core_application`.
- [x] Porta `InboxQuarantineRepositoryPort` e caso de uso `InboxQuarantineService` implementados em `core_application`.
- [x] Validação estrita de operador (`operator_actor_reference`) e obrigatoriedade de justificativa (`reason`).
- [x] Repositório `TransactionalInboxQuarantineRepository` no PostgreSQL com suporte a consulta paginada de quarentena e replay auditável via `inbox_delivery_attempts`.
- [x] Suíte de testes (205/205), Ruff, Mypy e Alembic check aprovados.
- [x] Validação automática e integridade: aprovado.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** Topologia multi-broker de mensagens e consumidores distribuídos fora do Titan Core.
- **Riscos residuais:** nenhuma nova tabela criada; o worker compõe serviços já testados e aprovados.

### Passo 4.9D — Worker Executável

- [x] Configuração centralizada `WorkerSettings` em `apps/worker/config.py`.
- [x] Ponto de entrada executável `apps/worker/main.py` com composição de RabbitMQ Consumer, TransactionalInboxRepository, OutboxReconciliationService e suporte a encerramento gracioso (`SIGINT`/`SIGTERM`).
- [x] Testes unitários de configuração (`tests/unit/test_worker_config.py`).
- [x] Suíte de testes (207/207), Ruff, Mypy e Alembic check aprovados.
- [x] Validação automática e integridade: aprovado.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** Métricas de observabilidade Prometheus/Grafana do worker.
- **Riscos residuais:** perda de conexão durante shutdown gracioso é tratada por rejeição/re-enfileiramento RabbitMQ sem perda de mensagens.



## Como validar o Passo 4.9B

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_inbox.py tests/application/test_inbox_deduplication.py tests/infrastructure/test_inbox_persistence_contract.py tests/integration/test_inbox_postgresql_flow.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application/inbox.py packages/core_infrastructure/persistence/inbox.py tests/application/test_inbox_deduplication.py tests/integration/test_inbox_postgresql_flow.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/inbox.py packages/core_infrastructure/persistence/inbox.py tests/application/test_inbox_deduplication.py tests/integration/test_inbox_postgresql_flow.py
.venv\Scripts\python.exe -m mypy packages/core_application/inbox.py packages/core_infrastructure/persistence/inbox.py tests/application/test_inbox_deduplication.py tests/integration/test_inbox_postgresql_flow.py
```

Resultado esperado: testes do incremento aprovados; banco em `20260722_0015 (head)`; Alembic, Ruff e Mypy aprovados sem erros.


## Como validar o Passo 4.9A

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_outbox_reconciliation.py tests/infrastructure/test_outbox_reconciliation_persistence_contract.py tests/integration/test_outbox_reconciliation_postgresql.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application/outbox.py packages/core_infrastructure/persistence/outbox.py tests/application/test_outbox_reconciliation.py tests/integration/test_outbox_reconciliation_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/outbox.py packages/core_infrastructure/persistence/outbox.py tests/application/test_outbox_reconciliation.py tests/integration/test_outbox_reconciliation_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_application/outbox.py packages/core_infrastructure/persistence/outbox.py tests/application/test_outbox_reconciliation.py tests/integration/test_outbox_reconciliation_postgresql.py
```

Resultado esperado: testes do incremento aprovados; banco em `20260722_0015 (head)`; Alembic, Ruff e Mypy aprovados sem erros.


## Como validar o Passo 4.8C

```powershell
docker compose up --detach --wait postgres rabbitmq
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_inbox.py tests/infrastructure/test_inbox_persistence_contract.py tests/infrastructure/test_rabbitmq_consumer.py tests/integration/test_inbox_postgresql.py tests/integration/test_worker_e2e.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy
```

Resultado esperado: 197 testes aprovados; banco em `20260722_0015 (head)`; Alembic, Ruff e Mypy aprovados sem erros.


## Como validar o Passo 4.8B

```powershell
docker compose up --detach --wait postgres rabbitmq
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/infrastructure/test_rabbitmq_publisher.py tests/integration/test_outbox_postgresql.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application/outbox.py packages/core_application/__init__.py packages/core_infrastructure/persistence/outbox.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py packages/core_infrastructure/rabbitmq.py tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/infrastructure/test_rabbitmq_publisher.py tests/integration/test_outbox_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/outbox.py packages/core_application/__init__.py packages/core_infrastructure/persistence/outbox.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py packages/core_infrastructure/rabbitmq.py tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/infrastructure/test_rabbitmq_publisher.py tests/integration/test_outbox_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_application/outbox.py packages/core_application/__init__.py packages/core_infrastructure/persistence/outbox.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py packages/core_infrastructure/rabbitmq.py tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/infrastructure/test_rabbitmq_publisher.py tests/integration/test_outbox_postgresql.py
```

Resultado esperado: testes aprovados; banco em `20260722_0014 (head)`; Alembic, Ruff e Mypy aprovados. O teste de integração confirma retry após `RESULTADO_DESCONHECIDO` com o mesmo `message_id`.

## Comandos para testar o Passo 1.4D

```text
docker compose config
docker compose up --detach --wait rabbitmq
docker compose ps
docker compose exec --no-TTY rabbitmq rabbitmq-diagnostics server_version
docker compose exec --no-TTY rabbitmq rabbitmqctl list_vhosts name
curl.exe --user titan:titan_rabbitmq_local_dev_password http://127.0.0.1:15672/api/overview
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
docker compose down
```

Resultado esperado: serviço `rabbitmq` saudável, versão 4.3.3, vhost `titan`, API autenticada e volume `titan_rabbitmq_data` preservado após `down`.

## Comandos para testar o Passo 1.4C

```text
docker compose config
docker compose up --detach keycloak
docker compose ps
docker compose exec --no-TTY keycloak /opt/keycloak/bin/kc.sh --version
curl.exe http://localhost:8080/realms/master/.well-known/openid-configuration
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
docker compose down
```

Resultado esperado: `keycloak` e `keycloak-postgres` saudáveis, Keycloak 26.7.0, discovery com issuer `http://localhost:8080/realms/master`, banco sem porta publicada e volume `titan_keycloak_postgres_data` preservado após `down`.

## Comandos para testar o Passo 1.4B

```text
docker compose config
docker compose up --detach mongo
docker compose ps
docker compose exec --no-TTY mongo mongosh --quiet --username titan_root --password titan_local_dev_password --authenticationDatabase admin --eval "db.version()"
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
docker compose down
```

Resultado esperado: serviço `healthy`, MongoDB 8.0.26, dez testes aprovados e volume `titan_mongo_data` preservado após `down`.

## Comandos para testar o Passo 1.4A

```text
docker compose config
docker compose up --detach postgres
docker compose ps
docker compose exec --no-TTY postgres psql --username titan --dbname titan --command "SHOW server_version;"
docker compose exec --no-TTY postgres psql --username titan --dbname titan --command "SELECT postgis_full_version();"
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
docker compose down
```

Resultado esperado: serviço `healthy`, PostgreSQL 18.4, PostGIS 3.6.4, oito testes aprovados e volume `titan_postgres_data` preservado após `down`.

## Comandos para testar o Passo 1.3

Terminal 1:

```text
python -m uv sync --locked
python -m uv run --locked uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```text
curl.exe --include http://127.0.0.1:8000/health
curl.exe --include http://127.0.0.1:8000/rota-inexistente
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
```

Resultado esperado: `/health` retorna `200` e `{"status":"ok"}`; a rota inexistente retorna `404`, `application/problem+json` e `ROTA_NAO_ENCONTRADA`. Os seis testes e as verificações estáticas devem passar. Encerre o servidor no Terminal 1 com `Ctrl+C`.

### Passo 5.1 — Evidência e Fonte de Origem (Evidence e Source)

- [x] Agregado `Evidence`, `Source` e `SourceType` implementados em `packages/core_domain/evidence.py`.
- [x] Função `compute_content_hash` (SHA-256) garantindo cálculo imutável e determinístico.
- [x] Porta `EvidenceRepositoryPort` e serviço `EvidenceService` criados em `packages/core_application/evidence_service.py`.
- [x] Tabela `core_audit.evidences` com RLS por `Organization` e `TransactionalEvidenceRepository` em `packages/core_infrastructure/persistence/evidence.py`.
- [x] Migration Alembic `20260722_0016_create_evidences_table.py` aplicada com sucesso.
- [x] Testes unitários (`test_evidence_domain.py`) e de integração PostgreSQL com RLS (`test_evidence_postgresql.py`) aprovados (212 testes no total).

## Comandos para testar o Passo 5.1

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 212 testes aprovados; banco em `20260722_0016 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.2 — Níveis de Confiança (ConfidenceLevel)

- [x] Value Object `ConfidenceLevel` e enumeração `ConfidenceTier` implementados em `packages/core_domain/evidence.py`.
- [x] Invariante de validação de `reason` não vazia e pertença a `ConfidenceTier` garantida no Domínio.
- [x] Agregado `Evidence` atualizado para conter `confidence_level: ConfidenceLevel`.
- [x] `EvidenceService` e `EvidenceRepositoryPort` atualizados em `packages/core_application/evidence_service.py`.
- [x] Tabela `core_audit.evidences` com colunas `confidence_tier` e `confidence_reason` e `TransactionalEvidenceRepository` atualizado em `packages/core_infrastructure/persistence/evidence.py`.
- [x] Migration Alembic `20260722_0017_add_confidence_level_to_evidences.py` aplicada com sucesso.
- [x] Testes unitários (`test_evidence_domain.py`) e de integração PostgreSQL com RLS (`test_evidence_postgresql.py`) atualizados e aprovados (213 testes no total).

## Comandos para testar o Passo 5.2

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 213 testes aprovados; banco em `20260722_0017 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.3 — Validade, Verificação e Revogação de Evidências

- [x] Value Objects `ValidityPeriod`, `VerificationRecord`, `VerificationOutcome` e `EvidenceRevocation` criados em `packages/core_domain/evidence.py`.
- [x] Agregado `Evidence` estendido para comportar validade temporal, lista imutável de verificações e registro de revogação.
- [x] Casos de uso `verify_evidence` e `revoke_evidence` implementados no `EvidenceService` e porta `EvidenceRepositoryPort` atualizada com `update` em `packages/core_application/evidence_service.py`.
- [x] Tabelas `core_audit.evidences` (com colunas de validade e revogação) e `core_audit.evidence_verifications` com RLS por `Organization` criadas e `TransactionalEvidenceRepository` atualizado em `packages/core_infrastructure/persistence/evidence.py`.
- [x] Migration Alembic `20260722_0018_add_validity_and_revocation_to_evidences.py` aplicada com sucesso.
- [x] Testes unitários (`test_evidence_domain.py`) e de integração PostgreSQL com RLS (`test_evidence_postgresql.py`) aprovados (215 testes no total).

## Comandos para testar o Passo 5.3

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 215 testes aprovados; banco em `20260722_0018 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.4 — Contratos Criptográficos (SigningProvider, KeyProvider e TrustValidator)

- [x] Tipos imutáveis `CryptographicProfile`, `SignatureStatus`, `KeyIdentifier`, `CryptographicSignature` e `ValidationResult` criados em `packages/core_domain/crypto.py`.
- [x] Exportações atualizadas em `packages/core_domain/__init__.py`.
- [x] Portas `KeyProviderPort`, `SigningProviderPort` e `TrustValidatorPort` definidas em `packages/core_application/crypto.py`.
- [x] Adapters in-memory para desenvolvimento e testes (`SoftwareKeyProvider`, `SoftwareSigningProvider`, `SoftwareTrustValidator`) implementados em `packages/core_infrastructure/crypto.py`.
- [x] Testes unitários (`test_crypto_domain.py`) e de infraestrutura criptográfica (`test_crypto_infrastructure.py`) aprovados (217 testes no total).

## Comandos para testar o Passo 5.4

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 217 testes aprovados; banco em `20260722_0018 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.5 — Gestão e Rotação de Chaves (KeyRegistry e Criptoperíodo)

- [x] Enumeração `KeyState` (`ACTIVE`, `ROTATED`, `REVOKED`) e entidade `KeyRecord` criados em `packages/core_domain/crypto.py`.
- [x] Exportações atualizadas em `packages/core_domain/__init__.py`.
- [x] Porta `KeyRegistryPort` e serviço `KeyManagementService` implementados em `packages/core_application/crypto.py`.
- [x] Tabela `core_audit.key_registry` com RLS por `Organization` e `TransactionalKeyRegistryRepository` implementados em `packages/core_infrastructure/persistence/crypto.py`.
- [x] Migration Alembic `20260722_0019_create_key_registry_table.py` criada e aplicada com sucesso.
- [x] Testes unitários (`test_crypto_domain.py`) e de integração PostgreSQL com RLS (`test_crypto_postgresql.py`) aprovados (217 testes no total).

## Comandos para testar o Passo 5.5

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 217 testes aprovados; banco em `20260722_0019 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.6 — Assinatura de Evidence

- [x] Atributo opcional `signature: CryptographicSignature | None = None` e método `sign_evidence()` criados em `packages/core_domain/evidence.py`.
- [x] Caso de uso `sign_evidence()` orquestrando busca de chave ativa e geração da assinatura implementado em `packages/core_application/evidence_service.py`.
- [x] Colunas de assinatura adicionadas à tabela `core_audit.evidences` com RLS por `Organization` e `TransactionalEvidenceRepository` atualizado em `packages/core_infrastructure/persistence/evidence.py`.
- [x] Migration Alembic `20260722_0020_add_signature_to_evidences.py` criada e aplicada com sucesso.
- [x] Testes unitários (`test_evidence_domain.py`) e de integração PostgreSQL com RLS (`test_evidence_postgresql.py`) aprovados (217 testes no total).

## Comandos para testar o Passo 5.6

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 217 testes aprovados; banco em `20260722_0020 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.7 — Documento e anexo

- [x] Entidade imutável `Attachment` criada em `packages/core_domain/evidence.py`.
- [x] Portas `BlobStoragePort` e `AttachmentRepositoryPort`, e serviço `DocumentService` criados em `packages/core_application/document_service.py`.
- [x] Adapter `SoftwareBlobStorage` criado em `packages/core_infrastructure/storage.py`.
- [x] Tabela `core_audit.attachments` com RLS por `Organization` e `TransactionalAttachmentRepository` criados em `packages/core_infrastructure/persistence/evidence.py`.
- [x] Migration Alembic `20260722_0021_create_attachments_table.py` criada e aplicada com sucesso.
- [x] Testes unitários (`test_evidence_domain.py`) e de integração PostgreSQL com RLS (`test_document_postgresql.py`) aprovados (220 testes no total).

## Comandos para testar o Passo 5.7

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 220 testes aprovados; banco em `20260722_0021 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.8 — Proveniência (Conclusão do Marco 5)

- [x] Entidades imutáveis `ProvenanceNode`, `ProvenanceEdge` e `ProvenanceTrace` criadas em `packages/core_domain/provenance.py`.
- [x] Portas e serviço `ProvenanceService` criados em `packages/core_application/provenance_service.py` com suporte a rastreio `trace_from_event()`, `trace_from_evidence()` e `trace_from_source()`.
- [x] Repositórios `DomainEventRepository` e `TransactionalEvidenceRepository` atualizados para suporte a consultas de linhagem por `source_id`.
- [x] Testes unitários (`test_provenance_domain.py`) e de integração PostgreSQL com RLS (`test_provenance_postgresql.py`) aprovados (222 testes no total).

## Comandos para testar o Passo 5.8

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 222 testes aprovados; banco em `20260722_0021 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 6.1 — Policy versionada

- [x] Entidade imutável `Policy` e enum `PolicyStatus` criados em `packages/core_domain/policy.py`.
- [x] Porta `PolicyRepositoryPort` e serviço `PolicyService` criados em `packages/core_application/policy_service.py` com ciclo de vida formal (`DRAFT`, `PUBLISHED`, `SUPERSEDED`, `REVOKED`) e busca por vigência ativa.
- [x] Tabela `core_audit.policies` com RLS por `Organization` e `TransactionalPolicyRepository` criados em `packages/core_infrastructure/persistence/policy.py`.
- [x] Migration Alembic `20260722_0022_create_policies_table.py` criada e aplicada com sucesso.
- [x] Testes unitários (`test_policy_domain.py`) e de integração PostgreSQL com RLS (`test_policy_postgresql.py`) aprovados (225 testes no total).

## Comandos para testar o Passo 6.1

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 225 testes aprovados; banco em `20260722_0022 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 6.2 — Rule versionada

- [x] Entidade imutável `Rule` e enum `SeverityLevel` criados em `packages/core_domain/rule.py`.
- [x] Porta `RuleRepositoryPort` e serviço `RuleService` criados em `packages/core_application/rule_service.py` com suporte a severidade, fonte normativa, evidências requeridas, justificativa e ação corretiva.
- [x] Tabela `core_audit.rules` com RLS por `Organization` e `TransactionalRuleRepository` criados em `packages/core_infrastructure/persistence/rule.py`.
- [x] Migration Alembic `20260722_0023_create_rules_table.py` criada e aplicada com sucesso.
- [x] Testes unitários (`test_rule_domain.py`) e de integração PostgreSQL com RLS (`test_rule_postgresql.py`) aprovados (228 testes no total).

## Comandos para testar o Passo 6.2

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 228 testes aprovados; banco em `20260722_0023 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 6.3 — Contrato de fatos da vertical

- [x] Abstrações imutáveis `Fact` e `FactSnapshot` criadas em `packages/core_domain/facts.py` com cálculo determinístico de hash SHA-256 e consulta por tipo.
- [x] Porta `FactProviderPort` e serviço `FactService` criados em `packages/core_application/fact_service.py` isolando o Core de dependências da vertical pecuária ou banco de dados.
- [x] Testes unitários (`test_fact_domain.py`) e de aplicação com provider simulado (`test_fact_service.py`) aprovados (230 testes no total).

## Comandos para testar o Passo 6.3

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 230 testes aprovados; banco em `20260722_0023 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 6.4 — Execução de uma regra pura

- [x] Abstrações imutáveis `RuleResult` e `RuleResultStatus` (`ATENDIDA`, `NAO_ATENDIDA`, `PENDENTE`, `NAO_APLICAVEL`, `INDETERMINADA`) criadas em `packages/core_domain/evaluation.py`, com justificativa obrigatória e `compute_rule_inputs_hash` (SHA-256 determinístico das entradas relevantes).
- [x] Motor puro `RuleEvaluationEngine` criado em `packages/core_application/evaluation_service.py`, decidindo aplicabilidade por vigência e satisfação pelas evidências exigidas e pelas condições declarativas, sem acessar dados da vertical.
- [x] Condição normativa declarativa `RuleCondition` e `ComparisonOperator` criadas em `packages/core_domain/rule.py`: a condição é dado (`fact_type`, `payload_key`, operador, valor esperado), nunca código, tornando `NAO_ATENDIDA` e `INDETERMINADA` alcançáveis sem acoplar o Core à vertical.
- [x] Coluna `conditions` (JSONB) adicionada a `core_audit.rules` pela migration `20260722_0024`, com round-trip verificado em `test_rule_postgresql.py`; o digest das condições entra no hash das entradas via `compute_conditions_digest`.
- [x] Lacuna nunca vira reprovação: fato ausente => `PENDENTE`; chave ausente ou tipo incomparável => `INDETERMINADA`; apenas violação definitiva => `NAO_ATENDIDA`, com precedência sobre lacunas.
- [x] Testes unitários (`test_evaluation_domain.py`, `test_rule_condition_domain.py`) e de aplicação com casos de sucesso, falha, pendência, indeterminação e não aplicável (`test_evaluation_service.py`) aprovados, confirmando reprodutibilidade de resultado e hash (264 testes no total).

## Comandos para testar o Passo 6.4

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 264 testes aprovados; banco em `20260722_0024 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 6.5 — Agregação em Evaluation

- [x] Agregado imutável `Evaluation` e `EvaluationOutcome` criados em `packages/core_domain/evaluation.py`, preservando Organization, Subject, finalidade, Policy e versão, regras e versões, snapshot completo, RuleResults, momento, versão do motor e executor.
- [x] `compute_evaluation_hash` e `aggregate_outcome` criados: o hash descreve o conteúdo avaliado e omite de propósito a identidade das instâncias de RuleResult, tornando a avaliação reproduzível e verificável por `is_reproducible()`.
- [x] `PolicyEvaluationService` criado em `packages/core_application/evaluation_service.py`, executando as regras em ordem estável para que o resultado não dependa da ordem de leitura do repositório.
- [x] Ausência de regra aplicável nunca é reportada como conformidade: sem nada verificado, o resultado é `INDETERMINADO`.
- [x] Apenas políticas publicadas ou substituídas são executáveis; rascunho e revogada são rejeitados.
- [x] Tabela `core_audit.evaluations` com RLS por `Organization` e gravação append-only criada em `packages/core_infrastructure/persistence/evaluation.py`, com migration `20260722_0025`.
- [x] Testes unitários (`test_evaluation_aggregate_domain.py`), de aplicação (`test_policy_evaluation_service.py`) e de integração PostgreSQL com RLS (`test_evaluation_postgresql.py`) aprovados, confirmando que alterar os fatos depois da avaliação não afeta a avaliação histórica (280 testes no total).

## Comandos para testar o Passo 6.5

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 280 testes aprovados; banco em `20260722_0025 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 6.6 — Decision explicável

- [x] `Decision`, `DecisionResult`, `DecisionReason` e `DecisionReasonCode` criados em `packages/core_domain/decision.py`, preservando política/versão, regras/resultados, sujeitos afetados, evidências, motivos e ações corretivas.
- [x] Invariante de explicabilidade garantida em dois níveis: o domínio recusa Decision sem razão e a tabela impõe `CHECK (jsonb_array_length(reasons) > 0)`, de modo que nem escrita direta em SQL produza conclusão muda.
- [x] Código da razão é contrato e mensagem humana é separada: `compute_decision_hash` inclui o código e ignora a mensagem, permitindo tradução sem inverter a conclusão.
- [x] `DecisionService` criado em `packages/core_application/decision_service.py`, derivando a conclusão da Evaluation sem reavaliar nada; descumprimento `BLOCKING`/`CRITICAL` reprova e descumprimento apenas informativo produz `APROVADA_COM_RESTRICOES`.
- [x] Evaluation adulterada (conteúdo que não confere com o hash registrado) é recusada e não fundamenta Decision alguma.
- [x] Evidências citadas na Decision são reunidas de `Fact.source_reference`, ligando a conclusão às evidências que sustentam os fatos.
- [x] `rule_code` adicionado ao `RuleResult` para que a razão identifique a regra de forma legível, sem alterar os hashes já definidos no Passo 6.4.
- [x] Tabela `core_audit.decisions` com RLS por `Organization` e gravação append-only criada em `packages/core_infrastructure/persistence/decision.py`, com migration `20260722_0026`.
- [x] Testes unitários (`test_decision_domain.py`), de aplicação (`test_decision_service.py`) e de integração PostgreSQL com RLS (`test_decision_postgresql.py`) aprovados, confirmando reconstrução da decisão a partir da Evaluation persistida (295 testes no total).

## Comandos para testar o Passo 6.6

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 295 testes aprovados; banco em `20260722_0026 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.1 — Relação universal e temporal

- [x] `UniversalRelation` imutável criada em `packages/core_domain/relations.py` com origem, destino, tipo, período, Organization, Event criador, evidências, confiança, quantidade opcional com unidade e metadados versionados.
- [x] `relation_type` é nome canônico livre validado por padrão, não enum: o Core não conhece os vínculos de nenhuma vertical e não precisa mudar quando uma vertical adiciona um vínculo novo.
- [x] Relação recusa origem ou destino pertencente a outra Organization, e `RelationService` bloqueia travessia entre Organizations com `CrossOrganizationTraversalDenied` antes de consultar o repositório.
- [x] Encerrar relação declara fim de vigência sem apagar o vínculo: consultas em instantes anteriores continuam respondendo, preservando a genealogia.
- [x] Quantidade usa `Decimal` (rejeita `float`), nunca negativa e sempre com unidade declarada.
- [x] Tabela `core_audit.relations` com RLS por `Organization`, índices por origem e destino e migration `20260722_0027` criadas em `packages/core_infrastructure/persistence/relations.py`.
- [x] Testes unitários (`test_relations_domain.py`), de aplicação (`test_relation_service.py`) e de integração PostgreSQL com RLS (`test_relations_postgresql.py`) aprovados, com grafo fictício genérico consultado em datas diferentes (309 testes no total).

## Comandos para testar o Passo 7.1

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 309 testes aprovados; banco em `20260722_0027 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.2 — Projeções reconstruíveis

- [x] `ReverseReference`, `ReferencingKind`, `ReferenceRole` e `compute_projection_digest` criados em `packages/core_domain/projections.py`.
- [x] `ProjectionRebuildService` criado em `packages/core_application/projection_service.py`, derivando a projeção de `domain_events` e `relations` sem regra de negócio própria.
- [x] Chave primária é o próprio conteúdo derivado, sem identificador sorteado: reconstruir produz linhas idênticas e a comparação entre reconstruções é exata.
- [x] Digest ignora o instante de reconstrução, que descreve a execução e não o conteúdo derivado.
- [x] Entradas ordenadas por chave total antes de gravar: o conteúdo não depende da ordem de leitura do banco.
- [x] `is_consistent_with_sources()` detecta projeção defasada sem gravar nada.
- [x] Tabela `core_audit.reference_projection` com RLS e migration `20260722_0028` criadas em `packages/core_infrastructure/persistence/projections.py`.
- [x] Testes unitários (`test_projections_domain.py`), de aplicação (`test_projection_service.py`) e de integração PostgreSQL (`test_projections_postgresql.py`) aprovados, confirmando que apagar somente a projeção e reconstruí-la devolve conteúdo idêntico com a fonte histórica intacta (323 testes no total).

## Comandos para testar o Passo 7.2

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 323 testes aprovados; banco em `20260722_0028 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.3 — NonConformity Core

- [x] `NonConformity` criada em `packages/core_domain/nonconformity.py` com origem, severidade, período afetado, responsável, prazo, ação corretiva, evidência de correção, reavaliação e histórico.
- [x] Ciclo de vida `DETECTADA → CLASSIFICADA → ATRIBUIDA → EM_CORRECAO → PRONTA_PARA_REAVALIACAO → ENCERRADA` com transições validadas; pular etapas é recusado e encerrada é terminal.
- [x] Reavaliação reprovada devolve o caso a `EM_CORRECAO` sem apagar a tentativa anterior.
- [x] Histórico só cresce, reforçado no banco por `CHECK (jsonb_array_length(transitions) > 0)` e por exigência de `closed_at` quando encerrada.
- [x] Submeter à reavaliação exige evidência de correção; encerrar exige a `Evaluation` reavaliadora e recusa avaliação não reproduzível.
- [x] `NonConformityService.open_from_evaluation` abre casos apenas para resultados que exigem tratamento, ignorando regra atendida e não aplicável.
- [x] Tabela `core_audit.nonconformities` com RLS, índices por sujeito e por estado, e migration `20260722_0029`.
- [x] Testes unitários (`test_nonconformity_domain.py`) e de integração PostgreSQL (`test_nonconformity_postgresql.py`) aprovados, percorrendo abrir, corrigir, reavaliar reprovando, corrigir de novo e encerrar (336 testes no total).

## Comandos para testar o Passo 7.3

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 336 testes aprovados; banco em `20260722_0029 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.4 — Recall Core

- [x] `RecallRequest`, `RecallResult`, `RecallPath`, `RecallStep` e `RecallGap` criados em `packages/core_domain/recall.py`, com direção retrospectiva, prospectiva e ambas.
- [x] `RecallService` criado em `packages/core_application/recall_service.py` com travessia em largura, ordem determinística e explicação de cada caminho.
- [x] Limites de profundidade, número de nós e detecção de ciclo geram `RecallGap` explícita; qualquer lacuna torna o resultado `INCONCLUSIVO`.
- [x] Janela temporal filtra as relações vigentes no instante consultado, mudando o grafo alcançável.
- [x] Filtro por tipo de relação restringe a travessia sem alterar o grafo.
- [x] Simulação não deixa rastro; incidente exige repositório e é gravado por inteiro para explicação posterior.
- [x] Decisões afetadas são localizadas a partir dos sujeitos alcançados, via `PostgresAffectedDecisionLookup`.
- [x] Subject inicial de outra Organization é recusado, e a travessia só enxerga o grafo da própria Organization.
- [x] Tabela `core_audit.recalls` com RLS, índice por sujeito e migration `20260722_0030`.
- [x] Testes de aplicação (`test_recall_service.py`) e de integração PostgreSQL (`test_recall_postgresql.py`) aprovados sobre grafo fictício genérico (349 testes no total).

## Comandos para testar o Passo 7.4

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 349 testes aprovados; banco em `20260722_0030 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.5 — Dossier Core

- [x] `Dossier` e `compute_dossier_hash` criados em `packages/core_domain/dossier.py`, com verificação offline pelo próprio documento.
- [x] Documento autocontido: sujeito, finalidade, política e versão, regras com condições declarativas, snapshot completo dos fatos, resultados por regra, decisão com razões e ações, evidências e não conformidades com histórico.
- [x] Hash calculado sobre a serialização canônica `titan-json-v1` já adotada pelo Core, permitindo recálculo por terceiros sem acesso ao Titan.
- [x] Evaluation ou Decision não reproduzíveis são recusadas; decisão de outra avaliação ou de outra política também.
- [x] Tabela `core_audit.dossiers` com RLS, índice por sujeito e migration `20260722_0031`.
- [x] Testes de aplicação (`test_dossier_service.py`) e de integração PostgreSQL (`test_dossier_postgresql.py`) aprovados, exportando o JSON, recalculando o hash fora do banco e refazendo o raciocínio da decisão apenas com o documento (358 testes no total).

## Comandos para testar o Passo 7.5

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 358 testes aprovados; banco em `20260722_0031 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.6 — VerificationBundle

- [x] `BundleManifest`, `BundleComponent`, `SignatureMaterial`, `VerificationBundle`, `BundleVerifier`, `ValidationReport` e `DimensionResult` criados em `packages/core_domain/verification.py`.
- [x] `VerificationBundleService` criado em `packages/core_application/verification_service.py`, com `export()` e `load()` para o pacote viajar como texto e ser reconstruído fora do Titan.
- [x] Verificador puro: sem rede, sem segredo e sem banco; sete dimensões independentes em vez de um booleano único.
- [x] Ausência de material produz `INDETERMINADA`; adulteração produz `INVALIDA` com o ponto exato nomeado em `failure_point`.
- [x] Componente presente mas não declarado reprova o pacote, impedindo mistura silenciosa.
- [x] Âncora de confiança incluída no pacote não é aceita por estar nele; sem âncora externa a assinatura é indeterminada.
- [x] Chave privada, segredo, token, credencial e contexto de organização são recusados na montagem.
- [x] Dossiê que não confere com o próprio hash não pode ser empacotado.
- [x] Testes (`test_verification_bundle.py`) aprovados, cobrindo transporte fora do Titan, adulteração de componente e de manifesto, componente intruso, ausência de âncora e lacuna declarada (370 testes no total).

## Comandos para testar o Passo 7.6

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 370 testes aprovados; banco em `20260722_0031 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.7 — API de verificação externa

- [x] ADR-0039 escrita, revisada e **aceita antes do código**, cumprindo o portão da ADR-0010 que exigia contrato antes da implementação.
- [x] Domínio estendido: `NAO_APLICAVEL` e `NAO_EXECUTADA` acrescentados a `VerificationStatus`; dimensão declarativa `REVOGACAO_ATUAL` sempre não executada; `NORMATIVE_DIMENSION_ORDER` e `MANDATORY_DIMENSIONS` criados.
- [x] Regra do agregado corrigida: dimensão obrigatória `INDETERMINADA`, `NAO_EXECUTADA` ou `NAO_APLICAVEL` sem permissão nunca produz agregado válido.
- [x] Algoritmo fora da allowlist produz `ASSINATURA = INDETERMINADA`, não erro de contrato e não `NAO_EXECUTADA`.
- [x] `failures` lista somente dimensões `INVALIDA`; `first_failure` segue a ordem normativa pública.
- [x] `POST /v1/verification/bundles` criado em `apps/api/verification.py`, hermético e sem consulta ao banco.
- [x] `400` para JSON inválido e chave duplicada; `422` para schema e pacote irrepresentável; `413` para corpo acima do limite; `200` inclusive para `INVALIDA`.
- [x] Limites de corpo, componentes, profundidade e âncoras aplicados; `Cache-Control: no-store`; âncora devolvida por fingerprint; `detail` sanitizado.
- [x] Testes (`test_verification_api.py`, `test_verification_bundle.py`) aprovados, cobrindo íntegro, inválido, incompleto, algoritmo não suportado, âncora duplicada, profundidade excessiva e determinismo do relatório (391 testes no total).

**Fora do escopo da aplicação:** rate limiting (`429`), terminação TLS e não captura de corpo por gateway, APM e tracing são responsabilidades de implantação, declaradas na ADR-0039 e não testáveis no nível do aplicativo.

## Comandos para testar o Passo 7.7

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 391 testes aprovados; banco em `20260722_0031 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.9 — Synchronization Core

- [x] Passo 7.8 (representação PDF) **deliberadamente adiado**, com decisão registrada: o cenário do Passo 7.10 não inclui PDF, e `PLANO_DE_IMPLEMENTACAO_VALIDADO.md` condiciona PAdES-LT/LTA a perfil jurídico aprovado, que não existe.
- [x] Contratos criados em `packages/core_domain/synchronization.py`: `DeviceClockReading`, `OfflineOperation`, `OperationManifestEntry`, `SynchronizationBatch`, `SynchronizationConflict`, `SynchronizationResult` e `SynchronizationBatchResult`, com os estados públicos em português da ADR-0021.
- [x] Digest da intenção separado do envelope: `compute_intent_digest` ignora OperationId, sequência local, relógio e tentativa, de modo que a mesma intenção recapturada produz o mesmo digest e o retry não duplica.
- [x] Relógio do Device permanece alegação: `TimeConfidenceLevel` não converte relógio local em prova temporal, e `precedes` só responde dentro da mesma continuidade monotônica — fora dela devolve `None` em vez de inventar precedência.
- [x] Manifesto detecta remoção, duplicação, substituição, alteração, Organization e Device divergentes e sequência fora da fronteira; `inspect` devolve todos os defeitos, não apenas o primeiro.
- [x] Ordem física do lote não cria causalidade: `SynchronizationService` processa por dependência declarada, e a dependente enviada fisicamente antes da origem é aceita depois dela.
- [x] Ciclo de dependências vira `CONFLITANTE` explícito, nunca pendência indefinida; dependência ausente, rejeitada ou em conflito permanece `DEPENDENCIA_PENDENTE` com o motivo nomeado.
- [x] IdempotencyKey reutilizada com intenção divergente produz `CONFLITANTE` e **nunca** recupera nem associa o resultado anterior; a mesma intenção sob a mesma chave produz `DUPLICADA` sem repetir o efeito.
- [x] Retomada é por operação, não por lote: a tentativa é do envelope, e o histórico append-only por tentativa preserva as decisões sucessivas em vez de reescrevê-las.
- [x] `RESULTADO_DESCONHECIDO` exige prazo de reconciliação e não é reprocessado no reenvio, porque reprocessar poderia repetir um efeito que talvez já exista; o estado não implica ausência, sucesso ou falha.
- [x] Conflito nunca é resolvido silenciosamente: não há last-write-wins, maior timestamp do Device nem último lote recebido; todo conflito carrega estado observado e alternativas.
- [x] Rejeição, conflito e quarentena preservam a captura: a OfflineOperation é gravada mesmo sem efeito oficial.
- [x] Tabelas `core_audit.offline_operations`, `core_audit.synchronization_results` e `core_audit.synchronization_batches` criadas com RLS e `FORCE ROW LEVEL SECURITY` na migration `20260722_0032`, com downgrade validado.
- [x] Três invariantes repetidas como `CHECK` no banco: `ACEITA` sem efeito, `CONFLITANTE` sem conflito e `RESULTADO_DESCONHECIDO` sem prazo são recusados mesmo por escrita direta em SQL.
- [x] Ausência deliberada de `UNIQUE (organization, idempotency_key)`: a segunda captura com intenção divergente precisa ser preservada para virar conflito explícito, e a constraint a apagaria em vez de explicá-la.
- [x] Releitura devolve `StoredOfflineOperation` com o payload em bytes canônicos, sem reconstruir `CanonicalPayload`, respeitando o contrato do Passo 2.4 que impede construir payload a partir de bytes arbitrários.
- [x] Testes de domínio (`test_synchronization_domain.py`), de aplicação (`test_synchronization_service.py`) e de integração PostgreSQL com RLS (`test_synchronization_postgresql.py`) aprovados, cobrindo a lista de testabilidade da ADR-0021 (438 testes no total).

**Fora do escopo deste passo, deliberadamente:** `OfflineCapabilityProfile`, `OfflineSession`, `OfflineAuthorizationSnapshot`, `DeviceTrustAssessment` e `LocalPreview` não constam da entrega do Passo 7.9 e não foram antecipados. A admissão do Device existe como porta explícita (`DeviceAdmissionPort`) com implementação permissiva, para que o `DeviceTrustAssessment` futuro tenha onde entrar sem alterar o serviço. O estado `VALIDADO_PARCIALMENTE` permanece declarado e não produzido: validação e processamento ocorrem na mesma fronteira transacional.

## Comandos para testar o Passo 7.9

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 438 testes aprovados; banco em `20260722_0032 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.10 — Prova completa do Core

- [x] Cenário fictício e genérico criado em `tests/integration/test_core_proof_postgresql.py`, encadeado contra o PostgreSQL autoritativo: autenticação → Organization → evento → evidência → genealogia → regra → avaliação → decisão → não conformidade → recall → dossiê → sincronização.
- [x] Vocabulário sem vertical alguma: os sujeitos são `lote`, `insumo` e `remessa`. Escrever a prova com termos de gado esconderia justamente o acoplamento que ela existe para descartar.
- [x] Cada elo alimenta o seguinte de verdade: a evidência assinada é a fonte do fato avaliado, a avaliação fundamenta a decisão, a decisão abre a não conformidade, a genealogia sustenta o recall e a operação offline sincronizada produz uma relação real do grafo.
- [x] **Substituir providers falsos sem alterar o Core:** o mesmo `EvidenceService` assina com `SoftwareSigningProvider` e com um segundo provedor de algoritmo diferente, sem uma linha de mudança no Core, e a chave continua sendo a registrada pelo Core.
- [x] **Adulterar cópias para testar integridade:** inverter a conclusão, trocar o fato que sustenta a reprovação e adulterar os bytes do componente do pacote são todos recusados — o dossiê pelo hash canônico e o `VerificationBundle` pelo verificador offline, sem consultar o Titan.
- [x] **Repetir operações:** o reenvio do lote recupera o resultado por `OperationId` sem repetir o efeito oficial, com `RESULTADO_RECUPERADO` no resultado.
- [x] **Isolamento entre duas Organizations:** role temporária `NOBYPASSRLS` percorre as **treze** tabelas do cenário no contexto da outra Organization e não enxerga nenhum registro. Provar uma tabela e presumir as outras seria exatamente a falha que este passo existe para descartar.
- [x] Recall provado nas duas propriedades: travessia limpa é `CONCLUSIVO`; travessia que reencontra o sujeito declara `CICLO_DETECTADO` e rebaixa o resultado inteiro a `INCONCLUSIVO` — lacuna nunca vira silêncio, mesmo quando o reencontro é inofensivo.
- [x] `VerificationBundle` só é declarado `VALIDA` com assinatura, política de verificação e âncora de confiança; sem âncora o veredito é `INDETERMINADA`, nunca válido por omissão.
- [x] O cenário roda em transação revertida ao final: a prova não deixa resíduo no banco.

#### Testes arquiteturais — correção de um teste que não verificava nada

- [x] **Defeito encontrado e corrigido:** `test_core_does_not_import_verticals` varria `packages/core`, diretório que nunca existiu. O teste passava sem examinar um único arquivo desde que foi escrito. Agora percorre os pacotes reais (`core_domain`, `core_application`, `core_infrastructure`, `core_integrity`).
- [x] `require_existing_root` acrescentada: qualquer teste de fronteira cujo alvo não exista passa a falhar alto. Renomear um pacote não pode transformar a verificação em aprovação automática.
- [x] Fronteiras novas cobertas: Core Domain não importa Application (a dependência aponta para dentro); Core Application não conhece framework nem ORM; `shared_kernel` não depende de quem depende dele.
- [x] Sete testes arquiteturais aprovados, sem nenhuma violação escondida pelo teste vazio anterior.

#### Superfície HTTP pública no fechamento do Core

- [x] `tests/api/test_core_public_surface.py` congela a superfície: `/health`, `/technical/authentication` e `POST /v1/verification/bundles`.
- [x] Guarda explícita contra endpoint de domínio antes do **Passo 10.4**, que é onde o plano prevê a "API mínima do fluxo aprovado". Construir a API REST de domínio agora seria pular um marco e inventar requisito.
- [x] Swagger respondendo em `/docs`, atendendo à validação por API/Swagger prevista no plano.
- [x] 449 testes aprovados no total.

**Portão do Marco 7:** contratos, testes arquiteturais e critérios do Core aprovados automaticamente. O Titan Livestock (Marco 8) permanece bloqueado até a validação manual do responsável.

#### Validação manual executada em 23 de julho de 2026

Roteiro executado pelo responsável, com os resultados observados:

- [x] Cinco testes da prova completa, nomeados um por critério do plano.
- [x] Sete testes arquiteturais e 34 testes de API/arquitetura.
- [x] Catálogo do PostgreSQL: **27 tabelas** em `core_audit`, todas com `relrowsecurity = t` e `relforcerowsecurity = t`, sem exceção.
- [x] Swagger inspecionado: apenas os três endpoints previstos, e apenas dois schemas.
- [x] `400` com `application/problem+json`, `reason_code: MALFORMED_JSON`, `cache-control: no-store` e `pragma: no-cache` observados no header real.
- [x] `detail` sanitizado, sem caminho de arquivo nem stack trace.
- [x] `401` com `www-authenticate: Bearer` na rota protegida sem token.
- [x] Portão completo: 449 testes.

**Três não conformidades encontradas pela inspeção manual, que o portão automático não detectava.** Os testes cobriam o *comportamento* do endpoint; ninguém verificava o que o OpenAPI *publica* sobre ele.

1. **Requisito textual da ADR-0039 não cumprido.** A ADR exige que o aviso "Pacotes sensíveis não devem ser enviados a uma instância pública não confiável. Nesses casos, utilize o verificador local" conste **também da documentação pública**. O `openapi.json` não o continha: o endpoint tinha `summary` e `description` nula. O aviso existia apenas na ADR e no guia de integração, e quem integra com a API lê o Swagger.
2. **Schema do corpo não publicado.** `requestBody` ausente do OpenAPI e resposta `200` com schema vazio. O `VerificationRequest` existia em código, mas o handler recebe `Request` cru — para controlar `400` versus `422` e recusar chave duplicada — e o FastAPI não o inferia. A ADR-0010 exigia schemas públicos.
3. **Rota protegida sem a negação declarada.** `/technical/authentication` não declarava o `401`; o Swagger o exibia como "Undocumented".

**Correção aplicada em 23 de julho de 2026**, sem alterar comportamento algum:

- [x] `description` do endpoint de verificação passa a conter o aviso obrigatório da ADR-0039, mais as limitações da resposta.
- [x] `public_contract_schemas()` publica `VerificationRequest` e `TrustAnchorInput` em `components.schemas`, e o `requestBody` os referencia; `app.openapi` foi estendido porque o FastAPI não registra componentes de rotas que leem o corpo cru.
- [x] `401` declarado em `/technical/authentication`.
- [x] Três testes de regressão criados em `TestContratoPublicado`, que verificam o **contrato publicado** e não apenas o comportamento — a lacuna que permitiu as três passarem despercebidas.
- [x] Portão completo reexecutado: **452 testes**, Ruff, Mypy e Alembic aprovados.

**Estado da validação manual:** aguardando a manifestação do responsável sobre as correções.

## Comandos para testar o Passo 7.10

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest tests/integration/test_core_proof_postgresql.py -v
python -m uv run --locked pytest tests/architecture tests/api -v
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 5 testes da prova completa, 7 arquiteturais e 449 no total aprovados; banco em `20260722_0032 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

---

## Passo 8.1 — RuralProperty

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Domínio (`packages/livestock_domain/property.py`):** Entidade imutável `RuralProperty` com contrato e validações (código, nome, município, UF de 2 letras maiúsculas, área em hectares positiva).
- **Aplicação (`packages/livestock_application/property_service.py`):** Porta `RuralPropertyRepositoryPort` e serviço `RuralPropertyService` com cadastro, busca por ID, busca por código e listagem paginada por `OrganizationId`.
- **Infraestrutura (`packages/livestock_infrastructure/persistence/property_repository.py`):** Repositório PostgreSQL `TransactionalRuralPropertyRepository` sobre a tabela `core_audit.rural_properties` com isolamento estrito via RLS (`titan.organization_id`).
- **Migration (`packages/core_infrastructure/persistence/migrations/versions/20260723_0033_create_rural_properties_table.py`):** Migration Alembic 0033 criando `core_audit.rural_properties` com políticas RLS ativadas e forçadas.
- **Suíte de Testes:**
  - `tests/livestock_domain/test_property_domain.py` (5 testes unitários)
  - `tests/livestock_application/test_property_service.py` (2 testes de aplicação)
  - `tests/integration/test_property_postgresql.py` (1 teste de integração RLS em PostgreSQL real)

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
```
- **Resultado:** 473 testes aprovados em 10.69s; Alembic em `20260723_0033 (head)`; Ruff e Mypy 100% limpos sem erros.

---

## Passo 8.2 — Animal e Identity

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Domínio (`packages/livestock_domain/animal.py`):** Entidade imutável `Animal` com `animal_id` permanente, `birth_property_id`, sexo (`AnimalSex`), raça, data de nascimento e coleção imutável de identificadores de campo versionados (`AnimalIdentifier`: brincos visuais, SISBOV, chip RFID).
- **Invariantes de Domínio:** Recusa de alteração da identidade permanente `animal_id` (dataclass `frozen=True`), proibição de mais de uma tag `ACTIVE` do mesmo tipo no mesmo animal e manutenção do histórico completo ao desativar brincos.
- **Aplicação (`packages/livestock_application/animal_service.py`):** Porta `AnimalRepositoryPort` e serviço `AnimalService` com `register_animal`, `attach_identifier`, `deactivate_identifier`, `get_animal` e `find_by_identifier` (com recusa de duplicidade de identificador oficial no tenant).
- **Infraestrutura (`packages/livestock_infrastructure/persistence/animal_repository.py`):** Repositório PostgreSQL `TransactionalAnimalRepository` sobre as tabelas `core_audit.animals` e `core_audit.animal_identifiers` com RLS por `OrganizationId`.
- **Migration (`packages/core_infrastructure/persistence/migrations/versions/20260723_0034_create_animals_tables.py`):** Migration Alembic 0034 criando `core_audit.animals` e `core_audit.animal_identifiers` com políticas RLS ativadas e forçadas.
- **Suíte de Testes:**
  - `tests/livestock_domain/test_animal_domain.py` (4 testes unitários)
  - `tests/livestock_application/test_animal_service.py` (2 testes de aplicação)
  - `tests/integration/test_animal_postgresql.py` (1 teste de integração RLS em PostgreSQL real)

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check packages tests
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
```
- **Resultado:** 480 testes aprovados em 14.20s; Alembic em `20260723_0035 (head)`; Ruff e Mypy 100% limpos sem erros.

---

## Passo 8.3 — AnimalMovement e PropertyStay

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Domínio (`packages/livestock_domain/movement.py`):**
  - Entidade `AnimalMovement`: **Fato e Evento de Domínio Autoritativo Imutável** com `origin_property_id`, `destination_property_id`, `movement_time`, `animal_ids`, `reason` e `evidence_reference`.
  - Entidade `PropertyStay`: **Projeção Temporal Reconstruível (Read Model / State)** que representa a permanência temporal contínua do animal em determinada fazenda (`start_time`, `end_time`, `status`).
  - Invariantes: recusa de movimentação com origem igual a destino, recusa de data futura, obrigatoriedade de pelo menos 1 animal, fechamento de permanências antigas e abertura de nova estada ativa no destino.
- **Aplicação (`packages/livestock_application/movement_service.py`):**
  - Portas `MovementRepositoryPort` e `PropertyStayRepositoryPort`.
  - Serviço `MovementService` com `register_movement`, `get_active_stay`, `get_stay_timeline` e `rebuild_stays_for_animal` (reconstrução determinística da linha do tempo a partir dos fatos autoritativos).
  - Provedor de Fatos `LivestockFactProvider` atualizado com localização e estada ativa do animal.
- **Infraestrutura (`packages/livestock_infrastructure/persistence/movement_repository.py`):** Repositórios `TransactionalAnimalMovementRepository` e `TransactionalPropertyStayRepository` em PostgreSQL operando sobre `core_audit.animal_movements`, `core_audit.animal_movement_items` e `core_audit.property_stays`.
- **Migration (`packages/core_infrastructure/persistence/migrations/versions/20260723_0036_create_movement_and_stay_tables.py`):** Migration Alembic 0036 criando as tabelas com suporte a RLS por `OrganizationId`.
- **Suíte de Testes:**
  - `tests/livestock_domain/test_movement_domain.py` (3 testes unitários)
  - `tests/livestock_application/test_movement_service.py` (1 teste de aplicação de timeline)
  - `tests/integration/test_movement_postgresql.py` (1 teste de integração RLS em PostgreSQL real)
- **Script de Validação Manual:** `scratch/validar_passo_8_3.py` (executado e aprovado com sucesso).

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check packages tests
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run python scratch/validar_passo_8_3.py
```
- **Resultado:** 485 testes aprovados em 11.08s; Alembic em `20260723_0036 (head)`; Ruff e Mypy 100% limpos sem erros; Validação manual executada com sucesso.

---

## Passo 8.4 — LivestockLot e LotMembership

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Domínio (`packages/livestock_domain/lot.py`):**
  - Entidade `LivestockLot`: Agregador que representa o grupo/lote com `lot_id`, `organization_id`, `property_id`, `code`, `name`, `lot_type` (`OPERATIONAL`, `SANITARY`, `COMMERCIAL`, `OTHER`) e `status`.
  - Entidade `LotMembership`: Associação temporal contínua entre animal e lote (`membership_id`, `lot_id`, `animal_id`, `valid_from`, `valid_until`, `reason`).
- **Aplicação (`packages/livestock_application/lot_service.py`):**
  - Portas `LivestockLotRepositoryPort` e `LotMembershipRepositoryPort`.
  - Serviço `LotService`: `create_lot()`, `add_animal_to_lot()` (com **Regra de Exclusividade Rígida para Lotes Operacionais/Manejo** e permissão de sobreposição para Lotes Sanitários/Comerciais), `remove_animal_from_lot()` e `get_lot_composition()` (composição temporal histórica).
- **Infraestrutura (`packages/livestock_infrastructure/persistence/lot_repository.py`):** Repositórios PostgreSQL `TransactionalLivestockLotRepository` e `TransactionalLotMembershipRepository` operando sobre `core_audit.livestock_lots` e `core_audit.lot_memberships`.
- **Migration (`packages/core_infrastructure/persistence/migrations/versions/20260723_0037_create_lots_tables.py`):** Migration Alembic 0037 criando as tabelas com RLS ativado e forçado por `OrganizationId`.
- **Suíte de Testes:**
  - `tests/livestock_domain/test_lot_domain.py` (2 testes unitários)
  - `tests/livestock_application/test_lot_service.py` (1 teste unitário da regra de exclusividade)
  - `tests/integration/test_lot_postgresql.py` (1 teste de integração RLS em PostgreSQL real)
- **Script de Validação Manual:** `scratch/validar_passo_8_4.py` (executado e aprovado com sucesso).

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check packages tests
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run python scratch/validar_passo_8_4.py
```
- **Resultado:** 489 testes aprovados em 11.62s; Alembic em `20260723_0037 (head)`; Ruff e Mypy 100% limpos sem erros; Validação manual executada com sucesso.

---

## Passo 8.5 — Veterinarian e Registro Profissional

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Domínio (`packages/livestock_domain/veterinarian.py`):**
  - Entidade `Veterinarian`: Representa o profissional veterinário com `veterinarian_id`, `organization_id`, `name`, `cpf` (validação de 11 dígitos), `council_number` (CRMV), `council_state` (UF de 2 letras), `verification_status` (`DECLARADO`, `DOCUMENTADO`, `VERIFICADO_EM_FONTE`, `INDETERMINADO`) e `evidence_reference`.
- **Aplicação (`packages/livestock_application/veterinarian_service.py`):**
  - Porta `VeterinarianRepositoryPort`.
  - Serviço `VeterinarianService`: `register_veterinarian()` (valida CPF e unicidade de CRMV na organização; inicia como `DECLARADO`), `attach_evidence()` (associa prova documental via módulo `Evidence` da ADR-0026 e eleva para `DOCUMENTADO`), `update_verification_status()` (permite promover para `VERIFICADO_EM_FONTE` ou marcar como `INDETERMINADO`).
- **Infraestrutura (`packages/livestock_infrastructure/persistence/veterinarian_repository.py`):** Repositório PostgreSQL `TransactionalVeterinarianRepository` operando sobre a tabela `core_audit.veterinarians` com RLS por `OrganizationId`.
- **Migration (`packages/core_infrastructure/persistence/migrations/versions/20260723_0038_create_veterinarians_table.py`):** Migration Alembic 0038 criando a tabela com RLS ativado e forçado.
- **Suíte de Testes:**
  - `tests/livestock_domain/test_veterinarian_domain.py` (2 testes unitários)
  - `tests/livestock_application/test_veterinarian_service.py` (1 teste unitário do fluxo de estados e unicidade de CRMV)
  - `tests/integration/test_veterinarian_postgresql.py` (1 teste de integração RLS em PostgreSQL real)
- **Script de Validação Manual:** `scratch/validar_passo_8_5.py` (executado e aprovado com sucesso).

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check packages tests
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run python scratch/validar_passo_8_5.py
```
- **Resultado:** 493 testes aprovados em 14.46s; Alembic em `20260723_0038 (head)`; Ruff e Mypy 100% limpos sem erros; Validação manual executada com sucesso.

---

## Passo 8.6 — Prova Integrada E2E da Vertical Titan Livestock (Encerramento do Marco 8)

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Teste de Integração E2E (`tests/integration/test_livestock_vertical_e2e.py`):**
  - Prova de integração completa de ponta a ponta em banco de dados PostgreSQL real conectando todas as primitivas da vertical Titan Livestock: `RuralProperty`, `Animal`, `AnimalIdentifier`, `Veterinarian`, `LivestockLot`, `LotMembership`, `AnimalMovement`, `PropertyStay` e `LivestockFactProvider`.
  - Verificação de isolamento tenant RLS entre diferentes `OrganizationId` em role PostgreSQL sem privilégios (`NOBYPASSRLS`).
- **Script de Validação Manual:** `scratch/validar_passo_8_6.py` (demonstração gráfica interativa da linha do tempo da vida do animal executada com sucesso completo).

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check packages tests
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run python scratch/validar_passo_8_6.py
```
- **Resultado:** 494 testes aprovados em 14.65s; Alembic em `20260723_0038 (head)`; Ruff e Mypy 100% limpos sem erros; Validação manual executada com sucesso.

> **MARCO 8 — TITAN LIVESTOCK OFICIALMENTE CONCLUÍDO E APROVADO COM 100% DE SUCESSO!**

---

## Passo 9.1 — Agregadores de Medicamentos e Prescrições

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Domínio (`packages/livestock_domain/medication.py` e `prescription.py`):**
  - Entidade `Medication`: Representa a bula do medicamento com `medication_id`, `organization_id`, `trade_name`, `active_ingredient`, `manufacturer`, `withdrawal_period_days` (carência em dias para abate) e `dosage_instruction`.
  - Entidade `Prescription`: Receita médica emitida pelo veterinário com `prescription_id`, `organization_id`, `veterinarian_id`, `medication_id`, `property_id`, `prescribed_date`, `dosage`, `administration_route`, `target_type` (`ANIMAL` ou `LOT`), `target_ids` e `reason`.
- **Aplicação (`packages/livestock_application/medication_service.py`):**
  - Portas `MedicationRepositoryPort` e `PrescriptionRepositoryPort`.
  - Serviço `MedicationService`: `register_medication()` (com recusa de nome comercial duplicado) e `issue_prescription()` (**com validação de que o veterinário possui status `DOCUMENTADO` ou `VERIFICADO_EM_FONTE`**, recusando prescrições de profissionais apenas `DECLARADO`).
- **Infraestrutura (`packages/livestock_infrastructure/persistence/medication_repository.py`):** Repositórios PostgreSQL `TransactionalMedicationRepository` e `TransactionalPrescriptionRepository` operando sobre `core_audit.medications`, `core_audit.prescriptions` e `core_audit.prescription_targets` com RLS por `OrganizationId`.
- **Migration (`packages/core_infrastructure/persistence/migrations/versions/20260723_0039_create_medication_and_prescription_tables.py`):** Migration Alembic 0039 criando as tabelas com RLS ativado e forçado.
- **Suíte de Testes:**
  - `tests/livestock_domain/test_medication_domain.py` (3 testes unitários)
  - `tests/livestock_application/test_medication_service.py` (1 teste unitário das regras de emissão de prescrição por status de veterinário)
  - `tests/integration/test_medication_postgresql.py` (1 teste de integração RLS em PostgreSQL real)
- **Script de Validação Manual:** `scratch/validar_passo_9_1.py` (executado e aprovado com sucesso).

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check packages tests
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run python scratch/validar_passo_9_1.py
```
- **Resultado:** 499 testes aprovados em 12.39s; Alembic em `20260723_0039 (head)`; Ruff e Mypy 100% limpos sem erros; Validação manual executada com sucesso.
- **Ressalva:** o `scratch/validar_passo_9_1.py` foi posteriormente removido do versionamento (scripts descartáveis passaram a ser ignorados pelo `.gitignore`). Além disso, este agregado recebeu depois a correção do contrato temporal (ver seção "Correção — contrato temporal da vertical").

## Correção — contrato temporal da vertical (commit `3846478`)

**Estado:** CONCLUÍDO. Revisão de corretude do Livestock já commitado (Marcos 8 e 9.1) que encontrou três problemas sistêmicos que o portão verde não pegava, todos corrigidos:

1. **datetime naive tratado silenciosamente como UTC** — os agregados coagiam `x.replace(tzinfo=UTC)` em vez de rejeitar; um horário local (ex.: UTC-3) virava UTC errado por 3 horas, sem erro. Corrigido: `require_utc` em todo campo datetime dos 7 agregados **rejeita** naive.
2. **`created_at = datetime.now(UTC)` como default de campo** — avaliado uma vez na carga do módulo (instância única de import) em 11 campos. Corrigido para `field(default_factory=lambda: datetime.now(UTC))`.
3. **Domínio lendo o relógio** — a checagem "movimento não pode ser no futuro" saiu do `__post_init__` para o `MovementService`. O domínio ficou determinístico.

**Evidência:** testes novos travando a rejeição de naive (domínio e serviço) e a checagem de futuro no serviço. 503 testes aprovados após a correção.

## Passo 9.1 (complemento) — MedicationBatch (commit `173b3a8`)

**Data de conclusão:** 23 de julho de 2026 · **Estado:** CONCLUÍDO. Preenche o `MedicationBatch` que o PLANO-9.1 previa e a entrega original omitiu.

### O que foi entregue
- **Domínio (`packages/livestock_domain/medication.py`):** `MedicationBatch` imutável — `batch_id`, `organization_id`, `medication_id`, `batch_number`, `expiry_date`, `manufacturing_date` opcional. Recusa validade inválida (`expiry_date <= manufacturing_date`) e número vazio; `require_utc` nas datas.
- **Aplicação (`medication_service.py`):** `MedicationBatchRepositoryPort` e `MedicationBatchService.register_batch` — recusa duplicidade `(org, medicamento, número)` e medicamento inexistente.
- **Infraestrutura + migration:** tabela `core_audit.medication_batches` com RLS+FORCE, FKs para organização e medicamento, `UNIQUE` de duplicidade; migration `20260723_0040`, registrada no `env.py`.
- **Testes:** 4 de domínio (inclui rejeição de naive), 3 de aplicação, 1 de integração com RLS.

## Passo 9.2 — VeterinaryPrescription

**Estado:** CONCLUÍDO. Entregue dentro da seção "Passo 9.1 — Agregadores de Medicamentos e Prescrições" acima (entidade `Prescription`, `issue_prescription()` com validação do status do veterinário, tabelas `prescriptions`/`prescription_targets` com RLS). Registrado aqui separadamente para alinhar à numeração do PLANO.

## Passo 9.3 — TreatmentApplication (commit `d04b7c1`)

**Data de conclusão:** 23 de julho de 2026 · **Estado:** CONCLUÍDO.

### O que foi entregue
- **Domínio (`packages/livestock_domain/treatment.py`):** `TreatmentApplication` imutável (append-only) — animal, lote (`medication_batch_id`), ator, `applied_at`, evidências, `prescription_id` opcional e `corrects_application_id` para a correção. `require_utc` no `applied_at`; recusa autocorreção.
- **Aplicação (`treatment_service.py`):** `TreatmentApplicationService` com **`register` + `correct`** e **nenhum método de edição**. A correção cria um novo registro que aponta para o original, que permanece imutável.
- **Infraestrutura + migration:** tabela `core_audit.treatment_applications` com RLS+FORCE, FKs (inclusive auto-FK de correção), índices por animal e por lote (base do recall); migration `20260723_0041`.
- **Evento:** `TreatmentAppliedEvent` declarado em `events.py`.
- **Testes:** domínio (imutabilidade, naive, entity_types, autocorreção), aplicação (**cenário do plano: edição recusada → correção por novo registro, original preservado**), integração com RLS + rastreabilidade por lote.
- **Validação manual (plano):** "registrar aplicação, tentar edição e confirmar correção por novo evento" — coberto por teste (`test_correction_creates_new_record_preserving_original`).

## Passo 9.4 — WithdrawalPeriod (commit `6600c10`)

**Data de conclusão:** 23 de julho de 2026 · **Estado:** CONCLUÍDO. **Portão do plano cumprido:** regra de negócio `titan-livestock-withdrawal-v1` proposta e **aprovada pelo responsável** antes da implementação.

### O que foi entregue
- **Regra aprovada:** por aplicação `withdrawal_ends_at = applied_at + withdrawal_period_days` (dias corridos, UTC); por animal a carência termina no **maior** prazo entre as aplicações efetivas; elegível quando `instante >= eligible_from`. O cálculo **congela (snapshot)** o prazo usado e a versão da regra.
- **Domínio (`packages/livestock_domain/withdrawal.py`):** `compute_withdrawal_ends`, `WithdrawalContribution` (prazo congelado + verificação de consistência), `AnimalWithdrawalStatus` (agrega, responde elegibilidade), `WITHDRAWAL_RULE_VERSION`.
- **Aplicação (`withdrawal_service.py`):** `WithdrawalCalculator.assess_animal` — resolve lote→medicamento, faz o snapshot do prazo e **descarta aplicações corrigidas** (conta a correção, não o original).
- **Sem migration:** é cálculo, não estado persistido.
- **Testes:** 10, cobrindo os casos de borda que o plano pede — **timezone** (naive rejeitado), **zero dias**, **sem tratamento** (sempre elegível), **múltiplas aplicações** (maior prazo), **correção** (supersessão).
- **Validação manual (plano):** "conferir datas-limite, timezone e casos de borda; confirmar preservação da versão da regra" — coberto por teste.

## Passo 9.5 — Regra de elegibilidade farmacológica (commit `4c7bf7e`)

**Data de conclusão:** 23 de julho de 2026 · **Estado:** CONCLUÍDO.

### O que foi entregue
- **Fato de carência:** `LivestockFactProvider` passa a emitir o fato `livestock.withdrawal` para um animal (`in_withdrawal`, `eligible_from`, `rule_version`, `blocking_batches`), computado pelo cálculo do 9.4.
- **Regra bloqueante + política (`eligibility.py`):** `build_eligibility_rule` (condição `in_withdrawal == False`, severidade **BLOCKING**, ação corretiva) e `build_eligibility_policy` (publicada). `PharmacologicalEligibilityService.evaluate_animal` delega Evaluation/Decision ao Core.
- **Sem domínio/tabela novos:** reusa a maquinária Policy/Rule/Evaluation/Decision do Core.
- **Testes:** animal em carência → **REJEITADA**; fora → **APROVADA**; sem tratamento → **APROVADA**.
- **Validação manual (plano):** "avaliar animal fora e dentro da carência; confirmar motivo, evidência, versão e sujeito afetado" — coberto por teste (motivo em `decision.reasons`; evidência em `blocking_batches` + snapshot; versão `titan-livestock-withdrawal-v1`; sujeito `decision.subject_id`).

## Passo 9.6 — Avaliação de lote e reavaliação (commit `fa26a18`)

**Data de conclusão:** 23 de julho de 2026 · **Estado:** CONCLUÍDO. **Fecha o Marco 9.**

### O que foi entregue
- **Fato de lote:** `LivestockFactProvider` emite `livestock.lot_eligibility` para um `livestock_lot` (`has_animal_in_withdrawal`, `blocking_animals`, `member_count`), avaliando os membros ativos no instante.
- **Regra de lote + serviço:** `build_lot_eligibility_rule` (BLOCKING: qualquer membro em carência reprova) e `PharmacologicalEligibilityService.evaluate_lot`.
- **Testes:** cenário ponta a ponta do plano — **`REJECTED → remoção do animal em carência → APPROVED`**, com ambas as decisões preservadas e **hashes de snapshot distintos**.
- **Dois defeitos reais corrigidos no caminho:**
  1. **Snapshots da vertical sem hash de integridade** — o `LivestockFactProvider` usava o construtor direto de `FactSnapshot` (hash vazio) em vez de `.create()`. Corrigido; agora todo snapshot da vertical é hashável.
  2. **`remove_animal_from_lot` quebrava no mesmo tick de clock** — no Windows o `datetime.now()` tem resolução grosseira; adicionar e remover rápido fazia `valid_until == valid_from` e a membership recusava, flakando o CI. Corrigido garantindo `valid_until` estritamente posterior.
- **Validação manual (plano):** "executar ponta a ponta o cenário `REJECTED → remoção → APPROVED` e comparar snapshots/hashes" — coberto por teste.

## Comandos para testar o Marco 9 completo

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 535 testes aprovados; banco em `20260723_0041 (head)`; Alembic, Ruff e Mypy aprovados sem erros.



















## Passo 10.1a — Emissão de eventos da vertical (commit `568a8bb`)

**Data de conclusão:** 24 de julho de 2026 · **Estado:** IMPLEMENTADO (validação manual pendente). **Abre o Marco 10.**

**Por que este passo existe.** O PLANO define o Passo 10.1 como "consulta cronológica reconstruída a partir dos eventos". Ao levantar o terreno descobriu-se que **a vertical não emitia evento nenhum**: as 13 subclasses de `DomainEvent` declaradas em `livestock_domain/events.py` nunca eram construídas — e não poderiam ser, porque o repositório do Core grava apenas `event_type` e os bytes canônicos do payload, de modo que campos de subclasse não teriam coluna e se perderiam na gravação. Uma linha do tempo lida do log encontraria a tabela vazia. O 10.1 foi então dividido, com aprovação do responsável: **10.1a** faz a vertical emitir; **10.1b** monta a timeline.

### O que foi entregue
- **Contrato de eventos (`packages/livestock_domain/events.py`, reescrito):** 14 constantes de `event_type` namespaced em `livestock.` e um construtor de `CanonicalPayload` por evento, no padrão que o próprio Core usa em `core_domain/corrections.py`. O 14º evento é o **`livestock.medication_batch_registered`**, que faltava desde o 9.1. O nome do schema do payload deriva do `event_type`, para os dois nunca divergirem.
- **Gravador (`packages/livestock_application/event_recorder.py`, novo):** `LivestockOperationContext` (organização, `actor_reference`, `source_reference`, `correlation_id`) e `LivestockEventRecorder`, que consulta a versão corrente no log do Core, monta o `DomainEvent` e delega o append. Recusa `event_type` não declarado, para o log não receber tipo improvisado.
- **Os 8 serviços da vertical emitem:** propriedade, animal (cadastro, marcação, desativação), veterinário (cadastro e promoções), medicamento, lote de medicamento, prescrição, movimentação, lote pecuário (criação, entrada, saída) e tratamento (registro e correção). Todo método de escrita troca `organization_id` solto por `context`.
- **Avaliações persistidas no Core:** `PharmacologicalEligibilityService` grava `Evaluation` e `Decision` nas tabelas do Core (avaliação antes da decisão, porque a decisão a referencia). Sem isso o bloqueio e a reavaliação do Marco 9 existiriam só durante a chamada.
- **Guarda de organização nos serviços:** operar entidade de outra Organization agora é recusado antes de gravar, e não depois.

### Decisões que valem para o resto do Marco 10
- **O agregado do evento é a entidade criada ou alterada.** Movimentar dez animais é **um** evento no fluxo do `animal_movement`, não dez; entrada e saída de lote pertencem ao `livestock_lot`. Um fato gravado duas vezes deixa de ser um fato — a timeline reúne os fluxos das entidades relacionadas.
- **A carência (9.4) NÃO virou evento.** É derivação pura de aplicações efetivas mais o prazo do medicamento; gravá-la criaria uma segunda fonte de verdade capaz de divergir do cálculo.
- **A autoria do tratamento vem do contexto.** O parâmetro `actor_id` foi removido de `register_application`/`correct_application`: com ele, o autor do registro e o do evento podiam divergir.
- **Sem ADR.** Não há decisão arquitetural nova — a vertical usar a porta do Core já é o desenho vigente (ADR-0001), e o esquema de versão por agregado e cadeia de hash é imposto pelo Core.

### Dois defeitos reais corrigidos na revisão
1. **A marcação inicial vinha datada antes do próprio cadastro.** O `AnimalService` lia o relógio duas vezes, então o evento `identifier_attached` ficava com `occurred_at` anterior ao `animal_registered`, e uma timeline ordenada por esse campo mostraria o brinco sendo posto antes de o animal existir. O relógio do Windows tem resolução grosseira (~20 instantes distintos em 20 mil leituras) e escondia o defeito em 199 de 200 execuções — em Linux, com microssegundos, inverteria sempre. Corrigido com um instante único para os dois fatos; empatados, a ordem fica por `aggregate_version`, que não depende do relógio.
2. **Reafirmar o status de um veterinário gravava evento vazio.** `update_verification_status` com o status já vigente escrevia `DOCUMENTADO → DOCUMENTADO` num log append-only, permanente e sem informação. Agora só grava quando o status muda de fato.

### Limitações registradas, a tratar no 10.1b ou depois
- **A correção de tratamento liga-se ao original por `corrects_application_id` no payload, não por `causation_id`.** A porta `DomainEventLog` expõe apenas `append` e `list_versions`, então o serviço não tem como descobrir o `event_id` do evento original. Usar `causation_id` de verdade exigiria ampliar a porta do Core.
- **Mudança só de evidência do veterinário não gera evento**, consequência da correção 2: não existe um `evidence_attached` declarado.
- **`attach_evidence` rebaixa veterinário já verificado** — força `DOCUMENTADO` sem olhar o status atual. Comportamento herdado do Marco 8; agora o rebaixamento fica registrado no log. Não alterado por mudar regra de negócio.
- **A gravação da entidade e a do evento não são atômicas por si.** Nos testes de integração as duas caem na mesma transação da conexão; em produção isso depende de a raiz de composição manter a mesma unidade de trabalho, o que deve ser amarrado no Passo 10.4.

### Testes
- **Contrato (`tests/livestock_domain/test_events_contract.py`):** congela os 14 `event_type`, exige o prefixo e o padrão canônico do Core, e verifica que o schema do payload deriva do tipo e que o payload é determinístico.
- **Gravador (`tests/livestock_application/test_event_recorder.py`):** versão por agregado (não global), separação entre instante do fato e instante do registro, recusa de tipo não declarado, correlação compartilhada e recusa de ator de outra Organization.
- **Por serviço:** cada operação gera exatamente os eventos esperados, no fluxo certo; **operação recusada não deixa evento no log**; CPF do veterinário fica fora do payload; correção de tratamento cria fluxo próprio com o vínculo no payload.
- **Integração (`test_livestock_vertical_e2e.py`):** liga o `DomainEventRepository` real e prova, contra o PostgreSQL, os fluxos por agregado na ordem certa, a **cadeia de hash do Core aplicada aos eventos da vertical** (`previous_hash` nulo no primeiro, encadeado nos seguintes) e autoria e correlação atravessando o fluxo inteiro. Os sete testes de RLS por tabela seguem com log em memória, por serem sobre o RLS das tabelas da vertical.

### Portão de verificação
`568 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (335 arquivos) e `alembic check` sem erros. Sem migration: nenhuma tabela nova — os eventos vão para o `core_audit.domain_events` do Core.

**Atenção ao rodar:** `TITAN_DATABASE_URL` é **obrigatória**, não opcional. Sem ela, `tests/integration/conftest.py` pula a suíte de integração inteira e o `alembic check` falha; o resultado parece verde (`N passed, 50 skipped`) sem ter provado nada. **Conferir `skipped == 0`.**

### Validação manual pendente (a cargo do responsável)
Consultar o log de um animal, de um lote e de um tratamento e confirmar ordem, correções, autoria e evidências — a mesma validação que o PLANO pede para o 10.1, verificável em parte já agora e por completo com a timeline do 10.1b.

## Passo 10.1b — Timeline Livestock

**Data de conclusão:** 24 de julho de 2026 · **Estado:** IMPLEMENTADO (validação manual pendente). **Fecha o Passo 10.1 do PLANO**, junto com o 10.1a.

### O que foi entregue
- **`packages/livestock_application/timeline_service.py` (novo):** `LivestockTimelineService` com três consultas — `animal_timeline`, `lot_timeline` e `treatment_timeline`, exatamente os três sujeitos que a validação manual do PLANO pede.
- **Porta de leitura no Core (`core_application/event_log.py`):** `DomainEventReader` e `RecordedEvent`. A porta existente só sabia escrever (`append`) e contar versões; ler um fluxo exigia a Infrastructure, que a Application não pode conhecer. `RecordedEvent` descreve o registro **por estrutura**, em propriedades somente-leitura, e o `DomainEventRepository` o satisfaz sem que nada precise mudar nele — a mesma solução que `ProvenanceService` já usava, aqui tipada em vez de `Any`.
- **Consulta histórica de vínculos (`lot_repository.py` + porta):** `list_memberships_for_animal`. O método existente filtra `valid_until IS NULL` e serve à regra de exclusividade; uma linha do tempo montada com ele mostraria só o lote atual e perderia todos os anteriores.
- **Corte bitemporal (`TimelineCutoff`):** dois eixos independentes, porque o Titan separa quando o fato ocorreu de quando foi registrado e as perguntas são diferentes — `occurred_until` responde "o que aconteceu até tal data"; `known_until` responde "o que o Titan sabia em tal data", que é a pergunta de auditoria. Um tratamento lançado com atraso não aparece numa reconstrução do que se sabia antes de ele ser lançado. Instante naive é recusado.

### Decisões
- **A ordem é uma chave total, não só `occurred_at`.** A chave é `(occurred_at, tipo do agregado, id do agregado, origem, sequência, id da origem)`. Ordenar apenas por instante deixaria empates resolvidos pela ordem em que o banco devolveu as linhas — duas leituras da mesma história seriam parecidas, não idênticas. Mesmo princípio do Passo 7.2.
- **Os repositórios da vertical dizem QUAIS fluxos pertencem ao sujeito; quem diz O QUE aconteceu é o evento.** Nenhum campo de estado atual entra na linha do tempo.
- **A correção não reordena nada: ela marca.** O registro corrigido permanece na sua posição cronológica com `superseded_by` apontando para quem o corrigiu. Reordenar para "correção sempre depois" mentiria sobre quando o fato ocorreu; omitir o corrigido apagaria o passado. O vínculo é lido do campo tipado da aplicação, não do payload — o payload diria o mesmo, mas exigiria desserializar bytes canônicos.
- **`Evaluation` e `Decision` entram como entradas próprias.** Não são eventos de domínio, mas são registros imutáveis do Core, e sem eles o bloqueio por carência e a reavaliação — o coração do Marco 9 — não apareceriam na história. A fronteira está nomeada no cabeçalho do módulo para não virar precedente frouxo.

### Testes
- **Unitários (`tests/livestock_application/test_timeline_service.py`, 12):** reunião dos fluxos que tocaram o animal e exclusão do que não é história dele; **ordem idêntica entre duas leituras**; cadastro nunca depois do que o seguiu; entrada de lote preservada após a remoção que a encerrou; correção marca o original sem removê-lo; cadeia de correção e lote de medicamento na história do tratamento; os dois eixos de corte; recusa de instante naive; isolamento por Organization.
- **Integração (`test_livestock_vertical_e2e.py`):** a mesma timeline montada sobre o `DomainEventRepository` real, contra o PostgreSQL — reunião dos fluxos, ordem reproduzível, corte devolvendo um prefixo exato da leitura completa, e outra Organization enxergando história vazia.

### Portão de verificação
`580 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (337 arquivos) e `alembic check` sem erros. Sem migration: a consulta é leitura.

### Limitação herdada, agora sem efeito prático
O vínculo de correção viaja em `corrects_application_id` no payload e não em `causation_id`, porque a porta do log não permite descobrir o `event_id` do evento original. A timeline contorna lendo o campo tipado do registro, então **a limitação não afeta a leitura**; ampliar a porta do Core continua sendo opção, não necessidade.

### Validação manual pendente (a cargo do responsável)
Consultar animal, lote e tratamento e confirmar ordem, correções, autoria e evidências — a validação que o PLANO define para o Passo 10.1.

## Passo 10.2 — Dossiê JSON da decisão farmacológica

**Data de conclusão:** 24 de julho de 2026 · **Estado:** IMPLEMENTADO (validação manual pendente).

**Divisão adotada, com aprovação do responsável:** o 10.2 foi dividido porque as evidências da vertical eram texto livre, e um dossiê que citasse `evidence:foto-1` cumpriria a forma da entrega sem cumprir o fundo — a validação manual do PLANO exige entender a decisão, com suas evidências, sem acesso ao banco.

### 10.2a — Evidência tipada na vertical (commit `60f3572`) · CONCLUÍDO

- **Domínio:** `TreatmentApplication.evidence_references` passou de `tuple[str, ...]` para `tuple[UniversalReference, ...]` apontando para `Evidence` do Core, na convenção que `Decision` e `NonConformity` já usavam. Recusa texto livre, referência que não seja `evidence` e evidência de outra Organization.
- **Campo novo `evidence_notes`:** as strings antigas nunca foram evidência — eram anotação de operador. Separar as duas impede que anotação seja apresentada como prova, e preserva informação operacional útil.
- **Serviço:** porta `EvidenceLookupPort`. Citar evidência inexistente é recusado (dossiê que aponta para o nada é prova vazia), e o serviço recusa aceitar referência sem ter como conferi-la, em vez de confiar no chamador.
- **Segurança:** evidência de outra Organization é recusada com a **mesma** mensagem de "não encontrada". Mensagem distinta viraria oráculo — bastaria tentar identificadores para descobrir o que outra organização possui. Mesmo princípio do `OrganizationContextDenied`.
- **Migration `20260724_0042`, sem perda:** havia 28 linhas com valores. A subida copia para `evidence_notes` antes de esvaziar; a descida devolve antes de remover a coluna. Ambos os sentidos foram executados e conferidos.

### 10.2b — Template do dossiê · CONCLUÍDO

**Fundação:**

- **O fato de carência mostra a conta, não só o resultado.** O payload de `livestock.withdrawal` passou a carregar `contributions`, com aplicação, lote, instante da aplicação, prazo congelado e fim calculado de cada contribuição. Duas consequências: quem tem o fato refaz o cálculo, e o dossiê consegue percorrer fato → aplicação → evidência, cadeia que o 10.2a tornou possível.
- **Seção de vertical no documento do Core** (`VerticalSection`, documento versão 3). Sob a chave única `vertical`, com `namespace`, `section_version` própria e `content`. O Core valida **apenas o envelope** — namespace canônico, versão inteira positiva, conteúdo não vazio — e não interpreta o conteúdo, porque conhecer vertical lhe é proibido. Ausência é declarada (`null`), não omitida. Há teste de que nenhum campo da vertical vaza para o nível do Core e de que a versão da seção é independente da versão do documento.

**Template (`livestock_application/dossier_template.py`):** `LivestockDossierTemplate` monta a seção `livestock` com quatro blocos.

- **`subject`** — identidade que um fiscal usa: brinco e SISBOV, lidos do fato `livestock.animal` **dentro do snapshot**, não do cadastro atual. O snapshot está congelado no instante da avaliação; o cadastro não. O campo `identity_source` declara essa origem.
- **`withdrawal`** — a conta da carência, com o prazo congelado de cada contribuição.
- **`evidence_chain`** — contribuição → aplicação → evidências, com hash de conteúdo e proveniência copiados. As anotações de operador viajam em campo separado, identificadas como tal: informação útil que não é prova.
- **`timeline`** — a linha do tempo completa do animal (decisão do responsável: inteira por padrão), cortada em `known_until` = instante da decisão.

**Por que o bloco `evidences` do Core fica vazio neste dossiê.** Aquele bloco é alimentado por `Fact.source_reference`, que é **singular** — serve ao fato que veio de um documento. A carência não vem de um documento: vem de um cálculo sobre N aplicações, cada uma com suas evidências. Declarar uma fonte única seria escolher arbitrariamente uma delas. `source_reference` fica nulo, que é a resposta honesta, e a cadeia completa viaja na seção da vertical. Para não haver dois formatos de evidência no mesmo documento, a serialização do conteúdo foi extraída para `evidence_content`, função pública do Core que a vertical reusa.

**Testes (10):** o dossiê é serializado, reconstruído e **verifica-se sem o Titan**; o animal é identificável pelo brinco; a decisão mostra a aritmética; a cadeia alcança a evidência com hash de 64 caracteres; anotação não se passa por prova; a timeline chega inteira até a decisão; **nada registrado depois da decisão entra na prova** — e um tratamento lançado depois aparece no dossiê novo sem invalidar o antigo, que continua conferindo.

### Correção no Core que este passo exigiu (commit `0a00128`, mesclado pelo PR #6)

O `DossierService` declarava copiar conteúdo e nunca apenas referenciar, mas o bloco `evidences` emitia só `{entity_type, id, contract_version}`. Cada entrada passou a poder carregar hash SHA-256, fonte, nível de confiança, validade, verificações e **revogação** — apresentar evidência revogada como válida transformaria o dossiê em prova falsa. Mudança aditiva, com teste de que dossiê da versão 1 continua verificando e não recebe campo novo retroativamente.

## Passo 10.3 — Dossiê PDF

**Data de conclusão:** 24 de julho de 2026 · **Estado:** IMPLEMENTADO (validação manual pendente).

### O que foi entregue

- **Porta `VerticalPdfTemplate` e `PdfSection` (`core_application/dossier_pdf_template.py`):** o PLANO exige template **fornecido pela vertical**, e o Core não pode conhecer vertical alguma. A porta troca **dados** — título, colunas e linhas de texto — e não objetos de renderização. A vertical não importa biblioteca de PDF; quem desenha é a Infrastructure do Core.
- **`SoftwareDossierPdfAdapter` recebe os templates de quem compõe a aplicação** e casa o namespace da seção com o do template. **Seção sem template não é descartada em silêncio:** o PDF declara que ela existe, não foi apresentada, e manda consultar o JSON.
- **`LivestockPdfTemplate` (`livestock_infrastructure/dossier_pdf_template.py`):** identificação do animal com brinco e SISBOV primeiro; carência com a aritmética visível (aplicação, prazo aplicado, fim calculado); uma seção de evidências por aplicação, com hash SHA-256 do conteúdo e **revogação em destaque**; e a linha do tempo.
- **Bloco "Como verificar este documento"** no PDF: procedimento em quatro passos para recalcular o hash canônico, com a regra de precedência escrita — havendo divergência entre JSON e PDF, **o JSON prevalece**.

### Decisões

- **Fidelidade antes de brevidade.** A linha do tempo é impressa inteira. Um PDF que resumisse o histórico deixaria de ser representação fiel do snapshot e passaria a ser uma opinião sobre ele. Para animal com histórico longo isso gera muitas páginas; reduzir é decisão de produto, e custa a palavra "fiel" que o PLANO usa.
- **Anotação de operador aparece marcada `NÃO É PROVA`.** No JSON a separação é estrutural; no papel precisava ser visível, senão alguém lê a anotação como evidência.

### Testes (8)

Todo valor impresso vem do JSON; a aritmética da carência é legível na folha; a anotação sai marcada como não sendo prova; **a linha do tempo é impressa inteira, sem resumo**; o PDF é produzido e carrega o material de verificação; seção sem template é declarada e não descartada; documento sem seção de vertical não imprime nada a mais; e linha que não cabe nas colunas é recusada, porque tabela desalinhada no papel vira dado trocado de coluna.

### Portão de verificação

`618 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (344 arquivos) e `alembic check` sem erros.

### Validação manual pendente

Comparar JSON e PDF campo a campo, verificar legibilidade e recalcular a integridade usando o procedimento impresso.

## Passo 10.4 — API mínima do fluxo aprovado

**Data de conclusão:** 24 de julho de 2026 · **Estado:** CONCLUÍDO. 10.4a e 10.4b implementados e **validados manualmente**. **Fecha o Passo 10.4.**

**Divisão adotada, com aprovação do responsável.** O 10.4 exige autenticação, autorização, teste positivo e negativo, tratamento de erro e validação com dois papéis e duas Organizations. A fundação não é detalhe de implementação: é pré-condição de todo endpoint. Separá-la isola um risco arquitetural transversal da simples exposição dos casos de uso — e se a raiz de composição estiver errada, todo endpoint construído sobre ela teria de ser refeito.

**Portão declarado:** nenhum outro endpoint da vertical é implementado enquanto a prova ponta a ponta do 10.4a não estiver aprovada.

### Decisões congeladas para o 10.4b

**Sete endpoints**, não seis — a contagem anterior tratava medicamento e lote como um só:

```
POST /v1/livestock/animals
POST /v1/livestock/medications
POST /v1/livestock/medication-batches
POST /v1/livestock/treatments
POST /v1/livestock/animals/{id}/eligibility
GET  /v1/livestock/animals/{id}/timeline
GET  /v1/livestock/dossiers/{id}
```

**`VeterinaryPrescription` NÃO integra a API mínima do Marco 10.** A capacidade de domínio existe e continua existindo, mas `prescription_id` é opcional em `TreatmentApplication` e **nenhuma regra do cenário aprovado depende de prescrição** — a regra bloqueante do 9.5 consulta o fato `livestock.withdrawal`. Expor `POST /prescriptions` agora seria endpoint que grava algo que nenhuma regra consulta, violando o critério de "estritamente necessários". A exposição depende da definição futura dos casos em que a prescrição será obrigatória, conforme a NR-4 — e então nascerão juntos regra de domínio, validação, fato, permissão, endpoint e testes.

**O dossiê é consequência da decisão, não criação manual.** `POST /animals/{id}/eligibility` executa fatos → avaliação → decisão → dossiê e devolve os identificadores. Não existe `POST /dossiers`: o operador não deveria ficar criando prova à mão.

**Permissões e papéis:**

| Papel | Permissões |
|---|---|
| `OPERADOR_PECUARIO` | `LIVESTOCK_ANIMAL.CRIAR`, `LIVESTOCK_MEDICATION.CRIAR`, `LIVESTOCK_TREATMENT.REGISTRAR`, `LIVESTOCK_ELIGIBILITY.EXECUTAR` |
| `AUDITOR` | `LIVESTOCK_TIMELINE.LER`, `DOSSIER.LER` |

`LIVESTOCK_ELIGIBILITY.EXECUTAR` é **uma** permissão de caso de uso, e não `AVALIAR` mais `EMITIR`. Internamente `Evaluation` e `Decision` são conceitos distintos; externamente, "executar elegibilidade" é uma capacidade de negócio única. Granularidade de permissão deve acompanhar necessidade real de separação de autoridade, não a quantidade de classes internas envolvidas — e hoje não há dois atores para as duas etapas.

O auditor não recebe **nenhuma** permissão de escrita. É o que torna o teste negativo inequívoco.

### 10.4a — Fundação HTTP da vertical · CONCLUÍDO

**Data:** 24 de julho de 2026. **Estado: CONCLUÍDO — validação manual aprovada.**

- **Raiz de composição (`apps/api/livestock_dependencies.py`):** conexão e **uma transação por requisição** — registro e evento nascem juntos ou não nascem; contexto organizacional resolvido a partir do cabeçalho `X-Titan-Organization-Id`; **RLS armado dentro da transação** com `set_config(..., true)`, para o isolamento acompanhar a unidade de trabalho e não sobrar para a próxima conexão do pool.
- **`require_permission(código)`, nunca papel.** A cadeia é `User → Membership → Role → Permission → Endpoint`. Uma rota que perguntasse "é OPERADOR_PECUARIO?" congelaria a organização de papéis dentro do código HTTP; perguntando pela permissão, papéis novos entram sem tocar em rota alguma.
- **Problem Details (`apps/api/problem.py`)** com `reason_code` estável, e a distinção mantida explícita: **401** — não sei quem você é; **403** — sei quem você é, e você não pode. Erro não previsto vira **500 sanitizado**, sem vazar nada do que aconteceu por dentro.
- **Endpoint-prova `POST /v1/livestock/animals`**, escolhido por ser simples o bastante para provar o encanamento sem envolver motor de regras, avaliação, decisão ou dossiê.
- **Superfície pública atualizada conscientemente.** As rotas de domínio do **Core** seguem fechadas: a API do Marco 10 é da vertical, e expor `/v1/decisions` ou `/v1/evidences` seria decisão à parte.

### Defesa em profundidade encontrada e corrigida no Core

O teste de isolamento falhou primeiro com **201 em vez de 403**: o operador da Org A criou animal na Org B.

A causa era o ambiente — o usuário `titan` do PostgreSQL é superusuário e **ignora RLS**. Mas isso expôs uma fragilidade real: `OrganizationContextService` consultava vínculos **confiando inteiramente no RLS** para filtrar por Organization, sem conferir se o vínculo devolvido pertencia à organização pedida. Uma conexão com role privilegiado — superusuário, engano de configuração, migração malfeita — derrubaria o isolamento **em silêncio**.

A ADR-0003 se chama "RLS **e defesa em profundidade**", e a segunda camada não existia. Foi acrescentada a conferência explícita `membership.organization_id == requested_organization_id`, com teste que usa um leitor deliberadamente permissivo para simular a ausência de RLS.

Além disso, as requisições da API no teste de integração passaram a rodar sob role `NOBYPASSRLS` criado por teste: sem isso, a prova de isolamento não valeria nada.

### Validação manual do 10.4a — APROVADA em 24 de julho de 2026

Os sete cenários foram operados pelo Swagger, com dois papéis e duas Organizations, contra o Keycloak e o PostgreSQL locais. Todos responderam o esperado.

**Ela encontrou cinco defeitos que os testes automatizados não pegaram.** Vale registrar quais, porque explicam por que o portão de validação manual existe:

1. **`reason_code` genérico no 401.** O handler devolvia `ERRO_HTTP`, e não havia como o cliente distinguir credencial ausente de qualquer outra falha HTTP. Corrigido com códigos por status conhecido (401, 403, 405, 409). O teste anterior afirmava apenas `status_code == 401` e passava com o corpo errado — passou a verificar código, mensagem, `www-authenticate` e content-type.
2. **Segurança ausente no OpenAPI.** A autenticação era ligada por `dependency_overrides`, e override **não entra no esquema**: o endpoint não declarava segurança, e o Swagger não anexava o token do botão Authorize. Fiação de produção por override é erro de desenho — a autenticação foi extraída para `apps/api/authentication.py`, de onde o `main` e a raiz de composição da vertical dependem da mesma dependência declarada.
3. **Configuração ausente reportada como credencial inválida.** Sem `TITAN_OIDC_ISSUER` e `TITAN_OIDC_AUDIENCE`, a API respondia 401 "Access Token ausente ou inválido" — mentira que manda o integrador caçar o defeito no lado errado. Agora responde 500 `AUTENTICACAO_NAO_CONFIGURADA`.
4. **Consulta de vínculos sem filtro por Organization.** `list_valid_for_user` filtrava por usuário, status e validade, e dependia **inteiramente do RLS** para o resto. Com a API rodando como superusuário — que ignora RLS — a consulta devolvia os vínculos de todas as Organizations, e a regra "exatamente um vínculo" negava acesso legítimo. A Organization passou a ser parâmetro obrigatório e filtro explícito na cláusula `WHERE`.
5. **Ruído no roteiro impresso** pela ferramenta de semeadura, e falha de codificação no console do Windows (cp1252 recusa `→`), que fazia a semeadura funcionar e o resultado se perder.

Os itens 3 e 4 são **defesa em profundidade** (ADR-0003), e somam-se à conferência acrescentada ao `OrganizationContextService` durante a implementação. Nenhuma das três foi pega pelos testes automatizados, porque todos rodam sob RLS efetivo; foi a validação com superusuário que as expôs.

### Ferramenta de semeadura (`apps/seed/`)

Escrita para destravar esta validação, e reusável em toda validação seguinte — é o começo do Passo 10.6, antecipado. Cria os usuários no Keycloak pela API de administração, monta as duas Organizations, os dois papéis com suas permissões, os vínculos e uma propriedade, e imprime o roteiro com os sete cenários e o corpo JSON pronto.

Usa apenas a biblioteca padrão: acrescentar dependência HTTP de produção por causa de uma ferramenta de desenvolvimento seria caro pelo motivo errado. É idempotente onde precisa ser — reusa usuário do Keycloak e vínculo externo, porque o par (emissor, subject) é único. Exige `TITAN_SEED_CONFIRM=1`, porque cria usuários com senha conhecida e isso só é aceitável em ambiente descartável.

### Dívida registrada

**A API não valida a própria configuração ao subir.** Ela inicia sem as variáveis de OIDC e só falha na primeira requisição autenticada. O certo é falhar no arranque, com mensagem clara. Some-se aos dois itens já anotados — rollback explícito da transação e 500 sanitizado — que têm código e não têm teste.

### Testes da prova ponta a ponta (8)

Criação autorizada `201`; sem token `401`; sem a permissão exigida `403` com `PERMISSAO_AUSENTE`; organização sem vínculo `403` com `CONTEXTO_ORGANIZACIONAL_NEGADO`, negação indistinguível; cabeçalho de organização ausente `400`; entrada inválida `422` em `problem+json` com os campos; conflito de domínio `409`; e o animal criado nasce com o evento no log do Core, provando que a transação cobre entidade e prova.

### Portão de verificação

`627 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (349 arquivos) e `alembic check` sem erros.

### Dívida registrada

Dois itens têm o código escrito e **não têm teste**: o **rollback explícito da transação** — a fixture já desfaz tudo, o que mascararia a prova — e o **500 sanitizado para erro inesperado**. Devem ser cobertos antes de o 10.4 fechar.

### Portão liberado

A prova ponta a ponta da fundação foi aprovada, e o 10.4b está liberado para começar.

### 10.4b — API mínima do fluxo · CONCLUÍDO

**Data:** 24 de julho de 2026. **Estado: CONCLUÍDO — validação manual aprovada.**

As sete rotas congeladas foram expostas, mais uma oitava que a decisão de escopo não previa e o domínio exige (ver abaixo). Todas sobre a fundação já aprovada no 10.4a.

| Rota | Permissão |
|---|---|
| `POST /v1/livestock/animals` | `LIVESTOCK_ANIMAL.CRIAR` |
| `POST /v1/livestock/medications` | `LIVESTOCK_MEDICATION.CRIAR` |
| `POST /v1/livestock/medication-batches` | `LIVESTOCK_MEDICATION.CRIAR` |
| `POST /v1/livestock/treatments` | `LIVESTOCK_TREATMENT.REGISTRAR` |
| `POST /v1/livestock/treatments/{id}/corrections` | `LIVESTOCK_TREATMENT.REGISTRAR` |
| `POST /v1/livestock/animals/{id}/eligibility` | `LIVESTOCK_ELIGIBILITY.EXECUTAR` |
| `GET /v1/livestock/animals/{id}/timeline` | `LIVESTOCK_TIMELINE.LER` |
| `GET /v1/livestock/dossiers/{id}` | `DOSSIER.LER` |

**A rota de correção não estava na lista congelada, e precisa estar.** Sem ela, a API ofereceria registro de tratamento sem oferecer correção — e corrigir por novo registro é o cenário que o Marco 9 existe para demonstrar. Não é rota nova de escopo: é a segunda metade de uma capacidade que já estava aprovada. **Não há PUT, PATCH nem DELETE em rota alguma da vertical**, e um teste de contrato falha se algum aparecer: append-only não é convenção, é ausência de rota que sobrescreva.

**A elegibilidade é POST, e não GET.** Ela não consulta: produz `Evaluation`, `Decision` e `Dossier` — registros permanentes. Um GET que grava prova quebra a expectativa de quem integra, e qualquer intermediário que repita a chamada produziria registros duplicados.

**O dossiê é consequência da decisão.** Não existe `POST /dossiers`: a execução da elegibilidade o materializa e devolve o identificador. O operador não cria prova à mão.

### Defeito estrutural encontrado: política não persistida

A avaliação falhava contra o PostgreSQL com violação de chave estrangeira: `evaluations` referencia `policies`, e **a política de elegibilidade era construída em memória a cada execução, sem nunca ser gravada**. Os testes unitários não pegavam porque repositórios falsos não impõem integridade.

O defeito era mais fundo que a chave estrangeira. Política construída em memória não tem existência própria: não pode ser consultada, comparada com a de ontem, nem citada por um dossiê emitido no ano passado. **Uma decisão só é reproduzível se a norma sob a qual foi tomada estiver registrada** — que é a tese do produto.

Foi criado `EligibilityPolicyProvider`, que grava política e regras na primeira execução e as reusa nas seguintes, procurando por código e versão. É o passo mínimo na direção da nota de rumo **NR-5**: quando a autoria passar ao administrador, o que muda é quem escreve a política; a leitura pela versão vigente já está aqui.

### Testes ponta a ponta (10, em `test_livestock_api_flow.py`)

O fluxo inteiro por HTTP — animal, medicamento, lote, tratamento, elegibilidade, dossiê — com dois papéis e duas Organizations. Cobre: bloqueio dentro da carência e aprovação fora dela; **o dossiê devolvido pela API verifica-se pelo próprio hash**, sem o Titan; a linha do tempo mostra cadastro, tratamento e decisão; a correção cria registro novo e o corrigido continua visível, marcado; auditor não escreve (403); **operador não lê dossiê** (403 — a separação vale nos dois sentidos); outra Organization não alcança o dossiê; lote inexistente devolve 404; tratamento no futuro devolve 409.

Dois testes de contrato foram acrescentados ao congelamento da superfície: nenhuma rota da vertical permite edição destrutiva, e toda rota declara autenticação e as negações 401 e 403 no OpenAPI.

### Defeito no próprio teste, encontrado e corrigido

O cliente de teste definia o override de autenticação na construção, e o override é **global à aplicação**. Num teste que usasse operador e auditor, o último sobrescrevia o outro, e os dois papéis agiam como um só — falha silenciosa que faria o teste provar o contrário do que afirma. O cliente passou a reafirmar o principal a cada requisição.

### Portão de verificação

`640 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (359 arquivos) e `alembic check` sem erros.

### Validação manual — APROVADA em 24 de julho de 2026

O fluxo completo foi operado pelo Swagger, com os dois papéis e as duas Organizations semeadas: cadastro, medicamento, lote, tratamento, elegibilidade bloqueando, correção por novo registro, leitura do dossiê e da linha do tempo pelo auditor, e as nove negações. Todos os cenários responderam o esperado.

**Dois defeitos de usabilidade encontrados, ambos na ferramenta de validação e não no produto:**

1. **Token expirando no meio do roteiro.** O padrão do Keycloak é de cinco minutos, e o roteiro não cabe nisso — o 401 resultante parece defeito da API quando é a credencial vencendo. A semeadura passou a ampliar a validade para 3600s no realm local, via API de administração, e o `titan-realm.json` já nasce assim. Está escrito no código por que isso só vale em ambiente local: ampliar validade de token em ambiente real amplia a janela em que uma credencial vazada continua servindo.
2. **Placeholders de data no roteiro** (`<hoje menos 10 dias>`) sendo enviados literalmente, com 422 correto em resposta. Todas as datas passaram a ser calculadas no instante da semeadura e impressas prontas para colar. A lição ficou registrada: placeholder em roteiro é convite a ser enviado literalmente.

A API se comportou corretamente nos dois episódios — o 422 apontou o campo exato e o motivo, que é o mínimo para corrigir sem adivinhação.

### Ferramenta de validação (`apps/seed/`)

O roteiro impresso pela semeadura cobre, com identificadores e datas reais: preparação do ambiente, o fluxo completo em cinco passos, a correção que não apaga, a leitura pelo auditor com o corte bitemporal, e as nove negações com seus `reason_code`. Fecha com o que o conjunto demonstra — que serve tanto para conferir quanto para apresentar.

## Passo 10.6 — Cenário demonstrativo reproduzível

**Data de conclusão:** 24 de julho de 2026 · **Estado:** IMPLEMENTADO (validação manual pendente). **Fecha o Marco 10**, já que o 10.5 é opcional pelo PLANO e a validação por Swagger se mostrou suficiente.

### O que foi entregue

`python -m apps.demo` executa, num comando, exatamente a sequência que o PLANO exige — **cadastro → tratamento → bloqueio → correção → reavaliação → dossiê** — e grava os artefatos em disco.

**A narrativa escolhida é a que prova a tese do produto.** Um operador lança a data errada de uma aplicação; o animal é **barrado** pela regra de carência; o erro é corrigido por novo registro; a reavaliação **libera**. As duas decisões existem, as duas aplicações continuam legíveis, e o registro errado permanece marcado. O Titan não apenas bloqueia: ele **redecide sobre fatos corrigidos sem apagar o que decidiu antes**.

Um cenário que apenas bloqueasse mostraria metade do produto — qualquer sistema recusa. O que é raro é recusar, aceitar correção e refazer a conta preservando as duas versões.

**Artefatos:** o dossiê em JSON e em PDF, gravados em `artefatos-demonstracao/` (ignorado pelo git — é saída, não fonte). O JSON é a prova: quem o recebe recalcula o SHA-256 dos bytes canônicos e compara com `dossier_hash`, sem o Titan no ar.

**Transação única:** ou o cenário inteiro existe, ou nada dele existe. Cenário pela metade confunde quem o inspeciona.

**Dados fictícios**, como o PLANO exige — nenhuma pessoa, propriedade ou animal real, e um teste verifica que nem `@` nem CPF aparecem no dossiê produzido.

### Testes (6)

Um roteiro de demonstração que ninguém executa apodrece em silêncio: a API muda, o cenário quebra, e só se descobre na hora de mostrar a alguém. Por isso a demonstração inteira roda no portão, com rollback ao final.

Cobrem: bloqueio seguido de aprovação sobre fatos corrigidos, com decisões distintas; o registro corrigido permanecendo legível e marcado; a sequência do PLANO percorrida inteira, na ordem; **o dossiê gravado em disco reconstruído e verificado sem o Titan**; o relatório narrando o essencial; e a ausência de dado pessoal.

### Portão de verificação

`646 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (362 arquivos) e `alembic check` sem erros.

### Validação manual pendente

Recriar o ambiente do zero — `docker compose down -v`, `docker compose up -d`, `alembic upgrade head` — e executar `python -m apps.demo`, conferindo os sete passos e inspecionando o JSON e o PDF gravados.

## Marco 12 — API de leitura e entidades faltantes

**Data:** 25 de julho de 2026 · **Estado:** IMPLEMENTADO (validação manual pendente).

**Fora do PLANO_DE_IMPLEMENTACAO_VALIDADO**, que se encerrou no Marco 10. Autorizado diretamente pelo responsável ao constatar que a API do Marco 10 não sustenta um frontend.

### Por que existe

A API do Marco 10 tinha oito rotas: seis criavam, duas liam por identificador. **Não havia listagem alguma** — quem cadastrasse um animal e perdesse o UUID não o alcançava mais. Metade do domínio (propriedade, lote pecuário, veterinário, movimentação) tinha serviço e persistência completos e nenhuma rota. E não havia CORS, o que bloqueia qualquer navegador em outra origem antes da requisição sair.

Nada disso era falha do Marco 10: o PLANO definiu "endpoints **estritamente necessários** para operar o cenário". A API existia para provar a tese, não para sustentar produto.

### O que foi entregue

**36 rotas** ao todo, contra 11 antes.

- **CORS** por `TITAN_CORS_ORIGINS`, sem curinga por padrão. `*` com credenciais é recusado pelo próprio navegador, e liberar tudo num serviço que carrega prova auditável não é conveniência.
- **Listagem e detalhe** de animal, propriedade, medicamento, lote de medicamento, tratamento, lote pecuário, veterinário e movimentação. Filtros onde fazem sentido: lotes por medicamento, tratamentos e movimentações por animal.
- **Composição temporal do lote** (`/lots/{id}/members?at_time=`): sem instante devolve a vigente; com ele, a que valia então. Um lote não é o que ele é hoje.
- **Escrita** de propriedade, lote, inclusão e encerramento de permanência, veterinário, atualização de verificação e movimentação.
- **`GET /dossiers?subject_id=`**, que exige o sujeito: devolver toda a prova da organização de uma vez não é pergunta que alguém faça, e é varredura cara sobre a tabela mais sensível.

### Decisões

**Paginação sem contagem total.** Contar exige varrer a tabela a cada página, e o custo cresce com o acervo — justamente onde a paginação deveria aliviar. `has_more` responde a única pergunta da interface, obtido pedindo um registro a mais e descartando-o. O teto de 200 é rígido: pedir acima é **recusado**, não reduzido em silêncio, para o cliente não acreditar que recebeu tudo.

**Permissão de leitura por área**, não uma só para tudo: `LIVESTOCK_ANIMAL.LER`, `LIVESTOCK_MEDICATION.LER`, e assim por diante. Papel de consulta restrita — um comprador que só vê o dossiê, um técnico que só vê tratamentos — deixa de exigir código novo para existir. Os conjuntos `LEITURA` e `ESCRITA` compõem os papéis, e `LIVESTOCK_PERMISSIONS` deriva deles.

**O operador passou a ler o que opera.** Cadastrar sem poder consultar o que se cadastrou não é papel utilizável. O dossiê ficou de fora: a prova é do auditor.

**`organization_id` nunca vem do cliente** — vem do contexto resolvido, e o RLS confirma no banco. Aceitá-lo por parâmetro daria ao chamador a chance de pedir dados de outra organização.

**Encerrar permanência é POST, não DELETE.** Fecha a vigência e acrescenta um fato; o vínculo anterior permanece. Um DELETE prometeria apagar o que o domínio preserva.

**O CPF do veterinário não sai da API.** É usado para impedir duplicidade no cadastro e não aparece em consulta alguma — há teste.

### Defeito encontrado no caminho

A ferramenta de semeadura mantinha uma **lista paralela** de permissões e ficou para trás em silêncio quando as de leitura nasceram. Passou a derivar de `LIVESTOCK_PERMISSIONS`, que é a fonte única.

### Testes (13, em `test_livestock_api_leitura.py`)

O animal cadastrado aparece na listagem; a página indica continuidade sem contar tudo, e páginas não se sobrepõem; pedir acima do teto é recusado; detalhe por identificador; recurso de outra organização responde como inexistente; identificador malformado é erro do cliente; ciclo completo de uma entidade que não tinha rota; o lote recebe e encerra permanência **sem apagar o vínculo**, com consulta temporal; movimentação é um fato só ainda que mova vários; o CPF não vaza; o auditor lê e não escreve; e os dossiês de um sujeito são encontráveis sem saber o UUID.

### Portão de verificação

`667 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (368 arquivos) e `alembic check` sem erros.

### Validação manual pendente

Percorrer as rotas de leitura pelo Swagger e conferir a paginação. Depois disso, a API sustenta um frontend.

## Marco 13 — Ciclo de vida do animal

**Fora do PLANO_DE_IMPLEMENTACAO_VALIDADO.** Descrito em `docs/PLANO_DE_CONCLUSAO_DO_DOMINIO.md`, autorizado pelo responsável ao optar por concluir o domínio antes de partir para o frontend.

### Passo 13.1 — Saída do rebanho

**Data:** 25 de julho de 2026 · **Estado:** CONCLUÍDO E VALIDADO.

#### Por que existe

Até aqui **o animal não tinha fim**. Todo animal cadastrado permanecia implicitamente vivo e presente, para sempre. As consequências não eram cosméticas: um recall varreria animais mortos há anos, a carência seria calculada para bois que já saíram, e toda listagem, tela e relatório nasceriam enviesados por incluir o rebanho inteiro desde a fundação da organização.

#### O que foi entregue

- `AnimalExit` em `livestock_domain/exit.py`, com `ExitType` (`MORTE`, `ABATE`, `VENDA`, `TRANSFERENCIA_DEFINITIVA`), instante, motivo, destino e evidências opcionais.
- `AnimalExitService` e `guard_animal_active` em `livestock_application/exit_service.py`.
- Tabela `core_audit.animal_exits` (migration `20260725_0043`) com RLS `FORCE` e `UNIQUE (animal_id)`.
- `POST /v1/livestock/animals/{id}/exit`, com permissão própria `LIVESTOCK_ANIMAL.REGISTRAR_SAIDA`.
- Listagem de animais passou a devolver o **rebanho ativo** por padrão, com `incluir_saidos=true` para o levantamento histórico. O detalhe sempre traz o objeto `saida`.

#### Decisões

**O estado é derivado, nunca campo mutável.** Não existe coluna `ativo` em `animals`: quem responde se o animal saiu é a existência da linha em `animal_exits`. Estado guardado em campo diverge do histórico assim que alguém o edita; estado derivado não tem como divergir.

**A saída fecha o futuro, não o passado** (decisão D-2 do plano de conclusão, tomada por delegação). `admite_fato_em` aceita `occurred_at <= saida.occurred_at`. Lançar hoje um tratamento aplicado na semana passada, antes do abate, é **regularização de registro** — o caso mais comum no campo — e recusá-lo apagaria o que de fato aconteceu, que é justamente o que um registro append-only não faz. Já um fato posterior à saída não pôde ocorrer: o animal não estava mais lá. O critério é sempre o instante em que o fato **ocorreu**, nunca o do registro.

**A guarda entrou pela porta de animal, e não por uma porta nova.** `guard_animal_active` lê a saída por `AnimalRepositoryPort.get_exit`, que todo serviço já recebe. Uma porta separada exigiria alterar a fiação de cada serviço, e quem esquecesse de fazê-lo teria a guarda desligada em silêncio. Hoje ela está ligada em tratamento, movimentação e lote.

**Terminalidade garantida no banco, e não só no serviço.** `UNIQUE (animal_id)` recusa a segunda saída mesmo que a conferência da aplicação falhe. Invariante que só a aplicação garante é invariante que se perde na primeira execução concorrente.

**Permissão própria para declarar a saída.** Quem cadastra não é necessariamente quem atesta morte, abate ou venda — um ato irreversível que encerra a história do animal. `LIVESTOCK_ANIMAL.REGISTRAR_SAIDA` deixa essa separação possível sem código novo.

#### Testes

`test_exit_service.py` (7): registro grava o fato no fluxo do animal; sair é terminal; saída no futuro é recusada; animal de outra organização não é alcançado; a guarda recusa fato posterior, aceita fato anterior e o instante exato da saída, e é silenciosa para quem está no rebanho. `test_treatment_service.py` (2): tratamento posterior à saída é recusado **sem deixar rastro no log**, e tratamento anterior continua aceito. `test_livestock_api_saida.py` (5): o animal que saiu deixa o rebanho ativo mas continua alcançável pelo detalhe; o levantamento histórico o traz com a saída preenchida; a segunda saída responde 409; o auditor recebe 403; animal inexistente responde 404.

#### Portão de verificação

`681 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (374 arquivos) e `alembic check` sem erros.

#### Validação manual — APROVADA em 25 de julho de 2026

Percorrida pelo Swagger, com conferência independente no banco ao final.

Registradas **cinco saídas**, cobrindo os quatro tipos (`ABATE`, `MORTE`, `VENDA`, `TRANSFERENCIA_DEFINITIVA`), cada uma com seu evento `livestock.animal_exited` no log — cinco fatos, cinco eventos, nenhum perdido. O animal que saiu deixou a listagem padrão e voltou com `incluir_saidos=true`, trazendo o objeto `saida`; o detalhe o trouxe preenchido sem parâmetro algum. Recusadas, como previsto: a segunda saída (409), a saída com data futura (409), o animal inexistente (404) e a tentativa do auditor (403).

**A prova central é o par de tratamentos sobre o animal abatido em 20/07.** A aplicação datada de 22/07 foi recusada com 409 e **não deixou rastro no banco**; a datada de 18/07, lançada no mesmo dia da conferência, foi aceita e gravada. O critério é o instante em que o fato ocorreu, e a regularização de registro atrasado continua possível depois da saída — que é o comportamento que distingue um registro append-only de um cadastro comum.

#### Armadilha de ambiente descoberta aqui

A senha do PostgreSQL local **não** é `titan`: o `compose.yaml` usa `TITAN_POSTGRES_PASSWORD`, com padrão `titan_local_dev_password`. Com a senha errada o `psycopg` não falha rápido — tenta `::1`, espera o timeout de conexão, e a suíte parece travada em vez de erro de configuração. A URL correta é:

```
postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan
```

**As duas Organizations do roteiro não se substituem, e confundi-las custou duas rodadas de diagnóstico às cegas.** `TITAN_OPERATOR_ORGANIZATION_ID` recebe a **operadora** — onde a identidade do usuário vive, e onde ele justamente *não* opera. O cabeçalho `X-Titan-Organization-Id` recebe a **Organization A**, que é onde há vínculo e onde estão a propriedade e o rebanho. O seed imprime as duas com rótulos distintos.

**A conferência de configuração no arranque existia e só olhava presença — resolvido no Passo 13.1a.** `TITAN_OPERATOR_ORGANIZATION_ID` estava *definida*, e por isso passou; o valor é que não era UUID. O `uvicorn` anunciou "Application startup complete" e a falha só apareceu na primeira requisição autenticada, como **500 `ERRO_INTERNO` sanitizado**, cuja causa real (`ValueError: O identificador de Organization não é um UUID válido`) existia apenas no log do servidor. Para quem validava pelo Swagger, o sintoma era indistinguível de erro nos dados enviados.

### Passo 13.1a — Forma da configuração no arranque, e a saída no roteiro do seed

**Data:** 25 de julho de 2026 · **Estado:** CONCLUÍDO.

Não é passo do plano de conclusão do domínio: é a infraestrutura de validação que o 13.1 mostrou faltar, feita antes do 13.2 porque barateia toda validação manual seguinte.

#### Conferência de forma, e não só de presença

`exigir_configuracao()` passou a recusar o arranque também quando a variável está definida com valor de forma errada: `TITAN_DATABASE_URL` que não seja `postgresql://`, `TITAN_OPERATOR_ORGANIZATION_ID` que não seja UUID e `TITAN_OIDC_ISSUER` que não seja URL absoluta http. A exceção nova é `ConfiguracaoInvalida`, distinta de `ConfiguracaoIncompleta` — faltar e estar errada são enganos diferentes e merecem mensagens diferentes.

**`TITAN_OIDC_AUDIENCE` fica deliberadamente de fora.** Audience é cadeia livre acordada com o emissor; inventar uma forma para ela recusaria configuração legítima, o que é pior do que não conferir.

**O limite continua sendo forma, nunca alcançabilidade.** Que a URL seja de PostgreSQL, o arranque garante; que o banco exista, responda e tenha as tabelas, não — isso é I/O e descobre-se usando. Vale igual para o emissor: que seja URL http, sim; que seja o Keycloak que assina os tokens, não.

**O valor recebido viaja na mensagem, menos onde carrega credencial.** É o valor que torna o diagnóstico imediato — mas a URL do banco traz a senha, e mensagem de arranque acaba em log, em ticket e em captura de tela. `TITAN_DATABASE_URL` é nomeada sem ser ecoada, e há teste que falha se a senha vazar.

#### Parte 5 do roteiro do seed

O roteiro impresso por `python -m apps.seed` ia até a Parte 4 sem uma linha sobre a saída, e a validação do 13.1 teve de ser ditada em conversa — que some quando a conversa acaba. A Parte 5 acrescenta os sete passos da saída com datas reais já calculadas, incluindo o par decisivo (fato posterior recusado, fato anterior aceito) e a segunda saída recusada.

#### Testes

`test_api_resiliencia.py` ganhou a classe `TestFormaDaConfiguracaoNoArranque` (8): UUID inválido recusado com o valor citado; emissor sem esquema recusado; banco de outro dialeto recusado; driver do SQLAlchemy não é assunto do arranque; a senha não viaja na mensagem; audience passa com qualquer valor; ausência tem precedência sobre forma; e o arranque de fato falha, pelo `TestClient`.

### Passo 13.2 — Genealogia

**Data:** 25 de julho de 2026 · **Estado:** CONCLUÍDO E VALIDADO.

#### Por que existe

O Passo 7.1 entregou a Relação Universal e Temporal, e a vertical **nunca a usou** — não havia uma única ocorrência de `UniversalRelation` em `apps/` ou `packages/livestock_*`. O animal registrava onde nasceu, não de quem. Sem mãe não há linhagem, e sem linhagem o parto do Marco 16 não teria para onde apontar.

#### A decisão que reorganizou o passo — D-4, maternidade dupla

Levantada pelo responsável durante a apresentação do escopo: **com transferência de embrião, a vaca que gesta não é a que forneceu o óvulo.** O escopo proposto tinha um único `mother_of` e teria produzido um dado que mente numa das duas leituras — ou a árvore genealógica erra, ou a rastreabilidade sanitária erra.

São **dois tipos de relação**, e não um com anotação, pelo mesmo argumento do touro do lote: "quem é a mãe genética" precisa ser consultável sem abrir metadados.

- `livestock.genetic_mother_of` — a doadora. **É por ela que a linhagem sobe.**
- `livestock.gestational_mother_of` — a receptora. Não é ancestral de ninguém; responde pelo histórico reprodutivo, que é outra pergunta e outra rota.
- `livestock.father_of` — o touro, que não muda de natureza com a transferência.

**Um ato do operador, dois fatos no registro.** Sem transferência, doadora e receptora são a mesma vaca e as duas relações são gravadas assim mesmo. Deixar a gestacional implícita obrigaria toda consulta futura a inferir, e inferência silenciosa é o que produz o dado que se contradiz — *ausência se declara, nunca se omite*.

#### O parto na vida da matriz

Pergunta do responsável que virou entrega: a vaca precisa ver o parto na linha do tempo dela. **O agregado do evento é a relação**, e não a cria nem o progenitor — é o vínculo que nasce ali. As duas pontas o enxergam por citação, exatamente como a movimentação pertence ao `animal_movement` e aparece na história de cada animal citado. Emitir um evento para cada ponta transformaria um fato em dois.

O `LivestockTimelineService` ganhou o `RelationRepositoryPort` como dependência **obrigatória**. Opcional com padrão nulo faria a genealogia sumir em silêncio para quem esquecesse de ligá-la — o mesmo perigo que o 13.1 evitou ao pôr a guarda na porta de animal.

#### Guardas da vertical

O Core já garante organização e não-autorreferência. A vertical acrescenta: **uma só mãe genética e uma só gestacional vigentes** (duas são contradição, não dado incompleto); **sexo coerente com o papel**, recusando `UNKNOWN`, porque nomear alguém como mãe é afirmar que é fêmea; **progenitor nascido antes da cria**, conferido só quando as duas datas existem; e **ciclo direto barrado**.

**Paternidade múltipla só entre vínculos `DECLARADO`.** É o touro do lote: monta natural com vários reprodutores, em que a paternidade só se resolve por DNA. Quem tem registro de cobertura afirma **um** pai — admitir um segundo ao lado de um vínculo documentado transformaria prova em palpite.

**A guarda de saída do rebanho não se aplica aqui.** Parentesco é fato anterior ao nascimento, e descobrir a mãe de um boi já abatido é a regularização que a decisão D-2 protege.

#### Vocabulário

O operador nunca vê `INFORMED` ou `VERIFIED_SOURCE`. `ParentageConfidence` traz `DECLARADO`, `DOCUMENTADO` e `VERIFICADO_EM_FONTE`, traduzidos para `ConfidenceTier` na fronteira — o Core não ganha enum por causa da vertical. O `INDETERMINADO` dos identificadores fica de fora: afirmar parentesco indeterminado é não afirmar parentesco, e para isso basta não registrar a relação.

#### Testes

`test_parentage_service.py` (22) e `test_livestock_api_genealogia.py` (10), mais o teste do parto na linha do tempo da matriz em `test_timeline_service.py`. Cobrem a transferência de embrião separando doadora de receptora, a árvore por gerações, o touro do lote, e cada guarda pelo seu lado negativo.

#### Portão de verificação

`723 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (378 arquivos) e `alembic check` sem erros. **Sem migration:** a tabela `relations` existe desde o Passo 7.1.

#### Limites conhecidos

**Ciclo profundo não é detectado** — varrer a árvore a cada escrita não se paga; a travessia se defende com conjunto de visitados. **Doadora de outra organização** (compra de embrião, caso comum) não pode ser registrada, porque a relação recusa uma ponta fora da Organization, e com razão: o caso é origem externa declarada, não vínculo, e exige decomposição própria.

#### Validação manual — APROVADA em 25 de julho de 2026

Percorrida pelo roteiro executável, com os 26 passos passando. **O responsável aprovou a prática e pediu que virasse regra**: está no `AGENTS.md`, em "O roteiro de validação manual é executável".

#### Validação manual executável

Percorrer o roteiro pelo Swagger custa caro: cada passo exige copiar o identificador que o anterior devolveu, e um engano de cópia produz erro que parece defeito da aplicação — foi assim que a validação do 13.1 se perdeu duas vezes. Por isso este passo entrega o roteiro **executável**:

```
python -m uv run --locked python -m apps.validacao
python -m uv run --locked python -m apps.validacao --pausar
```

São 26 passos que criam o rebanho, registram a genealogia, consultam a árvore e exercitam cada negação, imprimindo o que pediu, o que esperava, o que veio e por que o passo existe. **Descobre sozinho a Organization e a propriedade**, para que nenhum identificador precise ser copiado — confundir a operadora com a Organization A é justamente o engano que custou caro no 13.1.

O que ele **não** faz é julgar se a regra faz sentido para o negócio; isso continua sendo leitura humana, e é por isso que cada passo carrega a sua justificativa impressa.

A Parte 6 do roteiro do `apps.seed` continua existindo, para quem preferir conferir pelo Swagger.

**Cliente `titan-validacao` no realm local.** O `titan-swagger` tem `directAccessGrantsEnabled: false` e está certo — ele serve ao fluxo de navegador com PKCE. Habilitar o grant nele afrouxaria o cliente que a demonstração usa; um cliente à parte, criado sob demanda e só no realm local, mantém a separação. Ele precisa de **dois** mapeadores: `aud: titan-api` e `token_use: access`. Sem qualquer um deles a API responde 401, e o 401 fala do token quando o defeito está na configuração do cliente.

#### Armadilha descoberta aqui

**Passo que acrescenta permissão exige semeadura nova.** Os papéis guardam as permissões que existiam quando foram criados, e `ROLE_PERMISSIONS` é lido uma vez, na semeadura. O operador de uma semeadura anterior recebe **403 `PERMISSAO_AUSENTE`** em toda escrita nova — e o 403 fala de permissão quando o que falta é re-semear. Depois de semear, a API tem de subir com a **operadora nova**, que muda a cada execução.

O script sonda isso antes do primeiro passo e para com instrução, em vez de deixar vinte respostas vermelhas para serem lidas uma a uma.

### Passo 13.3 — Nascimento (ADR-0040)

**Data:** 25 de julho de 2026 · **Estado:** CONCLUÍDO E VALIDADO. **Fecha o Marco 13.**

#### Por que existe

Até aqui o animal surgia por cadastro, e `birth_date` era um campo digitado. O Passo 13.2 acrescentou a genealogia como **ato separado** — cadastra-se o bezerro e, numa segunda chamada, declara-se de quem ele é. Entre as duas há uma janela em que o animal está no rebanho sem linhagem, e se a segunda falha resta um órfão silencioso.

#### As decisões de domínio — todas do responsável, registradas na ADR-0040

O responsável decidiu as três questões que o plano marcava como portão, e a resposta reorganizou o modelo: **o evento reprodutivo é separado do indivíduo rastreável.**

| Situação | Evento | Cria `Animal`? |
|---|---|---|
| Nascimento vivo | `PARTO` | Sim |
| Natimorto | `PARTO`, resultado `NATIMORTO` | Sim, como indivíduo não-vivo ao nascer |
| Aborto | `ABORTO` | **Não** |
| Gemelar | **Um** `PARTO` | Dois ou mais |

**Natimorto não é morte.** `AnimalExit(MORTE)` diria que nasceu vivo e morreu depois, e o índice sairia como "97 nascimentos + 3 mortes neonatais" quando o correto é "94 nascidos vivos + 3 natimortos". Além disso, saída significa deixar o rebanho ativo, e quem nunca entrou não sai.

**Um parto, N crias.** Modelar o gemelar como dois partos perderia o vínculo obstétrico entre irmãos — que é justamente o que explica o natimorto quando o outro nasce vivo.

**Propriedade de nascimento derivada, com recuo explícito.** Vem da `PropertyStay` materna quando houver **uma única** permanência determinável; recua para a declarada; e admite lacuna. *Ausência de dado contextual não impede o registro de um fato real ocorrido.* Divergência entre declarada e permanência conhecida é **conflito explícito**, nunca resolvido em silêncio. A origem viaja no campo `birth_property_source`.

**Idade gestacional opcional, com base declarada.** Ausente significa `UNKNOWN` — nunca zero. Presente, viaja com `gestational_age_basis` (`KNOWN`, `ESTIMATED`). A classificação em precoce ou tardio é **derivada por regra versionada**, nunca gravada — mesmo princípio da carência no Passo 9.4.

#### Três consequências que o natimorto obrigou

1. **O rebanho ativo passou a excluir quem não nasceu vivo**, além de quem saiu. Sem isso o natimorto apareceria na listagem como se estivesse pastando.
2. **`guard_animal_active` passou a recusar qualquer fato sobre quem não nasceu vivo** — na mesma porta do 13.1, porque guarda que alguém esqueça de chamar é guarda desligada em silêncio.
3. **`birth_property_id` passou a aceitar nulo.** Mudança de contrato que atingiu 28 usos; o cadastro avulso continua exigindo a propriedade, e só o parto pode deixá-la ausente. `birth_outcome` e `birth_property_source` são **constitutivos e imutáveis**, como `birth_date` — não contrariam a regra "estado derivado, nunca campo mutável" do 13.1.

O rebanho legado recebe `NAO_INFORMADO` e `DECLARED`. Preencher `NASCIDO_VIVO` afirmaria o que ninguém registrou.

#### Fronteira com o Marco 16

`Pregnancy` **não** entra: exigi-la travaria o passo esperando a cobertura e o diagnóstico, e recusaria o caso majoritário do campo, em que o parto é registrado sem que a cobertura tenha sido. O `ReproductiveEvent` ganha `pregnancy_id` opcional quando o Marco 16 chegar.

#### Um fato, duas histórias

O agregado do evento é o **próprio evento reprodutivo**. A linha do tempo da mãe contém o parto; a do bezerro **começa** nele. Mesma propriedade que o 13.2 obteve com a relação de parentesco.

#### Testes

`test_reproduction_service.py` (24) e `test_livestock_api_reproducao.py` (12). Cobrem o gemelar com desfechos distintos, o natimorto sem saída e sem fatos, o aborto sem animal, as três vias da propriedade de nascimento com o conflito, e a idade gestacional nos dois sentidos.

#### Portão de verificação

`760 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (387 arquivos) e `alembic check` sem erros. Migration `20260725_0044`.

#### Limite conhecido

**O downgrade da migration falha se já houver animal sem propriedade de nascimento** — `SET NOT NULL` não passa com nulos existentes. É comportamento honesto: reverter apagaria a distinção entre "não sei onde nasceu" e "nasceu na fazenda X". Recriar do zero é o caminho em ambiente descartável.

#### Validação manual — APROVADA em 25 de julho de 2026

Roteiro executável completo, **38 passos passando**, com conferência independente no banco: dois partos e dois abortos registrados, dois nascidos vivos e dois natimortos, quatro eventos `livestock.reproductive_event_recorded` no log — e **nenhum natimorto com registro de saída**, que é a prova de que a distinção entre não nascer vivo e morrer depois sobreviveu até o banco.

## Marco 17 — Elegibilidade por mercado e conformidade territorial

**Fora do PLANO_DE_IMPLEMENTACAO_VALIDADO.** Priorizado pelo responsável sobre os Marcos 14 e 15, a partir da questão sobre embargos ambientais. Ver nota de rumo NR-6 e **ADR-0041**.

### Passo 17.1 — Georreferenciamento da propriedade (ADR-0026)

**Data:** 25 de julho de 2026 · **Estado:** CONCLUÍDO E VALIDADO.

#### Por que existe

A **ADR-0026** colocou o PostGIS no caminho crítico do MVP em 21/07/2026, nomeando a EUDR e as datas de aplicação. O PostGIS 3.6.4 está ativo no banco desde o Passo 1.4A. **E não havia uma única coluna espacial:** `RuralProperty` guardava município e UF. Este passo é a primeira vez que o espacial sai do `compose.yaml` e entra no domínio.

#### Decisões

**A geometria é entidade própria, e não campo da propriedade.** Cada registro cria uma **versão nova**; a anterior permanece. Sobrescrever faria a auditoria de 2027 ler a decisão de 2025 contra um polígono que não existia na época — que é o que a ADR-0026 proíbe ao dizer que geometria atual não substitui versão histórica usada por avaliação anterior.

**O material recebido é preservado com digest, e nunca reserializado.** O digest é calculado sobre o texto exato que chegou. Reserializar normalizaria espaços e ordem de chaves, e o digest deixaria de identificar o que de fato veio do SICAR. Há teste provando que o mesmo GeoJSON com espaçamento diferente produz digest diferente — e a rota de leitura devolve o material original, para que a conferência feche.

**Duas representações coexistem.** `source_payload` e `source_srid` guardam o declarado; a coluna `geom` guarda a normalização em 4326. A transformação é registrada, nunca silenciosa.

**Geometria inválida é recusada com o motivo, e não reparada.** `ST_IsValidReason` viaja na mensagem — sem ele, achar onde o anel se rompe num polígono de trinta mil vértices é inviável. Reparo é derivado novo, com método e diferenças declarados, e fica fora deste passo.

**Ponto não é limite de propriedade.** Só `Polygon` e `MultiPolygon` entram, e o `ST_Multi` uniformiza os dois numa forma só de coluna.

**Propriedade sem geometria continua válida.** A leitura responde `null`, que é lacuna declarada e não erro — mesmo tratamento da propriedade de nascimento desconhecida na ADR-0040.

**Permissão própria para ler o limite.** O polígono revela onde a operação fica, e derivados como bounding box e centroide revelam quase o mesmo. Ler o cadastro da propriedade não implica ler a geometria dela.

**O evento leva o digest, nunca o polígono.** Copiar a coordenada protegida para o log a faria existir em dois lugares com controles de acesso diferentes.

#### `geoalchemy2` não foi adicionada

O SQLAlchemy só precisava **saber escrever `geometry(...)` no DDL** para o `alembic check` comparar metadata e banco. A geometria entra por expressão SQL, é comparada dentro do banco e nunca vira objeto Python — nada do que a biblioteca oferece seria usado. `spatial_types.py` tem doze linhas e resolve, pelo mesmo critério que manteve o cliente do Keycloak na biblioteca padrão.

**Registrado no próprio módulo:** se o Titan passar a manipular geometria em Python, a dependência passa a valer o custo, e ampliar aquele arquivo é o sinal de que a decisão precisa ser revista.

#### Testes

`test_geometry_domain.py` (16), `test_property_geometry_postgresql.py` (7) e `test_livestock_api_geometria.py` (12). Os de PostgreSQL provam o que nenhum teste em memória provaria: transformação de SIRGAS 2000 / UTM 23S para 4326 conferida no banco, ampulheta recusada com o motivo do GEOS, versionamento preservando a versão 1 intacta, e isolamento sob papel `NOBYPASSRLS` — o usuário `titan` é superusuário e o teste passaria por acidente sem isso.

#### Portão de verificação

`796 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (395 arquivos) e `alembic check` sem erros. Migration `20260725_0045`.

#### Validação manual — APROVADA em 25 de julho de 2026

Roteiro executável completo, **47 passos passando**, incluindo os nove da geometria.

### Passo 17.2 — Importação do CAR pelo Titan_geodata

**Data:** 25 de julho de 2026 · **Estado:** CONCLUÍDO E VALIDADO. **54 passos do roteiro executável passando.**

#### A prévia ajuda o cadastro; a gravação carrega proveniência

O responsável queria usar os dados do CAR para **pré-preencher o cadastro**, e a primeira formulação minha foi restritiva demais. A síntese que ficou: `GET /properties/car-preview` consulta e **não grava nada** — município, UF e área vêm da fonte e evitam erro de digitação, e o que o operador confirmar entra como declaração dele. `POST .../geometry/import-car` grava, com proveniência `SICAR_CAR`.

**O risco real não é pré-preencher.** É o dado chegar pronto e perder a marca de que veio de fora. E há um risco que nenhuma das duas abordagens resolve: informar o CAR do vizinho. O antídoto é a proveniência declarada mais a proibição da ADR-0026 de inferir titularidade a partir de coordenadas — verificação de titularidade é afirmação à parte (NR-7).

#### Correção de modelagem: a camada é dimensão, não versão

Descoberto antes do commit, quando o responsável mostrou que o SICAR tem nove camadas. A chave era `UNIQUE (property_id, version)`; importar a reserva legal a transformaria em "versão 2 do limite", e `current_for` devolveria a reserva legal no lugar do perímetro.

Passou a ser **`UNIQUE (property_id, layer, version)`**, com `current_for(property_id, layer)` e `next_version_for(property_id, layer)`.

#### Camada do imóvel não é camada territorial

Registrado no domínio, porque a distinção vai voltar: **APP, reserva legal, hidrografia e área consolidada são partes do próprio imóvel.** Embargo do IBAMA, terra indígena da FUNAI, alerta do PRODES e uso do solo do MapBiomas existem independentemente de qualquer propriedade — a pergunta que respondem é se a fazenda **intersecta** aquela área.

Guardá-las nesta tabela faria área pública virar atributo de imóvel privado, e obrigaria a duplicá-la para cada propriedade que a tocasse. Elas exigem modelo próprio, com vigência, cobertura e `SpatialAssessment` (ADR-0026).

#### Descoberta de campo: dado oficial contém geometria inválida

Duas das três fazendas de teste têm camada com `Too few points in geometry component` **no próprio SICAR**. A primeira implementação recusava a importação inteira — e o perímetro válido não entrava por causa da área consolidada quebrada.

**A recusa está certa; a granularidade estava errada.** Camada inválida agora volta em `recusadas`, com o motivo, e não derruba as boas. Só o **perímetro** inválido faz a operação falhar: sem ele não há o que importar.

A validação de anel mínimo subiu para o domínio — anel com menos de quatro posições não delimita área, e conferir isso ali faz a recusa acontecer com mensagem do domínio, sem depender de haver banco.

#### O que a validação real mostrou

Três CAR de Mato Grosso do Sul importados de ponta a ponta. A área que o PostGIS calcula do polígono importado bate com a declarada no CAR com desvio de **0,02% a 0,04%** — o esperado por projeção geodésica:

| CAR | Declarada | Calculada | Camadas |
|---|---|---|---|
| `...1EF4AA06` (Santa Rita do Pardo) | 1.363,93 ha | 1.363,70 ha | 5 gravadas, 1 recusada |
| `...9923F6F7` (Ponta Porã) | 25.505,09 ha | 25.509,73 ha | 4 gravadas, 1 recusada |
| `...3DCF573F` (Ponta Porã) | 75,81 ha | 75,84 ha | 5 gravadas, 0 recusada |

`captured_at` recebe `dat_atuali` — a data de atualização do CAR, não a da importação. Um dos cadastros é de **2021**, e confundir os dois instantes faria a avaliação parecer mais fresca do que é.

#### O 17.5 ficou mais próximo do que o plano supunha

`RESERVA_LEGAL`, `APPS` e `USO_RESTRITO` são áreas onde a legislação restringe atividade, **e vêm do próprio CAR do imóvel** — sem depender de camada de embargo alguma. Cruzar `PropertyStay` com elas já responde "este animal permaneceu em área de reserva legal?".

Não é embargo do IBAMA e não substitui. Mas é conformidade territorial de verdade, meses antes do previsto.

#### Configuração opcional, e de propósito

A API sobe e opera inteira sem o provider; só a consulta e a importação ficam indisponíveis, com **503 nomeando as variáveis ausentes**. Tratá-las como obrigatórias impediria subir o Titan para quem não usa o Titan_geodata.

**A chave nunca vive no repositório:** entra por `TITAN_GEODATA_API_KEY`.

#### Testes

`test_car_client.py` (14), `test_geometry_service.py` (7) e o teste de camada como dimensão em `test_property_geometry_postgresql.py`.

#### Portão de verificação

`820 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (401 arquivos) e `alembic check` sem erros. Migration `20260725_0046`.

#### O que a validação manual encontrou — no roteiro, não no código

Os passos 8.0 a 8.5 só rodam com o provider configurado; sem ele são omitidos com aviso, e não falham. A primeira rodada real derrubou três defeitos, **todos no roteiro**:

**A sonda enxergava a ausência, não a recusa.** Ela tratava só `503` (provider não configurado). Provider configurado que recusa a chave responde `502`, então a Parte 8 rodava e devolvia cinco vermelhos dizendo a mesma coisa. Passou a tratar os dois, imprimindo o motivo do provider e lembrando que as variáveis são lidas **pela API**, não pelo script.

**A Parte 8 reusava a propriedade da Parte 7**, que já tinha geometria `DECLARADA` na versão 2 — o passo da data de captura afirmava sobre a geometria errada. Ganhou o passo 8.0, com propriedade própria. É o mesmo defeito que a Parte 7 tinha tido: roteiro que depende do estado deixado por outro só passa uma vez.

**Uma asserção envelheceu junto com o formato.** O passo 8.3 conferia `source` no topo da resposta da importação, escrito quando ela devolvia uma geometria só; com as camadas, o topo virou `{gravadas, recusadas}`. Passou a conferir o que agora importa: veio um perímetro, todas as gravadas têm fonte `SICAR_CAR`, e nenhuma recusa vem sem motivo — esta última é a que protege a descoberta de campo, porque recusa sem motivo é indistinguível de camada que o SICAR não tem.

**Chave recusada agora diz qual chave foi usada** (prefixo, sufixo e comprimento — nunca a chave). Sem isso não se distingue variável vazia, truncada, com o placeholder literal, ou errada. É o mesmo problema do 500 sanitizado do Passo 10.4.

## Marco 18 — Conformidade sanitária vitalícia (LIV-C01 a LIV-C09, POST-LIV-01, POST-LIV-02A)

**Consolidado neste checklist em 6 de agosto de 2026.** Entre 25 de julho e 4 de agosto, este trabalho foi conduzido e registrado numa trilha própria — `docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md` (o plano, com pergunta arquitetural e objetivo por etapa) e `docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md` (log **append-only**, citado abaixo por número de entrada) — sem nunca entrar aqui, apesar de o próprio log ter registrado a divergência em todas as suas 29 entradas (`DOCUMENTARY_PATH_DIVERGENCE_RECORDED`) sem jamais reconciliá-la. As entradas abaixo trazem o resumo necessário para não duplicar `STATUS.md`; a evidência linha a linha (comandos exatos, `scope_notes`, `residual_risks`) continua só lá.

### LIV-C01 — Baseline documental e normativo

**Data:** 4 de agosto de 2026 · **Estado:** CONCLUÍDA (`STATUS.md` Entry 0004).

Congela o baseline documental e normativo do planejamento de conformidade sanitária vitalícia, consolidado em `docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C01_BASELINE.md`. Nenhuma mudança de código, migration, ADR, `DOMAIN.md` ou `ARCHITECTURE.md`.

### LIV-C02 — Cobertura sanitária vitalícia e lacunas explícitas

**Data:** 4 de agosto de 2026 · **Estado:** CONCLUÍDA (`STATUS.md` Entry 0009, desenho na Entry 0008).

Sem introduzir `Aggregate` novo: cobertura passa a viajar como fato derivado `livestock.history_coverage` quando existe artefato de transferência recebido; o dossiê declara a cobertura honestamente como `NAO_DECLARADA`, `DECLARED` ou `PARTIAL_DECLARED`, com lacunas explícitas quando existirem.

**Evidência:** `packages/livestock_application/fact_provider.py`, `packages/livestock_application/dossier_template.py`. **Testes:** `tests/livestock_application/test_fact_provider_sanitary.py`, `tests/livestock_application/test_dossier_template.py`, `tests/integration/test_transfer_artifact_postgresql.py`, `tests/integration/test_livestock_api_saida.py -k cobertura_recebida`. **Portão:** `ruff check` limpo.

### LIV-C03 — Aquisição e continuidade documental

**Data:** 4 de agosto de 2026 · **Estado:** CONCLUÍDA (`STATUS.md` Entry 0012).

Orquestração de Application sobre conceitos existentes, sem `Aggregate` novo: um caso de uso explícito registra `ReceivedTransferArtifact` e qualquer fato importado junto. Preserva os invariantes da ADR-0042 — fato importado mantém proveniência externa; ausência de histórico prévio é lacuna de cobertura explícita, nunca histórico vazio.

**Evidência:** `packages/livestock_application/acquisition_continuity_service.py`, `apps/api/livestock_writes.py`. **Testes:** `tests/livestock_application/test_acquisition_continuity_service.py`, `test_transfer_artifact_service.py`, `test_imported_fact_service.py`, `tests/integration/test_livestock_api_saida.py -k documental`. **Portão:** `ruff check` limpo. Nenhuma migration.

### LIV-C04 — Fato sanitário importado no snapshot/evaluation

**Data:** 4 de agosto de 2026 · **Estado:** CONCLUÍDA (`STATUS.md` Entry 0013).

Fato sanitário importado passa a entrar no `FactSnapshot` com `origin`, `asserted_by`, `confidence_tier`, `source_artifact_id` e `source_reference` explícitos, sem virar observação local — proveniência e confiança preservadas como dimensões separadas. Comportamento de elegibilidade farmacológica pré-existente (que já consumia contribuições de carência importadas) preservado.

**Evidência:** `packages/livestock_application/fact_provider.py` (extensão do caminho de snapshot existente, sem novo aggregate/entity/schema). **Testes:** `tests/livestock_application/test_fact_provider_sanitary.py -k "importado or cobertura"`, `test_eligibility_service.py -k imported_treatment_fact_blocks_eligibility_with_provenance`. **Portão:** `ruff check`/`format --check` limpos. Nenhuma migration.

### LIV-C05 — Carência governada por mercado

**Data:** 4 de agosto de 2026 · **Estado:** CONCLUÍDA (`STATUS.md` Entry 0014, estendida na Entry 0016).

Base de carência de mercado explícita na configuração da vertical, usada para recalcular `livestock.withdrawal` na avaliação por mercado — sem tabela ou conceito persistente novo, combinando contribuições de carência existentes com configuração governada. Perfis de mercado estrangeiro deixaram de reutilizar silenciosamente o prazo técnico do medicamento local; sem base de carência governada, a avaliação de mercado agora falha fechado com o gap explícito `CARENCIA_POR_MERCADO_AUSENTE`. `MarketProfile` passou a expor a base de carência declarada para auditabilidade.

> **Nota de numeração:** a extensão registrada na Entry 0016 foi pedida sob o rótulo "LIV-C06", mas implementa a mesma semântica de carência-por-política do LIV-C05 do plano v1.2 — divergência já reconhecida na própria Entry 0015 do log (`STATUS.md`). O LIV-C06 real (abaixo) é outra coisa: emissão oficial de `Decision`.

**Evidência:** `packages/livestock_application/market_eligibility.py`, `apps/api/livestock_queries.py`. **Testes:** `tests/livestock_application/test_market_eligibility.py`, `tests/integration/test_livestock_api_leitura.py -k perfis_de_mercado`. **Portão:** `ruff check`/`format --check` limpos. Nenhuma migration — `Medication`, `Rule`, `NormativeBasis` e configuração permanecem conceitos distintos.

### LIV-C06 — Emissão oficial de `Decision` por revisão humana

**Data:** 4 de agosto de 2026 · **Estado:** CONCLUÍDA (`STATUS.md` Entry 0018, desenho na Entry 0017).

Leva decisões sanitárias vitalícias ao fluxo autorizado das ADRs 0048–0054: proposta imutável, autoridade resolvida do `OrganizationContext`, revisão humana oficial. **É exatamente o backend que a Onda 5 do `LIVESTOCK_PRODUCT_EXECUTION_PACKAGE.md` expôs em `/review/:proposalId`** (ver Marco 19 abaixo). Dossiê passou a preservar proposta e revisão quando a decisão é emitida por via humana.

**Evidência:** `GET /v1/livestock/decision-proposals/{proposal_id}`, `POST /v1/livestock/decision-proposals/{proposal_id}/reviews` (`apps/api/livestock_queries.py`). **Script de validação:** `apps/validacao/revisao_humana_decisao.py`. **Testes:** `tests/integration/test_livestock_api_leitura.py -k "revisao_humana or proposta_nao_corrente or abre_proposta"`. **Risco residual registrado no log:** execução completa da suíte de API ficava bloqueada localmente por uma falha de import pré-existente e não relacionada (`TERRITORIAL_DETER_RULE_CODE` ausente em `market_eligibility.py`) — o próprio log já instrui tratar isso como problema separado, não do LIV-C06.

### LIV-C07 — `Dossier`/`VerificationBundle` no escopo de conformidade vitalícia

**Data:** 4 de agosto de 2026 · **Estado:** CONCLUÍDA (`STATUS.md` Entry 0020).

Seção vertical do `Dossier` canônico passa a declarar explicitamente o escopo de cobertura vitalícia, o escopo de material importado e as limitações documentais — em vez de deixá-los implícitos. `VerificationBundleService` deriva os escopos sanitários declarados e as lacunas declaradas diretamente do dossiê canônico, preservando `Dossier` como fonte primária e `VerificationBundle` como pacote de verificação derivado. PDF continua só `Presentation` derivada, nunca fonte normativa.

**Evidência:** `packages/livestock_application/dossier_template.py`, `packages/core_application/verification_service.py`. **Testes:** `tests/livestock_application/test_dossier_template.py`, `tests/application/test_verification_bundle.py`. **Portão:** `ruff check` limpo. Nenhuma migration, API nova ou tipo de `Dossier`/`BundleManifest` novo.

### LIV-C08 — Fronteira do contrato de integração com ERP

**Data:** 4 de agosto de 2026 · **Estado:** CONCLUÍDA (`STATUS.md` Entry 0022).

Contrato outbound mínimo, sem autoridade de domínio acoplada a fornecedor: registro de tratamento passa a emitir um `COMMAND` versionado no outbox transacional existente, como reflexo administrativo técnico do evento sanitário autoritativo do Titan. Reaproveita a infraestrutura de publicação/reconciliação do Outbox já aceita; acknowledgement técnico continua separado de prova sanitária, `Evaluation` e `Decision`. Sem integração real com Odoo, sem API nova, sem alterar a fonte de verdade sanitária.

**Evidência:** `packages/livestock_application/erp_outbox.py`, `packages/livestock_application/treatment_service.py`, `packages/core_infrastructure/persistence/outbox.py`, `apps/api/livestock_treatments.py`. **Testes:** `tests/livestock_application/test_treatment_service.py`, `tests/integration/test_treatment_postgresql.py`. **Portão:** `ruff check`/`format --check` limpos. Nenhuma migration — o contrato `core_audit.outbox_messages` já existente bastou.

### LIV-C09 — Validação operacional do limite outbound

**Data:** 4 de agosto de 2026 · **Estado:** CONCLUÍDA (`STATUS.md` Entry 0027, progresso na Entry 0026, desenho pós-plano nas Entries 0023–0024).

Prova o limite assíncrono `fato sanitário → outbox → publicação → consumer/worker → acknowledgement técnico → reconciliação` de forma idempotente, auditável, isolada por Organization e sem transferir autoridade sanitária ao ERP. Handler de worker explícito para `livestock.erp.treatment_application.command`; máquina de estados do inbox mapeia falhas transitórias/permanentes para retry/quarentena; replay de quarentena bloqueado entre Organizations.

**Evidência:** `packages/livestock_application/erp_inbox.py`, `apps/worker/livestock_handlers.py`, `apps/worker/main.py`, `packages/core_infrastructure/persistence/inbox.py`. **Script de validação:** `apps/validacao/liv_c09_integracao_operacional.py`. **Testes:** `tests/livestock_application/test_erp_inbox.py`, `tests/integration/test_inbox_postgresql.py`, `test_inbox_quarantine_postgresql.py`, `test_outbox_postgresql.py`, `test_outbox_reconciliation_postgresql.py`, `test_worker_e2e.py` — provam recuperação de duplicata, retry transitório, quarentena permanente, retry de resultado desconhecido do outbox, reconciliação de claim expirado, fronteiras de autorização de replay e isolamento por Organization. **Portão:** `ruff check` limpo.

### POST-LIV-01 — Suporte operacional derivado mínimo

**Data:** 4 de agosto de 2026 · **Estado:** CONCLUÍDA (`STATUS.md` Entry 0028).

Camada mínima de suporte operacional: projeção de diagnóstico derivada apenas, sem substituir os registros nativos de outbox/inbox e sem introduzir nenhum endpoint mutável.

**Evidência:** `packages/core_application/operational_support.py`, `packages/core_infrastructure/persistence/operational_support.py`. **Script de validação:** `apps/validacao/post_liv_01_operational_summary.py`. **Testes:** `tests/application/test_operational_support.py`, `tests/integration/test_operational_support_postgresql.py`.

### POST-LIV-02A — Contrato outbound neutro e simulador

**Data:** 4 de agosto de 2026 · **Estado:** CONCLUÍDA (`STATUS.md` Entry 0029).

Substitui o payload outbound específico de tratamento por um contrato de intenção operacional neutro e versionado, separando intenção outbound, identidade externa estável da operação e classes explícitas de acknowledgement. Simulador local preserva desfechos distintos para `EXTERNAL_APPLIED`, `EXTERNAL_REJECTED`, recuperação de duplicata, duplicata não resolvida e `EXTERNAL_OUTCOME_UNKNOWN` — sem converter incerteza em sucesso silenciosamente.

**Evidência:** `packages/livestock_application/erp_contract.py`, `erp_outbox.py`, `erp_inbox.py`, `apps/worker/livestock_handlers.py`. **Script de validação:** `apps/validacao/post_liv_02a_neutral_contract.py`. **Testes:** `tests/livestock_application/test_erp_contract.py`, `test_erp_inbox.py`, `test_treatment_service.py`, `tests/integration/test_treatment_postgresql.py`, `test_worker_e2e.py`, `test_operational_support_postgresql.py`.

### POST-LIV-02B — Adaptador Odoo: só desenho, não implementado

**Data do desenho:** 4 de agosto de 2026 (commit `452609b`) · **Estado:** DESENHADA, NÃO IMPLEMENTADA.

`docs/plans/POST_LIV_02B_ODOO_COMMUNITY_ADAPTER_DESIGN_PACKAGE.md` e `POST_LIV_02B_ODOO_TARGET_DECISION.md` definem o alvo técnico ("Titan Connector API v1 → Titan Connector for Odoo Community → Odoo Community 18.x"), mas **não existe código correspondente** — nenhum arquivo em `packages/`/`apps/` cita Odoo — e não há entrada de conclusão em `STATUS.md`. A própria Entry 0029 é explícita: aguarda direção humana explícita antes de qualquer implementação.

## Marco 19 — Primeiro produto de frontend do Livestock (LIV-PROD-01)

**Data:** 6 de agosto de 2026 · **Estado:** CONCLUÍDA. Fonte: `docs/plans/LIVESTOCK_PRODUCT_EXECUTION_PACKAGE.md` (Ondas 0–5, Telas S1–S10).

Primeiro produto de frontend do Livestock: leitura do animal, registro de tratamento, elegibilidade e matriz de mercado do animal, operação comercial do lote e o workspace de revisão humana (S10, consumindo diretamente o LIV-C06 acima em `/review/:proposalId`). Mergeado em `main` via PRs #7 a #12, cada onda com portão de verificação próprio (`npm run build`/`lint`/`test` do frontend) e validação manual ponta a ponta contra API e PostgreSQL reais.

### NEXT-01 — Coverage e admissibilidade sanitária explícitas

**Data:** 12 de agosto de 2026 · **Estado:** PRIMEIRO CORTE INTERNO CONCLUÍDO. **Evidência:** `docs/plans/NEXT-01_COVERAGE_ADMISSIBILITY_DESIGN_PACKAGE.md` fixa `SANITARY_TEST_A_v1`; `packages/livestock_application/sanitary_test_coverage.py` deriva coverage/admissibilidade de `treatment_history` em 90 dias sem percentual ou persistência; `tests/livestock_application/test_sanitary_test_coverage.py` prova coverage completa com tratamento → `NAO_ATENDIDA`, completa sem tratamento → `ATENDIDA`, e parcial/ausente/inacessível/conflitante/não admissível → `INDETERMINADA`. **Portão verificado:** 1212 testes PostgreSQL incluídos passaram; Ruff, format check, Mypy e Alembic check verdes. **Limite preservado:** o artefato de transferência atual possui intervalo genérico; não foi promovido silenciosamente a coverage de tratamentos. Entrada operacional dimensional, API, persistência, mercado real e NEXT-02/03/05 exigem cortes próprios.

**Segundo corte concluído em 12 de agosto de 2026.** `packages/livestock_application/dimensional_coverage.py` introduz contrato de Application source-neutral, sem aggregate/persistência, combina intervalos admissíveis e oferece `ReceivedTransferArtifactCoverageAdapter` como primeiro adapter concreto. O artefato sem declaração dimensional produz zero contribuições; contribuições sem artefato são válidas; duas fontes contíguas podem formar coverage completa; lacunas permanecem `PARTIAL`. `SanitaryTestACoverageService` consome o assessment combinado. Evidência: 16 testes relacionados e 1220 testes completos com PostgreSQL passaram; Ruff, format check, Mypy e Alembic check verdes. Próximo portão possível: persistência/API e roteiro operacional em corte próprio; não autorizado por esta conclusão.

**Terceiro corte concluído em 12 de agosto de 2026.** A entrada operacional source-neutral de coverage dimensional passa a possuir persistência tenant-scoped em `core_audit.coverage_contributions`, com RLS forçado, serviço de aplicação e endpoints de registro/consulta por animal. `ReceivedTransferArtifact` é referência opcional de fonte e não dono da semântica. O roteiro executável `apps/validacao/coverage_dimensional.py` descobre a Organization e cria seus próprios dados, mostra requisições/respostas, explica cada passo, executa preflight e suporta `--pausar`. Testes relacionados cobrem criação, leitura, intervalo inválido, autorização, animal inexistente e rejeição de fonte de outra Organization. **Limite preservado:** a integração automática com `SANITARY_TEST_A_v1` não foi inventada; ela depende de uma classificação aprovada que distinga tratamentos antimicrobianos. **Portão verificado:** 1226 testes PostgreSQL incluídos passaram; Ruff, format check, Mypy e Alembic check verdes.

**Quarto corte concluído em 12 de agosto de 2026, commit `69230ba`.** A ADR-0056 foi aceita com `MedicationSanitaryClassificationAssertion` específica do Livestock, preservando `NO_ASSERTION != UNKNOWN != DOES_NOT_APPLY` e sem generalização prematura. A migration `20260812_0065` criou `core_audit.medication_classification_assertions` como trilha append-only protegida por RLS. `POST/GET /v1/livestock/medications/{medication_id}/sanitary-classifications` registram e recuperam Assertions de `ANTIMICROBIAL`; confiança é computada pelo servidor como `DOCUMENTED`, validação estrutural permanece explícita e o cliente não escolhe autoridade. A seleção usa `reference_time` e `knowledge_cutoff`, preservando conhecimento posterior fora da reprodução histórica. `SANITARY_TEST_A_v1` compõe `medication_classification` como dimensão independente de `treatment_history`: qualquer tratamento material sem classificação validada e temporalmente elegível remove a chave conclusiva e mantém `INDETERMINADA`; `APPLIES` permite detectar tratamento antimicrobiano; `DOES_NOT_APPLY` exige negação explícita. O roteiro `apps/validacao/classificacao_sanitaria_medicamento.py` prova ausência distinta de `UNKNOWN`, descobre os identificadores utilizados e suporta `--pausar`. Testes cobrem domínio, seleção, Policy, autorização e API; migration foi exercitada em downgrade/upgrade. **Portão verificado:** 1232 testes PostgreSQL incluídos passaram; Ruff, format check, Mypy e Alembic check verdes. **Riscos preservados:** não existe catálogo oficial, mercado real, taxonomia farmacológica genérica ou reconhecimento externo; esses limites impedem overclaim e permanecem fora do NEXT-01.

**Estado consolidado do NEXT-01 em 12 de agosto de 2026: CONCLUÍDO para o caso normativo controlado `SANITARY_TEST_A_v1`.** Os quatro cortes provam coverage dimensional, composição por múltiplas fontes, entrada operacional source-neutral e suficiência independente da classificação sanitária. O próximo desenvolvimento semântico é o Design Package do NEXT-02 — seleção temporal de duas versões fictícias de Policy e persistência de `NormativeBasisSnapshot`; nenhuma implementação do NEXT-02 está autorizada por este registro.

### NEXT-02 — Policy temporal e NormativeBasisSnapshot

**Design Package elaborado em 12 de agosto de 2026 · Estado: AGUARDANDO REVISÃO HUMANA.** `docs/plans/NEXT-02_POLICY_TEMPORAL_NORMATIVE_SNAPSHOT_DESIGN_PACKAGE.md` inventaria o suporte existente e fixa o caso `MARKET_TEST_A` com duas versões fictícias. Achados materiais: `get_active_at()` ainda mistura os eixos temporais, trata `valid_to` como inclusivo e esconde sobreposição com `ORDER BY version DESC LIMIT 1`; `Evaluation`/`context_hash` ainda não preservam `NormativeBasisSnapshot`. O pacote recomenda três cortes sequenciais, liberando primeiro apenas um resolvedor puro de Application com `reference_time`, `knowledge_cutoff`, intervalo semiaberto, lacuna e ambiguidade explícitas. Nenhum código, migration ou API do NEXT-02 foi autorizado ou implementado.

**Corte 1 concluído em 12 de agosto de 2026.** `packages/core_application/policy_temporal_selection.py` introduz somente contratos transitórios de Application (`PolicyTemporalCandidate`, request/result e resolvedor), sem entidade, aggregate, migration, API ou segunda fonte de Policy. O resolvedor filtra Organization, código, finalidade, status, `reference_time` e `knowledge_cutoff`; usa `[valid_from, valid_to)`; retorna `POLITICA_APLICAVEL_AUSENTE`, `LACUNA_TEMPORAL` ou `MULTIPLAS_POLITICAS_APLICAVEIS` sem fallback por maior versão. Oito testes fictícios cobrem v1 em maio, v2 em agosto, fronteira de 01/07, conhecimento posterior indisponível no corte original, auditoria retrospectiva, sobreposição ambígua, código ausente e draft inelegível. **Portão verificado:** 1240 testes PostgreSQL incluídos passaram; Ruff, format check, Mypy e Alembic check verdes. **Próximo portão:** revisão humana antes do Corte 2 tipado de `NormativeBasisSnapshot`; persistência e API permanecem não autorizadas.

**Corte 2 concluído em 12 de agosto de 2026.** Novo `packages/core_domain/normative.py`: `NormativeReferenceSnapshot`, classificação declarada da fonte e `NormativeBasisSnapshot` tipado, imutável e versionado, cobrindo identidade da base/Policy/Rules, finalidade, jurisdição, uso pretendido, `reference_time`, `knowledge_cutoff`, aprovação, referências, aplicabilidade, exceções, conflitos, gaps e limitações. O `snapshot_digest` é calculado e conferido sobre `CanonicalPayload`; ordem física de referências, Rules e coleções semânticas não altera a identidade, enquanto mudança de digest/dispositivo material altera a fotografia. `compute_context_hash()` recebeu o digest normativo opcional: quando presente ele participa da identidade da semântica aplicada; quando ausente mantém exatamente o contrato legado, sem reconstruir fundamento que não foi preservado. Seis testes novos provam invariantes, canonicalização, adulteração, reprodução estável, diferença de contexto e compatibilidade legada. **Portão verificado:** 1246 testes PostgreSQL incluídos passaram; Ruff, format check, Mypy e Alembic check verdes, sem nova operação de migration. **Próximo portão:** revisão humana antes do Corte 3 (persistência operacional e compatibilidade legada em banco); API e roteiro continuam fora do escopo até necessidade aprovada.

**Corte 3 e NEXT-02 concluídos em 12 de agosto de 2026.** `Evaluation` passou a preservar opcionalmente o `NormativeBasisSnapshot`; `PolicyEvaluationService` recusa fotografia cuja Policy, versão, finalidade ou Rules não correspondam exatamente ao que será executado, incorpora seu digest ao `context_hash` e `HistoricalReproductionService` reutiliza o mesmo digest preservado. O repositório PostgreSQL serializa o contrato tipado em `core_audit.evaluations.normative_basis_snapshot`, reconstrói-o com nova conferência de digest e mantém `NULL` como limitação honesta das Evaluations legadas; essa ausência é exposta pelo código controlado `NORMATIVE_BASIS_SNAPSHOT_LEGACY_ABSENT`, inclusive na reprodução histórica. Migration aditiva e reversível `20260812_0066`, testada em downgrade/upgrade, sem backfill normativo. O round-trip PostgreSQL prova snapshot completo, legado ausente e RLS por Organization. Não foi criado catálogo/tabela paralela de `normative_bases`: ainda não há fluxo de autoria/seleção que a consuma, e a Evaluation já preserva integralmente a base usada; persistência autoritativa adicional fica condicionada a esse caso concreto. Nenhuma API mudou, logo nenhum roteiro novo em `apps/validacao` é aplicável. **Portão verificado:** 1247 testes passaram; Ruff, format check, Mypy e Alembic check verdes. **Próximo incremento semântico:** NEXT-03 — fronteiras de Authority e reconhecimento externo, sujeito a Design Package e revisão antes de código.

### NEXT-03 — Autoridade por requisito e reconhecimento externo

**Design Package elaborado em 12 de agosto de 2026 · Estado: AGUARDANDO REVISÃO HUMANA.** `docs/plans/NEXT-03_AUTHORITY_EXTERNAL_RECOGNITION_DESIGN_PACKAGE.md` separa três fronteiras: competência para emitir Decision Titan (`DecisionAuthorityProfile`), autoria/competência de Source para atestar um requisito e reconhecimento externo da conclusão. O primeiro corte proposto cria somente `RequirementAuthorityAssessment` transitório e source-neutral para `AUTHORITY_TEST_A/v1`, usando Sources e Evidences sintéticos; competência não demonstrada e reconhecimento externo não demonstrado produzem `INDETERMINATE`, nunca alegação negativa ou reconhecimento implícito. Reaproveita Evidence, Provenance, Validation, EvidenceAdmissibilityAssessment, Policy, snapshot normativo e governança de decisão existentes. O pacote registra o principal gap atual: `automated_decision_authority()` ainda cria perfil ad hoc na vertical, portanto não será expandido como solução de competência de Source. Nenhum código, migration, API, mercado real, integração externa ou alteração de Odoo está autorizado por este registro.

**Corte 1 concluído em 12 de agosto de 2026.** `packages/livestock_application/requirement_authority.py` introduz apenas contratos transitórios source-neutral: `SourceCompetenceAssertion`, `RequirementAuthorityAssessment` e serviço puro. O assessment usa requisito, capacidade, finalidade, vigência `[valid_from, valid_until)` e `knowledge_cutoff`; exige base de competência, Evidence, validação e admissibilidade para `SATISFIED` sob a fronteira `INTERNAL_ONLY`. Source ausente, competência desconhecida/ambígua, conhecimento posterior, Evidence não admissível ou alegação externa sem reconhecimento demonstrado retornam `INDETERMINATE`; `NOT_SATISFIED` fica restrito a incompetência explícita e não ambígua. Nenhum `DecisionAuthorityProfile` é aceito como prova de Source, nem há entidade, aggregate, migration, API, Policy/Evaluation, mercado real, integração externa ou Odoo. Nove testes inteiramente sintéticos cobrem competência admissível, ausência, reconhecimento externo não demonstrado, conhecimento posterior, incompetência explícita, conflito entre Sources, admissibilidade e fronteira temporal. **Próximo portão:** revisão humana antes do Corte 2, que poderá integrar a suficiência de autoridade a uma Policy controlada; persistência e API permanecem não autorizadas.

**Corte 2 concluído em 12 de agosto de 2026.** `AuthorityTestARequirementService` converte exclusivamente o assessment fictício `AUTHORITY_TEST_A/v1` em Fact de requisito e Rule declarativa controlada. A chave `source_authority_sufficient` só é exposta como `true` para `SATISFIED` e como `false` para incompetência explícita não ambígua; em qualquer lacuna ela fica ausente, de modo que o motor Core retorna `INDETERMINADA` e não uma aprovação positiva. A fronteira de reconhecimento é preservável na coleção já tipada de `NormativeBasisSnapshot.limitations` como `RECOGNITION_BOUNDARY:<valor>` e, por isso, altera o digest normativo sem novo campo ou schema. Quatro testes cobrem resultado positivo, incompetência explícita, lacuna bloqueando conclusão e boundary alterando a identidade do snapshot. Nenhuma Evaluation/Decision persistida, API, migration, mercado real, reconhecimento positivo externo, Odoo ou `DecisionAuthorityProfile` foi alterado.

**Corte 3 e NEXT-03 concluídos em 12 de agosto de 2026.** A decisão de persistência condicional foi examinada contra o fluxo entregue: `RequirementAuthorityAssessment` é derivado a cada avaliação, não tem identificador, repositório, transições, aprovação, revogação, retenção autônoma ou consulta própria. As informações que explicam o resultado já vivem nas assertions de competência e, quando a Policy controlada o consome, no Fact e no `NormativeBasisSnapshot` que participam da Evaluation. Portanto, não foi criada entidade, migration, RLS, API ou roteiro manual: persistência seria duplicação sem ciclo de vida demonstrado. O NEXT-03 encerra mantendo explícita a fronteira entre competência da Source, autoridade de emissão da Decision e reconhecimento externo. **Portão de verificação:** decisão conferida contra os contratos e testes dos Cortes 1–2; suíte completa, Ruff, formato, Mypy e Alembic serão executados antes do commit. **Próximo incremento:** NEXT-05 — Market Eligibility Dossier, reutilizando o mecanismo de Dossier existente.

### NEXT-05 — Market Eligibility Dossier

**Design Package elaborado em 12 de agosto de 2026 · Estado: AGUARDANDO REVISÃO HUMANA.** `docs/plans/NEXT-05_MARKET_ELIGIBILITY_DOSSIER_DESIGN_PACKAGE.md` define que Market Eligibility reutiliza o `Dossier`, `DossierService`, `VerticalSection`, `VerificationBundle` e `BundleManifest` existentes. A extensão proposta é uma subseção versionada da vertical Livestock, sempre ancorada em uma única `Decision`/`Evaluation`/`Policy`; a matriz continua derivação de leitura e não ganha persistência nem identidade própria. O primeiro caso será `MARKET_TEST_A`, fictício, com boundary `INTERNAL_ONLY`, cobertura e snapshot normativo explícitos e aviso obrigatório de que o resultado Titan não autoriza exportação nem prova reconhecimento externo. Nenhum código, migration, API, mercado real, integração SISBOV/Odoo ou composição operacional foi autorizado por este registro.

## Notas de rumo — decisões de direção fora da numeração do PLANO

**Registradas em 24 de julho de 2026.** Não são passos do plano e não têm portão de verificação. São conclusões de análise que orientam passos futuros e que se perderiam se ficassem apenas em conversa. Nenhuma delas está implementada.

### NR-6 — Conformidade socioambiental e elegibilidade por mercado

**Registrada em 25 de julho de 2026**, a partir de questão levantada pelo responsável sobre embargos ambientais, terras indígenas e áreas de desmatamento.

**Não era imprevisto: era decidido e não implementado.** A **ADR-0026**, aceita em 21/07/2026, já colocava o PostGIS no caminho crítico do MVP, nomeava a EUDR com as datas de aplicação, e declarava que o go-to-market prioriza *"o comprador que precisa reconstruir fornecedores diretos e indiretos"*. O PostGIS 3.6.4 está ativo no banco desde o Passo 1.4A. O que não existe é uma única coluna espacial: `RuralProperty` guarda município e UF.

**A pergunta certa não é "está conforme".** É "para quais mercados este ativo é elegível" — elegibilidade é relação entre **um sujeito** e um destino, não propriedade do animal. Formalizado na **ADR-0041**, que na revisão do responsável teve a tese generalizada: **o Titan não atribui a um sujeito uma condição que pertence a outro.** Requisito de estabelecimento produz decisão sobre o estabelecimento; a matriz do animal declara `CONDICIONADO` e nomeia a dependência.

**A percepção que barateia tudo:** conformidade territorial é a mesma máquina da carência. `PropertyStay × camada de restrição × regra versionada → bloqueio explicável` tem a mesma forma que `aplicação × medicamento × regra → bloqueio explicável`. O motor do Marco 9, a decisão explicável, a reavaliação do 9.6 e o dossiê já existem.

**Três diferenças que a carência não tem:** o embargo é **retroativo** (publicado depois do fato, o que faz um animal aprovado ontem estar reprovado hoje sem nada nele ter mudado); a **prova negativa vence** (consulta de março não afirma nada sobre junho); e a **contaminação viaja pela cadeia** (fazenda limpa que compra de fazenda embargada herda o problema).

**As camadas vêm do `Titan_geodata`**, aplicação paralela do responsável, que já entrega geometria da fazenda e dados do SICAR e receberá camadas ambientais e sociais. É o *"provider externo substituível por contrato versionado"* que a ADR-0026 previa. **Decisão: importar e guardar**, o que torna a reprodutibilidade responsabilidade do Titan e resolve o fato de a origem ainda não versionar consultas históricas.

**Dívida descoberta:** `Medication.withdrawal_period_days` é número único, e o prazo varia por país de destino. Não foi erro — o escopo era mercado interno. **A correção não é transformar o campo em coleção:** prazo regulatório não é propriedade intrínseca do medicamento, e sim requisito normativo com fonte, vigência e condições próprias (espécie, via, dose, finalidade). A direção é uma entidade `WithdrawalRequirement`, registrada na ADR-0041 como consequência a detalhar.

**O limite que já apareceu três vezes:** doadora de embrião de terceiro (13.2), fornecedor indireto (aqui) e frigorífico (abate). `UniversalRelation` recusa ponta fora da Organization, e com razão. Como representar **contraparte externa** sem furar o isolamento exige ADR própria.

**Decomposição proposta — Marco 17:** 17.1 georreferenciamento da propriedade; 17.2 importação do CAR; 17.3 mercado de destino e matriz de elegibilidade; 17.4 carência por mercado; 17.5 avaliação territorial, quando as camadas existirem.

### NR-7 — `Assertion` como conceito estrutural emergente

**Registrada em 25 de julho de 2026**, observada pelo responsável ao revisar a ADR-0042. **Marcada, e deliberadamente não generalizada.**

Até o Marco 10 o vocabulário do Core era `Fact`, `Evidence`, `Policy`, `Decision`. As ADRs 0041 e 0042 fizeram aparecer algo maior, sem que nenhuma das duas o tenha proposto:

```text
                  Assertion
                 /    |    \
           Subject  Fact   AssertedBy
                       \
                      Evidence
                         |
                    Provenance
                         |
                     Confidence
```

**A mesma forma já apareceu quatro vezes:** `ContinuityAssertion` ("este animal é o mesmo indivíduo anterior"); o vínculo entre contraparte e Organization ("esta contraparte é a Organization Y"); o fato importado ("a Organization A afirma que o tratamento T ocorreu sobre o animal X naquele instante"); e a paternidade declarada do Passo 13.2.

E é previsível que se repita em toda integração externa — órgão oficial afirma, fazenda afirma, sensor afirma, veterinário afirma.

Se aparecer em domínio distinto pela terceira ou quarta vez, talvez exista um conceito de Core parecido com:

```text
Assertion<T>
    subject · predicate · value
    asserted_by · asserted_at
    evidence[] · provenance · confidence
```

**Não generalizar agora**, pela mesma cautela das ADRs 0041 e 0042: sem casos concretos em domínios diferentes, a abstração sai especulativa.

**Por que isso importa mais do que parece.** Ele descreve o que o Titan está se tornando: menos um banco que pretende possuir a verdade, e mais um sistema que preserva, relaciona, verifica e avalia **afirmações sobre o mundo real**. É a frase que fecha a ADR-0042 — *"o Titan não precisa possuir toda a realidade"* — e é o que torna a rastreabilidade tratável, porque nenhum sistema jamais possuirá a cadeia inteira.

Cada conceito responde a uma pergunta distinta, e a separação é o ativo:

```text
Identity    → sobre quem estamos falando?
Continuity  → é o mesmo sujeito anterior?
Provenance  → quem afirmou?
Evidence    → com base em quê?
Confidence  → quanto essa afirmação sustenta?
Coverage    → de qual período realmente sabemos?
Policy      → isso é suficiente para esta finalidade?
Decision    → qual é a conclusão?
```

### NR-8 — Modelo de receita, porta de entrada e a ordem que ela impõe ao Marco 17

**Data:** 25 de julho de 2026 · **Estado:** direção registrada; nenhuma decisão comercial fechada. **Quem paga ainda está indefinido** — o que segue são hipóteses avaliadas, não compromisso.

#### O enquadramento correto: a EUDR não é embargo

É regulação de acesso, e a responsabilidade legal é do **operador europeu que importa** — não do produtor, não do frigorífico brasileiro, não do software. Ninguém compra "o Titan me libera para exportar". Compram *"o Titan me dá com o que sustentar a declaração que eu assino, e me protege quando o auditor voltar dois anos depois"*.

Isso confirma a ADR-0041 como acerto comercial, e não só de modelagem: **o Titan mostra a matriz com motivos; quem decide é o frigorífico.**

Advertência operacional: o calendário da EUDR já foi adiado mais de uma vez. **Conferir o prazo vigente antes de usá-lo como argumento** — errar isso numa conversa comercial custa credibilidade. O que não muda é o marco de **31/12/2020**.

#### Onde o Titan é forte, e onde não responde ainda

Forte, e raro no mercado brasileiro:

- **Rastreabilidade individual, não predial.** A EUDR para bovinos pede a geolocalização de **todos** os estabelecimentos onde o animal permaneceu, não do último. `PropertyStay × geometria` é essa pergunta; sistema predial não a responde sem inventar.
- **Lacuna declarada em vez de silêncio** (ADR-0042). O modo de falhar do mercado é sinal verde onde o dado não existe — o bezerro veio de uma cria que ninguém mapeou, e o relatório não distingue "verifiquei e está limpo" de "não olhei".
- **Reprodutibilidade da avaliação.** Como o embargo é retroativo, "o que o mapa dizia no dia do embarque" e "o que diz hoje" divergem justamente no caso que importa. Quem reconsulta a fonte responde a pergunta errada.

Ainda não responde:

1. **A série temporal.** O CAR dá o polígono; o marco de 2020 exige PRODES/DETER/MapBiomas. Hoje o Titan sabe **onde** a fazenda fica e não sabe o que aconteceu lá. É o 17.5.
2. **O dado de fornecedor indireto.** A ADR-0042 modela a travessia entre organizations, mas o dado real da cadeia cria→recria→engorda está na **GTA**, estadual e heterogênea. Sem ingestão, é a melhor estrutura de proveniência do mercado com nada dentro.
3. **O artefato final.** O comprador europeu precisa de DDS no TRACES, com geolocalização em formato próprio e referência que desce a cadeia. O dossiê do 10.2/10.3 chega perto e não é isso. Menor esforço, maior valor percebido.

#### Consequência: o 17.5 passa na frente do 17.3

A matriz de elegibilidade é a moldura; a avaliação territorial é o quadro. **Matriz cujas células dizem `INDETERMINADO` por falta de camada demonstra arquitetura, não valor.** Com as camadas ligadas, a mesma matriz vira demonstração.

Isso inverte a ordem do PLANO, e a inversão é deliberada.

#### Hipótese 1 — gratuito para o produtor, pago pelo frigorífico

O defeito, se formulada como *"vendo a análise dos dados dele"*: a relação produtor↔frigorífico é adversarial no preço. Produtor que descobre que o software gratuito alimenta o comprador desinstala. Somem-se LGPD (muito pecuarista é pessoa física) e sigilo comercial.

**A ADR-0042 já resolve.** O Titan transfere declarações verificáveis, não acesso — o produtor **autoriza** um dossiê sobre um lote específico, para um comprador específico, numa transação específica. Não é venda de dado: é o produtor usando a plataforma **contra** a assimetria. Mesma receita, incentivos alinhados em vez de opostos.

**O escopo é o que mata a hipótese.** Gestão de fazenda — financeiro, estoque, pastagem, máquinas — é mercado disputado, de margem baixa e escopo infinito; construí-lo de graça consome o time e dilui o diferenciado. O gancho do pequeno produtor **não é gestão, é obrigação**:

- **GTA** — obrigatória e dolorosa. Torná-la trivial constrói a linha do tempo **como efeito colateral**, e resolve com um único movimento a adoção do produtor **e** a lacuna (2) acima. É o melhor wedge identificado.
- **PNIB** — obrigatória e individual; é onde os prediais não competem.
- **Carência** — já implementada, e é dinheiro direto: lote barrado no abate é prejuízo.

O gratuito precisa ser estreito a ponto de quase não gerar suporte. **Cada tela a mais é uma ligação por semana pelo resto do projeto.**

#### Hipótese 2 — canal certo, pedido errado

Garantia de compra não existe nesse mercado: o preço é spot, negociado por arroba, e pedi-la encerra a reunião. A desconfiança do responsável estava calibrada — garantia prometida e não honrada é pior que nenhuma.

O que os frigoríficos **já fazem** serve igual: bonificação por arroba, prioridade na escala de abate, acesso a canal que paga mais. Então o pedido é outro: *reconheça o dossiê do Titan como suficiente na homologação de fornecedor, e faça-o qualificar para a bonificação que você já paga.* Risco baixo para eles; não se promete o que não se controla.

#### A síntese: um frigorífico, uma região, a base de fornecedores dele

Mercado de dois lados tem partida a frio. A saída é não tentar os dois lados ao mesmo tempo: **começar pela base de fornecedores de um único frigorífico** — ele já é obrigado a homologar aqueles produtores, já tem a lista, a dor e a alavanca.

Isso dá **densidade numa geografia** em vez de cobertura fina em todas, e densidade é o que faz a cadeia cria→recria→engorda fechar. **Mato Grosso do Sul** é a região indicada: adiantada na PNIB, e os três CAR validados no 17.2 são de lá.

**Preço por atestação** — por lote embarcado, por animal atestado — e não por assento: o lado do produtor pode ser gratuito com honestidade, a receita cresce com o volume verificado, e o frigorífico paga proporcional ao risco que transfere.

#### Pagador não considerado: crédito e seguro

Bancos já checam conformidade socioambiental para liberar crédito rural (há resolução do CMN restringindo financiamento a imóvel com embargo — **conferir o número antes de citar**). Precisam da mesma verificação, têm dinheiro e processo. Não é para agora, e é a razão para **não amarrar a arquitetura só ao frigorífico**.

#### Advertência sobre "dado como ativo"

O valor **não** está em revender o agregado: esse comprador quase não existe, e os que existem exigem escala de anos. Está na atestação no instante da transação. Agregado é opcionalidade, nunca plano.

#### O mercado não está vazio

Boi na Linha/Imaflora, Agrotools, Niceplanet, Safe Trace e as plataformas próprias de JBS, Marfrig e Minerva. **A vantagem do Titan não é chegar primeiro: é ser individual e auditável onde eles são prediais e recalculados.**

### NR-1 — Âncora temporal por documento de terceiro

**Problema.** O `occurred_at` de um evento capturado offline é **tempo alegado** pelo relógio do dispositivo. Quem controla o aparelho controla a alegação. Isso é grave especificamente na carência: ela é calculada como `applied_at + dias`, então antedatar uma aplicação encurta a carência efetiva e libera o animal antes da hora — resíduo na carne, exatamente o dano que o Marco 9 existe para impedir. A ADR-0021, princípio 4, já veda tratar relógio de dispositivo como prova temporal, e o PLANO lista o risco na sua tabela ("relógio local apresentado como prova temporal").

**Direção.** Todo evento offline já possui um **intervalo provável ancorado no servidor**, sem precisar confiar no dispositivo:

- limite superior: o instante em que o lote sincronizou;
- limite inferior: `DeviceClockReading.last_server_contact_at`, campo que já existe no domínio, reforçado por `monotonic_elapsed_ms` e `monotonic_continuity_id` — relógio civil que salta sem o cronômetro monotônico acompanhar é inconsistência aritmética, não opinião.

Documentos de terceiro estreitam o intervalo e acrescentam corroboração independente. A **nota fiscal do medicamento** dá limite inferior forte (não se aplica o que ainda não se comprou) e permite conferência cruzada do número do lote contra o `batch_number` já registrado. A **nota do serviço veterinário** corrobora presença profissional na data. Ambas são documentos de terceiro com autorização carimbada pela SEFAZ e chave verificável fora do Titan.

**Limite honesto:** nota prova aquisição, não aplicação. Eleva confiança sem produzir certeza — por isso o destino natural é `ConfidenceLevel` (Passo 5.2), e não um booleano. Enquanto a chave não for validada na fonte, o estado é `EvaluationOutcome.VALIDACAO_EXTERNA_PENDENTE`, hoje declarado no Core e **sem nenhum produtor** — este seria o primeiro.

**Consequência para a regra de elegibilidade:** o registro entra sempre (registro existente vale mais que registro ausente), mas um animal cuja carência repousa em hora não verificável não deve ser liberado com o mesmo peso de outro registrado online.

**Aplicação prevista para além de medicamento:** vacinação, serviços veterinários e demais manejos com nota.

**Pendência de decisão:** quem introduz cada informação — veterinário, produtor ou ambos. Ver NR-4.

### NR-2 — Alinhar ao GS1 EPCIS quando houver abate e produtos

**Contexto.** Abate e produtos não estão nos Marcos 8 a 10; o Marco 11 cita regras adicionais de recall. Quando entrarem, a cadeia deixa de ser linear: o abate é **fan-out** (um animal vira dezenas de cortes) e o processamento é **fan-in** (carne moída e linguiça misturam muitos animais num lote). A estrutura correta é **DAG, não árvore** — árvore pressupõe um pai, e isso quebra no primeiro produto misto. A genealogia animal também é fan-in.

**Direção.** O problema já está resolvido e padronizado internacionalmente. O **GS1 EPCIS** define `TransformationEvent` exatamente para esse caso, com listas de entrada e de saída; é o único tipo de evento que quebra a cadeia de lote e cria lote novo, e é irreversível. A regulação norte-americana (FSMA 204) usa o vocabulário de CTE e KDE.

**Recomendação:** quando o escopo chegar, o trabalho é **mapear o modelo do Titan para o EPCIS**, não desenhar um grafo próprio. Um sistema de auditoria que não troca dados com o sistema do frigorífico e do comprador vira ilha, e ilha não serve como prova para terceiros.

**Forma esperada:** o produto é entidade nova, com fluxo de eventos próprio, mais relação de origem apontando para a carcaça e daí para o animal. A linha do tempo do produto é o fluxo dele mais a travessia da origem — mesma forma que a timeline do animal já tem. `LivestockTimelineService` generaliza; não precisa ser reescrito. **Cópia da história para dentro do produto é o caminho errado:** cria N cópias do mesmo fato, e uma correção na origem passa a exigir propagação para N lugares.

**Fundação já existente:** `RecallService` faz travessia de grafo; as relações do Passo 7.1 são universais e temporais; o `reference_projection` do 7.2 indexa quem aponta para cada entidade. Rastreabilidade para trás (*tracking*) e para frente (*tracing*) são as duas direções da mesma travessia.

**Problema em aberto:** o que a linha do tempo de um lote de carne moída com dezenas de origens deve mostrar. Históricos completos de todas as origens é ilegível; provavelmente o certo é o fluxo próprio do produto mais os pontos de decisão de cada origem. Decisão para quando houver produto.

### NR-3 — O diferencial é a proveniência da decisão, não o grafo

O grafo de rastreabilidade é mesa posta: padronizado, com implementações maduras e concorrência estabelecida. O Titan não deve competir ali, e sim adotar o padrão.

O que é raro, e não está nos padrões de rastreabilidade, é **provar por que uma decisão foi tomada e permitir refazê-la**: política versionada, regra versionada, snapshot de fatos hasheável, avaliação explicável e dossiê reproduzível por terceiro sem acesso ao banco. EPCIS diz para onde as coisas foram; não diz por que algo foi liberado ou barrado.

**Consequência prática:** ao priorizar, passos que reforçam reprodutibilidade da decisão (dossiê, verificação externa, confiança temporal) valem mais que passos que ampliam cobertura de rastreio.

### NR-4 — Quem registra o fato: pendência de decisão

**Questão levantada em 24/07/2026 e ainda em aberto:** quem introduz cada informação — o veterinário, o produtor, ou ambos.

**Observação que estreita a questão:** o modelo de dupla participação **já existe** no fluxo farmacológico. A prescrição exige veterinário com status `DOCUMENTADO` ou `VERIFICADO_EM_FONTE` — é a autoridade dele; a aplicação registra o ator que executou — é o ato do produtor. São dois papéis, dois registros, duas autorias, já modelados.

Portanto a pergunta em aberto não é "quem registra", e sim **em que casos a prescrição deixa de ser opcional na aplicação** — hoje `prescription_id` é opcional em `TreatmentApplication`. Torná-la obrigatória para certas classes de produto é decisão de regra de negócio, com portão de aprovação, e afeta diretamente o peso probatório do registro.

Relacionado: `DecisionAuthorityProfile` e o fluxo de aprovações da ADR-0016 permanecem como pendência deliberada do Core.

### NR-5 — Autoria de regras pelo administrador da vertical

**Levantado em 24/07/2026. Precisa de solução, não apenas de registro.**

**O problema.** Regras dependem de lei, e lei muda. Hoje a única regra de negócio da vertical — a de carência — é construída em Python, por `build_eligibility_rule` em `livestock_application/eligibility.py`. Nenhum administrador a edita. Publicar uma norma nova exige alterar código, revisar, testar e implantar, o que é lento demais para acompanhar mudança regulatória e concentra em desenvolvedores uma decisão que é do domínio.

**A dificuldade real, que precisa ser enunciada antes de qualquer solução.** Regra escrita em tempo de execução por um humano precisa continuar **determinística e reproduzível**. Se o administrador puder escrever expressão livre, perde-se a garantia de que a mesma decisão refeita daqui a cinco anos produz o mesmo resultado — que é a tese inteira do produto. Uma regra editável e não reproduzível seria pior do que não ter regra editável.

**Segunda exigência, temporal.** Quando a lei muda, decisões antigas **não** podem ser reavaliadas pela regra nova: foram tomadas sob a norma vigente à época, e o dossiê precisa continuar reproduzível sob aquela versão. `Policy` e `Rule` já são versionadas, com `valid_from`, `valid_to`, `status` e `normative_source`, e o dossiê já copia as condições declarativas de cada regra — a fundação existe. O que falta é o comportamento ficar explícito quando a autoria sair das mãos do desenvolvedor.

**Há um caminho barato que já está estruturalmente pronto, e vale explorá-lo antes do caro.** `RuleCondition` **já é dado declarativo**, não código: `fact_type`, `payload_key`, `operator`, `expected_value`, `description`. Uma regra composta por essas primitivas é determinística por construção, já é versionada, já viaja inteira dentro do dossiê e já é reexecutável. Ou seja, **para regras que caibam nessas primitivas, o problema de execução está resolvido** — o que falta é apenas a *autoria*: interface, validação e fluxo de aprovação para o administrador compor condições, sem tocar em código.

Vale medir quanto da regulação real cabe nessas primitivas antes de construir qualquer coisa maior. A suspeita é que a maior parte caiba: "carência cumprida", "vacinação registrada no prazo", "veterinário habilitado" são todas comparações sobre fatos.

**O caminho caro, para o que não couber.** A **ADR-0036 já está aceita** e decide justamente isso: compilar regras normativas para bytecode Wasm imutável e versionado, executado em sandbox determinístico, recuperando na reavaliação o bytecode exato vigente na data do evento. Ela nomeia `WasmNormativePolicyEvaluator`, `PolicyExecutionSandbox` e `NormativeExecutionReceipt`. Está aceita e **não implementada**.

**Encaminhamento proposto:**

1. Levantar quais regras reais da pecuária são necessárias e classificar cada uma como "cabe nas primitivas declarativas" ou "não cabe".
2. Se a maioria couber, construir a autoria declarativa primeiro — é incomparavelmente mais barata que o sandbox e resolve o problema prático.
3. Reservar a implementação da ADR-0036 para o que sobrar, com evidência de que sobrou.
4. Em qualquer dos caminhos, exigir portão de aprovação para publicar regra: o plano já trata regra de negócio como categoria de aprovação obrigatória, e autoria por administrador não afrouxa isso.

Decidido em 24/07/2026: `VeterinaryPrescription` **não** integra a API mínima do Marco 10 — ver Passo 10.4. A pendência é de **regra de negócio**, não de API.

Relacionado: [ADR-0011] fontes normativas, vigência e reavaliação temporal; [ADR-0016] decisões explicáveis e revisão humana; NR-4, sobre quem registra cada fato.
