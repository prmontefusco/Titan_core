# ADR 0001 — Arquitetura inicial do Titan: monólito modular

**Status:** Aceita  
**Data:** 20 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan será uma plataforma reutilizável para cadeias reguladas. O Titan Core deve permanecer independente das verticais, enquanto cada vertical fornece entidades, fatos, relações, regras, providers, adaptadores e templates próprios.

O MVP precisa privilegiar corretude, segurança, auditoria e entregas pequenas. Distribuir prematuramente o sistema em serviços independentes aumentaria a complexidade de transações, integridade, observabilidade, desenvolvimento local e operação.

Os documentos atuais também apresentam duas organizações diferentes: uma estrutura genérica baseada em `src/` e uma estrutura com `apps/` e `packages/`. É necessário definir uma única direção antes da criação de código.

## Problema

Definir a arquitetura de implantação inicial e a organização do repositório de forma que:

- o Core não dependa das verticais;
- domínio, aplicação, infraestrutura e apresentação permaneçam separados;
- executáveis não sejam confundidos com módulos de negócio;
- limites entre módulos possam ser verificados automaticamente;
- o ambiente local seja simples e reproduzível;
- futuras extrações de componentes sejam possíveis sem antecipá-las.

## Princípios arquiteturais

Esta decisão é fundamentada nos seguintes princípios:

1. **Domínio independente:** regras de negócio não dependem de frameworks, bancos, protocolos ou mecanismos de entrega.
2. **Dependências orientadas para dentro:** detalhes externos implementam contratos definidos pelas camadas internas.
3. **Core independente das verticais:** verticais usam contratos públicos do Core; o Core nunca conhece uma vertical.
4. **Fronteiras explícitas:** módulos colaboram por contratos públicos ou eventos aprovados, não por acesso oportunista a detalhes internos.
5. **Ownership definido:** cada dado, agregado e contrato possui exatamente um módulo responsável por sua escrita e evolução técnica.
6. **Auditabilidade por padrão:** a organização interna não pode permitir caminhos que contornem autorização, eventos, integridade ou auditoria.
7. **Evolução incremental:** somente estruturas exigidas pelo passo atual são criadas; generalizações dependem de necessidade comprovada.
8. **Simplicidade operacional:** distribuição física só é introduzida quando seus benefícios justificarem transações e operação distribuídas.
9. **Verificação automática:** fronteiras relevantes devem ser protegidas por testes arquiteturais, não apenas por convenção.
10. **Contratos estáveis:** detalhes internos podem evoluir sem quebrar consumidores autorizados.

## Alternativas consideradas

### 1. Monólito em uma única árvore `src/` organizada apenas por camada

```text
src/
  domain/
  application/
  infrastructure/
  interfaces/
```

**Vantagens:** estrutura inicial pequena e familiar.

**Desvantagens:** tende a agrupar módulos diferentes na mesma camada, reduz a visibilidade de ownership e facilita dependências acidentais entre Core e verticais.

### 2. Monólito modular com `apps/` e `packages/`

```text
apps/
  api/
  worker/
  web/                  # opcional e não inicial

packages/
  shared_kernel/
  core_contracts/
  core_domain/
  core_application/
  core_infrastructure/
  testing/
  <vertical>_domain/
  <vertical>_application/
  <vertical>_infrastructure/
```

**Vantagens:** separa executáveis de módulos, explicita Core e verticais, favorece testes arquiteturais e permite evolução incremental.

**Desvantagens:** exige disciplina de dependências, configuração do monorepo e convenções claras desde o início.

### 3. Microserviços

**Vantagens:** implantação e escala independentes por serviço.

**Desvantagens:** introduz comunicação distribuída, consistência eventual, observabilidade e operação incompatíveis com a fase atual. Aumenta o risco de quebrar auditabilidade e transações antes da validação do produto.

### 4. Repositórios separados para Core e cada vertical

**Vantagens:** isolamento físico forte.

**Desvantagens:** dificulta mudanças coordenadas de contratos, testes ponta a ponta e desenvolvimento greenfield; adiciona versionamento e publicação de pacotes antes de haver necessidade comprovada.

## Decisão proposta

Adotar um **monólito modular em monorepo**, organizado em `apps/` e `packages/`.

### Separação conceitual

`apps/` e `packages/` não são apenas categorias de diretório:

```text
apps     = executáveis, composição e mecanismos de entrega
packages = capacidades reutilizáveis, contratos e implementações internas
```

Um app inicia um processo e conecta adaptadores a casos de uso. Um package oferece uma capacidade que pode ser utilizada por mais de um executável, preservando as regras de dependência.

API e worker, por exemplo, podem invocar a mesma capacidade de aplicação. Eles não devem possuir implementações próprias da mesma regra de negócio.

### Responsabilidade de `apps/`

`apps/` contém somente pontos de entrada executáveis e composição:

- `api/`: aplicação HTTP;
- `worker/`: consumidor de tarefas assíncronas;
- `web/`: cliente ou console web, criado somente quando um passo aprovado exigir.

Um app pode configurar dependências, rotas, processos e lifecycle. Ele não contém regras de negócio.

Código exclusivo de um mecanismo de entrega pode permanecer no app, desde que não represente capacidade de domínio reutilizável. A simples existência de código em mais de um app não autoriza criar abstração compartilhada; a extração deve responder a uma necessidade concreta.

### Responsabilidade de `packages/`

`packages/` contém os módulos internos do monólito:

- Shared Kernel e contratos universais;
- camadas do Titan Core;
- infraestrutura do Core;
- suporte de testes;
- camadas de cada vertical, quando autorizadas.

A lista inicial de diretórios deve ser criada incrementalmente. Esta ADR não autoriza criar pacotes sem uso no passo em execução.

Um package deve possuir responsabilidade identificável, consumidor real e fronteira testável. Nomes previstos no desenho arquitetural não obrigam sua criação antecipada.

### Direção das dependências

Dentro de um módulo:

```text
Domain ← Application ← Infrastructure/Presentation
```

As dependências apontam para dentro:

- Domain não depende de framework, banco, mensageria ou apresentação;
- Application depende de Domain e contratos internos;
- Infrastructure implementa portas definidas pelas camadas internas;
- apps compõem implementações e adaptadores;
- verticais podem depender de contratos públicos do Core;
- Core nunca depende de uma vertical;
- uma vertical não acessa tabelas ou tipos internos de outra vertical;
- integrações entre módulos usam contratos públicos ou eventos aprovados.

### Isolamento lógico

Cada módulo deve possuir ownership explícito de seus dados e contratos. Compartilhar processo ou banco não autoriza acesso direto às tabelas de outro módulo.

Isolamento por Organization é obrigatório em todas as camadas aplicáveis e será detalhado em ADR própria.

### Ownership de dados e agregados

Ownership técnico de módulo e responsabilidade de negócio da Organization são conceitos diferentes:

- a Organization determina isolamento, responsabilidade e autorização sobre o registro;
- o módulo determina qual capacidade pode criar, validar, alterar por novo evento e evoluir tecnicamente aquele registro.

Cada tabela, coleção, projeção persistida, migration e contrato público deve possuir um único módulo owner. Somente esse módulo pode escrever diretamente em suas estruturas internas.

Um agregado, depois de formalizado em `DOMAIN.md`, representa uma fronteira de consistência transacional e invariantes. Ele pertence a um único módulo. Outro módulo não altera suas entidades internas; solicita uma operação por contrato público ou reage a evento publicado.

Regras de colaboração:

- leitura de outro módulo ocorre por contrato público, referência tipada ou projeção autorizada;
- escrita ocorre exclusivamente por caso de uso do módulo owner;
- transação não deve atualizar diretamente estruturas internas de múltiplos módulos;
- eventos publicados não transferem ownership;
- projeções derivadas pertencem ao módulo consumidor, mas não se tornam fonte de verdade;
- referências entre módulos não autorizam navegação irrestrita nem acesso entre Organizations;
- mudança de ownership exige ADR e plano de migração.

Esta ADR não decide a estratégia física de schemas, bancos ou chaves estrangeiras entre módulos. Essa decisão será tomada junto à persistência, preservando as regras acima.

### Crescimento incremental da estrutura

A árvore apresentada é um mapa de destinos possíveis, não uma ordem para criar diretórios vazios.

Para criar um novo app ou package, o passo em execução deve demonstrar:

1. capacidade ou mecanismo de entrega necessário agora;
2. consumidor real;
3. owner definido;
4. contratos e dependências permitidas;
5. teste proporcional à fronteira criada.

É proibido criar package para funcionalidade futura, duplicar camadas sem comportamento ou extrair abstração apenas por semelhança nominal. Diretórios, contratos e adaptadores surgem no primeiro passo que efetivamente os utiliza.

### Verificação arquitetural

A fundação deve incluir testes automatizados que verifiquem:

- ausência de dependência do Core para verticais;
- ausência de framework e infraestrutura no Domain;
- dependências acíclicas;
- ausência de importação entre módulos por caminhos internos não públicos;
- ausência de conceitos específicos de vertical no Core.

## Consequências

### Positivas

- desenvolvimento e testes locais mais simples que em arquitetura distribuída;
- transações e auditoria podem permanecer consistentes no mesmo processo;
- fronteiras ficam visíveis na árvore do repositório;
- Core e verticais podem evoluir no mesmo commit quando um contrato aprovado exigir;
- apps permanecem pequenos e substituíveis;
- workers e API reutilizam as mesmas camadas de aplicação sem duplicar regras.

### Negativas

- limites são lógicos e dependem de testes e disciplina;
- um banco compartilhado exige controle rigoroso de ownership;
- implantação inicial ocorre como uma unidade, exceto processos como worker;
- o repositório terá mais configuração que uma única árvore `src/`.

### Riscos e controles

| Risco | Controle |
|---|---|
| Monólito virar código acoplado | Testes arquiteturais e contratos públicos |
| `apps/` receber regra de negócio | Revisão de dependências e testes |
| Core conhecer uma vertical | Teste específico de imports e vocabulário |
| Acesso direto a dados de outro módulo | Ownership documentado e portas de aplicação |
| Pacotes vazios ou especulativos | Criação incremental, somente no passo autorizado |
| Ownership ambíguo | Um owner por dado, agregado, migration e contrato público |
| Regras duplicadas entre API e worker | Apps reutilizam a mesma capacidade de aplicação |
| Extração prematura de serviços | Exigir nova ADR e evidência operacional |

## O que esta ADR não decide

- tecnologia do OIDC Provider;
- tecnologia do Message Broker;
- banco e armazenamento de documentos;
- estratégia detalhada de Organization;
- protocolo offline;
- formato final dos contratos públicos;
- implantação em produção;
- extração futura de serviços.

Esses temas exigem decisões independentes.

## Critérios de aceitação

A ADR pode ser aceita quando:

- `apps/` estiver limitado a executáveis e composição;
- `packages/` estiver definido como local dos módulos;
- a direção das dependências estiver inequívoca;
- Core e verticais tiverem fronteira explícita;
- frontend permanecer opcional no início;
- nenhum pacote futuro tiver sido implicitamente autorizado;
- os conflitos com `ARCHITECTURE.md` estiverem identificados para harmonização posterior.

## Plano de reversão

Antes da criação de código, a decisão pode ser revertida apenas atualizando esta ADR e os documentos de arquitetura. Depois da fundação, qualquer mudança de estrutura exige nova ADR, plano de migração incremental e preservação dos contratos públicos.
