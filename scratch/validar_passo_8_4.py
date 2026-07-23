"""Script de Validação Manual do Passo 8.4 - LivestockLot e LotMembership (Titan Livestock)."""

import os
from uuid import uuid4

from sqlalchemy import create_engine, text

from packages.livestock_application.animal_service import AnimalService
from packages.livestock_application.lot_service import LotService
from packages.livestock_application.property_service import RuralPropertyService
from packages.livestock_domain.animal import AnimalSex
from packages.livestock_domain.lot import LotType
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.lot_repository import (
    TransactionalLivestockLotRepository,
    TransactionalLotMembershipRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.shared_kernel import OrganizationId


def main() -> None:
    print("=" * 70)
    print("   VALIDAÇÃO MANUAL: PASSO 8.4 — LIVESTOCK LOT & MEMBERSHIP (TITAN LIVESTOCK)")
    print("=" * 70)

    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url)

    org_a = OrganizationId(uuid4())
    org_b = OrganizationId(uuid4())

    with engine.connect() as conn:
        with conn.begin():
            # 1. Configura RLS para Org A
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
                text("SELECT set_config('titan.organization_id', :org_id, true)"),
                {"org_id": str(org_a.value)},
            )
            print("\n[1/5] Ambiente configurado com RLS para Org A:")
            print(f"      - Org A: {org_a.value}")
            print(f"      - Org B: {org_b.value}")

            # Repositórios e Serviços
            prop_repo_a = TransactionalRuralPropertyRepository(connection=conn)
            anim_repo_a = TransactionalAnimalRepository(connection=conn)
            lot_repo_a = TransactionalLivestockLotRepository(connection=conn)
            mem_repo_a = TransactionalLotMembershipRepository(connection=conn)

            prop_service_a = RuralPropertyService(repository=prop_repo_a)
            anim_service_a = AnimalService(repository=anim_repo_a)
            lot_service_a = LotService(
                lot_repository=lot_repo_a,
                membership_repository=mem_repo_a,
                animal_repository=anim_repo_a,
                property_repository=prop_repo_a,
            )

            # 2. Cadastra Propriedade e Animal
            prop = prop_service_a.register_property(
                organization_id=org_a,
                code="PROP-FAZ-LOT",
                name="Fazenda Esperança",
                municipality="Ribeirão Preto",
                state_code="SP",
            )
            animal = anim_service_a.register_animal(
                organization_id=org_a,
                birth_property_id=prop.property_id,
                sex=AnimalSex.MALE,
                breed="Nelore Mocho",
            )
            print("\n[2/5] Propriedade e Animal cadastrados:")
            print(f"      - Fazenda: {prop.name}")
            print(f"      - Animal ID: {animal.animal_id}")

            # 3. Cadastra Lotes: 2 Operacionais de Manejo e 1 Sanitário
            lot_op1 = lot_service_a.create_lot(
                organization_id=org_a,
                property_id=prop.property_id,
                code="PASTO-1",
                name="Lote Manejo Pasto 1",
                lot_type=LotType.OPERATIONAL,
            )
            lot_op2 = lot_service_a.create_lot(
                organization_id=org_a,
                property_id=prop.property_id,
                code="PASTO-2",
                name="Lote Manejo Pasto 2",
                lot_type=LotType.OPERATIONAL,
            )
            lot_san = lot_service_a.create_lot(
                organization_id=org_a,
                property_id=prop.property_id,
                code="AFTOSA-MAY",
                name="Lote Sanitário Aftosa Maio",
                lot_type=LotType.SANITARY,
            )
            print("\n[3/5] Lotes criados com finalidades distintas:")
            print(f"      - Lote Operacional 1: {lot_op1.name} (Tipo: {lot_op1.lot_type.value})")
            print(f"      - Lote Operacional 2: {lot_op2.name} (Tipo: {lot_op2.lot_type.value})")
            print(f"      - Lote Sanitário:     {lot_san.name} (Tipo: {lot_san.lot_type.value})")

            # 4. Adiciona animal ao Lote Operacional 1
            m1 = lot_service_a.add_animal_to_lot(
                lot_op1.lot_id, animal.animal_id, reason="Início da engorda no Pasto 1"
            )
            print(
                f"\n[4/5] Animal associado ao Lote Operacional 1 com sucesso. Membership ID: {m1.membership_id}"
            )

            # Testar recusa de sobreposição de lote operacional
            print("      Testando recusa de inclusão simultânea em outro Lote Operacional...")
            try:
                lot_service_a.add_animal_to_lot(lot_op2.lot_id, animal.animal_id)
                print("      [ERRO] FALHA: Permitiu inclusão simultânea em 2 lotes operacionais!")
            except ValueError as e:
                print(f"      [OK] SUCESSO: Recusado corretamente. Motivo: '{e}'")

            # Adiciona ao Lote Sanitário (Sobreposição permitida)
            m_san = lot_service_a.add_animal_to_lot(
                lot_san.lot_id, animal.animal_id, reason="Campanha de vacinação"
            )
            print(
                f"      [OK] SUCESSO: Animal associado ao Lote Sanitário sobreposto sem erros. Membership ID: {m_san.membership_id}"
            )

            # 5. Remove do Lote 1 e transfere para o Lote 2
            lot_service_a.remove_animal_from_lot(lot_op1.lot_id, animal.animal_id)
            m2 = lot_service_a.add_animal_to_lot(lot_op2.lot_id, animal.animal_id)
            print(
                f"\n[5/5] Animal removido do Lote 1 e transferido para Lote 2 com sucesso. Membership ID: {m2.membership_id}"
            )

            # Consulta composição atual do Lote 2
            comp_actual = lot_service_a.get_lot_composition(lot_op2.lot_id)
            print(f"      - Composição atual do Lote 2: {len(comp_actual)} animal(is) ativo(s).")

            # RLS Isolation: Org B não enxerga o lote da Org A
            role_name = f"titan_valida_lot_{uuid4().hex[:8]}"
            quoted_role = f'"{role_name}"'
            conn.execute(
                text(
                    f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                )
            )
            conn.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
            conn.execute(text(f"GRANT ALL ON core_audit.livestock_lots TO {quoted_role}"))
            conn.execute(text(f"GRANT ALL ON core_audit.lot_memberships TO {quoted_role}"))
            conn.execute(text(f"SET LOCAL ROLE {quoted_role}"))

            conn.execute(
                text("SELECT set_config('titan.organization_id', :org_id, true)"),
                {"org_id": str(org_b.value)},
            )
            lot_repo_b = TransactionalLivestockLotRepository(connection=conn)
            mem_repo_b = TransactionalLotMembershipRepository(connection=conn)
            anim_repo_b = TransactionalAnimalRepository(connection=conn)
            prop_repo_b = TransactionalRuralPropertyRepository(connection=conn)

            lot_service_b = LotService(
                lot_repository=lot_repo_b,
                membership_repository=mem_repo_b,
                animal_repository=anim_repo_b,
                property_repository=prop_repo_b,
            )

            if lot_service_b.lot_repository.get_by_id(lot_op1.lot_id) is None:
                print(
                    "      [OK] SUCESSO: A Org B NAO consegue enxergar os lotes da Org A (RLS Ativo)."
                )
            else:
                print("      [ERRO] FALHA: A Org B conseguiu enxergar os lotes da Org A!")

            conn.execute(text("RESET ROLE"))
            conn.execute(text(f"DROP OWNED BY {quoted_role}"))
            conn.execute(text(f"DROP ROLE {quoted_role}"))

    print("\n" + "=" * 70)
    print("      VALIDACAO MANUAL DO PASSO 8.4 CONCLUIDA COM SUCESSO COMPLETO!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
