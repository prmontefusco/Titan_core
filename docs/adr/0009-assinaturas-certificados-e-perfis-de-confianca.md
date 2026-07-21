# ADR 0009 — Assinaturas, certificados e perfis de confiança
**Status:** Aceita  
**Data:** 20 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Domain define Signature como comprovação criptográfica de autoria, integridade ou aprovação. Esse conceito não determina sozinho quem assinou, qual intenção foi manifestada, qual certificado é confiável ou qual efeito jurídico existe.

O Titan também diferencia identidade representada, custódia de chave, Actor, Issuer, Evidence, Dossier, Digest, TimestampToken e TemporalAnchor. Uma assinatura técnica da plataforma não pode ser apresentada como assinatura de User, Organization ou profissional.

Perfis brasileiros, europeus e privados possuem âncoras, políticas e efeitos diferentes. O Core precisa validar e explicar sem presumir equivalência entre jurisdições.

## Problema

Definir:

- fronteira entre Signature de domínio e objetos criptográficos;
- conteúdo e contexto efetivamente assinados;
- identidade representada e intenção;
- perfis de assinatura e confiança;
- função de SigningProvider, KeyProvider e TrustValidator;
- validação de certificados, revogação e timestamps;
- preservação e revalidação histórica;
- limites de alegações jurídicas, formatos e fornecedores.

## Princípios

1. **Assinatura não é verdade:** validação criptográfica não certifica conteúdo material.
2. **Contexto protegido:** assinatura não pode ser reutilizada em artefato, versão, Organization ou finalidade diferentes.
3. **Representação explícita:** custódia técnica não implica representação jurídica ou institucional.
4. **Confiança configurada:** certificado não é confiável apenas por existir ou formar cadeia criptográfica.
5. **Jurisdição explícita:** classificação legal depende de lei, perfil, prestador, finalidade e instante.
6. **Negações explicadas:** resultado não é reduzido a booleano.
7. **Histórico preservado:** nova verificação ou confiança não reescreve resultado anterior.
8. **Menor privilégio:** cliente não escolhe chave, algoritmo, perfil ou trust anchor livremente.
9. **Provider substituível:** SDK e produto permanecem em Infrastructure.
10. **Core gratuito não implica confiança gratuita:** serviço acreditado pode exigir contrato e custo.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Somente hash | Integridade simples | Não identifica signatário nem representa aprovação |
| Certificado self-signed | Gratuito e controlável | Terceiro não possui razão independente para confiar |
| CA privada Titan | Confiança organizacional configurável | Distribuição e governança próprias; sem qualificação pública automática |
| Certificado institucional ICP-Brasil | Reconhecimento brasileiro conforme perfil | Custo, custódia e efeito limitados à legislação aplicável |
| Provider de assinatura externa | Chave do signatário fora do Titan | Dependência, cerimônia e evidências do provider |
| Prestador qualificado eIDAS | Qualificação europeia conforme perfil | Custo, jurisdição e Trusted Lists específicas |
| Perfil global único | Configuração aparente mais simples | Mistura identidades, leis e níveis de confiança incompatíveis |

## Decisão

Adotar **SignatureProfile versionado**, **SigningProvider** e **TrustValidator** substituíveis. Nenhuma alegação jurídica qualificada é habilitada por padrão.

Cada operação resolve perfil aprovado no servidor. Payload, cliente ou certificado recebido não ampliam finalidade, confiança, identidade representada ou classificação jurídica.

ICP-Brasil, eIDAS e confiança privada são perfis independentes. Compatibilidade criptográfica não implica reconhecimento jurídico recíproco.

## Modelo conceitual

O Titan distingue:

- **Signature:** conceito de domínio que relaciona prova a artefato, identidade, finalidade e contexto;
- **CryptographicSignature:** bytes e parâmetros produzidos pela operação criptográfica;
- **Certificate:** vínculo assinado entre identidade declarada e chave pública;
- **CertificationPath:** cadeia avaliada até trust anchor permitido;
- **SignatureProfile:** regras versionadas de criação, validação e alegação;
- **SignatureValidation:** resultado explicado em instante e perfil definidos;
- **ValidationReport:** registro técnico imutável de uma execução de validação.

Os termos técnicos não se tornam automaticamente conceitos normativos do Domain sem atualização aprovada do `DOMAIN.md`.

Signature é imutável. Correção, substituição, countersignature ou nova validação cria registro correlacionado sem alterar bytes ou resultado anterior.

## Perfis de assinatura

SignatureProfile define, no mínimo:

- identificador e versão;
- finalidade e alegação permitida;
- tipo de artefato;
- identidade representada permitida;
- Organization e audiência aplicáveis;
- bytes protegidos e CanonicalSerialization;
- algoritmo e KeyProfile permitidos;
- certificado, políticas e trust anchors aceitos;
- timestamp e material de revogação exigidos;
- regra para determinar instante de referência da validação;
- jurisdição e requisitos de preservação;
- provider e cerimônia permitidos;
- regras de revalidação e códigos de resultado.

Mudança incompatível cria nova versão. Versão anterior permanece disponível enquanto houver Signature retida dependente dela.

Perfis conceituais podem atender integridade técnica, selo da plataforma, selo institucional de Organization, assinatura externa de pessoa ou classificação jurídica específica. Nomes e requisitos finais exigem aprovação própria.

## Conteúdo protegido

Assinatura protege bytes inequívocos. Quando utilizar estrutura canônica, ela inclui conforme perfil:

- domínio de separação da assinatura;
- finalidade;
- tipo, ID e versão do artefato;
- RecordOwnerOrganization;
- identidade representada;
- Digest e algoritmo;
- versão da CanonicalSerialization;
- instante ou referência temporal aplicável;
- identificador e versão do SignatureProfile.

Domínio de separação impede que assinatura válida para Dossier seja reutilizada como aprovação de Evidence, mensagem ou outro produto.

Assinar apenas hash sem contexto é proibido quando permitir substituição semântica. O Titan preserva bytes ou representação suficiente para reprodução exata.

## Identidade e intenção

Assinatura registra identidade representada, signatário declarado, Actor solicitante, ServiceIdentity executora, Issuer, custodiante e provider quando aplicáveis. Esses papéis não são equivalentes.

Identidade representada resulta da combinação entre identidade declarada, atributos certificados, SignatureProfile, vínculo interno aplicável e finalidade. Titan não infere representação institucional, mandato ou manifestação humana apenas pelo nome ou atributo presente no certificado.

Selo técnico comprova operação por chave controlada segundo perfil; não demonstra manifestação humana. Selo de plataforma não representa Organization ou User.

Assinatura externa de pessoa exige cerimônia que preserve autenticação, intenção, artefato apresentado, consentimento ou aprovação, instante, provider e evidências necessárias ao perfil.

O Titan não recebe nem controla chave privada pessoal. Account, email ou autenticação OIDC isolada não constituem assinatura qualificada nem manifestação suficiente para todo ato.

## Fronteiras de providers

### SigningProvider

- recebe artefato ou Digest e contexto já autorizados;
- executa ou coordena cerimônia permitida pelo perfil;
- utiliza KeyProvider para chaves sob custódia Titan;
- integra provider externo para signatários externos;
- retorna assinatura e evidências técnicas sem expor chave privada;
- preserva resultado desconhecido e tentativas correlacionadas.

### TrustValidator

- recebe assinatura, conteúdo, perfil, certificados e material temporal;
- constrói e valida CertificationPath contra trust anchors configurados;
- avalia algoritmo, políticas, usos, revogação e instante relevante;
- produz SignatureValidation explicada;
- não busca confiança em endereço indicado livremente pelo artefato.

Domain e Application não conhecem SDK, endpoint, PKCS#11, PAdES, CAdES, JAdES, OCSP ou formato nativo do provider.

## Certificados e confiança

Certificado recebido não é trust anchor. Validação confirma, conforme perfil:

- assinatura e encadeamento dos certificados;
- trust anchor previamente aprovado;
- identidade e identidade representada;
- Key Usage e Extended Key Usage;
- políticas, OIDs e restrições;
- validade no instante relevante;
- revogação por material histórico aplicável;
- algoritmos e parâmetros permitidos;
- correspondência da chave à assinatura;
- status do prestador no perfil ou lista confiável aplicável.

Certificado self-signed pode integrar trust store privado explicitamente distribuído, mas não se torna público, qualificado ou independente por isso.

Expiração atual não invalida automaticamente assinatura histórica. Revogação anterior ou posterior, motivo, timestamp confiável e material disponível são avaliados e explicados.

Trust store e trust anchors utilizados possuem versão, identificador estável e material ou Digest preservado. Referência mutável ao trust store atual não reproduz validação histórica.

## Timestamp e preservação

TimestampToken e CryptographicSignature são provas distintas. Timestamp não substitui assinatura; assinatura sem timestamp não cria prova temporal independente.

Quando o perfil exigir, TemporalAnchor válido fixa instante de referência para avaliar certificado, revogação e algoritmo.

Titan preserva assinatura, bytes protegidos, perfil, `key_id`, chave pública, certificado, cadeia, material de estado e revogação aplicável — como CRL, OCSP, Trusted Lists ou equivalente —, timestamps, trust store versionado, política e relatórios necessários.

Material novo de preservação é acrescentado sem sobrescrever evidência anterior. Revalidação produz novo resultado correlacionado e informa política, trust store e instante usados.

## Dimensões da validação

Cada execução registra separadamente:

- validade criptográfica da assinatura;
- integridade dos bytes protegidos;
- validade e adequação do certificado;
- construção e confiança da CertificationPath;
- conformidade com perfil técnico;
- conformidade com eventual perfil jurídico;
- suficiência do material histórico.

O resultado agregado não elimina resultados parciais.

O instante de referência é determinado pelo perfil e pode ser instante de assinatura declarado e confiável, TemporalAnchor validado, recebimento pelo Titan ou instante atual. Instante fornecido pelo cliente não é confiável sem evidência apropriada.

## Resultados de validação

Resultado agregado é:

- `VALIDA`, quando condições criptográficas e do perfil forem satisfeitas;
- `INVALIDA`, quando houver violação determinística;
- `INDETERMINADA`, quando faltar material ou confiança suficiente.

Resultado inclui escopo, perfil e versão, instante de referência, trust store e versão, verificações parciais, warnings e códigos de razão, como Digest divergente, assinatura inválida, identidade incompatível, cadeia não confiável, uso incorreto, política não permitida, revogação ou material histórico ausente.

Nenhum resultado `VALIDA` é emitido ou apresentado sem identificação visível do perfil, versão, escopo e instante de referência. Significa válido somente nesse contexto e não afirma verdade do conteúdo. `INDETERMINADA` não é convertida permissivamente em válida.

## Relatório de validação

Cada execução produz ValidationReport imutável e correlacionado contendo Signature, Digest e bytes ou referência imutável, perfil e versão, instantes de execução e referência, algoritmo, parâmetros, `key_id`, certificado, CertificationPath, trust store e versão, material temporal e de revogação, resultados parciais, resultado agregado, razões, warnings, limitações e versão do motor.

Nova validação cria novo relatório. Mudança de norma, política, trust store ou motor não altera nem reclassifica silenciosamente relatório anterior.

## Perfis jurídicos e jurisdições

Classificações simples, avançada e qualificada são interpretadas segundo perfil jurídico e jurisdição selecionados. Igualdade de nomenclatura entre regimes não implica requisitos ou efeitos equivalentes. Classificação nunca existe sem `jurisdiction_profile`.

No Brasil, perfil identifica cadeia, política, certificado e regras aplicáveis na data de referência e pode considerar MP nº 2.200-2/2001, Lei nº 14.063/2020, ICP-Brasil e legislação setorial. Cadeia até raiz conhecida não habilita automaticamente classificação jurídica.

Na União Europeia, perfil preserva ou referencia de forma verificável Trusted List, estado histórico e serviço qualificado no instante relevante. Presença atual não prova qualificação histórica, e ausência atual não invalida automaticamente serviço historicamente qualificado. Certificado ICP-Brasil não é apresentado automaticamente como assinatura qualificada eIDAS.

Assinatura pode ser admissível como evidência sem garantir força probatória, aceitação judicial ou veracidade. Alegação jurídica exige revisão profissional para finalidade, jurisdição e data concretas.

Formato futuro define como assinatura, certificados, timestamps e material de validação são associados ou incorporados, sem alterar semântica de resultado, confiança e preservação desta ADR.

## Privacidade e auditoria

Titan registra artefato, perfil, identidades e papéis, Digest, algoritmo, `key_id`, certificados, provider, instantes, resultado, razões e correlação necessários.

Não registra chave privada, PIN, secret, token de autenticação, biometria bruta ou dado da cerimônia além do necessário e legalmente autorizado.

Erros externos são normalizados, não enumeram contas ou configuração e não devolvem conteúdo sensível.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Assinaturas explicáveis; perfis substituíveis; jurisdições separadas; histórico revalidável; menor risco de alegação indevida |
| Negativas | Políticas e materiais adicionais; validação histórica complexa; serviços qualificados podem ter custo; revisão jurídica necessária |

## Riscos e controles

| Risco | Controle |
|---|---|
| Hash tratado como assinatura | Modelo e perfil distinguem provas |
| Selo Titan representar terceiro | Identidade representada e domínio de separação |
| Certificado tratado como confiável | CertificationPath e trust anchor configurado |
| Assinatura reutilizada em outro contexto | Conteúdo protegido inclui finalidade, artefato e perfil |
| Self-signed apresentado como qualificado | Confiança privada explícita |
| Revogação histórica simplificada | Instante, motivo, timestamp e material preservados |
| ICP-Brasil igualado a eIDAS | Perfis jurídicos independentes |
| Trust store mudar o passado | Resultado histórico imutável e revalidação correlacionada |
| Provider indisponível | Resultado pendente ou desconhecido, sem assinatura presumida |
| Gratuidade confundida com qualificação | Custos e prestador aprovados por perfil |

## Verificação automatizada

Testes devem cobrir:

- bytes ou Digest alterados;
- artefato, versão, finalidade ou Organization substituídos;
- domínio de separação incorreto;
- identidade representada incompatível;
- algoritmo, KeyPurpose ou perfil não permitidos;
- certificado expirado, ainda não válido ou revogado;
- cadeia, trust anchor, Key Usage, EKU, política e OID incorretos;
- instante de referência diferente e instante de cliente não confiável;
- trust store ou Trusted List histórica indisponível;
- assinatura histórica com timestamp e material preservado;
- material ausente com resultado `INDETERMINADA`;
- self-signed aceito somente por trust store privado explícito;
- revalidação sem sobrescrever resultado anterior;
- relatório com versão diferente do motor;
- identidade no certificado sem vínculo de representação;
- selo técnico não tratado como manifestação humana;
- perfil ICP-Brasil não tratado como eIDAS qualificado;
- ausência de segredo e biometria bruta em banco, logs e erros.

## Critérios de aceitação

A ADR pode ser aceita quando:

- Signature, assinatura criptográfica, certificado e validação forem distintos;
- perfil for versionado e resolvido pelo servidor;
- conteúdo protegido impedir substituição de contexto;
- identidade representada e intenção forem explícitas;
- selo técnico não significar manifestação humana;
- chave pessoal permanecer fora do Titan;
- confiança exigir path e trust anchor aprovados;
- validade criptográfica, confiança e conformidade forem resultados separados;
- perfil, versão, escopo e instante acompanharem todo resultado;
- trust stores e Trusted Lists forem reproduzíveis e versionados;
- identidade certificada não implicar representação institucional;
- expiração e revogação forem avaliadas no instante relevante;
- timestamp permanecer prova distinta;
- resultado admitir válida, inválida e indeterminada com razões;
- revalidação não reescrever histórico;
- ICP-Brasil, eIDAS e confiança privada permanecerem separados;
- classificação jurídica sempre identificar jurisdição;
- versão do motor integrar ValidationReport imutável;
- ausência histórica não ser substituída silenciosamente pelo estado atual;
- nenhuma alegação qualificada for habilitada sem revisão jurídica;
- formato e provider concretos permanecerem fora do Core.

## O que esta ADR não decide

Esta ADR não escolhe:

- certificadora, CA, trust service provider ou produto;
- certificado ou política concretos;
- PAdES, CAdES, XAdES, JAdES ou ASiC;
- algoritmo final;
- cerimônia de assinatura externa;
- armazenamento final de material de validação;
- perfil jurídico concreto habilitado;
- efeito probatório de documento específico;
- contrato completo do VerificationBundle.

## Referências normativas

MP nº 2.200-2/2001; Lei nº 14.063/2020; regulamentação ICP-Brasil e legislação setorial aplicáveis; Regulamento (UE) nº 910/2014 (eIDAS), conforme alterado pelo Regulamento (UE) 2024/1183 e texto consolidado aplicável; padrões ETSI, quando o perfil correspondente for aprovado.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída por nova ADR. Depois da adoção, mudança de provider, trust store ou perfil preserva Signatures, bytes protegidos, certificados, resultados e auditoria anteriores; nova validação ou assinatura é correlacionada, nunca sobrescrita.
