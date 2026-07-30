# ADR-0049 - Politicas regulatorias e perfis de mercado

**Data:** 2026-07-29<br>
**Status:** ACEITA<br>
**Aceita em:** 2026-07-29<br>
**Base normativa:** `DOMAIN.md` v1.19, ADRs aceitas ate ADR-0048<br>
**Escopo:** Titan Core e Titan Livestock<br>
**Relacionadas:** ADR-0041, ADR-0043, ADR-0044, ADR-0048

---

## 1. Contexto

O Titan Livestock ja demonstra elegibilidade por mercado para finalidades como exportacao para Uniao Europeia, China e Estados Unidos. A matriz atual combina finalidade, regras governadas, sujeito avaliado e leitura de politica vigente.

Essa capacidade nao pode evoluir por listas fixas no codigo ou por uma entidade de mercado que replique regras. Requisitos regulatorios, contratuais e internos possuem fontes, vigencias, jurisdicoes, audiencias e finalidades diferentes. A mesma realidade registrada pode ser avaliada por mais de uma `Policy`, sem que o dominio operacional seja reescrito.

A ADR-0048 exige que uma `Evaluation` preserve a `Policy`, as `Rules`, a fundamentacao normativa e o contexto que produziu a decisao. Esta ADR define como uma politica concreta e aplicavel sera selecionada para uma finalidade de mercado.

---

## 2. Problema

O Titan precisa responder, de modo deterministico e auditavel:

1. Qual mercado, jurisdicao e finalidade foram solicitados?
2. Quais `Policies` eram aplicaveis no instante de referencia e no conhecimento disponivel?
3. Que base normativa, contratual ou interna sustentava cada politica?
4. Como uma alteracao normativa cria nova versao sem reescrever avaliacoes anteriores?
5. O que acontece quando nenhuma, uma ou varias politicas parecem aplicaveis?
6. Como diferenciar requisito regulatorio, contratual e interno sem misturar seu efeito?

Essas respostas nao podem depender de selecao silenciosa, de uma regra embutida em entidade operacional ou de versao corrente de uma politica usada para reinterpretar uma decisao historica.

---

## 3. Decisao

Uma regra de mercado nao pertence ao dominio operacional. Ela pertence a uma `Policy` versionada, sustentada por uma base normativa identificavel e aplicada para uma finalidade delimitada.

O Titan adotara tres responsabilidades separadas:

```text
MarketProfile da vertical
    -> resolve finalidade, mercado, jurisdicao, audiencia e criterios de selecao
PolicyApplicabilityResolver da aplicacao
    -> encontra, valida ou recusa Policies candidatas
Policy + Rules + NormativeBasisSnapshot
    -> avaliam fatos, evidencias e relacoes no DecisionEngine
```

`MarketProfile` nao e fonte de regras e nao duplica `Policy`. Ele e uma configuracao versionada da vertical que declara qual finalidade e quais criterios delimitam a selecao de politicas aplicaveis.

Nesta fase, `MarketProfile` nao e entidade generica do Titan Core; ele pertence a vertical que possui o vocabulario do mercado. `PolicyApplicability` e o nome da questao arquitetural, nao uma entidade normativa. Sua eventual promocao a conceito generico exige ADR propria e alteracao formal do `DOMAIN.md`.

---

## 4. Escopo e nao objetivos

Esta ADR define criterios de representacao, selecao, temporalidade e composicao de politicas aplicaveis a perfis de mercado.

Esta ADR nao:

- cria uma regra concreta para Uniao Europeia, China, Estados Unidos ou outro mercado;
- cria `MarketProfile` generico no Core;
- cria `Jurisdiction` como nova entidade do Core;
- altera o significado de `Policy`, `Rule`, `NormativeBasis` ou `NormativeBasisSnapshot`;
- define DSL, sandbox, banco, API ou interface de autoria;
- substitui a autoridade regulatoria, contratual ou juridica competente;
- torna a matriz atual integralmente conforme a ADR-0048.

---

## 5. MarketProfile

Um `MarketProfile` e configuracao especializada, imutavel e versionada da vertical. Ele representa o contexto comercial de uma avaliacao, nao o conteudo de uma norma.

Quando aplicavel, um perfil preserva:

- identificador estavel e versao;
- vertical responsavel;
- mercado ou destino comercial declarado;
- finalidade canonica de avaliacao;
- jurisdicoes e audiencias declaradas;
- tipo de sujeito e sujeitos dependentes esperados;
- criterios para selecionar `Policies` candidatas;
- periodo de vigencia;
- responsavel pela publicacao, justificativa e referencias de evidencia;
- estado, substituicao e limitacoes.

Um perfil nao contem `RuleCondition`, valores de limites regulatorios ou conclusao de elegibilidade. Alteracao de finalidade, criterio de selecao, jurisdicao, audiencia, escopo ou estrategia de composicao cria nova versao.

Um perfil pode referenciar `Policies` especificas quando a governanca exigir conjunto fechado e versionado. Alternativamente, pode usar criterios controlados de descoberta. O modo utilizado deve ser explicito; uma lista incidental de IDs nao substitui estrategia de selecao publicada.

---

## 6. PolicyApplicability

`PolicyApplicability` designa a questao: uma `Policy` pode ser usada para esta finalidade, sujeito, jurisdicao, audiencia e instante?

Nesta fase, ela nao e entidade generica persistida do Core. O resolvedor de aplicacao produz resultado tecnico transitorio, estruturado e correlacionavel a `Evaluation`, sem criar novo registro normativo autoritativo, com:

- perfil e versao utilizados;
- `Policy` candidata e versao;
- criterios avaliados;
- instante de referencia e instante do conhecimento;
- `NormativeBasis` ou limitacoes aplicaveis;
- resultado `APLICAVEL`, `NAO_APLICAVEL`, `INDETERMINADA` ou `CONFLITANTE`;
- codigos, lacunas, conflitos e justificativas.

O resultado de aplicabilidade nao e `EvaluationOutcome`, `DecisionResult` nem autorizacao de emissao. Ele apenas delimita quais politicas podem seguir para avaliacao. Quando for necessario persisti-lo como objeto independente, sua identidade, imutabilidade, temporalidade, proveniencia e autorizacao exigem ADR propria e alteracao formal do `DOMAIN.md`.

---

## 7. Jurisdicao

O Core ja representa jurisdicao como contexto de `NormativeBasis`, `NormativeReference`, `NormativeBasisSnapshot` e mapeamentos de jurisdicao. Esta ADR nao cria uma entidade universal adicional.

O perfil declara identificadores controlados de jurisdicao adequados a vertical. A `Policy` e sua fundamentacao registram a jurisdicao e as condicoes de aplicabilidade relevantes. Jurisdicao ausente, ambigua ou sem mapeamento vigente nao e resolvida por suposicao: produz indeterminacao ou revisao.

---

## 8. Finalidade da avaliacao

Toda selecao de politica parte de uma finalidade explicita e versionavel.

Para elegibilidade de mercado, a finalidade pertence ao vocabulario da vertical, por exemplo `exportacao-uniao-europeia`. Ela nao se confunde com `AccessPurpose`: finalidade de avaliacao explica por que uma `Policy` e avaliada; finalidade de acesso delimita quem pode consultar quais dados.

Strings livres nao sao contrato suficiente. A vertical deve usar valor controlado, `Value Object` ou configuracao publicada equivalente.

---

## 9. NormativeBasis

`NormativeInstrument`, `NormativeInstrumentVersion`, `NormativeReference` e `NormativeBasis` sustentam uma politica regulatoria quando houver fundamento externo identificavel. Podem tambem sustentar uma politica contratual quando o contrato ou protocolo exigir interpretacao identificavel.

Uma `Policy` usada em `Evaluation` historica preserva `NormativeBasisSnapshot` correspondente. O snapshot inclui versoes, dispositivos, jurisdicao, condicoes, instantes, lacunas, conflitos e limitacoes conhecidos; nao e substituido por referencia a fundamentacao corrente.

Toda `Policy` contratual preserva contrato, protocolo, clausula, versao, autoridade e evidencias identificaveis por meio dos conceitos existentes ou de perfil especializado aprovado. Politica interna sem fonte normativa externa continua exigindo justificativa, autoridade, finalidade e versao. A ausencia de base externa nao autoriza apresenta-la como obrigacao legal ou regulatoria.

---

## 10. Policy e Rule

`Policy` e conjunto versionado de `Rules` para uma finalidade definida. `Rule` e criterio versionado e deterministico aplicado a `Facts`, `Claims`, `Evidences` ou relacoes.

O conteudo concreto de uma regra pertence a `Policy` e suas `Rules`, nunca a `MarketProfile` ou a entidade operacional da vertical. Para fins de apresentacao e governanca, a origem da obrigacao deve ser classificavel como:

- **regulatoria:** fundada em instrumento, referencia e interpretacao normativa identificaveis;
- **contratual:** fundada em contrato, protocolo comercial ou exigencia acordada identificavel;
- **interna:** criterio proprio da Organization, que nao e apresentado como norma externa.

Esta ADR nao cria enumeracao normativa nova no Core: a forma persistida, cardinalidade e regras dessa classificacao exigem definicao posterior. Politicas de origens distintas podem coexistir na mesma finalidade, mas sua precedencia, composicao e efeito devem ser explicitos. Nenhuma origem e implicitamente superior apenas pelo nome.

---

## 11. Selecao de politica

O cliente pode solicitar mercado ou finalidade, mas nao fornece `MarketProfile`, versao, jurisdicao resolvida ou `Policies` confiaveis. O servidor resolve o perfil publicado e aplicavel dentro do contexto autorizado.

O `PolicyApplicabilityResolver`, componente de aplicacao, recebe perfil resolvido pelo servidor, finalidade, sujeito, Organization, instantes e contexto autorizado. Ele:

1. resolve o `MarketProfile` versionado aplicavel;
2. identifica `Policies` candidatas por finalidade e escopo;
3. verifica vigencia, jurisdicao, audiencia, Organization, sujeito e limitacoes;
4. avalia a fundamentacao e a classificacao da politica quando aplicaveis;
5. produz candidatas aceitas, recusadas, ausentes e conflitantes no resultado tecnico correlacionavel;
6. entrega ao `DecisionEngine` apenas cada `Policy` explicitamente resolvida para sua propria `Evaluation`.

O resolvedor nao consulta payloads internos da vertical para interpretar uma `Rule`; ele usa contratos de contexto e referencias autorizadas. A execucao da regra continua sendo responsabilidade do motor de avaliacao.

---

## 12. Vigencia e temporalidade

Selecao e avaliacao devem distinguir, quando aplicavel:

- tempo do fato;
- instante de referencia da avaliacao;
- instante em que a politica e sua base normativa eram aplicaveis;
- instante de registro;
- instante do conhecimento;
- instante de emissao da decisao.

Uma politica publicada posteriormente nao e projetada sobre decisao anterior. Uma fonte normativa recuperada posteriormente tambem nao se torna conhecimento original sem registro explicito.

A aplicabilidade do `MarketProfile` e a aplicabilidade da `Policy` sao avaliadas separadamente. Perfil vigente nao torna `Policy` vigente; `Policy` vigente nao torna perfil aplicavel. A selecao somente e conclusiva quando todas as dimensoes requeridas forem resolvidas para os instantes e a finalidade correspondentes.

As adequacoes T1 e T2 da ADR-0048 sao pre-requisitos para alegar reproducao historica completa de uma selecao de politica regulatoria.

---

## 13. Multiplas Policies potencialmente aplicaveis

Mais de uma `Policy` aplicavel nao e erro por si so. Conforme a linguagem normativa vigente, cada `Evaluation` executa uma `Policy` e suas `Rules`.

Quando uma finalidade exigir mais de uma `Policy`, cada politica produz `Evaluation` propria. A apresentacao pode exibir os resultados lado a lado, mas nao os converte silenciosamente em `Decision` agregada.

Uma `Decision` agregada somente pode existir quando uma `Policy` agregadora, publicada e versionada, executar as regras necessarias em nova `Evaluation`, ou quando futura ADR alterar formalmente essa semantica. Uma configuracao versionada da vertical pode declarar criterios de coordenacao para leitura e apresentacao, mas nenhuma `Policy` individual define unilateralmente precedencia sobre outra `Policy` independente.

Sem estrategia publicada, o resolvedor nao escolhe candidata por ordem incidental, nao agrega resultados e nao fabrica `Policy` vazia. O resultado da resolucao permanece `INDETERMINADA` ou `CONFLITANTE`, com codigos e candidatas preservados no retorno tecnico.

---

## 14. Ausencia e conflito normativo

Ausencia de `Policy` aplicavel, multiplas politicas sem composicao definida, conflito de jurisdicao, lacuna temporal ou autoridade normativa indeterminada devem permanecer explicitos.

Resultados como `POLITICA_APLICAVEL_AUSENTE`, `MULTIPLAS_POLITICAS_APLICAVEIS`, `CONFLITO_NORMATIVO`, `LACUNA_TEMPORAL`, `JURISDICAO_INDETERMINADA` e `AUTORIDADE_INDETERMINADA` nao podem ser convertidos silenciosamente em elegibilidade, inelegibilidade ou escolha da politica mais recente.

Quando nenhuma `Policy` aplicavel puder ser resolvida, o sistema nao cria `Evaluation` nem `Decision` sem `Policy` identificada. O caso retorna resultado estruturado de resolucao inconclusiva ou, quando houver `Policy` de governanca explicitamente publicada para avaliar a ausencia, executa essa politica identificada.

---

## 15. Politicas regulatorias, contratuais e internas

O mesmo sujeito pode ser avaliado simultaneamente por exigencia regulatoria, condicao contratual de comprador e criterio interno de risco.

O Titan deve preservar a origem e o alcance de cada politica. Uma `Decision` ou apresentacao derivada deve indicar quais camadas participaram e evitar frases que transformem regra interna em obrigacao legal, ou condicao contratual em certificacao regulatoria.

Quando uma finalidade exigir conclusao agregada, a estrategia deve ser materializada por `Policy` agregadora publicada e versionada ou por conceito futuro formalmente aprovado. A origem de cada efeito permanece navegavel.

---

## 16. Versionamento

`MarketProfile`, `Policy`, `Rule`, `NormativeInstrumentVersion`, `NormativeReference` e `NormativeBasis` evoluem por novas versoes ou novos registros. Registros historicos nao sao alterados para refletir contexto posterior.

Substituir perfil ou politica pode iniciar `CurrentReevaluation`, mas nao reescreve a `Evaluation` ou a `Decision` anterior. `HistoricalReproduction`, `HistoricalComplianceAssessment` e `CounterfactualSimulation` usam os elementos definidos pela ADR-0048.

---

## 17. Invariantes

1. `MarketProfile` nao contem regras normativas nem resultado de elegibilidade.
2. Toda `Policy` usada possui finalidade e versao identificaveis.
3. Toda politica regulatoria preserva `NormativeBasis` quando aplicavel; politica contratual preserva seu fundamento identificavel ou lacuna explicita.
4. Selecao ambigua ou ausente nao produz escolha silenciosa.
5. A `Evaluation` preserva a `Policy`, as `Rules` e o `NormativeBasisSnapshot` aplicaveis.
6. Alteracao normativa ou de perfil nao reescreve decisao historica.
7. Finalidade de avaliacao nao se confunde com `AccessPurpose`.
8. Politica interna nao e apresentada como obrigacao regulatoria externa.
9. O Core nao importa vocabulos concretos de mercado da vertical.
10. `MarketProfile` nao e promovido a entidade generica do Core sem decisao formal posterior.
11. O cliente nao seleciona diretamente versao autoritativa de `MarketProfile` ou `Policy`.
12. Toda `Evaluation` referencia exatamente uma `Policy` publicada e identificada; ausencia de politica nao e representada por politica implicita, vazia ou sintetizada em tempo de execucao.

---

## 18. Fluxo de referencia

```text
1. Receber solicitacao de finalidade, Subject e contexto autorizado
2. Resolver no servidor MarketProfile versionado da vertical
3. Delimitar jurisdicao, audiencia e instantes relevantes
4. Encontrar Policies candidatas
5. Resolver aplicabilidade, lacunas e conflitos
6. Para cada Policy resolvida, construir NormativeBasisSnapshot da Evaluation
7. Delimitar snapshot de fatos, evidencias e relacoes para cada Evaluation
8. Executar Rules e produzir uma Evaluation por Policy
9. Produzir DecisionProposal ou Decision autorizada por Evaluation, conforme ADR-0048
10. Expor matriz e Dossier dentro do escopo autorizado, sem agregar Decisions sem Policy agregadora
```

---

## 19. Exemplo: elegibilidade para mercado

Para avaliar animal ou lote para `exportacao-china`, a vertical resolve o `MarketProfile` correspondente. O perfil declara a finalidade, jurisdicao e criterios para localizar politicas de rastreabilidade, qualificacao de estabelecimento, carencia ou outros requisitos aprovados.

Cada regra concreta permanece na `Policy` governada. Se a qualificacao do frigorifico depender de sujeito secundario, isso e requisito da politica e do perfil, nao campo permanente do animal. Se faltar uma politica, a matriz mostra lacuna; se houver conflito, mostra indeterminacao; se a politica mudar, a leitura pode sinalizar reavaliacao necessaria sem alterar a decisao anterior.

---

## 20. Estado atual e transicao

O Titan Livestock possui `MarketProfile` de aplicacao ainda estatico e regras governadas adotadas por finalidade. A matriz ja preserva `Policy`, `Rule`, versao, adocao e estado de projecao, mas nao possui ainda perfil versionado persistido, resolvedor formal de aplicabilidade, `Policy` agregadora publicada quando necessaria ou `NormativeBasisSnapshot` completo no caminho de mercado.

Essas limitacoes nao invalidam registros existentes nem autorizam altera-los. Elas delimitam o que a matriz atual pode afirmar.

A transicao deve ocorrer por incrementos separados:

1. concluir T1 e T2 da ADR-0048 para snapshot e temporalidade;
2. introduzir perfil versionado da vertical e resolvedor deterministico de aplicabilidade;
3. registrar fundamentacao normativa e introduzir `Policy` agregadora somente quando houver necessidade e autoridade para conclusao oficial agregada;
4. concluir T3 e T4 da ADR-0048 para emissao oficial autorizada.

---

## 21. Alternativas rejeitadas

### 21.1 Regras de mercado dentro de entidades operacionais

Rejeitada porque acopla a vertical a jurisdicoes e mercados, reescreve realidade registrada quando uma norma muda e impede avaliar o mesmo sujeito sob politicas diferentes.

### 21.2 MarketProfile como nova fonte de Rules

Rejeitada porque duplica `Policy`, dispersa versao e fundamento normativo e cria duas fontes de verdade para o mesmo requisito.

### 21.3 Escolher a primeira Policy encontrada

Rejeitada porque ordem de consulta nao e criterio normativo e oculta conflito ou lacuna de aplicabilidade.

### 21.4 Criar MarketProfile generico no Core agora

Rejeitada porque ainda nao ha consumidor em outra vertical que demonstre semantica universal. A configuracao especializada resolve a necessidade atual sem ampliar o dominio.

---

## 22. Criterios de conformidade

Uma implementacao esta conforme esta ADR somente se:

- perfil de mercado e politica possuem responsabilidades distintas;
- selecao de politica usa finalidade, versao, vigencia e contexto declarados;
- o servidor, e nao o cliente, resolve perfil, versao e politica autoritativos;
- ausencia, ambiguidade e conflito permanecem explicitos;
- politica regulatoria, contratual e interna sao distinguiveis;
- `NormativeBasisSnapshot` preserva a fundamentacao usada quando aplicavel;
- cada `Evaluation` referencia exatamente uma `Policy` publicada e identificada;
- ausencia de `Policy` nao produz `Evaluation`, `Decision` ou politica sintetizada;
- mudanca normativa gera nova versao, nova avaliacao ou reavaliacao, nunca sobrescrita historica;
- o Core permanece livre de vocabulos concretos de mercado;
- a emissao de `Decision` respeita a ADR-0048.

---

## 23. Questoes adiadas

Permanecem para decisoes proprias:

- taxonomia internacional canonica de mercados e jurisdicoes;
- fonte oficial e processo de captura de instrumentos regulatorios por pais;
- interface de autoria e aprovacao de perfis e politicas;
- forma persistida e cardinalidade da classificacao regulatoria, contratual e interna;
- conceito generico ou estrategia reutilizavel de composicao entre `Policies` independentes;
- DSL e sandbox de regras normativas;
- composicao avancada entre politicas de Organizations distintas;
- publicacao e distribuicao de bundles regulatorios;
- promocao de `MarketProfile` ou `PolicyApplicability` a conceito generico do Core.

---

## Conclusao

Mercado nao e uma propriedade permanente do animal, do lote ou de outra entidade operacional. Ele e um contexto de finalidade no qual uma `Policy` versionada pode ser aplicavel.

O Titan preserva a realidade registrada separadamente da interpretacao regulatoria, contratual ou interna. Dessa forma, uma mudanca de regra produz nova avaliacao explicavel, e nao uma reescrita silenciosa do passado.
