# ADR 0040 — Evento reprodutivo como origem da identidade do animal

**Status:** Aceita
**Data:** 25 de julho de 2026
**Decisores:** fundador e responsável pela arquitetura do Titan

## Contexto

Até o Passo 13.2 o animal surgia por cadastro: `POST /v1/livestock/animals` criava o registro e `birth_date` era um campo preenchido por quem digitava. O Passo 13.2 acrescentou a genealogia, mas como ato separado — cadastra-se o bezerro e, numa segunda chamada, declara-se de quem ele é. Entre as duas existe uma janela em que o animal está no rebanho sem linhagem, e se a segunda chamada falha resta um órfão silencioso.

O Passo 13.3 fecha essa janela. Ao fazê-lo, precisou responder três perguntas que o `PLANO_DE_CONCLUSAO_DO_DOMINIO` já marcava como portão — natimorto, aborto e parto múltiplo — e a resposta reorganizou o modelo o bastante para exigir esta ADR.

## A decisão central

**O evento reprodutivo é separado do indivíduo rastreável.**

```text
Gestação
   │
   └── Evento reprodutivo
          │
          ├── PARTO
          │    ├── Bezerro A → Animal
          │    └── Bezerro B → Animal
          │
          └── ABORTO
               └── perda gestacional
                    (normalmente sem Animal)
```

O parto é um **evento materno** capaz de produzir zero, um ou vários indivíduos. Cada indivíduo produzido carrega o seu próprio resultado de nascimento. Essa separação é o que faz os três casos difíceis caírem no lugar sem exceção:

| Situação | Evento reprodutivo | Cria `Animal`? | Motivo |
|---|---|---|---|
| Nascimento vivo | `PARTO` | Sim | Existe indivíduo vivo rastreável |
| Natimorto | `PARTO`, resultado `NATIMORTO` | Sim, como indivíduo não-vivo ao nascer | Preserva genealogia e resultado reprodutivo |
| Aborto | `ABORTO` | Não, por padrão | Registra o resultado da gestação sem inventar animal operacional |
| Gemelar | Um `PARTO` | Dois ou mais | Um evento materno produziu vários indivíduos |

## Natimorto não é morte

A saída mais curta seria criar o animal e registrar `AnimalExit` com `MORTE` imediata. Ela está errada, e o erro é semântico antes de ser técnico: **`MORTE` afirma que o animal nasceu vivo e morreu depois.** Natimorto significa o contrário — não houve nascimento com vida.

A consequência aparece no indicador, que é onde alguém decide comprar ou reprovar:

```text
Errado:   97 nascimentos + 3 mortes neonatais
Correto:  94 nascidos vivos + 3 natimortos
```

Há um segundo motivo, interno ao modelo: `AnimalExit` significa **saída do rebanho ativo**, e quem nunca entrou não sai. Registrar saída para natimorto corromperia o significado que o Passo 13.1 estabeleceu.

**Decidido:** o natimorto **cria** `Animal`, com `birth_outcome = NATIMORTO`, e **não** recebe registro de saída. Ele tem valor genealógico e zootécnico, e por isso é rastreável; mas não entra no ciclo operacional do rebanho.

Três consequências obrigatórias:

1. O rebanho ativo passa a excluir quem não nasceu vivo, além de quem saiu.
2. A guarda que hoje recusa fatos posteriores à saída passa a recusar qualquer fato sobre quem não nasceu vivo.
3. `birth_outcome` é **constitutivo e imutável**, definido no nascimento — como `birth_date`. Não contraria a regra "estado derivado, nunca campo mutável" do Passo 13.1, que trata de estado que muda ao longo da vida.

Animais cadastrados fora de um parto — o rebanho legado — recebem `NAO_INFORMADO`. Preencher `NASCIDO_VIVO` por padrão afirmaria o que ninguém registrou, e a listagem exclui apenas `NATIMORTO` explicitamente. **Ausência se declara, nunca se infere.**

## Aborto não inventa indivíduo

Aborto é evento reprodutivo próprio e **não cria `Animal` por padrão**. Criar um registro rastreável com status morto para um feto sem identidade atribuível seria fabricar entidade a partir de um fato que não a produziu.

Fica reservada a direção — sem implementação agora — de uma entidade intermediária para o produto da gestação, se houver necessidade veterinária:

```text
PregnancyOutcome
 ├── ABORTO
 ├── NATIMORTO
 └── NASCIDO_VIVO
```

Ela permitiria registrar informação sobre o produto da gestação sem promovê-lo a `Animal`.

## Um parto, várias crias

Modelar o parto gemelar como dois partos **perde a informação de que os dois pertencem ao mesmo evento obstétrico** — e é exatamente essa informação que explica o caso mais comum e mais importante: um bezerro nasce vivo e o outro é natimorto.

```text
                   ┌── Animal B001  → NASCIDO_VIVO
Gestação → PARTO ──┤
                   └── Animal B002  → NATIMORTO
```

O parto pertence à mãe; os indivíduos pertencem ao resultado do parto.

## Propriedade de nascimento: derivada, com recuo explícito

A propriedade onde a cria nasceu é derivada da `PropertyStay` materna válida no instante do parto, quando houver **uma única** permanência determinável. Derivar reduz erro de digitação e aproveita a linha do tempo que o Titan já mantém.

```text
1. Existe PropertyStay determinável da mãe?  → deriva.
2. Não existe, e foi declarada?              → aceita a declarada.
3. Não existe nem foi declarada?             → propriedade desconhecida.
```

**A ausência de um dado contextual não impede o registro de um fato real.** É melhor ter "parto ocorrido, propriedade de nascimento desconhecida" do que nenhum parto registrado só porque a linha do tempo da mãe estava incompleta.

**Divergência não é resolvida em silêncio.** Se a propriedade declarada difere da permanência materna conhecida, o registro é recusado como conflito de domínio — não porque a declarada esteja necessariamente errada, mas porque a contradição precisa ser corrigida conscientemente.

A origem do valor viaja com ele, em `birth_property_source`:

```text
DERIVED_FROM_MATERNAL_STAY   — derivada da permanência da mãe
DECLARED                     — declaração manual
UNKNOWN                      — nenhuma das duas
```

Isso põe a propriedade de nascimento na mesma escala de confiança que o Titan já aplica a evidências e a parentesco: o dado vale conforme a sua origem, e a origem é consultável.

## Idade gestacional: opcional, com base declarada

A idade gestacional do aborto é **opcional**. Torná-la obrigatória forçaria alguém a inventar um número para passar pela validação, e dado inventado é pior que dado ausente.

Ausência significa literalmente `UNKNOWN` — nunca `0`, nunca estimativa fabricada. Quando conhecida ou estimada, viaja com a base de determinação:

```text
gestational_age_days   — o número, quando houver
gestational_age_basis  — KNOWN | ESTIMATED | UNKNOWN
```

**Classificações como aborto precoce ou tardio são derivadas por regra versionada, e nunca informadas como fato primário.** É o mesmo princípio que o Passo 9.4 aplicou à carência: gravar a derivação criaria segunda fonte de verdade, e ela divergiria da primeira no dia em que a regra mudasse. Sem idade suficiente, a classificação permanece indeterminada — sem impedir o registro do aborto.

## Fronteira com o Marco 16

`Pregnancy` **não** entra aqui. Ela pressupõe cobertura e diagnóstico de gestação, que são o Marco 16, e exigi-la travaria o Passo 13.3 esperando por ele. Pior: o rebanho real não colabora — na maioria das fazendas o parto é registrado sem que a cobertura tenha sido.

O `ReproductiveEvent` nasce sem `pregnancy_id` e ganha o vínculo, opcional, quando o Marco 16 chegar. A direção completa fica registrada:

```text
Pregnancy
    ↓
ReproductiveEvent
    ↓
BirthOutcome
    ├── offspring → Animal A
    └── offspring → Animal B

Animal
    ↓
LifeCycle
    ↓
Treatment / Weight / Lot / Transfer / Exit
```

A fronteira que isso cria é boa e vale nomear: **reprodução explica como o animal surgiu; ciclo de vida explica o que aconteceu com ele depois que passou a existir como indivíduo rastreável.** A reorganização de `LifeCycle` como camada explícita fica para decomposição própria.

## Um fato, duas histórias

O agregado do evento é o **próprio evento reprodutivo** — não a mãe, não a cria. É a entidade criada pela operação, e mãe e crias o enxergam por citação, exatamente como o Passo 13.2 fez com a relação de parentesco e como o log já faz com a movimentação.

```text
VACA 982
──────────────────────────────────────────────>
     inseminação   gestação       parto
                                  │
                         ┌────────┴────────┐
                         ▼                 ▼
                     BEZERRO A         BEZERRO B
                     vivo              natimorto
                         │
                         ▼
                    pesagem, vacinação, lote
```

A linha do tempo da mãe contém o parto; a do bezerro **começa** nele. Um mesmo fato conecta histórias de entidades diferentes sem ser duplicado — que é a propriedade que o modelo de proveniência do Titan existe para sustentar.

## Consequência de projeto

O nascimento passa a ser a **origem comprovável da identidade do animal**, e não um `birth_date` preenchido no cadastro. O cadastro avulso continua existindo para o rebanho legado, e é honesto sobre o que não sabe: `birth_outcome = NAO_INFORMADO`, `birth_property_source = DECLARED`.

## Alternativas descartadas

**Natimorto como `Animal` + `AnimalExit(MORTE)`.** Mais barata, e produz indicador errado — além de corromper o significado de saída do rebanho.

**Aborto criando `Animal` com status morto.** Fabrica entidade rastreável para um produto de gestação sem identidade atribuível.

**Parto gemelar como dois partos.** Perde o vínculo obstétrico entre irmãos, que é o que explica o natimorto no par.

**Exigir `Pregnancy` no parto.** Trava o passo no Marco 16 e recusa o caso majoritário do campo.

**Recusar o parto sem propriedade determinável.** Deixa de registrar um fato real por causa de um dado contextual ausente.

## Relacionadas

ADR-0011 (fontes normativas, vigência e reavaliação temporal), para a regra versionada que classifica o aborto. Passo 9.4, pelo princípio de que derivação não vira fato gravado. Passos 13.1 e 13.2, cujas decisões esta ADR estende sem contrariar.
