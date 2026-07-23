# Verificação Externa

Este documento especifica como um terceiro verifica uma decisão do **Titan Core** sem depender do Titan: o pacote autossuficiente que viaja (`VerificationBundle`) e a API hospedada que o avalia por conveniência.

> **Estado:** cobre os passos **7.6** e **7.7**. A representação PDF (passo 7.8) foi adiada por decisão registrada e não existe.

Um princípio governa o marco inteiro:

> **A independência é propriedade do formato, não do serviço.** O verificador local elimina a dependência do Titan porque o terceiro inspeciona a implementação. A API hospedada é conveniência, e exige confiar na instância.

---

## 1. O pacote de verificação (`VerificationBundleService`)

### O que é?
Manifesto protegido mais os bytes dos componentes declarados, com assinatura, material temporal e material de revogação, empacotados para viajar como texto.

### Para que serve?
Entregar a um auditor, parceiro ou órgão algo que ele consiga verificar **sozinho**, sem rede, sem segredo e sem o banco do Titan.

### Como montar
```python
from packages.core_application.verification_service import VerificationBundleService
from packages.core_domain.verification import SignatureMaterial

bundle = VerificationBundleService().build_from_dossier(
    dossier=dossie,
    audience="AUDITORIA_EXTERNA",
    created_at=agora,
    signature=SignatureMaterial(
        key_id="chave-institucional-1",
        algorithm="sha256",
        profile="INSTITUTIONAL_SIGNATURE",
        signed_digest="",                 # preenchido pelo serviço com o digest do manifesto
        signature_value=assinatura,
        signed_at=agora,
        certificate_chain=("cert-emissor",),
        revocation_material=("crl-instante-de-referencia",),
    ),
    verification_policy={"perfil_minimo": "INSTITUTIONAL_SIGNATURE"},
    profiles=("INSTITUTIONAL_SIGNATURE",),
    declared_gaps=(),
)
```

Dossiê que não confere com o próprio hash é recusado na montagem: prova não se monta sobre material adulterado.

### O que nunca entra no pacote
`private_key`, `secret`, `token`, `credential`, `pin`, `password` e `organization_context` são recusados na montagem. Conveniência não justifica exportar segredo.

---

## 2. O verificador (`BundleVerifier`)

### Como funciona?
O verificador é **puro**: sem rede, sem segredo, sem banco. Se precisasse do Titan para concluir, o pacote não serviria para verificação externa — que é sua razão de existir.

O resultado **nunca é um booleano**. Oito dimensões respondem separadamente:

| Ordem | Dimensão | Obrigatória | O que responde |
|---|---|---|---|
| 1 | `ESTRUTURA` | sim | componentes presentes conferem com os declarados |
| 2 | `SERIALIZACAO` | sim | a serialização é conhecida pelo verificador |
| 3 | `INTEGRIDADE` | sim | os digests dos componentes conferem |
| 4 | `ASSINATURA` | sim | a assinatura confere contra a âncora fornecida |
| 5 | `TEMPORAL` | sim | o material temporal é coerente |
| 6 | `REVOGACAO` | sim | o material de revogação incorporado é coerente |
| 7 | `COBERTURA` | sim | o escopo declarado está comprovado |
| 8 | `REVOGACAO_ATUAL` | **não** | declarativa: sempre `NAO_EXECUTADA` |

`REVOGACAO_ATUAL` existe para **tornar visível o que o modo offline não faz**, em vez de deixar a ausência passar por confirmação.

```python
from packages.core_domain.verification import BundleVerifier

relatorio = BundleVerifier().verify(
    bundle=bundle,
    verified_at=agora,
    trust_anchors={"chave-institucional-1": valor_publico},
)
```

### Cinco estados, e por que não são quatro

| Estado | Significado |
|---|---|
| `VALIDA` | conferiu |
| `INVALIDA` | não conferiu, com o ponto exato nomeado |
| `INDETERMINADA` | **tentou avaliar e não concluiu** |
| `NAO_APLICAVEL` | não se aplica a este pacote |
| `NAO_EXECUTADA` | **sequer fazia parte do modo** |

`INDETERMINADA` e `NAO_EXECUTADA` não devem ser fundidas. Confundir ausência de material com reprovação acusaria sem base; confundi-la com aprovação daria garantia que ninguém verificou.

### A regra do agregado
**Dimensão obrigatória não avaliada nunca produz agregado válido.** A defesa é redundante de propósito: algoritmo fora da allowlist vira `INDETERMINADA` (houve tentativa sem capacidade), e a regra do agregado recusa explicitamente qualquer obrigatória não avaliada. Um falso verde aqui seria o pior defeito possível do contrato.

Consequência prática: **sem âncora de confiança o veredito é `INDETERMINADA`, nunca `VALIDA`**.

```python
relatorio = BundleVerifier().verify(bundle=bundle, verified_at=agora)   # sem âncora
assert relatorio.status is VerificationStatus.INDETERMINADA
```

### Falhas e ordem
`failures` lista **somente** dimensões `INVALIDA` — classificar indeterminação como falha acusaria sem base. `first_failure` segue a **ordem normativa pública** da tabela acima, e não a ordem interna de execução, para que otimização ou paralelização não alterem a resposta.

```python
if relatorio.failures:
    print(relatorio.first_failure.dimension, relatorio.first_failure.reason_code)
```

### Âncora dentro do pacote não vale
Âncora de confiança incluída no pacote **não é aceita por estar nele**. A confiança vem de fora, do verificador. Aceitá-la seria deixar o material provar a si mesmo.

---

## 3. A API hospedada (`POST /v1/verification/bundles`)

> Contrato definido e aceito na **ADR-0039**, cumprindo o portão da ADR-0010 que exigia ADR antes de URL, métodos e schemas públicos.

### Quando **não** usar
O material submetido é revelado à instância: dossiê, dados pessoais, identificadores, âncoras, IP e horário. **Para material sensível, use o verificador local.**

### Requisição
```http
POST /v1/verification/bundles
Content-Type: application/json

{
  "bundle": { ... },
  "trust_anchors": [
    {
      "anchor_id": "chave-institucional-1",
      "anchor_type": "PUBLIC_KEY",
      "algorithm": "ED25519",
      "encoding": "BASE64URL",
      "value": "...",
      "purpose": "BUNDLE_SIGNATURE"
    }
  ]
}
```

### Erro de contrato nunca se parece com resultado

| Código | Quando |
|---|---|
| `400` | JSON sintaticamente inválido ou chave duplicada |
| `413` | corpo acima de 1 MiB |
| `422` | violação de schema, profundidade acima de 32, pacote irrepresentável |
| `200` | **inclusive para `INVALIDA`** — a requisição foi processada e o resultado é a resposta |

Todos os erros usam RFC 9457 em `application/problem+json`.

### Limites operacionais
Ausência de autenticação de usuário não implica disponibilidade ilimitada: 1 MiB de corpo, 32 componentes, 512 KiB por componente, profundidade 32, 8 âncoras de 8 KiB.

### Resposta
```json
{
  "contract_version": "1.0",
  "verification_profile": "titan-bundle-verification-v1",
  "engine": {"name": "titan-bundle-verifier", "version": "1.0.0"},
  "bundle_reference": {"bundle_id": "...", "bundle_digest": "sha256:..."},
  "aggregate_status": "VALIDA",
  "verified_at": "...",
  "reference_instant": "...",
  "trust_anchors_used": [{"origin": "CALLER_SUPPLIED", "...": "..."}],
  "dimensions": [{"dimension": "ESTRUTURA", "status": "VALIDA", "...": "..."}],
  "gaps": [],
  "warnings": [],
  "limitations": [{"code": "SIGNATURE_VALID_ONLY_AGAINST_CALLER_SUPPLIED_ANCHOR"}]
}
```

Âncoras voltam por **fingerprint, nunca por valor**, e a resposta traz `Cache-Control: no-store`.

### O que a resposta declara sobre si mesma
As `limitations` são parte do contrato, não enfeite. Assinatura válida significa apenas que confere **contra a âncora que o próprio chamador escolheu** — não prova identidade, propriedade nem autorização da chave. Sem essas limitações explícitas, a API prometeria o que não prova.

---

## 4. Notas de integração

- **O pacote viaja como texto** e volta na outra ponta sem banco nem rede. Essa é a propriedade que torna a verificação independente.
- **Rate limiting (`429`), terminação TLS e não captura de corpo por gateway, APM e tracing** são responsabilidades de implantação, declaradas na ADR-0039 e não testáveis no nível da aplicação.
- **PDF não existe** e, quando existir, validar o PDF **não** equivalerá a validar a cadeia Titan.
