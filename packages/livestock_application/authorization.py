"""Permissões e papéis da vertical Titan Livestock (Passo 10.4a).

**Permissão, nunca papel, é o que uma rota exige.** O papel é apenas a forma de
entregar permissões a um vínculo: `User → Membership → Role → Permission`. Uma
rota que perguntasse "é OPERADOR_PECUARIO?" congelaria a organização de papéis
dentro do código HTTP, e criar `VETERINARIO` ou `GERENTE` amanhã exigiria alterar
rota. Perguntando pela permissão, papéis novos entram sem tocar em rota alguma.

Os papéis abaixo são os dois mínimos que a validação manual do PLANO exige — um
que opera e um que só lê. A separação existe para que o teste negativo seja
inequívoco: auditor que tenta registrar tratamento recebe 403, e isso prova que
autorização existe de fato, e não como intenção.
"""

from typing import Final

from packages.livestock_domain.entity_type_request import EntityKind

# -- Permissões --------------------------------------------------------------

ANIMAL_CRIAR: Final = "LIVESTOCK_ANIMAL.CRIAR"
ANIMAL_LER: Final = "LIVESTOCK_ANIMAL.LER"
# Declarar a saída é irreversível e fecha a história do animal: quem cadastra não
# é necessariamente quem atesta morte, abate ou venda. Permissão própria deixa
# essa separação possível sem código novo.
ANIMAL_REGISTRAR_SAIDA: Final = "LIVESTOCK_ANIMAL.REGISTRAR_SAIDA"
# A genealogia tem permissões próprias porque atravessa o rebanho inteiro: quem
# lê ascendência enxerga animais que não estão sob sua responsabilidade direta, e
# quem a declara afirma linhagem — que é o que dá valor comercial ao registro.
ANIMAL_REGISTRAR_GENEALOGIA: Final = "LIVESTOCK_ANIMAL.REGISTRAR_GENEALOGIA"
ANIMAL_LER_GENEALOGIA: Final = "LIVESTOCK_ANIMAL.LER_GENEALOGIA"
# O parto cria animais e declara linhagem num ato só — é a origem da identidade
# do rebanho, e quem a registra decide o que passa a existir.
REPRODUCTION_REGISTRAR: Final = "LIVESTOCK_REPRODUCTION.REGISTRAR"
REPRODUCTION_LER: Final = "LIVESTOCK_REPRODUCTION.LER"
MEDICATION_CRIAR: Final = "LIVESTOCK_MEDICATION.CRIAR"
MEDICATION_LER: Final = "LIVESTOCK_MEDICATION.LER"
TREATMENT_REGISTRAR: Final = "LIVESTOCK_TREATMENT.REGISTRAR"
TREATMENT_LER: Final = "LIVESTOCK_TREATMENT.LER"
SANITARY_CAMPAIGN_CRIAR: Final = "LIVESTOCK_SANITARY_CAMPAIGN.CRIAR"
SANITARY_CAMPAIGN_LER: Final = "LIVESTOCK_SANITARY_CAMPAIGN.LER"
PROPERTY_CRIAR: Final = "LIVESTOCK_PROPERTY.CRIAR"
PROPERTY_LER: Final = "LIVESTOCK_PROPERTY.LER"
# A geometria é dado sensível de localização: o polígono revela onde a operação
# fica, e derivados como bounding box e centroide revelam quase o mesmo. Ler o
# cadastro da propriedade não deve implicar ler o limite dela.
PROPERTY_REGISTRAR_GEOMETRIA: Final = "LIVESTOCK_PROPERTY.REGISTRAR_GEOMETRIA"
PROPERTY_LER_GEOMETRIA: Final = "LIVESTOCK_PROPERTY.LER_GEOMETRIA"
LOT_CRIAR: Final = "LIVESTOCK_LOT.CRIAR"
LOT_LER: Final = "LIVESTOCK_LOT.LER"
VETERINARIAN_CRIAR: Final = "LIVESTOCK_VETERINARIAN.CRIAR"
VETERINARIAN_LER: Final = "LIVESTOCK_VETERINARIAN.LER"
MOVEMENT_REGISTRAR: Final = "LIVESTOCK_MOVEMENT.REGISTRAR"
MOVEMENT_LER: Final = "LIVESTOCK_MOVEMENT.LER"
# Uma permissão de caso de uso, e não uma por etapa. Avaliar e decidir são
# conceitos distintos no Core, mas separá-los aqui só se justifica quando
# existirem atores diferentes para cada um — o que hoje não acontece.
ELIGIBILITY_EXECUTAR: Final = "LIVESTOCK_ELIGIBILITY.EXECUTAR"
DECISION_REVIEW_EXECUTE: Final = "LIVESTOCK_DECISION_REVIEW.EXECUTE"
TIMELINE_LER: Final = "LIVESTOCK_TIMELINE.LER"
DOSSIER_LER: Final = "DOSSIER.LER"
# Importar asserções de qualificação (ADR-0045) grava fato de terceiro sobre
# estabelecimento, que alimenta elegibilidade de mercado — permissão própria,
# distinta de registrar saída ou contraparte.
ESTABLISHMENT_QUALIFICATION_ASSERTION_IMPORTAR: Final = (
    "LIVESTOCK_ESTABLISHMENT_QUALIFICATION_ASSERTION.IMPORTAR"
)
ESTABLISHMENT_QUALIFICATION_ASSERTION_LER: Final = (
    "LIVESTOCK_ESTABLISHMENT_QUALIFICATION_ASSERTION.LER"
)
# Registrar uma transformação (ADR-0046) cria itens rastreáveis novos e consome
# um animal definitivamente — permissão própria porque a operação é o começo da
# rastreabilidade de produto, distinta de registrar saída do rebanho.
TRANSFORMATION_REGISTRAR: Final = "LIVESTOCK_TRANSFORMATION.REGISTRAR"
# Recall (Passo 7.4) percorre o grafo de relações além do que a linha do tempo
# de um único sujeito mostra — a mesma razão que separou ANIMAL_LER_GENEALOGIA
# de ANIMAL_LER. Permissão própria, distinta de TIMELINE_LER.
TRACEABILITY_LER: Final = "LIVESTOCK_TRACEABILITY.LER"
# Decidir um EntityTypeRequest concede Membership e Role de verdade (ADR-0031
# proíbe autoatribuição) — por isso é permissão própria, distinta de só
# enxergar a fila de pedidos pendentes. Fica **fora** de LEITURA/ESCRITA de
# propósito: se entrasse lá, todo OPERADOR_PECUARIO ganharia autoridade de
# aprovar gente na Organization sem essa decisão ter sido tomada de verdade.
ENTITY_TYPE_REQUEST_LER: Final = "LIVESTOCK_ENTITY_TYPE_REQUEST.LER"
ENTITY_TYPE_REQUEST_DECIDIR: Final = "LIVESTOCK_ENTITY_TYPE_REQUEST.DECIDIR"
EXTERNAL_SOURCE_CAPTURE_LER: Final = "LIVESTOCK_EXTERNAL_SOURCE_CAPTURE.LER"
EXTERNAL_SOURCE_CAPTURE_REVIEW: Final = "LIVESTOCK_EXTERNAL_SOURCE_CAPTURE.REVIEW"
TERRITORIAL_CAPTURE_SYNTHETIC_CREATE: Final = "LIVESTOCK_TERRITORIAL_CAPTURE.SYNTHETIC_CREATE"
TERRITORIAL_CAPTURE_READ: Final = "LIVESTOCK_TERRITORIAL_CAPTURE.READ"

# A leitura é permissão própria por área, e não uma só para tudo. Papel de
# consulta restrita — um comprador que só precisa ver o dossiê, um técnico que só
# vê tratamentos — deixa de exigir código novo para existir.
LEITURA: Final = frozenset(
    {
        ANIMAL_LER,
        MEDICATION_LER,
        TREATMENT_LER,
        SANITARY_CAMPAIGN_LER,
        PROPERTY_LER,
        LOT_LER,
        VETERINARIAN_LER,
        MOVEMENT_LER,
        TIMELINE_LER,
        DOSSIER_LER,
        ANIMAL_LER_GENEALOGIA,
        REPRODUCTION_LER,
        PROPERTY_LER_GEOMETRIA,
        ESTABLISHMENT_QUALIFICATION_ASSERTION_LER,
        TRACEABILITY_LER,
        EXTERNAL_SOURCE_CAPTURE_LER,
        TERRITORIAL_CAPTURE_READ,
    }
)

ESCRITA: Final = frozenset(
    {
        ANIMAL_CRIAR,
        ANIMAL_REGISTRAR_SAIDA,
        ANIMAL_REGISTRAR_GENEALOGIA,
        REPRODUCTION_REGISTRAR,
        PROPERTY_REGISTRAR_GEOMETRIA,
        MEDICATION_CRIAR,
        TREATMENT_REGISTRAR,
        SANITARY_CAMPAIGN_CRIAR,
        PROPERTY_CRIAR,
        LOT_CRIAR,
        VETERINARIAN_CRIAR,
        MOVEMENT_REGISTRAR,
        ELIGIBILITY_EXECUTAR,
        DECISION_REVIEW_EXECUTE,
        ESTABLISHMENT_QUALIFICATION_ASSERTION_IMPORTAR,
        TRANSFORMATION_REGISTRAR,
        EXTERNAL_SOURCE_CAPTURE_REVIEW,
        TERRITORIAL_CAPTURE_SYNTHETIC_CREATE,
    }
)

# Administração da própria Organization (hoje: decidir EntityTypeRequest) —
# deliberadamente separada de LEITURA/ESCRITA, que qualquer operador ganha.
ADMINISTRACAO: Final = frozenset({ENTITY_TYPE_REQUEST_LER, ENTITY_TYPE_REQUEST_DECIDIR})

LIVESTOCK_PERMISSIONS: Final = LEITURA | ESCRITA | ADMINISTRACAO

# -- Papéis ------------------------------------------------------------------

OPERADOR_PECUARIO: Final = "OPERADOR_PECUARIO"
AUDITOR: Final = "AUDITOR"
# Concede e nega EntityTypeRequest — nada além disso. Um admin com toda LEITURA
# ou ESCRITA sem evidência de necessidade seria conveniência, não capacidade
# comprovada; ampliar exige incremento próprio quando o caso de uso aparecer.
ADMIN_MESTRE: Final = "ADMIN_MESTRE"
# Estes três ainda não têm capacidade própria definida no domínio — nasceram do
# catálogo de tipos de entidade (EntityKind) antes de qualquer caso de uso
# concreto usá-los. Um Role sem Permission é honesto: aprovar o pedido já entrega
# o vínculo à Organization, e a capacidade chega em incremento futuro, quando
# existir.
FRIGORIFICO: Final = "FRIGORIFICO"
VETERINARIO: Final = "VETERINARIO"
CERTIFICADOR: Final = "CERTIFICADOR"
CONSUMIDOR: Final = "CONSUMIDOR"

ROLE_PERMISSIONS: Final = {
    # O operador lê o que opera: cadastrar sem poder consultar o que se cadastrou
    # não é um papel utilizável. O dossiê fica de fora — a prova é do auditor.
    OPERADOR_PECUARIO: ESCRITA | (LEITURA - frozenset({DOSSIER_LER})),
    # Auditor não escreve nada. É o que torna o teste negativo inequívoco.
    AUDITOR: LEITURA,
    ADMIN_MESTRE: ADMINISTRACAO,
    FRIGORIFICO: frozenset(),
    VETERINARIO: frozenset(),
    CERTIFICADOR: frozenset(),
    CONSUMIDOR: frozenset(),
}

# Mapeia cada EntityKind (o que a pessoa pediu para ser) ao Role concedido
# quando o pedido é aprovado. PRODUTOR e AUDITOR reaproveitam papéis que já
# existem — "Produtor e funcionários" é exatamente o que OPERADOR_PECUARIO já
# significa — em vez de duplicar o mesmo conjunto de permissões sob outro nome.
ENTITY_KIND_ROLE_NAMES: Final = {
    EntityKind.ADMIN: ADMIN_MESTRE,
    EntityKind.PRODUTOR: OPERADOR_PECUARIO,
    EntityKind.FRIGORIFICO: FRIGORIFICO,
    EntityKind.VETERINARIO: VETERINARIO,
    EntityKind.AUDITOR: AUDITOR,
    EntityKind.CERTIFICADOR: CERTIFICADOR,
    EntityKind.CONSUMIDOR: CONSUMIDOR,
}
