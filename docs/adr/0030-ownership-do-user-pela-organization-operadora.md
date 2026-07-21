# ADR 0030 — Ownership do User pela Organization operadora

**Status:** Aceita
**Data:** 21 de julho de 2026
**Decisores:** fundador e responsável pela arquitetura do Titan

## Contexto

`User` representa uma identidade humana interna e estável. Um mesmo User pode possuir Memberships com várias Organizations, mas a ADR 0002 exige exatamente uma RecordOwnerOrganization para cada registro protegido de domínio.

O ownership do registro interno do User não pode ser confundido com vínculo empregatício, relação contratual, titularidade de dados pessoais, representação jurídica ou Permission. Esses significados pertencem a conceitos distintos.

## Problema

É necessário definir qual Organization responde pelo registro global do User sem:

- transformar a primeira Organization convidante em responsável permanente pela identidade;
- duplicar User por Organization;
- permitir copropriedade implícita;
- fazer Membership conceder ownership;
- criar acesso ou Permission direta para o User;
- armazenar senha, token ou credencial no Titan.

## Alternativas consideradas

### User owned pela primeira Organization convidante

Simplifica a criação inicial, mas atribui responsabilidade permanente por uma identidade que pode manter vínculos posteriores com várias Organizations. Saída da primeira Organization exigiria transferência excepcional ou produziria ownership enganoso.

### Um User independente por Organization

Mantém isolamento local, mas fragmenta a identidade humana, dificulta auditoria entre vínculos, relink de identidade externa e continuidade histórica.

### User sem RecordOwnerOrganization

Evita escolher um owner, mas viola as ADRs 0002 e 0003 e introduz um dado de domínio implicitamente global.

### User owned pela Organization operadora da plataforma

Preserva uma identidade interna global, mantém owner inequívoco e deixa Membership representar exclusivamente o vínculo temporal com cada Organization usuária.

## Decisão

O registro interno de `User` possui como RecordOwnerOrganization a **Organization operadora da plataforma Titan**.

Essa atribuição significa apenas responsabilidade pelo ciclo de vida do registro interno no Titan. Ela não declara propriedade sobre a pessoa, seus dados pessoais, suas relações profissionais ou seus atos.

Membership permanece o único vínculo humano ordinário entre User e uma Organization usuária. Criar User não cria Membership, Role, Permission, AuthorizationGrant ou OrganizationContext.

## Invariantes

- User possui identidade interna estável e não é duplicado por Organization;
- User possui exatamente uma RecordOwnerOrganization operadora;
- Organization convidante não se torna owner do User;
- Membership não altera ownership do User;
- User não recebe Permission diretamente;
- senha, token, secret, credencial e dados do protocolo OIDC não integram User;
- ExternalIdentity permanece conceito separado e usa `(issuer, subject)` quando implementado;
- email, nome e telefone não são identificadores de segurança;
- suspensão ou evolução futura cria estado e histórico próprios, sem trocar silenciosamente a identidade.

## Aplicação e configuração

O ID da Organization operadora é resolvido por configuração confiável e caso de uso autorizado. Ele não é aceito livremente de payload, header, token ou claim externa.

Até existir esse caso de uso, Domain e persistência exigem explicitamente o RecordOwnerOrganization fornecido pela composição interna. A migration não inventa uma Organization operadora nem cria dado de domínio automaticamente.

## Persistência e isolamento

`User` é registro `PROTECTED` no schema owner `core_identity`, com:

- `user_id` interno e estável;
- `record_owner_organization_id` obrigatório;
- foreign key para Organization existente;
- RLS e `FORCE ROW LEVEL SECURITY`;
- policies ordinárias limitadas à Organization operadora contextualizada;
- ausência de coluna de senha, token, secret, Role ou Permission.

Memberships futuros pertencem às Organizations responsáveis por cada vínculo e referenciam o User por contrato autorizado. A foreign key não substitui Authorization nem concede visibilidade sobre o User.

## Consequências

### Positivas

- identidade humana não fica subordinada à primeira Organization convidante;
- ownership permanece único e auditável;
- Memberships podem evoluir independentemente;
- troca de OIDC Provider não altera User;
- persistência não armazena credenciais.

### Negativas

- operações sobre User exigem contexto interno da Organization operadora ou caminho autorizado dedicado;
- Organizations usuárias não consultam diretamente a tabela de Users;
- configuração incorreta da Organization operadora deve falhar fechada;
- provisionamento inicial da Organization operadora continua sendo responsabilidade separada.

## Critérios de aceitação

- User válido possuir ID interno e RecordOwnerOrganization operadora;
- persistência rejeitar owner inexistente e User duplicado;
- contexto de outra Organization não visualizar o User;
- criação não produzir Membership ou Permission;
- schema não possuir senha, token, secret, Role ou Permission;
- migration ser reversível e preservar RLS;
- Application futura não aceitar owner operador livremente do cliente.
