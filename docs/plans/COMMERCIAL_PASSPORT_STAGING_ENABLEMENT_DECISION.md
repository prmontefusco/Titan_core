# Commercial Passport — decisão de habilitação controlada em staging

**Data:** 2026-10-13  
**Estado:** PROPOSTA — DECISION RED, aguardando decisão humana explícita  
**Escopo:** habilitação temporária e controlada da consulta dinâmica em ambiente `HOMOLOGACAO`  
**Não autoriza:** publicação, alteração de configuração, emissão formal ou uso de dados reais

## Contexto

Os cortes F1–F13 do Commercial Passport, a pipeline mínima, a população temporal e o rastreio agregado
estão implementados e protegidos por release gates. O próximo passo não é novo BUILD: é decidir se a
consulta dinâmica deve ser exercitada em um ambiente compartilhado antes de qualquer uso produtivo.

A superfície possui duas operações diferentes:

- consulta dinâmica `GET /v1/livestock/properties/{property_id}/commercial-passport`;
- emissão formal `POST /v1/livestock/properties/{property_id}/commercial-passport/issue`.

Somente a consulta dinâmica possui composição produtiva opt-in. A emissão formal continua fail-closed:
`get_commercial_passport_issuance_pipeline()` retorna `None` e a API responde
`503 COMMERCIAL_PASSPORT_ISSUANCE_NAO_HABILITADA`.

## Evidência no repositório

- `apps/api/_registry.py` só publica as rotas quando
  `TITAN_COMMERCIAL_PASSPORT_API_ENABLED=true`;
- `apps/api/livestock_commercial_passport.py` só compõe a consulta quando
  `TITAN_COMMERCIAL_PASSPORT_PIPELINE_ENABLED=true` e todos os metadados da oportunidade são válidos;
- a consulta usa material persistido sob `OrganizationContext` e RLS, devolve `cache-control: no-store`
  e exige `PROPERTY_LER`;
- a emissão exige `DOSSIER_LER`, mas permanece indisponível mesmo quando a rota está publicada;
- `apps/validacao/commercial_passport_api.py --autenticado` descobre Organization e propriedade sem
  copiar identificadores, mostra requisições e respostas e valida autenticação, autorização, ausência de
  disclosure, configuração, projection e comportamento fail-closed;
- a suíte de release gate cobre `401`, `403`, `404`, `405`, `422`, `503`, isolamento por Organization,
  `no-store` e ausência de identificadores individuais na projeção agregada.

## Opções

### A — manter tudo desligado

Preserva o menor risco operacional, mas não produz evidência compartilhada de que autenticação, RLS,
configuração e projeção funcionam fora do ambiente local.

### B — piloto interno somente leitura em homologação

Publica as rotas e habilita apenas a pipeline de consulta dinâmica, com uma oportunidade controlada,
usuários internos e dados exclusivamente fictícios. A emissão formal permanece em `503`.

Vantagens:

- valida o produto construído sem ampliar contrato ou arquitetura;
- mantém o default seguro e rollback imediato por feature flag;
- não cria disclosure externo nem artefato formal que possa ser interpretado como certificado;
- usa o roteiro executável e os gates já existentes.

Limites:

- a projeção reflete apenas a oportunidade configurada;
- resultados de mercados reais continuam condicionados a `NormativeBasis` e regras governadas válidas;
- não comprova prontidão produtiva, capacidade, SLA ou adequação regulatória;
- a observabilidade inicial é operacional e baseada no roteiro, logs HTTP sanitizados e correlação já
  existentes; métricas específicas do Commercial Passport não existem.

### C — habilitar consulta e emissão formal

Não é executável no estado atual. Exigiria novo incremento aprovado para compor a pipeline de emissão,
definir governança do artefato, audiência, retenção, auditoria e rollback. Não deve ser obtida por override,
mock ou alteração direta do dependency provider em staging.

## Recomendação

Adotar a **Opção B**, como piloto interno, temporário e somente leitura em `HOMOLOGACAO`.

## Condições obrigatórias do piloto

1. Ambiente identificado como `HOMOLOGACAO`, isolado de produção.
2. Dados, usuários, propriedades e animais exclusivamente fictícios.
3. Um responsável operacional nomeado para aplicar configuração e executar o roteiro.
4. Um responsável de produto nomeado para avaliar se a projeção é compreensível e útil.
5. Uma oportunidade interna/controlada; não usar nome ou alegação de mercado real sem base normativa
   revisada e publicada.
6. Policy existente e versionada no próprio ambiente; nenhum UUID inventado ou copiado de outro ambiente.
7. Acesso restrito a usuários internos com Membership válido e `PROPERTY_LER`.
8. Emissão formal deve continuar retornando `503 COMMERCIAL_PASSPORT_ISSUANCE_NAO_HABILITADA`.
9. Respostas devem manter `cache-control: no-store`, `pragma: no-cache` e ausência de IDs individuais na
   seção populacional.
10. Nenhum token, segredo, payload pessoal ou identificador real pode ser copiado para logs ou evidências.

## Configuração proposta

Aplicar somente no processo da API de homologação, sem alterar defaults versionados:

```text
TITAN_ENVIRONMENT=HOMOLOGACAO
TITAN_COMMERCIAL_PASSPORT_API_ENABLED=true
TITAN_COMMERCIAL_PASSPORT_PIPELINE_ENABLED=true
TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_CODE=<codigo-interno-controlado>
TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_NAME=<nome-interno-controlado>
TITAN_COMMERCIAL_PASSPORT_PURPOSE=<finalidade-interna-controlada>
TITAN_COMMERCIAL_PASSPORT_POLICY_ID=<uuid-de-policy-existente-na-homologacao>
TITAN_COMMERCIAL_PASSPORT_POLICY_VERSION=<versao-positiva-existente>
TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_KIND=MARKET
```

Valores concretos pertencem à configuração do ambiente e não devem ser commitados neste documento.

## Execução e aceite

1. Confirmar migrations aplicadas e saúde da API, PostgreSQL e Keycloak.
2. Semear apenas massa fictícia e iniciar a API com a configuração proposta.
3. Executar `apps.validacao.commercial_passport_api --autenticado`.
4. Confirmar consulta `200`, rastreio populacional agregado, ausência de IDs individuais e headers
   sensíveis.
5. Confirmar negações `401`, `403`, isolamento uniforme e emissão formal `503`.
6. Registrar no checklist somente o resultado observado, sem copiar tokens ou dados sensíveis.
7. Encerrar o piloto ou mantê-lo habilitado apenas se todos os gates passarem e o responsável de produto
   aceitar a experiência.

## Rollback

Rollback primário: remover ou definir como `false` apenas
`TITAN_COMMERCIAL_PASSPORT_API_ENABLED` e reiniciar a API. As rotas deixam o OpenAPI e voltam a `404`.

Rollback defensivo adicional: remover ou definir como `false`
`TITAN_COMMERCIAL_PASSPORT_PIPELINE_ENABLED`; se a rota permanecer publicada, a consulta volta a
`503 COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO`.

Não há migration, transformação de dados ou artefato formal a reverter neste piloto. Dados fictícios
criados para validação seguem a política operacional do ambiente e não devem ser removidos por comando
destrutivo improvisado.

## Decisão necessária

O Product Owner deve aprovar ou rejeitar explicitamente a **Opção B** e nomear:

- o ambiente de homologação alvo;
- o responsável operacional;
- o responsável de produto.

Sem esses três elementos, as flags permanecem desligadas e nenhuma publicação é executada.
