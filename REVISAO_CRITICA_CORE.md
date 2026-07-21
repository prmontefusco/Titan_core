# Revisão Crítica — Titan Core (documentação)

**Data:** 21 de julho de 2026
**Escopo:** DOMAIN.md v1.18, ARCHITECTURE.md v1.27, DEVELOPMENT.md, AGENTS.md, README.md, VISION.md, PLANO_DE_IMPLEMENTACAO_VALIDADO.md, ADRs 0001–0026.
**Postura:** consistência interna, lacunas e riscos dos documentos do Core. Complementa a análise crítica de negócio e arquitetura realizada em 21/07.
**Natureza:** registro histórico da revisão realizada naquela data; não substitui os documentos de autoridade nem representa, sozinho, o estado vigente.

> **Atualização posterior:** esta revisão foi tratada documentalmente. PostGIS entrou no caminho crítico pela ADR-0026; estados de NonConformity foram traduzidos; proibições receberam IDs `P-001` a `P-207`; termos de vertical e seções esqueléticas da arquitetura foram corrigidos; MongoDB/GridFS foi rotulado adequadamente; Celery deixou de ser presumido; paths e protocolo foram harmonizados; ADRs de produtos concretos passaram a bloquear a infraestrutura correspondente; bootstrap e compartilhamento em escala foram registrados no plano; convenções HTTP foram aceitas na ADR-0027; e a governança das ADRs esclarece a decisão por fundador único. Os achados abaixo permanecem como registro histórico e não descrevem necessariamente o estado vigente.

---

## 1. Veredito

A documentação é internamente coerente em grau raro para o tamanho (~260 conceitos, 26 ADRs). As separações conceituais — integridade ≠ verdade, Actor ≠ Source ≠ Issuer, `INDETERMINADA` como resultado de primeira classe — são aplicadas com disciplina quase total. Os problemas encontrados são localizados: resíduos de versões antigas, três contradições reais entre documentos e lacunas operacionais concentradas nas seções esqueléticas de ARCHITECTURE.md.

---

## 2. Contradições e inconsistências encontradas

### 2.1 Termos de vertical dentro do Core (viola regra própria)

`ARCHITECTURE.md`, seção **"# Eventos"** (~linha 1447):

> "Tudo é evento. Cadastro. Movimentação. **Vacinação. Abate.** Transporte. Inspeção. Exportação."

Vacinação e abate são conceitos pecuários. O próprio documento exige testes que garantam "ausência de conceitos específicos de vertical no Core", e DOMAIN.md §2.6 proíbe o Core de conhecê-los. A seção é resíduo de rascunho antigo — assim como "# Genealogia" (Pai ↓ Filho) e "# Escalabilidade" (três palavras por fase), destoantes do restante. **Ação:** remover ou reescrever essas seções residuais.

### 2.2 Estados em inglês na NonConformity

`DOMAIN.md` §12 define o ciclo de vida como `DETECTED → CLASSIFIED → ASSIGNED → IN_CORRECTION → READY_FOR_REEVALUATION → CLOSED`. Todos os demais vocabulários controlados do documento estão em português (`APROVADA`, `ACEITA`, `PENDENTE`...), e o Passo 0.2 do plano exige explicitamente "estados em português". É a única violação encontrada — mas está em documento congelado, então corrigir agora é barato; depois de implementado, é migração.

### 2.3 Celery presumido antes da decisão

`PLANO`, Passo 4.8, presumia "consumo idempotente **pelo Celery**". Mas README e ADR-0006 dizem que produto do broker e **executor de workers "exigem decisão própria antes da adoção"** (ADR-0025 apenas veda Valkey como broker do Celery). **Tratado posteriormente:** o plano passou a usar "executor de workers aprovado" e a exigir ADR própria antes do consumo.

### 2.4 "Limite de linhas" residual no plano

`PLANO` §4, item 5 do fechamento de passo, ainda dizia "revisar o diff e **confirmar o limite de linhas**". DEVELOPMENT.md e AGENTS.md já afirmavam que "durante o MVP não existe limite fixo de linhas". **Tratado posteriormente:** o plano passou a exigir alteração coesa, revisável e restrita à capacidade do incremento, sem contagem arbitrária.

### 2.5 "Isolamento físico" que é lógico

ADR-0003 intitula-se "isolamento **físico** por Organization", mas a decisão é instância lógica compartilhada + schemas por módulo + RLS. RLS é defesa lógica em profundidade, não isolamento físico — a própria tabela de alternativas da ADR rejeita o isolamento físico real (banco/schema por Organization). O título promete mais do que a decisão entrega; em auditoria ou due diligence técnica isso custa credibilidade. **Ação:** renomear para "isolamento por RLS e defesa em profundidade".

### 2.6 Divergências menores

- `PLANO` §2 referenciava `Docs/` (maiúsculo) e a si próprio como fonte histórica. **Tratado posteriormente:** os caminhos foram normalizados para `docs/`, e plano vigente e fontes históricas agora estão separados.
- ARCHITECTURE Stack rotula MongoDB como "Object Storage" — GridFS não é object storage; a própria ADR-0004 usa o termo correto ("armazenamento de Documents").
- A análise crítica anterior citava versões v1.17/v1.25 e "PostGIS adiado". Essa leitura tornou-se histórica após a ADR-0026 e as versões v1.18/v1.27; PostGIS e o protocolo de limite fixo de linhas já foram tratados.

---

## 3. Lacunas

### 3.1 Seções operacionais esqueléticas

ARCHITECTURE.md alterna seções de profundidade excepcional (auditoria, offline, disposição) com seções de 3–10 linhas: **Segurança** (sem threat model, sem gestão de segredos além de proibições, sem hardening), **Escalabilidade** (sem nenhum alvo de volume, latência ou disponibilidade), **Genealogia** e **Eventos**. Nenhum documento define RPO/RTO, alvos de uptime ou ordem de grandeza esperada (eventos/dia, animais, Organizations). Sem isso, decisões como particionamento, retenção de DataAccessRecords e dimensionamento de checkpoint ficam sem critério objetivo quando chegarem.

### 3.2 Convenções de API ausentes

Versionamento de rotas, formato de erro, paginação e idempotência HTTP não estão definidos em lugar nenhum, e o Passo 1.3 cria a primeira API. "Nunca quebrar a API pública" exige convenções de compatibilidade definidas *antes* do primeiro endpoint. Cabe um documento curto (API_CONVENTIONS.md) ou ADR antes do Passo 1.3.

### 3.3 Decisões de produto bloqueiam o Passo 1.4

O Passo 1.4 sobe "OIDC Provider, Message Broker e Valkey" no Compose, mas não existe ADR escolhendo OIDC Provider concreto nem broker concreto. O plano deveria declarar essas duas ADRs como pré-requisito explícito do 1.4, ou o passo vai parar no meio.

**Tratado no plano:** a escolha dos produtos concretos de OIDC Provider e Message Broker passou a ser pré-requisito explícito do Passo 1.4; o executor de workers exige decisão própria antes do primeiro consumo.

### 3.4 Compartilhamento em escala não tem conceito de programa

O fluxo `SharingRequest → GrantAssessment → AuthorizationGrant` é individual e pesado. O caso de uso central da primeira vertical (centenas de produtores concedendo acesso ao mesmo frigorífico, com a mesma finalidade e o mesmo FieldScope) exigirá emissão em massa. O Core não possui conceito de "programa de compartilhamento" ou template de grant — cada vertical terá que orquestrar milhares de grants individuais por fora. Não é erro, mas é a lacuna do Core com maior impacto direto no produto. Vale ao menos uma nota de destino em DOMAIN.md ou uma ADR futura reconhecendo o padrão.

**Reconhecido no plano:** o tema foi incluído como expansão futura sujeita a validação do caso de uso e ADR própria, sem antecipar um novo modelo de domínio.

### 3.5 Proibições sem rastreabilidade para testes

DOMAIN.md §24 lista ~200 proibições e ARCHITECTURE.md acumula dezenas de "testes futuros devem impedir...". Não há mecanismo que ligue cada proibição a um teste ou marque-a como não verificável. Com esse volume, a lista vira aspiração. Sugestão barata: numerar as proibições (P-001...) e exigir no protocolo de passo que testes citem os IDs cobertos — cobertura passa a ser medível.

---

## 4. Riscos estruturais

**Custo de escrita da auditoria.** Cada acesso sensível gera múltiplos DataAccessRecords imutáveis (um por marco), mais cadeia de hash, mais serialização canônica, mais RLS. O SensitiveAccessProfile mitiga por selecionar o que é obrigatório, mas nenhum documento estabelece critério de calibração — o caminho padrão de um perfil mal calibrado é multiplicar por 5–10 o volume de escrita do sistema. Risco operacional real quando houver volume.

**Fail-closed generalizado sem válvula de escape descrita.** Praticamente toda ambiguidade produz `INDETERMINADA` ou revisão humana. Correto para decisões regulatórias; mas classificação ausente, FreshnessProfile ausente e OfflineCapabilityProfile ausente também negam por padrão. No bootstrap do sistema, quando quase nenhum perfil existe, quase tudo falha fechado. O plano não diz como os perfis mínimos iniciais nascem (seed autorizado? passo próprio?). Vale um passo explícito de "perfis mínimos de bootstrap".

**Tratado no plano:** foi criado passo futuro de bootstrap mínimo, idempotente, versionado e auditável, derivado apenas dos casos de uso já aprovados e sem permissões universais.

**26 ADRs aceitas em 2 dias, um decisor.** As alternativas registradas são plausíveis, mas o processo não teve contraditório real. O risco não é o conteúdo — é que "Aceita" sinaliza um peso de revisão que não ocorreu. Mitigação barata: registrar nas ADRs que a aceitação é de fundador único e que a primeira implementação de cada tema pode reabri-las sem cerimônia.

**Congelamento × custo de mudança.** O congelamento como "visão de destino" foi a resposta certa à crítica anterior. Mas achados como 2.2 mostram que o congelado contém erros; a regra de alteração ("corrigir contradição ou erro material") cobre esses casos — use-a agora, enquanto mudar é editar texto e não migrar dados.

---

## 5. O que está forte (e deve ser preservado)

A tríade Claim/Evidence/Fact com verificação, admissibilidade e confiança separadas; a decisão de manter contratos técnicos (IntegrityCheckpoint, VerificationBundle, CacheProfile) fora do Domain até aprovação — disciplina que quase nenhum projeto mantém; a temporalidade multi-instante (`occurred_at` / `recorded_at` / `known_at` / `effective_from`); RLS com FORCE + runtime sem ownership de tabela + categorias de tabela declaradas em migration; e o plano de implementação com validação manual observável por passo. O congelamento explícito dos documentos de destino resolveu a principal crítica estrutural da análise anterior.

---

## 6. Ações recomendadas, em ordem

1. Corrigir agora, por serem baratas e ficarem caras depois: estados da NonConformity para português (2.2) e remover seções residuais de ARCHITECTURE.md (2.1). As correções do limite de linhas e do executor já foram incorporadas ao plano.
2. Renomear ADR-0003 e revisar usos de "isolamento físico" (2.5).
3. Antes do Passo 1.3: definir convenções de API (3.2).
4. Antes do Passo 1.4: cumprir os portões já registrados no plano para ADRs de OIDC Provider e Message Broker concretos (3.3).
5. Executar o passo de perfis mínimos de bootstrap incluído no plano somente após existirem casos de uso aprovados que definam seu conteúdo.
6. Numerar proibições do DOMAIN §24 para rastreabilidade de testes (3.5).
7. Refinar a lacuna de compartilhamento em escala, já registrada como decisão futura no plano, somente quando o caso de uso justificar ADR própria (3.4).
