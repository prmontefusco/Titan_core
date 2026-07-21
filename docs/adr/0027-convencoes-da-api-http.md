# ADR 0027 — Convenções da API HTTP

**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** fundador e responsável pela arquitetura do Titan

## Contexto

O Passo 1.3 criará o primeiro endpoint HTTP. Sem convenções prévias, versionamento, erros, paginação, concorrência e idempotência podem se tornar contratos incompatíveis por acidente.

As convenções devem preservar OrganizationContext, autorização, negação por padrão, auditabilidade e resultado desconhecido sem transportar detalhes de protocolo para Domain.

## Alternativas

1. Definir cada endpoint isoladamente: menor trabalho inicial, maior inconsistência e custo de compatibilidade.
2. Criar framework próprio de API: uniformidade, mas abstração prematura e acoplamento.
3. Fixar convenções HTTP mínimas e evoluí-las por compatibilidade: reduz decisões acidentais sem antecipar endpoints.

## Decisão

Adotar convenções HTTP mínimas desde o primeiro endpoint. Presentation traduz HTTP; Application e Domain permanecem independentes de rotas, headers, status codes e Problem Details.

## Versionamento

- rotas públicas iniciam em `/api/v1`;
- versão representa contrato externo, não versão de Policy ou entidade;
- mudança compatível mantém a versão;
- remoção, mudança semântica ou formato incompatível exige nova versão ou transição documentada;
- endpoint técnico não versionado é permitido somente para saúde do processo e não expõe domínio.

## Representação

- JSON usa UTF-8 e nomes `snake_case`;
- timestamps usam RFC 3339 com offset explícito, preferencialmente UTC;
- identificadores são strings opacas e não transportam autorização;
- enums públicos usam códigos estáveis em português quando representam estados do Titan;
- campos monetários, medidas e coordenadas não usam ponto flutuante sem contrato explícito de precisão;
- campo ausente, `null` e coleção vazia não são semanticamente equivalentes por padrão.

## Erros

Erros HTTP utilizam `application/problem+json` conforme RFC 9457.

Cada resposta preserva, quando seguro e aplicável:

- `type` estável;
- `title` estável e legível;
- `status` igual ao status HTTP;
- `detail` seguro e não interpretado por máquinas;
- `instance` ou identificador opaco da ocorrência;
- código de razão estável em português;
- `correlation_id` seguro.

Erros não incluem stack trace, SQL, nomes internos, tokens, secrets, PII ou indicação que permita distinguir recurso invisível de inexistente. Validação de entrada informa campos de modo minimizado sem ecoar conteúdo sensível.

## Paginação e ordenação

- coleções potencialmente grandes exigem paginação;
- paginação usa cursor opaco vinculado a Organization, Purpose, filtros, ordenação e snapshot quando aplicável;
- cursor não é autorização e é revalidado a cada uso;
- ordenação possui desempate determinístico;
- limite máximo pertence ao perfil do endpoint;
- offset não é contrato padrão para coleções mutáveis;
- resposta informa próximo cursor e limitações, sem prometer total exato quando não calculado.

## Idempotência

Operações de criação ou comando sujeitas a retry aceitam `Idempotency-Key` quando o contrato exigir.

A identidade semântica inclui principal ou capacidade, Organization, Purpose, operação e Digest canônico da intenção. Repetição equivalente retorna o resultado conhecido; reutilização da chave com intenção diferente produz conflito. Resultado desconhecido permanece reconciliável e não é convertido automaticamente em falha.

Retenção da chave é definida pelo perfil e pela maior janela de retry ou replay aplicável.

## Concorrência

Recursos mutáveis expõem versão ou ETag forte quando a operação exigir concorrência otimista. Alteração condicionada usa `If-Match` ou contrato equivalente; precondição falsa não aplica mudança e produz resposta apropriada.

Last-write-wins silencioso é proibido para estado governado.

## Autenticação e autorização

- a API aceita somente credencial prevista pela ADR 0005;
- Presentation não confia em Organization, Roles, Permissions ou Purpose fornecidos pelo cliente;
- Application resolve principal, capacidade e OrganizationContext;
- autorização parcial declara redução explícita;
- autenticação válida não comprova autorização;
- paginação, exportação, filtros e campos derivados permanecem sujeitos à mesma autorização.

## Correlação e observabilidade

O cliente pode fornecer correlation ID em formato e tamanho aceitos, mas o valor é não confiável. A API gera ou normaliza identificador seguro e o propaga sem copiar payloads para logs.

Request ID, correlation ID, IdempotencyKey e Event ID são conceitos distintos.

## OpenAPI e compatibilidade

- OpenAPI gerado integra o contrato verificável;
- exemplos usam somente dados fictícios;
- testes detectam remoção ou incompatibilidade não aprovada;
- documentação distingue endpoint público, autenticado, administrativo e técnico;
- Swagger ou console técnico usa cliente OIDC próprio quando autenticação for adicionada.

## Critérios de aceite

- primeiro endpoint respeita versionamento ou exceção técnica declarada;
- erros usam Problem Details sem vazamento;
- listas grandes têm paginação determinística;
- retries não duplicam efeitos quando idempotência for exigida;
- concorrência rejeita versão obsoleta;
- recurso invisível não é enumerável;
- OpenAPI e testes cobrem contrato positivo e negativo;
- tipos HTTP não atravessam Presentation.

## Consequências

As convenções aumentam consistência e permitem testes de compatibilidade. Em contrapartida, exigem disciplina de contratos e tornam mudanças públicas deliberadas. Nenhuma convenção autoriza criar abstração universal antes de existir o primeiro consumidor.

## Referências

- [RFC 9457 — Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html), consultada em 21 de julho de 2026.
- [RFC 9110 — HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html), consultada em 21 de julho de 2026.
