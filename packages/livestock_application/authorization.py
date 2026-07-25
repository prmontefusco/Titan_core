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
TIMELINE_LER: Final = "LIVESTOCK_TIMELINE.LER"
DOSSIER_LER: Final = "DOSSIER.LER"

# A leitura é permissão própria por área, e não uma só para tudo. Papel de
# consulta restrita — um comprador que só precisa ver o dossiê, um técnico que só
# vê tratamentos — deixa de exigir código novo para existir.
LEITURA: Final = frozenset(
    {
        ANIMAL_LER,
        MEDICATION_LER,
        TREATMENT_LER,
        PROPERTY_LER,
        LOT_LER,
        VETERINARIAN_LER,
        MOVEMENT_LER,
        TIMELINE_LER,
        DOSSIER_LER,
        ANIMAL_LER_GENEALOGIA,
        REPRODUCTION_LER,
        PROPERTY_LER_GEOMETRIA,
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
        PROPERTY_CRIAR,
        LOT_CRIAR,
        VETERINARIAN_CRIAR,
        MOVEMENT_REGISTRAR,
        ELIGIBILITY_EXECUTAR,
    }
)

LIVESTOCK_PERMISSIONS: Final = LEITURA | ESCRITA

# -- Papéis ------------------------------------------------------------------

OPERADOR_PECUARIO: Final = "OPERADOR_PECUARIO"
AUDITOR: Final = "AUDITOR"

ROLE_PERMISSIONS: Final = {
    # O operador lê o que opera: cadastrar sem poder consultar o que se cadastrou
    # não é um papel utilizável. O dossiê fica de fora — a prova é do auditor.
    OPERADOR_PECUARIO: ESCRITA | (LEITURA - frozenset({DOSSIER_LER})),
    # Auditor não escreve nada. É o que torna o teste negativo inequívoco.
    AUDITOR: LEITURA,
}
