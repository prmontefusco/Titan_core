# Prompt de Pesquisa — Base Normativa de Mercados (China, EUA, UE, Indonésia)

**Data:** 2026-09-14
**Propósito:** prompt pronto para uso com Google Gemini (ou pesquisador humano), para levantar as
exigências regulatórias reais e atuais de importação de gado bovino vivo e/ou carne bovina do Brasil para
China, Estados Unidos, União Europeia e Indonésia.
**O que este documento NÃO é:** não é uma `NormativeBasis` do Titan, não autoriza nenhum mercado a sair de
`INDETERMINADO`, e o resultado da pesquisa não deve ser registrado no sistema sem passar pela validação
descrita em `docs/livestock/MARKET_NORMATIVE_BASIS_INTAKE_GUIDE.md`. Ver `docs/adr/0061-selecao-normativa-
temporal-antes-de-market-eligibility.md` para o motivo desse portão existir.

---

## Como usar

Cole o bloco "PROMPT" abaixo inteiro em uma sessão do Google Gemini com acesso a busca/grounding ativado
(este repositório já tem infraestrutura de teste em `apps/validacao/ai_provider_smoke.py` e
`GOOGLE_AI_API_KEY`/`.env.ai.local`, caso prefira rodar via API em vez do site). Peça explicitamente para o
modelo usar a capacidade de busca na web antes de responder — sem grounding, o risco de resposta plausível
porém inventada é alto, exatamente o que este prompt pede para evitar.

---

## PROMPT

```text
Você é um pesquisador regulatório. Sua tarefa é levantar, com fontes verificáveis, as exigências oficiais
atuais para exportação de gado bovino vivo e/ou carne bovina in natura do Brasil para quatro mercados:
China, Estados Unidos, União Europeia e Indonésia.

REGRAS OBRIGATÓRIAS, sem exceção:

1. Use busca na web para cada afirmação factual. Não responda de memória sobre datas, números de norma ou
   nomes oficiais de instrumento regulatório.
2. Se você não conseguir confirmar um dado com uma fonte específica, escreva literalmente "NÃO VERIFICADO"
   nesse campo — nunca preencha com algo plausível. Uma resposta incompleta e honesta vale mais que uma
   resposta completa e inventada.
3. Distinga claramente o que está em vigor hoje do que está proposto, em consulta pública ou com vigência
   futura ainda não iniciada. Datas de entrada em vigor de regulação já foram adiadas antes (ex.: EUDR) —
   confira a data vigente no momento da pesquisa, não uma data lembrada de treinamento.
4. Para cada exigência, cite a fonte: nome oficial do instrumento (lei, decreto, regulamento, instrução
   normativa, protocolo sanitário bilateral, resolução), autoridade emissora, jurisdição, data de publicação
   e/ou vigência, e URL da fonte oficial (site de governo, boletim oficial, ou organismo internacional como
   OMSA/WOAH) quando existir.
5. Não fabrique número de lei, data ou URL. Se a fonte primária não estiver acessível, diga isso
   explicitamente e cite a fonte secundária usada (ex.: notícia, análise de consultoria) com a ressalva de
   que não é fonte primária.
6. Registre a data em que você fez esta pesquisa — a resposta é uma fotografia de hoje, não uma verdade
   permanente.

Para CADA um dos quatro mercados (China, Estados Unidos, União Europeia, Indonésia), responda no formato
abaixo, repetindo a estrutura por mercado:

---
### Mercado: <nome>

#### 1. Status sanitário exigido
- Reconhecimento de status livre de febre aftosa (com ou sem vacinação) exigido pelo mercado importador,
  e se o Brasil (ou a região/zona brasileira específica) tem esse reconhecimento hoje.
- Outras exigências sanitárias específicas (ex.: brucelose, tuberculose, doença hemorrágica epizoótica),
  se aplicável a bovinos.
- Fonte(s) com citação completa.

#### 2. Rastreabilidade e identificação individual
- Exigência de identificação individual do animal (equivalente ao SISBOV brasileiro) para elegibilidade
  de exportação.
- Nível de granularidade exigido (predial vs. individual) e período mínimo de rastreabilidade histórica
  exigido antes do embarque.
- Fonte(s).

#### 3. Resíduos de medicamentos veterinários e período de carência
- Limites máximos de resíduo (LMR) aceitos pelo mercado para antimicrobianos/antiparasitários comuns em
  bovinos, se diferentes do padrão brasileiro (Ministério da Agricultura/ANVISA).
- Qualquer exigência de carência mínima diferenciada por mercado.
- Fonte(s).

#### 4. Exigências ambientais e territoriais (relevante especialmente para UE)
- Exigência de rastreabilidade geoespacial / ausência de desmatamento (ex.: EUDR da União Europeia) —
  data de vigência ATUAL confirmada (não presumida), escopo de produtos cobertos, e o que é exigido do
  exportador/produtor em termos de geolocalização.
- Qualquer exigência equivalente para os demais mercados.
- Fonte(s).

#### 5. Habilitação de estabelecimento (frigorífico/unidade processadora)
- Processo de habilitação do estabelecimento brasileiro para exportar a esse mercado (lista de
  estabelecimentos habilitados, autoridade que audita/aprova, frequência de reavaliação).
- Fonte(s), incluindo, se existir, lista pública de estabelecimentos habilitados.

#### 6. Instrumentos normativos que fundamentam o acima
Para cada exigência citada em 1-5, listar em tabela:

| Instrumento (nome oficial) | Tipo (lei/decreto/regulamento/protocolo bilateral/instrução) | Autoridade emissora | Jurisdição | Publicado em | Vigente desde | Status (vigente/proposto/revogado) | URL da fonte oficial |
|---|---|---|---|---|---|---|---|

#### 7. Mudanças recentes ou pendentes (últimos 12 meses / anunciadas)
- Qualquer alteração normativa recente, proposta em consulta pública, ou data de entrada em vigor
  adiada/confirmada que afete os itens 1-5.

#### 8. Lacunas desta pesquisa
- Liste explicitamente o que você NÃO conseguiu verificar com fonte confiável, em vez de omitir.

---

Ao final, inclua uma seção "Data da pesquisa" com a data/hora em que a busca foi realizada, e uma seção
"Fontes primárias vs. secundárias" resumindo quais afirmações têm fonte oficial direta e quais dependem de
fonte secundária.
```

---

## Observação sobre Indonésia

Indonésia não consta hoje na matriz de mercados do Titan (`packages/livestock_application/
market_eligibility.py` só declara `exportacao-china`, `exportacao-estados-unidos` e
`exportacao-uniao-europeia`). Incluí Indonésia no prompt porque foi pedido explicitamente, mas adicionar um
quarto mercado à matriz é, em si, uma decisão de produto separada desta pesquisa — ver
`docs/livestock/MARKET_NORMATIVE_BASIS_INTAKE_GUIDE.md`.
