# Plano de Negócio: Titan Livestock

**Versão:** 2.0
**Data:** 21 de julho de 2026
**Tipo:** Documento de execução interna — não é material de captação
**Substitui:** v1.0 (20/07/2026). Os defeitos da v1.0 estão catalogados em `ANALISE_CRITICA.md`.

> Este documento é subordinado a `DOMAIN.md` e `ARCHITECTURE.md`. Onde ele contradisser
> qualquer um dos dois, ele está errado. Nenhuma afirmação comercial aqui pode exigir
> comportamento que o modelo de domínio proíba.

> Regra de honestidade: todo número tem fonte citada ou é marcado `[SUPOSIÇÃO]`.
> Nenhum número sem uma dessas duas marcas deve permanecer neste documento.

---

# 0. Decisões vinculantes que moldam este plano

Registradas em 21/07/2026. Alterá-las exige revisão completa deste documento.

| # | Decisão | Consequência assumida |
|---|---|---|
| D1 | **Core-first completo.** As 25 ADRs, `DOMAIN.md` e `ARCHITECTURE.md` permanecem íntegros. Livestock só depois do Core provado. | Primeiro produto vendável em ~30-42 meses. Ver §5. |
| D2 | **GTM invertido.** Vender ao frigorífico/trader primeiro. O comprador impõe o cadastro à cadeia dele. | Sem tese de viralidade entre produtores. |
| D3 | **Fundador solo, capital próprio mínimo.** Sem contratações até haver receita recorrente. | Velocidade limitada por uma pessoa. Sobrevivência precisa de receita não-software. |
| D4 | **Documento de execução, não de captação.** | Números conservadores. Sem valuation aspiracional. |

## 0.1 A tensão central, declarada

D1 + D3 é a combinação mais difícil possível: **o escopo mais largo com o menor recurso.**

Não vou esconder isso atrás de otimismo. O plano inteiro abaixo existe para responder uma
única pergunta: *como sobreviver 30-42 meses sem produto vendável, sem queimar capital que
você não tem, e descobrindo cedo se a hipótese comercial é falsa.*

A resposta tem três partes:

1. **Desacoplar as duas linhas do tempo.** A validação comercial termina no mês 9. A
   construção termina no mês 30-42. Se a comercial falhar, você para no mês 9 tendo perdido
   9 meses, não 3 anos.
2. **Receita de serviço antes de receita de software.** Diagnósticos pagos financiam a
   construção e validam a dor.
3. **Capital não-diluitivo.** Fomento público brasileiro para agtech/rastreabilidade, que
   é compatível com "capital próprio mínimo" de um jeito que venture capital não é.

**Gate G4 (mês 12) é o ponto onde D1 é reavaliada.** Se não houver financiamento cobrindo
18 meses, Core-first completo não é financiável e o escopo terá que ser cortado. Isso não é
uma opinião sobre a decisão — é uma condição aritmética.

---

# 1. O que mudou desde a v1.0

A v1.0 foi escrita sobre um diagnóstico de mercado que os dados não sustentam. Correções:

### 1.1 Não existe crise de embargo. O mercado está em recorde.

A v1.0 alegava "Embargo da UE em carne brasileira (2024): $2B+ perdidos".

O Brasil fechou **2025 com US$ 18,03 bilhões** em exportações de carne bovina, volume de
3,50 milhões de toneladas — **alta de 40,1% em receita** e 20,9% em volume, o maior
desempenho da história. A China responde por 48% do volume.

**Implicação comercial direta:** você não pode entrar em um frigorífico dizendo "vocês
estão perdendo dinheiro". Eles estão tendo o melhor ano de que se tem registro. O pitch de
crise queima credibilidade no primeiro minuto.

O pitch correto é **prazo regulatório com data marcada**, não crise. Ver §2.

### 1.2 O vento regulatório é real, datado, e favorece um cronograma longo

Duas obrigações com datas firmes:

**EUDR (União Europeia).** Cobre gado bovino entre sete commodities. Exige o histórico
ambiental de cada propriedade de origem — **incluindo fornecedores indiretos**. Entre os
produtos cobertos, a carne bovina combina o maior volume de exportação com a maior
complexidade estrutural de adequação.

> ⚠️ **`[VERIFICAR ANTES DE USAR COMERCIALMENTE]`** — as fontes consultadas divergem sobre
> as datas de aplicação. Uma indica vigência desde 30/12/2025 para grandes operadores e
> 30/06/2026 para PMEs; outra indica adiamento para 30/12/2026 (médias e grandes) e
> 30/06/2027 (micro e pequenas). A regra sofreu ao menos um adiamento e pode ter sofrido
> outro. **Confirme a data vigente na fonte primária (EUR-Lex / Comissão Europeia) antes de
> citá-la em qualquer proposta.** Citar prazo errado a um diretor de compliance destrói
> credibilidade instantaneamente.

**PNIB (Brasil).** O Plano Nacional de Identificação Individual de Bovinos e Búfalos, lançado
em 17/12/2024, torna a identificação individual obrigatória para todo o rebanho até 2032:

- 2024-2026: construção da base de dados nacional
- 2026: integração dos órgãos estaduais de sanidade
- **2027-2029: obrigatória para animais em manejo sanitário ou em protocolos privados homologados pelo MAPA**
- 2030-2032: ampliação para todo o rebanho
- **A partir de 01/01/2033: proibida a movimentação de bovinos não identificados**

**Isto é a melhor notícia deste plano.** Um Core completo entregue em 2029-2030 não chega
atrasado — chega exatamente quando as Etapas 3 e 4 do PNIB estão vinculando o rebanho
nacional inteiro. Pela primeira vez, o cronograma longo de D1 tem uma justificativa
estratégica em vez de ser apenas um custo.

**Mas:** o MAPA está construindo a base de dados nacional. **O Titan não é o sistema de
registro.** Ele opera *sobre* o PNIB/SISBOV. Qualquer plano que posicione o Titan como
cadastro central compete com o governo e perde. Ver §3.

### 1.3 A concorrência é densa, madura e inclui o governo

A v1.0 citava apenas Trace e Provenance — players internacionais irrelevantes para este
mercado. O cenário real brasileiro:

| Player | Posição |
|---|---|
| **Agrotools** | 18 anos de mercado, inventou o conceito de rastreabilidade de território agrícola no Brasil, já entrega avaliação de risco EUDR para centenas de empresas |
| **Niceplanet** | Rastreabilidade e conformidade socioambiental, cobre TACs do MPF e EUDR |
| **Safe Trace** | Rastreabilidade de cadeia alimentar completa, do produtor ao consumidor |
| **SurTrace** | Converte NF-e em evidência auditável para EUDR/ANVISA/ESG. **Carne em desenvolvimento** |
| **AgriTrace (CNA)** | Plataforma da Confederação da Agricultura, abrangência nacional |
| **AgroBrasil+Sustentável** | **Plataforma do próprio MAPA**, aposta do governo para atender a lei antidesmatamento da UE |
| **JBS / Marfrig** | Plataformas proprietárias (Transparência Pecuária, Verde+) |

O risco 8.5 da v1.0 — *"frigorífico sabe fazer frigorífico, não software"* — está factualmente
errado. Os dois maiores compradores do mercado já construíram as próprias plataformas. E
existe uma opção gratuita do governo.

**Consequência:** "rastreabilidade" como categoria está ocupada. Entrar por ali é suicídio.
A entrada tem que ser por uma lacuna específica que os ocupantes não cobrem. Ver §2.

---

# 2. A tese, reescrita

## 2.1 O que o Titan NÃO é

- Não é sistema de registro de animais. Isso é PNIB/SISBOV.
- Não é plataforma de análise geoespacial de risco. Isso é Agrotools/Niceplanet, com 18 anos de vantagem.
- Não é "rastreabilidade". A palavra está queimada e ocupada.
- **Não vende "fraude impossível".** `DOMAIN.md` §2.2 é explícito: integridade não significa verdade. Hash-chain prova que o dado não foi alterado depois de inserido; não prova que era verdadeiro na inserção. Vender o contrário é falso, é derrubável na primeira reunião técnica, e cria exposição jurídica.

## 2.2 O que o Titan é

**Uma camada de evidência auditável sobre cadeias de fornecimento reguladas, especializada
no problema que ninguém resolve bem: o fornecedor indireto.**

Três capacidades, todas já formalizadas no `DOMAIN.md`:

**(a) Genealogia de fornecedor indireto.** `UniversalRelation` + `Genealogy` + `Transformation`
respondem "de onde veio, por onde passou, com que evidência, com que lacunas". A EUDR exige
o histórico ambiental incluindo fornecedores indiretos — a fazenda que vendeu para a fazenda
que vendeu para o frigorífico. É o problema estrutural mais difícil da adequação da carne
bovina, e é exatamente o que a seção 9 do `DOMAIN.md` foi construída para modelar.

**(b) Lacuna declarada em vez de lacuna escondida.** `ProvenancePath` registra explicitamente
links ausentes, ciclos, objetos inacessíveis e completude. Todo concorrente entrega um
semáforo verde/vermelho. O Titan entrega verde/vermelho **mais o mapa exato do que não se
sabe**. Para um diretor de compliance que assina declaração de due diligence sob
responsabilidade pessoal, saber onde está o buraco vale mais que um verde otimista.

**(c) Dossiê verificável por terceiro, sem depender do Titan.** `Dossier` + `VerificationBundle`
+ verificação externa (ADR-0010). O auditor, o comprador europeu ou a autoridade competente
validam o dossiê offline, sem conta, sem API, sem confiar em você. Isso reduz auditoria de
semanas para horas e é o único argumento de ROI defensável tecnicamente.

## 2.3 Posicionamento em uma frase

> Para o exportador que assina declaração de due diligence EUDR sob responsabilidade
> pessoal: o Titan reconstrói a cadeia de fornecedores diretos e indiretos, declara
> explicitamente o que não pôde ser comprovado, e emite um dossiê que o auditor verifica
> sozinho.

## 2.4 Relação com os incumbentes: complementar, não frontal

Agrotools e Niceplanet fazem análise geoespacial e de risco muito bem. Nenhum deles tem
— nem tem incentivo para construir — o rigor de proveniência, admissibilidade de evidência,
fundamentação normativa temporal e correção sem reescrita de histórico que está no
`DOMAIN.md`.

Isso abre duas rotas que devem ser testadas em paralelo na fase comercial:

- **Rota direta:** vender ao exportador como camada de evidência sobre os dados que ele já tem.
- **Rota de parceria/OEM:** ser a camada de evidência *dentro* da oferta de um incumbente. Menor receita por contrato, ciclo de venda muito menor, e resolve o problema de distribuição de um fundador solo sem rede no setor.

A rota de parceria é subestimada e pode ser a saída mais realista dado D3.

---

# 3. Fronteiras que o domínio impõe ao comercial

A v1.0 vendia coisas que o próprio Titan proíbe. Correção permanente:

| Não prometer | Porque o domínio proíbe | O que prometer |
|---|---|---|
| "Fraude impossível" | `DOMAIN.md` §2.2 — integridade ≠ verdade | "Alteração posterior detectável; origem, autoria e sequência confirmáveis" |
| "Frigorífico busca qualquer animal e vê histórico completo" | Isolamento por Organization. Acesso cruzado exige `SharingRequest → GrantAssessment → AuthorizationGrant` com escopo e finalidade | "Acesso ao que cada fornecedor concedeu explicitamente, com escopo e finalidade registrados" |
| "Elegível para abate: SIM/NÃO, regras simples" | `NormativeBasis` exige interpretação versionada, `approved_by`, capacidade declarada e Evidence de competência | "Avaliação fundamentada em interpretação normativa aprovada e versionada — inclui resultado `INDETERMINADA`" |
| "Auditoria automática em 5 minutos" | `Evaluation` pode retornar `INDETERMINADA`; admissibilidade de evidência é decisão de Policy | "Dossiê emitido em minutos; casos indeterminados sinalizados para revisão humana" |
| "Recall em minutos" | `Recall` depende de completude de genealogia, que pode ter lacunas declaradas | "Reconstrução da genealogia conhecida em minutos, com as lacunas explicitadas" |

**`INDETERMINADA` como resultado de primeira classe é argumento de venda, não defeito.**
Concorrente que sempre devolve verde/vermelho está mentindo em algum percentual dos casos,
e o diretor de compliance que assina sabe disso.

---

# 4. Go-to-market invertido, sob restrição de "sem produto por 30 meses"

O problema óbvio de D2 + D1: como vender primeiro ao frigorífico se o software só existe
em 2029?

**Você não vende software. Vende, em três estágios, o que já tem: conhecimento do domínio.**

## Estágio 1 — Diagnóstico pago (meses 1-9)

**Oferta:** mapeamento da exposição EUDR da cadeia de fornecimento, com foco em fornecedor
indireto. Entregável: relatório de lacunas de rastreabilidade, inventário de fornecedores
indiretos não cobertos, e desenho do dossiê de conformidade que a empresa precisará emitir.

**Preço:** R$ 25.000 a R$ 80.000 por engajamento `[SUPOSIÇÃO — validar nas 3 primeiras propostas]`

**Por que funciona:**
- Gera caixa desde o mês 3-4, sem produto
- É a validação mais barata que existe: se ninguém paga pelo diagnóstico, ninguém pagará pelo software
- Produz o dado real da dor, que alimenta o `NormativeBasis` e as Policies do Livestock
- Cria a relação que vira design partner
- O prazo EUDR de 30/12/2026 cria urgência genuína, hoje

**Meta:** 2-4 engajamentos no ano 1.

## Estágio 2 — Design partner (meses 9-24)

**Oferta:** co-desenvolvimento. O cliente paga uma mensalidade de parceria em troca de
influência sobre o roadmap, prioridade de implantação e condição comercial preferencial no
contrato futuro.

**Preço:** R$ 8.000 a R$ 20.000/mês `[SUPOSIÇÃO]`

**Contrapartida dele:** acesso a dados reais (anonimizados quando necessário), acesso aos
fornecedores dele para teste, e uma LOI para licença futura.

**Meta:** 1 design partner até o mês 18.

## Estágio 3 — Licença (mês 30+)

**Preço-alvo:** R$ 10.000 a R$ 35.000/mês por exportador, com variação por volume de
fornecedores na cadeia. `[SUPOSIÇÃO — validar]`

**Comparação com a v1.0:** ela pedia US$ 50k/mês ≈ R$ 270k/mês, ticket de ERP tier-1, de
um comprador com margem líquida de 1-3%. A faixa acima é 8-25× menor e ainda é um contrato
respeitável.

**Modelo alternativo a testar:** preço por cabeça processada ou por fornecedor auditado.
Alinha custo a valor e reduz a barreira de assinatura inicial.

## 4.1 Perfil do primeiro cliente

Não frigorífico pequeno, como dizia a v1.0. **Exportador de médio porte com destino UE e
cadeia de fornecimento indireta relevante.** Critérios:

- Exporta para UE (exposição EUDR direta e datada)
- Grande o bastante para ter um diretor de compliance dedicado
- Pequeno o bastante para não ter construído plataforma própria (exclui JBS, Marfrig, Minerva)
- Com histórico de TAC do MPF ou pressão socioambiental — a dor já é consciente

Também considerar: **traders e importadores europeus**, que carregam a responsabilidade
legal da declaração EUDR e têm capacidade de pagar substancialmente maior que o frigorífico
brasileiro.

---

# 5. Cronograma realista

## 5.1 Estimativa de esforço do Core completo

`DOMAIN.md` formaliza ~250 conceitos. `DEVELOPMENT.md` impõe: uma capacidade por passo,
<300 linhas por passo, portão de validação manual entre passos, Ruff + Mypy + testes a cada
passo.

Agrupando conceitos em capacidades entregáveis: **~120-180 passos** para o Core.
A 1,5-2,5 dias úteis por passo (domínio + aplicação + infra + migration + testes + revisão):

| Cenário | Dedicação | Core completo | + Vertical Livestock | Primeiro produto vendável |
|---|---|---|---|---|
| Otimista | Integral, sem serviço | 20 meses | +5 meses | **~mês 25** |
| Base `[SUPOSIÇÃO]` | ~70% dev, 30% comercial | 30 meses | +6 meses | **~mês 36** |
| Pessimista | 50% dev (serviço pesado) | 42 meses | +8 meses | **~mês 50** |

**O cenário base é o de planejamento: primeiro produto vendável por volta de meados de 2029.**

Isso coincide com a Etapa 3 do PNIB (2027-2029) e está depois do início da EUDR. Chega tarde
para a primeira onda EUDR e no tempo certo para a obrigatoriedade nacional. É um trade-off
real, e é consequência direta de D1.

## 5.2 O custo explícito de D1

Se o escopo fosse cortado para um Core mínimo (8-12 conceitos: Organization, Subject, Event,
Evidence, Signature, Genealogy, Policy/Rule, Evaluation, Dossier), o primeiro produto vendável
sairia em **4-6 meses**, dentro da janela EUDR de 2026-2027.

**A diferença entre as duas escolhas é de aproximadamente 24-30 meses de receita.**

Você optou por D1. Este plano executa D1. Mas o número acima precisa estar escrito, e
**G4 (mês 12) é o momento formal de reavaliá-lo** com informação real em mãos.

## 5.3 Marcos

| Marco | Mês | Conteúdo |
|---|---|---|
| M0 | 0-1 | Este plano aprovado. Passo 0.4 liberado. Lista de 40 alvos comerciais montada. |
| M1 | 1-3 | Passos 0.4-1.x. Fundação técnica. 20 conversas comerciais. |
| M2 | 3-6 | Core: Identity + Organization + Event. 1º diagnóstico pago assinado. |
| M3 | 6-9 | Core: Evidence + Provenance. 2º diagnóstico. Negociação de design partner. |
| M4 | 9-12 | Core: Sharing/Grants + Audit. Fomento submetido. **G4.** |
| M5 | 12-18 | Core: Policies/Rules/Evaluations/Decisions. Design partner assinado. |
| M6 | 18-24 | Core: Normative + Correction + Recall. Homologação PNIB iniciada. |
| M7 | 24-30 | Core: Documents/Integrity/Keys/Verification externa. Core completo. |
| M8 | 30-36 | Vertical Livestock. Piloto em produção com o design partner. |
| M9 | 36+ | Primeiros contratos de licença. |

**Objetivo estratégico transversal:** obter homologação do Titan como **protocolo privado
homologado pelo MAPA** dentro do PNIB. A Etapa 3 (2027-2029) menciona explicitamente
"protocolos privados homologados pelo Mapa" como caminho de identificação obrigatória. Ser
homologado transforma o Titan de fornecedor opcional em trilho regulatório. É o fosso mais
valioso disponível e deve ser perseguido a partir do mês 18.

---

# 6. Gates de kill/continue

Esta é a seção mais importante do documento. Ela existe para que uma hipótese falsa custe
9 meses em vez de 3 anos.

| Gate | Mês | Critério de continuidade | Se falhar |
|---|---|---|---|
| **G1** | 3 | 20 conversas com exportadores/traders realizadas. ≥5 confirmam fornecedor indireto entre as 3 maiores dores de compliance. | A tese de produto está errada. Refazer §2 antes de escrever mais código. |
| **G2** | 6 | ≥1 diagnóstico pago assinado (≥R$25k). | Ninguém paga pelo seu conhecimento do domínio. É evidência forte de que não pagarão pelo software. Parar e reavaliar o mercado inteiro. |
| **G3** | 9 | ≥1 LOI ou term sheet de design partner, mesmo condicionado a entrega futura. | O comprador não se compromete com prazo longo. **Core-first completo perde a justificativa comercial.** Cortar escopo. |
| **G4** | 12 | Financiamento (fomento, design partner ou receita de serviço) cobrindo ≥18 meses de custo. | **D1 não é financiável.** Decisão forçada: cortar para Core mínimo, ou captar capital diluitivo, ou encerrar. |
| **G5** | 18 | ≥40% dos módulos do Core entregues com testes verdes e arquitetura preservada. | Estimativa de velocidade era otimista em >50%. Recalcular tudo e reaplicar G4. |
| **G6** | 30 | Core completo. Design partner ativo. | Reavaliar antes de investir na vertical. |

**Regra:** um gate falhado não é uma decepção a ser racionalizada. É informação cara que
você comprou. Ignorar um gate falhado anula o propósito de tê-lo escrito.

---

# 7. Modelo financeiro

Valores em R$. Todos os itens de receita são `[SUPOSIÇÃO]` até o primeiro contrato assinado.

## 7.1 Custo operacional (fora custo de vida)

| Item | Mensal | Anual |
|---|---|---|
| Infraestrutura de desenvolvimento (PostgreSQL, MongoDB, Valkey, ambientes) | R$ 400 - 1.200 | R$ 5k - 14k |
| Ferramentas, domínio, certificados, CI | R$ 300 - 600 | R$ 4k - 7k |
| Viagens comerciais (4-8 por ano) | — | R$ 12k - 30k |
| Contabilidade, jurídico societário | R$ 500 - 1.200 | R$ 6k - 15k |
| Reserva jurídica (revisão de contrato, `NormativeBasis` por profissional habilitado) | — | R$ 15k - 40k |
| **Total operacional** | | **R$ 42k - 106k/ano** |

Não incluído: seu custo de vida. Ele domina o modelo e só você tem o número.
**Preencha:** custo de vida mensal = R$ ______. Runway atual em meses = ______.

Custos que aparecem depois e que a v1.0 omitia inteiramente: certificação ICP-Brasil,
auditoria de segurança, seguro de responsabilidade civil profissional, implantação e
integração por cliente. Nenhum antes do mês 24, mas todos reais.

## 7.2 Receita projetada

| Ano | Período | Fonte | Faixa |
|---|---|---|---|
| Y1 | 2026-07 → 2027-06 | 2-3 diagnósticos | R$ 50k - 200k |
| Y2 | 2027-07 → 2028-06 | 3-4 diagnósticos + design partner parcial | R$ 150k - 400k |
| Y3 | 2028-07 → 2029-06 | Design partner pleno + 1º piloto | R$ 250k - 600k |
| Y4 | 2029-07 → 2030-06 | 3-6 licenças | R$ 600k - 1,8M |
| Y5 | 2030-07 → 2031-06 | 8-15 licenças | R$ 1,5M - 4,5M |

**Margem bruta realista: 60-70%**, não os 95% da v1.0. Uma plataforma de conformidade
regulada carrega implantação, suporte, revisão jurídica contínua e auditoria.

**Comparação com a v1.0:** ela projetava US$ 20M (≈R$ 108M) de receita no ano 3. Este plano
projeta R$ 250k-600k no mesmo período — cerca de **200 vezes menos**. A v1.0 não estava
otimista; estava aritmeticamente quebrada (suas próprias linhas de "média mensal" contradiziam
seus totais por fatores de 7× e 17×).

## 7.3 Capital não-diluitivo — prioridade alta

Compatível com D3 de um jeito que venture capital não é. A verificar e submeter até o mês 9:

- **FINEP** — programas de subvenção e crédito para inovação
- **EMBRAPII** — cofinanciamento de PD&I com unidades credenciadas
- **BNDES** — linhas para inovação e para rastreabilidade agropecuária
- **FAPs estaduais** (FAPESP PIPE e equivalentes, conforme seu estado)
- **CNPq / editais MAPA** ligados ao PNIB

`[A VERIFICAR]` — nomes, editais vigentes, prazos e elegibilidade precisam ser confirmados
antes de qualquer planejamento sobre eles. Não trate nenhum como receita até haver carta
de aprovação.

Um único aporte de R$ 200k-500k não-diluitivo muda a viabilidade de D1 de improvável para
plausível. **Esta é provavelmente a atividade de maior retorno por hora disponível no ano 1.**

---

# 8. Riscos

Reescritos. Os da v1.0 eram otimistas demais e um deles era factualmente falso.

## R1 — Runway acaba antes do Core (probabilidade: ALTA)

O risco dominante. 30-42 meses sem produto, solo, capital mínimo.

**Mitigação:** receita de serviço desde o mês 3; fomento não-diluitivo até o mês 12; G4 como
ponto de decisão forçada. **Aceitar que serviço reduz velocidade de desenvolvimento — e
escolher a alocação conscientemente em vez de deixar acontecer.**

## R2 — O mercado consolida antes de você entregar (probabilidade: ALTA)

Agrotools tem 18 anos e centenas de clientes EUDR. SurTrace já tem carne em desenvolvimento.
O MAPA lançou plataforma gratuita. A janela EUDR de 2026-2027 será disputada e vencida por
outros enquanto o Core é construído.

**Mitigação:** não disputar essa janela. Mirar a obrigatoriedade PNIB de 2029-2032. Buscar
homologação MAPA. Considerar seriamente a rota de parceria/OEM (§2.4), que transforma
concorrente em canal.

## R3 — Plataforma gratuita do governo elimina o mercado (probabilidade: MÉDIA)

O AgroBrasil+Sustentável pode absorver a demanda básica de conformidade.

**Mitigação:** posicionar acima do mínimo regulatório — evidência auditável por terceiro,
fornecedor indireto, lacunas declaradas. Plataforma de governo tende a atender o requisito
mínimo, não a responsabilidade pessoal de quem assina a declaração. Monitorar de perto: se
ela cobrir fornecedor indireto com rigor, a tese precisa mudar.

## R4 — O diferencial não é percebido como valor (probabilidade: MÉDIA-ALTA)

Rigor de proveniência, admissibilidade e `INDETERMINADA` são superiores tecnicamente. O
comprador pode simplesmente preferir o verde/vermelho simples e barato.

**Mitigação:** este é exatamente o que G1 e G2 testam. Se 20 conversas e um diagnóstico pago
não confirmarem, o diferencial é engenharia sem mercado — e é melhor descobrir no mês 6.

## R5 — Fundador solo não fecha venda enterprise (probabilidade: MÉDIA)

Venda a diretoria de exportador exige rede, referência e presença. D3 diz sem sócio comercial.

**Mitigação:** diagnóstico pago é venda consultiva, muito mais acessível a um técnico
credível do que venda de licença. Rota de parceria/OEM contorna a distribuição. Reavaliar
D3 em G3.

## R6 — Complexidade do domínio derrota um desenvolvedor solo (probabilidade: MÉDIA)

250 conceitos, invariantes rigorosas, testes arquiteturais, protocolo de portões manuais.
Módulos como disposição de dados, forense de incidente e sustentabilidade são projetos
inteiros isoladamente.

**Mitigação:** G5 mede velocidade real contra a estimativa no mês 18, cedo o bastante para
corrigir. Ordenar os módulos por proximidade ao dossiê de fornecedor indireto — se o
runway acabar no mês 24, que o que existir seja a parte vendável.

## R7 — Responsabilidade civil por decisão errada (probabilidade: BAIXA, impacto ALTO)

O Titan emite dossiê que sustenta declaração regulatória. Dossiê errado → exposição.

**Mitigação:** o `DOMAIN.md` já protege (não presume verdade, `INDETERMINADA`, lacunas
declaradas). O material comercial precisa refletir isso — ver §3. Contrato com limitação de
responsabilidade e seguro E&O antes do primeiro cliente de produção.

---

# 9. Os próximos 90 dias

Nesta ordem. Nada abaixo depende de escrever mais documentação.

**Semanas 1-2**
- [ ] Aprovar este plano; arquivar a v1.0
- [ ] Corrigir "CVM" → "MAPA / órgãos estaduais / IBAMA" em todo o material (a CVM regula mercado de capitais, não pecuária — o erro aparecia 4× na v1.0)
- [ ] Preencher custo de vida e runway em §7.1. Sem esse número, o plano não é executável
- [ ] Liberar o Passo 0.4 do plano de implementação

**Semanas 3-6**
- [ ] Montar lista de 40 alvos: exportadores médios com destino UE + traders europeus
- [ ] Escrever o diagnóstico de uma página (dor → entregável → preço)
- [ ] Iniciar as 20 conversas de G1
- [ ] Levantar editais de fomento vigentes e prazos

**Semanas 7-12**
- [ ] Concluir as 20 conversas. **Avaliar G1**
- [ ] Enviar 3-5 propostas de diagnóstico
- [ ] Passos 1.x do Core em paralelo
- [ ] Preparar submissão de fomento

**Não fazer nos próximos 90 dias:** expandir `DOMAIN.md`, escrever nova ADR sem que um passo
de implementação a exija, ou produzir material de captação.

---

# 10. A pergunta que este plano existe para responder

Foram produzidas ~5.000 linhas de especificação, 25 ADRs e zero linhas de código, sem uma
conversa registrada com um comprador.

A qualidade do `DOMAIN.md` é real — a separação entre integridade, verdade, confiança,
freshness e admissibilidade é onde todos os concorrentes erram, e é ativo defensável.

Mas nenhuma dessas 5.000 linhas responde se um exportador assina. Documentação é confortável:
progresso visível, sem risco de rejeição. Ligar para um diretor de compliance e ouvir "não"
é desconfortável, e é a única atividade que gera informação real sobre a viabilidade deste
negócio.

**G2 é o gate que importa.** Se até o mês 6 ninguém pagar R$25.000 pelo seu conhecimento
deste domínio, a probabilidade de alguém pagar R$300.000/ano pelo software é baixa — e é
muito melhor saber disso no mês 6 do que no mês 36.

---

# Fontes

- [Brasil bate recorde e exporta US$ 18,3 bilhões em carne bovina em 2025 — CNN Brasil](https://www.cnnbrasil.com.br/agro/brasil-bate-recorde-e-exporta-us-183-bilhoes-em-carne-bovina-em-2025/)
- [Brasil bate recorde nas exportações de carne bovina em 2025 — ABIEC](https://abiec.com.br/brasil-bate-recorde-nas-exportacoes-de-carne-bovina-em-2025/)
- [Brasil Encerra 2025 com Maior Exportação de Carne Bovina da História — Forbes Agro](https://forbes.com.br/forbes-agro/2026/01/brasil-encerra-2025-com-maior-exportacao-de-carne-bovina-da-historia-diz-abiec/)
- [EUDR: Tudo que você precisa saber — Serasa Experian](https://www.serasaexperian.com.br/conteudos/eudr-tudo-que-voce-precisa-saber-sobre-a-nova-lei-da-uniao-europeia-para-produtos-livres-de-desmatamento/)
- [EUDR: quais são as mudanças no setor de commodities agrícolas? — Geoambiente](https://geoambiente.com.br/blog/eudr/)
- [Documento orienta produtores brasileiros no cumprimento de regulação europeia sobre desmatamento — FGV](https://portal.fgv.br/noticias/documento-orienta-produtores-brasileiros-no-cumprimento-de-regulacao-europeia-sobre)
- [Plano nacional trará rastreabilidade individual de bovinos e bubalinos até 2032 — SEAPI/RS](https://www.agricultura.rs.gov.br/plano-nacional-trara-rastreabilidade-individual-de-bovinos-e-bubalinos-a-rebanho-brasileiro-ate-2032)
- [Rastreabilidade total até 2032 — Mesa Brasileira da Pecuária Sustentável](https://pecuariasustentavel.org.br/noticias/rastreabilidade-total-ate-2032-o-horizonte-da-pecuaria-brasileira-e-o-papel-estrategico-da-rastreabilidade-individual/)
- [Governo lança plano de rastreio individual na pecuária — ((o))eco](https://oeco.org.br/reportagens/governo-lanca-plano-de-rastreio-individual-na-pecuaria-com-foco-apenas-sanitario/)
- [Rastreabilidade e Identificação Individual de Bovinos e Búfalos — MAPA (PDF)](https://www.gov.br/agricultura/pt-br/assuntos/camaras-setoriais-tematicas/documentos/camaras-setoriais/carne-bovina/2025/72a-ro-18-03-2025/apresentacao-rastreabilidade.pdf)
- [Agrotools — EUDR: Soluções pioneiras](https://agrotools.com.br/blog/esg-sustentabilidade/eudr-solucoes-pioneiras-para-uma-nova-oportunidade/)
- [Niceplanet — Rastreabilidade e Conformidade](https://niceplanet.com.br/en)
- [Safe Trace / Agrotransparência](https://www.agrotransparencia.com.br/)
- [SurTrace](https://surtrace.com.br/)
- [AgriTrace — Programa Rastreabilidade Animal, CNA](https://www.cnabrasil.org.br/projetos-e-programas/programa-rastreabilidade-animal)

---

**Documento criado:** 21/07/2026
**Próxima revisão obrigatória:** G4 (mês 12) ou qualquer gate falhado
**Próximo passo:** preencher custo de vida e runway em §7.1
