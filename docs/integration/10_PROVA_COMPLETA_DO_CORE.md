# Prova Completa do Core

Este documento descreve a prova de ponta a ponta que fecha o **Marco 7**: o que ela encadeia, o que ela garante e o que ela deliberadamente não faz.

> **Estado:** cobre o passo **7.10**. Evidência executável em `tests/integration/test_core_proof_postgresql.py`.

---

## 1. A cadeia

```
autenticação → Organization → evento → evidência → genealogia → regra →
avaliação → decisão → não conformidade → recall → dossiê → sincronização
```

Cada elo **alimenta** o seguinte, e não apenas coexiste com ele:

| Elo | Como se liga ao anterior |
|---|---|
| Evidência | assinada por provider substituível, verificada e registrada |
| Avaliação | consome fato cuja `source_reference` é a evidência assinada |
| Decisão | derivada da avaliação, sem reavaliar nada |
| Não conformidade | aberta a partir do resultado de regra que falhou |
| Recall | percorre a genealogia construída no elo anterior |
| Dossiê | copia política, regras, fatos, avaliação e decisão |
| Sincronização | a operação offline aceita **produz uma relação real do grafo** |

### Vocabulário sem vertical
Os sujeitos são `lote`, `insumo` e `remessa`, e a política é genérica.

> O Core não conhece Livestock. Uma prova escrita com termos de gado esconderia exatamente o acoplamento que ela existe para descartar.

---

## 2. Os quatro critérios de validação

### Substituir providers falsos sem alterar o Core
O **mesmo** `EvidenceService` — mesma classe, mesmo código — assina com `SoftwareSigningProvider` e com um segundo provedor de algoritmo diferente. A chave continua sendo a registrada pelo Core, não uma escolhida pelo provedor.

> Se o Core precisasse mudar para trocar de provedor, a porta não seria uma porta.

### Adulterar cópias para testar integridade
A adulteração é feita na **cópia exportada**, não no banco: é assim que o material viaja, e é aí que a verificação externa precisa recusá-lo.

| Adulteração | Recusada por |
|---|---|
| inverter o resultado da decisão | `compute_dossier_hash` |
| trocar o fato que sustenta a reprovação | `compute_dossier_hash` |
| alterar os bytes do componente do pacote | `BundleVerifier` (`INVALIDA`) |

### Repetir operações
O reenvio do lote recupera o resultado por `OperationId` **sem repetir o efeito oficial**, com `RESULTADO_RECUPERADO` nos códigos de razão.

### Isolamento entre duas Organizations
Uma role temporária `NOLOGIN NOSUPERUSER NOBYPASSRLS` percorre as **treze** tabelas do cenário no contexto da outra Organization e não enxerga nenhum registro.

> Percorrer as treze é deliberado. Provar o isolamento de uma tabela e presumir o das demais seria exatamente o vazamento que este passo existe para descartar.

O usuário `titan` do PostgreSQL local é superusuário e **ignora RLS**: provar isolamento com ele não provaria nada.

---

## 3. Duas propriedades que a prova fixa

### Lacuna nunca vira silêncio
O recall é exercitado nas duas direções:

| Travessia | Resultado |
|---|---|
| retrospectiva sobre cadeia linear | sem lacuna → `CONCLUSIVO` |
| ambas as direções | reencontra o sujeito, declara `CICLO_DETECTADO` → `INCONCLUSIVO` |

O resultado inteiro é rebaixado **mesmo quando o reencontro é inofensivo**. Essa é a escolha conservadora do passo 7.4, e a prova a fixa como comportamento esperado.

### Válido por omissão não existe
O `VerificationBundle` só é declarado `VALIDA` com assinatura, política de verificação **e** âncora de confiança externa. Sem âncora, o veredito é `INDETERMINADA`.

---

## 4. Testes arquiteturais

O portão do Marco 7 exige testes arquiteturais aprovados. Sete fronteiras são verificadas em `tests/architecture/test_dependency_boundaries.py`:

| Fronteira | Regra |
|---|---|
| Packages → apps | pacotes reutilizáveis não importam apps executáveis |
| Core Domain | sem framework, ORM, infraestrutura ou vertical |
| Core Domain → Application | a dependência aponta para dentro |
| Core Application | sem apps nem infraestrutura |
| Core Application → framework | caso de uso não conhece HTTP nem ORM |
| Shared Kernel | é a base do grafo; não depende de quem depende dele |
| Core → verticais | nenhum pacote do Core conhece vertical alguma |

### Um teste que não verificava nada
A checagem de que o Core não importa verticais varria `packages/core` — diretório que **nunca existiu**. Ela passava sem examinar um único arquivo desde que foi escrita.

A correção tem duas partes. A verificação passa a percorrer os pacotes reais, e `require_existing_root` faz **qualquer** fronteira cujo alvo não exista falhar alto.

> Renomear um pacote não pode transformar a verificação em aprovação automática, que é pior do que não ter o teste.

Nenhuma violação real estava escondida atrás dele.

---

## 5. Superfície HTTP pública

No fechamento do Core, a API expõe exatamente:

| Método | Caminho | Natureza |
|---|---|---|
| `GET` | `/health` | técnica |
| `GET` | `/technical/authentication` | técnica |
| `POST` | `/v1/verification/bundles` | verificação externa |

`tests/api/test_core_public_surface.py` congela esse conjunto e falha se um endpoint de domínio aparecer.

> A **API REST de domínio pertence ao passo 10.4** — "endpoints estritamente necessários para operar o cenário já implementado". A guarda obriga essa decisão a passar pelo plano, em vez de entrar despercebida.

---

## 6. Como executar

```powershell
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest tests/integration/test_core_proof_postgresql.py -v
python -m uv run --locked pytest tests/architecture tests/api -v
```

O cenário roda em transação revertida ao final: **a prova não deixa resíduo no banco**.

---

## 7. O que a prova não faz

- **Não aprova o Marco 7.** O portão exige que os critérios sejam *aprovados*, não apenas verdes. A validação manual do responsável é que libera o Marco 8.
- **Passo 7.8** (representação PDF verificável) e **Passo 7.9** (Deep Offline Capability) foram concluídos e validados posteriormente em suítes de testes dedicadas.
- **Não exercita a API de domínio**, que não existe até o passo 10.4.

