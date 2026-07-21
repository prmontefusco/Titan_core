# ADR 0015 — Proveniência, validação e níveis de confiança
**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan recebe declarações, Documents, medições, integrações, observações, dados de dispositivos e resultados derivados. Uma informação pode possuir bytes íntegros e ainda ser incorreta, desatualizada, não autorizada ou insuficiente para determinada Policy.

O Domain já reconhece Claim, Fact, Evidence, Source, Provenance, ConfidenceLevel, Validity e VerificationStatus. Esta ADR consolida sua semântica sem criar um modelo paralelo chamado EvidenceProvenance.

ADRs 0013 e 0014 exigem que classificação, finalidade, retenção e disposição acompanhem dados e derivados.

## Problema

Definir:

- como origem, captura, transformação e uso permanecem navegáveis;
- como validação, confiança, frescor, conflito e admissibilidade permanecem distintos;
- como preservar resultados históricos e consultar estado atual sem reescrita;
- como tratar fonte indisponível, resposta parcial e resultado desconhecido.

## Princípios

1. **Origem não é verdade:** Source, autoridade declarada, assinatura e oficialidade não comprovam verdade material.
2. **Validação é delimitada:** confirma somente campos, método, fonte, instante e finalidade declarados.
3. **Confiança é explicável:** não existe score universal nem promoção automática por tipo de Source.
4. **Histórico e atual são separados:** consulta posterior não reescreve Evidence, Evaluation ou Decision anterior.
5. **Incerteza permanece visível:** ausência, conflito e indisponibilidade nunca são convertidos em confirmação ou zero.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Booleano `verified` | Simplicidade | Apaga escopo, método, tempo, conflito e limitações |
| Source oficial como verdade | Decisão rápida | Autoridade, atualidade e correção ficam confundidas |
| Score universal de confiança | Ordenação fácil | Precisão falsa e pesos sem significado entre domínios |
| Provenance em texto livre | Flexibilidade | Não permite navegação, impacto ou validação automática |
| Grafo tipado e assessments versionadas | Explicação e auditoria | Mais contratos, estados e reconciliação |

## Decisão

Manter Provenance como conceito canônico e representá-la por relações tipadas, imutáveis e navegáveis entre objetos versionados.

Validação produz assessment própria e nunca altera silenciosamente Claim, Fact, Evidence ou dado de origem. Admissibilidade em Evaluation é decisão de Policy separada.

Estados e códigos apresentados pelo Titan serão estáveis e em português. Detalhes de provider, transporte, OCR, endpoint e payload externo permanecem na Infrastructure.

Os novos conceitos são candidatos arquiteturais e dependem de aprovação no `DOMAIN.md`.

## EvidenceOriginType

Tipo controlado da forma pela qual a informação entrou ou foi produzida:

- `DECLARACAO_DE_USUARIO`;
- `DOCUMENTO_RECEBIDO`;
- `EXTRACAO_DE_DOCUMENTO`;
- `FONTE_OFICIAL`;
- `TERCEIRO_AUTORIZADO`;
- `CAPTURA_DE_DISPOSITIVO`;
- `OBSERVACAO`;
- `CONFIRMACAO_MANUAL`;
- `RESULTADO_DERIVADO`.

O tipo descreve origem, não qualidade, autoridade ou confiança. Perfis podem acrescentar valores versionados sem alterar o significado dos existentes.

## SourceProfile

Perfil versionado de uma Source para finalidade delimitada.

Preserva identidade declarada e verificada separadamente, Organization responsável, tipos de dado, jurisdição, autoridade alegada, contratos, métodos de validação, autenticação técnica referenciada, disponibilidade esperada, frescor, limitações, validade e Evidence.

SourceProfile não torna a Source confiável universalmente. Mudança de contrato, autoridade ou método cria nova versão.

## SourceSnapshot

Estado imutável observado de uma Source em um instante delimitado.

Preserva Source e SourceProfile, instantes solicitado, observado e registrado, contrato e versão, ValidationScope, request e response Digests, referência opaca ao material bruto permitido, atualização declarada, resultado técnico e limitações.

SourceSnapshot comprova a observação sustentada por Evidence; não comprova correção, completude, autoridade ou verdade material da Source.

## ProvenanceLink

Relação imutável e tipada entre objeto de origem e objeto produzido, capturado, transformado, validado ou utilizado.

Preserva source object e versão, derived object e versão, relação, EvidenceOriginType, Source, Actor, Channel, Device, instante alegado, capturado e registrado, transformação, método e versão, DataContract, DataClassification, RetentionAssignment, Digest, correlação e limitações.

Relações iniciais: `DECLARADO_POR`, `OBSERVADO_POR`, `CAPTURADO_DE`, `IMPORTADO_DE`, `EXTRAIDO_DE`, `DERIVADO_DE`, `VALIDADO_CONTRA`, `CORROBORADO_POR`, `CONTESTADO_POR`, `UTILIZADO_EM`, `SUBSTITUIDO_POR`.

ProvenanceLink não transfere ownership, não concede Visibility e não prova causalidade ou verdade.

## Grafo de Provenance

O grafo é navegável nos dois sentidos e preserva versões. Deve responder, conforme Authorization:

- de onde veio uma afirmação ou valor;
- quem declarou, capturou, importou, transformou ou validou;
- quais métodos, contratos e versões foram usados;
- quais Evaluations, Decisions, Dossiers, Publications e derivados utilizaram o objeto;
- quais caminhos estão ausentes, conflitantes ou inacessíveis.

Ciclo, duplicação ou referência ausente não são ocultados. Resultado incompleto é marcado como tal.

## ProvenancePath

Resultado reconstruível e autorizável de navegação por ProvenanceLinks entre origem e destino.

Preserva links e versões, direção, instante da consulta, filtros, Authorization aplicada, lacunas, ciclos, objetos inacessíveis, completude e limitações. Não se torna fonte autoritativa paralela ao grafo.

Quando necessário para auditoria, o caminho é preservado como snapshot imutável do resultado conhecido naquele instante. Mudança posterior do grafo não reescreve o snapshot.

## ValidationScope

Escopo imutável de uma validação: `CAMPO`, `OBJETO`, `COLECAO`, `RELACAO` ou `DOCUMENTO`.

Delimita objetos e versões, campos incluídos e excluídos, período, relações e critérios de seleção. Alteração cria nova ValidationRequest; resultado nunca é ampliado além do escopo.

## ValidationRequest

Solicitação imutável de validação delimitada por ValidationScope, SourceProfile, método, finalidade, instante de referência, FreshnessProfile, OrganizationContext, ProcessingContext, DataContract, correlação e IdempotencyKey.

Cliente pode solicitar finalidade e campos, mas o servidor resolve perfil, escopo autorizado e método. ValidationRequest não concede acesso à Source ou ao objeto.

## ValidationAttempt

Tentativa operacional correlacionada à ValidationRequest.

Preserva executor, início, término, contrato do provider, request Digest, response Digest, referência opaca ao material bruto permitido, resultado técnico, retry, limitações e resultado desconhecido.

Estados técnicos iniciais:

- `PENDENTE`;
- `CONCLUIDA`;
- `FONTE_INDISPONIVEL`;
- `RESULTADO_DESCONHECIDO`;
- `NAO_SUPORTADA`;
- `FALHA_TRANSITORIA`;
- `FALHA_PERMANENTE`.

Falha de comunicação após envio não é sucesso nem falha confirmada. Retry preserva identidade lógica quando o provider permitir ou cria tentativa correlacionada sem apagar a anterior.

## ValidationAssessment

Avaliação imutável do que uma ou mais tentativas e Evidences permitem concluir.

Preserva objeto e versão, campos solicitados, valores observados quando autorizados, campos confirmados, divergentes, ausentes e não avaliados, método, SourceProfile, Evidences, instante efetivo, freshness, ConfidenceAssessment, VerificationStatus, limitações, assessor e versão do motor.

Resultado sobre um campo não se estende aos demais. Estrutura válida, Signature verificada ou resposta autenticada não confirma conteúdo não avaliado.

## VerificationStatus

Estado da verificação de Claim, Fact, Evidence ou campo no instante avaliado:

- `NAO_VERIFICADO`;
- `VERIFICACAO_PENDENTE`;
- `VERIFICADO`;
- `CONTESTADO`;
- `CONFLITANTE`;
- `EXPIRADO`;
- `INVALIDO`;
- `REVOGADO`.

`FONTE_INDISPONIVEL` e `RESULTADO_DESCONHECIDO` pertencem à tentativa, não provam estado do conteúdo. `REJEITADO_POR_POLITICA` pertence à admissibilidade, não à verificação.

## ConfidenceAssessment

Avaliação explicável da confiança disponível para objeto, finalidade e instante delimitados.

Preserva dimensões consideradas, Evidence, método, SourceProfile, cobertura, corroborabilidade, atualidade, incerteza, conflitos, limitações e ConfidenceLevel resultante.

Capabilities iniciais de ConfidenceLevel:

- `AUTODECLARADA`;
- `EVIDENCIA_ANEXADA`;
- `ASSINATURA_VERIFICADA`;
- `FONTE_CONFIRMADA`;
- `CORROBORADA`.

Esses valores descrevem suporte disponível e não formam necessariamente escala ordinal. `CONFLITANTE`, `INDISPONIVEL` e `EXPIRADO` são condições, não níveis de confiança.

Policy ou perfil define dimensões, pesos e limites quando necessários. O Core não calcula score universal.

ConfidenceAssessment não representa probabilidade de verdade, precisão estatística, chance de fraude ou certeza material. Quantificação de probabilidade ou incerteza pertence a UncertaintyStatement ou método específico.

## FreshnessProfile

Perfil versionado que define exigência de atualidade por tipo de informação, finalidade, Source, jurisdição e Policy.

Preserva instante de referência, tolerância, evento de atualização, requisitos de relógio, comportamento para fonte indisponível, aprovação e limitações. O Core não fixa janela temporal universal.

## FreshnessAssessment

Avaliação imutável da atualidade do material para finalidade e instante definidos.

Registra Source, instante da consulta, instante de atualização declarado, validade, tolerância da Policy, clock confidence, resultado e limitações.

“Não revogado” significa somente que nenhuma revogação aplicável foi identificada nas fontes e instantes declarados. Fonte indisponível não renova freshness anterior.

## EvidenceAdmissibilityAssessment

Decisão imutável de Policy sobre a possibilidade de usar Evidence ou ValidationAssessment em Evaluation específica.

Resultados iniciais: `ACEITA`, `ACEITA_COM_RESTRICOES`, `REVISAO_NECESSARIA`, `REJEITADA_POR_POLITICA`, `INDETERMINADA`.

Preserva Policy e versão, finalidade, Evidence, ValidationAssessment, confiança, freshness, conflitos, limitações, códigos de razão e Actor ou motor. Não altera VerificationStatus nem declara verdade material.

ReasonCodes são estáveis, versionados e apresentados em português. Cada código referencia Rules, Evidences e limitações aplicáveis; mensagem humana é separada e pode ser traduzida sem alterar o resultado.

Uma Evidence não verificada pode ser admissível para captura ou triagem e insuficiente para Publication, certificação ou Decision sensível.

## Conflitos

Valores divergentes permanecem como Claims ou Evidences distintas ligadas por Provenance. O Titan não escolhe silenciosamente “último valor”, Source mais oficial ou maior confiança.

ConflictAssessment registra objetos, campos, versões, Sources, Evidences, temporalidade, materialidade, hipóteses, resolução, Actor e limitações.

ConflictMaterialityAssessment avalia impacto do conflito para finalidade, Policy, Evaluation ou Decision delimitada. Preserva diferenças, objetos dependentes, thresholds, versão, impacto potencial, necessidade de revisão, Evidence e limitações.

Materialidade não é severidade universal. Diferença pequena pode alterar Rule decisiva; diferença grande pode ser irrelevante para outro escopo.

Resultado pode exigir nova captura, confirmação manual, Source adicional, Correction, revisão ou decisão humana. Resolução não apaga o conflito histórico.

## Estado histórico e estado atual

ValidationAssessment histórica preserva material, perfil, método, relógio e conhecimento disponíveis no instante original.

CurrentValidationAssessment consulta fontes atuais e cria novo objeto correlacionado. Não substitui assessment anterior nem projeta informação posterior sobre Decision histórica.

Comparação explica:

- o que era conhecido e validado no instante original;
- o que mudou na Source, Evidence, método ou estado;
- quais objetos estão potencialmente afetados;
- se nova Evaluation é autorizada ou necessária.

## Dados brutos, privacidade e retenção

Payload externo bruto é Artifact ou Document referenciado de forma opaca quando sua preservação for necessária e autorizada. Não integra automaticamente Event, log, Outbox ou contrato público.

DataClassification, ProcessingActivity, DataContract, RetentionAssignment e LegalHold acompanham requests, responses, ProvenanceLinks, Evidences, assessments, caches, quarentena e derivados.

Minimização ocorre antes da chamada externa e antes da persistência. Logs preservam correlação, código e resultado seguro, não credencial, payload, atributo pessoal ou resposta integral.

Disposição de payload não reescreve Provenance. Permanece envelope mínimo não reversível conforme ADR 0014.

## Offline

Operação offline registra Source, Actor, Device, Channel, instantes, EvidenceOriginType, DataClassification, contrato e limitações. Horário do dispositivo não é prova temporal independente.

Sem fonte remota, o estado permanece `NAO_VERIFICADO` ou `VERIFICACAO_PENDENTE`. Sincronização cria ValidationRequest e revalida identidade, Authorization, finalidade, Policy, contrato, freshness e conflitos.

Falha de validação não elimina a OfflineOperation original.

## Fronteiras arquiteturais

Domain define objetos, estados, relações e invariantes. Não conhece HTTP, endpoint, JSON externo, OCR, driver, broker ou banco.

Application resolve perfil, autorização, contrato e Policy; coordena requests, assessments, admissibilidade, conflito e impacto.

Infrastructure implementa adapters, autenticação técnica, transporte, retry, armazenamento de material bruto e coleta de Evidence operacional. Não decide verdade, confiança, admissibilidade ou efeito de negócio.

Presentation mostra origem, escopo, estado, freshness, limitações e razões sem revelar campos não autorizados.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Provenance navegável; validação por campo; histórico preservado; confiança explicável; adapters substituíveis |
| Negativas | Mais objetos e versões; armazenamento de lineage; reconciliação e autorização por caminho |

## Riscos e controles

| Risco | Controle |
|---|---|
| Source oficial tratada como verdade | Dimensões independentes e assessment delimitada |
| Indisponibilidade virar rejeição | Estado técnico separado de admissibilidade |
| Score ocultar incerteza | ConfidenceAssessment explicável sem score universal |
| Resposta atual reescrever história | Assessments correlacionadas e imutáveis |
| Payload externo vazar | Referência opaca, minimização e DataContract |
| Lineage conceder acesso | Authorization aplicada a cada objeto e caminho |

## Verificação automatizada

Testes futuros devem cobrir:

- Source oficial, Signature ou Digest promovendo conteúdo a verdade;
- campo não consultado apresentado como confirmado;
- SourceSnapshot apresentado como verdade ou estado completo da Source;
- ValidationScope ampliado entre request, assessment e admissibilidade;
- ProvenancePath incompleto apresentado como grafo completo;
- fonte indisponível alterando conteúdo para inválido;
- resultado desconhecido tratado como ausência de resposta;
- Evidence não verificada usada fora da admissibilidade da Policy;
- ConfidenceLevel usado como score ordinal universal;
- ConfidenceAssessment apresentado como probabilidade de verdade;
- FreshnessAssessment sem FreshnessProfile aplicável;
- CurrentValidationAssessment sobrescrevendo resultado histórico;
- conflito resolvido por “último valor” sem assessment;
- materialidade de conflito reutilizada fora da finalidade avaliada;
- ProvenanceLink ausente, cíclico, inacessível ou com versão incorreta;
- payload, credencial ou atributo pessoal em log, mensagem ou contrato público;
- offline apresentado como remotamente verificado.

## Critérios de aceitação

A ADR pode ser aceita quando:

- Provenance permanecer conceito canônico e navegável nos dois sentidos;
- SourceSnapshot preservar o observado sem declarar verdade material;
- ValidationScope delimitar campos, objetos, coleções, relações ou Documents sem ampliação implícita;
- ProvenancePath ser reconstruível, autorizável e explicitamente incompleto quando aplicável;
- Source, Actor, Channel, Device e EvidenceOriginType forem distintos;
- ValidationAttempt, ValidationAssessment, VerificationStatus, confiança, freshness e admissibilidade não forem confundidos;
- estados e códigos públicos forem estáveis e em português;
- validação for por campo, método, fonte, finalidade e instante;
- ConfidenceAssessment não for interpretada como probabilidade e freshness usar perfil versionado;
- conflito possuir materialidade contextual e não severidade universal;
- admissibilidade produzir ReasonCodes estáveis separados da mensagem humana;
- indisponibilidade, conflito, parcialidade e resultado desconhecido permanecerem explícitos;
- histórico não for reescrito por consulta ou conhecimento posterior;
- Policy decidir admissibilidade sem declarar verdade material;
- classificação, retenção, privacidade, offline e Authorization forem preservados;
- provider, API, OCR, schema, migration, fila e worker permanecerem fora da decisão.

## O que esta ADR não decide

Esta ADR não escolhe:

- SISBOV, GTA, MAPA ou qualquer Source concreta;
- endpoint, provider, credencial, contrato HTTP, OCR ou formato externo;
- banco, tabela, índice, fila, worker, cache ou scheduler;
- pesos universais, verdade material, decisão jurídica ou comercial;
- fluxo completo de correção, contestação humana ou integração externa.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída. Depois da adoção, nova decisão preserva SourceProfiles, SourceSnapshots, ProvenanceLinks, ProvenancePaths, scopes, requests, attempts, assessments, conflitos, perfis de freshness, códigos e relatórios históricos.

Reversão não promove dado não verificado, apaga conflito, reduz classificação ou reescreve Evaluation e Decision anteriores.
