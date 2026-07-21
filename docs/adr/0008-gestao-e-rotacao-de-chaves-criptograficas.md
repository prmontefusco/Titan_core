# ADR 0008 — Gestão e rotação de chaves criptográficas
**Status:** Aceita  
**Data:** 20 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan poderá assinar Evidences, Dossiers, checkpoints ou outros artefatos conforme perfil aprovado. A validade histórica dessas assinaturas depende de identificar a chave, proteger o material privado, preservar material público e reagir corretamente a rotação, perda ou comprometimento.

Guardar chave privada no banco, código ou configuração da aplicação concentraria dados e mecanismo de proteção no mesmo ambiente. Acoplar o Core a um HSM, KMS ou fornecedor impediria substituição e testes proporcionais.

Esta decisão trata de chaves de assinatura ou selo institucional controladas pelo Titan. Chaves de usuários, TLS, OIDC Provider, TSA, banco, backup e criptografia de conteúdo possuem responsáveis e semânticas distintas.

## Problema

Definir:

- fronteira entre Titan e mecanismo protegido;
- ownership, finalidade e isolamento das chaves;
- identificação de chave e material criptográfico;
- geração, ativação, criptoperíodo, rotação e destruição;
- indisponibilidade, perda e comprometimento;
- preservação da verificação histórica;
- backup, recuperação e separação de funções;
- agilidade de algoritmo;
- limites da escolha de produto e certificado.

## Princípios

1. **Chave privada não é dado de domínio:** Domain e Application nunca recebem seus bytes.
2. **Menor privilégio:** identidade técnica utiliza somente finalidade e chave autorizadas.
3. **Separação de finalidade:** chave não é reutilizada entre funções criptográficas incompatíveis.
4. **Isolamento explícito:** chave não representa Organization diferente sem autorização e perfil aprovados.
5. **Identidade histórica:** toda assinatura referencia exatamente material e algoritmo utilizados.
6. **Rotação não reescreve:** nova chave não altera assinatura histórica.
7. **Falha segura:** indisponibilidade não autoriza fallback para chave menos protegida.
8. **Provider substituível:** produto e SDK permanecem em Infrastructure.
9. **Auditoria sem segredo:** operação é explicável sem registrar material privado.
10. **Agilidade criptográfica:** algoritmo ou provider pode evoluir preservando provas anteriores.

## Escopo

Inclui chaves usadas pelo Titan para assinatura institucional de artefatos, selo técnico de processo ou plataforma e assinatura de checkpoints, caso decisão posterior exija.

Não inclui chave privada de pessoa física ou signatário externo, chaves da TSA ou OIDC Provider, certificados TLS, chaves de criptografia de banco, disco, backup ou conteúdo, secrets de aplicações ou material de autenticação de ServiceIdentity.

Cada categoria excluída exige ciclo, acesso e decisão próprios.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Arquivo ou variável de ambiente | Simples | Exposição, cópia e rotação frágeis |
| Chave criptografada no PostgreSQL | Backup centralizado | Dado e acesso ficam próximos; aplicação precisa descriptografar a chave |
| Keystore local | Adequado a desenvolvimento | Dependência do host, disponibilidade e controle operacional limitados |
| SoftHSM | Interface realista e gratuito | Proteção depende do host; não equivale a HSM físico ou serviço acreditado |
| HSM próprio | Controle e chave não exportável | Custo, redundância, operação e recuperação especializados |
| KMS ou Cloud HSM | Alta disponibilidade e operação gerenciada | Custo, lock-in e requisitos jurisdicionais |
| Serviço remoto de assinatura | Custódia especializada | Dependência externa, latência e integração contratual |

## Decisão

Adotar porta **KeyProvider** substituível. Em produção, material privado permanece exclusivamente em mecanismo protegido e é preferencialmente não exportável. O Titan persiste somente referência opaca, metadados públicos e histórico operacional.

SoftHSM ou keystore local é permitido somente em desenvolvimento e testes, identificado como perfil não produtivo.

HSM, KMS, Cloud HSM, serviço remoto e produto concreto serão avaliados separadamente conforme perfil de confiança, jurisdição, disponibilidade, custo e requisitos operacionais.

## Fronteira de responsabilidades

### Domain

- conhece Signature e significado de autoria, integridade ou aprovação;
- não conhece HSM, KMS, PKCS#11, key handle, certificado ou SDK;
- não recebe chave privada, PIN, secret ou credencial do provider.

### Application

- escolhe finalidade e perfil aprovados;
- solicita assinatura de Digest ou bytes canônicos por referência interna;
- autoriza operação e constrói contexto;
- associa resultado ao artefato sem confiar em metadado não validado;
- não escolhe livremente algoritmo ou chave informados pelo cliente.

### Infrastructure e KeyProvider

- resolvem referência opaca para mecanismo configurado;
- autenticam a ServiceIdentity técnica;
- executam geração e operação criptográfica permitidas;
- retornam assinatura, `key_id`, algoritmo e material público referenciável;
- aplicam timeout, retry seguro, auditoria e limites;
- nunca retornam bytes privados à aplicação.

## Identidade e metadados

O Titan distingue:

- **KeyPurpose:** finalidade lógica e perfil permitido;
- **KeyVersion:** material criptográfico concreto utilizado em um período;
- **key_id:** identificador imutável de KeyVersion;
- **provider_reference:** referência opaca no mecanismo protegido;
- **representada por:** Organization ou plataforma cuja identidade o uso declara;
- **custodiada por:** responsável técnico pela proteção e operação.

KeyPurpose e identidade representada podem continuar durante rotações. Cada geração distinta de material criptográfico recebe novo `key_id`, ainda que perfil lógico e metadados permaneçam iguais.

`key_id` é identificador lógico estável e opaco do Titan para uma geração específica. Não é reutilizado, não revela segredo e não precisa coincidir com identificador ou caminho interno do provider. A associação com a referência nativa pertence à Infrastructure.

Metadados preservam, quando aplicável:

- `key_id` e KeyPurpose;
- RecordOwnerOrganization ou plataforma responsável;
- `provider_profile_id` e referência opaca da chave;
- ambiente e identidade representada;
- algoritmo, parâmetros e tamanho;
- chave pública ou referência verificável;
- certificado e cadeia referenciados, quando existentes;
- perfil de confiança;
- criação, ativação, expiração, revogação, destruição e criptoperíodo;
- estado e motivo;
- substituição e predecessor;
- responsáveis e correlação de operações.

Metadados não são prova de que a operação ocorreu no provider; retornos criptográficos e auditoria correspondente devem ser validados.

PIN, wrapping key, seed, chave privada, recovery share, secret de acesso e qualquer material suficiente para reconstruir a chave privada não são persistidos no banco Titan.

## Perfil de chave

Toda geração utiliza perfil versionado que define KeyPurpose, ambiente, identidade representada, algoritmo e parâmetros, mecanismo de proteção, exportabilidade, criptoperíodo, operações, aprovações, rotação, backup, recuperação, destruição e material público preservado.

KeyPurpose é valor controlado e versionado, nunca texto livre. Chave aprovada para uma finalidade não é reutilizada para outra, mesmo com algoritmo e identidade iguais.

Cliente, payload ou mensagem não ampliam nem substituem o perfil. Alteração incompatível exige nova versão de perfil e nova geração de material quando aplicável.

## Identidade representada

Toda operação registra quem ou o que a chave representa: plataforma Titan, Organization, serviço técnico ou autoridade institucional aprovada.

Custódia técnica pelo operador não autoriza afirmar representação de Organization, pessoa ou profissional sem contrato, delegação e perfil correspondentes.

Identidade representada é distinta de RecordOwnerOrganization dos metadados, ServiceIdentity executora, custodiante técnico e Actor aprovador.

## Isolamento e finalidade

Chaves são separadas por ambiente, finalidade, perfil e identidade representada. Reuso entre desenvolvimento e produção é proibido.

Uma chave não assina por múltiplas Organizations por conveniência. Chave de plataforma declara selo da plataforma e não assinatura da Organization ou User.

Application valida OrganizationContext, Permission, finalidade, artefato e KeyPurpose antes da solicitação. KeyProvider também restringe ServiceIdentity e operação, oferecendo defesa em profundidade.

Nome, referência, finalidade ou identidade representada fornecidos por cliente, mensagem ou payload não são confiáveis.

## Ciclo de vida

Toda chave possui estado explícito e transições autorizadas. Fases conceituais em português:

- planejada;
- gerada;
- ativa;
- suspensa;
- expirada;
- revogada;
- comprometida;
- perdida;
- destruída.

Geração pode seguir para ativação; chave ativa pode ser suspensa, expirar, ser revogada, comprometida ou perdida. Suspensão pode retornar à ativa somente por procedimento autorizado. Comprometimento não retorna a estado confiável, destruição é irreversível e recuperação do material não altera automaticamente estado ou autorização.

Estado criptográfico do material, autorização administrativa de uso e disponibilidade operacional são dimensões distintas. Chave pode permanecer válida para verificação histórica estando bloqueada para novas assinaturas ou indisponível no provider.

Estado do metadado Titan e estado no provider são reconciliados. Divergência resulta em suspensão ou negação até investigação.

Ativação exige algoritmo, perfil, responsáveis, período e testes aprovados. Expiração impede novas assinaturas, mas não elimina validação histórica.

Códigos e transições finais serão consolidados no contrato de Application ou `DOMAIN.md` antes da implementação.

## Rotação

Rotação é planejada por criptoperíodo, política, algoritmo, certificado, capacidade ou risco.

Regras:

- cada geração distinta de material recebe novo `key_id`;
- ativação pode possuir sobreposição controlada;
- somente uma versão é padrão por finalidade e contexto, salvo migração explícita;
- novas assinaturas usam versão ativa resolvida pelo servidor;
- assinatura preserva `key_id`, algoritmo, perfil e material público;
- versão anterior deixa de assinar após encerramento;
- chave pública, certificado, política e material histórico permanecem disponíveis;
- artefatos antigos não são reassinados silenciosamente;
- mudança é auditada e reversão operacional não reutiliza material comprometido.

Verificação histórica não depende de a chave privada anterior continuar disponível.

## Indisponibilidade e perda

Se o KeyProvider não puder executar ou confirmar a operação, o resultado é pendente, falhou ou indeterminado conforme contrato. Não se presume assinatura.

Não existe fallback automático para arquivo local, chave de desenvolvimento, algoritmo mais fraco ou outra identidade.

Perda significa material indisponível sem evidência de exposição. Novas assinaturas usam nova KeyVersion após procedimento aprovado. Assinaturas históricas continuam verificáveis com material público preservado.

Falha de comunicação pode produzir resultado desconhecido: o provider pode ter assinado sem que a resposta tenha chegado. O Titan não presume execução nem ausência dela.

Nova tentativa preserva identidade lógica quando o provider suporta idempotência ou cria tentativa correlacionada sem apagar resultado anterior possível. Assinaturas recuperadas permanecem registradas e explicadas.

Idempotência lógica não exige bytes de assinatura idênticos. Verificação considera algoritmo, parâmetros, chave, conteúdo e validade criptográfica conforme o perfil.

## Comprometimento

Suspeita ou confirmação de comprometimento exige:

1. bloquear novas operações;
2. preservar logs e evidências;
3. registrar incidente, descoberta, último uso conhecido como confiável, primeiro instante suspeito, bloqueio, revogação e confiança da delimitação;
4. revogar certificado e versão quando aplicável;
5. gerar e ativar nova KeyVersion por procedimento aprovado;
6. localizar Signatures, Evidences, Dossiers e checkpoints potencialmente afetados;
7. considerar timestamps e estado histórico na análise;
8. publicar resultado e reavaliar artefatos sem apagar histórico.

Comprometimento conhecido não é corrigido por reassinatura silenciosa. Artefatos potencialmente afetados são relacionados à janela. Quando ela não puder ser delimitada, não se presume que todo histórico seja seguro nem necessariamente inválido; o resultado permanece explicado e pode ser indeterminado.

## Backup e recuperação

Preferência é alta disponibilidade, redundância e backup controlado pelo mecanismo protegido, sem exportação para o Titan.

Quando backup ou recuperação de chave privada forem permitidos, exigem política explícita, criptografia, separação de funções, dupla aprovação, inventário, teste, auditoria e destino com proteção equivalente.

Recuperação não reativa automaticamente chave expirada, revogada ou comprometida. Restauração de metadados sem material correspondente mantém operação bloqueada.

Destruição produz evidência auditável de que o procedimento aprovado foi executado no mecanismo e locais inventariados. Não prova inexistência absoluta de cópias desconhecidas, especialmente quando o material foi exportável. Material público e histórico de validação são preservados.

## Controles operacionais

Papéis de administração, uso, auditoria, backup e recuperação são separados. ServiceIdentity possui grants mínimos por operação e chave. Operações sensíveis podem exigir dupla aprovação e autenticação reforçada. Quotas e rate limits reduzem abuso. Logs registram identificadores, finalidade, resultado e correlação, nunca segredo. Inventário e reconciliação detectam chave órfã, desconhecida ou divergente. Ambientes não compartilham credenciais administrativas. Alertas cobrem uso anômalo, falhas, expiração e alteração de política.

## Agilidade criptográfica

Algoritmos e parâmetros usam allowlist versionada por perfil. Cliente e payload não negociam algoritmo livremente.

Assinatura registra algoritmo e parâmetros necessários à verificação. Suporte de verificação permanece enquanto houver artefato retido dependente dele.

Algoritmo descontinuado impede novas assinaturas. Migração preserva evidência antiga e pode adicionar prova correlacionada, sem reescrever bytes ou alegar que assinatura nova ocorreu no instante original.

## Limite da substituição do provider

Substituição preserva contratos e permite novas chaves em outro mecanismo, mas não garante portabilidade de material privado não exportável.

Nesse caso, novas operações usam nova geração no provider sucessor. Artefatos históricos permanecem vinculados ao material público e ao provider anterior apenas quando alguma operação ainda exigir acesso à chave privada antiga.

Referência física ou identificador nativo do provider não atravessa para Core ou contrato público.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Chave privada isolada; rotação auditável; histórico verificável; provider substituível; menor lock-in no Core |
| Negativas | Componente crítico adicional; custo possível; operação e recuperação especializadas; indisponibilidade pode bloquear assinatura |

## Riscos e controles

| Risco | Controle |
|---|---|
| Chave privada no banco ou código | Referência opaca e operação somente no KeyProvider |
| Chave universal | Separação por ambiente, finalidade, perfil e identidade representada |
| Rotação quebrar histórico | Novo `key_id` e preservação do material público |
| Provider indisponível | Estado pendente ou falha segura, sem fallback local |
| Perda confundida com comprometimento | Procedimentos e estados distintos |
| Comprometimento oculto | Bloqueio, incidente, revogação e análise de impacto |
| Backup menos protegido | Proteção equivalente, dupla aprovação e auditoria |
| Chave de plataforma representar Organization | Identidade representada explícita no perfil e assinatura |
| Algoritmo escolhido pelo cliente | Allowlist e resolução pelo servidor |
| SoftHSM apresentado como produção | Perfil não produtivo explícito |
| Provider substituível prometer portabilidade física | Contrato portável, nova chave e limite de não exportabilidade explícito |

## Verificação automatizada

Testes devem cobrir:

- provider falso sem vazamento de chave privada;
- isolamento entre duas Organizations;
- finalidade ou KeyPurpose incorreta;
- KeyPurpose livre ou identidade representada ausente;
- chave de outro ambiente;
- algoritmo fora da allowlist;
- ativação e expiração;
- rotação com novo `key_id`;
- verificação de assinatura anterior após rotação;
- sobreposição controlada;
- indisponibilidade e resultado desconhecido;
- duas assinaturas válidas diferentes para a mesma intenção;
- ausência de fallback local;
- suspensão e revogação;
- perda e comprometimento distintos;
- janela de comprometimento delimitada e indeterminada;
- localização de artefatos afetados;
- reconciliação entre Titan e provider;
- autorização de backup, recuperação e destruição;
- recuperação sem reativação automática;
- troca de provider com chave não exportável;
- ausência de chave, PIN ou secret em banco, logs e erros.

## Critérios de aceitação

A ADR pode ser aceita quando:

- material privado permanecer fora de Domain e Application;
- produção exigir mecanismo protegido e preferencialmente não exportável;
- Titan persistir apenas referência opaca e metadados públicos;
- `key_id` for estável, opaco e nunca reutilizado;
- referência nativa do provider permanecer em Infrastructure;
- chaves forem separadas por finalidade, ambiente, perfil e identidade;
- KeyPurpose for controlado e identidade representada obrigatória;
- cada geração de material receber novo `key_id`;
- estado criptográfico, autorização e disponibilidade forem distintos;
- estados e transições autorizadas forem explícitos;
- rotação preservar verificação histórica;
- perda, indisponibilidade e comprometimento forem distintos;
- resultado desconhecido e tentativas correlacionadas forem preservados;
- idempotência não exigir igualdade dos bytes da assinatura;
- comprometimento bloquear uso e produzir análise de impacto;
- incidente registrar janela e confiança da delimitação;
- backup e recuperação não reduzirem o nível de proteção;
- nenhum fallback automático enfraquecer o perfil;
- algoritmos forem resolvidos por allowlist do servidor;
- provider concreto permanecer fora do Core;
- troca de provider não prometer migração de chave não exportável;
- destruição não alegar inexistência absoluta além da evidência disponível;
- SoftHSM e keystore local permanecerem restritos a desenvolvimento;
- certificados, assinatura jurídica e chaves excluídas continuarem fora do escopo.

## O que esta ADR não decide

Esta ADR não escolhe:

- HSM, KMS, Cloud HSM, serviço remoto ou fornecedor;
- PKCS#11 ou API concreta;
- algoritmo, tamanho e criptoperíodo finais;
- certificado, CA, cadeia ou política de assinatura;
- assinatura de pessoa física;
- formato de Signature, PAdES, CAdES ou JAdES;
- chave de TLS, OIDC, TSA, banco, backup ou conteúdo;
- topologia, alta disponibilidade e valores de timeout;
- efeito jurídico ICP-Brasil ou eIDAS.

## Referências normativas
NIST SP 800-57 Part 1 — Recommendation for Key Management: General; NIST SP 800-57 Part 2 — Best Practices for Key Management Organizations; e FIPS 140-3 — Security Requirements for Cryptographic Modules, quando exigido pelo perfil.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída por nova ADR. Depois da adoção, troca de provider preserva `key_id`, metadados, material público, Signatures e auditoria histórica; migração de material privado somente ocorre por procedimento suportado e aprovado.
