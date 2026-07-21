# ADR 0010 — Verificação externa e VerificationBundle
**Status:** Aceita  
**Data:** 20 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan precisa permitir que terceiro verifique integridade, assinatura, prova temporal e composição de Dossier sem acesso ao banco ou confiança cega na API. Ao mesmo tempo, um arquivo exportado não consegue comprovar sozinho estado atual de revogação, nova Policy ou informação não incluída.

O Domain define Dossier como snapshot verificável e PDF como representação. As ADRs 0007 e 0009 exigem provas e relatórios históricos reproduzíveis, com escopo e perfis explícitos.

Exportação atravessa a fronteira de Authorization: depois de entregue, o Titan não controla cópias. Um pacote não pode incluir dados apenas porque contribuíram internamente para uma Decision.

## Problema

Definir:

- conteúdo e semântica de VerificationBundle;
- escopos verificáveis e declarações de completude;
- fronteira entre validação offline e API online;
- autorização, publicação, privacidade e revogação de acesso;
- código de verificação;
- versionamento, preservação e redaction;
- relatório e resultados;
- segurança do formato e do verificador;
- relação entre Dossier JSON, PDF e cadeia Titan.

## Princípios

1. **Escopo explícito:** resultado declara exatamente o que foi verificado.
2. **Offline reproduzível:** prova histórica não depende do banco Titan.
3. **Online complementar:** API atualiza contexto sem reescrever o pacote.
4. **Completude demonstrada, não presumida:** ausência e redaction são visíveis.
5. **Confiança não é transportada automaticamente:** certificado incluído não vira trust anchor.
6. **Exportação autorizada:** Visibility interna não implica direito de publicar.
7. **Imutabilidade:** mudança produz novo bundle correlacionado.
8. **Privacidade mínima:** somente dados aprovados para audiência e finalidade entram no pacote.
9. **Resultado explicado:** nenhum booleano resume toda a validação.
10. **Integridade não é verdade:** pacote válido não certifica conteúdo material.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Somente API online | Dados atuais e controle de acesso | Dependência do Titan e baixa preservação independente |
| Somente PDF | Distribuição simples | Não contém necessariamente cadeia, políticas e provas suficientes |
| Bundle offline | Autossuficiência histórica | Não conhece revogação ou fatos posteriores sem novo material |
| Bundle mais API | Prova preservada e atualização opcional | Dois contratos e resultados temporais distintos |
| Cadeia integral pública | Descoberta fácil | Viola Visibility, finalidade e minimização |

## Decisão

Adotar modelo híbrido: **VerificationBundle imutável e autossuficiente para o escopo declarado**, complementado por **API de verificação autorizada e explicável**.

Validação offline usa somente material empacotado e trust policy fornecida de forma confiável ao verificador. Consulta online nunca é requisito oculto para declarar resultado offline.

Autossuficiência significa conter o material específico do artefato necessário ao escopo. Trust policy, trust anchors previamente aprovados e regras jurídicas podem permanecer externos, desde que necessidade e identidade sejam declaradas.

Container físico, compressão, criptografia do arquivo, URL e interface serão decididos separadamente.

## Modelo técnico

O Titan distingue:

- **VerifiedArtifact:** bytes ou snapshot alvo;
- **BundleManifest:** inventário canônico e protegido do pacote;
- **VerificationBundle:** manifesto e material necessário ao escopo;
- **ValidationReport:** execução imutável de validação;
- **VerificationCode:** referência pública limitada, quando publicada;
- **OnlineVerificationResponse:** resultado atual da API em contexto definido.

São contratos técnicos de Application e Infrastructure até eventual inclusão aprovada no `DOMAIN.md`.

VerificationBundle não é Dossier. Pode conter Dossier e representações, mas possui finalidade própria de transporte e verificação.

## Modos de verificação

O modo é selecionado explicitamente:

- `OFFLINE`: utiliza somente conteúdo incorporado ou fornecido localmente;
- `ONLINE`: consulta fontes externas previamente aprovadas e registra cada fonte;
- `REFERENCE`: resolve referência imutável no Titan e verifica o material retornado.

Nenhum modo muda automaticamente para outro. Indisponibilidade online não autoriza substituir fonte, confiança ou estado sem indicação explícita.

## Escopos de verificação

O manifesto declara um ou mais escopos:

- integridade dos bytes ou snapshot;
- Signature conforme SignatureProfile;
- inclusão em IntegrityCheckpoint;
- TemporalAnchor e prova de existência;
- reprodução do Dossier e sua Decision;
- encadeamento de Provenance incluído;
- completude delimitada da cadeia Titan.

Verificar assinatura do PDF não comprova automaticamente Dossier JSON, Decision, Genealogy ou cadeia Titan. Verificar checkpoint não comprova verdade dos registros incluídos.

Completude é avaliada somente contra fronteira declarada e verificável, como sequências, contagem, IDs, cursor de checkpoint, prova de cobertura, manifesto de subconjunto ou redaction. Sem prova do conjunto esperado, componentes presentes podem ser íntegros, mas completude permanece `INDETERMINADA`.

## Estrutura conceitual do VerificationBundle

O bundle contém conceitualmente identificador e versão do formato, manifesto protegido, escopo, inventário, artefato ou referências imutáveis permitidas, Digests, serialização, Signatures, certificados, CertificationPaths, TimestampTokens, TemporalAnchors, checkpoints, provas de cobertura, material histórico, redactions, lacunas, perfis, políticas e informações de reprodução.

Presença não implica validade ou confiança. Manifesto classifica cada componente como obrigatório, opcional, deliberadamente ausente ou externo.

## Manifesto

BundleManifest é canônico, versionado e imutável. Preserva:

- identificador e versão do bundle;
- bundle predecessor ou substituído;
- RecordOwnerOrganization e Issuer;
- audiência, finalidade, classificação e validade da publicação;
- artefatos, IDs, versões, nomes lógicos e Digests;
- escopos declarados;
- componentes, tamanhos, media types e Digests;
- referência única, obrigatoriedade, relações e ordem quando relevante;
- algoritmos e versões de CanonicalSerialization;
- perfis e versões;
- lacunas, exclusões, redactions e limitações;
- instante de criação e Actor responsável;
- correlação e versão do contrato.

Manifesto possui Digest e selo ou Signature conforme perfil aprovado, impedindo adição, remoção, substituição ou mistura silenciosa de componentes.

Assinatura do manifesto confirma somente integridade e identidade declaradas pelo perfil; material interno continua sujeito à própria validação.

Validade estrutural confirma consistência entre manifesto, inventário e componentes. Não comprova origem confiável. Autenticidade de emissão depende de Signature, checkpoint, Publication ou mecanismo exigido pelo perfil.

Componente não listado não integra o escopo. Extensão permitida ocupa namespace específico, não altera interpretação protegida e aparece no relatório. Arquivo inesperado fora dessa área torna o bundle inválido ou incompatível conforme perfil.

## Conteúdo do bundle

Conforme escopo, o bundle inclui:

- artefato ou snapshot canônico;
- Dossier JSON e PDF opcional;
- hashes, cadeias e provas de inclusão;
- IntegrityCheckpoints e TemporalAnchors;
- Signatures e bytes protegidos;
- certificados e CertificationPaths avaliados;
- material histórico de estado e revogação;
- trust stores, Trusted Lists ou referências com material/Digest verificável;
- SignatureProfiles e políticas versionadas;
- ValidationReports existentes;
- versão dos motores e especificações necessárias;
- manifesto e assinatura ou selo correspondente.

Trust anchor incluído não é confiável apenas por estar no bundle. Verificador aplica trust policy externa ou perfil previamente aceito e informa a origem da confiança.

Chaves privadas, PINs, secrets, tokens, credenciais, biometria bruta, OrganizationContext e conteúdo sem Visibility aprovada são proibidos.

## Autorização e publicação

Gerar, publicar, compartilhar, baixar e revogar referência online são operações distintas, autorizadas e auditadas.

Application avalia OrganizationContext, RecordOwnerOrganization, Permission, Publication, AuthorizationGrant, audiência, finalidade e Visibility de cada componente antes do snapshot.

Autorização de um Dossier não implica acesso a toda Evidence subjacente. Componente não exportável é omitido ou substituído por prova mínima aprovada, com lacuna explícita.

Bundle exportado pode ser copiado fora do Titan. Revocation impede novas entregas ou consultas, mas não apaga cópias já distribuídas. Conteúdo sensível exige decisão de divulgação proporcional a esse risco.

## Redaction e minimização

Redaction nunca modifica bundle existente. Produz novo bundle, novo manifesto e novos Digests, correlacionado ao anterior quando autorizado.

Remoção visual não basta: bytes, metadados, anexos, campos ocultos e nomes também são inspecionados. Redaction declara campos e efeitos sobre os escopos verificáveis.

Prova seletiva avançada permanece fora do escopo. Hash de dado previsível não é anonimização e pode permitir inferência.

## Verificação offline

Verificador opera sem rede por padrão e:

1. valida estrutura, limites e versão;
2. confere manifesto e inventário;
3. recalcula Digests e serializações;
4. valida assinaturas, certificados e material temporal;
5. verifica provas de inclusão e escopos;
6. avalia perfis e trust policy configurada;
7. emite ValidationReport imutável.

Resultado offline descreve estado segundo material e instante de referência incluídos. Não afirma revogação atual, Publication atual ou ausência de evento posterior.

Falta de serialização, perfil, trust material, componente ou prova resulta em `INDETERMINADA` para dimensão afetada, não em consulta de rede silenciosa.

## API de verificação

A API conceitual recebe referência ou artefato permitido e retorna dimensões de integridade, assinatura, confiança, timestamp, checkpoint, escopo, completude, estado atual conhecido, warnings e razões.

Resposta identifica contrato, perfil, versão, instante de referência, instante da execução, motor e fontes consultadas. Resultado online não altera ValidationReport histórico do bundle.

Cada dimensão atual informa fonte, instante da consulta, atualização declarada pela fonte quando disponível, resultado, limitações e falhas parciais. “Não revogado” significa somente ausência de revogação aplicável nas fontes e instantes declarados.

Conteúdo protegido exige autenticação, OrganizationContext e Authorization. Endpoint deliberadamente público retorna somente metadados aprovados para Publication pública.

URL, métodos e schemas públicos serão definidos em ADR de contratos antes da implementação.

## VerificationCode

VerificationCode é referência aleatória de alta entropia para versão imutável de Publication e escopo mínimo aprovado. Não autentica User, não concede acesso geral e não substitui Authorization para conteúdo protegido.

Alteração de conteúdo, versão ou Visibility não muda silenciosamente o objeto resolvido. Nova versão recebe novo código ou associação explicitamente versionada.

Expirar ou revogar o código impede novas resoluções no serviço Titan. Não invalida bundle obtido, não apaga cópia e não revoga Signature, TimestampToken, checkpoint ou Evidence.

Código não deriva de ID sequencial, CPF, hash previsível ou segredo reutilizado. Aplicam-se rate limit, monitoramento, expiração ou revogação quando previstas e respostas que evitem enumeração.

QR Code público usa preferencialmente VerificationCode. Digest exposto inclui algoritmo, domínio de separação e finalidade e não referencia conteúdo sensível ou previsível sem análise de privacidade. QR Code não acrescenta confiança.

## Dimensões do resultado

ValidationReport separa:

- integridade estrutural do bundle;
- integridade dos componentes;
- autenticidade da emissão;
- validade das Signatures e confiança das cadeias;
- validade de timestamps e checkpoints;
- cobertura e completude;
- compatibilidade de perfil;
- estado histórico e estado atual consultado;
- suficiência do material.

Cada dimensão possui estado, razões, evidências, limitações e instante de referência. Resultado agregado não elimina resultados parciais.

## Resultado e relatório

Cada dimensão produz resultado parcial e agregado `VALIDA`, `INVALIDA` ou `INDETERMINADA` para perfil e escopo declarados.

ValidationReport registra bundle e manifesto, material incorporado, fontes externas, componentes, Digests, perfil, política, trust store, instantes, versões de motor e parser, configuração relevante, suíte compatível de test vectors, verificações, resultados, razões, warnings, limitações e lacunas.

Resultado nunca afirma simultaneamente estado histórico e atual sem separá-los. Validade do bundle não implica verdade, conformidade regulatória atual ou ausência de dados fora do escopo.

## Versionamento e preservação

Qualquer alteração de conteúdo, manifesto, escopo, redaction ou material incorporado cria novo bundle. Bundle anterior permanece imutável e verificável.

Formato e versão antigos permanecem documentados e suportados enquanto houver retenção ou replay. Migração gera novo pacote correlacionado, não substituição silenciosa.

Test vectors públicos são sintéticos, documentados, licenciados e não contêm dados pessoais ou comerciais reais. Incluem casos válidos, adulterados, parciais, incompatíveis, maliciosos e ambíguos.

## Segurança do verificador

Parser trata todo bundle como não confiável. Deve impor:

- limites de tamanho, quantidade, profundidade e expansão;
- proteção contra path traversal, nomes duplicados e links;
- allowlist de algoritmos e formatos;
- parsing seguro de PDF, certificados e estruturas;
- proibição de execução de scripts e macros;
- ausência de acesso automático a URLs do bundle;
- timeouts e limites de memória e CPU;
- isolamento proporcional para conteúdo complexo.

Erros não expõem segredos, caminhos internos ou configuração de confiança.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Verificação histórica offline; interoperabilidade; prova explicável; API não obrigatória; privacidade delimitada |
| Negativas | Pacotes maiores; formatos versionados; material histórico complexo; risco de cópias externas; manutenção de verificador |

## Riscos e controles

| Risco | Controle |
|---|---|
| PDF tratado como cadeia completa | Escopo explícito e resultados separados |
| Pacote parcial apresentado como completo | Fronteira, contagem, lacunas e provas |
| Material incluído virar confiança | Trust policy externa e origem declarada |
| Dado protegido exportado | Authorization por componente e minimização |
| Revocation prometer apagar cópia | Limite de controle após exportação explícito |
| Código enumerável | Alta entropia, rate limit e respostas seguras |
| Bundle malicioso | Parser restrito, limites e ausência de rede |
| Trust ou estado atual presumido offline | Resultado histórico separado do online |
| Redaction apenas visual | Novo artefato e inspeção de bytes/metadados |
| Formato antigo inverificável | Especificação, suporte e test vectors versionados |

## Verificação automatizada

Testes devem cobrir:

- bundle íntegro e reprodução offline;
- manifesto ou componente alterado, ausente ou extra;
- extensão permitida e arquivo inesperado fora do namespace;
- pacote parcial e alegação indevida de completude;
- completude sem fronteira verificável;
- Signature, checkpoint ou timestamp inválidos;
- trust anchor incluído mas não confiável;
- material histórico insuficiente;
- ausência de consulta de rede no modo offline;
- diferença entre resultado histórico e online;
- modos offline, online e reference sem transição automática;
- fonte online desatualizada ou parcialmente indisponível;
- duas Organizations e componente sem Visibility;
- geração, Publication e download sem Permission;
- revogação online sem promessa de apagar cópia;
- redaction de conteúdo, metadado e anexo;
- código previsível, expirado, revogado e rate limited;
- código antigo depois de nova Publication;
- Digest público previsível ou sem domínio de separação;
- path traversal, expansão excessiva, nomes duplicados e formato malicioso;
- test vector processado por implementação independente.

## Critérios de aceitação

A ADR pode ser aceita quando:

- bundle for autossuficiente para escopo declarado;
- dependências externas de confiança forem explicitamente identificadas;
- modos offline, online e reference forem explícitos;
- manifesto proteger inventário e componentes;
- validade estrutural não for confundida com autenticidade;
- verificação parcial não for apresentada como completa;
- completude válida exigir fronteira verificável;
- componentes extras seguirem regra formal de extensão;
- offline não depender de consulta oculta ao Titan;
- estado histórico e atual forem separados;
- confiança não vier automaticamente do material incluído;
- exportação exigir Authorization por componente;
- revogação não prometer apagar cópias;
- redaction gerar novo artefato;
- código de verificação não substituir autenticação geral;
- código resolver Publication imutável e escopo delimitado;
- revogação do código não revogar prova exportada;
- Digest público exigir contexto e análise de privacidade;
- resultado possuir perfil, escopo, dimensões e razões;
- estado atual informar fonte, instante e frescor;
- relatório identificar parser, política, trust store e test vectors;
- PDF, Dossier e cadeia Titan permanecerem distintos;
- bundles e formatos históricos permanecerem reproduzíveis;
- parser tratar conteúdo como não confiável;
- test vectors forem sintéticos e cobrirem casos maliciosos;
- container, API pública final e UI permanecerem fora do escopo.

## O que esta ADR não decide

Esta ADR não escolhe:

- ZIP, ASiC ou container físico;
- compressão ou criptografia do bundle;
- URL, rota ou schema final da API;
- biblioteca ou linguagem do verificador;
- interface gráfica;
- hospedagem pública;
- prova seletiva ou zero-knowledge;
- formato final do PDF;
- perfil jurídico concreto.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída por nova ADR. Depois da adoção, mudança de formato ou API preserva bundles, manifestos, relatórios, perfis e test vectors anteriores; migração produz nova versão correlacionada.
