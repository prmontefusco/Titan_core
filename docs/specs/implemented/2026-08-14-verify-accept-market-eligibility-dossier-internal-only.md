# VERIFY/ACCEPT — Dossiê de Elegibilidade `INTERNAL_ONLY`

- **Nível:** STANDARD
- **Estado:** ACCEPTED pelo Founder em 2026-08-14
- **Decisão de Discovery:** PROCEED
- **Owner de produto:** Founder / Product Owner
- **Data:** 2026-08-14
- **Tipo:** VERIFY/ACCEPT; não autoriza BUILD

## Problema e usuário

O Titan já gera um `Dossier` canônico de elegibilidade sintética e o empacota em
`VerificationBundle` verificável offline. Ainda não foi demonstrado se uma pessoa de
negócio de frigorífico/comprador, sem conhecer a arquitetura interna, consegue usar
o artefato para entender o que foi avaliado, por quê, com quais provas, limitações e
conclusão.

O usuário primário desta validação é um leitor interno que representa o papel de
frigorífico/comprador. O objetivo é avaliar a comunicabilidade do artefato existente,
não medir proficiência técnica do leitor nem validar um mercado real.

## Contexto e objetivo

Capacidades existentes confirmadas:

- `MarketEligibilityDossierSectionBuilder` produz a seção `market_eligibility`;
- `MarketEligibilityDossierTemplate` persiste pelo `DossierService` existente;
- `VerificationBundleService` empacota o Dossier sem formato paralelo;
- `BundleVerifier` confere o pacote offline;
- o único perfil aceito pelo template é sintético `MARKET_TEST_A`;
- a boundary de reconhecimento é exclusivamente `INTERNAL_ONLY`;
- coverage dimensional, limitações, Policy, Rules, FactSnapshot, Evaluation,
  Decision e autoridade já integram o envelope canônico.

Objetivo: verificar se o leitor responde, olhando somente o Dossier, o Bundle e o
relatório de verificação fornecidos, às perguntas de negócio definidas no roteiro
associado, sem deduzir certificação, autorização de exportação ou reconhecimento
externo.

## Fora de escopo

- novo motor de regras, Policy, Rule ou mercado real;
- API, PDF, tela, migration, integração externa ou alteração de domínio;
- score de confiança;
- validação regulatória, comercial ou externa;
- transformar feedback hipotético em requisito;
- alterar o artefato durante esta fase.

## Comportamento e regras de negócio

Cada cenário usa somente `MARKET_TEST_A`, material sintético e
`RECOGNITION_BOUNDARY:INTERNAL_ONLY`.

O leitor deve conseguir distinguir:

- fato/evidência usada de evidência ausente;
- regra satisfeita de regra falha ou indeterminada;
- coverage parcial de violação comprovada;
- Evaluation técnica de Decision emitida;
- autoridade de emissão de reconhecimento externo;
- integridade verificável de verdade material ou autorização de exportação.

O `Dossier` JSON é a fonte canônica. O `VerificationBundle` e seu relatório provam
integridade e verificabilidade do material fornecido; não elevam a conclusão a
reconhecimento externo. Não há PDF nesta validação.

## Cenários de validação

| Cenário | Situação sintética | Resultado esperado para leitura |
|---|---|---|
| A — Elegível internamente | fatos suficientes e requisito atendido | conclusão interna favorável, evidências e coverage completa identificáveis |
| B — Evidência ausente | fato/evidência necessária ausente | pendência ou indeterminação explícita, sem conclusão positiva nem negativa inventada |
| C — Requisito violado | fatos suficientes demonstram requisito não atendido | rejeição interna, regra e razão identificáveis |
| D — Coverage histórico parcial | informação válida, mas intervalo/dimensão insuficiente | coverage parcial e impacto impeditivo da conclusão positiva explicitamente distinguíveis |

Os artefatos de B, C e D serão preparados somente para a futura execução da
validação com os construtores e serviços existentes. Esta SPEC não cria fixtures,
scripts, regras ou dados persistidos.

## Critérios de aceite

Para cada cenário, o leitor responde sem consultar código, ADR, banco ou arquitetura:

1. sujeito avaliado;
2. finalidade/perfil sintético;
3. instante de avaliação e corte de conhecimento, quando declarado;
4. Policy e versão das Rules;
5. requisitos avaliados, satisfeitos, falhos e pendentes/indeterminados;
6. evidências/fatos utilizados e evidências ausentes;
7. coverage, período e limitações relevantes;
8. Decision, razões e ação corretiva quando houver;
9. autoridade de emissão e revisão aplicável, sem inventar revisão ausente;
10. limite `INTERNAL_ONLY` e ausência de reconhecimento externo;
11. resultado de integridade/verificação offline e seu limite semântico.

Cada resposta deve ser classificável como `DATA`, `DOMAIN`, `PRESENTATION`,
`TERMINOLOGY`, `TRACEABILITY`, `PRODUCT` ou `NONE`, conforme o roteiro.

Resultado final:

- **ACCEPTED:** todas as respostas críticas são encontradas corretamente e não há
  necessidade de conhecimento técnico do Titan;
- **ACCEPTED_WITH_GAPS:** a conclusão é compreensível, mas há lacunas de
  apresentação, terminologia ou rastreabilidade sem erro de dados/domínio;
- **REJECTED:** informação essencial não existe, é ambígua, induz conclusão errada
  ou exige conhecimento da arquitetura para interpretar o resultado.

## Plano técnico

Não há BUILD. A execução futura reutiliza o caminho existente:

```text
Decision/Evaluation/Policy sintéticas
  → MarketEligibilityDossierTemplate
  → Dossier canônico
  → VerificationBundleService
  → BundleVerifier offline
```

O roteiro humano está em
`docs/specs/proposed/2026-08-14-verify-accept-market-eligibility-dossier-internal-only-validation.md`.
Os resultados serão registrados no mesmo documento de SPEC durante VERIFY/ACCEPT;
somente uma entrega de produto posterior, se aprovada, entra no checklist.

## Verificação e observabilidade

- Antes da leitura humana, executar os testes existentes de seção de dossiê e Bundle
  para confirmar o mecanismo técnico.
- Preparar os quatro artefatos com identificadores sintéticos e sem dados reais.
- Guardar os Dossiers, Bundles e relatórios de verificação usados na rodada como
  material de sessão, sem versionar credenciais, dados pessoais ou fonte externa.
- Registrar respostas antes de qualquer explicação técnica; depois classificar cada
  problema pela taxonomia desta SPEC.

Não há nova telemetria, log, métrica ou alerta: esta é uma validação interna manual,
sem alteração de runtime.

## Documentação afetada

- esta SPEC e seu roteiro de leitura;
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md` somente se um incremento observável de produto
  vier a ser aprovado e concluído;
- `docs/product/CAPABILITY_MAP.md` somente se a rodada revelar mudança factual de
  capacidade, não apenas uma preferência de apresentação.

## Riscos, alternativas e perguntas abertas

**Risco principal:** o Dossier canônico é completo e verificável, mas JSON/Bundle
pode exigir vocabulário técnico demais para um leitor de negócio. Isso é evidência de
`PRESENTATION` ou `TERMINOLOGY`, não autorização automática para alterar o Core.

**Alternativa rejeitada agora:** criar PDF, tela ou API para tornar a leitura mais
agradável. Sem evidência da rodada, isso seria BUILD especulativo.

**Decisões do Founder ainda necessárias:** nenhuma para executar a validação interna.
Após ACCEPT, o Founder decide se há Discovery externa com frigorífico/comprador e se
uma lacuna de apresentação justifica um incremento próprio.

## Registro de VERIFY interno — 2026-08-14

### Método e limite da leitura

Foram preparados em memória, sem persistência e sem alterar runtime, quatro
Dossiers/Bundles de `MARKET_TEST_A`: A atendido, B evidência ausente, C requisito
não atendido e D coverage parcial. Cada Dossier verificou seu hash canônico e cada
Bundle retornou `VALIDA` no `BundleVerifier` offline. Os 11 testes existentes de
`test_market_eligibility_dossier_section.py` também passaram.

A leitura foi um **proxy interno**: o avaliador limitou-se ao Dossier, Bundle e
relatório de verificação, mas não substitui uma pessoa de negócio independente. Os
tempos abaixo são estimativas de localização no artefato, usadas somente como sinal
de apresentação.

### Resultado por cenário

| Cenário | Resultado técnico | Conclusão de leitura |
|---|---|---|
| A — elegível internamente | hash válido; Bundle `VALIDA`; Decision `APROVADA` | conclusão interna favorável, Policy/version, coverage completa e `INTERNAL_ONLY` identificáveis; origem da evidência e descrição humana da regra não estavam autocontidas |
| B — evidência ausente | hash válido; Bundle `VALIDA`; Decision `INDETERMINADA` | ausência `territorial_evidence` e impacto na conclusão identificáveis; não houve falsa reprovação ou aprovação |
| C — requisito violado | hash válido; Bundle `VALIDA`; Decision `REJEITADA` | violação e razão identificáveis; o documento traz código/resultado da Rule, mas não sua descrição completa no caso preparado |
| D — coverage histórica parcial | hash válido; Bundle `VALIDA`; Decision `INDETERMINADA` | status `PARTIAL` e impacto impeditivo identificáveis; a dimensão não explica sozinha onde está a lacuna dentro do intervalo |

### Respostas observadas e tempo aproximado

| Bloco de perguntas | A | B | C | D | Achado |
|---|---:|---:|---:|---:|---|
| sujeito, finalidade, instante e Policy | 20–40 s | 20–40 s | 20–40 s | 20–40 s | sujeito aparece como `animal` + UUID; finalidade é sintética e técnica |
| Decision, razões e estado do requisito | 30–60 s | 45–75 s | 30–60 s | 45–75 s | estados não se confundem com reconhecimento externo |
| Rule e versão utilizada | 45–90 s | 45–90 s | 45–90 s | 45–90 s | `rule_results` traz código/versão; `rules` estava vazio nos artefatos preparados |
| fatos/evidências e origem | 60–120 s | 45–90 s | 60–120 s | 60–120 s | fatos existem, mas `source_reference` está ausente nos cenários; não há origem humana legível |
| coverage e limitações | 30–60 s | 30–60 s | 30–60 s | 45–90 s | dimensões e intervalo são visíveis; a localização da lacuna parcial não é detalhada |
| autoridade, revisão e `INTERNAL_ONLY` | 20–45 s | 20–45 s | 20–45 s | 20–45 s | emissão automatizada é visível; não há revisão humana aplicável; boundary é explícita |
| integridade/verificação | 30–60 s | 30–60 s | 30–60 s | 30–60 s | Bundle válido é localizável; exige explicar que integridade não é verdade material ou autorização |

### Pontos que exigiram explicação técnica

1. UUID e `entity_type=animal` não identificam o animal na linguagem do negócio.
2. `market-test-a`, códigos de Rule e estados como `atendida`/`pendente` são
   compreensíveis como sinais, mas não explicam integralmente a regra sem o item
   completo em `rules`.
3. O fato de coverage não possui `source_reference` nos cenários preparados; logo o
   artefato não permite apontar origem humana/documental da evidência usada.
4. `PARTIAL` declara cobertura insuficiente, mas não apresenta o subintervalo ou
   lacuna concreta sem depender da razão da Decision.
5. O relatório de Bundle prova consistência do pacote, não verdade material,
   certificação ou autorização; essa distinção exigiu explicação curta.

### Classificação dos achados

| Achado | Classe | Avaliação |
|---|---|---|
| Sujeito exposto como UUID sem identificador operacional | PRESENTATION | O domínio aceita fatos de identidade; o cenário/dossiê de mercado não os torna legíveis por si só |
| Rules não copiadas para os Dossiers preparados | TRACEABILITY | `DossierService` suporta Rules; o caminho exercitado não as recebeu. Não é lacuna do motor de regras |
| Origem de evidência ausente nos fatos sintéticos | DATA | O cenário não contém Evidence/Source; não demonstra falha de domínio nem justifica mudança estrutural |
| Códigos e enumerações técnicos | TERMINOLOGY | Resultado e ausência são corretos, mas não são linguagem natural de negócio |
| Coverage parcial sem posição explícita da lacuna | PRESENTATION | O status e a razão chegam ao leitor; a visualização de intervalo é insuficiente para explicar a lacuna sozinha |
| `INTERNAL_ONLY` e limite contra export authorization | NONE | Boundary é explícita e impediu interpretação como reconhecimento externo |
| Verificação offline confundível com validade comercial | PRESENTATION | O mecanismo é correto; a mensagem para negócio ainda é técnica |

Não foi encontrado achado `DOMAIN`. O único achado `DATA` pertence aos cenários
sintéticos preparados, não demonstra ausência de conceito no repositório.

### Resultado global recomendado

**ACCEPTED_WITH_GAPS.** As conclusões essenciais são alcançáveis sem conhecer a
arquitetura interna e sem interpretar o resultado como reconhecimento externo: sujeito
no nível de tipo/ID, finalidade, instante, Decision, razões, estados, coverage,
autoridade automatizada, boundary e integridade estão presentes. As lacunas são de
apresentação, terminologia e rastreabilidade do material de teste; não justificam
alteração de Core, domínio ou mecanismo de avaliação.

### Recomendação posterior ao aceite

Não criar camada derivada de apresentação agora. Primeiro usar o roteiro externo já
definido nesta SPEC para verificar se frigorífico/comprador realmente precisa de uma
leitura não técnica e quais campos importam. Se a Discovery externa confirmar a
necessidade, abrir uma nova Discovery/SPEC de apresentação derivada, mantendo
`Dossier` JSON e `VerificationBundle` como fontes canônicas.

### ACCEPT do Founder — 2026-08-14

O Founder concedeu **ACCEPT** ao resultado `ACCEPTED_WITH_GAPS`. Não há autorização
de BUILD decorrente desta rodada: gaps de `PRESENTATION`, `TERMINOLOGY`,
`TRACEABILITY` e o dado sintético ausente permanecem insumos para Discovery externa
com frigorífico/comprador. Não foram identificados gaps de `DOMAIN`.
