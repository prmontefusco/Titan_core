# ADR-0058 — Artefato de captura externa source-neutral

**Status:** PROPOSTA  
**Data:** 12 de agosto de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Corte 1 do POST-LIV-03 provou, com dados e transporte falsos, que o Titan consegue
capturar e interpretar a forma mínima de Animal, GTA e Movimentação do simulador local
SISBOV. Cada captura é marcada permanentemente como `SIMULATED`.

O próximo corte precisa preservar a captura e permitir sua revisão antes de eventualmente
produzir Facts ou coverage. O fluxo atual de `ImportedLivestockFact`, porém, exige
`ReceivedTransferArtifact`. Esse agregado representa um pacote recebido numa
transferência de custódia entre organizações, conforme ADR-0042. Uma consulta a API
externa não é transferência de custódia, mesmo quando se refere ao mesmo Animal ou GTA.

Usar `ReceivedTransferArtifact` para a resposta de uma API:

- afirmaria uma travessia de custody que não ocorreu;
- confundiria quem forneceu material com quem transferiu histórico;
- permitiria que a existência de uma resposta externa parecesse continuidade entre
  Organizations;
- enfraqueceria os invariantes da ADR-0042.

Ao mesmo tempo, uma resposta HTTP sem identidade, digest, instante, contrato e escopo
não pode sustentar revisão futura. A integração não deve conservar tokens, segredos ou
URLs escolhidas pelo conteúdo externo.

## Problema

Definir o menor artefato persistível que represente material capturado de fonte externa,
sem criar autoridade, Fact, Evidence, coverage, associação de sujeito ou transferência
de custódia por acidente.

## Precedentes reutilizados

- **ADR-0015:** origem, validação, confiança, admissibilidade e verdade material são
  dimensões distintas;
- **ADR-0020:** adapters traduzem contratos; parsing e autenticação técnica não decidem
  confiança, admissibilidade ou negócio;
- **ADR-0039/0055:** digest e integridade de material não provam emissor, autoridade ou
  reconhecimento externo;
- **ADR-0042:** `ReceivedTransferArtifact` continua exclusivo para a prova recebida em
  transferência de custody; identificador coincidente não une sujeitos;
- **NEXT-01:** contribuição de coverage é dimensional, source-neutral e explícita; um
  artefato nunca gera coverage apenas por existir;
- **POST-LIV-03/Corte 1:** `SISBOV_SIMULATOR_LOCAL` é material fictício, não fonte
  oficial.

## Decisão proposta

Introduzir na vertical Livestock o artefato append-only e tenant-scoped
`ExternalSourceCaptureArtifact`.

Ele responde somente:

> “Qual material foi capturado por esta Organization, de qual perfil de Source, sob qual
> contrato/escopo, em que instante e com qual resultado técnico observável?”

Ele não responde “o que é verdadeiro?”, “quem tem autoridade?”, “a que Animal Titan
isto pertence?”, “qual coverage está completa?” ou “houve transferência de custody?”.

Contrato conceitual mínimo:

```text
ExternalSourceCaptureArtifact
  artifact_id
  record_owner_organization_id
  source_profile_code
  source_environment                 # inicialmente SIMULATED
  contract_version
  resource_kind                      # inicialmente ANIMAL | GTA | MOVEMENT
  request_scope_digest               # nunca segredo nem URL livre
  response_status / transport_outcome
  response_digest
  captured_at
  raw_material_reference?            # Document/armazenamento protegido, se necessário
  parser_name / parser_version
  parsing_assessment_reference?
  correlation_reference
  limitations[]
  recorded_by / recorded_at
```

O `request_scope_digest` identifica o escopo autorizado da consulta sem registrar
credenciais ou reproduzir dados protegidos desnecessariamente. `response_digest` é nulo
quando não houve corpo e, quando existe, confere exatamente ao material preservado. A
resposta bruta, se retida, fica em armazenamento protegido como material/documento;
ela não é copiada para evento, log, outbox ou `Fact.payload`.

O primeiro `source_profile_code` permitido será
`SISBOV_SIMULATOR_LOCAL`, com `source_environment=SIMULATED`. A implementação não
aceitará um perfil “oficial” sem configuração, autorização, credenciais e revisão
específicas posteriores.

## Fluxo e fronteiras

```text
adapter de Source (Infrastructure)
      ↓ resposta técnica não confiável
ExternalSourceCaptureArtifact
      ↓ parsing assessment delimitado
material revisável
      ↓ associação humana explícita, quando necessária
importação aprovada de Fact e/ou contribuição dimensional
      ↓ Policy decide admissibilidade e efeito
Evaluation / Decision
```

O primeiro corte persistente para no segundo estágio. Ele não cria Facts, Evidences,
coverage contributions, Assertions, Evaluation, Decision ou Dossier.

Uma associação a Animal local é uma proposta/revisão operacional separada, baseada em
identificador e material visível. Ela nunca funde identidades, nunca altera
identificadores e nunca cria continuidade histórica. Ausência, colisão e divergência
permanecem explícitas.

`ReceivedTransferArtifact` pode, futuramente, ser uma fonte de material para o mesmo
processo de avaliação, mas não é supertipo nem requisito deste artefato. Os dois
conceitos preservam papéis diferentes.

## Invariantes

1. `ExternalSourceCaptureArtifact` não é `ReceivedTransferArtifact` e não altera seus
   invariantes.
2. Captura externa não produz Fact, Evidence, coverage, Assertion, Evaluation ou
   Decision automaticamente.
3. `SIMULATED` é imutável para material vindo do simulador; nunca pode ser promovido por
   edição posterior a oficial, validado ou reconhecido.
4. Digest válido comprova apenas integridade do material retido contra aquele digest.
5. Autenticação de transporte, HTTP 200, existência de identificador externo ou parsing
   bem-sucedido não comprovam verdade, autoridade, admissibilidade ou cobertura.
6. Um resultado 404, vazio, parcial, timeout, 401, 403 ou 5xx nunca prova inexistência
   do sujeito, GTA ou evento no mundo externo.
7. Identificador externo coincidente cria no máximo candidato de associação; não liga
   sujeitos nem cria continuidade.
8. Cada captura é imutável; nova consulta ou correção cria nova captura com correlação
   explícita, sem sobrescrever a anterior.
9. Segredos, tokens, headers sensíveis e URL arbitrária não entram no artefato, eventos,
   logs, testes ou payloads de domínio.
10. RLS protege o artefato por Organization; uma captura não permite leitura cruzada.
11. Coverage exige contribuição dimensional explícita, validada e admissível; captura
    isolada contribui zero.
12. A Policy continua sendo a única consumidora que decide o efeito de material aceito.

## Alternativas descartadas

### Reutilizar `ReceivedTransferArtifact`

Rejeitada. Distorce semântica de custody e viola a ADR-0042.

### Converter diretamente a resposta em `ImportedLivestockFact`

Rejeitada. Pula a captura auditável, a revisão de associação e o portão de
validação/admissibilidade; além de exigir falsamente um artefato de transferência.

### Guardar apenas campos normalizados sem o material/digest de captura

Rejeitada. Não permite explicar qual resposta produziu o mapeamento, detectar mudança
de parser nem investigar conflito posterior.

### Criar agora um aggregate Core universal de provider externo

Rejeitada. Há somente o caso Livestock/SISBOV simulator; a ADR-0020 já define as
fronteiras genéricas necessárias. Generalização ao Core exigirá segundo domínio concreto.

### Tratar a captura como Evidence automaticamente

Rejeitada. Evidence requer semântica e admissibilidade próprias. A captura pode ser
material para Evidence futura, mas não substitui sua avaliação.

## Cortes de implementação propostos

1. **Corte 2 do POST-LIV-03:** domínio/application/infrastructure mínimos para o
   artefato, RLS, persistência append-only, perfil exclusivamente simulado e roteiro
   manual de captura/revisão; sem Facts nem coverage.
2. **Corte 3:** somente após escolher campos reais e Policy consumidora, importar Facts
   e/ou contribuições dimensionais explicitamente aprovadas.
3. **Integração oficial:** somente após contrato oficial confirmado, autorização de uso,
   ServiceIdentity/credenciais externas, capability review e desenho de segurança
   próprios. Ela cria perfil novo e nunca reclassifica capturas simuladas.

## Fora de escopo

- conexão oficial SISBOV/MAPA, homologação, produção, white-list ou credenciais reais;
- execução HTTP, polling, cache, webhook, worker, outbox ou sincronização em lote;
- emissão/cancelamento de GTA ou alteração de dados externos;
- autoridade sanitária, reconhecimento externo, autorização de exportação;
- importação de Facts, Evidence, coverage ou Assertion;
- associação automática, fusão de Animal, continuidade entre Organizations ou mudança de
  Policy.

## Critérios para aceitação

Esta ADR só deve ser aceita quando houver concordância explícita de que a captura
externa precisa ter identidade e retenção próprias e que a primeira implementação será
limitada ao Corte 2 acima. A implementação deve provar RLS, imutabilidade, digest,
ausência de segredos, marca `SIMULATED`, falhas explícitas, associação não automática e
ausência de efeitos sobre Facts/coverage/Decision.
