# Plano de Conclusão do Domínio Livestock — Marcos 13 a 16

**Data:** 25 de julho de 2026
**Estado:** PROPOSTO — aguarda aprovação antes de qualquer código
**Relação com o plano anterior:** o `PLANO_DE_IMPLEMENTACAO_VALIDADO.md` encerrou-se no Marco 10 e declara que expansões exigem decomposição própria. Este documento é essa decomposição.

---

## 1. Por que estes marcos, e não outros

O levantamento encontrou duas lacunas que não são funcionalidades faltando — são o modelo incompleto:

**O animal não tem fim de vida.** Não existe morte, abate, venda nem saída, e `Animal` não possui campo de estado. Todo animal cadastrado permanece implicitamente vivo e presente. Um recall varre animais mortos há anos; a carência é calculada para bois que já saíram; toda listagem construída no Marco 12 já nasce enviesada. O rebanho só cresce.

**A genealogia do Core está construída e a vertical nunca a usou.** O Passo 7.1 entregou relação universal e temporal, e a vertical não possui uma única relação. O animal registra onde nasceu, não de quem. Sem mãe, não há linhagem — e o parto não tem para onde apontar.

Vacinação e pesagem são acréscimos ao modelo. Estas duas são fechamento dele, e por isso vêm primeiro.

---

## 2. Decisões de regra de negócio

O responsável delegou estas decisões, pedindo que fossem tomadas com base em pesquisa. Seguem decididas, com o raciocínio exposto para poderem ser contestadas.

> **Ressalva necessária.** As decisões abaixo apoiam-se em fontes secundárias e em leitura de bulas citadas por fabricantes. Não constituem parecer veterinário nem jurídico. Antes de uso em produção, o responsável técnico veterinário deve confirmar prazos e obrigatoriedades contra as bulas vigentes e a norma aplicável.

### D-1 — Vacina tem carência, e é a mesma máquina

**Decidido: sim, vacina tem período de carência, declarado por produto — e o cálculo é o mesmo do Passo 9.4.**

A pesquisa confirmou prazos reais: a Bovilis RB-51 (brucelose) exige não abater antes de três semanas da aplicação; a Resguard Multi declara 21 dias após a última dose. Os prazos variam por produto e constam da bula, exatamente como nos antiparasitários.

**Consequência de projeto, e é a mais importante deste plano:** uma vacina **é** um `Medication` com `withdrawal_period_days`. Não há cálculo novo, não há entidade nova de carência, não há segunda regra de elegibilidade. O que falta é **classificação** — distinguir imunobiológico de farmacológico — e o vínculo com a campanha oficial, que é o que o PNIB cobra.

Isso torna o Marco 14 muito mais barato do que parecia, e é a razão de ele vir depois do 13 sem prejuízo de prazo.

**Não decidido aqui, e fica para quando houver demanda:** carência de leite, que é prazo distinto do de carne na mesma bula. O modelo atual tem um só prazo por medicamento.

### D-2 — A saída encerra o futuro, não o passado

**Decidido: um animal que saiu do rebanho recusa fatos novos, e aceita o registro tardio de fatos anteriores à saída.**

O critério não é conveniência: é a distinção entre quando o fato ocorreu e quando foi registrado, que o Titan já sustenta desde o Passo 10.1.

- **Aceito:** lançar hoje um tratamento aplicado antes da saída. O fato aconteceu; o registro atrasou. Recusá-lo apagaria história real e é exatamente o que um sistema append-only não faz.
- **Recusado:** qualquer fato cujo `occurred_at` seja posterior à saída — tratamento, movimentação, inclusão em lote. Um boi abatido não é movimentado.
- **Recusado:** uma segunda saída. Sair é terminal.
- **Mantido:** consultar, avaliar elegibilidade e emitir dossiê continuam permitidos depois da saída. É justamente quando a auditoria acontece.

**Consequência para as listagens:** passam a distinguir rebanho ativo de histórico, com o ativo como padrão. Quem lista animais quer o rebanho, não o cemitério.

### D-3 — O pai é opcional, e a paternidade tem confiança declarada

**Decidido: mãe obrigatória, pai opcional, e ambos com nível de confiança explícito.**

A pesquisa mostrou que paternidade indeterminada é caso reconhecido, não exceção a tratar como erro: em monta natural com vários touros, a paternidade só é certa com exame de DNA, e os registros genealógicos admitem inscrição com apenas um ascendente conhecido, desde que comprovado.

Exigir o pai forçaria o operador a inventar dado — que é pior que dado ausente, e contraria o princípio do Titan de que lacuna é pendência, não reprovação.

**Consequência de projeto:** a paternidade reusa o `ConfidenceLevel` do Passo 5.2, com os mesmos níveis que o veterinário já usa:

| Nível | Significado na paternidade |
|---|---|
| `DECLARADO` | Informado pelo produtor, sem comprovação |
| `DOCUMENTADO` | Registro de cobertura ou inseminação |
| `VERIFICADO_EM_FONTE` | Exame de DNA arquivado |

E admite-se o caso do **touro do lote**: vários pais possíveis, nenhum confirmado. Isso se expressa como relações múltiplas de paternidade em `DECLARADO`, e não como um campo de texto — porque a pergunta "quais touros podem ser o pai" precisa ser consultável.

---

## 3. Marcos

### Marco 13 — Ciclo de vida completo do animal

Fecha o modelo. Nenhum passo aqui é opcional.

#### Passo 13.1 — Saída do rebanho — IMPLEMENTADO em 25/07/2026

Detalhamento do que foi entregue e das decisões: `docs/CHECKLIST_DE_IMPLEMENTACAO.md`, Marco 13.

**Entrega:** evento de saída com tipo (`MORTE`, `ABATE`, `VENDA`, `TRANSFERENCIA_DEFINITIVA`), instante, motivo e evidência opcional. Estado do animal **derivado dos eventos**, nunca campo mutável. Guardas conforme D-2. Listagens passam a filtrar por rebanho ativo, com o ativo como padrão.

**Validação manual:** registrar cada tipo de saída; confirmar que fato posterior é recusado e fato anterior lançado com atraso é aceito; confirmar que a listagem padrão deixa de mostrar o animal e a consulta histórica continua mostrando; confirmar que o dossiê ainda é emitido.

#### Passo 13.2 — Genealogia

**Entrega:** relações de maternidade e paternidade usando `RelationService` do Core — a primeira vez que a vertical usa a genealogia do Passo 7.1. Confiança conforme D-3. Consulta de ascendência e descendência.

**Validação manual:** registrar mãe conhecida e pai desconhecido; registrar touro do lote com três pais possíveis; consultar ascendência; confirmar que a confiança viaja na resposta.

#### Passo 13.3 — Nascimento — IMPLEMENTADO em 25/07/2026

Detalhamento e decisões: **ADR-0040** e `docs/CHECKLIST_DE_IMPLEMENTACAO.md`, Marco 13.

**Entrega:** um ato que cria o animal **e** as relações de parentesco na mesma transação. Sem isso, cadastro e genealogia ficam sempre um passo defasados.

**Cresceu em relação ao previsto aqui.** As três perguntas marcadas como portão no Marco 16 — natimorto, aborto e parto múltiplo — tiveram de ser respondidas já, porque o ato de nascimento não existe sem elas. A resposta separou o **evento reprodutivo** do **indivíduo rastreável**: o parto é evento materno que produz zero, uma ou várias crias, cada qual com o seu resultado de nascimento. Natimorto cria indivíduo e **não** recebe registro de saída; aborto não cria indivíduo; gemelar é um evento com várias crias.

**Validação manual:** passos 6.1 a 6.12 do roteiro executável (`python -m apps.validacao`).

---

### Marco 14 — Manejo sanitário

Barato por causa de D-1: reusa medicamento, lote, carência e veterinário.

#### Passo 14.1 — Classificação de imunobiológico

**Entrega:** `Medication` distingue imunobiológico de farmacológico. A carência continua sendo a mesma. Consultas passam a poder responder "quais vacinas este animal recebeu".

#### Passo 14.2 — Campanha de vacinação

**Entrega:** campanha oficial (brucelose, aftosa) com janela de vigência, ligando aplicações ao programa que as exige. É o que o PNIB e o PNCEBT cobram.

**Portão:** confirmar com responsável técnico quais campanhas são obrigatórias e em que faixa etária, antes de codar a regra de exigibilidade.

**Prazo externo:** a Etapa 3 do PNIB inicia em janeiro de 2027 e exige identificação e cadastro de animais submetidos a manejo sanitário.

---

### Marco 15 — Manejo zootécnico

#### Passo 15.1 — Pesagem

**Entrega:** peso em `Decimal` — nunca `float`, que o serializador canônico recusa — com unidade, método e instante. Precisão mínima conforme ICAR: 1 kg ao nascimento, 2 kg depois.

#### Passo 15.2 — Escore de condição corporal

**Entrega:** escore com escala declarada, porque escala varia por região e um número sem escala não significa nada.

#### Passo 15.3 — Derivações zootécnicas

**Entrega:** ganho médio diário e peso ajustado como **cálculo**, jamais como evento — mesma regra da carência no Passo 9.4, e a mesma distinção que o ICAR faz entre traço registrado e traço calculado.

---

### Marco 16 — Reprodução

Depende do 13.2.

**Passos:** cobertura ou inseminação; diagnóstico de gestação; desmame. **O parto saiu daqui** — foi entregue no Passo 13.3, e o que resta ao Marco 16 é a gestação que o antecede.

**Portão resolvido antecipadamente.** As regras de natimorto, aborto e parto múltiplo foram decididas pelo responsável e estão na **ADR-0040**. O que sobra para este marco é ligar `Pregnancy` ao `ReproductiveEvent`, por um `pregnancy_id` opcional que já foi previsto — exigi-lo no 13.3 recusaria o caso majoritário do campo, em que o parto é registrado sem que a cobertura tenha sido.

---

## 4. Explicitamente fora deste plano

Cada um exige decomposição própria:

- **Prescrição obrigatória** (NR-4) — depende de definir em que casos a prescrição deixa de ser opcional.
- **Autoria de regras pelo administrador** (NR-5) — `RuleCondition` já é declarativo e provavelmente resolve a maior parte; a ADR-0036 (Wasm) fica para o que não couber.
- **Abate como transformação em produtos** (NR-2) — é DAG, não árvore, e o caminho é mapear para GS1 EPCIS. O Passo 13.1 registra que o animal **saiu** por abate; o que ele vira é outro marco.
- **Carência de leite**, distinta da de carne.
- **Frontend.**

---

## 5. Nota de rumo comercial e cadeia pós-abate

### Nenhuma receita atrelada ao desfecho da elegibilidade

Hipótese levantada e **recusada**: cobrar do produtor por negociação bem-sucedida. O defeito não é de preço, é estrutural.

**O Titan passaria a ter interesse financeiro no animal ser elegível** — lucraria com o "sim" e não com o "não". É o arranjo das agências de rating pagas pelo emissor, e um auditor identifica isso em uma pergunta: *"recebem se o lote for reprovado?"*. Tudo no sistema foi construído para ser crível; receita que aposta no resultado destrói de fora o que a arquitetura protege por dentro. Não se corrige com política interna — a pergunta é sobre o incentivo, não sobre a intenção.

**E taxaria justamente o evento que o sistema precisa capturar.** A venda é a transferência de custódia, a travessia de fronteira entre organizations — a coisa mais difícil e mais valiosa do modelo. Cobrar ali faz o produtor usar o Titan para a GTA e fechar a venda por fora.

> **Nunca precifique o evento que você precisa que aconteça.**

A regra reaparece no recall. Some-se a fricção de cobrar valores pequenos de milhares de produtores pulverizados, e o fato de que comissão sobre venda de boi já tem dono — o corretor, que ao menos traz o comprador.

**O produtor é oferta, não demanda.** Se houver cobrança um dia, que seja assinatura plana por conveniência, **nunca vinculada ao desfecho da elegibilidade**.

### As três linhas de receita do frigorífico

1. **Homologação de fornecedor**, recorrente por fornecedor ativo. Substitui custo que eles já têm em gente — o mais fácil de vender.
2. **Atestação por lote**, na compra, com a regra de desenho que resolve o conflito: **cobra-se pela resposta, não pelo "sim"** — lote reprovado custa exatamente o mesmo. Isso precisa estar na proposta comercial, não só na prática.
3. **Arquivo e reprodução de auditoria**, recorrente.

**A terceira é o negócio, não um acessório.** A pergunta do auditor não é "está conforme?", é *"o que você sabia no dia em que assinou aquela declaração?"*. O Titan responde porque guarda o texto exato com digest e nunca substitui; quem reconsulta a fonte responde o que o mapa diz hoje, que é a pergunta errada. Consequência: depois de alguns anos de declarações apoiadas em evidência que mora no Titan, **sair significa ficar sem lastro para o que já se assinou**. Precificar retenção barato no começo e jamais descartar dado.

**Recall é capacidade incluída, nunca cobrada por uso.** Cobrar por consulta faz consultarem tarde, e recall tarde arruína a marca deles e, junto, a nossa. Não se precifica a emergência.

### A jusante do abate: identidade vira conjunto

No abate a cadeia deixa de ser linha e vira grafo: animal → carcaça (1:1), carcaça → cortes (1:N), cortes → **caixa (N:M)**, caixa → pallet → contêiner (agregação). A caixa quebra o elo — pode conter carne de vários animais, e moída de centenas.

**Para a EUDR o conjunto basta.** A regulação pergunta se a mercadoria é livre de desmatamento, não qual boi virou qual bife: se todos os animais do conjunto declarado estão limpos, a caixa está limpa. Não é preciso 1:1 — é preciso que o conjunto seja **honesto e fechado**, que é o que a ADR-0042 já faz ao preservar a afirmação com sua incerteza.

**Não inventar o modelo: é a NR-2, e o alvo é GS1 EPCIS** (transformação com entradas e saídas, agregação, GTIN/SSCC/GLN). A divisão fica limpa — **EPCIS diz o que aconteceu; o Titan diz quem afirmou, com base em quê, com que confiança e com qual lacuna**, que é o que falta ao EPCIS. Adotar o padrão entrega compatibilidade, não o ativo.

**Não é preciso negociar com cada elo:** o frigorífico já é cliente e já precisa provar para frente; a atestação viaja como artefato verificável e não como acesso, então quem recebe não precisa ser tenant para consumir a prova; e a pressão vem do fim da cadeia, onde está a responsabilidade legal — **um comprador-farol no fim puxa o formato para trás** com mais alavanca do que vender elo a elo.

**Sequência:** (1) fazenda → porteira, onde estamos, e parar aí de propósito; (2) animal → carcaça dentro do frigorífico, salto único e mais valioso, pegando carona na identificação de carcaça que o SIF já obriga; (3) carcaça → caixa com semântica de conjunto e saída EPCIS; (4) elos seguintes como tenants, se quiserem contribuir.

**Alerta:** a montante — cria → recria → engorda — ainda não está resolvida, e é onde a EUDR morde. Descer para a jusante antes de a montante estar densa deixa as duas finas. **QR code no bife é marketing, não negócio**: encanta em feira e não sustenta receita.

**Não prometer** rastreio do corte até o animal individual — na moída é falso, e promessa falsa em algo verificável derruba a credibilidade da parte que é verdadeira. A afirmação honesta é mais forte: *"a carne desta caixa veio deste conjunto declarado de animais, e todos satisfazem X"*.

Cada elo à frente que cita uma referência do Titan torna o arquivo do frigorífico mais carregado de consequência: **o fosso cresce sozinho a cada elo.**

---

## 6. Protocolo

Vale o mesmo do plano anterior: antes de cada passo, apresentar escopo, arquivos previstos, critérios de aceitação e riscos; ao final, executar o portão completo (`pytest` com `skipped == 0`, `ruff check`, `ruff format --check`, `mypy`, `alembic check`), registrar evidências no checklist e aguardar validação manual.

Decisão arquitetural nova interrompe o passo e vira ADR antes do código.
