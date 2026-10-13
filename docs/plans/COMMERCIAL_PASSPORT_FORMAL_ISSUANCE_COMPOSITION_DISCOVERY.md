# Commercial Passport — Discovery da composição de emissão formal

**Data:** 2026-10-13  
**Estado:** DECISION REQUIRED  
**Resultado da Discovery:** não iniciar BUILD antes da decisão de produto/domínio  
**Motivação:** o Product Owner decidiu concluir a implementação antes da homologação da Opção B

## Problema

A rota de emissão formal existe, mas permanece fail-closed porque
`get_commercial_passport_issuance_pipeline()` retorna `None`. A camada de aplicação já possui
`CommercialPassportFormalIssuanceService`, que congela uma projection, persiste um `Dossier` e gera um
`VerificationBundle`.

O gap não é simplesmente instanciar esse serviço. O `DossierService` exige uma única tríade coerente:

- `Decision`;
- `Evaluation`;
- `Policy`.

O Commercial Passport pode conter várias oportunidades comerciais. A pipeline dinâmica atual parte de
`MarketReadinessReport` e não define qual `Decision` deve ancorar uma emissão que agrega oportunidades.
Escolher silenciosamente uma decisão, fabricar uma decisão ou emitir um dossiê sem a tríade violaria os
contratos existentes e a filosofia do Titan.

## Usuário e resultado desejado

O operador interno quer emitir um artefato verificável de um Commercial Passport previamente calculado,
preservando exatamente quais avaliações, decisões e policies sustentaram o conteúdo, sem apresentar o
artefato como autorização de exportação, certificado público ou decisão regulatória.

## Evidência no repositório

- `PropertyCommercialPassportIssuancePort` já define a porta HTTP da emissão;
- `CommercialPassportFormalIssuanceService.issue()` exige explicitamente `passport`, `decision`,
  `evaluation`, `policy`, audiência e instante de emissão;
- o serviço recusa `Decision` de outra Organization ou cujo sujeito não seja a propriedade;
- `DossierService.build_and_store()` preserva uma única Decision/Evaluation/Policy e exige repositório;
- `TransactionalDossierRepository` persiste o snapshot append-only sob RLS;
- `VerificationBundleService` já empacota o Dossier e o interpretador Livestock declara o escopo
  `commercial_passport_snapshot`;
- a rota e os testes HTTP usam stub para provar o contrato, mas não resolvem material autoritativo real;
- a consulta dinâmica atual pode agregar oportunidades, mas sua composição configurada usa uma única
  oportunidade por processo.

## Invariantes aplicáveis

1. Um artefato formal não pode inventar Decision, Evaluation, Policy ou fundamento normativo.
2. A Decision deve pertencer à mesma Organization e ter a propriedade como sujeito.
3. A versão da Policy e o contexto temporal devem corresponder ao material congelado.
4. Consulta dinâmica e emissão formal continuam operações distintas.
5. A emissão não concede acesso externo nem substitui `AuthorizationGrant`.
6. O snapshot deve permanecer reproduzível depois de novos dados ou decisões.
7. Falta ou ambiguidade de material autoritativo resulta em negação, não em seleção heurística.

## Opções

### A — uma emissão formal por oportunidade e por Decision

A requisição identifica a oportunidade. A pipeline reconstrói o Passport apenas para essa oportunidade e
resolve uma única Decision/Evaluation/Policy coerente da propriedade e do contexto temporal.

Vantagens:

- encaixa no contrato atual do Dossier sem alterá-lo;
- vínculo de autoridade inequívoco;
- menor incremento e rollback simples;
- várias oportunidades podem ser emitidas separadamente.

Trade-offs:

- não produz um único artefato formal multi-oportunidade;
- exige definir como resolver a Decision aplicável sem usar “última decisão” de forma ambígua;
- pode exigir nova entrada no request HTTP para selecionar a oportunidade.

### B — emissão multi-oportunidade com um Dossier por oportunidade

Uma solicitação gera vários Dossiers/VerificationBundles, um para cada oportunidade com material
autoritativo válido.

Vantagens:

- preserva o modelo atual de Dossier;
- permite operação em lote sem misturar autoridades.

Trade-offs:

- muda significativamente o contrato de resposta e a atomicidade;
- precisa decidir comportamento quando apenas parte das oportunidades é emitível;
- maior complexidade operacional e de idempotência.

### C — estender o Core para Dossier ancorado em múltiplas Decisions

Criaria semântica transversal nova no Core.

Rejeitada nesta Discovery: não existe segundo consumidor comprovado; alteraria contrato, domínio e
persistência do Core e seria decisão arquitetural RED com ADR própria.

### D — emitir artefato informativo sem Decision/Evaluation/Policy

Rejeitada: enfraquece o `Dossier`, cria um segundo significado para o mesmo artefato e contradiz o modelo
de evidência → avaliação → decisão → dossiê.

## Recomendação

**Opção A:** emissão formal de uma única oportunidade, ancorada em uma única tríade
Decision/Evaluation/Policy previamente persistida e temporalmente compatível.

O primeiro corte deve aceitar somente uma oportunidade interna controlada. Mercados reais permanecem fora
até possuírem `NormativeBasis` e regras governadas revisadas. A ausência de uma tríade exatamente
compatível deve responder fail-closed sem persistir Dossier ou bundle.

## Questões que a decisão deve fechar

1. A oportunidade será selecionada pelo código configurado no servidor ou explicitamente na requisição?
2. Qual relação persistida prova que uma Decision/Evaluation corresponde à oportunidade do Passport?
3. Em caso de mais de uma Decision temporalmente elegível, qual regra determinística seleciona a correta?
4. A primeira emissão fica restrita a oportunidade sintética/interna?
5. É necessária idempotência explícita no POST antes da primeira exposição em homologação?

## Próxima etapa se PROCEED

Criar uma SPEC para um único corte contendo:

- contrato de seleção da oportunidade;
- resolução determinística e owner-scoped da tríade autoritativa;
- composição transacional do `CommercialPassportFormalIssuanceService`;
- recusa atômica para material ausente, ambíguo ou incompatível;
- testes positivos, negativos, autorização, isolamento, concorrência/idempotência e rollback;
- atualização do roteiro executável para confirmar emissão real e consulta posterior do Dossier/bundle.

Nenhuma feature flag será ligada como parte desse BUILD.
