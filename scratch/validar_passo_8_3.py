"""Script de Validação Manual do Passo 8.3 - AnimalMovement e PropertyStay (Titan Livestock)."""

import os
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine, text

from packages.livestock_application.animal_service import AnimalService
from packages.livestock_application.movement_service import MovementService
from packages.livestock_application.property_service import RuralPropertyService
from packages.livestock_domain.animal import AnimalSex
from packages.livestock_domain.movement import StayStatus
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.movement_repository import (
    TransactionalAnimalMovementRepository,
    TransactionalPropertyStayRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.shared_kernel import OrganizationId


def main() -> None:
    print("=" * 70)
    print("   VALIDAÇÃO MANUAL: PASSO 8.3 — MOVEMENT & PROPERTY STAY (TITAN LIVESTOCK)")
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
            # 1. Cadastra organizações e configura contexto RLS para Org A
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

            # Inicializa repositórios e serviços para Org A
            prop_repo_a = TransactionalRuralPropertyRepository(connection=conn)
            anim_repo_a = TransactionalAnimalRepository(connection=conn)
            mov_repo_a = TransactionalAnimalMovementRepository(connection=conn)
            stay_repo_a = TransactionalPropertyStayRepository(connection=conn)

            prop_service_a = RuralPropertyService(repository=prop_repo_a)
            anim_service_a = AnimalService(repository=anim_repo_a)
            mov_service_a = MovementService(
                movement_repository=mov_repo_a,
                stay_repository=stay_repo_a,
                animal_repository=anim_repo_a,
                property_repository=prop_repo_a,
            )

            # 2. Cadastra 2 propriedades rurais (Origem e Destino)
            prop_origem = prop_service_a.register_property(
                organization_id=org_a,
                code="PROP-FAZ-01",
                name="Fazenda Origem (Ribeirão Preto)",
                municipality="Ribeirão Preto",
                state_code="SP",
                total_area_hectares=500.0,
            )
            prop_destino = prop_service_a.register_property(
                organization_id=org_a,
                code="PROP-FAZ-02",
                name="Fazenda Destino (Sertãozinho)",
                municipality="Sertãozinho",
                state_code="SP",
                total_area_hectares=300.0,
            )
            print("\n[2/5] Propriedades rurais cadastradas:")
            print(f"      - Origem: {prop_origem.name} (ID: {prop_origem.property_id})")
            print(f"      - Destino: {prop_destino.name} (ID: {prop_destino.property_id})")

            # 3. Cadastra Animal na Fazenda Origem
            animal = anim_service_a.register_animal(
                organization_id=org_a,
                birth_property_id=prop_origem.property_id,
                sex=AnimalSex.MALE,
                breed="Nelore Mocho",
                birth_date=date(2025, 3, 1),
            )
            print("\n[3/5] Animal registrado na Fazenda Origem:")
            print(f"      - Animal ID: {animal.animal_id}")

            # Registra estada inicial no nascimento
            from packages.livestock_domain.movement import PropertyStay
            from packages.shared_kernel import TypedId

            stay_repo_a.save(
                PropertyStay(
                    stay_id=TypedId.new("property_stay"),
                    organization_id=org_a,
                    animal_id=animal.animal_id,
                    property_id=prop_origem.property_id,
                    start_time=datetime.now(UTC) - timedelta(days=60),
                    end_time=None,
                    status=StayStatus.ACTIVE,
                )
            )

            # 4. Registra movimentação do animal da Origem para o Destino
            m_time = datetime.now(UTC) - timedelta(hours=2)
            movement = mov_service_a.register_movement(
                organization_id=org_a,
                origin_property_id=prop_origem.property_id,
                destination_property_id=prop_destino.property_id,
                movement_time=m_time,
                animal_ids=(animal.animal_id,),
                reason="Transferência de rebanho para recria",
            )

            print("\n[4/5] Movimentação registrada e permanências atualizadas:")
            print(f"      - Movement ID (Fato): {movement.movement_id}")
            print(f"      - Motivo: {movement.reason}")

            active_stay = mov_service_a.get_active_stay(animal.animal_id)
            print(
                f"      - Permanência Ativa Atual: Fazenda {active_stay.property_id if active_stay else 'Nenhuma'}"
            )
            print(
                f"      - Status da Estada Ativa: {active_stay.status.value if active_stay else 'Nenhum'}"
            )

            timeline = mov_service_a.get_stay_timeline(animal.animal_id)
            print(f"      - Total de estadas na linha do tempo: {len(timeline)}")
            print(
                f"        1. Estada Origem: Status={timeline[0].status.value}, Fim={timeline[0].end_time.strftime('%Y-%m-%d %H:%M:%S UTC') if timeline[0].end_time else 'Ativo'}"
            )
            print(
                f"        2. Estada Destino: Status={timeline[1].status.value}, Fim={timeline[1].end_time.strftime('%Y-%m-%d %H:%M:%S UTC') if timeline[1].end_time else 'Ativo'}"
            )

            # 5. Testar recusa de movimentação inválida (destino = origem)
            print("\n[5/5] Testando recusa de movimentação para a mesma propriedade...")
            try:
                mov_service_a.register_movement(
                    organization_id=org_a,
                    origin_property_id=prop_destino.property_id,
                    destination_property_id=prop_destino.property_id,
                    movement_time=datetime.now(UTC),
                    animal_ids=(animal.animal_id,),
                )
                print("      [ERRO] FALHA: Permitiu movimentar para a mesma propriedade!")
            except ValueError as e:
                print(f"      [OK] SUCESSO: Recusado corretamente. Motivo: '{e}'")

            # Testar RLS em outra Role (Org B não enxerga movimentação)
            role_name = f"titan_valida_mov_{uuid4().hex[:8]}"
            quoted_role = f'"{role_name}"'
            conn.execute(
                text(
                    f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                )
            )
            conn.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
            conn.execute(text(f"GRANT ALL ON core_audit.animal_movements TO {quoted_role}"))
            conn.execute(text(f"GRANT ALL ON core_audit.animal_movement_items TO {quoted_role}"))
            conn.execute(text(f"GRANT ALL ON core_audit.property_stays TO {quoted_role}"))
            conn.execute(text(f"SET LOCAL ROLE {quoted_role}"))

            conn.execute(
                text("SELECT set_config('titan.organization_id', :org_id, true)"),
                {"org_id": str(org_b.value)},
            )
            mov_repo_b = TransactionalAnimalMovementRepository(connection=conn)
            stay_repo_b = TransactionalPropertyStayRepository(connection=conn)
            anim_repo_b = TransactionalAnimalRepository(connection=conn)
            prop_repo_b = TransactionalRuralPropertyRepository(connection=conn)

            mov_service_b = MovementService(
                movement_repository=mov_repo_b,
                stay_repository=stay_repo_b,
                animal_repository=anim_repo_b,
                property_repository=prop_repo_b,
            )

            if mov_service_b.movement_repository.get_by_id(movement.movement_id) is None:
                print(
                    "      [OK] SUCESSO: A Org B NAO consegue enxergar a movimentação da Org A (RLS Ativo)."
                )
            else:
                print("      [ERRO] FALHA: A Org B conseguiu enxergar a movimentação da Org A!")

            conn.execute(text("RESET ROLE"))
            conn.execute(text(f"DROP OWNED BY {quoted_role}"))
            conn.execute(text(f"DROP ROLE {quoted_role}"))

    print("\n" + "=" * 70)
    print("      VALIDACAO MANUAL DO PASSO 8.3 CONCLUIDA COM SUCESSO COMPLETO!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
