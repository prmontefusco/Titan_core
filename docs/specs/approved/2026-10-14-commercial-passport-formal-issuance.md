# SPEC aprovada — Emissão formal do Commercial Passport interno

**Estado:** APPROVED  
**Data da decisão:** 2026-10-14  
**Origem:** `docs/plans/COMMERCIAL_PASSPORT_FORMAL_ISSUANCE_COMPOSITION_DISCOVERY.md`

## Objetivo

Permitir a emissão formal, idempotente e auditável de um Commercial Passport de
propriedade para uma única oportunidade comercial interna configurada no servidor,
sem habilitar a funcionalidade em qualquer ambiente durante o BUILD.

## Escopo aprovado

- uma emissão corresponde a uma propriedade e a uma oportunidade configurada;
- a oportunidade deve estar explicitamente marcada para uso interno sintético;
- a emissão exige uma `Decision` cujo subject seja a propriedade, na mesma
  Organization, com `purpose`, `policy_id` e `policy_version` iguais aos da
  oportunidade;
- a `Evaluation` é exclusivamente aquela referenciada pela `Decision` e deve
  possuir os mesmos subject, purpose, Policy e coordenadas temporais solicitadas;
- a `Policy` é exclusivamente a identidade e versão referenciadas por
  `Decision`/`Evaluation`;
- ausência, divergência ou mais de uma `Decision` candidata falha fechado e não
  persiste Dossier;
- não é permitido escolher material por heurística de "mais recente";
- `Idempotency-Key` é obrigatório; a mesma chave e intenção devolvem o mesmo
  resultado, e a reutilização para intenção diferente é conflito;
- projeção, resolução autoritativa, persistência do Dossier, construção do
  VerificationBundle e registro idempotente ocorrem na mesma transação;
- o VerificationBundle continua autocontido e construído em memória, conforme o
  contrato Core atual; este incremento não cria repositório ou tabela para ele.

## Contrato HTTP

O endpoint existente `POST /v1/livestock/properties/{property_id}/commercial-passport/issue`
mantém seu corpo e passa a exigir o header `Idempotency-Key`.

- `200`: emissão concluída ou replay idempotente;
- `409`: chave reutilizada com intenção divergente ou material autoritativo
  ausente/ambíguo/divergente;
- `422`: entrada sintaticamente ou temporalmente inválida;
- `503`: emissão desligada ou configuração interna inválida.

Todas as respostas permanecem `no-store`.

## Release gates

- `TITAN_COMMERCIAL_PASSPORT_API_ENABLED` continua controlando o registro da rota;
- `TITAN_COMMERCIAL_PASSPORT_PIPELINE_ENABLED` continua controlando a consulta;
- `TITAN_COMMERCIAL_PASSPORT_ISSUANCE_ENABLED=true` controla exclusivamente a
  composição formal e tem default desligado;
- `TITAN_COMMERCIAL_PASSPORT_ISSUANCE_PROFILE=INTERNAL_SYNTHETIC` é obrigatório
  para compor a emissão inicial.

Nenhuma flag será habilitada como parte desta implementação.

## Critérios de aceite

1. O default continua retornando `503` para emissão.
2. Sem `Idempotency-Key`, a API rejeita a requisição antes de persistir.
3. Com o gate e perfil corretos, uma tríade exata gera Dossier e bundle.
4. Zero ou múltiplas Decisions exatas retornam conflito sem Dossier.
5. Divergência de Organization, subject, purpose, Policy, versão ou coordenadas
   temporais retorna conflito sem Dossier.
6. Replay da mesma intenção retorna os mesmos identificadores; chave reutilizada
   para outra intenção retorna conflito.
7. RLS impede uso de material de outra Organization.
8. Testes, verificações estáticas, Alembic checks e roteiro executável passam.

## Fora de escopo

- oportunidade externa ou real de produção;
- múltiplas oportunidades em um único Dossier;
- criação de Decision/Evaluation durante a emissão;
- persistência autônoma de VerificationBundle;
- mudança de schema, domínio, Policy ou AuthorizationGrant;
- habilitação ou homologação do recurso.
