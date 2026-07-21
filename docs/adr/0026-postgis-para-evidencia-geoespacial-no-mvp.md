# ADR 0026 — PostGIS para evidência geoespacial no MVP

**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan Livestock pretende atender exportadores, frigoríficos e seus fornecedores em cadeias sujeitas a obrigações ambientais e de rastreabilidade. O go-to-market prioriza o comprador que precisa reconstruir fornecedores diretos e indiretos, declarar lacunas e produzir dossiê verificável.

A EUDR inclui produtos bovinos. O texto vigente exige informação sobre os estabelecimentos onde os animais foram mantidos. As datas atuais de aplicação são 30 de dezembro de 2026 para operadores que não sejam micro ou pequenas empresas e 30 de junho de 2027 para a maioria das micro e pequenas empresas.

A ADR 0003 adotou PostgreSQL como banco transacional e deixou PostGIS fora do escopo inicial, exigindo passo e migration próprios para eventual ativação. A estratégia comercial revista torna a localização uma evidência necessária no caminho crítico do MVP.

O Titan, contudo, não pretende substituir plataformas especializadas, sensoriamento remoto, bases governamentais ou análise territorial profissional. Integridade de uma geometria não comprova exatidão material, titularidade, regularidade ambiental ou conformidade jurídica.

## Problema

Definir se e como o MVP deve:

- armazenar localizações e limites espaciais de forma validável;
- preservar origem, versão e limitações de geometrias;
- relacionar estabelecimentos e movimentos da cadeia bovina;
- comparar geometrias com camadas externas versionadas;
- produzir resultados espaciais explicáveis e reproduzíveis;
- manter isolamento por Organization e autorização por finalidade;
- evitar transformar o Titan em plataforma GIS genérica.

## Princípios

1. **Geometria é evidência, não verdade automática:** formato válido e interseção calculada não comprovam legitimidade da fonte ou conclusão jurídica.
2. **Proveniência obrigatória:** toda geometria relevante preserva Source, método, instante, versão, precisão, Evidence e limitações.
3. **Resultado delimitado:** uma avaliação espacial vale somente para geometrias, camadas, versões, método, instante e finalidade declarados.
4. **Separação de responsabilidades:** PostGIS executa armazenamento, validação e relações espaciais; Application decide admissibilidade e coordena Policies.
5. **Isolamento por Organization:** extensão espacial não cria caminho alternativo à Authorization ou à RLS.
6. **Interoperabilidade:** entrada e saída usam perfis versionados e formatos documentados.
7. **Escopo mínimo:** somente capacidades necessárias ao incremento comercial atual são implementadas.
8. **Desconhecido permanece desconhecido:** ausência, baixa precisão ou cobertura incompleta não se convertem em aprovação.

## Alternativas consideradas

### 1. Manter PostGIS fora do MVP

**Vantagens:** menor infraestrutura e nenhuma especialização espacial inicial.

**Desvantagens:** localização ficaria como texto ou JSON sem constraints e índices espaciais; comparação territorial dependeria integralmente de terceiros e dificultaria reprodução e auditoria.

### 2. Armazenar GeoJSON sem PostGIS

**Vantagens:** formato interoperável e implementação aparentemente simples.

**Desvantagens:** validação topológica, SRID, consultas, índices e relações espaciais teriam de ser implementados ou duplicados fora do banco.

### 3. Adotar plataforma geoespacial externa como autoridade do Titan

**Vantagens:** acesso imediato a análises maduras e bases especializadas.

**Desvantagens:** lock-in, custo, dependência de contrato, perda de reprodutibilidade e risco de confundir conclusão externa com decisão do Titan.

### 4. Ativar PostGIS com escopo vetorial mínimo e providers externos substituíveis

**Vantagens:** constraints, índices e operações espaciais no banco transacional já aprovado, preservando integração com análises especializadas.

**Desvantagens:** migrations e testes mais complexos; exige disciplina de SRID, precisão, topologia, desempenho e autorização.

## Decisão

Ativar **PostGIS no PostgreSQL do Titan** e colocá-lo no caminho crítico do MVP para evidência geoespacial vetorial.

Esta ADR substitui somente a decisão da ADR 0003 que mantinha PostGIS fora do escopo inicial. Permanecem vigentes PostgreSQL, schemas por módulo, migrations, papéis separados, `RecordOwnerOrganization`, RLS, contexto transacional e demais controles da ADR 0003.

PostGIS pertence à Infrastructure. Tipos SQL, funções `ST_*`, índices GiST e detalhes do provider não atravessam a fronteira para Domain.

A Application solicita uma relação espacial conceitual e recebe resultado normalizado. O adapter registra a operação técnica efetivamente executada, mas não transforma nomes do PostGIS em regra de negócio.

## Contratos conceituais

### SpatialOperationProfile

Perfil imutável e versionado que delimita:

- proposição espacial suportada;
- tipo `geometry` ou `geography` utilizado pela Infrastructure;
- SRID, ordem dos eixos e dimensionalidade;
- predicado espacial e justificativa semântica;
- tolerância e modelo de precisão;
- transformações admitidas;
- limites de complexidade e orçamento de execução;
- versões relevantes do PostgreSQL, PostGIS, GEOS e PROJ;
- versão da migration e do adapter.

`ST_Intersects`, `ST_Contains`, `ST_Covers`, `ST_Within`, `ST_Overlaps` e `ST_Touches` não são equivalentes. O perfil escolhe o predicado que responde à proposição avaliada e define o comportamento esperado em bordas, buracos, coleções e geometrias de dimensões diferentes.

Trocar `geometry` por `geography`, predicado, SRID, tolerância, dimensionalidade ou modelo de precisão é mudança semântica e exige nova versão do perfil.

### SpatialAssessment

Avaliação imutável que preserva:

- proposição espacial explicitamente avaliada;
- representações e versões utilizadas;
- SpatialOperationProfile;
- camada e versão de referência;
- temporalidades aplicáveis;
- SpatialCoverageAssessment;
- resultado e ReasonCodes;
- Evidence, limitações e versão do executor.

Resultado positivo ou negativo sempre qualifica a proposição declarada. Não representa conformidade, irregularidade, causalidade ou verdade universal.

### SpatialCoverageAssessment

Avalia separadamente cobertura:

- geográfica;
- temporal;
- temática;
- de resolução;
- de precisão;
- de identidade;
- de disponibilidade;
- da cadeia de estabelecimentos.

Cobertura suficiente em uma dimensão não supre outra. Cobertura nacional não compensa período incompatível; atualidade não compensa resolução inadequada.

## Escopo mínimo do MVP

O MVP pode implementar incrementalmente:

- ponto de estabelecimento ou local de manutenção de animais;
- polígono de propriedade, estabelecimento ou área declarada quando houver fonte adequada;
- importação de GeoJSON ou formato aprovado;
- validação de tipo, SRID, dimensões, coordenadas, validade geométrica e limites de tamanho;
- normalização controlada para WGS 84 (`SRID 4326`) sem descartar a representação original;
- índice espacial GiST para padrões de consulta comprovados;
- relações como interseção, contenção, cobertura, proximidade e não interseção;
- vinculação temporal entre animal, estabelecimento, movimento e geometria versionada;
- comparação com camada externa imutável ou snapshot identificado;
- avaliação de cobertura, precisão, conflito e lacunas;
- exportação interoperável acompanhada de Provenance e limitações.

Cada capacidade entra somente quando possuir caso de uso, consumidor, Policy, teste e critério de aceite atuais.

## Fora do escopo

Esta decisão não autoriza:

- plataforma GIS genérica;
- editor cartográfico completo;
- sensoriamento remoto próprio;
- classificação automática de cobertura vegetal ou desmatamento;
- processamento massivo de raster;
- cópia indiscriminada de bases governamentais ou comerciais;
- substituição de CAR, MapBiomas, PRODES, Agrotools, Niceplanet ou autoridade competente;
- declaração automática de conformidade ambiental ou EUDR;
- inferência de ownership jurídico a partir de coordenadas;
- mapa público ou compartilhamento entre Organizations sem autorização.

Raster, tiles, geocodificação, roteamento, imagens de satélite e análise geodésica avançada exigem necessidade comprovada e decisão própria.

## Representação e precisão

A Infrastructure utiliza `geometry` com SRID explícito como representação vetorial inicial. A escolha de `geography`, projeção local ou transformação adicional depende da operação e deve ser justificada por perfil técnico versionado.

As representações são distinguidas conceitualmente:

- `SourceGeometry`: material exatamente como recebido;
- `NormalizedGeometry`: serialização canônica sem alteração material declarada;
- `TransformedGeometry`: mudança de SRID, precisão ou outra transformação;
- `OperationalGeometry`: representação preparada, simplificada ou subdividida para uma operação autorizada.

Relações entre representações declaram `EQUIVALENTE_DECLARADA`, `TRANSFORMADA`, `SIMPLIFICADA`, `REPARADA` ou `DERIVADA`. Validade estrutural não comprova equivalência material.

Regras:

- coordenadas sem sistema de referência conhecido são rejeitadas ou permanecem não admissíveis;
- transformação preserva referência ao material original e ao método utilizado;
- arredondamento, simplificação, correção topológica e redução de precisão são transformações registradas;
- geometria inválida não é corrigida silenciosamente;
- geometria reparada é novo derivado e nunca substitui o original;
- reparo registra método, versão, parâmetros, diferenças, justificativa e limitações;
- simplificação, snapping, redução de precisão e subdivisão registram tolerância, finalidade, Digest e relação com o original;
- precisão declarada não é apresentada como precisão observada;
- ponto não é promovido a polígono nem interpretado como limite cadastral;
- geometria atual não substitui versão histórica usada por avaliação anterior.

## Proveniência e confiança

Toda geometria relevante preserva ou referencia:

- identificador e versão;
- objeto e período aos quais se aplica;
- `RecordOwnerOrganization`;
- Source e SourceSnapshot;
- Actor ou processo responsável pela captura ou importação;
- formato, SRID e representação original;
- transformação e parser utilizados;
- precisão, resolução ou escala conhecida;
- Digest do material de origem;
- ValidationAssessment e ConfidenceAssessment;
- licença, finalidade, retenção e restrições de compartilhamento;
- limitações, lacunas e conflitos.

Localização declarada, documental, observada por dispositivo, importada de fonte oficial e derivada por cálculo permanecem semanticamente distintas.

## Camadas externas

Uma camada externa é utilizada somente por adapter aprovado e contrato versionado. Cada importação ou consulta preserva provider, versão do contrato, instante, cobertura, licença, request/response Digests, freshness e limitações.

Comparação reproduzível utiliza snapshot imutável, versão identificada ou Evidence suficiente para recuperar o material autorizado. Referência ao estado mutável atual de uma fonte não reproduz avaliação histórica.

Confirmação do provider é Evidence externa. O Titan não a converte automaticamente em verdade material, oficialidade ou conclusão jurídica.

## Avaliação espacial

Uma SpatialAssessment registra:

- geometrias e versões utilizadas;
- camada e versão de referência;
- proposição avaliada, operação espacial e SpatialOperationProfile;
- SRIDs e transformações;
- instante de referência;
- SpatialCoverageAssessment e precisão disponíveis;
- resultado, ReasonCodes, Evidence e limitações;
- versões de PostgreSQL, PostGIS, GEOS, PROJ, migration, adapter e perfil relevantes.

Resultados iniciais distinguem `RELACAO_DETECTADA`, `RELACAO_NAO_DETECTADA`, `CONFLITANTE`, `COBERTURA_INSUFICIENTE`, `FONTE_INDISPONIVEL` e `INDETERMINADA` conforme o caso de uso e a linguagem pública aprovada.

`RELACAO_NAO_DETECTADA` somente é emitida quando a operação foi concluída adequadamente e possui cobertura suficiente para a proposição declarada. Ausência de confirmação por cobertura, precisão, identidade, temporalidade, conflito ou indisponibilidade produz o resultado limitado correspondente.

`ST_Intersects = false` prova somente que as representações avaliadas não se intersectaram sob o perfil declarado. Não prova ausência universal de sobreposição, desmatamento, embargo, irregularidade ou risco.

Resultado falso de predicado espacial comprova somente a relação computada entre as representações identificadas. Predicado negativo não comprova ausência material ou jurídica do fenômeno representado.

Comparação de bounding boxes é pré-filtro de candidatos e não constitui resultado geométrico final. Bounding boxes podem se interceptar enquanto as geometrias permanecem disjuntas.

## Temporalidade espacial

Uma operação preserva separadamente:

- período de validade da geometria;
- instante de observação;
- instante de publicação da fonte;
- instante de ingestão;
- instante da avaliação;
- vigência própria da camada ou condição representada.

Camadas ou geometrias de períodos incompatíveis não são combinadas sem avaliação explícita. Conhecimento atual não reinterpreta silenciosamente SpatialAssessment histórica.

Para cadeia bovina, cobertura pode considerar as permanências materiais do animal e as referências geográficas dos respectivos estabelecimentos. Um único ponto ou somente o estabelecimento final não comprova cobertura da cadeia completa.

## Segurança e isolamento

Tabelas espaciais protegidas seguem integralmente a ADR 0003:

- `RecordOwnerOrganization` obrigatório;
- `ENABLE ROW LEVEL SECURITY` e `FORCE ROW LEVEL SECURITY`;
- runtime sem superuser, ownership ou `BYPASSRLS`;
- contexto local à transação;
- grants mínimos por operação;
- nenhuma função `SECURITY DEFINER` sem decisão específica;
- resposta não distingue objeto inexistente de geometria invisível;
- índices e planos de execução não autorizam acesso cross-Organization.

Bounding boxes, centroids, tiles, hashes, métricas e resultados derivados também podem revelar localização protegida e permanecem sujeitos a classificação, FieldScope, Purpose e DataContract.

A autorização para receber resultado espacial derivado considera o risco de reconstrução da geometria de origem. Consultas repetidas com geometrias arbitrárias podem constituir sondagem espacial.

Controles incluem Purpose específico, granularidade mínima, rate limiting, limites de formas fornecidas pelo cliente, respostas não diferenciáveis quando apropriado, agregação, auditoria e detecção de padrão. Funções auxiliares, views, materializações, tabelas temporárias, planos preparados e execução paralela não podem contornar RLS.

## Desempenho

Índices espaciais são criados somente para consultas comprovadas. Operações devem usar predicados compatíveis com índice quando aplicável, limites de complexidade, paginação e proteção contra payloads excessivos.

Testes confirmam que consultas críticas permanecem dentro do orçamento aprovado e usam índice espacial quando essa for a estratégia esperada para cardinalidade e distribuição representativas. Não se exige um operador específico do planner como regra de correção.

O orçamento considera tempo, memória, linhas e candidatos examinados, vértices, tamanho serializado, profundidade de coleções, quantidade de partes e camadas e ausência de explosão cartesiana.

Geometria estruturalmente válida ainda pode ser operacionalmente hostil. Timeout, quotas, bulkhead e limites são aplicados antes da execução dispendiosa. Subdivisão ou simplificação exige transformação autorizada e equivalência demonstrada para a operação.

## Consequências

### Positivas

- evidência espacial integra o banco transacional e a auditoria já aprovados;
- relações espaciais tornam-se consultáveis e reproduzíveis;
- o MVP atende melhor à cadeia de estabelecimentos exigida pelo posicionamento EUDR;
- providers especializados permanecem substituíveis;
- localização participa de Provenance, Decisions e Dossiers sem virar conclusão automática.

### Negativas

- ambiente e migrations passam a depender da extensão PostGIS;
- testes exigem PostgreSQL real com extensão compatível;
- geometrias malformadas ou complexas podem elevar custo e latência;
- projeções, precisão e topologia exigem conhecimento técnico específico;
- backup, restore e portabilidade precisam incluir a extensão e suas versões.

## Riscos e controles

| Risco | Controle |
|---|---|
| Geometria íntegra apresentada como verdadeira | Provenance, ValidationAssessment e linguagem delimitada |
| Interseção apresentada como infração | Assessment separado da Decision e da conclusão jurídica |
| Bounding box apresentada como interseção real | Separar pré-filtro candidato do predicado exato |
| SRID incorreto produzir resultado falso | SRID obrigatório, transformação versionada e testes conhecidos |
| Correção topológica alterar evidência | Original preservado e transformação explícita |
| Simplificação alterar relação espacial | Derivado versionado, tolerância e comparação com o original |
| `geometry` trocada por `geography` silenciosamente | SpatialOperationProfile versionado |
| Vazamento entre Organizations | RLS, Authorization, FieldScope e testes negativos espaciais |
| Resultado booleano permitir reconstrução | Purpose, granularidade, rate limit, auditoria e detecção de sondagem |
| Camada externa mudar depois da decisão | Snapshot ou versão imutável identificada |
| Camadas de períodos incompatíveis serem combinadas | SpatialCoverageAssessment temporal |
| Feature duplicada alterar contagem | Identidade, deduplicação e limitação declarada |
| Consulta espacial degradar o banco | GiST, limites, planos de execução e métricas |
| Geometria complexa exaurir recursos | Quotas, timeout, limites, bulkhead e transformação aprovada |
| Upgrade alterar fixture conhecida | Versões preservadas e testes comparativos |
| Titan competir com plataforma GIS madura | Escopo vetorial mínimo e providers especializados |
| Licença impedir redistribuição | LicenseConstraint e exportação por componente |
| Ausência de dados virar aprovação | Resultado indeterminado ou cobertura insuficiente |

## Testes mínimos

- extensão ausente impede migration de forma explícita;
- SRID ausente ou incompatível é rejeitado;
- latitude, longitude, tipo e dimensões inválidos são rejeitados;
- geometria inválida não é corrigida silenciosamente;
- original e transformação possuem Digests e relação preservados;
- ponto não é tratado como polígono;
- predicados distintos usam casos conhecidos de borda, toque, contenção, sobreposição e buracos;
- bounding boxes se cruzam enquanto geometrias permanecem disjuntas;
- ponto sobre borda produz o resultado definido pelo predicado escolhido;
- troca entre `geometry` e `geography` exige nova versão de perfil;
- ordem de eixos invertida e datum incompatível são detectados;
- simplificação estreita não pode eliminar interseção silenciosamente;
- reparo topológico não substitui o original;
- camada versionada diferente produz avaliação distinta;
- camada geograficamente completa e temporalmente incompatível não produz cobertura suficiente;
- features duplicadas não são tratadas silenciosamente como fenômenos independentes;
- camada indisponível produz resultado limitado, não aprovação;
- consulta crítica respeita orçamento e estratégia de índice esperada para dados representativos;
- geometria válida com complexidade excessiva é limitada;
- geometria de outra Organization permanece invisível;
- bounding box ou centroide não contorna FieldScope;
- sondagem booleana repetida é limitada e auditada;
- função auxiliar, view, prepared statement ou execução paralela não contorna RLS;
- avaliação histórica continua usando a geometria e camada originais;
- upgrade de PostGIS, GEOS ou PROJ executa fixtures comparativas;
- restore recria extensão, índices, constraints, views e RLS antes de validar equivalência;
- exportação preserva tipo, CRS, ordem de eixos, dimensionalidade, precisão, encoding, Digests, cadeia de transformação, versões, temporalidade, cobertura, licença, Provenance e limitações;
- resultado espacial não emite decisão jurídica automaticamente.

## Invariantes adicionais

- todo resultado identifica proposição, representações, versões, predicado, SRID, precisão, cobertura e limitações;
- predicado negativo não comprova ausência universal do fenômeno;
- bounding-box filtering não é resultado espacial final;
- mudança de tipo espacial, SRID, precisão, simplificação ou reparo cria nova representação ou perfil;
- derivado espacial preserva restrições de acesso e risco de inferência da origem;
- índice melhora execução, mas não altera autorização, precisão ou semântica;
- cobertura geográfica, temporal, temática, de identidade e da cadeia são independentes;
- upgrade do motor não reinterpreta SpatialAssessments históricos;
- operação espacial calcula relação; Decision autorizada determina eventual significado de negócio.

## Critérios de aceitação

A ADR pode ser aceita quando:

- substituir somente a exclusão inicial de PostGIS da ADR 0003;
- PostGIS permanecer detalhe de Infrastructure;
- SpatialOperationProfile preservar a semântica técnica versionada;
- SpatialAssessment identificar a proposição avaliada;
- escopo vetorial mínimo estiver separado de análise ambiental própria;
- localização declarada, observada, importada e derivada permanecer distinta;
- original, SRID, transformação, precisão e Provenance forem preservados;
- camadas externas forem versionadas ou reproduzíveis;
- cobertura geográfica, temporal, temática e da cadeia for avaliada separadamente;
- RLS e Authorization cobrirem dados e derivados espaciais;
- resultado desconhecido ou cobertura insuficiente não virar aprovação;
- avaliação espacial não for confundida com conformidade jurídica;
- testes de isolamento, correção e desempenho estiverem previstos;
- sondagem espacial e derivados reveladores estiverem controlados;
- raster, sensoriamento remoto e GIS genérico permanecerem fora do escopo.

## Plano de implementação incremental

1. fixar versões compatíveis de PostgreSQL e PostGIS no passo de infraestrutura;
2. ativar a extensão por migration autorizada;
3. testar backup, restore e migration em banco descartável;
4. introduzir o primeiro armazenamento espacial somente junto ao caso de uso da vertical;
5. criar índice e operação espacial apenas para consulta comprovada;
6. integrar primeiro provider externo por contrato substituível;
7. produzir avaliação e relatório com Evidence, cobertura e limitações;
8. medir custo e desempenho antes de ampliar tipos ou operações.

## Plano de reversão

Antes da primeira coluna espacial, a decisão pode ser revertida por nova ADR e remoção da extensão do ambiente.

Depois da persistência, a reversão exige exportação interoperável com SRID e Provenance, comprovação de equivalência das operações necessárias, migration versionada, validação de Digests e preservação das avaliações históricas. Remover a extensão não autoriza descartar geometrias, camadas ou Evidence já utilizadas.

## Referências

- [Regulamento (UE) 2023/1115 — texto e requisitos de geolocalização](https://eur-lex.europa.eu/legal-content/en/ALL/?uri=CELEX%3A32023R1115), consultado em 21 de julho de 2026.
- [Regulamento (UE) 2025/2650 — alteração e datas de aplicação](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32025R2650), consultado em 21 de julho de 2026.
- [Regulamento (UE) 2023/1115 — versão consolidada de 26 de dezembro de 2025](https://eur-lex.europa.eu/eli/reg/2023/1115/2025-12-26/eng), consultado em 21 de julho de 2026.
- [PostGIS — `ST_Intersects`](https://postgis.net/docs/ST_Intersects.html), consultado em 21 de julho de 2026.
- [PostGIS — índices espaciais](https://postgis.net/documentation/faq/spatial-indexes/), consultado em 21 de julho de 2026.
- [PostGIS — escolha entre geometry e geography](https://postgis.net/documentation/faq/geometry-or-geography/), consultado em 21 de julho de 2026.
