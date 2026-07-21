# ADR 0002 — Isolamento e propriedade por Organization

**Status:** Aceita  
**Data:** 20 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

Organization é a unidade principal de isolamento, responsabilidade e autorização do Titan. Um User pode participar de várias Organizations, relações podem conectar Subjects de Organizations diferentes e um recall pode precisar atravessar fronteiras organizacionais.

Essas relações são necessárias, mas não podem conceder acesso implicitamente. Também é preciso determinar como Policies, Rules, integrações, tarefas assíncronas, projeções e registros de segurança são atribuídos a uma Organization.

O `DOMAIN.md` atualmente declara que todo registro protegido possui uma Organization responsável, sem definir precisamente “registro protegido” nem o tratamento de dados considerados globais. A decisão deve eliminar essa ambiguidade antes da persistência.

## Problema

Definir um modelo de propriedade e autorização que:

- impeça vazamento entre Organizations;
- determine um owner inequívoco para cada registro de domínio;
- permita compartilhamento e relações explicitamente autorizadas;
- preserve genealogia e recall entre Organizations;
- funcione em API, worker, sincronização offline, cache e projeções;
- mantenha auditoria mesmo antes da seleção de uma Organization pelo usuário;
- não dependa de confiança em identificadores fornecidos pelo cliente.

## Princípios

1. **Negação por padrão:** ausência de autorização explícita resulta em acesso negado.
2. **Um owner:** todo registro protegido de domínio possui exatamente uma Organization proprietária.
3. **Contexto explícito:** toda operação protegida executa em uma única Organization ativa.
4. **Relação não é autorização:** referência, genealogia ou transformação não concedem acesso.
5. **Menor privilégio:** acesso compartilhado é limitado por finalidade, capacidade, sujeitos e período.
6. **Histórico preservado:** transferência, revogação ou encerramento não reescreve registros passados.
7. **Defesa em profundidade:** isolamento deve existir em contratos, aplicação, persistência, cache, filas e testes.
8. **Auditabilidade:** concessões, negações, revogações e travessias são registradas.

## Significado de owner

Nesta ADR, `owner` significa exclusivamente **Organization responsável pelo registro dentro do Titan** (`RecordOwnerOrganization`). É uma atribuição técnica e de domínio que determina:

- qual Organization responde pela criação e pelo ciclo de vida do registro no Titan;
- qual namespace e política de autorização são aplicados por padrão;
- quem pode iniciar compartilhamento, publicação, correção ou revogação, conforme Permission;
- qual Organization aparece como responsável na auditoria.

`owner` não declara, por si só:

- propriedade civil ou comercial do Subject representado;
- titularidade de propriedade intelectual;
- posse, custódia física ou responsabilidade regulatória;
- papel de controlador, operador ou titular de dados pessoais;
- autoria ou emissão da informação;
- direito irrestrito de alterar, excluir ou compartilhar o registro.

Esses efeitos dependem de legislação, contrato, política aplicável e conceitos específicos da vertical. Quando necessário, devem ser modelados separadamente e nunca inferidos apenas de `RecordOwnerOrganization`.

O nome definitivo desse conceito deve ser formalizado em `DOMAIN.md` antes da implementação. Código, banco e API não devem utilizar `owner` com outro significado implícito.

## Dimensões independentes de acesso e responsabilidade

Os seguintes conceitos não são sinônimos:

| Dimensão | Significado |
|---|---|
| Ownership | Organization responsável pelo registro no Titan |
| Visibilidade | Quem pode descobrir a existência ou visualizar determinada parte do registro |
| Publicação | Ato versionado de um emissor tornar conteúdo elegível para uma audiência e finalidade definidas |
| Compartilhamento | Concessão explícita de acesso a Organization ou Actor determinados |
| Autorização | Decisão realizada no momento da operação considerando Actor, OrganizationContext, Permission, concessões, finalidade, validade e recurso |

Publicar não transfere ownership, não concede visibilidade irrestrita e não autoriza automaticamente qualquer operação. Compartilhar não muda o emissor nem o owner. Visibilidade não implica Permission de alteração. Autorização é sempre avaliada para a operação concreta.

O emissor registra ou atesta a informação e pode ser diferente de RecordOwnerOrganization. Essa diferença deve permanecer explícita e auditável.

## Alternativas consideradas

### 1. Banco ou schema independente por Organization

**Vantagens:** isolamento físico forte e restauração individual potencialmente simples.

**Desvantagens:** migrations, operação, conexões, recall autorizado entre Organizations e crescimento do número de Organizations ficam mais complexos. Não é proporcional à fase inicial.

### 2. Registros sem owner, filtrados apenas por relações

**Vantagens:** modelo aparentemente flexível.

**Desvantagens:** ownership ambíguo, autorização difícil de provar e alto risco de vazamento. Uma relação poderia ser confundida com permissão.

### 3. Escopo genérico `PLATFORM` ou `ORGANIZATION` em todo registro

**Vantagens:** facilita dados globais.

**Desvantagens:** cria dois modelos de autorização e permite que registros sejam promovidos indevidamente a globais. Aumenta a superfície de acesso privilegiado.

### 4. Uma Organization owner por registro, com compartilhamento explícito

**Vantagens:** ownership inequívoco, modelo uniforme, auditoria clara e compartilhamento controlável. Policies e Rules reutilizáveis continuam tendo emissor responsável.

**Desvantagens:** exige contratos de concessão/publicação, filtros obrigatórios e desenho cuidadoso para relações entre Organizations.

## Decisão proposta

Adotar **uma Organization proprietária para todo registro protegido de domínio**, com acesso e compartilhamento explícitos.

Dados estritamente técnicos que não representam domínio — como versão de migration ou configuração local de processo — não são registros protegidos de domínio. Eles continuam sujeitos a segurança operacional, mas não introduzem um segundo escopo de negócio.

Quando uma operação técnica ou de segurança precisar produzir registro auditável sem Organization ativa, o registro será de responsabilidade da Organization operadora da plataforma. Isso não concede a ela acesso irrestrito aos dados das demais Organizations.

### Propriedade

Todo registro protegido deve possuir `owner_organization_id` ou referência conceitualmente equivalente, obrigatória e imutável.

Record ownership significa:

- responsabilidade primária pelo registro;
- namespace padrão para autorização e unicidade;
- origem das políticas de retenção e compartilhamento aplicáveis;
- ponto inicial para auditoria de acesso.

Propriedade não significa que o registro possa ser alterado. Eventos, Evidences, Policies publicadas, Rules publicadas, Evaluations, Decisions e Dossiers permanecem imutáveis.

Um registro nunca possui dois RecordOwnerOrganizations simultâneos. Outras Organizations podem possuir relação jurídica ou operacional com o Subject e receber visibilidade ou acesso delimitados sem se tornarem responsáveis pelo registro no Titan.

### Organization ativa

Toda operação protegida deve receber um OrganizationContext validado contendo, quando aplicável:

- Organization ativa;
- User ou Actor;
- Membership válida;
- Roles e Permissions efetivas;
- origem da autenticação;
- correlação da operação.

O OrganizationContext é **construído e validado pelo servidor**, nunca escolhido livremente pelo cliente. O cliente pode solicitar atuação em determinada Organization, mas não fornece contexto confiável, Roles ou Permissions efetivas.

A Application resolve a solicitação usando identidade autenticada, vínculos ou concessões vigentes, finalidade, recurso e políticas aplicáveis. Somente depois dessa validação o OrganizationContext passa a existir para o caso de uso.

Trocar a Organization solicitada exige nova validação. OrganizationContext não é reutilizado entre Organizations e não pode ser aceito apenas porque veio em header, token, payload ou mensagem.

O OIDC Provider autentica a identidade. Claims do token não substituem Membership, Role ou Permission mantidas pelo Titan.

### Atores não humanos e concessões sem Membership

Membership representa vínculo de User humano com Organization, mas não é a única fonte possível de autorização.

Serviços, sistemas, integrações e dispositivos podem atuar como Actor sem Membership humano quando existir vínculo técnico explícito e vigente que determine:

- identidade autenticada do Actor;
- Organization pela qual pode atuar;
- Permissions ou capacidades concedidas;
- finalidade e recursos permitidos;
- validade;
- emissor da concessão;
- credencial ou mecanismo de autenticação;
- condições de revogação;
- auditoria de uso.

Concessões entre Organizations e autorizações administrativas também podem existir sem Membership do Actor na Organization proprietária do registro. Elas devem ser explícitas, delimitadas, revogáveis e avaliadas no OrganizationContext.

Um Actor de plataforma não recebe acesso universal por sua categoria. Administração entre Organizations exige Permission privilegiada explícita, justificativa, finalidade e auditoria reforçada.

Os conceitos definitivos para identidade de serviço, vínculo técnico e concessão devem ser formalizados em `DOMAIN.md` antes de implementação.

### Operações envolvendo várias Organizations

Uma operação executa por exatamente uma Organization atuante, ainda que referencie ou afete outras.

Devem ser preservados:

- Organization atuante;
- owner de cada registro;
- Organizations referenciadas ou afetadas;
- autorização usada para cada travessia;
- Actor, finalidade e momento;
- resultado permitido ou negado.

Transferência de posse, custódia ou responsabilidade operacional não muda o owner de eventos históricos. Ela produz Events e UniversalRelations que representam a mudança ao longo do tempo.

### Compartilhamento e publicação

Compartilhamento exige concessão explícita, auditável, revogável e delimitada. A concessão deve indicar:

- Organization concedente e receptora;
- recurso, Subject ou conjunto delimitado;
- Permissions concedidas;
- finalidade;
- início e fim de validade;
- Actor responsável;
- justificativa e correlação;
- estado e histórico de revogação.

Policies, Rules, templates ou catálogos reutilizáveis possuem RecordOwnerOrganization e emissor identificados, que podem ser diferentes. Publicação os torna elegíveis para consumo autorizado por audiência e finalidade definidas; não os transforma em dados sem owner.

Os conceitos definitivos de concessão e publicação devem ser formalizados em `DOMAIN.md` antes da implementação correspondente.

### Genealogia e recall

UniversalRelation pode referenciar Subjects de Organizations diferentes, mas pertence a uma única Organization responsável pelo registro da relação.

Uma relação não revela automaticamente os registros dos Subjects conectados. Recall atravessa uma fronteira somente quando o OrganizationContext e as concessões permitem.

O resultado deve distinguir:

- caminho conhecido e autorizado;
- existência de fronteira sem autorização para detalhamento;
- lacuna de dados;
- relação contestada ou com confiança insuficiente.

Ocultar detalhes por autorização não permite concluir que não existem afetados. O RecallResult deve ser marcado como limitado ou inconclusivo quando a restrição impedir conclusão completa.

### API e contratos

- endpoints protegidos exigem OrganizationContext;
- IDs não comprovam autorização;
- consultas recebem Organization explicitamente;
- erros não devem permitir enumeração de registros de outra Organization;
- referências públicas incluem Organization quando necessário para desambiguação;
- paginação, busca e exportação aplicam o mesmo isolamento.

### Workers, Outbox e Message Broker

OutboxMessage e tarefas protegidas carregam Organization, Actor ou mecanismo responsável, correlação, causação e versão do payload.

Worker reconstrói e valida OrganizationContext de sistema antes de executar o caso de uso. Receber uma mensagem não concede autorização e o Message Broker não é fonte de identidade ou permissão.

Retries preservam Organization e contexto originais. Dead letter, falha permanente e reprocessamento permanecem auditáveis.

### Operação offline

OfflineOperation registra Organization no momento da criação. Na sincronização, o servidor revalida Membership, Permission, versão e conflitos.

Autorização válida no momento da captura offline não garante aceitação posterior. Suspensão, revogação ou mudança de contexto pode resultar em rejeição explícita, sem perda da operação original.

### Cache e projeções

- chaves de cache incluem Organization quando o conteúdo for protegido;
- cache nunca amplia autorização;
- invalidação considera Organization;
- projeções preservam owner e regras de visibilidade;
- reconstrução de projeção não pode misturar Organizations;
- dados definitivos não existem somente no cache.

### Persistência

A estratégia física será detalhada na ADR do PostgreSQL. Ela deve fornecer defesa em profundidade, além dos filtros da Application.

Repositórios e Unit of Work protegidos exigem OrganizationContext ou owner explícito. Consultas sem escopo são proibidas, exceto operações administrativas específicas, auditadas e formalmente autorizadas.

Migrations, índices e constraints devem preservar ownership e desempenho dos filtros por Organization.

## Consequências

### Positivas

- ownership inequívoco;
- modelo uniforme para todos os módulos;
- autorização reproduzível;
- compartilhamento e recall auditáveis;
- menor risco de consulta cruzada acidental;
- Policies e Rules reutilizáveis preservam autoria e responsabilidade.

### Negativas

- contratos e índices carregam Organization com frequência;
- compartilhamento exige modelo próprio;
- operações administrativas ficam mais rigorosas;
- recall entre Organizations pode retornar resultado limitado;
- testes de isolamento tornam-se obrigatórios em todos os módulos.

### Riscos e controles

| Risco | Controle |
|---|---|
| Filtro por Organization esquecido | Repositórios com contexto obrigatório e defesa no banco |
| ID enumerável revelar existência | Respostas indistinguíveis e testes negativos |
| Token ser usado como autorização completa | Membership e Permission validadas pelo Titan |
| Mensagem assíncrona perder contexto | Envelope obrigatório e revalidação no worker |
| Cache misturar Organizations | Namespace por Organization e testes |
| Relação genealógica vazar detalhes | Travessia autorizada e resultado limitado |
| “Dado global” contornar owner | Organization emissora obrigatória |
| Operador da plataforma obter acesso implícito | Permissões administrativas explícitas e auditoria |
| `owner` ser interpretado como propriedade jurídica | Definição restrita de RecordOwnerOrganization e conceitos legais separados |
| Cliente forjar OrganizationContext | Contexto construído e validado no servidor |
| Serviço operar sem vínculo humano | Identidade técnica e concessão explícitas, delimitadas e revogáveis |
| Publicação ser confundida com autorização | Dimensões independentes e avaliação por operação |

## O que esta ADR não decide

- tecnologia ou configuração do OIDC Provider;
- mecanismo físico de isolamento no PostgreSQL;
- estrutura definitiva de concessão e publicação;
- nomes definitivos de RecordOwnerOrganization, identidade técnica e concessão;
- políticas de retenção e exclusão;
- regras comerciais de compartilhamento;
- contratos entre Organizations em uma vertical;
- requisitos legais de proteção de dados.

## Critérios de aceitação

A ADR pode ser aceita quando:

- todo registro protegido de domínio possuir exatamente uma Organization owner;
- owner possuir significado técnico e de domínio, sem inferência jurídica automática;
- ownership, visibilidade, publicação, compartilhamento e autorização permanecerem distintos;
- “registro protegido” estiver delimitado;
- dados reutilizáveis continuarem com emissor responsável;
- Organization ativa e owner não forem confundidos;
- OrganizationContext for construído e validado pelo servidor;
- atores não humanos exigirem identidade e concessão explícitas;
- relações não concederem acesso;
- workers, offline, cache e projeções preservarem isolamento;
- recall declarar limitações causadas por autorização;
- não existir escopo global implícito;
- detalhes físicos permanecerem para ADR própria.

## Plano de reversão

Antes da persistência, a decisão pode ser revista por nova versão desta ADR. Depois da criação de dados, mudança de ownership ou introdução de escopo global exige nova ADR, migration, análise de impacto em autorização e plano para preservar auditoria histórica.
