# ADR 0020 — Integrações externas e validação de fontes
**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan precisará consultar registros oficiais, parceiros autorizados, serviços de certificados, documentos e outras fontes para sustentar validações. Disponibilidade, contrato, identidade, cobertura e qualidade dessas fontes variam e podem mudar sem controle do Titan.

A ADR 0015 já define SourceProfile, SourceSnapshot, ValidationRequest, ValidationAttempt, ValidationAssessment, freshness, conflito e admissibilidade. Esta ADR não cria um segundo modelo de proveniência ou validação. Ela define a fronteira pela qual a Application solicita observações externas e a Infrastructure adapta protocolos concretos.

Integração não é prova de verdade. Resposta autenticada comprova comunicação com o sistema identificado dentro das evidências disponíveis; não confirma automaticamente correção, completude, autoridade jurídica ou adequação para uma Decision.

## Problema

Definir:

- como consultar fontes externas sem acoplar Core ou Application a APIs específicas;
- como autorizar e minimizar dados enviados e recebidos;
- como preservar contrato, request, response, temporalidade e resultado técnico;
- como tratar respostas parciais, divergentes, indisponíveis ou desconhecidas;
- como executar retry, idempotência, rate limiting, cache e reconciliação com segurança;
- como testar integrações antes da disponibilidade de fontes reais.

## Princípios

1. **Adapter não decide o domínio:** transporte observa; Application avalia; Policy decide admissibilidade.
2. **Contrato explícito:** toda chamada usa SourceProfile e contrato versionados.
3. **Menor divulgação:** somente dados autorizados e necessários atravessam a fronteira.
4. **Resultado técnico não é resultado de negócio:** HTTP, assinatura ou sucesso do provider não aprovam objeto.
5. **Incerteza preservada:** parcialidade, indisponibilidade e resultado desconhecido permanecem distintos.
6. **Histórico reproduzível:** a observação usada por uma Decision não depende do estado mutável atual da fonte.
7. **Substituição por semântica:** providers podem mudar sem reduzir as garantias do contrato interno.
8. **Desconhecido não é negativo:** ausência de confirmação ou resultado desconhecido nunca é convertido automaticamente em inexistência, rejeição, invalidade ou falha de negócio.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Core chama APIs diretamente | Pouco código inicial | Acopla domínio a protocolo, fornecedor e payload |
| Modelo único igual ao JSON externo | Mapeamento simples | Mudanças externas atravessam todo o sistema |
| ETL periódico como única integração | Bom para volume | Frescor e finalidade por operação ficam imprecisos |
| Porta estável e adapters por Source | Isolamento, testes e substituição | Exige mapeamento, contrato e observabilidade |
| Broker como interface universal | Desacoplamento operacional | Não representa sozinho consulta, resposta ou autorização |

## Decisão

A Application utilizará uma porta `ExternalEvidenceProvider` para obter uma observação externa delimitada por ValidationRequest autorizada.

A porta retorna resultado técnico normalizado suficiente para criar ValidationAttempt e SourceSnapshot. ValidationAssessment, ConfidenceAssessment, FreshnessAssessment, conflito, admissibilidade e Decision continuam fora do adapter.

Cada Source concreta possui adapter na Infrastructure. O Core não conhece endpoint, verbo HTTP, JSON, SOAP, SDK, certificado cliente, segredo, código do fornecedor ou estratégia de retry.

## Gramática arquitetural

Esta integração preserva a gramática transversal do Titan: `Request → Attempt → Assessment → Decision`, sustentada por `Evidence` e, quando aplicável, apresentada por `Report`.

Cada etapa responde a uma pergunta própria e não substitui a anterior. Request expressa intenção delimitada; Attempt registra execução; Assessment interpreta material; Decision produz efeito autorizado; Evidence sustenta afirmações; Report apresenta escopo e limitações.

## ExternalEvidenceProvider

Contrato conceitual da porta:

```text
validate(
    request: ExternalValidationRequest,
    context: AuthorizedExternalAccessContext
) -> ExternalValidationResult
```

Os nomes são contratos arquiteturais da Application, não novas entidades obrigatórias do Domain.

`ExternalValidationRequest` projeta somente:

- ValidationRequest e ValidationScope resolvidos;
- SourceProfile e versão;
- contrato e versão esperados;
- finalidade, OrganizationContext e ProcessingContext autorizados;
- campos mínimos permitidos;
- instante de referência e requisito de freshness;
- CorrelationId e IdempotencyKey aplicáveis.

`AuthorizedExternalAccessContext` é produzido pela Application depois da autenticação e Authorization. O adapter não aceita livremente Organization, Purpose, fields ou endpoint enviados pelo cliente.

`ExternalValidationResult` preserva conceitualmente:

- provider e versão do contrato executado;
- instantes solicitado, enviado, recebido e registrado;
- request e response Digests;
- campos confirmados, divergentes, ausentes e não avaliados, quando tecnicamente determináveis;
- estado técnico, freshness declarada e limitações;
- referência opaca ao material bruto autorizado;
- metadados de retry, rate limit e correlação;
- evidências de autenticação da Source, sem secrets.

O resultado não contém conclusão de verdade, confiança, admissibilidade, conformidade, elegibilidade ou efeito jurídico.

## Resolução do provider

A Application resolve SourceProfile e capacidade necessária. A Infrastructure seleciona adapter previamente configurado para esse perfil.

Provider, endpoint e credencial não são escolhidos pelo payload. Redirecionamentos, hosts, certificados e destinos permitidos seguem configuração confiável e allowlist para reduzir SSRF, exfiltração e substituição de Source.

Uma Source pode possuir mais de um provider aprovado. Fallback somente ocorre quando Policy e perfil declararem equivalência de finalidade, contrato, autoridade e qualidade. Troca automática não transforma fontes diferentes em corroboradoras nem oculta qual fonte respondeu.

## Contratos e mapeamento

O adapter traduz o contrato externo para o contrato interno sem transportar semântica implícita.

Cada mapeamento versionado declara:

- campos externos e internos;
- unidades, códigos, calendários e timezone;
- obrigatoriedade, nulidade e valores desconhecidos;
- regras de normalização e serialização;
- precisão, truncamento e arredondamento;
- paginação, ordenação e fronteira de cobertura;
- compatibilidade com versões anteriores;
- limitações conhecidas.

`MappingVersion` identifica uma versão imutável da tradução entre contrato externo e interno. Preserva provider, schema externo, regras, parser compatível, validade, aprovação e Digest. Mudança de significado cria nova MappingVersion; correção não reescreve resultados históricos.

Campo desconhecido não vira zero, vazio, falso ou confirmado. Código novo ou versão não suportada produz resultado explícito e não é interpretado pelo adapter por aproximação silenciosa.

Mudança incompatível do contrato exige nova versão do mapeamento e testes. Suporte antigo permanece enquanto houver requests pendentes, snapshots, quarentena ou replay que dependam dele.

`ContractCompatibilityAssessment` avalia versões delimitadas do contrato e do mapping como `COMPATIVEL`, `PARCIAL`, `INCOMPATIVEL` ou `DESCONHECIDA`. Preserva diferenças, campos afetados, capacidades, testes, Evidence, limitações, assessor e instante. Compatibilidade estrutural não comprova equivalência semântica; resultado parcial não autoriza interpretar campos não avaliados.

## Capacidades da Source

`SourceCapabilities` é declaração versionada e comprovável das capacidades de um SourceProfile e contrato, como snapshot consistente, paginação estável, filtros, assinatura, idempotência, consulta de status, callback, rate limit, freshness e limites de lote.

Capacidade não é presumida nem reutilizada em outra versão. Infrastructure a observa; Application decide se é suficiente para a ValidationRequest. Ausência de capacidade necessária produz limitação, revisão ou negação segura conforme Policy.

## Autorização, finalidade e minimização

Antes da chamada, a Application verifica principal, capacidade, Organization atuante, Purpose, Permission, AuthorizationGrant, FieldScope, DataContract, classificação, ProcessingActivity e Policy.

A autorização efetiva usa a menor restrição aplicável. Permissão para consultar internamente não implica permissão para enviar à Source, persistir resposta bruta, compartilhar, exportar ou reutilizar para treinamento de IA.

O request externo contém apenas identificadores e campos indispensáveis. Dados não autorizados são removidos antes do adapter. Logs, traces, métricas e mensagens não contêm token, secret, payload integral ou atributo pessoal.

Resposta recebida também passa por minimização, classificação, retenção e contrato antes da persistência ou exposição.

## Tentativa, snapshot e avaliação

Cada chamada cria ValidationAttempt correlacionada. O material observado gera SourceSnapshot imutável quando houver conteúdo preservável, incluindo versão do contrato, Digests, escopo, instantes e limitações.

O snapshot protege o que foi observado naquele instante. Consulta posterior cria novo snapshot; não reescreve o anterior nem a Decision que o utilizou.

Application transforma resultados técnicos em ValidationAssessment por campo. Campo não retornado permanece ausente ou não avaliado conforme contrato. Resposta parcial nunca é apresentada como confirmação integral.

## Estados técnicos e resultado desconhecido

Estados seguem a ADR 0015: `PENDENTE`, `CONCLUIDA`, `FONTE_INDISPONIVEL`, `RESULTADO_DESCONHECIDO`, `NAO_SUPORTADA`, `FALHA_TRANSITORIA` e `FALHA_PERMANENTE`.

Falha de comunicação após envio pode significar que a fonte recebeu ou processou a solicitação. `RESULTADO_DESCONHECIDO` não é sucesso nem falha confirmada.

O estado desconhecido preserva janela, efeitos possíveis, reconciliação e Evidence. Nenhuma projeção pode convertê-lo silenciosamente em resultado negativo para encerrar o fluxo.

Retry:

- preserva a ValidationRequest e sua IdempotencyKey;
- cria nova ValidationAttempt correlacionada;
- respeita backoff, jitter, limite e orientação confiável de rate limit;
- não altera payload ou escopo para obter resposta;
- não apaga tentativa anterior nem possível efeito externo.

Quando a operação externa puder produzir efeito, retry automático exige idempotência comprovada pelo contrato. Sem essa garantia, a operação vai para reconciliação ou revisão segura.

Resultado desconhecido permanece reconciliável por consulta de status, chave externa autorizada, callback autenticado ou procedimento específico do provider. Ausência de resultado na reconciliação não prova ausência de processamento.

## Cache e freshness

Cache é otimização da Infrastructure e não fonte de verdade. Cada entrada é vinculada a SourceProfile, contrato, ValidationScope, Purpose permitido, classificação, Organization aplicável, instante observado e prazo.

O uso do cache deve ser autorizado pelo FreshnessProfile e DataContract. Cache expirado não é renovado por indisponibilidade da Source. Resposta armazenada para uma Organization, Purpose ou escopo não é reutilizada fora deles.

Invalidação não reescreve snapshots históricos. Dado altamente sensível pode proibir cache ou exigir armazenamento criptografado e isolado.

## Paginação, lote e completude

Integrações paginadas ou em lote registram cursor, fronteira, ordenação, páginas esperadas e obtidas, contagens, duplicidades, omissões e truncamento.

Conclusão completa exige comprovação da fronteira declarada. Limite de página, timeout, falta de autorização ou interrupção resulta em cobertura parcial ou indeterminada, nunca em lista vazia conclusiva.

Mudança concorrente na Source durante paginação é registrada. Quando o provider não oferecer snapshot ou cursor consistente, a limitação acompanha SourceSnapshot e ValidationAssessment.

## Callbacks e material recebido

Webhook ou callback é entrada não confiável até validação. Infrastructure verifica canal, assinatura ou autenticação aplicável, replay, timestamp, tamanho, formato e correlação antes de produzir tentativa ou Evidence.

`ReplayProtectionEvidence` registra, quando aplicável, nonce ou identificador não secreto, timestamp observado, Digest, janela aceita, mecanismo, resultado e limitações. Comprova somente a execução do controle declarado, não unicidade universal ou ausência de replay fora da janela.

Callback válido tecnicamente não amplia escopo, não cria Authorization e não decide o domínio. Evento sem correlação suficiente permanece em quarentena observável; não é ligado por email, nome ou coincidência fraca.

Uploads e respostas brutas são tratados como Artifact ou Document. Parsing ocorre em ambiente restrito, com limites de tamanho, tipo e recursos. Conteúdo recebido nunca escolhe livremente URL, caminho, parser, algoritmo ou credencial.

`ParsingAssessment` preserva origem, parser e versão, MappingVersion, formatos esperado e detectado, campos produzidos, warnings, erros, conteúdo ignorado, limites, resultado e Evidence. Parsing bem-sucedido comprova somente interpretação técnica; não confirma verdade ou correção do conteúdo.

## Credenciais e identidade técnica

Secrets pertencem à Infrastructure e a mecanismo apropriado de gestão de secrets. Não entram em Domain, banco de negócio, payload, Outbox, log ou relatório.

Credenciais são separadas por ambiente, finalidade e provider, possuem menor privilégio, rotação e revogação. ServiceIdentity executora é auditada sem substituir Actor e Organization originadores.

Falha de autenticação técnica não é apresentada como inexistência ou invalidade do objeto consultado.

## Observabilidade e auditoria

Cada tentativa registra correlação, adapter, contrato, duração, resultado seguro, retry, rate limit e volume, sem conteúdo protegido.

Métricas distinguem indisponibilidade, timeout, contrato incompatível, resposta parcial, autenticação, autorização, resultado desconhecido e falha de parsing.

DataAccessRecord é produzido quando a chamada ou resposta configurar acesso sensível segundo ADR 0019. Aceitação pelo broker ou conclusão do adapter não comprova processamento, entrega a destinatário ou efeito de negócio.

## Testabilidade

Toda integração começa com adapter determinístico de teste e fixtures sintéticas. O contrato deve ser validado sem credenciais ou dependência da Source real.

Testes de contrato cobrem:

- resposta válida, parcial, vazia, malformada e incompatível;
- compatibilidade completa, parcial, incompatível e desconhecida;
- SourceCapabilities ausente, alterada ou insuficiente;
- campos novos, ausentes, nulos e códigos desconhecidos;
- timeout antes e depois do envio;
- retry, duplicidade, rate limit e resultado desconhecido;
- paginação truncada, repetida e alterada concorrentemente;
- autenticação inválida, callback repetido e assinatura incorreta;
- replay fora da janela ou com Digest divergente;
- parser novo alterando resultado histórico ou ocultando warnings;
- minimização de request, response, logs e traces;
- isolamento entre Organizations, Purposes e ambientes;
- cache expirado, escopo incompatível e Source indisponível;
- adapter tentando ampliar ValidationScope ou produzir Decision;
- material malicioso, oversized ou direcionando URL arbitrária.

Sandbox do provider real, quando existir, complementa e não substitui testes locais. Fixtures não contêm dados pessoais, comerciais ou credenciais reais.

## Fronteiras arquiteturais

Domain conhece Source, Evidence, Provenance e assessments já aprovadas; não conhece `ExternalEvidenceProvider`, HTTP, SDK ou payload externo.

Application define e utiliza a porta, resolve autorização, perfil, contrato e finalidade, e coordena assessments.

Infrastructure implementa adapters, credenciais, transporte, parsing, retry, cache, rate limit, reconciliação e material bruto.

Presentation mostra origem, instante, escopo, freshness, estado e limitações, sem expor contrato técnico ou campo não autorizado.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Core desacoplado; providers substituíveis; testes locais; evidência histórica; falhas explícitas |
| Negativas | Mapeamentos versionados; maior esforço de fixtures, reconciliação, segurança e monitoramento |

## Riscos e controles

| Risco | Controle |
|---|---|
| API externa virar modelo do Core | Porta e tradução na Infrastructure |
| Resposta autenticada virar verdade | Assessment e admissibilidade separadas |
| Provider alternativo alterar semântica | Equivalência aprovada e origem explícita |
| Retry duplicar efeito externo | Idempotência comprovada ou reconciliação |
| Paginação parcial parecer completa | Cobertura e limitações obrigatórias |
| Vazamento em request ou telemetria | Minimização e testes negativos |
| Cache cruzar Organization ou Purpose | Chave e autorização contextualizadas |
| Payload atacar infraestrutura | Allowlist, limites, parsing restrito e quarentena |

## Critérios de aceitação

A ADR pode ser aceita quando:

- reutilizar os conceitos da ADR 0015 sem modelo paralelo;
- Core e Domain permanecerem independentes de APIs e providers;
- Application controlar Authorization, Purpose, escopo e minimização;
- adapter não decidir confiança, admissibilidade ou negócio;
- contrato e mapeamento forem explícitos e versionados;
- MappingVersion possuir identidade imutável e compatibilidade ser avaliada;
- SourceCapabilities forem versionadas e não presumidas;
- requests, responses, snapshots e tentativas forem correlacionáveis;
- parcialidade, ausência, indisponibilidade e resultado desconhecido permanecerem distintos;
- retry não presumir idempotência nem apagar tentativa anterior;
- paginação e lote declararem cobertura e truncamento;
- cache respeitar freshness, Organization, Purpose, classificação e contrato;
- callbacks e material externo forem tratados como não confiáveis;
- replay e parsing produzirem Evidence e assessments delimitadas;
- secrets e dados protegidos não aparecerem em domínio, logs ou mensagens;
- provider falso e fixtures sintéticas permitirem testes determinísticos;
- nenhuma Source concreta, schema, API ou produto seja escolhido nesta decisão.

## O que esta ADR não decide

Esta ADR não escolhe:

- SISBOV, GTA, MAPA, CAR, MapBiomas ou provider concreto;
- endpoint, protocolo, SDK, formato, credencial ou contrato comercial;
- banco, tabela, fila, worker, scheduler ou tecnologia de cache;
- regra de negócio, verdade material, confiança ou efeito jurídico;
- integração bidirecional de comando com efeito externo específica.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída. Depois da adoção, nova decisão preserva contratos internos, versões de mapeamento, ValidationRequests, ValidationAttempts, SourceSnapshots, Digests, correlações, resultados desconhecidos, quarentenas e Evidences históricas.

Troca de provider cria nova configuração e, quando necessário, nova versão de SourceProfile. Não reinterpreta respostas antigas, elimina limitações nem promove equivalência não demonstrada.
