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

# -- Permissões --------------------------------------------------------------

ANIMAL_CRIAR: Final = "LIVESTOCK_ANIMAL.CRIAR"
MEDICATION_CRIAR: Final = "LIVESTOCK_MEDICATION.CRIAR"
TREATMENT_REGISTRAR: Final = "LIVESTOCK_TREATMENT.REGISTRAR"
# Uma permissão de caso de uso, e não uma por etapa. Avaliar e decidir são
# conceitos distintos no Core, mas separá-los aqui só se justifica quando
# existirem atores diferentes para cada um — o que hoje não acontece.
ELIGIBILITY_EXECUTAR: Final = "LIVESTOCK_ELIGIBILITY.EXECUTAR"
TIMELINE_LER: Final = "LIVESTOCK_TIMELINE.LER"
DOSSIER_LER: Final = "DOSSIER.LER"

LIVESTOCK_PERMISSIONS: Final = frozenset(
    {
        ANIMAL_CRIAR,
        MEDICATION_CRIAR,
        TREATMENT_REGISTRAR,
        ELIGIBILITY_EXECUTAR,
        TIMELINE_LER,
        DOSSIER_LER,
    }
)

# -- Papéis ------------------------------------------------------------------

OPERADOR_PECUARIO: Final = "OPERADOR_PECUARIO"
AUDITOR: Final = "AUDITOR"

ROLE_PERMISSIONS: Final = {
    OPERADOR_PECUARIO: frozenset(
        {
            ANIMAL_CRIAR,
            MEDICATION_CRIAR,
            TREATMENT_REGISTRAR,
            ELIGIBILITY_EXECUTAR,
        }
    ),
    # Auditor não escreve nada. É o que torna o teste negativo inequívoco.
    AUDITOR: frozenset({TIMELINE_LER, DOSSIER_LER}),
}
