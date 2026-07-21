# ADR 0011 — Fontes normativas, vigência e reavaliação temporal
**Status:** Aceita  
**Data:** 20 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan deve explicar uma Decision conforme os fatos, Evidences, Policy, Rules e conhecimento disponíveis no instante relevante. Em cadeias reguladas, a fundamentação também pode mudar: normas são publicadas, corrigidas, alteradas, revogadas, consolidadas ou tornam-se aplicáveis em momentos distintos.

Uma Decision histórica não pode ser reescrita quando a norma muda. Ao mesmo tempo, auditor, regulador ou Organization autorizada precisa conseguir reproduzir o resultado original, avaliar sua fundamentação histórica, simular outra regra e executar reavaliação atual sem confundir essas operações.

`Law` seria estreito para o Core. A fundamentação pode vir de lei, decreto, regulamento, instrução, resolução, portaria, norma técnica, licença, contrato ou protocolo de mercado. Além disso, texto normativo não é automaticamente uma Rule executável: aplicabilidade e interpretação exigem contexto, aprovação e proveniência.

## Problema

Definir:

- representação, identidade, conteúdo, relações e temporalidade das fontes normativas;
- vínculo auditável com Policy, Rule, Evaluation e Decision;
- reprodução, avaliação histórica, simulação, reavaliação, impacto, tipos e limites das afirmações.

## Princípios

1. **Histórico imutável e temporalidade explícita:** mudança normativa não reescreve Decision; publicação, vigência, aplicabilidade, conhecimento e avaliação não são sinônimos.
2. **Fonte não é interpretação:** texto normativo e Rule permanecem distintos; referência identifica versão e dispositivo.
3. **Comparação não é decisão:** simulação não produz efeito operacional; o Titan apresenta base, resultado, escopo e limitações.
4. **Core genérico e autoridade delimitada:** regras concretas pertencem às verticais; hash não comprova oficialidade, interpretação ou validade jurídica.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Guardar somente Policy e versão | Modelo simples | Não explica a origem nem alterações normativas |
| Entidade `Law` com Rules embutidas | Ligação direta | Restringe fontes, mistura texto e interpretação e acopla o Core |
| Consultar sempre a fonte atual | Menor armazenamento | Destrói reprodutibilidade e pode alterar silenciosamente o passado |
| Instrumento normativo e base normativa versionados | Proveniência, temporalidade e comparação explícitas | Exige curadoria, relações e revisão especializada |

## Decisão

Adotar `NormativeInstrument` como identidade estável de uma fonte normativa e `NormativeInstrumentVersion` como expressão imutável de seu conteúdo em determinado contexto temporal.

Policy e Rule não pertencem ao instrumento. Elas registram, por meio de `NormativeBasis`, a interpretação operacional aprovada de referências normativas precisas.

Evaluation e Decision preservam um `NormativeBasisSnapshot` imutável suficiente para explicar e reproduzir a fundamentação utilizada. Mudança de norma, interpretação ou Policy cria novos registros e relações, nunca alteração silenciosa do histórico.

Os nomes são linguagem conceitual inicial. Sua inclusão definitiva no `DOMAIN.md`, representação física e APIs dependem de etapas posteriores aprovadas.

## Instrumento normativo

`NormativeInstrument` identifica de forma estável um instrumento, independentemente das mudanças de conteúdo. Deve registrar, quando aplicável:

- tipo controlado, identificador oficial e título;
- jurisdição, autoridade emissora e Source;
- relações com outros instrumentos.

Cada conteúdo distinto é uma `NormativeInstrumentVersion`, que preserva:

- identificador próprio, estável e não reutilizável;
- versão ou expressão oficial e datas de emissão e publicação;
- vigência e aplicabilidade declaradas;
- URI, publicador declarado, tipo e identificador da publicação;
- instantes, método e responsável pela captura e pelo registro;
- conteúdo, Artifact ou referência imutável permitida;
- Digest, algoritmo, serialização, Signature e Evidence de origem;
- idioma, jurisdição, estado, limitações, correções, anexos e relações.

Integridade do conteúdo, identidade da Source, autoridade da Source e oficialidade são dimensões independentes. `official_status_declared` registra a alegação recebida; `official_status_verified` registra verificação sustentada por Evidence. Uma cópia íntegra não se torna oficial por possuir Digest válido.

O Titan não inventa `v1` ou `v2` como se fossem identificadores jurídicos quando a fonte não os possuir. Pode manter versão técnica interna, preservando a identificação oficial e o tipo de alteração.

## Relações normativas

Relações possuem tipo controlado, direção, vigência, referência ao dispositivo e Evidence. Exemplos conceituais:

- `ALTERA`;
- `REVOGA`;
- `SUBSTITUI`;
- `CONSOLIDA`;
- `CORRIGE`;
- `REGULAMENTA`;
- `REFERENCIA`.

Relação não permite deduzir automaticamente efeito jurídico total. Revogação parcial, regra transitória, decisão de autoridade ou conflito entre jurisdições podem exigir interpretação aprovada.

## Temporalidade

O modelo distingue, quando aplicável:

- emissão (`issued_at`), publicação (`published_at`) e vigência declarada (`effective_from`, `effective_until`);
- aplicabilidade contextual (`applicable_from`, `applicable_until`), registro (`recorded_at`) e conhecimento pelo processo (`known_at`);
- fatos (`facts_as_of`), Evaluation (`evaluated_at`), Decision (`decision_at`) e instante respondido pela análise (`reference_time`).

Esses campos não são intercambiáveis. Seleção normativa não utiliza somente `decision_at`. Considera jurisdição, Subject, atividade, território, produto, mercado, fatos, regras transitórias, retroatividade e demais condições aprovadas.

Ausência ou conflito produz `INDETERMINADA`, revisão ou negação conforme Policy, sempre com razão controlada: `POLITICA_APLICAVEL_AUSENTE`, `MULTIPLAS_POLITICAS_APLICAVEIS`, `CONFLITO_NORMATIVO`, `LACUNA_TEMPORAL`, `JURISDICAO_INDETERMINADA` ou `AUTORIDADE_INDETERMINADA`. O motor não completa lacunas por suposição.

## Referência e base normativa

`NormativeReference` aponta para uma versão imutável e, quando possível, para artigo, seção, cláusula, anexo ou trecho canônico. Preserva identificação oficial, Digest e Evidence necessária.

`NormativeBasis` vincula Policy ou Rule às referências que a fundamentam e registra:

- finalidade, escopo, jurisdição e contexto de aplicabilidade;
- `interpreted_by`, `approved_by`, Organization e `approval_authority`;
- capacidade declarada do aprovador, justificativa e Evidence de competência;
- `approved_at`, `valid_from`, `valid_until`, estado e `intended_use`;
- versão da interpretação;
- divergências, exceções, limitações, base anterior e motivo da mudança.

Uma norma não executa Rules diretamente. Extração automatizada pode auxiliar, mas não se torna fundamentação aprovada sem validação, autoria e auditoria.

Aprovação identifica quem aprovou, em qual capacidade e para qual finalidade. Aprovação privada é decisão interna da Organization, salvo Evidence específica de competência ou reconhecimento externo. O Titan não a apresenta como entendimento oficial de autoridade pública, tribunal, certificadora ou auditor externo.

## Fotografia normativa da decisão

`NormativeBasisSnapshot` registra conceitualmente:

- NormativeBasis, NormativeReferences, dispositivos, Digests e versões;
- jurisdição, aplicabilidade, Policy, Rules, referência temporal e conhecimento;
- Actor aprovador, Evidence, lacunas, conflitos, exceções e limitações.

Um `dict` de código e versão não é suficiente como contrato. A fotografia deve ser tipada, imutável, correlacionada ao snapshot dos fatos e incluída no material auditável da Evaluation e da Decision.

## Operações temporais

O Titan distingue quatro operações:

### Reprodução histórica

Reexecuta snapshot, Policy, Rules, base normativa e versão do motor originais. Verifica reprodutibilidade técnica. Diferença é registrada e investigada; o resultado original não é substituído.

### Avaliação histórica de conformidade

Cria nova Evaluation para examinar se a decisão corresponde à base considerada aplicável no instante histórico. Pode usar conhecimento posterior, interpretação revisada ou fonte recuperada, desde que isso seja declarado separadamente.

O resultado não afirma automaticamente validade jurídica, fraude, culpa ou ausência de responsabilidade.

### Simulação contrafactual

Aplica Policy, Rules ou base normativa alternativas a um snapshot declarado. Responde hipótese como “qual seria o resultado sob a versão atual?”. É identificada como simulação, não altera a Decision e não produz efeito operacional sem caso de uso autorizado.

### Reavaliação atual

Avalia fatos e regras aplicáveis ao contexto atual. Pode produzir nova Decision somente por operação autorizada. Mantém relação com a decisão anterior e explica alterações de fatos, Policy, Rules, base, motor e resultado.

“Replay” não é usado como termo universal para essas quatro semânticas.

## Comparação

Resultado comparativo preserva:

- operação executada e sua finalidade;
- Decision original;
- snapshots original e comparado;
- instantes de referência e conhecimento;
- Policies, Rules, bases normativas e motores;
- resultados e diferenças por regra;
- razão classificada da divergência;
- Actor, Organization, autorização e instante da execução;
- limitações e necessidade de revisão.

Razões podem incluir mudança normativa, nova interpretação, alteração de fatos, Evidence posterior, correção de dados, versão do motor ou erro identificado. A classificação deve ser explicável e não presume intenção.

## Tipos e escopo das afirmações

Toda afirmação produzida possui tipo controlado:

- **factual** descreve registros e resultados; **computacional**, o resultado de Rule, Policy e motor;
- **proveniência** descreve origem e dependências; **normativa**, a interpretação adotada por Policy;
- **jurídica** declara aplicabilidade, legalidade, responsabilidade, fraude, sanção, obrigação ou efeito jurídico.

O motor genérico não emite afirmação jurídica sem perfil especializado, autoridade competente e processo de revisão e aprovação registrados. Afirmação normativa descreve a interpretação adotada; não a transforma em entendimento oficial.

`AssertionScope` acompanha toda conclusão e registra, quando aplicável:

- tipo, objeto, Subject, Organization, finalidade, período, `reference_time` e jurisdição;
- Policy, Rules, motor, versões, dados e Evidences considerados ou excluídos;
- limitações, lacunas, códigos de razão e autoridade declarada.

Afirmação sem escopo não pode ser apresentada como conclusão do Titan. API, interface, relatório e exportação preservam tipo e escopo e não ampliam uma conclusão limitada por meio de texto comercial ou apresentação visual.

## Análise de impacto regulatório

Nova versão ou relação normativa pode iniciar, mediante autorização:

1. validação da Source, conteúdo, Evidence, dispositivos e relações alterados;
2. localização de NormativeBases, Policies, Rules e objetos dependentes pela Provenance;
3. classificação temporal, aplicabilidade, simulação ou reavaliação controlada;
4. abertura de revisão, tarefa ou NonConformity e relatório para Actor autorizado.

O resultado `POTENCIALMENTE_AFETADO` indica que a Provenance cruza versão, dispositivo, NormativeBasis, Policy ou Rule afetada. Não significa `INVALIDO` e não modifica Decision, Dossier, Publication, Signature ou Evidence.

### Relatório de impacto normativo

O relatório registra instrumentos e versões comparados, dispositivos e relações alterados, dependências diretas, indiretas, semânticas possíveis ou desconhecidas, Policies, Rules e Decisions potencialmente afetadas, caminho de Provenance, período, Organizations, limitações de Authorization, lacunas, resultado, razões, Actor e finalidade.

O relatório é imutável e não corrige, republica, sanciona nem inicia recall automaticamente.

### Recall

O fluxo conceitual é `ImpactAnalysis → RecallAssessment → RecallDecision → comunicação e execução`. Detecção técnica, análise regulatória, decisão de negócio, comunicação e execução são etapas distintas.

Recall exige caso de uso específico, Policy aprovada e Actor competente. O Core pode identificar população potencialmente afetada, mas não declara obrigatoriedade, dispensa, culpa ou extensão final. Os conceitos definitivos de recall dependem de decisão própria antes da inclusão no `DOMAIN.md`.

## Limites das conclusões

O Titan pode afirmar, com escopo e Evidence:

- qual Policy, Rule e base normativa foram registradas;
- quais versões e dispositivos foram usados;
- se a reprodução obteve o mesmo resultado;
- se uma simulação alternativa divergiu;
- quais objetos podem ser afetados por uma mudança.

Detecção técnica utiliza estados como `ANOMALIA_DETECTADA`, `INCONSISTENCIA`, `AFIRMACAO_NAO_SUSTENTADA`, `CONFLITO_DE_EVIDENCIAS` ou `POTENCIAL_MANIPULACAO`. Somente Policy especializada pode encaminhar `REVISAO_DE_FRAUDE_NECESSARIA`, que ainda não constitui conclusão de fraude.

O Titan não conclui automaticamente:

- que uma norma é juridicamente aplicável sem Policy aprovada;
- que a decisão foi juridicamente correta ou incorreta;
- que houve ou não fraude, culpa ou responsabilidade;
- que recall é obrigatório ou dispensável;
- que uma norma retroage;
- que conteúdo íntegro é autêntico, oficial ou verdadeiro.

Essas conclusões exigem Policy específica, autoridade competente e, quando aplicável, revisão jurídica ou regulatória registrada.

## Segurança, autorização e isolamento

Registrar, aprovar, publicar, relacionar, interpretar e substituir fonte normativa são operações distintas. Cada uma exige Permission, OrganizationContext, Actor e auditoria.

Fonte pública não torna automaticamente Policy, Decision ou Dossier públicos. Sharing, Publication e Visibility continuam independentes.

Conteúdo externo é não confiável para parsing. URLs não são seguidas livremente a partir do payload; origens, formatos, tamanho, assinatura e Digests seguem allowlists e políticas aprovadas. Tokens, credenciais e conteúdo licenciado sem autorização não integram snapshots exportáveis.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Decisões historicamente explicáveis; comparação transparente; impacto regulatório rastreável; Core reutilizável |
| Negativas | Curadoria normativa; temporalidade complexa; necessidade de interpretação e aprovação; retenção de conteúdo histórico |

## Riscos e controles

| Risco | Controle |
|---|---|
| Norma tratada como Rule | NormativeBasis separa fonte e interpretação |
| Data da decisão escolher regra errada | Aplicabilidade multitemporal e contexto explícito |
| Texto consolidado apagar história | Versões e relações imutáveis |
| Hash ser apresentado como autoridade | Source, Evidence e limites separados do Digest |
| Simulação alterar decisão | Resultado correlacionado e sem efeito automático |
| Mudança gerar recall indevido | Policy e Actor competente decidem ação |
| Motor declarar fraude | Conclusões jurídicas fora do resultado automático |
| Referência externa mudar | Snapshot, versão, dispositivo e Digest |
| Norma de uma vertical contaminar o Core | Instrumento genérico; significado na vertical |

## Verificação automatizada

Testes futuros devem cobrir:

- versões imutáveis, relações normativas, referência precisa e Digest divergente;
- temporalidades distintas, seleção contextual e razões de `INDETERMINADA`;
- Policy sem NormativeBasis, aprovação privada e oficialidade não comprovada;
- reprodução idêntica ou divergente e conhecimento posterior declarado;
- simulação sem efeito, reavaliação correlacionada e afirmações com escopo;
- impacto por Provenance sem invalidar objetos ou iniciar recall;
- anomalia sem fraude, isolamento entre Organizations e conteúdo externo malicioso, mutável ou apenas declarado oficial.

## Critérios de aceitação

A ADR pode ser aceita quando:

- instrumento genérico, identidade estável, versão oficial e conteúdo imutável forem distintos;
- norma e Rule permanecerem separadas e relações não produzirem efeito jurídico automático;
- temporalidades e aplicabilidade contextual forem explícitas;
- referência identificar dispositivo e NormativeBasis registrar autoria, capacidade, aprovação e limitações;
- integridade, identidade, autoridade e oficialidade da Source forem dimensões distintas;
- Decision preservar fotografia normativa tipada, imutável e temporal;
- toda afirmação possuir tipo, AssertionScope, Evidence, limitações e razões;
- aprovação privada não ser apresentada como oficial;
- reprodução, avaliação histórica, simulação e reavaliação permanecerem distintas;
- conhecimento posterior não ser apresentado como conhecimento original;
- impacto produzir `POTENCIALMENTE_AFETADO`, relatório e Provenance sem modificar objetos;
- recall exigir caso de uso, Policy e Actor competentes;
- anomalia não ser fraude e conclusão jurídica exigir perfil e revisão registrados;
- API e interface não ampliarem conclusão técnica;
- isolamento, Visibility, Publication, auditoria e independência das verticais forem preservados.

## O que esta ADR não decide

Esta ADR não escolhe:

- fontes, integrações, ontologia ou legislação concreta de uma vertical;
- regra de carência ou outra interpretação jurídica específica;
- algoritmo, persistência, API, interface, política ou conclusão concreta sobre fraude, recall, sanção ou caso real.

## Plano de reversão

Antes da implementação, a proposta pode ser substituída por nova ADR. Depois da adoção, mudança de modelo preserva instrumentos, versões, referências, bases, snapshots, comparações e relatórios históricos. Migração cria registros correlacionados e nunca reescreve a fundamentação de Decisions anteriores.
