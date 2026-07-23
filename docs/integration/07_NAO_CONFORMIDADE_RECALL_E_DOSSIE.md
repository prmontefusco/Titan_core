# Não Conformidade, Recall e Dossiê

Este documento especifica como o **Titan Core** trata pendências que exigem correção, navega a genealogia para localizar o que foi potencialmente afetado, e produz o dossiê autocontido que permite verificar uma decisão sem acesso ao banco.

> **Estado:** cobre os passos **7.3**, **7.4** e **7.5**. Pacote de verificação, API de verificação externa, representação PDF e sincronização serão acrescentados conforme forem entregues.

Dois princípios atravessam o marco:

1. **Encerrar não apaga.** Todo histórico é acrescentado, jamais sobrescrito.
2. **Lacuna é declarada, nunca silenciada.** Resultado incompleto é marcado como tal.

---

## 1. Não conformidade (`NonConformityService`)

### O que é?
Registro auditável de falha, lacuna ou condição que exige tratamento, com origem, severidade, período afetado, responsável, prazo, ação corretiva, evidência de correção e reavaliação.

### Para que serve?
Transformar um resultado de regra que falhou em um caso acompanhável até o encerramento, sem perder o rastro de como se chegou lá.

### Como funciona?

```
DETECTADA → CLASSIFICADA → ATRIBUIDA → EM_CORRECAO → PRONTA_PARA_REAVALIACAO → ENCERRADA
                                            ▲                    │
                                            └────────────────────┘
                                          (reavaliação reprovou)
```

Pular etapas é recusado, e `ENCERRADA` é terminal. O **único retorno permitido** devolve o caso de `PRONTA_PARA_REAVALIACAO` para `EM_CORRECAO` — porque corrigir nem sempre resolve na primeira tentativa. A tentativa rejeitada permanece no histórico.

### Abertura a partir de uma avaliação
```python
from packages.core_application.nonconformity_service import NonConformityService
from packages.core_infrastructure.persistence.nonconformity import (
    TransactionalNonConformityRepository,
)

service = NonConformityService(
    repository=TransactionalNonConformityRepository(connection=db_connection)
)

abertas = service.open_from_evaluation(avaliacao)
```

Apenas resultados que exigem tratamento abrem caso:

| Resultado da regra | Origem registrada |
|---|---|
| `NAO_ATENDIDA` | `REGRA_NAO_ATENDIDA` |
| `PENDENTE` | `EVIDENCIA_AUSENTE` |
| `INDETERMINADA` | `DIVERGENCIA_ENTRE_FONTES` |
| `ATENDIDA` / `NAO_APLICAVEL` | *não gera registro* |

Tratar o que não falhou transformaria a lista de pendências em ruído.

### Ciclo de tratamento
```python
nc = service.classify(nc.nonconformity_id, occurred_at=agora)
nc = service.assign(nc.nonconformity_id, responsible_reference=resp, due_date=prazo, occurred_at=agora)
nc = service.start_correction(nc.nonconformity_id, occurred_at=agora)
nc = service.submit_for_reevaluation(
    nc.nonconformity_id,
    correction_evidence_references=[referencia_da_evidencia],  # obrigatório
    occurred_at=agora,
)
nc = service.close_with_reevaluation(nc.nonconformity_id, reavaliacao, occurred_at=agora)
```

### Garantias
- **Correção exige prova.** Submeter à reavaliação sem evidência é recusado — encerrar viraria declaração.
- **Encerrar exige a `Evaluation` que reavaliou**, e avaliação não reproduzível é rejeitada.
- **O encerramento depende do resultado.** Se a reavaliação ainda aponta descumprimento, `close_with_reevaluation` **devolve o caso à correção** em vez de encerrá-lo.
- **Histórico só cresce**, reforçado no banco por `CHECK (jsonb_array_length(transitions) > 0)` e exigência de `closed_at` quando encerrada.

### Navegabilidade
A `origin_reference` aponta para a `Evaluation` que originou o caso, e ela preserva o snapshot completo dos fatos. É o fio que leva da pendência até os fatos e evidências que a justificam.

---

## 2. Recall (`RecallService`)

### O que é?
Navegação retrospectiva e prospectiva pela genealogia para localizar sujeitos e decisões **potencialmente afetados**.

### Para que serve?
Responder "o que mais pode ter sido atingido por isto?" de forma explicável e delimitada.

### Como funciona?
Travessia em largura sobre as relações do Passo 7.1, com limites explícitos. A largura é proposital: o caminho mais curto até um sujeito é o mais fácil de explicar.

```python
from packages.core_application.recall_service import RecallService
from packages.core_domain.recall import RecallDirection, RecallMode, RecallRequest

resultado = RecallService(
    relations=relation_repository,
    decisions=PostgresAffectedDecisionLookup(connection=db_connection),
    result_repository=TransactionalRecallRepository(connection=db_connection),
).execute(
    RecallRequest(
        organization_id=org_id,
        subject_reference=sujeito,
        direction=RecallDirection.AMBAS,
        mode=RecallMode.INCIDENTE,
        at_time=instante,          # janela temporal
        max_depth=5,
        max_nodes=500,
        relation_types=("transformacao",),
    )
)
```

### Explicar cada caminho
```python
for sujeito in resultado.affected_subjects():
    for caminho in resultado.paths_to(sujeito):
        print(caminho.explain())
        # subject:abc --[transformacao]--> subject:def --[transformacao]--> subject:ghi
```

### Lacuna nunca vira silêncio
Qualquer limite atingido gera `RecallGap` explícita e torna o resultado **inteiro** inconclusivo:

| Razão | Quando ocorre |
|---|---|
| `PROFUNDIDADE_MAXIMA` | parou no limite havendo relações por percorrer |
| `LIMITE_DE_NOS` | teto de nós atingido |
| `CICLO_DETECTADO` | sujeito já visitado nesta travessia |

```python
if not resultado.is_conclusive:
    for explicacao in resultado.explain_gaps():
        print(explicacao)
```

Omitir a lacuna transformaria desconhecimento em falsa cobertura — alguém concluiria que nada mais foi afetado quando a busca apenas parou.

### Simulação e incidente
| Modo | Comportamento |
|---|---|
| `SIMULACAO` | hipótese; **não** deixa rastro |
| `INCIDENTE` | ato auditável; **não executa sem repositório** e é gravado por inteiro |

### O resultado localiza, não julga
Sujeitos alcançados são **potencialmente afetados**: indica necessidade de revisão. Não significa inválido, não declara culpa, fraude, obrigatoriedade nem extensão final de recall, e não modifica Decision, Dossier, assinatura ou Evidence alguma.

---

## 3. Dossiê (`DossierService`)

### O que é?
Snapshot imutável e **autocontido** de uma decisão e da avaliação que a sustenta.

### Para que serve?
Permitir compreender e verificar a decisão **sem depender de consultas ao banco** — é o artefato que se entrega a um auditor, a um parceiro ou a um órgão.

### Como funciona?
O dossiê **copia o conteúdo em vez de referenciá-lo**:

```
document
├── policy            código, nome, versão, status, vigência
├── rules[]           incluindo as condições declarativas de cada regra
├── facts             snapshot COMPLETO dos fatos, com payloads
├── evaluation        resultado por regra, hashes, versão do motor
├── decision          resultado, razões, ações corretivas
├── evidences[]       referências que sustentam os fatos
└── nonconformities[] com histórico de transições
```

Um dossiê que guardasse apenas identificadores exigiria o banco do Titan para ser compreendido — exatamente o que ele existe para evitar.

### Como utilizar no código Python:
```python
from packages.core_application.dossier_service import DossierService
from packages.core_infrastructure.persistence.dossier import TransactionalDossierRepository

dossier = DossierService(
    repository=TransactionalDossierRepository(connection=db_connection)
).build_and_store(
    decision=decisao,
    evaluation=avaliacao,
    policy=politica,
    rules=[regra],
    nonconformities=[nc],
)
```

### Verificação offline
```python
from packages.core_domain.dossier import compute_dossier_hash

documento = json.loads(json_exportado)
assert compute_dossier_hash(documento) == hash_publicado
```

O digest usa a serialização canônica **`titan-json-v1`**, já adotada pelo Core, e não um formato próprio. Um dossiê que só o Titan consegue verificar não serve para verificação externa.

### Reproduzir a decisão sem o banco
```python
condicao = documento["rules"][0]["conditions"][0]
fato = next(
    f for f in documento["facts"]["facts"] if f["fact_type"] == condicao["fact_type"]
)
satisfeita = fato["payload"][condicao["payload_key"]] == condicao["expected_value"]
# confere com documento["evaluation"]["rule_results"][0]["status"]
```

### Garantias
- **Prova não se monta sobre material adulterado.** Evaluation ou Decision não reproduzíveis são recusadas.
- **Coerência exigida.** Decisão de outra avaliação ou de outra política é recusada.
- **Qualquer alteração quebra o hash**, inclusive mudar somente o resultado da decisão.

---

## 4. Notas de integração

- **Isolamento**: `core_audit.nonconformities`, `core_audit.recalls` e `core_audit.dossiers` aplicam RLS por Organization.
- **O PDF ainda não existe.** Conforme o plano, o PDF será uma representação posterior e independente do dossiê; validar o PDF nunca equivalerá a validar a cadeia Titan.
- **Verificação externa por terceiros** (pacote autossuficiente com assinaturas, timestamps e material de revogação) é o Passo 7.6 e ainda não foi entregue.
