# ADR-0069 - Market Supply Intelligence como analise nao regulatoria

**Data:** 2026-08-28  
**Estado:** ACCEPTED  
**Escopo:** Titan Livestock, produto futuro

## Contexto

Sinais de mercado indicam demanda por visibilidade de capacidade de atendimento por mercado, janela comercial e gaps. O repositorio ja possui `MarketReadiness` derivado, coverage dimensional, `Evaluation`, `Decision`, Dossier e VerificationBundle.

`DOMAIN.md` confirma que o Core deve permanecer independente das verticais e que conceitos especificos pertencem a vertical enquanto nao houver evidencia de generalizacao. Tambem confirma que estimativa, premissa ou proxy nao podem ser apresentados como medicao, Decision ou reconhecimento externo.

## Problema

Implementar demanda comercial, forecast ou analise agregada sem fronteira aceita poderia confundir intencao comercial com Policy, previsao com Decision, readiness operacional com reconhecimento externo, e artefato analitico com Dossier regulatorio.

## Decisao

`Market Supply Intelligence` e uma camada analitica nao regulatoria de Titan Livestock.

Ela nao emite, redefine ou substitui:

- `Fact`;
- `Evidence`;
- `Policy`;
- `Rule`;
- `Evaluation`;
- `Decision`;
- certificado;
- autorizacao de exportacao;
- reconhecimento externo.

Ela pode consumir saidas canonicas existentes, mas nao altera sua semantica historica.

### CommercialDemand

`CommercialDemand` pertence inicialmente a Titan Livestock, nao ao Titan Core.

Ele representa intencao comercial da Organization compradora/frigorifico. Nao e Policy, Rule, Fact, Evidence, Evaluation, Decision, execucao contratual, reserva de animais, requisito regulatorio ou autorizacao de acesso a fornecedores.

A existencia de `CommercialDemand` nao concede acesso implicito a dados de produtores.

### Candidate Population

Candidate Population nao sera um Aggregate Root standalone na primeira implementacao.

A direcao aceita e:

```text
CandidatePopulationCriteria
        |
        v
PopulationResolver
        |
        v
CandidatePopulationSnapshot
```

`CandidatePopulationCriteria` preserva a base explicita para resolver sujeitos candidatos: Organization ou network scope, finalidade, Policy/versao, janela comercial, restricoes de sujeito, geografia, filtros operacionais/comerciais, restricoes de autorizacao, `reference_time` e `knowledge_cutoff`.

`PopulationResolver` e responsabilidade de aplicacao/analytics. Ele resolve somente sujeitos autorizados, respeita temporalidade historica, nao usa estado atual como historico, preserva inclusoes/exclusoes deterministicas quando possivel, e distingue inacessivel de desconhecido sem vazar dados protegidos.

`CandidatePopulationSnapshot` e preservado quando uma analise vira artefato historico ou compartilhado. Deve conter representacao imutavel suficiente para reproducibilidade, como criteria digest, `reference_time`, `knowledge_cutoff`, resolved/generated-at, Policy/versao, contagens incluidas/excluidas, resumo de exclusoes, proveniencia da populacao, referencia de autorizacao e digest canonico. O design nao exige que IDs individuais sejam armazenados em artefato visivel ao comprador.

### SupplyForecast

`SupplyForecast` e computado sob demanda por padrao.

Nao existe estado permanente mutavel de forecast. Um resultado pode ser transiente; snapshot imutavel so deve ser preservado quando necessario para reproducibilidade, relatorio compartilhado, auditoria historica ou artefato analitico explicito.

Direcao aceita:

```text
Forecast calculation
        |
        v
SupplyForecastResult
        |
        +--> transient only
        |
        +--> if historical/shared artifact is emitted
                |
                v
        SupplyForecastSnapshot
                |
                v
        SupplyIntelligenceReport
```

O forecast inicial deve ser deterministico, explicavel, assumption-aware, nao regulatorio e nao decisional. Nao usar ML/IA em CUT F.

Todo forecast deve preservar ou declarar `generated_at`, `reference_time`, `knowledge_cutoff`, horizonte/janela, Policy/versao, Candidate Population, premissas, versao das premissas, proveniencia, incerteza, gaps conhecidos e limitacoes.

Hipoteses de acao corretiva podem participar apenas como cenarios explicitos. Elas nunca mutam Fact, criam Evidence, criam Evaluation, criam Decision, reescrevem status historico ou afirmam que algo ja ocorreu.

### GapAnalysis

Nao havera motor comercial paralelo de gaps nem taxonomia normativa concorrente.

`GapAnalysis` deriva de material canonico existente, conforme aplicavel:

- `RuleResult`;
- status/reason;
- `missing_evidence_types`;
- CoverageAssessment;
- limitations de Evaluation;
- informacoes de gap de `MarketReadiness`;
- limitacoes de fonte/conhecimento;
- dados inacessiveis, desconhecidos ou conflitantes.

Ela pode agregar e explicar, mas nao reinterpretar resultados em um segundo modelo de verdade.

### SupplyIntelligenceReport

O nome aceito e `SupplyIntelligenceReport`.

Ele e artefato analitico separado. Nao e Dossier, VerificationBundle, certificado, Decision regulatoria, compromisso oficial de supply ou reconhecimento externo.

Semantica obrigatoria: analitico, nao regulatorio, nao decisional, temporally bounded, Policy-contextual, assumption-aware, authorization-aware e limitation-aware.

Modelo futuro deve avaliar campos como:

```text
report_id
generated_at
CommercialDemand snapshot/reference
CandidatePopulationSnapshot
Policy/version
MarketReadiness summary
GapAnalysis
optional SupplyForecastSnapshot
limitations
unknowns
assumptions
authorization context
provenance
canonical_hash
```

`SupplyIntelligenceReport` pode ser hashable/canonicamente identificavel no futuro, mas nao sera colocado dentro de `VerificationBundle` neste corte, nao vira Dossier e nao implica verificacao regulatoria.

## Alternativas

1. Reusar `MarketReadiness` e criar camada analitica Livestock separada.
2. Transformar readiness em atributo persistido do Animal.
3. Emitir forecast como `Decision` futura.
4. Promover `CommercialDemand` ao Core imediatamente.

## Justificativa

A alternativa 1 preserva as ADRs e invariantes existentes: `Policy != CommercialDemand`, `Evaluation != Decision`, `Projection != Decision`, readiness nao vira estado do Animal, e Core nao absorve conceito vertical prematuro.

As alternativas 2 e 3 violariam diretamente a separacao entre estado derivado, Evaluation, Decision e historico. A alternativa 4 generalizaria o Core sem evidencia de segunda vertical.

## Consequencias

- `CommercialDemand` e conceito Livestock ate nova evidencia.
- Supply analytics nao altera `Fact`, `Evidence`, `Policy`, `Rule`, `Evaluation`, `Decision`, Dossier ou VerificationBundle.
- Forecast deve ser on-demand por padrao e snapshot imutavel apenas quando houver artefato historico/compartilhado.
- Candidate Population precisa ser explicavel e reproduzivel sem expor membership individual a comprador por padrao.
- Gap comercial deriva de resultados canonicos.
- CUT F continua nao autorizado por esta ADR.

## Decisoes resolvidas nesta ADR

- Market Supply Intelligence e camada analitica nao regulatoria.
- `CommercialDemand` pertence inicialmente a Titan Livestock.
- `CommercialDemand` e owned pela Organization compradora/frigorifico.
- Candidate Population nao nasce como Aggregate Root standalone.
- Direcao `CandidatePopulationCriteria -> PopulationResolver -> CandidatePopulationSnapshot`.
- SupplyForecast e computed-on-demand por padrao.
- SupplyForecastSnapshot e imutavel quando preservado.
- Forecast inicial e deterministico e sem ML/IA.
- Acoes corretivas hipoteticas sao apenas premissas/cenarios.
- GapAnalysis deriva de material canonico existente.
- Nome `SupplyIntelligenceReport` aceito.
- SupplyIntelligenceReport e separado de Dossier/VerificationBundle.
- Nenhuma integracao oficial real e autorizada por esta ADR.

## Decisoes futuras

- Especificar contrato de implementacao de CUT F antes de qualquer BUILD.
- Decidir formato persistente concreto de `CommercialDemand`, se o corte aprovado exigir persistencia.
- Decidir formato tecnico de `CandidatePopulationSnapshot` e digest canonico.
- Decidir se `SupplyIntelligenceReport` sera arquivo, registro imutavel ou ambos.
- Decidir perfil de verificacao/hash publico para relatorios analiticos, sem misturar com Dossier.

Esta ADR aceita a arquitetura de produto, mas nao autoriza codigo, migration, API, worker, endpoint comercial ou CUT F.
