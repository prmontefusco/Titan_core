# Acesso oficial ao SISBOV/MAPA — Investigação

**Data:** 15 de setembro de 2026
**Sessão:** Investigação externa (pesquisa web), não Discovery de engenharia — não há decisão de arquitetura
a tomar ainda; a pergunta é puramente "isso é possível, e como".
**Gatilho:** `docs/plans/SISBOV_CORTE3_DISCOVERY.md` concluiu DEFER para o Corte 3 da `ADR-0058`, com gatilho
de retomada explícito: "acesso oficial (ou caminho concreto e autorizado) ao SISBOV/MAPA". Esta investigação
responde a essa pergunta.

---

## Método e aviso de proveniência

Pesquisa feita nesta sessão via busca web e leitura direta de páginas oficiais (`gov.br`,
`agricultura.gov.br`). Achados abaixo são separados em **verificado por fonte primária lida diretamente
nesta sessão** e **não verificado/desatualizado**. Uma armadilha concreta foi encontrada e descartada no
processo: buscas por "prazo de migração para o novo SISBOV" retornam com destaque dois artigos
(`brangus.org.br`, `beefpoint.com.br`) que, por título, parecem falar do "SISBOV 2.0" atual, mas ao serem
lidos diretamente são de **19 de janeiro de 2007**, sobre uma migração de sistema que já ocorreu há quase
vinte anos (prazo então era 31/12/2007). Nenhum dado desses dois artigos é usado abaixo. Registro isso porque
é exatamente o tipo de erro que uma sessão futura, pesquisando o mesmo tema com menos cuidado, cometeria.

## Achado central (verificado por fonte primária)

**O SISBOV oficial tem uma API REST real e documentada — "API de Integração SISBOV 2.0"
(`manual-api-treinamento-sisbov.agricultura.gov.br`, com especificação Swagger como fonte "soberana").** Isso
é mais concreto do que o esperado: não é preciso "pedir dados por ofício", existe um mecanismo técnico de
integração já em produção.

- **Autenticação:** `POST /integracao/auth/system` com headers `X-ACCESS-KEY`/`X-SECRET-KEY`, devolvendo um
  Bearer Token JWT usado nas chamadas seguintes.
- **Recursos disponíveis (nível simplificado):** animais, propriedades, produtores, proprietários, técnicos,
  movimentações e GTAs. Nível completo acrescenta upload em lote, lotes, numeração, frigoríficos, inspeções e
  processos administrativos.
- **Modelo de acesso:** a documentação descreve exatamente dois perfis — **`Certificadora`** (escopo restrito
  aos próprios recursos) e **`Admin`** (irrestrito). **Não há nenhum perfil de leitura pública, consulta por
  terceiros ou integração para sistema que não seja uma certificadora credenciada** — nem no manual de
  treinamento, nem na wiki da API.
- **Contato técnico do sistema:** `sisbov@agricultura.gov.br`, (61) 3218-2207 / 2677.

## O que significa "virar certificadora" (verificado por fonte primária — catálogo de serviços `gov.br`)

O credenciamento como certificadora é o único caminho documentado para obter `X-ACCESS-KEY`/`X-SECRET-KEY`.
Não é um cadastro de desenvolvedor — é credenciamento como **entidade regulada que exerce função delegada
pelo MAPA**:

- Elegível: "empresas públicas ou privadas interessadas em participar do SISBOV como entidades
  certificadoras".
- Exigências: documentação de constituição da empresa; estrutura organizacional e administrativa;
  **estrutura de pessoal compatível com a área geográfica de abrangência**; **diretor técnico habilitado e
  registrado em conselho profissional**; manual operacional próprio; termo de compromisso assinado pelo
  representante legal e pelo diretor técnico.
- Custo: gratuito. Prazo: "não estimado ainda" pelo próprio MAPA.
- Órgão responsável: Coordenação de Sistemas de Rastreabilidade / Secretaria de Defesa Agropecuária (SDA),
  via Superintendências Federais de Agricultura; submissão por processo SEI.

**Isso não é integração de software — é se tornar uma entidade certificadora.** O papel de certificadora
inclui responsabilidades operacionais reais no mundo físico (aplicar/homologar identificadores, manter
estrutura técnica proporcional à área de cobertura, responder por um diretor técnico registrado em conselho
profissional). O Titan é uma plataforma de software; não tem, e não deveria fabricar, essa capacidade
operacional de campo. Pedir credenciamento como certificadora só para obter leitura de API seria pretender
ser algo que a organização não é — o mesmo tipo de "aprovação privada apresentada como entendimento oficial"
que `DOMAIN.md` já proibiu nesta sessão para `NormativeBasis`.

## Opções

**A — Titan busca credenciamento como certificadora SISBOV.**
Tecnicamente obtém acesso pleno à API. Rejeitada como primeira opção: exige que o Titan (ou uma organização
por trás dele) assuma função regulatória real — diretor técnico registrado, estrutura de campo proporcional à
área de cobertura — que não corresponde ao que o produto é hoje. É uma decisão de negócio/regulatória de
outra ordem de grandeza, não uma integração técnica.

**B — Parceria com uma certificadora já credenciada.**
Uma certificadora existente (ex.: `pantanalcertificadora.com.br`, citada nas próprias páginas oficiais como
exemplo do setor) já tem `X-ACCESS-KEY`/`X-SECRET-KEY` e a estrutura de campo exigida. Uma parceria comercial
poderia permitir que o Titan consuma dados via essa certificadora (ela consulta em nome do produtor cliente
comum, ou expõe um contrato de compartilhamento). Isso é decisão comercial — quem, condições, custo — não
teria BUILD sem ela estar fechada.

**C — Consulta formal ao MAPA perguntando se existe modalidade de acesso mais estreita.**
Nenhuma documentação pública menciona um perfil de "consulta/leitura" para sistema privado de rastreabilidade
que não seja certificadora — mas a documentação pública também não é exaustiva (a wiki não descreve nem o
processo de solicitação de credenciais de certificadora, que só apareceu no catálogo de serviços). Um contato
direto a `sisbov@agricultura.gov.br` custa uma pergunta e pode revelar uma modalidade não documentada (ex.:
convênio, API pública futura, consulta pontual por CPF/CNPJ do proprietário). Não garante resposta nem prazo.

**D — DEFER indefinidamente, sem próxima ação.**
Mantém o Corte 3 bloqueado sem abrir nenhuma frente nova. Evita esforço, mas descarta a única informação nova
desta investigação (a API existe e tem contato direto).

## Trade-offs

| Opção | A favor | Contra |
|---|---|---|
| A — Titan vira certificadora | Acesso pleno e direto | Desproporcional: assume função regulatória de campo que o produto não exerce; decisão de outra ordem, não técnica |
| B — parceria com certificadora | Usa estrutura já credenciada e testada pelo setor | Depende de encontrar e negociar parceiro comercial; nenhum controle técnico sobre prazo |
| C — consulta formal ao MAPA | Barata (uma pergunta), pode revelar caminho não documentado | Sem garantia de resposta ou de que exista modalidade mais leve |
| D — DEFER sem ação | Zero esforço | Desperdiça o achado concreto (API existe, tem contato) |

## Recomendação

**C, em paralelo com registrar B como opção comercial a avaliar.** Diferente da conclusão anterior desta
mesma frente (`SISBOV_CORTE3_DISCOVERY.md`), que tratava "acesso oficial" como uma incógnita grande e
indefinida, esta investigação encontrou que **existe um sistema real, documentado, com um contato técnico
nomeado** — o próximo passo de menor custo não é mais "pesquisar mais", é perguntar diretamente ao MAPA se
existe um caminho para um sistema privado de rastreabilidade como o Titan sem assumir o papel completo de
certificadora. A Opção A (Titan virar certificadora) não é recomendada: é uma mudança de natureza da
organização, não uma decisão técnica que esta investigação deveria empurrar.

## Decisão necessária

1. Autorizar contato formal a `sisbov@agricultura.gov.br` perguntando se existe modalidade de acesso/consulta
   para sistema privado de rastreabilidade que não seja certificadora credenciada — e, se não existir, qual o
   caminho recomendado pelo próprio MAPA para um caso como o do Titan?
2. Em paralelo, você tem conhecimento de alguma certificadora credenciada (ou relação comercial) que valha a
   pena avaliar como parceira (Opção B)?

Enquanto nenhuma das duas gerar um caminho concreto, o Corte 3 da `ADR-0058` permanece bloqueado — mas agora
por uma causa mais precisa e acionável: falta decisão comercial/institucional sobre como o Titan se relaciona
com o SISBOV oficial, não falta de informação sobre se ele existe.

## Parqueado em 16/09/2026

Nem o contato formal ao MAPA (Opção C) nem a avaliação de parceria com certificadora (Opção B) serão
perseguidos agora — decisão do responsável, sem prazo definido para retomada. Nenhuma das duas depende de
código ou de outra decisão deste repositório; podem ser retomadas a qualquer momento futuro simplesmente
executando os próximos passos já descritos acima, sem precisar refazer esta investigação.

## Fontes consultadas nesta sessão

- [API de Integração SISBOV 2.0 — manual de treinamento](https://manual-api-treinamento-sisbov.agricultura.gov.br/)
- [Wiki — API de Integração SISBOV 2.0](https://manual-api-treinamento-sisbov.agricultura.gov.br/solucoes/wiki/)
- [MAPA — sisbov.agricultura.gov.br](https://sisbov.agricultura.gov.br/)
- [Credenciar certificadoras no SISBOV — catálogo de serviços gov.br](https://www.gov.br/pt-br/servicos/credenciar-certificadoras-no-sisbov)
- [Credenciamento de Certificadora no SISBOV — carta de serviços MAPA](https://www.gov.br/agricultura/pt-br/acesso-a-informacao/acoes-e-programas/cartas-de-servico/defesa-agropecuaria-rastreabilidade/credenciamento-de-certificadora-no-sisbov) (nota: esta página, apesar do título, descreveu no fetch desta sessão o credenciamento de *fabricantes/importadores de brincos*, não de certificadoras — possível inconsistência de conteúdo vs. título no próprio portal gov.br; a página de "Credenciar certificadoras" listada acima é a fonte usada para os requisitos de certificadora)
