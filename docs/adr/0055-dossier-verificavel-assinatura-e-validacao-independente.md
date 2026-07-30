# ADR-0055 - Dossier verificavel, assinatura e validacao independente

**Data:** 2026-07-29<br>
**Status:** ACEITA<br>
**Aceita em:** 2026-07-29<br>
**Base normativa:** `DOMAIN.md` v1.19 e ADRs aceitas ate ADR-0054<br>
**Escopo:** Titan Core<br>
**Relacionadas:** ADR-0007, ADR-0009, ADR-0010, ADR-0048, ADR-0051, ADR-0052, ADR-0053, ADR-0054

---

## 1. Contexto

Um relatorio pode ser legivel sem ser verificavel; um `Dossier` confiavel deve permitir demonstrar integridade, origem, autoridade e limites mesmo fora do ambiente que o produziu.

Auditor, frigorifico, produtor, certificadora, autoridade, comprador, sistema externo ou parte contestante podem precisar examinar uma decisao sem acesso ao banco, conta no Titan, confianca na infraestrutura corrente, acesso a todos os dados ou conexao com fontes externas.

O `DOMAIN.md` define `Dossier` como snapshot auditavel, imutavel e autocontido de `Decision`, `Evaluation` ou processo de conformidade, e define PDF como representacao, nao fonte primaria. A ADR-0010 ja decidiu o `VerificationBundle` imutavel e autocontido para transporte e verificacao. Esta ADR aplica essas garantias ao ciclo de decisoes explicaveis sem criar segundo formato, manifesto ou mecanismo de trust concorrente.

---

## 2. Problema

Sem contrato formal, um PDF pode ser alterado sem deteccao, uma assinatura pode proteger apenas apresentacao visual, links externos podem desaparecer, redaction pode mudar significado silenciosamente, e um verificador pode concluir "valido" apenas porque um hash coincide.

Integridade, autenticidade, autoridade, validade temporal, conformidade e verdade material sao conclusoes distintas. Assinatura valida demonstra que identidade delimitada assinou bytes delimitados; nao demonstra isoladamente que a decisao esta correta, reconhecida por terceiro ou juridicamente eficaz.

---

## 3. Decisao

O Titan representa `Dossier` como artefato normativo imutavel, versionado e identificavel que preserva a explicacao auditavel de uma `Decision`, `Evaluation` ou processo delimitado.

Para verificacao independente, o `Dossier` pode ser empacotado em `VerificationBundle` conforme ADR-0010. O bundle contem `BundleManifest` canonico, inventario, material incorporado ou referencias permitidas, digests, signatures, perfis, limitacoes e evidencias necessarias ao escopo declarado. O `VerificationBundle` declara explicitamente para quais dimensoes e escopo e autocontido; referencia externa nao o invalida, mas impede alegacao de autocontencao para verificacao integral quando material necessario nao estiver incorporado.

A verificacao nao exige confiar na interface, banco corrente ou estado operacional atual do Titan. Ela pode depender de perfil de confianca externo e deve declarar o que conseguiu e o que nao conseguiu verificar.

PDF, HTML, JSON resumido e QR Code sao apresentacoes derivadas. Nenhuma apresentacao constitui isoladamente a identidade normativa do `Dossier` ou do `VerificationBundle`.

---

## 4. Escopo e nao objetivos

Esta ADR define:

- relacao entre `Dossier`, `VerificationBundle`, `BundleManifest`, apresentacao e `ValidationReport`;
- identidade, conteudo minimo e referencias verificaveis do artefato;
- assinatura, prova temporal, trust e validacao independente;
- verificacao offline, parcial e por dimensoes;
- redaction, divulgacao seletiva, preservacao, suplemento, revogacao e portabilidade;
- limites de conclusao de verificador independente.

Esta ADR nao define:

- algoritmo criptografico definitivo alem de perfil ja aprovado;
- infraestrutura completa de PKI, armazenamento fisico ou UX de portal publico;
- reconhecimento juridico universal ou autoridade externa automatica;
- politica de retencao especifica de vertical;
- disponibilidade perpetua de fonte externa;
- novo `DossierManifest`, `TrustProfile`, `ValidationPolicy` ou `VerificationResult` genericos paralelos aos conceitos e contratos da ADR-0010.

---

## 5. Modelo conceitual

| Conceito | Responsabilidade |
| --- | --- |
| `Dossier` | Artefato normativo que preserva a explicacao auditavel de escopo delimitado. |
| `VerificationBundle` | Pacote de transporte e verificacao autocontido para escopo declarado, definido pela ADR-0010. Pode conter `Dossier`, mas nao se confunde com ele. |
| `BundleManifest` | Inventario canonico, protegido, versionado e imutavel do `VerificationBundle`. E o manifesto aplicavel; esta ADR nao cria `DossierManifest` paralelo. |
| Presentation | PDF, HTML, JSON resumido ou QR Code derivados para leitura humana. |
| `Signature` | Prova criptografica sobre objeto e contexto delimitados. |
| `ValidationReport` | Registro imutavel de verificacao concreta, com perfil, politica, trust material, instantes, dimensoes e limitacoes. |
| `SignatureProfile` e trust policy | Contratos que delimitam algoritmos, cadeias, autoridades reconhecidas, revogacao e criterios de validacao. |

```text
Evaluation + Decision + autoridade + revisoes
        -> Dossier normativo
        -> VerificationBundle com BundleManifest
        -> Signature e provas temporais conforme perfil
        -> Presentation derivada
        -> ValidationReport independente
```

---

## 6. Conteudo e identidade do Dossier

O `Dossier` preserva ou referencia, quando aplicavel e autorizado:

- identidade, versao do formato, contrato e versao de canonicalizacao;
- Subject, finalidade, Organization emissora e escopo de divulgacao;
- `Evaluation`, `evaluation_hash`, snapshot, `snapshot_hash` e tempos relevantes;
- `Decision`, `decision_hash`, `DecisionReasons`, condicoes, restricoes e limitacoes;
- `Policy`, Rules, `NormativeBasisSnapshot` e contexto de aplicabilidade;
- `DecisionAuthorityProfile`, identidade ou referencia de autoridade e emissor;
- `DecisionProposal`, `DecisionReview`, aprovacoes, `DecisionOverride` e `DecisionRelation`, quando existentes;
- Evidences, artefatos, fontes, anexos, redactions, lacunas e dependencias externas materialmente relevantes;
- instrucoes, perfil e versao de verificacao aplicaveis.

Identidades seguem a ADR-0051: tipo, dominio semantico, esquema e versao de canonicalizacao sao declarados. Hashes de objetos distintos usam separacao de dominio. Metadados observacionais nao alteram identidade semantica sem contrato explicito.

O tipo e escopo declarado do `Dossier` determinam seus componentes obrigatorios. Um Dossier de `Evaluation` nao exige `Decision`, autoridade de emissao ou revisoes inexistentes. Um Dossier de `Decision` inclui ou referencia a cadeia decisoria materialmente necessaria. Ausencia de componente nao aplicavel difere de lacuna em componente obrigatorio.

`dossier_hash` identifica exclusivamente o conteudo normativo canonico do `Dossier`, segundo seu dominio e contrato de identidade. Empacotamento, apresentacao, trust material adicional ou transporte nao alteram `dossier_hash` enquanto esse conteudo permanecer identico.

---

## 7. BundleManifest, conteudo incorporado e referencias

O `BundleManifest` da ADR-0010 declara componentes, relacoes, obrigatoriedade, digests, tamanhos, media types, versoes, lacunas, redactions, perfis e limites. Toda colecao e ordenada deterministicamente pelo contrato de canonicalizacao; extensao critica desconhecida impede verificacao integral e extensao nao critica somente pode ser ignorada quando o manifesto assim permitir.

Componentes podem ser:

- **EMBEDDED**: bytes fazem parte do bundle e participam do inventario protegido;
- **CONTENT_ADDRESSED_REFERENCE**: referencia possui digest, versao ou identidade verificavel suficiente;
- **LOCATOR_ONLY**: URL, caminho, nome ou localizador sem identidade verificavel suficiente.

`LOCATOR_ONLY` nao basta para reproducao ou verificacao forte. Referencia material deve possuir identidade semantica verificavel. Quando objeto externo necessario nao tiver identidade suficiente ou estiver indisponivel, isso e limitacao explicita e impede alegacao de verificacao completa na dimensao afetada.

O `Dossier` e o `VerificationBundle` possuem identidades distintas. `bundle_hash` identifica `BundleManifest`, inventario protegido e componentes que participam da identidade do pacote, conforme ADR-0010. Inclusao de um mesmo `Dossier` em bundles diferentes nao altera `dossier_hash`, salvo mudanca do proprio conteudo normativo do `Dossier`.

`dossier_hash` e `bundle_hash` sao calculados separadamente, cada um sobre objeto canonico, dominio versionado e contrato de identidade proprios. Hash de JSON bruto, PDF, resposta HTTP ou ordem de banco nao constitui identidade normativa.

Cada componente externo declara se sua incorporacao e necessaria para integridade do pacote, verificacao criptografica, reproducao da `Evaluation`, verificacao de autoridade, verificacao integral ou informacao suplementar. Um bundle somente se declara autocontido para determinada dimensao quando todo material necessario a essa dimensao estiver incorporado.

---

## 8. Assinaturas, tempo e autoridade

Toda `Signature` declara `signature_target` normativamente inequivoco: tipo do objeto assinado, identidade ou digest exato, dominio semantico, versao do contrato de identidade, contexto, finalidade, perfil criptografico e escopo assinados. A finalidade nao e inferida apenas por chave, certificado ou localizacao da assinatura.

Assinatura sobre `dossier_hash` nao protege automaticamente `VerificationBundle`. Assinatura sobre `bundle_hash` nao demonstra automaticamente aprovacao de `Decision`. Assinatura sobre Presentation nao protege objetos normativos fora de seu escopo declarado.

Assinaturas de emissor, `Decision`, autoridade, aprovacao, selo temporal e preservacao possuem escopos distintos e nao sao intercambiaveis.

Validacao temporal separa `claimed_signing_time`, `trusted_timestamp`, `verification_time`, intervalo de validade de chave e conhecimento de revogacao. Revogacao posterior nao invalida automaticamente assinatura historicamente valida: a conclusao depende de perfil, instante confiavel demonstrado, estado de revogacao conhecido e motivo ou efeito da revogacao.

Assinatura valida nao prova automaticamente competencia decisoria. A autoridade e avaliada separadamente com `DecisionAuthorityProfile`, identidade, escopo, vigencia e evidencias preservadas.

---

## 9. Trust e validacao independente

Trust material incluido no bundle nao se torna confiavel apenas por estar presente. O verificador aplica trust policy externa ou perfil previamente aceito e informa a origem da confianca, algoritmos permitidos, autoridades reconhecidas, regras de revogacao, tolerancias temporais e formatos suportados.

Um verificador independente deve conseguir, no escopo permitido:

1. validar formato, schema, versao e limites;
2. canonicalizar manifesto e recalcular digests;
3. verificar componentes incorporados e referencias disponiveis;
4. verificar `Signature`, certificados, cadeias e prova temporal;
5. verificar coerencia entre `Evaluation`, `Decision`, autoridade, revisoes, override e relacoes;
6. avaliar trust policy e compatibilidade de perfil;
7. produzir `ValidationReport` estruturado.

`ValidationReport` separa ao menos integridade, assinatura, confianca, autoridade, tempo, disponibilidade de conteudo, suporte de perfil, redaction, completude e coerencia interna. Resultado agregado pode ser valido, invalido, parcialmente verificado, indeterminado ou nao suportado conforme perfil, mas nao substitui as dimensoes e razoes separadas.

`ValidationReport` e imutavel como registro de verificacao executada com determinada politica, trust material, conhecimento e `verification_time`. Ele nao constitui conclusao permanente sobre o Dossier: nova politica, conhecimento de revogacao, trust store ou verificador pode produzir outro `ValidationReport`, sem alterar o anterior.

---

## 10. Verificacao offline e parcial

Verificacao totalmente offline e possivel somente para escopo cujo bundle incorpore manifesto, objetos necessarios, schemas, perfis, material de trust requerido, provas temporais, estado historico de revogacao quando exigido e artefatos de reproducao aplicaveis.

Modo offline parcial pode confirmar integridade, coerencia interna e assinaturas com material incorporado, sem conseguir verificar revogacao atual, autoridade externa, fonte remota ou reconhecimento regulatorio corrente.

Ausencia de rede, componente externo indisponivel ou trust material ausente nao e adulteracao por si so. O verificador nao consulta rede silenciosamente no modo offline; registra limitacao e produz resultado parcial ou indeterminado na dimensao afetada.

Verificacao estrutural e criptografica nao implica reproducao da `Evaluation`. Reproducao exige artefatos, runtime, contratos e entradas definidos pelas ADRs 0050-0052. Reavaliacao independente produz nova conclusao e nao substitui nem altera `Evaluation` historica incorporada ao `Dossier`.

Bundle preserva evidencia e estado de autoridade conhecidos no escopo temporal declarado, mas nao garante que toda autoridade externa possa ser confirmada independentemente ou em tempo real. Quando validacao depender de registro externo, `ValidationReport` declara fonte, instante consultado e limitacao correspondente.

---

## 11. Apresentacoes humanas

PDF, HTML, JSON resumido e QR Code sao derivados. QR Code e meio de representacao ou transporte: seu conteudo pode ser Presentation, identificador verificavel, fragmento de bundle ou mero localizador, e sua presenca nao adiciona por si so integridade ou autenticidade. Toda apresentacao declara o `dossier_hash` ou identificador verificavel a que corresponde, versao da apresentacao, redaction e aviso de parcialidade quando aplicaveis.

Todo valor normativo exibido deriva de conteudo identificado no `Dossier` ou bundle. Apresentacao nao inclui conteudo material fora do manifesto, nao substitui o manifesto canonico e nao pode divergir silenciosamente de objeto assinado. Assinatura de PDF isolado nao comprova `Dossier`, `Decision` ou cadeia Titan salvo quando o perfil declarar escopo explicitamente limitado.

---

## 12. Redaction e divulgacao seletiva

`FULL_DOSSIER`, derivado redigido e pacote de divulgacao seletiva sao formas conceituais de entrega, nao enums persistidos nesta ADR.

Redaction nunca remove bytes de `Dossier` ou `VerificationBundle` ja publicados. Produz novo artefato, novo manifesto, novos digests e nova identidade, correlacionados ao original quando autorizacao permitir. O derivado declara politica e motivo de redaction, campos ou objetos ocultados, compromissos ou provas minimas quando aplicaveis, e impacto sobre verificabilidade.

Correlacao com artefato original pode ser declarativa ou criptograficamente demonstravel conforme perfil. Declarar identificador do original nao prova, isoladamente, que derivado preserva corretamente todos os valores nao redigidos.

Remocao visual nao basta: bytes, metadados, anexos, campos ocultos, nomes e referencias sao inspecionados. Dossier parcial ou redigido nao se apresenta como completo, e redaction nao amplia ou inverte razoes originais.

---

## 13. Versionamento, suplemento, revogacao e disponibilidade

`Dossier` e bundle publicados sao imutaveis. Nova evidencia, nova `Decision`, correcao, redaction, suplemento, substituicao ou revogacao criam novo artefato ou relacao explicita. Nenhum arquivo e substituido silenciosamente mantendo identificador ou digest anterior.

Revogacao de Publication, codigo de verificacao, chave ou acesso impede novas entregas ou alteracoes conforme contrato, mas nao apaga copia ja distribuida nem reescreve verificacao historica. Efeito posterior deve ser representado por relacao, `Revocation`, `DecisionRelation`, suplemento ou novo `ValidationReport`.

Dependencia externa e classificada como requerida para integridade, requerida para verificacao completa ou suplementar. Indisponibilidade deve identificar objeto ausente, diferenciar ausencia de inconsistencia e permitir verificacao parcial quando o perfil permitir.

---

## 14. Invariantes

1. `Dossier` nao e apenas apresentacao visual.
2. Todo `Dossier` possui identidade canonica e imutavel.
3. Manifesto e componentes materialmente incluidos participam da identidade correspondente.
4. Localizador nao substitui identidade de conteudo.
5. `Signature` declara objeto e contexto exatos assinados.
6. Assinatura valida nao prova automaticamente autoridade ou conformidade.
7. Verificacao nao retorna apenas booleano quando houver dimensao parcial ou limitacao.
8. Conteudo ausente nao e confundido com conteudo adulterado.
9. Apresentacao humana referencia identidade verificavel correspondente.
10. Redaction produz derivado identificavel e nao mutacao silenciosa.
11. Nova versao nao substitui `Dossier` historico.
12. Verificacao historica considera tempo, validade e revogacao aplicaveis.
13. Verificador declara trust policy, perfil e fontes de confianca usados.
14. Extensao critica desconhecida impede validacao integral.
15. Metadado observacional nao altera identidade sem contrato explicito.
16. Falha de assinatura altera conclusao de autenticidade, nao conteudo historico.
17. Validade criptografica, autoridade, reconhecimento externo e verdade material permanecem conclusoes distintas.
18. Verificacao offline declara dimensoes avaliadas e limitacoes.
19. Dossier parcial ou redigido nao se apresenta como completo.
20. Relacao de suplemento, substituicao ou revogacao e explicita.
21. Trust material incluido nao e aceito automaticamente como trust anchor.
22. Verificador offline nao consulta rede silenciosamente.
23. `Dossier` e `VerificationBundle` possuem identidades distintas.
24. Alteracao de empacotamento nao altera `dossier_hash` quando conteudo normativo do `Dossier` permanecer identico.
25. `bundle_hash` nao substitui `dossier_hash`, e `dossier_hash` nao demonstra sozinho integridade integral do bundle.
26. Autocontencao e declarada por escopo e dimensao.
27. Toda `Signature` possui alvo normativo inequivoco.
28. Assinatura de objeto nao se estende implicitamente a objetos relacionados.
29. Finalidade de assinatura nao e inferida apenas por chave, certificado ou posicao da assinatura.
30. Completude e avaliada contra tipo, escopo e perfil declarado do `Dossier`.
31. `ValidationReport` registra conclusao contextual e temporal, nao verdade permanente sobre objeto.
32. Verificacao estrutural nao implica reproducao da `Evaluation`.
33. Declarar correlacao com `Dossier` original nao prova, isoladamente, derivacao criptografica correta.

---

## 15. Fluxos de referencia

### 15.1 Emissao

```text
Evaluation + Decision + autoridade + revisoes
        -> selecionar conteudo do Dossier
        -> canonicalizar Dossier segundo seu contrato
        -> calcular dossier_hash
        -> montar inventario do VerificationBundle
        -> canonicalizar BundleManifest
        -> calcular bundle_hash e digests dos componentes
        -> incorporar ou referenciar artefatos
        -> assinar objetos e contextos declarados
        -> gerar apresentacoes derivadas
        -> publicar pacote imutavel
```

### 15.2 Verificacao

```text
Dossier ou VerificationBundle recebido
        -> validar formato e schema
        -> canonicalizar manifesto
        -> recalcular digests
        -> verificar componentes e anexos
        -> verificar assinaturas e tempo
        -> avaliar autoridade e trust policy
        -> verificar coerencia interna
        -> produzir ValidationReport estruturado
```

---

## 16. Estado atual e transicao

O `DOMAIN.md` ja define `Dossier`, `SingleFileVerificationBundle`, `Signature`, `CanonicalSerialization` e cadeia de proveniencia. A ADR-0010 ja define `VerificationBundle`, `BundleManifest`, `ValidationReport`, verificacao offline, redaction, trust e preservacao. O Core atual possui partes de integridade e verificacao, mas ainda nao entrega integralmente o contrato de snapshots, autoridade, revisao, identidade e temporalidade exigido pelas ADRs 0048-0054.

A transicao deve:

- preservar `Dossiers` e bundles existentes segundo seus contratos historicos;
- declarar claramente perfil, versao, escopo, lacunas e limitacoes de cada exportacao;
- vincular novos Dossiers a snapshots, Decisions, autoridades, revisoes e hashes conforme as ADRs anteriores forem implementadas;
- reutilizar `BundleManifest` e `ValidationReport` da ADR-0010, sem criar formatos paralelos;
- criar test vectors e testes de verificador independente antes de alegar verificacao integral;
- bloquear alegacao de validade completa quando depender de componente, trust ou evidencia temporal ausente.

---

## 17. Alternativas rejeitadas

### 17.1 Tratar PDF como Dossier normativo

Rejeitada porque apresentacao visual nao garante inventario, relacoes, escopo, redaction ou cadeia verificavel.

### 17.2 Criar manifesto paralelo ao BundleManifest

Rejeitada porque duplicaria identidade, canonicalizacao e verificacao ja decididas na ADR-0010.

### 17.3 Considerar hash coincidente como verificacao completa

Rejeitada porque hash nao demonstra autoridade, trust, tempo, completude, admissibilidade ou reconhecimento externo.

### 17.4 Confiar automaticamente em certificado ou trust anchor incluido

Rejeitada porque material incorporado precisa ser avaliado por trust policy independente.

### 17.5 Redigir arquivo ja publicado

Rejeitada porque destroi a identidade historica e oculta o escopo originalmente divulgado.

### 17.6 Consultar rede silenciosamente durante verificacao offline

Rejeitada porque mistura estado atual com verificacao historica e mascara limitacoes do pacote.

---

## 18. Criterios de conformidade

Uma implementacao esta conforme esta ADR quando:

- produz `Dossier` identificavel e `VerificationBundle` conforme ADR-0010 para verificacao independente;
- usa `BundleManifest` canonico, versionado e protegido, sem manifesto paralelo;
- inclui ou referencia `Evaluation`, snapshot, `Decision`, autoridade, revisoes e override materialmente relevantes;
- distingue componentes incorporados, referencias verificaveis e localizadores insuficientes;
- assina identidade delimitada, e nao apenas PDF ou apresentacao;
- produz `ValidationReport` por dimensoes, perfil e limitacoes;
- nao confunde integridade, assinatura, trust, autoridade, tempo, conformidade ou verdade material;
- suporta verificacao offline sem rede silenciosa e declara parcialidade;
- produz derivado novo para redaction ou divulgacao seletiva;
- preserva relacoes explicitas de nova versao, suplemento, substituicao ou revogacao;
- cobre em testes pacote integro, manifesto alterado, anexo alterado ou ausente, referencia externa indisponivel, assinatura valida e invalida, chave expirada ou revogada posteriormente, ausencia de selo temporal, autoridade nao reconhecida, algoritmo ou extensao critica nao suportados, apresentacao divergente, redaction declarada e nao declarada, pacote parcial, verificacao offline e reutilizacao de identificador com conteudo diferente.

---

## 19. Questoes adiadas

- algoritmo criptografico e formato binario definitivos por perfil aprovado;
- infraestrutura de PKI, trust stores e listas de revogacao de producao;
- UX de portal, QR Code e apresentacoes publicas;
- prova seletiva avancada e zero-knowledge para divulgacao minima;
- reconhecimento juridico ou regulatorio por jurisdicao;
- estrategia de retencao de longo prazo de esquemas, parsers e test vectors.

Essas questoes nao autorizam reduzir verificacao a PDF, hash isolado ou confianca cega no ambiente Titan.

---

## 20. Consequencias

O Titan fecha o ciclo de confianca: realidade representada, snapshot, `Evaluation`, autoridade, revisao, `Decision` e `Dossier` podem ser examinados por terceiro com escopo e limites declarados.

Isso exige disciplina de manifesto, identidade, assinatura, trust, redaction e preservacao. Em troca, o Titan pode demonstrar nao apenas que registrou uma decisao, mas como ela pode ser verificada sem depender integralmente de sua operacao presente.
