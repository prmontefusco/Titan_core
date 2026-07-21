# ADR 0012 — Sustentabilidade, materialidade, métricas e divulgações
**Status:** Aceita  
**Data:** 20 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan é uma plataforma de confiança para cadeias reguladas. Claims ambientais, sociais e de governança podem influenciar elegibilidade, risco, acesso a mercados, financiamento, auditoria e comunicação a stakeholders.

O Core já possui Source, Evidence, Provenance, Policy, Rule, Evaluation, Decision, Publication, AssertionType, AssertionScope, Dossier e Recall. Essas capacidades permitem sustentar informações de sustentabilidade, mas ainda não definem medição, limites, materialidade, metas, divulgação ou asseguração.

Governança técnica e de dados do Titan não equivale à dimensão de governança de sustentabilidade. Esta também pode abranger conduta empresarial, supervisão, ética, controles, riscos, conflitos de interesse, denúncias e remediação.

Referenciais como GRI, IFRS S1/S2, ESRS, TNFD, normas locais e protocolos contratuais possuem objetivos, materialidades, escopos e versões diferentes. O Titan não pode combiná-los silenciosamente nem produzir pontuação ESG universal.

## Problema

Definir:

- sustentabilidade transversal e fronteiras entre Core, vertical, perfil e Infrastructure;
- conformidade, desempenho, divulgação, medição, cálculo, limites, materialidade, metas e asseguração;
- versionamento, Provenance, limites das afirmações e relação com Recall.

## Princípios

1. **Evidência antes da alegação:** toda informação relevante preserva origem, método, escopo e limitações.
2. **Sem score universal:** resultado depende de finalidade, perfil, período e materialidade.
3. **Framework substituível:** referencial concreto não atravessa a fronteira genérica do Core.
4. **Dimensões separadas:** conformidade, desempenho, risco, impacto e divulgação não são sinônimos.
5. **Histórico imutável:** correção, metodologia ou fator novo não reescreve resultado publicado.
6. **Materialidade explícita:** tema omitido ou incluído possui avaliação, perfil e justificativa.
7. **Agregação explicada:** cobertura, estimativas, exclusões e dupla contagem são visíveis.
8. **Afirmação delimitada:** o Titan não declara que Organization ou produto “é sustentável”.
9. **Evolução incremental:** capacidade nasce com consumidor e teste reais; pacotes vazios são proibidos.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Módulo único `esg` | Descoberta simples | Mistura semânticas, frameworks, verticais e ownership |
| Campos E, S e G em Organization | Implementação rápida | Score implícito, baixa auditabilidade e evolução difícil |
| Modelo específico de um framework | Entrega direcionada | Acoplamento, versões e jurisdições incompatíveis |
| Capacidades genéricas e perfis versionados | Reuso, Provenance e múltiplos referenciais | Exige contratos e fronteiras rigorosos |

## Decisão

Adotar sustentabilidade como conjunto de capacidades transversais reutilizáveis, composto por medições, cálculos, limites, materialidade, metas, divulgações e asseguração, integrado aos conceitos existentes do Titan.

O Core fornece semântica genérica. Verticais definem tópicos, indicadores e regras concretas. Perfis versionados mapeiam informações para referenciais ou obrigações. Infrastructure integra fontes, fatores, sensores e ferramentas externas.

Não será criado pacote ou módulo monolítico chamado `esg` ou `compliance`. A organização física permanece a da ADR 0001 e evolui somente quando houver capacidade implementada.

Os conceitos desta ADR são candidatos arquiteturais. Sua inclusão na linguagem oficial depende de atualização aprovada do `DOMAIN.md`.

## Semânticas distintas

O Titan preserva a cadeia semântica:

```text
Measurement → CalculatedMetric → avaliação especializada
→ SustainabilityAssertion → SustainabilityDisclosure → Publication
```

AssuranceStatement pode avaliar escopo delimitado dessa cadeia. Measurement registra observação ou entrada; CalculatedMetric, resultado computado; avaliação especializada interpreta métricas; SustainabilityAssertion formula alegação autorizada; SustainabilityDisclosure reúne conteúdo versionado; Publication disponibiliza versão para audiência e finalidade. Nenhum é intercambiável.

Conformidade, desempenho, impacto, risco, oportunidade, divulgação e asseguração permanecem distintos. Medição íntegra pode demonstrar desempenho desfavorável; divulgação completa não comprova conformidade; conformidade não implica sustentabilidade geral.

## Natureza dos resultados

MetricNature classifica `ATIVIDADE`, `INSUMO`, `PRODUTO_DIRETO`, `RESULTADO`, `IMPACTO`, `RISCO`, `OPORTUNIDADE`, `CONFORMIDADE`, `COMPROMISSO`, `PROGRESSO` ou `EXPOSICAO`.

A natureza integra MetricDefinition e SustainabilityAssertion. Uma categoria não é convertida automaticamente em outra: atividade não prova impacto; ausência registrada não prova ausência de impacto; conformidade não prova desempenho superior; meta não prova progresso; progresso não prova atingimento; asseguração não prova sustentabilidade universal.

Alegação de impacto identifica se o método demonstra associação, atribuição ou causalidade. Correlação isolada não sustenta alegação causal.

## Fronteiras

**Titan Core:** pode conhecer MetricDefinition, Measurement, CalculationMethod, CalculatedMetric, ReportingBoundary, Baseline, Target, MaterialityAssessment, DisclosureProfile, SustainabilityDisclosure e AssuranceStatement, se aprovados no Domain.

Também reutiliza Claim, Source, Evidence, Provenance, NormativeReference, NormativeBasis, Policy, Rule, Evaluation, Decision, Publication, AssertionType e AssertionScope.

**Verticais:** definem tópicos, Subjects, unidades, indicadores, fatores, Rules, fontes, materialidade setorial e casos de uso. O Core não importa conceitos de vertical.

**Perfis:** DisclosureProfile versionado mapeia definições, disclosures, materialidade, períodos, limites, unidades, omissões, métodos, validações e alegações permitidas para referencial, jurisdição, contrato ou audiência.

**Infrastructure:** implementa fatores, bases, fontes, sensores, cálculo, armazenamento e formatos externos. Resposta externa não se torna Measurement verificada sem Application.

**Presentation:** apresenta período, limite, método, cobertura, Provenance, incerteza, perfil, lacunas e AssertionScope. Interface não transforma resultado técnico em selo, certificação ou alegação jurídica.

## Tópicos de sustentabilidade

SustainabilityTopic é classificação versionada dentro de perfil, não coluna fixa E, S ou G. Um tópico pode participar de mais de uma dimensão ou referencial.

Categorias ambientais, sociais ou de governança auxiliam organização e descoberta, mas não determinam materialidade, conformidade ou resultado.

Tópico de vertical não é promovido ao Core apenas por aparecer em framework externo.

## Métricas e medições

MetricDefinition define código, versão, natureza, propósito, grandeza, unidade, período, limites, metodologia, dados exigidos, qualidade, incerteza, agregação, arredondamento, Evidence e perfil.

Measurement registra Subject, Organization, período, instante, valor, unidade, ReportingBoundary, método de obtenção, ValueOrigin, Source, Actor, Evidence, Provenance, ValidationStatus, UncertaintyStatement, cobertura, limitações e versão da definição.

Valor sem unidade, período, limite ou definição versionada não é métrica publicável.

Unidade recebida é validada e convertida por regra versionada. Valor original, unidade original, conversão, precisão e arredondamento são preservados.

ValueOrigin distingue `MEDIDO`, `OBSERVADO`, `CALCULADO`, `ESTIMADO`, `MODELADO`, `PREMISSA`, `IMPORTADO` e `PROXY`. Origem da saída e composição das entradas permanecem separadas. Relatório apresenta cobertura por origem e nunca descreve estimativa como medição.

UncertaintyStatement registra tipo, origem, limites, confiança quando aplicável, distribuição ou método, propagação, sensibilidade, arredondamento e limitações. Tipos iniciais: `INCERTEZA_DE_MEDICAO`, `INCERTEZA_DE_MODELO`, `INCERTEZA_DE_FATOR`, `INCERTEZA_DE_COBERTURA`, `INCERTEZA_DE_CLASSIFICACAO`, `DESCONHECIDA`. O Titan não inventa intervalo probabilístico.

DataQualityAssessment avalia, conforme perfil, completude, atualidade, precisão, consistência, representatividade, rastreabilidade, validação, cobertura e proporção estimada. O Core não produz score universal de qualidade.

Lacuna usa razão controlada: `NAO_COLETADO`, `INDISPONIVEL`, `NAO_APLICAVEL`, `FORA_DO_ESCOPO`, `ACESSO_RESTRITO`, `FONTE_INDISPONIVEL` ou `METODOLOGIA_NAO_SUPORTADA`. Lacuna nunca é convertida em zero; omissão autorizada informa razão, efeito potencial e tratamento do perfil.

## Cálculos e fatores

CalculationMethod é imutável por versão e define fórmula, entradas, unidades, fatores, precedência, tratamento de ausência, estimativa, incerteza, arredondamento e saída.

CalculatedMetric preserva MetricDefinition, entradas e Digests, unidades, conversões, método, fatores, versões, ReportingBoundary, período, resultados intermediários necessários, arredondamento, ausências, estimativas, premissas, UncertaintyStatement, motor, tolerância, warnings, Actor e AssertionScope.

Fator externo registra Source, região, período, aplicabilidade, versão, unidade e Evidence. Atualização não recalcula nem substitui silenciosamente resultado anterior.

Reprodução confirma resultado equivalente dentro da tolerância declarada para material e método iguais. Não confirma verdade das entradas nem adequação científica ou jurídica. Componente novo produz simulação ou reavaliação, não reprodução histórica.

## Limites de reporte

ReportingBoundary delimita Organization, operações, Subjects, período, território, cadeia de valor, consolidação, inclusões, exclusões e critérios.

Limite organizacional, operacional, geográfico e de cadeia de valor são dimensões distintas. Ownership do registro não determina controle operacional, responsabilidade jurídica ou inclusão em relatório.

Mudança de limite cria nova versão e torna comparações condicionais. Série histórica pode ser reapresentada somente por operação explícita que preserve valores anteriores e justificativa.

## Agregação e dupla contagem

Agregação preserva componentes, Organizations de origem, unidades, conversões, limites, cobertura, estimativas, lacunas, qualidade e método.

O motor detecta, quando possível, interseção de Subject, período, origem ou escopo que possa gerar dupla contagem. Detecção produz warning ou resultado indeterminado conforme Policy; não elimina componente automaticamente.

Resultado agregado não concede Visibility sobre cada componente. Application calcula com dados autorizados e publica somente nível aprovado, preservando Evidence suficiente sem expor dados protegidos.

O Core não compensa ou normaliza tópicos heterogêneos em score único sem DisclosureProfile explícito. Quando permitido, método versionado preserva justificativa, pesos, ausências, limites, aprovação, sensibilidade e warnings; componentes não desaparecem no agregado.

## Baseline, meta e progresso

Baseline é referência versionada para comparação. Target define indicador, valor, unidade, período, limite, baseline, trajetória, responsável, aprovação, validade e perfil.

ProgressAssessment compara Measurements ou CalculatedMetrics com Target sob método identificado. Meta, desempenho observado, previsão e conclusão permanecem separados.

Alteração de baseline usa RebaseliningAssessment e cria RestatedBaseline correlacionada, preservando baseline anterior, motivo, diferença, método, período, objetos afetados e aprovação. Divulgações anteriores continuam ligadas à baseline original salvo republicação explícita.

Mudança de limite, método ou meta cria nova versão e informa comparabilidade. Meta não atingida não é NonConformity sem Policy que assim determine.

## Materialidade

MaterialityAssessment é avaliação versionada para tipo, perfil, tópico, stakeholders, Organization, cadeia de valor, período, método, thresholds, Evidence e aprovação declarados.

Pode avaliar materialidade de impacto, financeira, dupla, regulatória ou contratual. O tipo integra o contrato e não é convertido automaticamente em outro.

Preserva tópicos considerados, stakeholders e fontes consultados, impactos, riscos, oportunidades, critérios, thresholds, Evidence, conflitos, resultado, omissões, justificativas, Actor, aprovação e limitações.

Tema não material em um perfil pode ser material em outro. Ausência de Evidence suficiente resulta em `INDETERMINADA` ou revisão conforme Policy, não em omissão silenciosa.

## Comparabilidade

ComparabilityAssessment avalia compatibilidade de definição, natureza, limite, período, método, fatores, unidade, qualidade, cobertura, ValueOrigin, incerteza e ajustes.

Resultados: `COMPARAVEL`, `COMPARAVEL_COM_AJUSTES`, `PARCIALMENTE_COMPARAVEL`, `NAO_COMPARAVEL`, `INDETERMINADA`. Unidade e período iguais não bastam; diferenças de qualidade ou proporção estimada permanecem visíveis.

## Divulgação

SustainabilityDisclosure é snapshot imutável que identifica Organization, escopo, período, DisclosureAudience, canal, jurisdição, idioma, perfil, índice de conteúdo, SustainabilityAssertions, métricas, métodos, fatores, limites, baseline, Targets, progresso, cobertura, ValueOrigins, lacunas, omissões, incerteza, comparabilidade, aprovações, AssuranceStatements, Publication, Digests, correções e versões correlacionadas.

Toda divulgação preserva índice de conteúdo ou mapeamento exigido pelo perfil, versões utilizadas, Assertions, aprovações, Publication e Digest.

Dados atuais não reescrevem divulgação histórica. Correção, republicação ou novo período gera versão correlacionada e informa o que mudou.

DisclosureAudience distingue `INTERNA`, `CONTRATUAL`, `CLIENTE`, `AUDITOR`, `REGULATORIA` e `PUBLICA`. A mesma Assertion exige aprovação para cada audiência; acesso aos bytes não autoriza republicação.

Tradução cria Artifact correlacionado e preserva idiomas, tradutor ou processo, revisão, Digest, relação e versão prevalente definida pelo perfil.

LicenseConstraint registra titular ou provider, licença, usos, exportação, redistribuição, limite de citação, validade e restrições. Digest não concede licença; direito de armazenar não implica direito de redistribuir.

## Asseguração

AssuranceStatement registra provedor, identidade, competência, escopo, `assurance_standard`, versão, `assurance_level_code`, rótulo, tipo de conclusão, período, procedimentos, amostragem, material, limitações, relacionamento com o Subject, interesse financeiro, outros serviços, conflito declarado, base de independência, Signature, Evidence e instante.

Presença de Signature não comprova independência, competência ou nível de asseguração. Asseguração parcial não se apresenta como validação de toda a divulgação ou Organization.

Nível de asseguração só é interpretado no padrão e versão declarados. Independência é Assertion sustentada, não conclusão automática.

CertificationReference e CertificationStatus permanecem distintos de AssuranceStatement. Preservam esquema, titular, organismo, escopo, validade, auditoria, suspensão, uso de marca e Evidence. Certificação não comprova sustentabilidade universal.

## Afirmações de sustentabilidade

SustainabilityAssertion preserva AssertionType, SustainabilityAssertionKind e AssertionScope e identifica métrica, período, limite, perfil, método, Evidence, incerteza, omissões e aprovação.

SustainabilityAssertionKind distingue `RESULTADO_MEDIDO`, `RESULTADO_CALCULADO`, `CONFORMIDADE_METODOLOGICA`, `CONFORMIDADE_DA_DIVULGACAO`, `COMPROMISSO_DE_META`, `PROGRESSO_DA_META`, `ALEGACAO_COMPARATIVA`, `REFERENCIA_DE_ASSEGURACAO`, `REFERENCIA_DE_CERTIFICACAO` e `ALEGACAO_DE_IMPACTO`. Cada tipo exige material próprio; alegação comparativa exige ComparabilityAssessment e alegação de impacto exige método adequado.

O Titan pode declarar que resultado foi calculado ou divulgado conforme perfil e material registrados. Não declara automaticamente:

- que Organization, produto ou cadeia “é sustentável”;
- que informação atende todo framework ou jurisdição;
- que ausência de Evidence prova ausência de impacto;
- que desempenho favorável em um tópico compensa outro;
- que divulgação elimina risco de greenwashing;
- que asseguração implica verdade material universal.

Alegação comparativa exige baseline, população, período, unidade, limite e método equivalentes ou diferenças explicitamente ajustadas.

## Privacidade, autorização e isolamento

Métricas sociais, denúncias, força de trabalho, saúde, comunidades e dados de cadeia podem conter dados pessoais, sensíveis ou sigilosos. Implementação dessas capacidades depende da decisão de classificação e ciclo de vida de dados.

OrganizationContext, Permission, AuthorizationGrant, finalidade, Visibility, Publication e minimização são avaliados na coleta, cálculo, revisão, agregação, asseguração, exportação e divulgação.

Agregação ou pseudonimização não implica anonimização. Relatórios impedem inferência indevida de pessoa, comunidade, fornecedor ou Organization quando o escopo não autorizar.

## Correção, impacto e Recall

Correction, nova Evidence, fator, método, limite, perfil ou NormativeReference pode tornar métricas e divulgações `POTENCIALMENTE_AFETADAS`.

Motivo distingue `CORRECAO_DE_DADOS`, `ATUALIZACAO_DE_METODO`, `ATUALIZACAO_DE_FATOR`, `MUDANCA_DE_LIMITE`, `MUDANCA_DE_PERFIL`, `REESTABELECIMENTO_DE_BASELINE`, `NOVA_EVIDENCIA` e `ESTIMATIVA_SUBSTITUIDA`. Evolução científica não implica erro, fraude ou greenwashing anterior.

Análise por Provenance localiza Measurements, CalculatedMetrics, MaterialityAssessments, Targets, ProgressAssessments, Decisions, Dossiers, Publications e divulgações dependentes.

Impacto não invalida automaticamente artefato, não caracteriza fraude ou greenwashing e não inicia republicação, sanção ou recall. Cada efeito exige Policy, caso de uso e Actor competentes.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Sustentabilidade auditável; múltiplos perfis; cálculos reproduzíveis; comparação delimitada; integração com Recall |
| Negativas | Modelagem dimensional; curadoria de fatores; versões e licenças; privacidade; risco de alegações indevidas |

## Riscos e controles

| Risco | Controle |
|---|---|
| Score universal esconder contexto | Resultados por perfil, tópico e AssertionScope |
| Framework contaminar Core | Perfis e vertical por contratos públicos |
| Dupla contagem | Provenance, limites, componentes e warning explícito |
| Fator novo reescrever passado | Versões imutáveis e reavaliação correlacionada |
| Agregação expor dado protegido | Authorization, limiar e minimização |
| Relatório virar certificado | Divulgação e asseguração separadas |
| Greenwashing automatizado | Alegações permitidas, Evidence e limitações |
| Conteúdo licenciado redistribuído | Referência e política de licença |

## Verificação automatizada

Testes futuros devem cobrir:

- atividade ou correlação apresentada indevidamente como impacto causal;
- estimativa, proxy ou premissa apresentada como medição;
- lacuna convertida em zero, omissão sem razão ou cobertura parcial como integral;
- métricas de mesmo nome com definições, unidades ou períodos incompatíveis;
- cálculo, conversão, fator, tolerância e incerteza reproduzíveis;
- materialidades distintas e baseline restabelecida sem apagar a anterior;
- comparação com limites, métodos, qualidade ou ValueOrigins incompatíveis;
- score ou compensação entre tópicos sem perfil aprovado;
- audiência alterada, tradução divergente ou conteúdo licenciado redistribuído;
- assegurador com conflito, nível sem padrão ou certificação expirada como vigente;
- simulação, correção e impacto potencial sem alterar história ou iniciar Recall;
- isolamento, inferência por agregação e conteúdo de vertical ausente do Core.

## Critérios de aceitação

A ADR pode ser aceita quando:

- cadeia separar Measurement, CalculatedMetric, avaliação, Assertion, Disclosure, Publication e asseguração;
- atividade, produto direto, resultado, impacto, risco, conformidade, meta e progresso não forem confundidos;
- ValueOrigin identificar medições, estimativas, modelos, premissas e proxies;
- lacuna nunca significar zero e omissão permanecer explicada;
- métrica e cálculo preservarem definição, limite, método, fatores, versões, Provenance e incerteza;
- materialidade indicar tipo, perfil, período, escopo, Evidence e aprovação;
- rebaselining criar RestatedBaseline correlacionada sem reescrever a original;
- comparação avaliar método, limite, período, qualidade, cobertura e incerteza;
- qualidade e compensação dependerem de perfil sem score universal do Core;
- divulgação identificar audiência, canal, idioma, cobertura, lacunas e licença;
- tradução criar Artifact correlacionado e versão prevalente explícita;
- asseguração registrar padrão, nível, conflitos e independência declarada;
- certificação permanecer distinta e validade não ser presumida;
- alegação causal exigir método adequado e AssertionScope;
- privacidade, Authorization, impacto potencial e independência das verticais forem preservados.

## O que esta ADR não decide

Esta ADR não escolhe:

- indicador, cálculo, fator, método, regra, entidade ou fluxo concreto de vertical;
- framework obrigatório, obrigação jurídica, certificação, score, selo ou benchmark;
- persistência, pacote, API, interface, fonte, provider, sensor ou ferramenta;
- retenção, privacidade ou localização de dados.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída por nova ADR. Depois da adoção, mudança de conceito ou perfil preserva definições, medições, métodos, fatores, limites, avaliações, metas, divulgações, assegurações e relatórios históricos. Migração cria versões correlacionadas e nunca reescreve alegação publicada.
