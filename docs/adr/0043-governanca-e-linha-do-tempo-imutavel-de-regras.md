# ADR 0043 - Governanca e linha do tempo imutavel de regras
**Status:** Aceita  
**Data:** 26 de julho de 2026  
**Decisores:** responsavel pelo produto e arquitetura do Titan

## Contexto

O Titan ja possui Policy, Rule, Evaluation e Decision. O incremento atual permite regras declarativas versionadas, persistidas e avaliadas de forma deterministica, mas algumas regras concretas ainda nascem em codigo da aplicacao ou da vertical.

Isso atende a validacao inicial do motor, mas cria uma limitacao importante: quando a regra normativa ou operacional muda, a alteracao tende a exigir novo deploy. Para uma plataforma de confianca, a regra aplicada em uma decisao precisa ser tao auditavel quanto o animal, o lote, a Evidence ou a Decision.

As ADRs 0011, 0016, 0017 e 0036 ja estabelecem que fonte normativa, interpretacao, Policy, Rule, Evaluation, Decision, reavaliacao e impacto historico sao conceitos distintos. Esta ADR detalha a governanca de ciclo de vida das Rules como artefatos versionados e auditaveis no Core.

## Problema

Definir:

- onde vive a governanca generica de regras;
- quem pode inserir, aprovar, publicar, substituir, suspender ou revogar regras;
- como preservar uma linha do tempo imutavel para cada Rule;
- como diferenciar regra propria de uma Organization, template Titan, regra de certificadora e interpretacao baseada em fonte governamental;
- como consultar regras aplicaveis por Organization, finalidade, vigencia, jurisdicao e contexto;
- como analisar impacto quando uma regra muda sem reescrever Decisions historicas.

## Principios

1. **Regra como artefato auditavel:** Rule concreta nao e apenas codigo nem configuracao efemera.
2. **Core generico:** governanca, versionamento, publicacao, auditoria e impacto pertencem ao Core.
3. **Vertical especializada:** fatos, payloads, templates concretos e vocabulario operacional pertencem as verticais.
4. **Motor separado do conteudo:** codigo executa contratos e invariantes; regra publicada e dado versionado.
5. **Historico preservado:** mudanca de regra cria nova versao, evento e relacao, nunca altera Evaluation ou Decision anterior.
6. **Autoridade declarada e verificavel:** quem cadastra, quem emite, quem aprova e quem publica podem ser atores diferentes.
7. **Sem oficialidade presumida:** regra baseada em lei, governo ou certificacao nao vira entendimento oficial sem Evidence e autoridade aplicaveis.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Manter regras concretas em codigo | Simples para MVP | Mudanca exige deploy e enfraquece auditabilidade normativa |
| Guardar apenas JSON de condicoes em tabela | Reduz deploy | Nao resolve autoridade, aprovacao, publicacao, timeline e impacto |
| Criar regra por vertical sem Core comum | Flexibilidade local | Duplica governanca e impede reutilizacao entre verticais |
| Publicar todas as regras diretamente por orgao externo | Autoridade forte | Inviavel no MVP e dependente de integracoes futuras |
| Governanca Core com regras versionadas e adotadas por Organizations | Auditabilidade e evolucao incremental | Exige novos casos de uso, permissoes e testes |

## Decisao

Adotar no Core uma governanca generica de regras com linha do tempo imutavel.

O Core define identidade, versao, publicacao, adocao, autoridade declarada, eventos de ciclo de vida, consulta aplicavel e analise de impacto. Verticais definem fatos, payloads, templates iniciais e interpretacoes operacionais especificas, sem contaminar o Core com conceitos como Animal, GTA, medicamento ou propriedade rural.

Regras concretas passam a ser artefatos versionados e publicados. O codigo da aplicacao nao deve ser a fonte primaria de regra normativa concreta; ele deve criar templates iniciais, validar definicoes, executar o motor deterministico, preservar hashes e coordenar publicacao, avaliacao e impacto.

## Modelo conceitual

### RuleIdentity

Identidade estavel da regra ao longo do tempo.

Preserva codigo canonico, Organization responsavel, vertical ou escopo generico, finalidade, tipo de regra, classificacao, criador inicial e relacoes com templates ou fontes normativas.

Alterar a semantica executavel nao altera a identidade; cria nova RuleVersion.

### RuleVersion

Versao imutavel da regra.

Preserva RuleIdentity, numero ou identificador de versao, condicoes declarativas ou referencia a artefato Wasm, severidade, requisitos de Evidence, justificativa, acao corretiva, vigencia normativa, aplicabilidade operacional, NormativeBasis, autor, aprovadores, Digests, estado e limitacoes.

Versao publicada nao e editada. Correcao, refinamento, excecao ou mudanca de interpretacao cria nova versao correlacionada.

### RulePublication

Ato auditavel que torna uma RuleVersion elegivel para uso por uma Organization, audiencia, finalidade, periodo e escopo.

Publication nao prova oficialidade da fonte, nao concede acesso aos dados subjacentes e nao altera Decisions historicas. Revocation ou supersession impedem novos usos conforme escopo e instante, mas preservam usos anteriores.

### RuleAdoption

Ato pelo qual uma Organization adota uma RuleVersion ou RuleTemplate para uma finalidade operacional propria.

Uma Organization pode adotar template do Titan, regra interna propria, regra de certificadora, regra contratual ou interpretacao baseada em norma governamental. A adocao registra efetividade operacional, escopo, aprovacao, autoridade interna, excecoes e Evidence.

### RuleTimelineEvent

Evento imutavel do ciclo de vida da regra.

Tipos iniciais:

- `RULE_IDENTITY_CREATED`;
- `RULE_VERSION_DRAFTED`;
- `RULE_VERSION_SUBMITTED_FOR_REVIEW`;
- `RULE_VERSION_APPROVED`;
- `RULE_VERSION_REJECTED`;
- `RULE_VERSION_PUBLISHED`;
- `RULE_VERSION_SUPERSEDED`;
- `RULE_VERSION_SUSPENDED`;
- `RULE_VERSION_REVOKED`;
- `RULE_ADOPTED`;
- `RULE_ADOPTION_CHANGED`;
- `RULE_IMPACT_ASSESSMENT_REQUESTED`;
- `RULE_IMPACT_ASSESSMENT_COMPLETED`.

Cada evento preserva Organization, Actor, capacidade, instante, motivo, Evidence, correlacao, versoes envolvidas e representacao minima autorizada.

### RuleImpactAssessment

Analise imutavel de impacto causada por nova versao, suspensao, revogacao, mudanca normativa ou mudanca de adocao.

Localiza Evaluations, Decisions, Dossiers, Publications, NonConformities e objetos de vertical potencialmente afetados por Provenance e referencias a RuleVersion.

Resultados iniciais:

- `SEM_IMPACTO`;
- `POTENCIALMENTE_AFETADO`;
- `AFETADO_CONFIRMADO`;
- `INDETERMINADO`;
- `REVISAO_HUMANA_NECESSARIA`.

ImpactAssessment nao reescreve Evaluation, Decision, Dossier ou Publication e nao inicia Recall automaticamente.

## Papeis

Os papeis sao distintos:

- **Author:** cadastra ou propõe a versao da regra.
- **Issuer:** autoridade alegada da regra, fonte ou interpretacao.
- **Approver:** aprova a versao para publicacao ou adocao.
- **Publisher:** torna a versao executavel dentro do escopo.
- **AdoptingOrganization:** Organization que decide usar a regra.
- **Consumer:** caso de uso, Organization ou vertical que avalia a regra.

No MVP, o Author e o Publisher podem ser operador autorizado do Titan ou Organization usuaria. Orgaos governamentais, certificadoras e auditores podem aparecer como NormativeSource, Issuer declarado ou Evidence, sem exigir integracao direta.

Futuramente, orgaos governamentais ou certificadoras podem publicar pacotes padrao ou fontes oficiais, desde que haja integracao, autenticacao, autoridade, Evidence e ADR ou incremento proprio.

## Insercao

Insercao de regra cria Draft ou nova versao, nunca altera versao publicada.

Campos minimos para uma versao declarativa:

- RuleIdentity ou pedido de criacao de identidade;
- Organization responsavel;
- Author e capacidade;
- Issuer declarado;
- tipo de fonte: `LEI`, `REGULAMENTO`, `CONTRATO`, `POLITICA_INTERNA`, `CERTIFICACAO`, `TEMPLATE_TITAN` ou `OUTRA`;
- NormativeBasis ou justificativa operacional;
- jurisdicao quando aplicavel;
- finalidade e escopo;
- condicoes executaveis ou referencia a artefato;
- severidade;
- requisitos de Evidence;
- vigencia normativa;
- efetividade operacional pretendida;
- limitacoes;
- Evidence e Digests quando aplicaveis.

Ausencia de fonte normativa pode ser valida para regra interna, mas deve ficar explicita. Fonte normativa externa nao dispensa aprovacao da Organization para uso operacional.

## Consulta

O Core deve permitir consultas auditaveis como:

- regras ativas para uma Organization e finalidade;
- regras aplicaveis em um instante historico;
- regras publicadas, substituidas, suspensas ou revogadas;
- regras por Issuer, fonte, jurisdicao, severidade ou tipo de Subject;
- linha do tempo de uma RuleIdentity;
- versao usada por uma Evaluation ou Decision;
- regras adotadas por uma Organization a partir de templates;
- regras potencialmente afetadas por mudanca normativa.

Consulta respeita OrganizationContext, Visibility, Publication, FieldScope e DataContract. Conhecer codigo de regra nao implica acesso a justificativa, Evidence, fonte completa ou impacto.

## Analise e reavaliacao

Mudanca de regra pode iniciar analise de impacto autorizada.

O Titan distingue:

- reproduzir uma Evaluation historica com a mesma RuleVersion;
- simular um snapshot antigo com nova RuleVersion;
- reavaliar estado atual com regra vigente;
- analisar impacto em Decisions, Dossiers e Publications.

Nenhuma dessas operacoes altera historico. Nova Decision exige caso de uso, autoridade e Policy aplicaveis conforme ADR 0016.

## Fronteiras arquiteturais

Domain define conceitos, estados e invariantes de RuleIdentity, RuleVersion, Publication, Adoption, TimelineEvent e ImpactAssessment.

Application coordena insercao, validacao, aprovacao, publicacao, consulta, selecao de regra aplicavel, analise de impacto e reavaliacao.

Infrastructure persiste registros, aplica RLS, busca regras, armazena artefatos permitidos e materializa consultas. Nao decide autoridade, vigencia, resultado, oficialidade ou impacto.

Presentation coleta pedidos e mostra representacoes autorizadas. Cliente nao fornece status, versao final, OrganizationContext, autoridade ou resultado confiaveis.

Verticais produzem FactSnapshots e templates especificos. O Core nunca importa modulo de vertical nem conhece payloads como dominio semantico; apenas avalia contratos declarativos aprovados.

## Consequencias

| Tipo | Consequencias |
|---|---|
| Positivas | Regra muda sem deploy; auditoria de ciclo de vida; decisoes historicas reproduziveis; adocao por frigorifico; futura participacao de governo ou certificadora |
| Negativas | Mais casos de uso, permissoes, estados, migrations e testes; curadoria normativa vira processo explicito |

## Riscos e controles

| Risco | Controle |
|---|---|
| Regra governamental cadastrada como oficial sem prova | Issuer declarado, NormativeBasis, Evidence e limitacoes separados |
| Frigorifico alterar regra para apagar problema | Nova versao e timeline imutavel; Decision antiga preserva RuleVersion usada |
| Template Titan virar regra obrigatoria sem adocao | RuleAdoption explicita por Organization |
| Core conhecer semantica livestock | Core avalia fact_type e payload declarativos; vertical produz fatos |
| Mudanca retroativa reescrever historico | ImpactAssessment e reavaliacao criam novos registros |
| Cliente publicar status arbitrario | Application resolve autoridade, aprovacao e transicoes |

## Verificacao automatizada

Testes futuros devem cobrir:

- versao publicada nao editavel;
- nova versao preservando identidade e supersession;
- consulta historica retornando a RuleVersion aplicavel no instante;
- Decision preservando RuleVersion usada;
- RuleAdoption exigida para template virar regra operacional de uma Organization;
- fonte governamental declarada nao apresentada como oficial sem Evidence;
- regra interna sem fonte externa mantendo justificativa explicita;
- impacto por nova RuleVersion marcando objetos como potencialmente afetados sem alterar Decisions;
- Core sem dependencia de vertical;
- cliente nao definindo status publicado, autoridade ou OrganizationContext;
- RLS impedindo Organization acessar regra interna de outra sem Publication ou grant.

## Criterios de aceitacao

A ADR e atendida quando:

- regras concretas puderem ser publicadas como artefatos versionados;
- ciclo de vida gerar timeline imutavel;
- adocao por Organization for separada de template ou fonte normativa;
- consulta por Organization, finalidade, vigencia, status e fonte for possivel;
- Evaluation e Decision preservarem a RuleVersion usada;
- mudanca de regra produzir impacto/reavaliacao sem reescrever historico;
- Core permanecer generico e verticais permanecerem donas dos fatos especificos;
- insercao e publicacao dependerem de autoridade e auditoria.

## O que esta ADR nao decide

Esta ADR nao escolhe:

- schema fisico, endpoint, UI, workflow ou nomes finais de tabelas;
- catalogo completo de permissoes;
- quais leis, protocolos ou certificacoes serao cadastrados;
- interpretacao juridica concreta de carencia, EUDR, SISBOV ou outra regra;
- integracao direta com governo, certificadora ou auditor;
- formato final de artefatos Wasm alem da direcao definida na ADR 0036.

## Plano de reversao

Antes da implementacao, esta ADR pode ser substituida por nova decisao. Depois da implementacao, reversao preserva RuleIdentities, RuleVersions, Publications, Adoptions, TimelineEvents, Evaluations, Decisions e ImpactAssessments historicos.

Reversao nao apaga timeline, nao altera versao usada por Decision e nao transforma simulacao ou impacto em decisao operacional.
