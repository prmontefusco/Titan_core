# ADR 0023 — Resposta a incidentes e preservação forense
**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan preservará evidências, decisões, dados pessoais, documentos, chaves, integrações e trilhas de auditoria para cadeias reguladas. Um evento adverso pode afetar confidencialidade, integridade, disponibilidade, autenticidade, privacidade ou capacidade de comprovação sem que sua natureza e extensão sejam imediatamente conhecidas.

As ADRs anteriores já definem Audit, LegalHold, ImpactAssessment, DeviceTrustAssessment, comprometimento de chaves, quarentena, retenção e localização. Falta um processo canônico que separe sinal, avaliação, incidente, contenção, investigação, comunicação, recuperação e encerramento.

A Resolução CD/ANPD nº 15/2024 disciplina a comunicação de incidentes de segurança com dados pessoais no Brasil. O NIST SP 800-61 Rev. 3 integra resposta a incidentes à gestão contínua de riscos. O Titan registra perfis, avaliações e evidências aplicáveis, mas não conclui automaticamente obrigação jurídica, atribuição ou admissibilidade forense.

## Problema

Definir:

- quando um sinal se torna caso investigado ou incidente confirmado;
- como classificar severidade, materialidade, escopo e confiança;
- quem pode conter, preservar, comunicar, recuperar e encerrar;
- como manter cadeia de custódia sem ampliar acesso;
- como impedir que contenção destrua Evidence ou histórico;
- como avaliar dados, Decisions, Publications e organizações afetadas;
- como comunicar autoridades, titulares, clientes e parceiros;
- como recuperar o serviço sem reintroduzir comprometimento;
- como aprender e revisar controles sem reescrever o incidente.

## Princípios

1. **Sinal não é incidente:** alerta ou anomalia inicia avaliação, não conclusão.
2. **Incidente não prova autoria:** correlação, causa, culpa, fraude e responsabilidade permanecem assessments distintas.
3. **Preservar antes de alterar:** ações urgentes mantêm Evidence proporcional sempre que possível.
4. **Contenção não é erradicação:** bloquear efeito não comprova remoção da causa.
5. **LegalHold não concede acesso:** preservação e Authorization permanecem separadas.
6. **Desconhecido permanece visível:** ausência de artefato ou caminho não prova ausência de impacto.
7. **Comunicação é decisão autorizada:** obrigação, público, conteúdo, prazo e canal são avaliados.
8. **Recuperação não encerra o caso:** serviço disponível não comprova integridade, reconciliação ou conclusão.
9. **Histórico é imutável:** nova Evidence cria nova assessment, não reescreve o conhecimento anterior.

## Invariantes adicionais

- obrigação de comunicar é avaliada separadamente por audiência, jurisdição, base e contrato;
- `COMUNICACAO_NAO_EXIGIDA_NO_ESCOPO` não significa ausência universal de obrigação;
- prazo calculado vale somente para trigger, calendário, timezone, norma, versão e fatos declarados;
- comunicação preliminar não é relato completo e declara limitações materiais conhecidas;
- correção ou complemento não substitui historicamente mensagem enviada;
- declaração de provider é Evidence externa, não conclusão sobre o escopo do Titan;
- restore técnico não restaura automaticamente classificação, Authorization, Purpose ou direito de uso;
- disponibilidade restaurada não comprova integridade, confidencialidade ou completude;
- encerramento não elimina riscos residuais, desconhecidos ou possibilidade de reabertura;
- nova Evidence cria conhecimento prospectivo e não reescreve o snapshot anterior.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Tratar alertas como incidentes | Resposta rápida | Excesso, ruído e conclusões falsas |
| Processo externo sem modelo no Titan | Ferramentas especializadas | Perde correlação com Evidence e Decisions |
| Automação total de contenção | Baixa latência | Pode destruir prova ou ampliar indisponibilidade |
| Caso versionado com decisões separadas | Explicável e auditável | Mais estados, autoridade e reconciliação |

## Decisão

Adotar fluxo versionado:

`IncidentSignal → IncidentTriage → IncidentCase → IncidentAssessment → ResponseDecision → ResponseAction → RecoveryAssessment → IncidentClosure`

ForensicCollection, ChainOfCustody, LegalHold, ImpactAssessment e CommunicationAssessment sustentam o fluxo sem substituir suas etapas.

Os conceitos são candidatos arquiteturais e somente entram no `DOMAIN.md` após aprovação.

## IncidentSignal

Observação potencialmente relevante de segurança ou privacidade.

Preserva Source, tipo, instante observado e recebido, objeto ou escopo seguro, correlação, DetectionRule e versão, confidence operacional, Evidence e limitações. Sinal pode vir de auditoria, usuário, provider, Device, integração, threat intelligence ou controle manual.

Duplicação ou correlação não apaga sinais originais. Ausência de sinal não comprova ausência de incidente.

## IncidentTriage

Assessment imutável que decide se o sinal será descartado justificadamente, monitorado, correlacionado ou promovido a IncidentCase.

Resultados iniciais: `DESCARTADO_COM_JUSTIFICATIVA`, `MONITORAMENTO`, `CORRELACIONADO`, `CASO_ABERTO`, `INDETERMINADO`.

Preserva sinais, escopo inicial, classificação, prioridade, assessor, ReasonCodes, Evidence, conflitos e limitações. Descartar não elimina sinais nem impede reabertura por nova Evidence.

## IncidentCase

Agregado de coordenação do incidente potencial ou confirmado.

Preserva CaseId, Organizations e papéis, commander, equipe, abertura, status, escopo alegado, DataClassifications, ativos, Signals, Evidences, decisões, ações, comunicações, LegalHolds, impactos, custos, limitações e timeline.

Estados iniciais: `ABERTO`, `EM_TRIAGEM`, `EM_CONTENCAO`, `EM_INVESTIGACAO`, `EM_RECUPERACAO`, `EM_MONITORAMENTO`, `ENCERRADO`, `REABERTO`.

Estado coordena trabalho e não declara sozinho causa, severidade, notificação ou resolução.

## IncidentKnowledgeState

Snapshot imutável do conhecimento disponível sobre IncidentCase em um instante. Preserva fatos confirmados, hipóteses, itens descartados, desconhecidos, escopo, impacto, causa, dados e titulares alegados, autoria não confirmada, obrigações avaliadas, recuperação, Sources, Evidence, confiança, versão e limitações.

ResponseDecision, CommunicationAssessment, RecoveryAssessment e IncidentClosure referenciam o snapshot utilizado. Novo conhecimento cria snapshot correlacionado; não transforma hipótese antiga em fato histórico.

## IncidentAssessment

Avaliação imutável do incidente para escopo, snapshot e instante declarados.

Preserva propriedades afetadas, vetores possíveis, ativos, dados e titulares potencialmente envolvidos, Organizations, jurisdições, período, exposição, confiança, materialidade, impacto, causa conhecida ou hipóteses, Evidence, lacunas e limitações.

Resultados distinguem `NAO_CONFIRMADO`, `SUSPEITO`, `CONFIRMADO`, `INDETERMINADO`. Confirmação pode ser parcial por propriedade ou escopo.

Severidade é produzida por IncidentSeverityProfile versionado e não por enum universal isolado. Considera impacto técnico, operacional, pessoal, regulatório, contratual, cadeia, alcance e reversibilidade sem somá-los silenciosamente.

## ResponseDecision

Decisão autorizada que aprova, rejeita ou condiciona ações de contenção, preservação, investigação, comunicação, recuperação ou monitoramento.

Preserva autoridade, IncidentAssessment, finalidade, escopo, prioridade, riscos da ação, Evidence a preservar, dependências, prazo, dupla aprovação quando exigida e rollback seguro.

Automação pode executar playbook previamente aprovado dentro de limites. Bloqueio de principal, Device, chave ou integração não invalida automaticamente objetos históricos nem prova comprometimento.

## ResponseAction

Execução append-only de ResponseDecision.

Estados: `PENDENTE`, `EM_EXECUCAO`, `CONCLUIDA`, `PARCIAL`, `FALHOU`, `RESULTADO_DESCONHECIDO`, `CANCELADA`.

Preserva executor, ServiceIdentity, instantes, alvos, mudanças, tentativa, idempotência, resultado, receipts, Evidence e limitações. Resultado desconhecido exige reconciliação; retry não repete efeito sem garantia.

Aceitação por provider, broker ou endpoint não comprova efeito concluído. Ação parcial não é contenção completa.

## Contenção, erradicação e isolamento

O Titan distingue:

- `Containment`: limita propagação ou efeito;
- `Isolation`: separa ativo ou fluxo;
- `Eradication`: remove causa identificada;
- `Mitigation`: reduz risco ou impacto;
- `Recovery`: restaura capacidade controlada.

Cada operação possui decisão, Evidence, escopo e resultado próprios. Quarentena preserva classificação, retenção, LegalHold e acesso mínimo.

Break-glass é temporal, restrito, justificado e auditado. Não remove LegalHold, não permite acesso universal e não autoriza alterar Evidence.

## ForensicCollection

Coleta imutável e delimitada de material para investigação.

Preserva autorização, collector, Source, sistema e estado, método e versão, instante, timezone, TimeConfidence, escopo, filtros, ordem de aquisição, Digests, cópia de trabalho, original preservado, ferramentas, erros, redactions, classificação, retenção e limitações.

Coleta proporcional não presume captura total do sistema. Falta de autorização, indisponibilidade, volatilidade ou lacuna fica explícita.

## ChainOfCustody

Sequência append-only de custódia de ForensicArtifact.

Cada ChainOfCustodyEntry registra Artifact e Digest, origem, custodiante anterior e novo, propósito, ação, local, instantes, embalagem ou proteção lógica, receipt, autorização e Evidence.

Digest demonstra consistência dos bytes segundo algoritmo e material disponível; não prova origem, completude, licitude, autoria ou admissibilidade judicial. Lacuna de custódia não é ocultada e produz assessment próprio.

Cópia de análise é distinguida do original. Transformação, extração, normalização, parsing ou redaction gera Artifact derivado e ProvenanceLink.

## Preservação e LegalHold

IncidentPreservationScope delimita objetos, sistemas, períodos, Organizations, categorias, derivados e exclusões.

LegalHold pode ser aplicado ao escopo por autoridade competente. Preserva contra disposição, mas não amplia Visibility, Purpose ou Permission. Conteúdo pessoal não necessário continua minimizado e protegido.

Snapshot, backup ou export forense não se torna cópia livre de retenção ou localização. Disposition posterior exige liberação do hold, avaliação e reconciliação.

## Impacto e objetos dependentes

IncidentImpactTrigger inicia ImpactAssessment conforme ADR 0017 para localizar dados, Events, Evidences, Decisions, Dossiers, Publications, grants, Signatures, checkpoints, integrações e recalls potencialmente afetados.

Encontrar dependência não invalida o objeto. Ausência de caminho não prova ausência de impacto quando inventário, Provenance, Authorization ou coleta forem incompletos.

Comprometimento de chave segue ADR 0008 e registra janela de exposição e confiança. Suspensão interna de principal, Membership, ServiceIdentity ou Device bloqueia novas operações mesmo que credencial externa permaneça válida.

## CommunicationAssessment

Assessment imutável sobre necessidade, destinatários, conteúdo, canal e prazo de comunicação.

Preserva IncidentAssessment, controlador e operadores alegados, titulares, autoridades, clientes, seguradoras ou parceiros, jurisdições, NormativeBases, contratos, risco ou dano, dados envolvidos, informações disponíveis, prazos calculados, aprovações, Evidence e limitações.

Resultados: `COMUNICACAO_NAO_EXIGIDA_NO_ESCOPO`, `COMUNICACAO_EXIGIDA`, `COMUNICACAO_VOLUNTARIA`, `REVISAO_JURIDICA_NECESSARIA`, `INDETERMINADA`.

O Core não fixa prazo universal. CommunicationProfile versionado resolve fonte normativa, calendário, timezone, trigger, destinatário, conteúdo mínimo, comunicação preliminar ou complementar e atualização.

Cada audiência e base recebe resultado próprio. O cálculo preserva trigger, regra, calendário, timezone, NormativeBasis e versão; detecção não substitui automaticamente o evento inicial definido pelo perfil.

## IncidentCommunication

Registro imutável de comunicação preparada, aprovada, enviada, aceita pelo canal, entregue quando comprovável, corrigida ou complementada.

Preserva audiência, versão, idioma, conteúdo ou referência protegida, redactions, approvers, canal, instantes, receipts, correlação e limitações. Envio não prova leitura, compreensão ou efeito jurídico.

Comunicação não revela segredo, investigação ativa, terceiro ou técnica defensiva além do escopo autorizado. Nova informação produz complemento ou correção; não reescreve a mensagem histórica.

Tipos correlacionados incluem `PRELIMINAR`, `COMPLEMENTAR` e `CORRETIVA`. Comunicação posterior referencia as anteriores e explica o que foi acrescentado ou corrigido.

## CommunicationDeliveryAssessment

Assessment imutável das Evidences de entrega para IncidentCommunication e destinatário delimitados.

Resultados: `ENTREGA_COMPROVADA_NO_CANAL`, `ACEITACAO_PELO_CANAL`, `ENTREGA_PROVAVEL`, `ENTREGA_INDETERMINADA`, `FALHA_CONFIRMADA`. Preserva canal, tentativa, receipts, callbacks, instante, correlação e limitações. Aceitação técnica não comprova recepção humana, leitura, compreensão ou efeito jurídico.

## Terceiros e cadeia

Incidente de provider, subprocessador ou Organization parceira cria Source e Evidence próprias. Declaração externa não é aceita como escopo completo sem assessment.

DataContract e contrato operacional definem contatos, cooperação, preservação, prazos, dados mínimos e responsabilidades alegadas. O Titan não infere controlador, operador, culpa ou obrigação apenas de ownership ou hospedagem.

## RecoveryAssessment

Avaliação imutável da prontidão para restaurar serviço, dados ou integração.

Preserva baseline confiável, backups, testes de restore, patches, secrets e chaves rotacionados, identidades, configurações, integridade, reconciliações, monitoramento reforçado, riscos residuais, rollback e aprovação.

Restore não retorna dados eliminados, bloqueados ou incompatíveis ao uso ordinário. LegalHolds, DataLocationAssignments, RetentionAssignments e restrições são reaplicados antes da liberação.

Recuperação parcial ou sob limitação permanece explícita. Disponibilidade não comprova integridade ou confidencialidade.

Resultados: `APTA_PARA_RECUPERACAO`, `APTA_COM_RESTRICOES`, `RECUPERACAO_PARCIAL`, `NAO_APTA`, `INDETERMINADA`. Aceitação de risco residual exige Actor com autoridade e decisão própria.

## IncidentClosure e revisão

IncidentClosure exige autoridade e reconcilia ações, comunicações, holds, impactos, recuperação, lacunas e riscos residuais. Encerramento administrativo não declara inexistência de impacto futuro.

PostIncidentReview registra timeline, hipóteses confirmadas e descartadas, causa quando conhecida, controles, eficácia, gaps, métricas, decisões, melhorias, owners e prazos. Lições não alteram assessments históricas.

Nova Evidence material pode reabrir o caso com relação explícita à versão encerrada.

Motivos: `REABERTURA_POR_NOVA_EVIDENCIA`, `REABERTURA_POR_ESCOPO_AMPLIADO`, `REABERTURA_POR_FALHA_DE_RECUPERACAO`, `REABERTURA_POR_COMUNICACAO_CORRETIVA`, `REABERTURA_POR_IMPACTO_TARDIO`, `REABERTURA_POR_RECORRENCIA`.

Reabertura cria nova fase ou versão relacionada e não apaga IncidentClosure anterior.

## Melhorias pós-incidente

PostIncidentReview pode produzir ImprovementRecommendation com problema, Evidence, benefício, risco, prioridade e owner proposto.

Alteração exige ImprovementDecision por autoridade competente e, quando aprovada, ActionPlan com escopo, responsável, dependências, prazo, validação e rollback. A equipe de resposta não altera diretamente Policy, retenção, configuração, Authorization, arquitetura ou fornecedor apenas por registrar recomendação.

## Fronteiras arquiteturais

Domain define sinais, casos, knowledge states, assessments, decisões, ações, custódia, comunicação, melhorias, recuperação e encerramento; não conhece SIEM, EDR, SOAR, ticketing, ferramenta forense ou canal regulatório concreto.

Application coordena autoridade, playbooks, holds, impacto, comunicação e recuperação. Infrastructure coleta sinais, executa ações aprovadas, preserva material, integra ferramentas e produz Evidence operacional. Presentation aplica redaction e Need-to-Know.

## Testabilidade

Testes futuros devem cobrir:

- alerta promovido automaticamente a incidente confirmado;
- ausência de log apresentada como ausência de impacto;
- severidade calculada sem perfil ou cobertura;
- contenção apagando Evidence ou sendo apresentada como erradicação;
- LegalHold ampliando acesso;
- coleta sem autorização, Digest, ferramenta ou TimeConfidence;
- transformação sobrescrevendo Artifact original;
- lacuna de custódia ocultada;
- chain of custody apresentada como admissibilidade jurídica;
- ação aceita pelo provider apresentada como concluída;
- retry duplicando bloqueio, revogação ou comunicação;
- resultado desconhecido sem reconciliação;
- dependência marcada automaticamente inválida;
- atribuição, fraude ou culpa inferida de correlação;
- prazo universal ignorando perfil, timezone ou norma específica;
- não comunicação para uma audiência aplicada a todas;
- prazo calculado pelo trigger ou timezone incorreto;
- comunicação preliminar apresentada como completa;
- complemento sem referência ou correção ocultando erro anterior;
- comunicação enviada apresentada como lida;
- receipt do canal apresentado como leitura humana;
- mensagem histórica reescrita por complemento;
- restore reintroduzindo dado eliminado ou região incompatível;
- restore reativando grant, Purpose ou direito de uso;
- baseline íntegra contendo comprometimento anterior;
- recuperação disponível apresentada como íntegra;
- recuperação parcial apresentada como plena;
- risco residual aceito sem autoridade;
- caso encerrado com ações ou riscos não reconciliados;
- encerramento removendo LegalHold automaticamente;
- recomendação alterando Policy sem ImprovementDecision;
- nova Evidence sem reabertura correlacionada;
- nova Evidence modificando IncidentKnowledgeState histórico.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Resposta explicável; custódia auditável; comunicação versionada; recuperação segura |
| Negativas | Mais perfis e autoridade; armazenamento sensível; exercícios e reconciliação contínuos |

## Critérios de aceitação

A ADR pode ser aceita quando:

- sinal, triage, caso e incidente confirmado forem distintos;
- severidade, causa, autoria, culpa e obrigação de comunicar não forem inferidas automaticamente;
- contenção, isolamento, erradicação, mitigação e recuperação permanecerem separados;
- Evidence original, derivados e cadeia de custódia forem navegáveis;
- LegalHold preservar sem conceder acesso;
- ações tiverem decisão, autoridade, idempotência e resultado próprios;
- impacto localizar dependentes sem invalidá-los automaticamente;
- comunicação usar assessment e perfil versionados, sem prazo universal no Core;
- recuperação reaplicar retenção, localização e bloqueios;
- encerramento exigir reconciliação e permitir reabertura;
- knowledge states preservarem o que era conhecido por decisão;
- entrega técnica não ser confundida com leitura ou compreensão;
- melhoria exigir recomendação, decisão e plano próprios;
- ferramentas e fornecedores permanecerem fora do Domain.

## Referências

- ANPD, Resolução CD/ANPD nº 15, de 24 de abril de 2024, Regulamento de Comunicação de Incidente de Segurança: <https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd>.
- ANPD, notícia oficial de aprovação do regulamento: <https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-aprova-o-regulamento-de-comunicacao-de-incidente-de-seguranca>.
- ANPD, canal e orientações para comunicação de incidente: <https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/comunicado-de-incidente-de-seguranca-cis>.
- NIST SP 800-61 Rev. 3, abril de 2025: <https://csrc.nist.gov/pubs/sp/800/61/r3/final>.

Referências consultadas em 21 de julho de 2026. Canal, formulário e orientação operacional são referências versionáveis e não regra congelada no Core. Operação exige revisão jurídica e de segurança da versão vigente e do caso concreto.

## O que esta ADR não decide

Esta ADR não escolhe SIEM, EDR, SOAR, ticketing, ferramenta forense, seguradora ou canal concreto. Também não fixa prazo universal, matriz final de severidade, equipe nominal, playbook técnico, obrigação jurídica, autoria, culpa ou admissibilidade judicial.

## Plano de reversão

Antes da implementação, a proposta pode ser substituída. Depois da adoção, nova decisão preserva Signals, triages, cases, assessments, decisions, actions, collections, custody entries, holds, impacts, communications, recoveries, closures e reviews históricos.

Reversão não apaga lacunas, desfaz comunicação, reclassifica conhecimento passado ou apresenta recuperação como inexistência do incidente.
