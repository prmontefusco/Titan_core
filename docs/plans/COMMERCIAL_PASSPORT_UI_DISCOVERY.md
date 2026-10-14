# DISCOVERY — Emissão e download interno do Commercial Passport

**Estado:** PROCEED recomendado — decisão de produto necessária antes do BUILD  
**Data:** 2026-10-14  
**Origem:** continuidade após a persistência byte-idêntica do VerificationBundle

## Contexto

A tela `apps/web/src/pages/CommercialPassport.tsx` hoje consulta apenas a
projeção dinâmica. A API já oferece, separadamente, a emissão formal interna e
a recuperação autenticada do `VerificationBundle` persistido. O próximo corte
pode ligar essas capacidades existentes numa ação explícita da UI, sem criar
regra nova de domínio, nova permissão ou publicação externa.

## Evidência no repositório

- a tela já coleta `property_id`, `reference_time` e `knowledge_cutoff`;
- `POST /v1/livestock/properties/{property_id}/commercial-passport/issue`
  exige `Idempotency-Key` e retorna `verification_bundle_id`;
- `GET /v1/livestock/commercial-passport/verification-bundles/{bundle_id}`
  devolve os bytes persistidos e exige `DOSSIER_LER`;
- o cliente web atual trata apenas JSON e ainda não possui fluxo de download;
- a emissão formal continua desligada por feature gate, portanto a UI deve
  tratar `503` como capacidade indisponível e não assumir que o botão prova a
  habilitação do ambiente.

## Opções

### A — Ação explícita na tela existente (recomendada)

Adicionar um botão “Emitir e baixar bundle” à tela atual. O clique envia a
mesma temporalidade preenchida, cria uma chave de idempotência por tentativa
sem expor a chave ao usuário, recebe o `bundle_id` e então baixa os bytes pela
rota autenticada. O resultado mostra `bundle_id`, digest e estado da operação.

**Trade-offs:** menor superfície e reaproveitamento máximo; a tela passa a
misturar consulta e escrita, exigindo confirmação textual clara de que emitir é
uma operação permanente.

### B — Tela separada de emissão

Criar uma rota/página própria para emissão e manter a consulta somente leitura.

**Trade-offs:** separação conceitual melhor, mas aumenta navegação, código e
testes para uma única operação interna sem benefício funcional atual.

### C — Somente cliente técnico/roteiro

Manter a UI sem emissão e usar apenas o roteiro executável para operadores.

**Trade-offs:** preserva o corte atual, mas não fecha o fluxo operacional que já
foi solicitado para continuidade do produto.

## Salvaguardas obrigatórias no corte recomendado

- nunca emitir automaticamente ao carregar ou consultar a projeção;
- exigir clique explícito e explicar que a emissão cria evidência permanente;
- reutilizar a mesma chave apenas em retry da mesma tentativa;
- baixar exatamente a resposta binária recebida, sem parse/re-serialização;
- não habilitar nenhuma flag de ambiente;
- mapear `401`, `403`, `404`, `409`, `422` e `503` para mensagens seguras;
- cobrir cliente e tela com testes de headers, idempotência, bytes e falhas;
- atualizar o checklist somente quando o comportamento estiver implementado e
  verificado.

## Recomendação

Prosseguir com a opção A, limitada à UI interna já existente. Ela não altera
contratos públicos nem o domínio; apenas consome os dois endpoints aprovados e
preserva a separação entre consulta dinâmica e emissão formal explícita.

## Decisão necessária

Aceitar ou rejeitar a opção A para abrir o BUILD da UI. A aceitação não habilita
as feature flags, não executa emissão em ambiente real e não substitui a
validação manual/homologação posteriormente adiada.
