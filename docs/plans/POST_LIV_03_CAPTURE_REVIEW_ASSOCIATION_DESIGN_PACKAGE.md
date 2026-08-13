# POST-LIV-03 — Revisão humana e associação de captura simulada

Status: PROPOSTA  
Design status: AGUARDANDO_REVISAO_HUMANA  
Implementation gate: BLOCKED_PENDING_HUMAN_APPROVAL  
Date: 2026-08-12  
Artifact ID: `POST-LIV-03-REVIEW-DP-v1`

## 1. Ponto de partida

O Corte 2 criou `ExternalSourceCaptureArtifact` com RLS, digest, resultado técnico e
parser. Ele deliberadamente não persiste resposta bruta, Fact, Evidence, coverage ou
associação a Animal.

Esse limite é seguro, mas produz uma consequência objetiva: **um revisor não consegue
avaliar a associação vendo apenas digest e código de diagnóstico.** Expor API agora
seria apenas publicar metadados insuficientes para uma revisão significativa.

## 2. Objetivo

Permitir que um operador autorizado examine uma projeção mínima, determinística e
imutável do material simulado e registre uma decisão humana de associação candidata a
Animal local, sem fundir identidades, alterar Animal, criar continuidade, importar Facts
ou afirmar qualidade/admissibilidade do material.

## 3. Decisão proposta

Estender o artefato já aceito, sem criar segundo aggregate, com uma
`review_projection` canônica e minimizada, produzida exclusivamente pelo parser
versionado no instante da captura.

```text
ExternalSourceCaptureArtifact
  ... anchors já persistidos
  review_projection
    resource_kind
    external_reference
    declared_fields[]             # somente allowlist do resource
    parser_version
    projection_digest
```

Para o simulador, a allowlist inicial é deliberadamente estreita:

| Recurso | Campos visíveis na revisão |
|---|---|
| Animal | `numero`, `statusAnimal`, `ERASPropriedadeLocalizacao` |
| GTA | `numeroCompleto`, `status`, `dataEmissao`, ERAS origem/destino |
| Movimentação | `id`, `statusMovimentacao`, referências declaradas de GTA e Animal |

Não serão persistidos corpo bruto, JWT, headers, credenciais, CPF/CNPJ, e-mail, nome de
produtor, UUID técnico da fonte fora da referência externa estritamente necessária ou
qualquer campo não listado. O `projection_digest` é calculado sobre a projeção canônica;
ele não alegará verificar a resposta original, cujo digest continua separado.

Essa extensão exige **adendo aprovado à ADR-0058**, pois o contrato aceito atual não
inclui a projeção persistida.

## 4. Associação humana: significado estreito

O ato será registrado como `ExternalSourceCaptureAssociationReview`, append-only,
tenant-scoped e ancorado numa única captura e num único Animal candidato.

```text
ExternalSourceCaptureAssociationReview
  review_id
  capture_artifact_id
  candidate_animal_id
  status = CONFIRMED_CANDIDATE | REJECTED | NEEDS_MORE_EVIDENCE
  basis_code
  limitations[]
  reviewed_by / reviewed_at
```

`CONFIRMED_CANDIDATE` significa apenas:

> “O revisor confirma que esta captura deve ser considerada para o Animal local indicado
> no próximo fluxo aprovado.”

Ele não significa identidade civil/registral confirmada, continuidade entre tenants,
transferência de custody, validade de GTA, movimentação ocorrida, origem oficial,
admissibilidade, coverage ou elegibilidade.

Um Animal pode receber várias reviews; uma captura pode receber reviews conflitantes.
Não haverá estado “vinculado” no Animal nem substituição de review anterior. Conflito é
visível, não resolvido por último registro.

## 5. Corte proposto

### Corte 2B — captura revisável e review semântico mínimo

1. aprovar adendo à ADR-0058 para `review_projection` e review de associação;
2. persistir a projeção canônica allowlisted na mesma tabela do artefato, com migration
   aditiva e RLS;
3. criar tabela append-only de reviews, também RLS;
4. expor somente leitura de captura e comando explícito de review, com permissões novas
   e roteiro em `apps/validacao` que descobre Organization/Animal;
5. testar RLS, rejeição de tenant cruzado, ausência/ambiguidade de candidato, projeção
   imutável, conflito de reviews e ausência de efeitos sobre Animal/Facts/coverage.

## 6. Proibições verificáveis

- nenhum endpoint aceita corpo externo, URL, token ou credencial;
- nenhum endpoint captura HTTP: o adapter concreto continua posterior;
- review não altera identificador, `Animal`, `PropertyStay`, `AnimalMovement`, Fact,
  Evidence, coverage, Assertion, Evaluation, Decision ou Dossier;
- o simulador permanece `SIMULATED` em todas as leituras e reviews;
- resposta 404/vazia/erro não permite review positiva de inexistência;
- coincidência de `OFFICIAL_SISBOV` apenas pode fundamentar `basis_code`; não é fusão.

## 7. Alternativas rejeitadas

### Expor somente digest e diagnóstico

Rejeitada: não permite revisão humana material, apenas clique formal.

### Persistir todo o JSON bruto no PostgreSQL

Rejeitada neste corte: mistura material externo potencialmente sensível com dados
operacionais e amplia retenção/visibilidade sem necessidade demonstrada. Retenção de
material bruto deverá reutilizar Documents/armazenamento protegido quando surgir caso
concreto.

### Colocar `capture_artifact_id` ou estado de associação no Animal

Rejeitada: um Animal pode ter múltiplas capturas e opiniões; esse atalho esconderia
conflitos e transformaria revisão em identidade implícita.

### Converter review diretamente em Fact importado

Rejeitada: review de associação e admissibilidade de conteúdo são decisões distintas.

## 8. Próximo portão

Aprovar este package e o adendo correspondente da ADR-0058. Só então implementar o
Corte 2B. O Corte 3 — mapeamento de Facts e coverage — continua bloqueado até existir
campo específico, Policy consumidora e regra de admissibilidade aprovados.
