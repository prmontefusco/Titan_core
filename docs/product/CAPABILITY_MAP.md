# Mapa de capacidades do Titan Technologies

Fotografia factual do repositório em 14 de agosto de 2026. Este mapa não é roadmap,
backlog nem ledger de entrega; o progresso validado permanece em
`docs/CHECKLIST_DE_IMPLEMENTACAO.md`.

| Capacidade | Estado | Evidência principal |
|---|---|---|
| Identity, Organizations e Users | Implementada | `packages/core_domain`, OIDC, Membership, Roles, Permissions e RLS |
| Autorização e tenancy | Implementada | `OrganizationContext`, autorização de aplicação e RLS PostgreSQL |
| Audit e integridade | Implementada | eventos append-only, hash chain, checkpoints, timestamps e correções |
| Evidence, Policy, Rules e Decision | Implementada | pacotes Core e ADRs 0015–0017, 0048–0054 |
| Documents e dossiês | Parcial | Dossier/VerificationBundle/PDF implementados; MongoDB/GridFS ainda não integra o domínio |
| Offline e Devices | Parcial | contratos e sincronização segura no Core; não há cliente de campo autônomo |
| Geospatial | Implementada para Livestock | PostGIS, geometria de propriedade e captura territorial versionada |
| Integrations | Parcial | outbox/inbox/RabbitMQ, contrato ERP neutro, simulador SISBOV e provider territorial configurável |
| Properties e Animals | Implementada em Livestock | propriedade rural, animais, movimentos, lotes, reprodução e saída |
| Sanitary compliance | Implementada em Livestock | medicamentos, tratamentos, carência, campanhas e elegibilidade por mercado |
| Rastreabilidade de transformação | Implementada em Livestock | TransformationEvent, TraceableItem, balanceamento e recall |
| Telemetry e Measurements | Não iniciada | não há capacidade de produto nem módulo dedicado |
| Alerts | Não iniciada como capacidade própria | NonConformity e Recall existem; alertas operacionais não são módulo separado |
| Agriculture e Compliance como verticais | Não iniciada | não criar até necessidade de produto aprovada |

## Uso

Antes de propor capacidade nova, consultar este mapa, `DOMAIN.md`, `ARCHITECTURE.md`,
ADRs e o checklist para evitar duplicação. Atualizar esta fotografia somente quando
uma capacidade concreta mudar; não registrar datas, passos ou evidências de execução
que pertencem ao checklist.
