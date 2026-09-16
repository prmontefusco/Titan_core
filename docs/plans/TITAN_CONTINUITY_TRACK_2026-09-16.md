# Titan Continuity Track — 2026-09-16

Status: guia operacional de continuidade

Este documento registra a trilha combinada para continuar o Titan depois da
correcao do compose BuyerPolicy e da analise estrategica baseada nos documentos
de autoridade e no material `docs/outros/PUBLICADO_AgriHub Conecta-ONLINE.pdf`.

Ele nao e SPEC, nao e backlog completo e nao substitui
`docs/CHECKLIST_DE_IMPLEMENTACAO.md`. O checklist continua sendo o ledger do que
foi efetivamente entregue e validado. Cada incremento abaixo ainda deve seguir o
fluxo canonico de `DEVELOPMENT.md`:

`IDEA -> DISCOVERY -> DECISION -> SPEC -> PLAN -> BUILD -> VERIFY -> ACCEPT`

## Direcao de produto

O Titan deve priorizar a camada de confianca que transforma evidencias rurais em
prontidao comercial, regulatoria e operacional. A proposta nao e criar um ERP,
nem um marketplace prematuro, nem uma ferramenta generica de cadastro.

O foco imediato e terminar o basico com profundidade:

1. evidencias auditaveis;
2. linha do tempo;
3. avaliacao por finalidade;
4. lacunas acionaveis;
5. dossie verificavel;
6. compartilhamento seletivo;
7. simulacao economica/regulatoria quando a base estiver madura.

## Trilha de produto

### 1. Fechar BuyerPolicy Fase 3/4

Objetivo: deixar completo e verificavel o fluxo comprador-fornecedor.

Ordem recomendada:

- validar manualmente os roteiros BuyerPolicy existentes;
- concluir o Incremento 4: snapshot e acesso pos-expiracao;
- ajustar o checklist com o estado real;
- garantir que logs, auditoria, response models e limites de visibilidade expliquem
  corretamente o que aconteceu;
- so depois iniciar novas capacidades comerciais.

Criterio de pronto:

- comprador compartilha criterio contratual;
- fornecedor autoavalia sujeito autorizado;
- comprador compoe a avaliacao contratual com matriz regulatoria;
- comprador consulta historico e trilha de acesso;
- acesso pos-expiracao preserva evidencia historica dentro dos limites aprovados.

### 2. Ligar Commercial Passport real minimo

Objetivo: transformar a base tecnica em uma experiencia de produto reconhecivel
para o produtor.

Primeiro corte:

- uma propriedade;
- oportunidades comerciais conhecidas;
- readiness de propriedade;
- resumo populacional quando disponivel;
- lacunas explicitas;
- sem marketplace;
- sem disclosure externo;
- sem score opaco.

Criterio de pronto:

- o produtor consegue ver para quais oportunidades esta pronto, quase pronto ou
  bloqueado, e por que.

### 3. Criar motor de lacunas e acoes recomendadas

Objetivo: sair de resultado estatico para proxima acao operacional.

Primeiro corte:

- classificar lacuna como `MISSING`, `UNKNOWN`, `EXPIRED`, `INSUFFICIENT` ou
  `BLOCKING`;
- mapear impacto por mercado, comprador ou oportunidade;
- gerar recomendacao operacional simples;
- preservar que recomendacao nao e decisao regulatoria, nao e garantia comercial
  e nao substitui Policy/Evaluation/Decision.

Criterio de pronto:

- cada bloqueio relevante possui explicacao, evidencia esperada e proxima acao
  possivel.

### 4. Fortalecer o cofre de evidencias do produtor

Objetivo: consolidar a base de prova que alimenta prontidao comercial e
regulatoria.

Prioridade:

- GTA declarada/importada;
- CAR, geometria e permanencia;
- tratamentos, medicamentos, prescricao e carencia;
- SISBOV quando houver caminho oficial e autorizado;
- documentos e anexos com provenance, validade, cobertura e limitacoes.

Criterio de pronto:

- o Titan sabe dizer quais evidencias existem, que periodo cobrem, que finalidade
  atendem e onde ha lacuna.

### 5. Preparar experiencia simples e tolerante ao campo

Objetivo: reduzir atrito para produtor real antes de existir parceiro formal.

Primeiro corte:

- importacao manual assistida;
- roteiros simples;
- erros compreensiveis;
- dossie/exportacao;
- desenho offline-friendly quando a operacao justificar;
- linguagem de beneficio: vendavel, financiavel, menos exposto.

## Trilha operacional do Codex

Cada nova sessao ou incremento relevante deve iniciar com uma retomada curta:

```text
RETOMADA
Objetivo:
Estado atual:
Decisao ja aprovada:
Arquivos provaveis:
Risco:
Proximo passo:
```

### 1. RETOMADA

Ler, quando aplicavel:

- `VISION.md`;
- `DOMAIN.md`;
- `ARCHITECTURE.md`;
- `DEVELOPMENT.md`;
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`;
- ADR/SPEC/PLAN do incremento em curso.

Saida esperada:

- estado atual;
- proximo passo;
- bloqueadores;
- arquivos ou fronteiras provaveis.

### 2. DISCOVERY curta

Antes de implementar capacidade nova:

- confirmar se ja existe capacidade parecida;
- localizar testes, rotas, services e migrations relacionadas;
- identificar se pertence ao Core ou a uma vertical;
- classificar a mudanca como GREEN, YELLOW ou RED conforme `DEVELOPMENT.md`;
- apontar conflito com documentos de autoridade antes de escrever codigo.

Saida esperada:

- `PROCEED`, `DEFER` ou `NEED DECISION`.

### 3. SPEC/PLAN proporcional

Para incremento pequeno, plano curto pode bastar. Para comportamento relevante,
API, migration, contrato publico, seguranca, tenancy, auditoria ou nova entidade,
usar SPEC/PLAN formal.

O plano deve declarar:

- objetivo;
- fora de escopo;
- arquivos/fronteiras;
- testes;
- comportamento observavel;
- riscos.

### 4. BUILD

Regras de execucao:

- uma funcionalidade por vez;
- sem refatoracao fora do escopo;
- sem abstracao futura sem uso atual;
- sem enfraquecer regra de negocio;
- sem alterar dominio, ADR, API publica ou dependencia sem decisao aplicavel;
- criar ou atualizar roteiro em `apps/validacao` quando houver comportamento
  observavel por API.

### 5. VERIFY

Portao padrao:

```text
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
python -m uv run --locked alembic -c packages/asset_infrastructure/persistence/migrations/alembic.ini check
```

Para API observavel:

- teste focado primeiro;
- roteiro manual executavel;
- suite completa depois.

### 6. ACCEPT

Antes do commit:

- revisar diff;
- listar riscos residuais;
- atualizar checklist se houve Marco, Passo ou etapa observavel entregue;
- commit limpo com mensagem objetiva.

## Fila imediata recomendada

1. Retomada BuyerPolicy pos-commit: checklist, roteiros manuais e Incremento 4.
2. BuyerPolicy Incremento 4: snapshot e acesso pos-expiracao.
3. Commercial Passport pipeline minima: projection real minima atras da API
   release-gated.
4. Gap Engine v1: lacunas e acoes recomendadas.
5. Cofre de evidencias v1: visao consolidada por propriedade/animal.

## Notas estrategicas do PDF AgriHub Conecta

O material do AgriHub Conecta reforca que a adocao pelo produtor depende de ganho
compreensivel, simplicidade e validacao em campo. As dores mapeadas incluem custo
operacional, credito, gestao, mao de obra, energia/frete, selos de qualidade e
sustentabilidade, alem de maturidade digital desigual.

Implicacao para o Titan:

- apresentar regulacao como prontidao comercial, nao como burocracia;
- priorizar lacunas acionaveis e linguagem operacional;
- tratar o cofre de evidencias como ativo economico do produtor;
- manter a arquitetura de confianca forte, mas entregar experiencia simples.
