# ADR 0003 — PostgreSQL e isolamento por RLS e defesa em profundidade

**Status:** Aceita  
**Data:** 20 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan precisa persistir eventos, identidades, relações, evidências, políticas, avaliações, decisões, não conformidades, outbox e projeções com forte consistência, constraints, transações e auditoria.

A ADR 0001 definiu monólito modular e ownership técnico por módulo. A ADR 0002 definiu exatamente uma RecordOwnerOrganization por registro protegido, contexto validado pelo servidor e negação por padrão.

É necessário escolher o banco transacional e estabelecer uma defesa física que reduza o risco de uma consulta incorreta atravessar Organizations. A proteção da Application continua obrigatória; o banco funciona como camada adicional.

## Problema

Definir:

- banco transacional do Titan;
- organização física dos módulos;
- enforcement de RecordOwnerOrganization;
- papéis de conexão;
- Row-Level Security;
- constraints e índices;
- transações e concorrência;
- migrations, backup e restauração;
- tratamento de projeções e compartilhamentos;
- limites de operações administrativas.

## Princípios

1. **Defesa em profundidade:** autorização na Application e isolamento adicional no banco.
2. **Negação por padrão:** contexto ausente ou inválido não retorna nem modifica registros protegidos.
3. **Responsabilidade estrutural única:** cada schema, tabela, índice, constraint e migration possui exatamente um módulo responsável.
4. **Menor privilégio:** runtime não é superuser, não possui `BYPASSRLS` e não é owner das tabelas.
5. **Transação explícita:** contexto e operação protegida pertencem à mesma transação.
6. **Histórico preservado:** tabelas imutáveis recebem proteção também por privilégios físicos.
7. **Reprodutibilidade:** schema nasce exclusivamente de migrations versionadas.
8. **Observabilidade segura:** falhas são rastreáveis sem registrar credenciais ou dados sensíveis desnecessários.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| MongoDB principal | Documentos flexíveis | Menor aderência a transações relacionais, constraints e integridade referencial do Core |
| Banco ou schema por Organization | Isolamento físico forte | Multiplica migrations, objetos e conexões; dificulta recall interorganizacional |
| PostgreSQL com filtro apenas na Application | Simplicidade | Consulta sem filtro pode expor outra Organization |
| PostgreSQL, schemas por módulo e RLS | Transações, ownership modular e proteção por linha | Exige papéis, contexto e policies cuidadosamente testados |

MongoDB permanece candidato apenas para conteúdo documental conforme ADR própria.

Responsabilidade técnica de módulo por uma estrutura não é RecordOwnerOrganization dos registros armazenados. Os dois conceitos nunca devem compartilhar significado implícito em código, banco ou documentação.

## Decisão

Adotar **PostgreSQL como banco transacional principal**, em uma instância lógica compartilhada pelo monólito, com:

- schemas por módulo;
- RecordOwnerOrganization obrigatória nas tabelas protegidas;
- Row-Level Security como defesa em profundidade;
- papéis separados para migration, runtime e operação;
- migrations versionadas como única forma de alterar schema;
- concorrência otimista como padrão da aplicação;
- isolamento transacional mais forte apenas quando uma invariável exigir.

PostGIS não integra o escopo inicial. Sua ativação exige passo e migration próprios.

## Organização por schemas

Cada módulo persistente recebe schema próprio quando criar sua primeira estrutura real. Exemplos ilustrativos:

```text
core_identity
core_audit
core_evidence
core_policy
core_decision
core_recall
```

Esses nomes não autorizam criação antecipada. Schema surge junto da primeira migration do módulo.

Regras:

- módulo owner controla tabelas, índices, constraints e migrations de seu schema;
- nomes de objetos são qualificados explicitamente;
- `search_path` não é usado como fronteira de segurança;
- runtime não recebe `CREATE` em schemas de aplicação;
- criação por usuários não confiáveis no `public` é proibida;
- acesso SQL direto entre schemas não substitui contrato público entre módulos;
- mudança de ownership de estrutura exige ADR e migration.

O PostgreSQL alerta que schemas presentes no `search_path` confiam em usuários capazes de criar objetos neles. Por isso, privilégios de criação e caminho de resolução devem ser restritos.

## RecordOwnerOrganization

RecordOwnerOrganization representa a Organization responsável pelo ciclo de vida lógico do registro dentro do Titan.

Não implica necessariamente propriedade jurídica, autoria intelectual, emissão do conteúdo ou exclusividade de acesso. Essa separação é obrigatória para documentos governamentais, Policies publicadas, registros importados, relações entre Organizations e Evidences emitidas por terceiros.

Toda tabela com registros protegidos possui coluna obrigatória semanticamente equivalente a:

```text
record_owner_organization_id NOT NULL
```

Regras:

- o valor é definido por caso de uso autorizado, nunca copiado sem validação do payload;
- índices de busca protegida começam ou incluem RecordOwnerOrganization conforme o padrão de consulta;
- unicidade organizacional usa constraint composta com RecordOwnerOrganization;
- relações internas à mesma Organization devem preservar owner nas constraints quando aplicável;
- relações interorganizacionais usam contratos e UniversalRelations explícitas;
- IDs isolados nunca comprovam acesso;
- mudança excepcional de RecordOwnerOrganization produz auditoria e segue caso de uso específico.

Transferência de RecordOwnerOrganization não é atualização ordinária. Exige operação específica, Permission própria, auditoria, validação das Organizations de origem e destino e mecanismo técnico revisado, sem conceder bypass genérico de RLS ao runtime.

O tipo definitivo de identificador será decidido na ADR de IDs.

## Row-Level Security

RLS será habilitada em toda tabela protegida:

```text
ENABLE ROW LEVEL SECURITY
FORCE ROW LEVEL SECURITY
```

Políticas devem negar acesso quando o contexto transacional estiver ausente ou inválido. O PostgreSQL aplica negação por padrão quando RLS está ativa e nenhuma policy permite a operação.

Na primeira implementação, policies ordinárias concedem acesso apenas quando RecordOwnerOrganization corresponde à Organization atuante. Acesso compartilhado ou interorganizacional depende de caminho dedicado aprovado posteriormente, sem ampliar genericamente a policy base.

Cuidados obrigatórios:

- runtime não é table owner;
- runtime não é superuser;
- runtime não possui `BYPASSRLS`;
- `FORCE ROW LEVEL SECURITY` também submete o table owner em operações normais;
- `USING` controla linhas existentes e `WITH CHECK` controla valores inseridos ou alterados;
- policies são específicas e testadas para `SELECT`, `INSERT`, `UPDATE` e `DELETE`;
- combinação permissiva/restritiva de policies deve ser explícita;
- `TRUNCATE` e verificações de integridade referencial não são tratados como acesso normal por RLS;
- funções `SECURITY DEFINER` exigem decisão e revisão específica;
- subconsultas em policies são evitadas devido a concorrência, complexidade e risco de vazamento.

A documentação oficial informa que superusers e roles com `BYPASSRLS` ignoram RLS, e que table owners normalmente também ignoram, salvo `FORCE ROW LEVEL SECURITY`. Esses privilégios não podem ser usados pela aplicação.

## Contexto transacional

Depois de validar AuthenticatedPrincipal e autorizações, a Infrastructure inicia transação e define contexto local à transação para a Organization atuante e demais atributos estritamente necessários.

Regras:

- contexto usa escopo local à transação, nunca estado persistente da sessão;
- conexão retirada do pool começa sem contexto confiável;
- caso de uso protegido não executa fora da transação contextualizada;
- commit ou rollback elimina o contexto;
- worker e Synchronization seguem o mesmo fluxo;
- valores de contexto não substituem validação da Application;
- testes comprovam ausência de vazamento entre reutilizações da conexão.

O mecanismo SQL exato será definido e testado no passo de infraestrutura, sem alterar a semântica desta ADR.

## Compartilhamento, publicação e recall

RLS baseada em owner é a proteção mínima. Visibility, Publication e AuthorizationGrant não devem transformar policies de banco em motor de autorização de negócio.

Para leituras interorganizacionais, o módulo owner deve expor um caminho explicitamente autorizado. A implementação pode utilizar projeção por Organization receptora ou outro mecanismo aprovado em ADR posterior.

Até essa decisão:

- runtime não recebe papel com bypass para consultas compartilhadas;
- relação não amplia policy automaticamente;
- consulta cross-Organization genérica é proibida;
- resultado de recall sem visibilidade suficiente é limitado ou inconclusivo;
- dados projetados permanecem derivados e revogáveis;
- source of truth conserva RecordOwnerOrganization original.

Projeção de compartilhamento deve distinguir:

- Organization responsável pela projeção;
- RecordOwnerOrganization do registro de origem;
- referência verificável à fonte;
- AuthorizationGrant que permitiu a derivação;
- validade e estado da concessão.

A projeção não transfere ownership da fonte. Revogação deve impedir novos acessos e atualizar ou invalidar a projeção sem apagar o histórico auditável.

## Papéis de banco

| Papel | Responsabilidade e limites |
|---|---|
| Migration owner | Cria e altera objetos por migrations; pode delegar ownership a role sem login; nunca é credencial de runtime |
| Application runtime | Conecta API e worker; recebe apenas operações necessárias; não cria objetos, altera policies, ignora RLS ou executa `TRUNCATE` protegido |
| Operação administrativa | Separada do runtime; temporária, mínima, auditada e usada apenas por procedimento documentado |

Backup e restore usam papel e procedimento próprios para evitar backup silenciosamente filtrado por RLS.

## Imutabilidade física

Para tabelas append-only, o runtime recebe somente operações necessárias, normalmente `INSERT` e `SELECT`.

`UPDATE`, `DELETE` e `TRUNCATE` são negados. Corrections e Revocations criam novos registros.

Migrations e procedimentos excepcionais preservam cadeia de hashes e exigem plano, justificativa, backup e auditoria.

## Constraints e índices

- `NOT NULL` em campos obrigatórios;
- constraints únicas compostas por RecordOwnerOrganization quando a unicidade for organizacional;
- foreign keys somente dentro do ownership e das fronteiras aprovadas;
- índices começam por Organization quando o padrão de consulta justificar;
- índices para ordem temporal, correlação e reconstrução são definidos por uso comprovado;
- constraint não substitui invariável de domínio;
- mensagens de violação não podem revelar dados de outra Organization.

Foreign keys não são mecanismo de Authorization. Toda referência protegida é validada pela Application no OrganizationContext correto antes da persistência. Erros de integridade são traduzidos para respostas seguras, sem revelar se uma linha externa existe.

O PostgreSQL oferece constraints únicas sobre grupos de colunas, adequadas para unicidade delimitada por Organization.

Ordem de colunas em índices depende de consulta comprovada. RecordOwnerOrganization deve participar quando necessária ao isolamento e ao plano de execução, mas não precisa ser automaticamente a primeira coluna de todo índice.

## Classificação das estruturas persistentes

Toda tabela nova é considerada protegida por padrão. Cada migration declara uma categoria:

| Categoria | Significado |
|---|---|
| `PROTECTED` | Dados pertencentes a uma RecordOwnerOrganization; RLS obrigatória |
| `PLATFORM_INTERNAL` | Dados estritamente técnicos, sem conteúdo de negócio interorganizacional |
| `REFERENCE_CATALOG` | Catálogo ou Publication versionada com Organization responsável definida |
| `DERIVED_PROJECTION` | Projeção reconstruível com origem, owner e regras de Visibility preservados |

Classificar tabela fora de `PROTECTED` exige justificativa expressa na migration e no passo de implementação. Estrutura técnica não pode armazenar dados de domínio para contornar RecordOwnerOrganization ou RLS.

Catálogos e projeções não são implicitamente globais. Sua categoria define controles adicionais, não exceção automática de Authorization.

## Transações e concorrência

`READ COMMITTED` será o nível padrão inicial, combinado com versão de agregado e concorrência otimista.

Casos que exigirem snapshot estável ou invariáveis entre múltiplas linhas podem usar `REPEATABLE READ`, `SERIALIZABLE` ou locks explícitos, com justificativa no caso de uso e testes concorrentes.

Operações sujeitas a falha de serialização devem ser idempotentes e capazes de repetir a transação completa. Nível mais forte não será aplicado globalmente sem evidência.

Event, mudança de estado e OutboxMessage pertencentes à mesma operação são gravados na mesma transação.

## Migrations

- toda alteração de schema possui migration versionada;
- alteração manual é proibida;
- migration pertence ao módulo owner;
- aplicação e reversão são testadas em banco descartável;
- migration destrutiva exige plano específico e autorização;
- mudança em tabela protegida preserva ou recria RLS, grants, constraints e índices;
- estado das migrations é verificável;
- deploy não depende de auto-criação de tabelas pelo ORM.

## Backup, restauração e auditoria

- backups incluem todos os schemas e objetos necessários;
- procedimento deve falhar, não omitir silenciosamente linhas por RLS;
- restauração é testada periodicamente;
- verificação pós-restauração inclui migrations, contagens, RLS e cadeia de integridade;
- credenciais de backup são separadas;
- acesso a backup é auditado;
- política de retenção será definida separadamente.

## Operação e observabilidade

Observabilidade operacional, administração de dados e manutenção do banco são capacidades separadas:

- observabilidade pode consultar latência, locks, deadlocks, uso de índices, contagens agregadas, saúde e falhas de migration sem ler conteúdo protegido;
- administração de dados exige autorização privilegiada, finalidade, procedimento e auditoria;
- manutenção do banco utiliza papel próprio e não concede acesso funcional pelo Titan;
- métricas e logs não devem copiar payloads, Decisions, Evidences ou Documents sem necessidade aprovada.

Papel de observabilidade não recebe acesso a linhas protegidas apenas por precisar monitorar o serviço.

## Consequências

### Positivas

- banco compatível com transações e constraints do Core;
- defesa adicional contra consulta sem Organization;
- ownership modular visível por schema;
- imutabilidade reforçada por privilégios;
- migrations e restauração reproduzíveis;
- outbox transacional no mesmo banco.

### Negativas

- RLS aumenta complexidade de migrations e testes;
- contexto transacional precisa integrar o pool de conexões;
- compartilhamento interorganizacional exige caminho dedicado;
- schemas por módulo exigem qualificação e disciplina;
- operações administrativas tornam-se mais rigorosas.

### Riscos e controles

| Risco | Controle |
|---|---|
| Runtime ignorar RLS | Role não owner, sem superuser/BYPASSRLS, FORCE RLS |
| Conexão reutilizar contexto | Configuração local à transação e teste de pool |
| Policy permitir mais que o esperado | Default deny e testes por comando |
| Constraint revelar existência externa | Design composto, erros seguros e testes negativos |
| `search_path` executar objeto indevido | Nomes qualificados e CREATE restrito |
| Compartilhamento virar bypass | Caminho dedicado sem papel privilegiado genérico |
| Backup omitir linhas | Procedimento específico e teste de restauração |
| Migration remover proteção | Verificação automatizada de RLS e grants |
| Append-only ser alterado | Privilégios sem UPDATE/DELETE/TRUNCATE |
| Tabela ser declarada “técnica” para evitar RLS | Proteção por padrão e justificativa na migration |
| Projeção ocultar owner da fonte | Dois contextos de Organization, referência e concessão preservados |
| Operação confundir métrica com acesso a dados | Papéis separados e observabilidade sem conteúdo protegido |

## Verificação automatizada do schema

Testes de integração consultam catálogos do PostgreSQL e fazem a CI falhar quando uma tabela classificada como protegida:

- não possui RecordOwnerOrganization obrigatória;
- não possui RLS habilitada;
- não possui `FORCE ROW LEVEL SECURITY`;
- não possui policies para operações autorizadas;
- concede `UPDATE`, `DELETE` ou `TRUNCATE` indevidos ao runtime;
- está no schema incorreto;
- possui owner, grants ou categoria incompatíveis;
- permite acesso com contexto ausente ou de outra Organization.

A CI também valida que toda tabela possui classificação e módulo estrutural responsável.

## O que esta ADR não decide

- versão major exata do PostgreSQL;
- tipo definitivo de IDs;
- ORM ou driver;
- ferramenta de migrations;
- mecanismo final para Visibility compartilhada;
- armazenamento binário de Documents;
- retenção e descarte;
- alta disponibilidade e topologia de produção;
- PostGIS.

## Critérios de aceitação

A ADR pode ser aceita quando:

- PostgreSQL for confirmado como banco transacional;
- schemas forem organizados por módulo, não por Organization;
- toda tabela protegida exigir RecordOwnerOrganization;
- RLS for defesa em profundidade, não única autorização;
- runtime não puder ignorar RLS;
- primeira policy ordinária limitar owner à Organization atuante;
- contexto for local à transação;
- compartilhamento não criar bypass genérico;
- tabelas append-only negarem mutação ao runtime;
- transações e outbox preservarem atomicidade;
- migrations e backups tiverem verificação explícita;
- toda tabela possuir classificação e responsável estrutural;
- CI verificar RLS, FORCE RLS, policies, grants e privilégios do runtime;
- observabilidade não exigir acesso ao conteúdo protegido;
- detalhes ainda não decididos permanecerem fora do escopo.

## Plano de reversão

Antes da primeira migration, a decisão pode ser substituída por nova ADR. Depois da persistência, mudança de banco, estratégia de schemas ou RLS exige ADR, migração incremental, validação de isolamento, plano de rollback e preservação integral da auditoria.
