# Segurança, Multi-Tenancy e Isolamento RLS

Este documento detalha o modelo de segurança, autenticação e isolamento multi-tenant do **Titan Core**, explicando como o isolamento é aplicado no PostgreSQL e como sistemas integradores devem passar credenciais e contextos de organização.

---

## 1. Multi-Tenancy com RLS (Row-Level Security) no PostgreSQL

### O que é?
É a política de isolamento físico/lógico em nível de linha (*Row-Level Security*) ativada nativamente no motor PostgreSQL para todas as tabelas do Titan.

### Para que serve?
Garantir que, mesmo em caso de erro na camada de aplicação ou query SQL mal formatada, o banco de dados proíba terminantemente qualquer vazamento ou modificação de dados pertencentes a outra organização (`OrganizationId`).

### Como funciona?
Toda conexão com o banco de dados que executa consultas ou alterações de estado de tenant deve definir a variável de sessão RLS antes da query:

```sql
SELECT set_config('titan.organization_id', 'f31bc184-feaa-4ec1-a690-3032683000e9', true);
```

### Como utilizar no código Python:
```python
from packages.core_application.organization_context import OrganizationContextService
from packages.shared_kernel import OrganizationId

org_id = OrganizationId.from_string("f31bc184-feaa-4ec1-a690-3032683000e9")

# Define a variável de sessão RLS na transação ativa
OrganizationContextService.apply_context(connection=db_connection, organization_id=org_id)
```

---

## 2. Identidade Universal e Referências (`UniversalReference`)

### O que é?
Representação universal e imutável de qualquer ator, usuário ou serviço no ecossistema Titan.

### Para que serve?
Permitir que sistemas externos identifiquem com precisão quem originou uma ação (`actor_reference`) e qual serviço produziu a mensagem (`producer_reference`).

### Estrutura em Código Python:
```python
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

actor_ref = UniversalReference(
    target_id=TypedId(entity_type="user", value=user_uuid),
    organization_id=OrganizationId(org_uuid),
    contract_version=1,
)

producer_ref = UniversalReference(
    target_id=TypedId(entity_type="service", value=service_uuid),
    organization_id=OrganizationId(org_uuid),
    contract_version=1,
)
```

---

## 3. Modos de Avaliação de Autorização (`AuthorizationEvaluationMode`)

### O que são?
Políticas de validação declaradas no envelope da mensagem que indicam ao Titan como avaliar os privilégios de execução.

### Valores Suportados:

| Modo | Descrição | Cenário de Uso |
|---|---|---|
| `SERVICE_AUTHORITY_ONLY` | Valida apenas a autoridade e chave do serviço produtor. | Tarefas automáticas de sistema, cron jobs, Workers. |
| `ACTOR_CONTEXT_ONLY` | Valida as permissões do usuário final informado em `actor_reference`. | Ações disparadas diretamente por usuários via interface web/mobile. |
| `DUAL_AUTHORITY` | Exige validação conjunta das permissões do serviço produtor E do usuário final. | Operações críticas de alto risco (ex: transferências bancárias, estornos). |

---

## 4. Integração com Autenticação OIDC e Tokens JWT

### O que é?
Suporte a autenticação baseada no padrão OpenID Connect (OIDC) com tokens JWT assinados pelo provedor de identidade.

### Como um Sistema Externo Autentica no Titan API:
1. O sistema parceiro obtém um token JWT de acesso através do IdP configurado (ex: Keycloak, Auth0, Google OIDC).
2. Envia o token no cabeçalho HTTP de cada requisição:
   ```http
   Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
   ```
3. O Titan API valida a assinatura da chave pública do IdP, extrai o `sub` (ID do usuário) e as `roles`/`tenant_id` das claims do JWT e configura o RLS do PostgreSQL automaticamente para a requisição.
