# Discovery — Policies de elegibilidade específicas do comprador

- **Nível previsto:** CRITICAL
- **Estado:** proposta de Discovery; não autoriza implementação
- **Decisão de Discovery:** aguardando decisão humana
- **Owner de produto:** Founder / Product Owner
- **Data:** 2026-08-15

## 1. Problema e oportunidade

Além de requisitos regulatórios de um mercado, frigoríficos e compradores podem
possuir critérios comerciais, contratuais ou internos próprios. Hoje não há uma
forma governada de um comprador declarar esses critérios sem misturá-los a uma
Policy normativa do Titan ou sem criar lógica particular fora do produto.

O objetivo é permitir que uma Organization compradora publique e evolua seus
critérios de elegibilidade de forma auditável, versionada e explicável, sem
alterar fatos operacionais, regras regulatórias ou conclusões históricas.

## 2. Evidência no repositório

- A ADR-0049 aceita explicitamente que requisitos regulatórios, contratuais e
  internos coexistam para uma mesma finalidade, preservando sua origem e alcance.
- `Policy`, `Rule`, versionamento, publicação e `RuleAdoption` já existem. A
  API vertical `/v1/rule-governance` já oferece criação/publicação de Policy,
  governança de Rule e catálogo de templates Livestock.
- `RuleSourceType` já diferencia `CONTRACT` e `INTERNAL_POLICY`.
- A política hoje é isolada pela `organization_id` proprietária. Não existe um
  contrato de relação comprador–produtor, compartilhamento inter-Organization,
  seleção formal de `MarketProfile` persistido, nem composição autorizada de
  Policies independentes.
- O perfil de mercado corrente ainda é estático; a ADR-0049 proíbe fazer dele
  uma segunda fonte de Rules ou permitir que o cliente escolha uma Policy
  autoritativa diretamente.

## 3. Recomendação de modelagem

Não criar `BuyerRule`, `BuyerMarket` nem uma segunda engine de regras.

Uma exigência do comprador deve ser uma **Policy existente**, de propriedade da
Organization compradora, com Rules governadas e origem classificável como
`CONTRACT` ou `INTERNAL_POLICY`. O perfil comercial futuro apenas seleciona e
coordena Policies publicadas; ele não contém condições de regra.

```text
Policy regulatória publicada              Policy do comprador publicada
  origem: regulatória                       origem: contratual ou interna
  owner: autoridade competente/Titan        owner: Organization compradora
                  \                         /
                   \ resolução autorizada /
                    ↓
             Evaluation separada por Policy
                    ↓
        apresentação comparativa explicável
```

Uma avaliação positiva de Policy compradora significa apenas que o sujeito
atende ao critério daquele comprador, naquela versão, finalidade, contexto e
instante. Ela nunca significa autorização de exportação, conformidade legal ou
reconhecimento externo.

## 4. Invariantes propostos

1. A Policy do comprador não altera, substitui nem reinterpreta uma Policy
   regulatória.
2. A origem é obrigatória e visível: `REGULATORY`, `CONTRACTUAL` ou `INTERNAL`;
   um critério interno nunca é apresentado como obrigação legal.
3. Cada `Evaluation` continua apontando para exatamente uma Policy publicada,
   versão, Rules e snapshot de fundamento aplicáveis.
4. A UI e o cliente solicitam uma finalidade; o servidor resolve as Policies
   aplicáveis no contexto autorizado. Não aceitam IDs de Policy arbitrários
   como autoridade de seleção.
5. Ausência, ambiguidade, conflito temporal, falta de fundamento, acesso
   inter-Organization não autorizado ou dados insuficientes permanecem
   explícitos e fail-closed.
6. Não há `Decision` agregada de “elegível para comprador” sem estratégia de
   composição publicada e autoridade de emissão definida.
7. A Organization ativa, a Organization proprietária da Policy e o limite de
   reconhecimento devem permanecer distinguíveis na leitura e no Dossier.
8. Nenhuma relação de contraparte concede leitura de Facts, Evidence, Decision
   ou Policy; o compartilhamento exige contrato explícito e autorização backend.

## 5. Opções consideradas

### A. Regras livres por comprador, executadas no frontend

Rejeitada. Duplicaria a engine, não teria versionamento/autoridade confiáveis e
permitiria que interface ou papel visual se tornassem fonte de autorização.

### B. Novo agregado `BuyerEligibilityRule`

Rejeitada. Duplicaria `Policy` + `Rule` + governança de versões, contrariando a
ADR-0049, que já localiza a regra concreta em uma Policy governada.

### C. Policy existente por comprador, com seleção e composição explícitas

Recomendada. Reutiliza o modelo e a governança já existentes, preserva origem e
limita a nova decisão ao contexto de autoria, escopo compartilhado e composição.

### D. Permitir somente filtros de consulta do comprador

Adiada como possível recurso comercial distinto. Filtros podem ser úteis, mas
não são avaliação explicável nem substituem uma Policy publicada.

## 6. Plano incremental proposto

### Fase 0 — decisão de produto e ADR (pré-requisito)

Produzir ADR específica antes de código, pois a capacidade altera fronteiras de
tenancy, governança, autoridade e contrato público.

Decidir:

- se o primeiro caso é **interno** do frigorífico, **contratual** bilateral, ou
  ambos;
- quem pode criar, revisar, publicar, revogar e adotar Policies do comprador;
- quem é dono da Policy e qual Organization pode avaliá-la;
- se produtor recebe somente resultado, detalhes das Rules, ou nada sem convite;
- quais fontes mínimas fundamentam uma Policy contratual/interna;
- se o primeiro resultado é somente comparativo ou emite Decision própria;
- como a finalidade e a relação comprador–fornecedor serão representadas;
- estratégia de composição para uma conclusão agregada futura.

**Saída:** ADR aceita e SPEC CRITICAL aprovada. Sem API, migration ou UI.

### Fase 1 — primeiro corte seguro: Policy privada isolada

Permitir que uma Organization compradora, com capability nova e explicitamente
aprovada, governe uma Policy própria para um propósito sintético e
`INTERNAL_ONLY`.

Escopo máximo:

- reutilizar criação, publicação, versionamento e timeline de Policy/Rule;
- limitar a autoria aos templates e fact types Livestock já autorizados;
- exigir classificação de origem, justificativa e referência contratual/interna
  segura, conforme decisão da Fase 0;
- avaliar somente sujeitos e dados que já estejam autorizadamente visíveis para
  a própria Organization compradora;
- emitir Evaluation separada, com boundary explícito;
- fornecer leitura técnica/auditável e roteiro de validação.

Fora de escopo: relacionamento novo entre Organizations, compartilhamento de
dados, mercado real, seleção de lote, Dossier agregado, integração ERP, editor
livre de DSL e Decision agregada.

**Gate:** o caso deve funcionar usando somente dados já autorizados para a
Organization compradora. Se isso não for um caso de negócio útil, pular direto
para a Fase 2 após a decisão de compartilhamento.

### Fase 2 — compartilhamento e avaliação bilateral controlada

Somente se o caso comercial exigir avaliar Animals/lot de outra Organization.

Definir e implementar, em incremento próprio:

- relação explícita, escopo, finalidade, vigência e revogação do acesso;
- policy de redaction para Facts, Evidence, razões e Dossiers;
- autorização server-side tanto na descoberta quanto na leitura dos resultados;
- auditoria de concessão, consulta, uso e revogação;
- isolamento testado entre comprador A, comprador B e produtor;
- comportamento após revogação, inclusive para consultas históricas.

Esta fase não concede autoridade sobre os registros do produtor; somente define
uma leitura autorizada e delimitada.

### Fase 3 — composição de resultado e experiência de produto

Após haver pelo menos um caso real regulatório e um caso comprador, decidir se
é necessária uma Policy agregadora publicada. Até essa decisão, a interface
mostra resultados lado a lado:

| Camada | Resultado | Limite semântico |
|---|---|---|
| Regulatória | Evaluation/Decision da Policy regulatória | não prova aceite comercial |
| Comprador | Evaluation/Decision da Policy do comprador | não prova conformidade legal |
| Composta | somente se houver Policy agregadora aprovada | explica origem e precedência |

Implementar a tela somente após APIs de leitura e redaction existirem. Ela deve
usar `PageContext`, razão/limitação e referências de Policy, sem concluir
"aprovado para exportação" a partir de um estado técnico ou privado.

### Fase 4 — escala e operação (adiada)

Impacto de mudança de Policy, reavaliação em massa, notificações, catálogo de
modelos comerciais, importação contratual, APIs para compradores e integrações
ERP são incrementos separados. Nenhum entra no primeiro corte.

## 7. Contratos e limites técnicos iniciais

| Área | Reuso | Lacuna/decisão |
|---|---|---|
| Regras determinísticas | `Policy`, `Rule`, `RuleEvaluationEngine` | proibir DSL livre no primeiro corte |
| Governança/auditoria | `RuleIdentity`, timeline, adoption | definir autoridade e ciclo de revisão |
| Origem | `RuleSourceType.CONTRACT` / `INTERNAL_POLICY` | persistência/apresentação da origem da Policy |
| Avaliação | `Evaluation`, `Decision`, snapshots | definir se o comprador pode emitir Decision |
| Tenant isolation | `OrganizationContext`, RLS | desenhar compartilhamento bilateral antes de atravessar tenants |
| UI | shell/context/statuses existentes | nenhuma tela até contrato de leitura real |

## 8. Critérios de aceite para a futura SPEC da Fase 1

1. Uma Policy do comprador é distinguível de Policy regulatória no modelo, API,
   resultado e Dossier, com origem e boundary legíveis.
2. Somente capability server-side aprovada permite cada ação de governança.
3. Nova versão ou revogação não reescreve Evaluation ou Decision histórica.
4. Uma Policy não aplicável, incompleta ou sem fundamento exigido não gera
   conclusão positiva.
5. Uma Organization não consegue criar, listar, avaliar ou inferir dados da
   Policy de outra Organization sem relacionamento autorizado.
6. Cada Evaluation preserva Policy/Rules/tempos/snapshot exigidos pelos
   contratos existentes.
7. O roteiro em `apps/validacao` demonstra os casos positivo, negativo,
   `403`, isolamento, conflito e revogação aplicáveis.
8. A UI apresenta `403` como não autorizado, e não como lista vazia; não usa
   role ou entity-kind como autorização.

## 9. Riscos

- **Mistura semântica:** chamar requisito privado de “regra de mercado” pode
  fazê-lo parecer regulatório. Mitigação: origem e boundary obrigatórios.
- **Vazamento entre Organizations:** comprador não pode descobrir dados do
  produtor por busca, erro, contagem ou timing. Mitigação: relacionamento,
  RLS, 404 seguro, testes negativos e redaction.
- **Agregação indevida:** combinar resultados por conveniência cria uma decisão
  sem Policy/autoridade. Mitigação: avaliações separadas até ADR de composição.
- **Autoria sem governança:** critérios comerciais podem mudar frequentemente.
  Mitigação: rascunho, publicação, versão, vigência, revisão e trilha auditável.
- **DSL excessiva:** editor genérico cedo aumenta superfície de segurança e
  validação. Mitigação: catálogo controlado de templates/fact types no início.

## 10. Decisão humana necessária

**Recomendação: PROCEED para a Fase 0, não para implementação.**

Para abrir a ADR e a SPEC, confirmar:

1. O primeiro caso de uso prioritário é uma exigência interna do frigorífico ou
   uma cláusula contratual compartilhada com o produtor?
2. O resultado privado deve ser visível ao produtor, somente ao comprador, ou
   depender de consentimento/escopo bilateral?
3. No MVP, é suficiente avaliar uma Policy compradora isolada e exibir o
   resultado ao lado da avaliação regulatória, sem uma conclusão agregada?
4. O comprador pode usar somente templates factuais já existentes ou há um
   requisito concreto que exigiria um novo fact type/template?

## 11. Não implementação

Este documento não adiciona API, migration, capability, relacionamento entre
Organizations, Policy, Rule, avaliação, Decision, tela, integração ou alteração
de `DOMAIN.md`. Ele organiza a decisão necessária para que a evolução não
crie uma segunda fonte de regras nem enfraqueça isolamento e auditabilidade.
