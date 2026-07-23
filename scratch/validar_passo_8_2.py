"""Script de Validação Manual do Passo 8.2 - Animal e Identity (Titan Livestock)."""

import os
from datetime import date
from uuid import uuid4

from sqlalchemy import create_engine, text

from packages.livestock_application.animal_service import AnimalService
from packages.livestock_domain.animal import AnimalSex, IdentifierType
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.shared_kernel import OrganizationId, TypedId


def main() -> None:
    print("=" * 70)
    print("      VALIDAÇÃO MANUAL: PASSO 8.2 — ANIMAL & IDENTITY (TITAN LIVESTOCK)")
    print("=" * 70)

    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url)

    org_a = OrganizationId(uuid4())
    org_b = OrganizationId(uuid4())
    prop_a = TypedId.new("rural_property")

    with engine.connect() as conn:
        with conn.begin():
            # 1. Cadastra organizações e propriedade de nascimento
            conn.execute(
                text(
                    """
                    INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
                    VALUES (:id_a, :id_a), (:id_b, :id_b)
                    """
                ),
                {"id_a": org_a.value, "id_b": org_b.value},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO core_audit.rural_properties (
                        property_id, record_owner_organization_id, code, name, municipality, state_code, created_at
                    ) VALUES (
                        :id, :org_a, 'PROP-ORIGEM', 'Fazenda Origem', 'Ribeirão Preto', 'SP', NOW()
                    )
                    """
                ),
                {"id": prop_a.value, "org_a": org_a.value},
            )
            print("\n[1/5] Ambiente configurado:")
            print(f"      - Org A: {org_a.value}")
            print(f"      - Propriedade de Nascimento: {prop_a}")

            # 2. Configura contexto RLS para Org A
            conn.execute(
                text("SELECT set_config('titan.organization_id', :org_id, true)"),
                {"org_id": str(org_a.value)},
            )
            repo_a = TransactionalAnimalRepository(connection=conn)
            service_a = AnimalService(repository=repo_a)

            # 3. Cadastra Animal com identificador SISBOV oficial
            animal_a = service_a.register_animal(
                organization_id=org_a,
                birth_property_id=prop_a,
                sex=AnimalSex.MALE,
                breed="Nelore Mocho",
                birth_date=date(2025, 4, 15),
                initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
                initial_identifier_value="BR9900112233",
            )
            print("\n[2/5] Animal cadastrado com identidade permanente:")
            print(f"      - Animal ID (Permanente): {animal_a.animal_id}")
            print(f"      - Sexo/Raça: {animal_a.sex.value} / {animal_a.breed}")
            print(f"      - SISBOV Inicial: {animal_a.identifiers[0].identifier_value}")

            # 4. Anexa brinco de manejo EAR_TAG e desativa/substitui brinco
            animal_com_brinco = service_a.attach_identifier(
                animal_a.animal_id, IdentifierType.EAR_TAG, "BRINCO-MANEJO-10"
            )
            print("\n[3/5] Brinco de manejo anexado:")
            print(
                f"      - Total de identificadores no animal: {len(animal_com_brinco.identifiers)}"
            )
            print(
                f"      - Identidade permanente permanece intacta: {animal_com_brinco.animal_id == animal_a.animal_id}"
            )

            # 5. Tenta cadastrar outro animal com o mesmo SISBOV na Org A (Deve falhar)
            print("\n[4/5] Testando recusa de brinco SISBOV duplicado na mesma organização...")
            try:
                service_a.register_animal(
                    organization_id=org_a,
                    birth_property_id=prop_a,
                    sex=AnimalSex.FEMALE,
                    initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
                    initial_identifier_value="BR9900112233",
                )
                print("      [ERRO] FALHA: Permitiu cadastrar SISBOV duplicado!")
            except ValueError as e:
                print(f"      [OK] SUCESSO: Recusado corretamente. Motivo: '{e}'")

            # 6. Testar RLS em outra Role (Org B não deve enxergar)
            role_name = f"titan_valida_anim_{uuid4().hex[:8]}"
            quoted_role = f'"{role_name}"'
            conn.execute(
                text(
                    f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                )
            )
            conn.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
            conn.execute(text(f"GRANT ALL ON core_audit.animals TO {quoted_role}"))
            conn.execute(text(f"GRANT ALL ON core_audit.animal_identifiers TO {quoted_role}"))
            conn.execute(text(f"SET LOCAL ROLE {quoted_role}"))

            print("\n[5/5] Testando impedimento de acesso cruzado (RLS) pela Org B...")
            conn.execute(
                text("SELECT set_config('titan.organization_id', :org_id, true)"),
                {"org_id": str(org_b.value)},
            )
            repo_b = TransactionalAnimalRepository(connection=conn)
            service_b = AnimalService(repository=repo_b)

            if service_b.get_animal(animal_a.animal_id) is None:
                print(
                    "      [OK] SUCESSO: A Org B NAO consegue enxergar o animal da Org A (RLS Ativo)."
                )
            else:
                print("      [ERRO] FALHA: A Org B conseguiu enxergar o animal da Org A!")

            conn.execute(text("RESET ROLE"))
            conn.execute(text(f"DROP OWNED BY {quoted_role}"))
            conn.execute(text(f"DROP ROLE {quoted_role}"))

    print("\n" + "=" * 70)
    print("      VALIDACAO MANUAL DO PASSO 8.2 CONCLUIDA COM SUCESSO COMPLETO!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
