# Resultado da Pesquisa Gemini — Base Normativa de Mercado (China/EUA/UE/Indonésia)

**Data da pesquisa (declarada pelo Gemini):** 14/09/2026, 17:45 (horário local)
**Data de recebimento neste repositório:** 14/09/2026
**Status:** **CLAIM — não validado, não é `NormativeBasis`.** Ver
`docs/livestock/MARKET_NORMATIVE_BASIS_INTAKE_GUIDE.md` para o que isso significa e os passos exigidos
antes de qualquer uso em `Policy`/`Rule`/`Evaluation`/`Decision`.
**Prompt de origem:** `docs/livestock/MARKET_NORMATIVE_BASIS_RESEARCH_PROMPT.md`

---

## Nota de proveniência e verificação preliminar (14/09/2026)

Esta seção foi acrescentada por esta sessão ao receber o resultado colado pelo usuário. **Não substitui** a
revisão humana com competência regulatória declarada exigida pelo guia de intake — é uma checagem de
plausibilidade de primeira camada, feita por busca web independente em cinco das afirmações mais
consequentes do texto abaixo.

### O que foi checado e corroborado por fonte independente

| Afirmação da pesquisa | Checagem independente | Resultado |
|---|---|---|
| OMSA/WOAH reconheceu o Brasil livre de febre aftosa sem vacinação em 29/05/2025, na 92ª Sessão Geral, em Paris | Corroborado por `gov.br/agricultura` (MAPA), Agência Brasil, ApexBrasil, USP/FMVZ | Consistente |
| GACC (China) reconheceu o Brasil livre de febre aftosa sem vacinação, declaração datada 29/05/2026, comunicada ao Brasil em 02/06/2026 | Corroborado por `gov.br/agricultura` (MAPA), Correio Braziliense, Diário do Grande ABC | Consistente |
| UE suspendeu a importação de carnes e produtos de origem animal do Brasil a partir de 03/09/2026, por insuficiência de garantias sobre controle de antimicrobianos (não por contaminação) | Corroborado por Agência Brasil (agência oficial do governo brasileiro), Agrimidia, Terra | Consistente |
| EUDR adiado para 30/12/2026 (grandes/médios operadores) por Regulamento (UE) 2025/2650, publicado no Jornal Oficial em 23/12/2025 | Corroborado por Access2Markets (Comissão Europeia), Mayer Brown, Vieira de Almeida | Consistente |
| Indonésia exige certificação Halal (BPJPH) obrigatória para carne importada a partir de 17/10/2026, sem prorrogação para carne/laticínios | Corroborado por fontes especializadas em certificação halal (Centro Halal, American Halal Foundation, BPJPH) | Consistente, com nuance: as fontes independentes destacam que carne/laticínios **nunca tiveram** o período de carência que outros produtos tiveram — já estavam sob exigência separada antes dessa data-limite |

### O que NÃO foi checado — permanece exigindo verificação humana com fonte primária

Os cinco itens acima são os eventos centrais (as narrativas). **Não verifiquei** os detalhes técnicos
granulares abaixo, que são exatamente a classe de dado onde um modelo de linguagem mais erra mesmo quando
acerta o evento geral — números de decreto, seções de regulamento, limites numéricos e contagens:

- Números exatos de decreto/regulamento citados na tabela de cada mercado (ex.: "Decreto GACC nº 248",
  "GB 31650-2019", "9 CFR § 94.29", "21 CFR § 556.570", datas de publicação exatas);
- Valores numéricos de LMR citados (ex.: "30 ppb ractopamina no músculo", "1,6 ppm ivermectina no fígado");
- A contagem "73 plantas frigoríficas brasileiras habilitadas" pela Indonésia em setembro de 2026;
- O texto integral e as condições exatas do protocolo bilateral Brasil-China para bovinos vivos (o próprio
  Gemini já marcou isso como não verificado, seção "Lacunas");
- O texto legal integral do ato da Comissão Europeia de 03/09/2026 (o próprio Gemini já marcou isso como
  dependente de fonte secundária — imprensa, não Jornal Oficial).

**Conclusão desta checagem preliminar:** a pesquisa parece bem fundamentada nos eventos centrais, mas os
citações técnicas específicas (números de norma, limites numéricos, contagens) precisam de conferência
humana contra fonte primária antes de qualquer uma virar campo de `NormativeInstrument`/`NormativeReference`
no Titan — exatamente como o guia de intake já previa.

---

## Conteúdo da pesquisa (colado pelo usuário, sem edição de conteúdo)

### Mercado: China

**1. Status sanitário exigido**

Febre aftosa e reconhecimento: A China exige que a carne bovina seja originária de regiões livres de febre
aftosa (Foot-and-Mouth Disease - FMD). Historicamente, as exportações brasileiras eram autorizadas a partir
de zonas reconhecidas internacionalmente como livres de febre aftosa com vacinação. Em 29 de maio de 2025, a
Organização Mundial de Saúde Animal (OMSA/WOAH), durante a 92ª Sessão Geral, reconheceu oficialmente todo o
território brasileiro como livre de febre aftosa sem vacinação. Em junho de 2026, a Administração-Geral de
Aduanas da China (GACC) concedeu o reconhecimento oficial bilateral do status brasileiro livre de febre
aftosa sem vacinação, abrindo negociações para ampliação do protocolo bilateral (incluindo cortes com osso
e miúdos).

Gado bovino vivo: MERCADO FECHADO. Não existe protocolo sanitário bilateral vigente entre o Brasil e a
China que autorize a exportação de bovinos vivos em pé para abate ou reprodução. O comércio bilateral
limita-se à carne bovina in natura desossada, miúdos e subprodutos específicos (como cálculo biliar bovino,
com protocolo firmado em 2026).

Outras exigências sanitárias (EEB, Brucelose, Tuberculose):

- Encefalopatia Espongiforme Bovina (EEB/BSE): O protocolo bilateral estabelece mecanismo de autoembargo
  imediato caso o Brasil identifique qualquer caso de EEB (mesmo atípico). O envio de carne é suspenso
  preventivamente pelo MAPA até que a autoridade chinesa (GACC) analise o laudo técnico da OMSA e autorize a
  retomada. A carne deve provir de animais com menos de 30 meses de idade (critério histórico de mitigação
  de risco de EEB).
- Brucelose e Tuberculose: Os animais devem ser originários de propriedades cadastradas no Serviço
  Veterinário Oficial (SVO), submetidas a controle sanitário oficial, sem histórico de focos dessas doenças
  nos prazos previstos nas normas de vigilância agropecuária.

Fonte(s): OMSA/WOAH – Resolução da 92ª Sessão Geral da Assembleia Mundial de Delegados (29 de maio de
2025); GACC / Ministério da Agricultura e Pecuária (MAPA) – Comunicados bilaterais sobre o reconhecimento
do status sanitário (junho de 2026); Protocolo Sanitário Bilateral Brasil-China sobre Carne Bovina
Desossada Congelada (2012, aditado em 2015 e atualizações técnicas DIPOA/MAPA).

**2. Rastreabilidade e identificação individual**

Exigência de identificação individual (SISBOV): A China não exige obrigatoriamente a certificação SISBOV
(que é o padrão mandatório da União Europeia). Contudo, o protocolo bilateral exige comprovação documental
estrita de que os animais são nascidos e criados no Brasil, rastreáveis até a fazenda de origem, e que
cumpram o critério de idade do padrão comercial "Boi China" (máximo de 30 meses no abate, atestado por
registros de nascimento ou dentição — até 4 dentes incisivos permanentes).

Nível de granularidade e histórico de permanência: A granularidade regulatória exigida na esfera oficial é
predial/lote, baseada na Guia de Trânsito Animal (GTA) e na Base Nacional de Dados (BND), sob supervisão do
SVO. A indústria exportadora exige que os animais permaneçam em propriedades livres de interdições
sanitárias e ambientais, com registro das movimentações ao longo de sua vida produtiva.

Fonte(s): MAPA/DIPOA – Manuais de Procedimentos de Certificação Sanitária Internacional e Sistema de
Informação de Requisitos e Certificados da Área Animal (SISREC); Protocolo Sanitário Bilateral Brasil-China
de Quarentena e Inspeção Veterinária.

**3. Resíduos de medicamentos veterinários e período de carência**

- Ractopamina e beta-agonistas: A China adota TOLERÂNCIA ZERO para o uso de ractopamina, clembuterol e
  quaisquer outros beta-agonistas na alimentação animal. É proibida a administração dessas substâncias a
  bovinos destinados ao abate para o mercado chinês.
- Hormônios promotores de crescimento: Proibição de promotores hormonais sintéticos e esteroides
  anabolizantes (como acetato de medroxiprogesterona e progesterona fora de indicações terapêuticas
  estritas com registro oficial). A detecção de resíduos na carne acarreta suspensão sumária da planta
  frigorífica pela GACC.
- Padrão de LMR: Regido pelo padrão chinês GB 31650-2019 (National Food Safety Standard - Maximum residue
  limits for veterinary drugs in foods). Resíduos de antimicrobianos e antiparasitários (como avermectinas)
  devem cumprir estritamente os LMRs chineses, frequentemente mais restritivos que os do Codex Alimentarius.
- Períodos de carência: Devem ser estritamente cumpridos com base na bula dos medicamentos veterinários
  registrados no MAPA, sendo exigido registro individual ou por lote de tratamentos sanitários e carências
  nas fichas de fornecimento de gado ao frigorífico.

Fonte(s): Ministério da Agricultura e Assuntos Rurais da China (MARA) / Comissão Nacional de Saúde (NHC) /
GACC – Norma GB 31650-2019; MAPA/SDA – Instruções técnicas sobre conformidade de resíduos para o mercado
chinês.

**4. Exigências ambientais e territoriais**

Exigências vigentes do governo importador: Não existe, no âmbito regulatório oficial do governo chinês
(GACC), legislação mandatória equivalente ao regulamento de desmatamento da UE (EUDR) que imponha
geolocalização por polígono ou data de corte legal para a entrada na alfândega.

Exigências de mercado e cadeia privada: Há crescente pressão comercial e compromissos voluntários do setor
privado (como o protocolo Beef on Track / Carne Legal do Ministério Público Federal brasileiro, adotado por
grandes frigoríficos habilitados para a China), que barram animais de áreas embargadas pelo IBAMA por
desmatamento ilegal, invasão de terras indígenas ou unidades de conservação.

Fonte(s): GACC – Decretos nº 248 e nº 249 (não contêm requisitos de desmatamento); Ministério Público
Federal (MPF) – Protocolo de Monitoramento de Fornecedores de Gado (Beef on Track).

**5. Habilitação de estabelecimento (frigorífico/unidade processadora)**

Processo de habilitação: O frigorífico deve possuir Serviço de Inspeção Federal (SIF) ativo e cumprir as
disposições dos Decretos GACC nº 248 (Regulamento de Registro e Gestão de Produtores Estrangeiros de
Alimentos Importados) e nº 249 (Medidas Administrativas de Segurança dos Alimentos Importados e
Exportados). A indicação é feita pelo MAPA (DIPOA) através do sistema informatizado CIFER (China Import
Food Enterprise Registration), seguida de auditoria documental ou presencial/virtual pela autoridade
aduaneira chinesa (GACC).

Lista pública e reavaliação: Os estabelecimentos autorizados constam do cadastro oficial da GACC. A GACC
realiza auditorias periódicas no sistema de defesa sanitária brasileiro e inspeções técnicas nas plantas;
não conformidades em auditoria ou detecção de resíduos químicos em porto de destino levam à suspensão
cautelar do estabelecimento até a conclusão do plano de ação corretiva.

Fonte(s): GACC – Decretos nº 248 e 249/2021; Portal Oficial CIFER/Single Window
(`ciferquery.singlewindow.cn`); MAPA – Lista de Estabelecimentos Nacionais Habilitados à Exportação (Portal
gov.br).

**6. Instrumentos normativos**

| Instrumento | Tipo | Autoridade | Jurisdição | Publicado em | Vigente desde | Status | Fonte |
|---|---|---|---|---|---|---|---|
| Protocolo Sanitário Brasil-China de Carne Bovina | Protocolo Bilateral | MAPA / AQSIQ-GACC | Bilateral | 2012 (aditado 2015/2019) | 2015 | Vigente | gov.br/agricultura |
| Decreto GACC nº 248 (Registro de Empresas Estrangeiras) | Decreto | GACC | China | 12/04/2021 | 01/01/2022 | Vigente | customs.gov.cn |
| Decreto GACC nº 249 (Segurança dos Alimentos Importados) | Decreto | GACC | China | 12/04/2021 | 01/01/2022 | Vigente | customs.gov.cn |
| GB 31650-2019 (LMR Medicamentos Veterinários) | Padrão Técnico Nacional | NHC/MARA/SAMR | China | 06/09/2019 | 01/04/2020 | Vigente | samr.gov.cn |
| Resolução 92ª Sessão Geral OMSA | Resolução Internacional | OMSA/WOAH | Internacional | 29/05/2025 | 29/05/2025 | Vigente | woah.org |
| Portaria MAPA nº 665/2024 | Portaria Ministerial | MAPA | Brasil | 21/03/2024 | 02/05/2024 | Vigente | in.gov.br |

**7. Mudanças recentes ou pendentes**

Reconhecimento bilateral de febre aftosa sem vacinação (junho de 2026); protocolo sanitário para cálculo
biliar bovino (2026); intensificação de auditorias sanitárias e controles de resíduos (2026).

**8. Lacunas desta pesquisa**

Não foi possível obter o texto integral e não censurado do documento diplomático confidencial do protocolo
bilateral atualizado de 2026 via link público aberto; dados extraídos de notas conjuntas do MAPA, circulares
do DIPOA e normas técnicas da GACC.

---

### Mercado: Estados Unidos

**1. Status sanitário exigido**

- Gado bovino vivo: PROIBIDO. O USDA APHIS não autoriza a importação de bovinos vivos em pé provenientes do
  Brasil devido ao risco de transmissão de febre aftosa e outras doenças de ruminantes (9 CFR Part 93).
- Carne bovina in natura: Permitida exclusivamente sob regras estritas de mitigação de risco (9 CFR §
  94.29). Regiões elegíveis: 14 estados brasileiros nomeados (Bahia, DF, Espírito Santo, Goiás, Mato Grosso,
  Mato Grosso do Sul, Minas Gerais, Paraná, Rio Grande do Sul, Rio de Janeiro, Rondônia, São Paulo, Sergipe,
  Tocantins), mais Santa Catarina sob 9 CFR § 94.11.
- Condições obrigatórias do produto: apenas carne desossada; remoção completa de ossos, coágulos e
  principais linfonodos; maturação mínima de 24h com pH < 6,0 no Longissimus dorsi antes da desossa.
- EEB/BSE: Brasil classificado como risco insignificante (9 CFR § 94.18/94.19).

Fonte(s): 9 CFR § 94.29 (ecfr.gov); USDA APHIS – Import Provisions for Fresh Beef from Brazil.

**2. Rastreabilidade e identificação individual**

SISBOV NÃO exigido. Controle oficial em nível de propriedade/rebanho: a carne deve provir de animais
nascidos, criados e mantidos na região autorizada desde o nascimento ou por, no mínimo, 60 dias imediatamente
anteriores ao abate (9 CFR § 94.29(b)), sem trânsito por regiões não elegíveis.

Fonte(s): 9 CFR § 94.29(a)-(c); USDA FSIS – Import Guidance for Meat Products from Brazil.

**3. Resíduos de medicamentos veterinários e período de carência**

- LMR regidos por 21 CFR Part 556 (FDA), monitorados pelo National Residue Program (FSIS).
- Ractopamina: PERMITIDA nos EUA — tolerância de 30 ppb no músculo e 90 ppb no fígado (21 CFR § 556.570).
- Ivermectina: tolerância de 1,6 ppm no fígado e 10 ppb no músculo (21 CFR § 556.344).
- Hormônios promotores de crescimento (estradiol, progesterona, testosterona) autorizados em implantes
  aprovados pela FDA, sob condições regulamentadas.

Fonte(s): 21 CFR Part 556 (ecfr.gov); USDA FSIS – National Residue Program.

**4. Exigências ambientais e territoriais**

Sem regulação federal em vigor sobre desmatamento/geolocalização. Projeto de lei FOREST Act (S.825/H.R.1812)
em tramitação no Congresso, não aprovado.

Fonte(s): congress.gov.

**5. Habilitação de estabelecimento**

Baseado em equivalência de sistema de inspeção (USDA FSIS audita SIF/MAPA); equivalência para carne bovina
in natura reestabelecida em 21/02/2020. Lista pública de estabelecimentos elegíveis mantida pelo FSIS, com
auditorias periódicas e reinspeção física/laboratorial amostral no porto de entrada.

Fonte(s): USDA FSIS – Eligible Foreign Establishments – Brazil; Federal Register Vol. 85, No. 37.

**6. Instrumentos normativos**

| Instrumento | Tipo | Autoridade | Jurisdição | Publicado em | Vigente desde | Status | Fonte |
|---|---|---|---|---|---|---|---|
| 9 CFR § 94.29 | Regulamento Federal | USDA APHIS | EUA | 02/07/2015 | 01/09/2015 (reinst. 2020) | Vigente | ecfr.gov |
| 9 CFR § 94.11 | Regulamento Federal | USDA APHIS | EUA | Codificado | Vigente | Vigente | ecfr.gov |
| 21 CFR Part 556 | Regulamento Federal | FDA | EUA | Codificado | Vigente | Vigente | ecfr.gov |
| Federal Meat Inspection Act (21 U.S.C. 601) | Lei Federal | Congresso dos EUA | EUA | 1906 (emendada) | Vigente | Vigente | uscode.house.gov |
| FSIS Notice — Reinstatement of Brazil Fresh Beef Eligibility | Notificação Administrativa | USDA FSIS | EUA | 21/02/2020 | 21/02/2020 | Vigente | fsis.usda.gov |

**7. Mudanças recentes ou pendentes**

Apesar do reconhecimento pleno da OMSA (maio/2025), o APHIS não alterou automaticamente o 9 CFR § 94.29 —
mitigação de desossa/maturação/pH e a lista dos 14 estados seguem exigidas. Cota "Others" de 65.005 t
(tarifa intra-cota US$ 0,044/kg); tarifa extracota de 26,4% após esgotamento.

**8. Lacunas desta pesquisa**

Não localizada publicação formal do APHIS no Federal Register dispensando maturação/pH ou ampliando a lista
de 14 estados após o reconhecimento da OMSA de maio/2025 — portanto, as exigências de mitigação permanecem
plenamente em vigor conforme a pesquisa.

---

### Mercado: União Europeia

**1. Status sanitário exigido**

- Gado bovino vivo: NÃO AUTORIZADO (Brasil fora do Anexo I do Regulamento de Execução (UE) 2021/404).
- Carne bovina in natura: historicamente autorizada, desossada e maturada, de zonas aprovadas.
- **SUSPENSÃO EM VIGOR desde 03/09/2026** (ver checagem independente acima): UE suspendeu importação de
  carnes e produtos de origem animal do Brasil (bovina, aves, mel, ovos, pescados) por garantias
  insuficientes quanto ao Regulamento (UE) 2019/6 art. 118 e Regulamento Delegado (UE) 2023/1529
  (antimicrobianos como promotores de crescimento / reservados a uso humano). Brasil retirado da lista de
  países com garantias equivalentes.
- Estradiol em fêmeas (set/2024): Diretiva 96/22/CE + Ofício-Circular Conjunto MAPA nº 24/2024 restringiram
  abate para UE a machos, até sistema que garanta ausência de exposição a estradiol em protocolos de IATF.

Fonte(s): Regulamento (UE) 2016/429; Regulamento de Execução (UE) 2021/404; Regulamento (UE) 2019/6 art.
118 e Regulamento Delegado (UE) 2023/1529; MAPA – Ofício-Circular Conjunto nº 24/2024 e Portaria SDA/MAPA nº
1.635/2026.

**2. Rastreabilidade e identificação individual**

SISBOV OBRIGATÓRIO, com dupla identificação individual (brinco + botom eletrônico), registrado na Base
Nacional de Dados Únicos. Animais devem nascer ou permanecer no mínimo 90 dias em ERAS (Estabelecimento
Rural Aprovado no SISBOV) e cumprir ao menos 40 dias na última ERAS antes do embarque para abate.

Fonte(s): IN MAPA nº 17/2006 e nº 51/2018; Decisão da Comissão 2008/61/CE.

**3. Resíduos de medicamentos veterinários e período de carência**

TOLERÂNCIA ZERO para estilbenos, tireostáticos, beta-agonistas (ractopamina) e substâncias com ação
estrogênica/androgênica/gestagênica para engorda (Diretiva 96/22/CE). LMR regidos pelo Regulamento (CE) nº
470/2009 e Regulamento (UE) nº 37/2010. Vedação de antimicrobianos para promoção de crescimento e da lista
de reserva humana da UE (Regulamento 2019/6 / Regulamento Delegado 2023/1529) — motivo direto da suspensão
de 03/09/2026.

Fonte(s): Diretiva 96/22/CE; Regulamento (CE) nº 470/2009; Regulamento (UE) nº 37/2010; Regulamento (UE)
2019/6; Regulamento Delegado (UE) 2023/1529.

**4. Exigências ambientais e territoriais (EUDR)**

Regulamento (UE) 2023/1115 (EUDR). Escopo: bovinos vivos (SH 0102), carnes bovinas frescas/refrigeradas/
congeladas (SH 0201, 0202, 0206, 0210), couros e peles (SH 4101). Data de corte: 31/12/2020 — nenhuma carne
pode ser colocada no mercado da UE se produzida em terra desmatada (legal ou ilegal) após essa data.
Geolocalização exigida: polígono completo para propriedades > 4 ha; ponto único para propriedades ≤ 4 ha.
Declaração de Diligência Prévia (DDS) obrigatória no sistema eletrônico da UE.

**Vigência confirmada por checagem independente:** adiada duas vezes — Regulamento (UE) 2024/3234
(dez/2024) e depois Regulamento (UE) 2025/2650 (publicado no Jornal Oficial em 23/12/2025) — aplicação
obrigatória a partir de **30/12/2026** para grandes/médios operadores e comerciantes de todos os portes, e
**30/06/2027** para micro/pequenas empresas.

Fonte(s): Regulamento (UE) 2023/1115 (JO L 150, 09/06/2023); Regulamento (UE) 2024/3234; Regulamento (UE)
2025/2650.

**5. Habilitação de estabelecimento**

Regime de pré-listagem: MAPA/DIPOA inspeciona conformidade com Regulamentos (CE) nº 852/2004 e nº 853/2004,
cadastra no TRACES NT; DG SANTE da Comissão Europeia aprova listagem e audita periodicamente in loco. Lista
pública no portal DG SANTE (Non-EU Approved Establishments).

Fonte(s): Regulamento (UE) 2017/625; Portal TRACES NT / DG SANTE.

**6. Instrumentos normativos**

| Instrumento | Tipo | Autoridade | Jurisdição | Publicado em | Vigente desde | Status | Fonte |
|---|---|---|---|---|---|---|---|
| Regulamento (UE) 2023/1115 (EUDR) | Regulamento | Parlamento/Conselho | UE | 09/06/2023 | 29/06/2023 | Vigente (aplicação adiada) | eur-lex.europa.eu |
| Regulamento (UE) 2024/3234 | Regulamento | Parlamento/Conselho | UE | 23/12/2024 | 26/12/2024 | Vigente | eur-lex.europa.eu |
| Regulamento (UE) 2025/2650 | Regulamento | Parlamento/Conselho | UE | 23/12/2025 | 26/12/2025 | Vigente | eur-lex.europa.eu |
| Regulamento (UE) 2019/6 (art. 118) | Regulamento | Parlamento/Conselho | UE | 07/01/2019 | 28/01/2022 | Vigente | eur-lex.europa.eu |
| Diretiva 96/22/CE | Diretiva | Conselho da UE | UE | 23/05/1996 | 23/05/1996 | Vigente | eur-lex.europa.eu |
| Regulamento (CE) nº 470/2009 / (UE) nº 37/2010 | Regulamentos | Parlamento/Comissão | UE | 2009/2010 | Vigente | Vigente | eur-lex.europa.eu |
| IN MAPA nº 51/2018 (SISBOV) | Instrução Normativa | MAPA | Brasil | 01/10/2018 | 01/10/2018 | Vigente | in.gov.br |
| Ofício-Circular Conjunto nº 24/2024 | Ofício-Circular | MAPA | Brasil | 20/09/2024 | 20/09/2024 | Vigente | gov.br/agricultura |

**7. Mudanças recentes ou pendentes**

Suspensão de 03/09/2026 (checagem independente confirma o evento; texto legal integral do ato da Comissão
não localizado em fonte primária aberta); adiamento do EUDR para 30/12/2026 confirmado; restrição a machos
por estradiol desde set/2024 mantida.

**8. Lacunas desta pesquisa**

Texto integral do ato da Comissão Europeia de 03/09/2026 não consolidado em ato normativo isolado
acessível no EUR-Lex até a data da pesquisa — verificado apenas por comunicados de imprensa e portarias de
resposta do MAPA.

---

### Mercado: Indonésia

**1. Status sanitário exigido**

Zoneamento por Lei nº 41/2014 (altera Lei nº 18/2009). Com o reconhecimento OMSA de maio/2025, todo o
rebanho brasileiro atende ao requisito zootécnico de origem.

- Carne bovina in natura e subprodutos: MERCADO ABERTO (protocolo MAPA/DGLAHS) — com osso, sem osso, miúdos,
  preparados de carne.
- Gado bovino vivo: MERCADO ABERTO — protocolo bilateral para engorda (feedlot) e abate imediato, regido
  nacionalmente pela IN MAPA nº 46/2018. Exige Estabelecimento Pré-Embarque (EPE) credenciado, com
  quarentena/isolamento, testes de brucelose (sorologia), tuberculose (tuberculinização) e inspeção
  parasitária, atestados em Certificado Zoossanitário Internacional (CZI).

Fonte(s): Lei nº 41/2014; DGLAHS/Ministério da Agricultura da Indonésia; IN MAPA nº 46/2018.

**2. Rastreabilidade e identificação individual**

Carne: SISBOV não exigido; rastreabilidade oficial por GTA + SIF, nível predial/lote. Gado vivo: identificação
individual OBRIGATÓRIA — brinco numerado por animal no EPE, numeração constando no CZI.

Fonte(s): IN MAPA nº 46/2018; DGLAHS – SOP for Live Cattle Importation.

**3. Resíduos de medicamentos veterinários e período de carência**

LMR regidos por Permentan nº 14/2020 e normas SNI. TOLERÂNCIA ZERO para beta-agonistas e hormônios
sintéticos de crescimento (Lei nº 18/2009, art. 53). Carências conforme bula MAPA, validadas pela DGLAHS.

Fonte(s): Lei nº 18/2009 (art. 53); Permentan nº 14/2020.

**4. Exigências ambientais e territoriais**

Sem regulação de geolocalização/desmatamento para importação.

**5. Habilitação de estabelecimento e certificação Halal**

- Frigoríficos indicados pelo MAPA/DIPOA, auditados por DGLAHS e Barantin (Agência de Quarentena da
  Indonésia). Pesquisa cita 73 estabelecimentos habilitados em setembro/2026, após homologação de 21 novas
  plantas.
- **Certificação Halal obrigatória** — BPJPH (vinculada ao Ministério de Assuntos Religiosos), sob Lei nº
  33/2014 (UU JPH), Decreto Governamental (PP) nº 39/2021 e nº 42/2024. Abate deve seguir rito islâmico.
  Certificadoras brasileiras precisam de Acordo de Reconhecimento Mútuo (MRA) homologado junto ao BPJPH.
  **Prazo confirmado por checagem independente: 17/10/2026**, e as fontes independentes destacam que carne
  e laticínios nunca tiveram prorrogação — já estavam sob exigência separada antes dessa data. A partir de
  18/10/2026, cargas sem certificação BPJPH sofrem bloqueio de entrada.

Fonte(s): Lei nº 33/2014; Decreto Governamental nº 39/2021 e nº 42/2024; BPJPH (halal.go.id); DGLAHS —
lista de estabelecimentos (set/2026).

**6. Instrumentos normativos**

| Instrumento | Tipo | Autoridade | Jurisdição | Publicado em | Vigente desde | Status | Fonte |
|---|---|---|---|---|---|---|---|
| Lei nº 18/2009 (alterada pela Lei nº 41/2014) | Lei Federal | Parlamento da Indonésia | Indonésia | 2009/2014 | 2014 | Vigente | dpr.go.id |
| Lei nº 33/2014 (UU JPH — Halal) | Lei Federal | Governo da Indonésia | Indonésia | 17/10/2014 | 17/10/2014 | Vigente | peraturan.go.id |
| Decreto Governamental nº 42/2024 | Decreto Governamental | Presidente da Indonésia | Indonésia | 17/10/2024 | 17/10/2024 | Vigente | peraturan.go.id |
| Permentan nº 14/2020 (LMR) | Regulamento Ministerial | Ministério da Agricultura | Indonésia | 2020 | 2020 | Vigente | pertanian.go.id |
| IN MAPA nº 46/2018 (ruminantes vivos) | Instrução Normativa | MAPA | Brasil | 28/08/2018 | 28/08/2018 | Vigente | in.gov.br |
| Protocolo Sanitário Bilateral Brasil-Indonésia | Acordo Bilateral | MAPA/DGLAHS | Bilateral | 2019 (aditado 2023/2024) | 2019 | Vigente | gov.br/agricultura |

**7. Mudanças recentes ou pendentes**

Ampliação para 73 plantas habilitadas (set/2026, não verificado independentemente); marco Halal mandatório
em 17/10/2026 (confirmado independentemente); consolidação do status de aftosa sem vacinação (maio/2025).

**8. Lacunas desta pesquisa**

Texto integral em português do protocolo zootécnico específico para bovinos vivos (MAPA/DGLAHS) não
localizado; quarentena/testes de EPE confirmados via normas gerais da IN MAPA nº 46/2018 e questionário de
habilitação DGLAHS via processo SEI do MAPA.

---

## Fontes primárias vs. secundárias (conforme declarado pelo Gemini)

Ver seção equivalente no texto original recebido — resumidamente, a pesquisa identifica como dependentes de
fonte secundária (não confirmadas em diário oficial aberto): a suspensão da UE de 03/09/2026 (confirmada
como evento real por esta checagem independente, mas sem o ato normativo integral localizado), o
reconhecimento bilateral da China (idem — evento confirmado, protocolo formal ainda em redação diplomática
segundo a pesquisa) e a contagem de 73 plantas habilitadas pela Indonésia.
