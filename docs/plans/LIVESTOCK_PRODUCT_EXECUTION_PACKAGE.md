# LIVESTOCK_PRODUCT_EXECUTION_PACKAGE

Status: BASELINE_DE_EXECUCAO_PROPOSTA
Date: 2026-08-05
Scope: Pacote de execução de produto para a primeira onda de entrega frontend/backend do Livestock

## 1. Propósito

Este documento converte o baseline concluído do backend Livestock em um plano executável de produto.

Ele não reabre o modelo de domínio.
Ele não substitui o plano arquitetural aprovado.
Ele não autoriza, por si só, nova expansão de domínio.

Seu papel é mais estreito e prático:

- definir quais jornadas de usuário do Livestock devem virar produto primeiro;
- definir o contrato mínimo de telas para essas jornadas;
- definir a ordem de entrega entre endurecimento do backend, implementação do frontend e validação manual;
- definir o fechamento operacional necessário antes de considerar utilizável a primeira fatia de produto do Livestock.

## 2. Posição do Produto

O Titan Livestock está pronto para sair de "capacidade governada de backend" para "fatia de produto voltada ao operador".

A plataforma já comprova:

- registro sanitário de tratamentos;
- elegibilidade governada por `Policy`;
- elegibilidade orientada a mercado por animal e por lote;
- explicação comercial por mercado;
- revisão humana de decisões oficiais;
- geração de dossiê;
- reflexão operacional outbound para ERP sem autoridade sanitária do ERP.

O próximo movimento correto não é uma nova etapa de expansão de domínio.
O próximo movimento correto é uma etapa de execução de produto sobre contratos já aceitos.

## 3. Fundação Comprovada

Este pacote deriva do estado atual do repositório e dos artefatos já aprovados:

- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [CORTE_MVP_BACKEND.md](/C:/programing/Titan/docs/CORTE_MVP_BACKEND.md)
- [LIVESTOCK_EXECUTIVE_CLOSURE_LIV_C01_TO_C09.md](/C:/programing/Titan/docs/plans/LIVESTOCK_EXECUTIVE_CLOSURE_LIV_C01_TO_C09.md)
- [LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md)

Evidência de repositório para a shell atual de frontend:

- [apps/web/src/App.tsx](/C:/programing/Titan/apps/web/src/App.tsx)
- [apps/web/src/components/Dashboard.tsx](/C:/programing/Titan/apps/web/src/components/Dashboard.tsx)

O `apps/web` atual ainda não é um frontend de produto do Livestock.
Ele é uma shell autenticada com fluxo de aprovação/status e um dashboard placeholder.

## 4. Objetivo de Execução

Entregar a primeira fatia real de produto Livestock na qual um operador possa:

1. identificar o contexto da organização;
2. localizar animais e lotes;
3. inspecionar histórico sanitário e posição comercial atual;
4. registrar aplicação de tratamento;
5. avaliar elegibilidade e posição por mercado;
6. entender por que um mercado está bloqueado, condicionado ou inconclusivo;
7. disparar e acompanhar o fluxo oficial de revisão humana quando a emissão automática da decisão for recusada;
8. inspecionar a decisão resultante e o dossiê.

## 5. Princípios de Produto

Todo incremento de produto neste pacote deve preferir:

1. reaproveitamento de contratos existentes de backend antes de adicionar novos endpoints;
2. explicação antes de cosmética de dashboard;
3. fluxos de leitura antes de expansão de escrita;
4. corretude operacional antes de amplitude de relatórios;
5. limitações explícitas antes de atalhos otimistas de UX;
6. scripts de validação manual junto de todo comportamento observável.

Nenhuma tela deste pacote pode inventar uma conclusão de domínio que o backend ainda não produza.

## 6. Fechamento Operacional Antes da Expansão de Produto

Antes de considerar pronta para uso interno a primeira fatia de produto Livestock, a equipe deve fechar este checklist operacional:

- confirmar que a branch está limpa e que o reparo recente de CI foi commitado;
- reexecutar o portão de qualidade do repositório escolhido para o release candidate;
- confirmar que os scripts de validação do Livestock continuam passando depois dos primeiros ajustes de API para o frontend;
- verificar login OIDC local, resolução de organização e chamadas protegidas à API através do `apps/web`;
- confirmar que nenhum trabalho pendente de produto depende de comportamento de adapter ERP real;
- confirmar que os scripts manuais existentes continuam sendo a fonte de verdade para aceite do produto.

Portão de release recomendado para a primeira fatia utilizável:

- `python -m uv run --locked pytest`
- `python -m uv run --locked ruff check .`
- `python -m uv run --locked ruff format --check .`
- `python -m uv run --locked mypy`
- `python -m uv run --locked alembic check`
- comandos de build e teste do frontend em `apps/web`
- validação manual direcionada via `apps/validacao`

Se permanecerem falhas pré-existentes do repositório fora do incremento, elas devem ser registradas explicitamente e separadas da decisão de aceite da fatia de produto.

## 7. Jornadas de Usuário Priorizadas

A primeira onda de produto não deve buscar paridade total com toda capacidade de backend.
Ela deve priorizar jornadas que exponham o valor do backend governado que já foi concluído.

### J1. Home operacional do Livestock

Resultado para o usuário:
O operador chega a um dashboard do Livestock que explica o que já pode ser feito agora e mostra os principais pontos de entrada.

Por que vem primeiro:
A shell atual do `apps/web` já autentica usuários e resolve status.
Este é o caminho mais estreito entre a capacidade web existente e uma superfície real de produto.

### J2. Busca e detalhe de animal

Resultado para o usuário:
O operador encontra um animal e abre uma página única de detalhe com identidade, estado atual e atalhos para timeline, tratamentos, elegibilidade e mercados.

Por que vem em segundo:
O animal é a âncora natural do modelo sanitário e simplifica a primeira jornada real de leitura.

### J3. Registro de tratamento

Resultado para o usuário:
O operador registra uma aplicação de tratamento com a evidência mínima suportada e vê imediatamente que ela entrou no histórico autoritativo.

Por que vem em terceiro:
Esta é a primeira jornada de escrita com valor direto de negócio e alimenta o restante do produto.

### J4. Timeline sanitária

Resultado para o usuário:
O operador entende o que aconteceu com o animal ao longo do tempo, incluindo histórico de tratamentos e sinais sanitários relevantes.

Por que vem em quarto:
A timeline é o principal ativo de explicabilidade e reduz atrito de suporte em todas as telas seguintes.

### J5. Elegibilidade do animal

Resultado para o usuário:
O operador executa a elegibilidade de um animal, vê o resultado, entende se a conclusão é aprovada, restrita ou indeterminada, e compreende as razões.

Por que vem em quinto:
Esta é a primeira tela em que o modelo de decisão do Titan aparece como valor de produto.

### J6. Matriz de mercado e explicação comercial

Resultado para o usuário:
O operador responde "para onde posso vender, por que não posso e qual é a próxima ação?" para um animal.

Por que vem em sexto:
Esta é a capacidade mais inteligível comercialmente que já está implementada.

### J7. Visão comercial do lote

Resultado para o usuário:
O operador abre um lote e vê posição agregada por mercado, membros afetados e próxima ação necessária.

Por que vem em sétimo:
Isso transforma as capacidades de lote do backend em ferramenta operacional de planejamento.

### J8. Fluxo de revisão humana

Resultado para o usuário:
Quando a emissão automática é recusada, o operador consegue inspecionar a proposta, registrar a revisão oficial e acessar a decisão emitida e o dossiê.

Por que vem em oitavo:
Este é um fluxo de governança mais alto e deve vir depois que as jornadas centrais de leitura/escrita estiverem estáveis.

## 8. Fora de Escopo da Primeira Onda de Produto

Estes itens ficam intencionalmente fora da primeira fatia de produto Livestock:

- operação de adapter ERP real e callbacks;
- expansão territorial além do que já foi aceito no backend;
- nova modelagem regulatória de mercado;
- dashboards analíticos ou BI generalizados;
- operação offline mobile-first;
- autoria de novas regras pelo frontend;
- fluxos de rastreabilidade de produto e transformação industrial fora da fatia aprovada do Livestock.

## 9. Contrato de Telas

O frontend não deve começar como um sistema genérico de menus.
Ele deve começar como um produto compacto com um pequeno conjunto de páginas autoritativas.

### Tela S1. Home do Livestock

Propósito:
Ponto de entrada do operador do Livestock.

Conteúdo mínimo:

- organização ativa;
- resumo das capacidades do Livestock disponíveis neste ambiente;
- atalhos para animais, lotes, tratamentos, análise de mercado e revisão humana;
- nota explícita quando uma capacidade ainda depender de fluxo por script/manual.

Ações principais:

- abrir busca de animal;
- abrir busca de lote;
- registrar tratamento;
- abrir fila de revisão.

### Tela S2. Busca de Animal

Propósito:
Localizar animais pelos identificadores já suportados pelos dados do backend.

Conteúdo mínimo:

- campo de busca e controles de filtro;
- lista de resultados com resumo de identidade do animal;
- navegação direta para o detalhe do animal.

Ações principais:

- abrir detalhe do animal.

### Tela S3. Detalhe do Animal

Propósito:
Hub operacional único para um animal.

Conteúdo mínimo:

- identificadores canônicos;
- propriedade ou contexto atual, quando disponível;
- resumo sanitário/comercial atual;
- links para timeline, tratamentos, elegibilidade, matriz de mercado e fluxos relacionados a dossiê.

Ações principais:

- registrar tratamento;
- abrir timeline;
- executar elegibilidade;
- executar análise de mercado.

### Tela S4. Registro de Tratamento

Propósito:
Registrar uma nova aplicação de tratamento usando o contrato atual do backend.

Conteúdo mínimo:

- animal selecionado;
- lote de medicamento;
- instante de aplicação;
- dose;
- referências de evidência ou notas, quando suportado;
- feedback claro de sucesso/falha.

Ações principais:

- submeter aplicação;
- retornar ao detalhe do animal.

### Tela S5. Timeline do Animal

Propósito:
Mostrar a narrativa sanitária histórica sem reescrever história.

Conteúdo mínimo:

- entradas cronológicas;
- tipo de evento ou tipo de fato;
- timestamps relevantes;
- correções ou limitações, quando presentes.

Ações principais:

- inspecionar detalhes de uma entrada;
- voltar ao detalhe do animal.

### Tela S6. Elegibilidade do Animal

Propósito:
Expor o resultado oficial atual de elegibilidade para um animal.

Conteúdo mínimo:

- outcome;
- reasons;
- limitations;
- identificadores de evaluation e decision;
- link para dossiê, quando emitido;
- estado explícito de revisão necessária quando a emissão automática for recusada.

Ações principais:

- abrir fluxo de proposta/revisão quando necessário;
- abrir dossiê quando disponível;
- abrir matriz de mercado.

### Tela S7. Matriz de Mercado

Propósito:
Explicar posição por mercado e próxima ação para um animal.

Conteúdo mínimo:

- mercados solicitados;
- status por mercado;
- `summary`, `why`, `next_action`;
- estado de seleção de dependência quando um sujeito como frigorífico for exigido;
- gaps e reasons sem normalização silenciosa.

Ações principais:

- reexecutar com seleção de mercados;
- reexecutar com sujeito dependente exigido;
- abrir explicação comercial.

### Tela S8. Explicação Comercial

Propósito:
Dar ao operador uma explicação legível pelo negócio para comercialização de animal ou lote.

Conteúdo mínimo:

- `commercial_outlook`;
- narrativa;
- próxima ação recomendada;
- lista de mercados com status e membros afetados quando o sujeito for um lote.

Ações principais:

- abrir detalhe do sujeito;
- ajustar sujeito dependente exigido;
- encaminhar para revisão humana quando necessário.

### Tela S9. Detalhe do Lote e Mercados do Lote

Propósito:
Expor o lote como sujeito operacional, não apenas como lista de membros.

Conteúdo mínimo:

- identidade do lote;
- contagem de membros;
- resumo da lista de membros;
- avaliação agregada por mercado;
- drill-down de animais afetados.

Ações principais:

- executar análise de mercado do lote;
- inspecionar animais afetados.

### Tela S10. Workspace de Revisão Humana

Propósito:
Transformar proposta/revisão/decisão/dossiê em fluxo de produto, e não apenas em endpoint técnico.

Conteúdo mínimo:

- resumo da proposta;
- indicador de atualidade;
- contagem de revisões e aprovações exigidas;
- entrada de fundamentação humana;
- resultado da decisão emitida;
- acesso ao dossiê após emissão.

Ações principais:

- registrar revisão;
- abrir decisão;
- abrir dossiê.

## 10. Estratégia de Contrato de Backend

A primeira onda de produto deve preferir superfícies de API já existentes e adicionar apenas contratos finos de suporte à leitura quando necessário.

Regra padrão:

- se o backend já retorna a informação necessária para uma tela, o frontend deve se adaptar a esse contrato;
- se a informação existe, mas exige múltiplas chamadas, um endpoint fino e orientado a leitura é aceitável;
- se a tela exigir nova semântica de domínio, a tela deve ser adiada em vez de inventar isso na UI.

Adições de backend aceitáveis neste pacote:

- endpoints orientados a leitura para listagem/busca de animais ou lotes;
- endpoints orientados a agregação de leitura que reduzam orquestração no frontend;
- pequenas melhorias de shape de resposta que não alterem o significado de domínio;
- mensagens de validação e metadados seguros para UX.

Adições de backend não aceitáveis neste pacote:

- criação de novo aggregate ou entity sem aprovação separada;
- lógica de mercado movida para controllers ou frontend;
- verdade do ERP importada para fluxos sanitários;
- semânticas de fallback silencioso criadas por conveniência da UI.

## 11. Ordem de Entrega

### Onda 0. Bootstrap do produto

Objetivo:
Transformar o `apps/web` de shell autenticada em shell do Livestock.

Entregar:

- home do Livestock;
- modelo de navegação;
- layout base e utilitários compartilhados de busca de dados;
- integração com API protegida no fluxo de autenticação atual.

### Onda 1. Jornada de leitura do animal

Objetivo:
Permitir que o operador encontre e entenda um animal antes de liberar novas escritas.

Entregar:

- busca de animal;
- detalhe do animal;
- leitura da timeline;
- estados de vazio/carregamento/erro.

### Onda 2. Jornada de escrita de tratamento

Objetivo:
Tornar utilizável no produto o primeiro fluxo operacional de escrita.

Entregar:

- formulário de registro de tratamento;
- fluxo de sucesso/falha;
- retorno pós-escrita para detalhe/timeline do animal.

### Onda 3. Elegibilidade e análise de mercado

Objetivo:
Expor na UI o valor central do modelo de decisão do Titan.

Entregar:

- tela de elegibilidade do animal;
- matriz de mercado;
- explicação comercial;
- seleção de sujeito dependente quando suportada.

### Onda 4. Operação comercial por lote

Objetivo:
Levar o produto da análise individual do animal para o planejamento operacional em grupo.

Entregar:

- detalhe do lote;
- análise de mercado do lote;
- explicação comercial do lote.

### Onda 5. Revisão humana e dossiê

Objetivo:
Expor o caminho oficial governado quando a automação não puder concluir sozinha.

Entregar:

- detalhe da proposta;
- execução da revisão;
- detalhe da decisão;
- acesso ao dossiê.

## 12. Pacote de Validação Manual

Toda onda que alterar comportamento observável do produto deve manter uma trilha executável de validação.

Expectativa mínima por onda:

- um ou mais scripts em `apps/validacao` continuam autoritativos para o comportamento de backend;
- o checklist manual do frontend referencia esses scripts, não memória ad hoc de endpoint;
- a validação do produto sempre verifica tanto o fluxo visual quanto o resultado de backend.

Pareamento recomendado de validação:

- Onda 1: scripts de leitura existentes + walkthrough no navegador;
- Onda 2: script de registro de tratamento + walkthrough na UI;
- Onda 3: `mercados_orientados`, `matriz_elegibilidade_mercados`, `explicacao_comercial`;
- Onda 4: `mercados_orientados_lote`;
- Onda 5: scripts de revisão e dossiê já existentes para governança de decisão.

## 13. Primeiro Incremento Recomendado

O primeiro incremento de implementação deve ser:

`LIV-PROD-01 — shell web do Livestock + jornada de leitura do animal`

Escopo:

- adaptar o `apps/web` para virar uma shell do Livestock;
- criar a home do Livestock;
- criar busca de animal;
- criar detalhe do animal;
- expor leitura da timeline;
- ainda não incluir escrita de tratamento nem mutação de revisão humana.

Por que este é o ponto mínimo e seguro de partida:

- reaproveita a fundação de frontend que já existe;
- evita começar por um fluxo de escrita antes que o modelo de leitura esteja estável;
- expõe valor de produto imediatamente;
- exercita autenticação, autorização, contexto de organização e integração com API sem reabrir semântica de domínio.

## 14. Declaração Executiva de Fechamento

O backend do Livestock já não está esperando descoberta arquitetural central.

O próximo movimento correto é execução de produto:

- fechar a higiene operacional restante para release;
- construir o frontend voltado ao operador do Livestock sobre os contratos aprovados;
- entregar valor em ondas estreitas, começando pelas jornadas de leitura e avançando para escrita e fluxos de governança.

Este pacote é a baseline dessa transição.
