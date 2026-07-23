# ADR 0039 — Contrato público da API de verificação externa

**Status:** Aceita
**Data:** 23 de julho de 2026
**Decisores:** fundador e responsável pela arquitetura do Titan

## Contexto

A ADR-0010 estabeleceu o modelo híbrido de verificação externa: `VerificationBundle` imutável e autossuficiente, complementado por API de verificação explicável. Ela encerrou dizendo explicitamente que **"URL, métodos e schemas públicos serão definidos em ADR de contratos antes da implementação"**, deixando o contrato HTTP fora do seu escopo.

O Passo 7.6 entregou o pacote e o `BundleVerifier` puro em `packages/core_domain/verification.py`, com dimensões independentes, lacunas declaradas e ponto exato de falha. O Passo 7.7 precisa expor essa semântica como contrato público sem reduzi-la, sem prometer mais do que ela prova e sem criar uma superfície que revele mais do que deve.

Esta ADR define esse contrato. Ela **preserva a interpretação das verificações já implementadas** e não altera conclusões anteriores, mas **amplia o modelo de relatório**: acrescenta os estados `NAO_APLICAVEL` e `NAO_EXECUTADA` e a oitava dimensão declarativa `REVOGACAO_ATUAL`, que permanece não executada no perfil offline. Afirmar que nada muda no domínio seria falso — o que não muda é o significado do que já era avaliado.

## Onde a confiança realmente reside

Esta é a distinção mais importante da ADR, e a razão de ela existir:

```text
verificador local (BundleVerifier)
    elimina dependência do Titan
    o terceiro inspeciona ou controla a implementação

API pública hospedada
    oferece conveniência
    exige confiar na instância verificadora
```

Quem chama a API precisa confiar que o servidor executou o algoritmo declarado, não adulterou o resultado, usou a versão informada, não omitiu falhas, não substituiu âncoras e não reteve o pacote. **Nenhuma dessas garantias é demonstrável pela própria resposta.**

Portanto: o pacote permanece verificável independentemente do Titan **por meio do verificador local**. A API pública transporta a mesma semântica, mas sua resposta depende da confiança na instância utilizada. A independência é propriedade do formato, não do serviço.

## O que uma assinatura válida realmente prova

Verificar uma assinatura com uma chave fornecida pelo próprio chamador **não demonstra que essa chave pertence legitimamente ao emissor alegado**.

A API demonstra que a assinatura confere contra a âncora que o chamador decidiu fornecer. Ela **não** demonstra que a chave pertence ao Titan, que pertence à organização alegada, nem que estava autorizada no instante da emissão.

Um chamador pode montar pacote falso, par de chaves próprio e âncora correspondente, e obter assinatura criptograficamente válida. Isso não é vulnerabilidade **desde que o resultado seja descrito honestamente** — por isso `trust_anchors_used` sempre declara `"origin": "CALLER_SUPPLIED"` e toda resposta com assinatura avaliada carrega a limitação `SIGNATURE_VALID_ONLY_AGAINST_CALLER_SUPPLIED_ANCHOR`.

A dimensão `ASSINATURA` cobre apenas a conferência criptográfica. O vínculo de identidade e legitimidade da chave **não é estabelecido por este contrato**, porque a instância não mantém trust store própria.

## O material submetido é revelado

O endpoint não consulta nem revela registros adicionais mantidos pelo Titan. Contudo, **o material submetido é disponibilizado à instância verificadora**, que pode observar conteúdo do dossiê, dados pessoais, informações comerciais, identificadores, documentos, endereços, geometrias, metadados de propriedade, âncoras fornecidas, endereço IP e horário da consulta.

Requisito explícito, que deve constar também da documentação pública:

> Pacotes sensíveis não devem ser enviados a uma instância pública não confiável. Nesses casos, utilize o verificador local.

## Requisitos e Princípios

1. **Nunca um booleano.** A resposta expõe cada dimensão separadamente e um agregado calculado por regra pública. Não existe campo `valid: true`.
2. **Validade não é veracidade.** Integridade verificada não afirma verdade do conteúdo, conformidade regulatória atual nem ausência de dados fora do escopo.
3. **Histórico e atual são separados.** A verificação descreve o material incluído e o instante de referência declarado. Estado atual de revogação e de publicação **não é consultado** e aparece como dimensão `NAO_EXECUTADA`.
4. **Verificação hermética.** O modo público não realiza acesso à rede, ao sistema de arquivos externo, ao banco de domínio nem resolve URLs, URIs, caminhos, entidades XML, links de certificado ou nomes de bucket declarados pelo pacote ou pelas âncoras. Sem isso o endpoint viraria vetor de SSRF, leitura local, varredura interna e vazamento por DNS, além de perder determinismo.
5. **Âncoras vêm do chamador.** Âncora contida no pacote nunca é confiada por estar nele. Sem âncora fornecida, a dimensão de assinatura é `INDETERMINADA`.
6. **Nenhum algoritmo é escolhido por dado do pacote.** O algoritmo efetivo é a interseção entre o declarado pelo pacote, a allowlist do contrato e o tipo de âncora compatível.
7. **Erro de contrato não é resultado de verificação.** Material que não pode ser representado como `VerificationBundle` produz `problem+json`; material representável cujas propriedades não conferem produz relatório.
8. **Consulta por identificador é operação distinta.** Recuperar dossiê ou pacote do Titan por identificador exige autenticação, `OrganizationContext` e `Authorization`, e não faz parte deste contrato.
9. **Credencial de acesso não é autorização de domínio.** O contrato não exige identidade Titan nem autorização sobre Organizations ou registros. Uma implantação pode exigir credencial de acesso, API key ou proteção de gateway **exclusivamente para controle de abuso**, sem conceder acesso a dados de domínio e sem alterar a semântica da verificação. Ausência de autenticação de usuário não implica disponibilidade ilimitada.
10. **Integração por campos estruturados.** `reason_code`, `dimension`, `status` e códigos de limitação são contrato. `detail`, `warnings` e textos são explicativos, podem ser localizados e não constituem contrato lógico.

## Alternativas Consideradas

### Opção A — Endpoint que verifica material submetido (Adotada)

`POST /v1/verification/bundles` recebe o pacote exportado e devolve o relatório dimensional.

- *Vantagens:* um terceiro de posse do pacote confere sem conta e sem acesso ao banco. Não consulta registros internos. Complementa o verificador local sem substituí-lo.
- *Desvantagens:* revela o pacote ao operador, exige controles de abuso e não dispensa confiança na instância.

### Opção B — Endpoint autenticado que verifica por identificador

`GET /verification/dossiers/{id}` recupera do banco e verifica.

- *Vantagens:* conveniente para clientes internos.
- *Desvantagens:* **não é verificação externa.** Depende do Titan estar de pé, acessível e íntegro — a dependência que o pacote existe para eliminar. Exige autorização e revela existência de registros.

### Opção C — Somente verificação local

- *Vantagens:* superfície zero, confidencialidade máxima.
- *Desvantagens:* exclui quem não pode executar a biblioteca; a ADR-0010 previu a API no modelo híbrido.

**Decisão:** adotar a Opção A, descrita honestamente como conveniência. A Opção C permanece o caminho recomendado para material sensível. A Opção B pode surgir depois como contrato separado e autenticado.

## Contrato

### Endpoint e versionamento

```text
POST /v1/verification/bundles
Content-Type: application/json
```

O caminho carrega a versão. Mudança incompatível exige nova URL ou novo media type; o campo `contract_version` no corpo **não autoriza** o servidor a alterar o schema silenciosamente.

Três versões distintas, com ciclos independentes:

| Campo | Significa |
|---|---|
| `contract_version` | formato da API |
| `verification_profile` | regras de interpretação do pacote |
| `engine.version` | implementação concreta |

Correção de segurança no motor não cria nova versão de contrato.

### Dimensões

Os nomes são exatamente os do domínio (`VerificationDimension`), sem taxonomia paralela:

| Dimensão | Verifica | Obrigatória no agregado |
|---|---|---|
| `ESTRUTURA` | manifesto e inventário consistentes; nada não declarado | sim |
| `SERIALIZACAO` | perfil de canonicalização conhecido | sim |
| `INTEGRIDADE` | digest do manifesto e dos componentes | sim |
| `ASSINATURA` | assinatura sob âncora fornecida | sim |
| `TEMPORAL` | âncora temporal do material incluído | sim |
| `REVOGACAO` | material de revogação **incluído no pacote** | sim |
| `COBERTURA` | escopo declarado e lacunas | sim |
| `REVOGACAO_ATUAL` | estado atual em fontes externas | não — sempre `NAO_EXECUTADA` |

### Regra da dimensão `REVOGACAO`

Ausente **nunca** é convertido automaticamente em `NAO_APLICAVEL`:

```text
perfil exige material e ele está ausente     → INDETERMINADA (ou INVALIDA
                                                conforme o contrato do pacote)
tipo de assinatura sem mecanismo de revogação → NAO_APLICAVEL
material presente mas inconclusivo            → INDETERMINADA
demonstra revogação no instante relevante     → INVALIDA
demonstra não revogação no instante relevante → VALIDA
```

### Governança de `NAO_APLICAVEL`

A aplicabilidade de uma dimensão é determinada pelo `verification_profile`, pelo tipo do pacote e por regras do verificador — **nunca por declaração livre do pacote ou do chamador**. Um pacote que declare `ASSINATURA` como não aplicável não faz o verificador ignorar assinatura quando o perfil a exige. Sem isso, bastaria declarar-se inaplicável para escapar do agregado.

### Estados por dimensão

```text
VALIDA          confirmada
INVALIDA        violação determinística
INDETERMINADA   avaliada, evidência insuficiente
NAO_APLICAVEL   fora do escopo declarado deste pacote
NAO_EXECUTADA   fora do modo de verificação, não foi avaliada
```

`INDETERMINADA` e `NAO_EXECUTADA` são diferentes e não devem ser fundidas: a primeira tentou e não concluiu; a segunda nem fazia parte do modo.

### Regra do agregado

Determinística, pública e versionada. Clientes **não** devem reconstruí-la:

```text
sobre as dimensões OBRIGATÓRIAS:
    se alguma = INVALIDA                       → agregado = INVALIDA
    senão se alguma = INDETERMINADA            → agregado = INDETERMINADA
    senão se alguma = NAO_EXECUTADA            → agregado = INDETERMINADA
    senão se alguma = NAO_APLICAVEL sem
         permissão expressa do perfil          → agregado = INDETERMINADA
    senão                                      → agregado = VALIDA

sobre as dimensões NÃO OBRIGATÓRIAS (ex.: REVOGACAO_ATUAL):
    NAO_EXECUTADA não afeta o agregado,
    mas aparece sempre e gera entrada em `limitations`.

warnings não alteram o agregado.
lacuna declarada torna COBERTURA = INDETERMINADA,
logo o agregado não é VALIDA quando há lacuna.
ausência de âncora torna ASSINATURA = INDETERMINADA,
logo o agregado não é VALIDA sem âncora fornecida.
```

**Nenhuma dimensão obrigatória não avaliada pode resultar em agregado válido.** Esta é a defesa contra o pior erro possível do contrato: declarar um pacote `VALIDA` sem ter verificado sua assinatura. A regra fecha o caminho, e a reclassificação de "algoritmo não suportado" como `INDETERMINADA` fecha o outro.

### Ordem de avaliação e `first_failure`

Todas as dimensões aplicáveis são avaliadas; nenhuma é abandonada por curto-circuito. `first_failure` é a primeira falha segundo a **ordem normativa pública e versionada**:

```text
ESTRUTURA → SERIALIZACAO → INTEGRIDADE → ASSINATURA → TEMPORAL → REVOGACAO → COBERTURA
```

Assim otimização interna ou paralelização não alteram a resposta. `failures` traz todas; `first_failure` é conveniência derivada.

`failure` refere-se **exclusivamente** a dimensões `INVALIDA`. Resultados `INDETERMINADA` aparecem em `dimensions`, `gaps` e `warnings`, sem serem artificialmente classificados como falha. Logo, um agregado `INDETERMINADA` sem nenhuma dimensão inválida devolve `"failures": []` e `"first_failure": null` — o que é resultado correto, e não omissão.

### Âncoras de confiança

```json
{
  "trust_anchors": [
    {
      "anchor_id": "chave-1",
      "anchor_type": "PUBLIC_KEY",
      "algorithm": "ED25519",
      "encoding": "BASE64URL",
      "value": "...",
      "purpose": "BUNDLE_SIGNATURE"
    }
  ]
}
```

- `anchor_id` duplicado é erro de contrato (`422`), nunca resolução silenciosa.
- Máximo de 8 âncoras; 8 KiB por âncora.
- Algoritmos permitidos por allowlist do contrato.
- A resposta devolve **fingerprint, nunca o valor**.

### Resposta `200`

```json
{
  "contract_version": "1.0",
  "verification_profile": "titan-bundle-verification-v1",
  "engine": { "name": "titan-bundle-verifier", "version": "1.0.0" },
  "bundle_reference": { "bundle_id": "...", "bundle_digest": "sha256:..." },
  "aggregate_status": "INVALIDA",
  "verified_at": "2026-07-23T12:00:00Z",
  "reference_instant": "2026-07-20T15:00:00Z",
  "trust_anchors_used": [
    { "origin": "CALLER_SUPPLIED", "anchor_id": "chave-1",
      "algorithm": "ED25519", "fingerprint": "sha256:..." }
  ],
  "declared_scopes": ["INTEGRIDADE", "CONTEUDO_DA_DECISAO"],
  "examined_components": ["dossier.json"],
  "dimensions": [
    { "dimension": "INTEGRIDADE", "status": "INVALIDA",
      "reason_code": "DIGEST_DIVERGENTE",
      "failure_point": "dossier.json",
      "parameters": { "component": "dossier.json" },
      "detail": "…" }
  ],
  "failures": [ { "dimension": "INTEGRIDADE", "reason_code": "DIGEST_DIVERGENTE",
                  "failure_point": "dossier.json" } ],
  "first_failure": { "dimension": "INTEGRIDADE", "reason_code": "DIGEST_DIVERGENTE",
                     "failure_point": "dossier.json" },
  "gaps": [],
  "warnings": [],
  "limitations": [
    { "code": "CONTENT_TRUTH_NOT_ASSERTED" },
    { "code": "CURRENT_REVOCATION_NOT_CHECKED" },
    { "code": "RESULT_DEPENDS_ON_VERIFIER_INSTANCE" },
    { "code": "SIGNATURE_VALID_ONLY_AGAINST_CALLER_SUPPLIED_ANCHOR" }
  ]
}
```

`bundle_digest` é calculado sobre a **representação canônica do `VerificationBundle`**, excluindo as `trust_anchors` da requisição e qualquer metadado HTTP. Assim o mesmo pacote produz a mesma referência independentemente das âncoras usadas para verificá-lo.

Enums em caixa alta; apresentação e idioma são responsabilidade do cliente.

`200` também para `INVALIDA`: a requisição foi processada com sucesso e o resultado é a resposta. Usar `4xx` confundiria erro de protocolo com resultado de verificação.

### Fronteira entre erro e resultado

```text
Se o material NÃO pode virar entrada do BundleVerifier → erro de contrato.
Se PODE e o verificador conclui que não confere      → relatório de verificação.
```

| Situação | Resposta |
|---|---|
| JSON sintaticamente inválido | `400 MALFORMED_JSON` |
| JSON válido, mas `bundle` ausente ou tipo incorreto | `422 MALFORMED_REQUEST` |
| Estrutura não interpretável como pacote | `422 MALFORMED_BUNDLE` |
| `anchor_id` duplicado | `422 DUPLICATE_ANCHOR_ID` |
| Versão de pacote não suportada | `422 UNSUPPORTED_BUNDLE_VERSION` |

A versão do contrato é selecionada pela URL `/v1`. Caminho inexistente produz `404`; não existe `UNSUPPORTED_CONTRACT_VERSION` no corpo, porque a requisição não declara versão de contrato.
| Algoritmo de assinatura não suportado | `200` com `ASSINATURA = INDETERMINADA`, razão `ALGORITMO_NAO_SUPORTADO_PELO_VERIFICADOR` |
| Digest divergente, payload ausente, âncora não fornecida, cadeia incompleta | `200` com relatório |

Algoritmo não suportado **não** é pacote malformado: o pacote é legítimo, apenas este motor não sabe avaliá-lo. E **não** é `NAO_EXECUTADA`: houve tentativa de avaliação e o motor não teve capacidade, o que é exatamente `INDETERMINADA`. `NAO_EXECUTADA` fica reservada a dimensões genuinamente fora do modo contratado, como `REVOGACAO_ATUAL`.

### Limites operacionais

| Limite | Valor |
|---|---|
| Corpo | 1 MiB |
| Componentes | 32 |
| Componente individual | 512 KiB |
| Profundidade JSON | 32 |
| Âncoras | 8 |

Propriedades duplicadas em JSON são rejeitadas. Propriedades desconhecidas no nível superior são rejeitadas; extensões vivem em namespace próprio.

Respostas adicionais, sempre em `application/problem+json`:

```text
413 Payload Too Large
429 Too Many Requests
503 Service Unavailable
```

### Privacidade, logs e retenção

- Corpo da requisição **não é registrado em log**.
- **Nenhuma retenção** do pacote após a resposta, salvo incidente autorizado.
- Telemetria usa apenas metadados minimizados: código de razão sanitizado, status agregado, latência, tamanho. **Não** registra `failure_point`, nomes de componentes, `detail`, escopos nem `bundle_id`.
- Respostas enviam `Cache-Control: no-store` e `Pragma: no-cache`; caches intermediários não devem armazenar.

A política de não retenção aplica-se à aplicação **e aos componentes operacionais sob controle da instância**: gateway, reverse proxy, WAF, APM, tracing, error tracking, filas, dumps e logs de depuração. O corpo não pode aparecer em log, span, dump ou evento de exceção. Não se promete garantia sobre infraestrutura de terceiros fora do controle do operador — a documentação pública de cada instância deve declarar sua política concreta.

## Impacto no que já foi entregue

O Passo 7.6 definiu `VerificationStatus` com três estados. Esta ADR exige cinco: acrescenta `NAO_APLICAVEL` e `NAO_EXECUTADA`, e acrescenta a dimensão `REVOGACAO_ATUAL`, sempre `NAO_EXECUTADA` no modo offline. A implementação do 7.7 deve estender o domínio, mantendo os testes existentes.

## Verificação automatizada exigida

1. pacote íntegro sem âncora → `ASSINATURA = INDETERMINADA`;
2. âncora contida no pacote não é confiada automaticamente;
3. âncora com algoritmo incompatível;
4. `anchor_id` duplicado → `422`;
5. pacote malformado → `422 problem+json`;
6. digest incorreto → `200` com `INVALIDA`;
7. corpo acima do limite → `413`;
8. rate limit → `429`;
9. URL declarada no pacote não gera acesso externo;
10. nenhum payload aparece em log;
11. resposta contém `Cache-Control: no-store`;
12. todas as dimensões aparecem, inclusive `NAO_EXECUTADA`;
13. agregado é determinístico;
14. `first_failure` não muda com ordem de execução;
15. propriedades duplicadas rejeitadas;
16. profundidade excessiva rejeitada;
17. `detail` sem stack trace nem caminho interno;
18. versão de pacote não suportada segue regra explícita;
19. pacotes iguais geram relatório igual, ignorando `verified_at`;
20. algoritmo não suportado → `ASSINATURA = INDETERMINADA`, não `422` e não `NAO_EXECUTADA`;
21. algoritmo não suportado em dimensão obrigatória **não** permite agregado `VALIDA`;
22. dimensão obrigatória `NAO_EXECUTADA` resulta em agregado `INDETERMINADA`;
23. pacote não consegue declarar dimensão obrigatória como `NAO_APLICAVEL`;
24. assinatura válida sob chave arbitrária retorna a limitação de identidade da âncora;
25. pacote sem material de revogação segue a regra explícita de `REVOGACAO`;
26. JSON sintaticamente inválido retorna `400`;
27. `first_failure` permanece nulo quando o agregado é indeterminado sem dimensão inválida;
28. `bundle_digest` não muda quando apenas as âncoras da requisição mudam;
29. endpoint rejeita `POST` em HTTP sem TLS;
30. gateway, APM e tracing não capturam o corpo.

## Invariantes

- A API pública não consulta dados de domínio nem confirma existência de registros no Titan.
- O pacote submetido é revelado à instância verificadora; verificação confidencial exige execução local ou instância confiável.
- A resposta depende da confiança na instância verificadora. A independência do Titan é garantida pelo formato autossuficiente e pelo verificador local, **não** pela API hospedada pelo próprio Titan.
- Nenhuma âncora é confiável apenas por estar no pacote.
- `ASSINATURA = VALIDA` significa apenas que a assinatura confere contra uma âncora fornecida pelo chamador e compatível com o contrato. **Não afirma** que identidade, propriedade, autorização ou legitimidade institucional da âncora foi verificada.
- Nenhuma dimensão obrigatória não avaliada pode resultar em agregado `VALIDA`.
- A aplicabilidade de uma dimensão é decidida pelo perfil e pelo verificador, nunca por declaração do pacote.
- A API é servida somente sobre HTTPS.
- O modo público é hermético e não resolve referências externas.
- Resultado inválido é resposta bem-sucedida; entrada irrepresentável é erro de contrato.
- O agregado é função determinística e versionada das dimensões aplicáveis.
- Nenhum payload submetido é persistido ou registrado por padrão.
- Nenhum status HTTP ou campo agregado reduz as dimensões a uma conclusão de veracidade ou conformidade.

## Consequências

- Um terceiro verifica um pacote sem conta e sem acesso ao banco, ciente de que confia na instância.
- Quem precisa de independência real usa o verificador local — e a documentação diz isso.
- Material sensível tem orientação explícita de não ser submetido a instância pública.
- A superfície pública permanece mínima: um método, um recurso, nenhuma leitura de banco, nenhum acesso externo.

## Garantia final

A API informa quais propriedades do pacote foram **comprovadas**, **rejeitadas**, permaneceram **indeterminadas** ou **não foram executadas**. Uma assinatura válida significa apenas que ela confere contra a âncora explicitamente fornecida. Nenhuma dimensão obrigatória não avaliada resulta em agregado válido.

## Fora de escopo

`VerificationCode`, QR Code, publicação, revogação de referência online, dimensões atuais que exijam fontes externas, o pacote HTML/Wasm autônomo da ADR-0034 e o contrato autenticado de consulta por identificador.
