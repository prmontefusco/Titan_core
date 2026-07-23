# Guia de Integração e Funcionalidades do Titan Core

Este diretório contém a documentação técnica oficial do **Titan Core**, detalhando as funcionalidades já construídas, como funcionam, para que servem, como utilizá-las e como integrar sistemas externos à plataforma Titan.

---

## 📚 Índice de Documentos

1. **[01_MENSAGERIA_E_EVENTOS.md](01_MENSAGERIA_E_EVENTOS.md)**
   - Padrões Inbox / Outbox
   - Formato do Envelope Canônico (`IncomingMessageEnvelope`)
   - Digest Semântico (`titan-json-v1`)
   - Reconciliação Operacional de Outbox
   - Deduplicação de Mensagens e Registro Forense de Conflito (`inbox_conflicts`)
   - Quarentena Pré-Tenant e Replay Auditável por Operador
   - Execução Assíncrona via Worker Daemon (`apps/worker`)

2. **[02_SEGURANCA_E_MULTITENANCY.md](02_SEGURANCA_E_MULTITENANCY.md)**
   - Isolamento de Dados por RLS (Row-Level Security)
   - Identidade Universal (`UniversalReference`) e Organizações
   - Modos de Avaliação de Autorização (*Service Authority*, *Actor Context*, *Dual Authority*)
   - Autenticação OIDC e Validação de Tokens JWT

3. **[03_INTEGRIDADE_E_AUDITORIA.md](03_INTEGRIDADE_E_AUDITORIA.md)**
   - Idempotência Transacional no PostgreSQL (`IdempotencyService`)
   - Corrente de Hashes Criptograficamente Encadeada (*Hash Chain*)
   - Checkpoints de Estado de Integridade (`IntegrityCheckpointService`)
   - Concorrência Otimista com Registro de Versão

4. **[04_EVIDENCIAS_CRIPTOGRAFIA_E_PROVENIENCIA.md](04_EVIDENCIAS_CRIPTOGRAFIA_E_PROVENIENCIA.md)**
   - Evidence imutável, nível de confiança e revogação sem apagamento
   - Gestão, rotação e revogação de chaves (`KeyManagementService`)
   - Assinatura por portas substituíveis e resultado `VÁLIDA` / `INVÁLIDA` / `INDETERMINADA`
   - Documentos e anexos com hash SHA-256 obrigatório (`DocumentService`)
   - Proveniência navegável `Source → Evidence → DomainEvent`

5. **[05_POLITICAS_AVALIACAO_E_DECISAO.md](05_POLITICAS_AVALIACAO_E_DECISAO.md)**
   - Policy versionada com ciclo de vida formal
   - Rule versionada e condições normativas declarativas (`RuleCondition`)
   - Contrato de fatos da vertical (`FactProviderPort`) — a fronteira do Core
   - Execução determinística de regra e agregação em `Evaluation`
   - Decision explicável, sem conclusão sem justificativa

6. **[06_GENEALOGIA_E_PROJECOES.md](06_GENEALOGIA_E_PROJECOES.md)**
   - Relação universal e temporal (`UniversalRelation`)
   - Consulta por instante, navegação retrospectiva e prospectiva
   - Encerramento que preserva o histórico
   - Projeções reconstruíveis e referências reversas

7. **[07_NAO_CONFORMIDADE_RECALL_E_DOSSIE.md](07_NAO_CONFORMIDADE_RECALL_E_DOSSIE.md)**
   - Ciclo de vida da não conformidade, com reavaliação que pode reprovar
   - Recall com janela temporal, controle de ciclos e profundidade
   - Lacuna declarada como resultado inconclusivo
   - Simulação e incidente
   - Dossiê autocontido e verificação offline por `titan-json-v1`

---

## 🚀 Visão Geral Arquitetural de Integração

```
                                  ┌────────────────────────────────────────────────────────┐
                                  │                     SISTEMA PARCEIRO                   │
                                  └───────────────────────────┬────────────────────────────┘
                                                              │
                                                              ▼
                                                   [RabbitMQ / Exchange AMQP]
                                                              │
                                                              ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                                TITAN CORE                                               │
 │                                                                                                         │
 │  ┌─────────────────────────────────┐   ┌────────────────────────────────┐   ┌────────────────────────┐  │
 │  │        Worker Daemon            │   │       Validação Pré-Tenant     │   │ Quarentena Pré-Tenant  │  │
 │  │      (apps/worker/main.py)      │──►│   (Produtor & Autorização)     │──►│ (untrusted_quarantine)│  │
 │  └────────────────┬────────────────┘   └───────────────┬────────────────┘   └────────────────────────┘  │
 │                   │                                    │                                                │
 │                   ▼                                    ▼                                                │
 │  ┌──────────────────────────────────────────────────────────────────────┐   ┌────────────────────────┐  │
 │  │                    Transação Única PostgreSQL                        │   │    Replay Auditado     │  │
 │  │                                                                      │◄──│  (Operador + Justific) │  │
 │  │  RLS Session ──► Deduplicação Inbox ──► Handler ──► Outbox State     │   └────────────────────────┘  │
 │  └──────────────────────────────────────────────────────────────────────┘                               │
 └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Requisitos de Conexão e Dependências Locais

Para executar ou integrar localmente com o Titan Core, utilize as seguintes credenciais padrão de desenvolvimento:

- **PostgreSQL**: `postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan`
- **RabbitMQ AMQP**: `amqp://titan:titan_rabbitmq_local_dev_password@127.0.0.1:5672/titan`
- **Fila Padrão do Worker**: `titan.outbox`
