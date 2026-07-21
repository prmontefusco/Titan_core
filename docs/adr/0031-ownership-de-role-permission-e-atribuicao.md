# ADR 0031 — Ownership de Role e Permission e atribuição de papéis

**Status:** Aceita
**Data:** 21 de julho de 2026
**Decisores:** fundador e responsável pela arquitetura do Titan

## Contexto e problema

Permission é autorização atômica, Role é conjunto nomeado de Permissions e Membership é vínculo humano temporal. É necessário permitir papéis próprios por Organization sem permitir capacidades técnicas inventadas, claims externas autoritativas ou perda do histórico na remoção.

## Alternativas

- Permissions e Roles globais impedem composição local.
- Permissions e Roles livres por Organization permitem capacidades divergentes.
- Permission canônica da plataforma e Role por Organization separam capacidade técnica de composição organizacional.

## Decisão

- Permission integra catálogo canônico owned pela Organization operadora;
- Role é owned pela Organization que o define e referencia Permissions canônicas;
- MembershipRoleAssignment atribui Role a Membership da mesma Organization e período;
- remoção cria MembershipRoleRevocation append-only, sem alterar a atribuição original;
- não existe associação User–Permission nem Membership–Permission;
- claims externas não criam Role, Permission ou atribuição.

## Invariantes

- Permission possui código canônico estável;
- Role possui nome organizacional e conjunto explícito de Permissions;
- Role e Membership da atribuição pertencem à mesma Organization;
- atribuição efetiva exige Membership e período vigentes e ausência de revogação aplicável;
- revogação não possui efeito anterior ao instante registrado;
- Role não concede acesso sem Authorization da operação;
- mudança incompatível da composição exige novo Role;
- User nunca recebe Permission diretamente.

## Persistência e consequências

Permissions pertencem a `REFERENCE_CATALOG` owned pela Organization operadora, legível pelo runtime e imutável por ele. Roles, composição, atribuições e revogações pertencem à Organization usuária, carregam RecordOwnerOrganization, RLS e `FORCE ROW LEVEL SECURITY`.

Organizations combinam capacidades aprovadas sem ampliar o catálogo técnico. A remoção produz histórico verificável. Bootstrap das Permissions e dos perfis mínimos permanece em passo próprio.

## Critérios de aceitação

- criar Permission sob owner operador;
- criar Role com Permissions existentes;
- atribuir Role somente a Membership da mesma Organization;
- revogar preservando a atribuição original;
- resolução excluir atribuição expirada, revogada ou fora do contexto;
- inexistir Permission direta ao User;
- isolamento e migrations reversíveis serem comprovados no PostgreSQL.
