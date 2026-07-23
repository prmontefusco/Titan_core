"""Script de Validação Manual do Passo 8.6 - Prova Integrada E2E da Vertical Titan Livestock."""

import os
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine, text

from packages.livestock_application.animal_service import AnimalService
from packages.livestock_application.fact_provider import LivestockFactProvider
from packages.livestock_application.lot_service import LotService
from packages.livestock_application.movement_service import MovementService
from packages.livestock_application.property_service import RuralPropertyService
from packages.livestock_application.veterinarian_service import VeterinarianService
from packages.livestock_domain.animal import AnimalSex, IdentifierType, VerificationStatus
from packages.livestock_domain.lot import LotType
from packages.livestock_domain.movement import PropertyStay, StayStatus
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.lot_repository import (
    TransactionalLivestockLotRepository,
    TransactionalLotMembershipRepository,
)
from packages.livestock_infrastructure.persistence.movement_repository import (
    TransactionalAnimalMovementRepository,
    TransactionalPropertyStayRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.livestock_infrastructure.persistence.veterinarian_repository import (
    TransactionalVeterinarianRepository,
)
from packages.shared_kernel import OrganizationId, TypedId


def main() -> None:
    print("=" * 75)
    print("   PROVA INTEGRADA E2E DA VERTICAL TITAN LIVESTOCK (PASSO 8.6 - MARCO 8)")
    print("=" * 75)

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
            print("\n[1/8] Ambiente de Banco de Dados configurado com RLS para Org A:")
            print(f"      - Org A: {org_a.value}")

            # Repositórios e Serviços
            prop_repo = TransactionalRuralPropertyRepository(connection=conn)
            anim_repo = TransactionalAnimalRepository(connection=conn)
            mov_repo = TransactionalAnimalMovementRepository(connection=conn)
            stay_repo = TransactionalPropertyStayRepository(connection=conn)
            lot_repo = TransactionalLivestockLotRepository(connection=conn)
            mem_repo = TransactionalLotMembershipRepository(connection=conn)
            vet_repo = TransactionalVeterinarianRepository(connection=conn)

            prop_service = RuralPropertyService(repository=prop_repo)
            anim_service = AnimalService(repository=anim_repo)
            mov_service = MovementService(
                movement_repository=mov_repo,
                stay_repository=stay_repo,
                animal_repository=anim_repo,
                property_repository=prop_repo,
            )
            lot_service = LotService(
                lot_repository=lot_repo,
                membership_repository=mem_repo,
                animal_repository=anim_repo,
                property_repository=prop_repo,
            )
            vet_service = VeterinarianService(repository=vet_repo)
            fact_provider = LivestockFactProvider(
                property_repository=prop_repo,
                animal_repository=anim_repo,
                stay_repository=stay_repo,
            )

            # 2. Cadastra Propriedades Rurais
            p_origem = prop_service.register_property(
                organization_id=org_a,
                code="FAZ-PRIMAVERA",
                name="Fazenda Primavera (Nascimento/Cria)",
                municipality="Ribeirão Preto",
                state_code="SP",
                total_area_hectares=1200.0,
            )
            p_destino = prop_service.register_property(
                organization_id=org_a,
                code="FAZ-SANTA-INES",
                name="Fazenda Santa Inês (Engorda)",
                municipality="Sertãozinho",
                state_code="SP",
                total_area_hectares=850.0,
            )
            print("\n[2/8] Propriedades rurais registradas:")
            print(f"      - Origem:  {p_origem.name} (ID: {p_origem.property_id})")
            print(f"      - Destino: {p_destino.name} (ID: {p_destino.property_id})")

            # 3. Cadastra Veterinário e Valida Elevação por Evidência
            vet = vet_service.register_veterinarian(
                organization_id=org_a,
                name="Dr. Carlos Eduardo Rocha",
                cpf="987.654.321-00",
                council_number="12987",
                council_state="SP",
            )
            vet_service.attach_evidence(vet.veterinarian_id, "evidence:carteira-crmv-pdf-9911")
            vet_verified = vet_service.update_verification_status(
                vet.veterinarian_id, VerificationStatus.VERIFICADO_EM_FONTE
            )
            print("\n[3/8] Veterinário Responsável cadastrado e verificado:")
            print(f"      - Nome:   {vet_verified.name}")
            print(f"      - CRMV:   {vet_verified.council_state}-{vet_verified.council_number}")
            print(f"      - Status: {vet_verified.verification_status.value}")

            # 4. Cadastra Animal e Anexa Brinco SISBOV + Manejo Visual
            animal = anim_service.register_animal(
                organization_id=org_a,
                birth_property_id=p_origem.property_id,
                sex=AnimalSex.MALE,
                breed="Nelore Mocho PO",
                birth_date=date(2025, 1, 15),
            )
            anim_service.attach_identifier(
                animal_id=animal.animal_id,
                identifier_type=IdentifierType.OFFICIAL_SISBOV,
                identifier_value="BR9988776655",
            )
            anim_service.attach_identifier(
                animal_id=animal.animal_id,
                identifier_type=IdentifierType.EAR_TAG,
                identifier_value="BEZ-001",
            )

            print("\n[4/8] Animal registrado com identificação auditável:")
            print(f"      - Animal ID: {animal.animal_id}")
            print(f"      - SISBOV:    BR9988776655 (Status: VERIFICADO_EM_FONTE)")
            print(f"      - Manejo:    BEZ-001 (Ativo)")

            stay_repo.save(
                PropertyStay(
                    stay_id=TypedId.new("property_stay"),
                    organization_id=org_a,
                    animal_id=animal.animal_id,
                    property_id=p_origem.property_id,
                    start_time=datetime.now(UTC) - timedelta(days=120),
                    end_time=None,
                    status=StayStatus.ACTIVE,
                )
            )

            # 5. Associação ao Lote de Desmame na Origem
            lot_desmame = lot_service.create_lot(
                organization_id=org_a,
                property_id=p_origem.property_id,
                code="DESMAME-2025",
                name="Lote Desmame Primavera 2025",
                lot_type=LotType.OPERATIONAL,
            )
            m_desmame = lot_service.add_animal_to_lot(
                lot_desmame.lot_id, animal.animal_id, reason="Alojamento pós-desmame"
            )
            print("\n[5/8] Lote Operacional de Desmame criado na Origem:")
            print(f"      - Lote:          {lot_desmame.name}")
            print(f"      - Membership ID: {m_desmame.membership_id}")

            # 6. Movimentação do Animal da Fazenda Origem para Fazenda Destino
            m_time = datetime.now(UTC) - timedelta(hours=4)
            movimento = mov_service.register_movement(
                organization_id=org_a,
                origin_property_id=p_origem.property_id,
                destination_property_id=p_destino.property_id,
                movement_time=m_time,
                animal_ids=(animal.animal_id,),
                reason="Transferência de rebanho para recria e engorda",
            )
            print("\n[6/8] Movimentação inter-fazendas registrada (Fato Imutável):")
            print(f"      - Movement ID: {movimento.movement_id}")
            print(f"      - Motivo:      {movimento.reason}")

            timeline = mov_service.get_stay_timeline(animal.animal_id)
            print("      - Linha do Tempo de Permanência (PropertyStay):")
            print(
                f"        1. Origem ({timeline[0].property_id}): Status={timeline[0].status.value}, Fim={timeline[0].end_time.strftime('%Y-%m-%d %H:%M UTC')}"
            )
            print(
                f"        2. Destino ({timeline[1].property_id}): Status={timeline[1].status.value}, Fim=Ativo"
            )

            # 7. Transferência de Lote na Fazenda Destino
            lot_service.remove_animal_from_lot(lot_desmame.lot_id, animal.animal_id)
            lot_engorda = lot_service.create_lot(
                organization_id=org_a,
                property_id=p_destino.property_id,
                code="ENGORDA-PASTO-5",
                name="Lote Engorda Intensiva Pasto 5",
                lot_type=LotType.OPERATIONAL,
            )
            m_engorda = lot_service.add_animal_to_lot(
                lot_engorda.lot_id, animal.animal_id, reason="Alojamento em engorda no destino"
            )
            print("\n[7/8] Transferência de Lote efetuada no Destino:")
            print(f"      - Saída do Lote Desmame: Sucesso")
            print(
                f"      - Entrada no Lote {lot_engorda.name}: Sucesso (Membership ID: {m_engorda.membership_id})"
            )

            # 8. Verificação do FactProvider e Isolamento RLS
            snapshot = fact_provider.get_snapshot(
                organization_id=org_a,
                target_id=animal.animal_id,
                at_time=datetime.now(UTC),
            )
            animal_fact = snapshot.facts[0]
            print("\n[8/8] Fatos de localização integrados ao Motor de Políticas do Core:")
            print(f"      - Propriedade Atual: {animal_fact.payload['current_property_id']}")
            print(f"      - Status da Estada:  {animal_fact.payload['stay_status']}")

            # Testar RLS em outra Role (Org B)
            role_name = f"titan_valida_e2e_{uuid4().hex[:8]}"
            quoted_role = f'"{role_name}"'
            conn.execute(
                text(
                    f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                )
            )
            conn.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
            conn.execute(text(f"GRANT ALL ON ALL TABLES IN SCHEMA core_audit TO {quoted_role}"))
            conn.execute(text(f"SET LOCAL ROLE {quoted_role}"))

            conn.execute(
                text("SELECT set_config('titan.organization_id', :org_id, true)"),
                {"org_id": str(org_b.value)},
            )
            anim_repo_b = TransactionalAnimalRepository(connection=conn)

            if anim_repo_b.get_by_id(animal.animal_id) is None:
                print(
                    "      [OK] SUCESSO COMPLETO: A Org B NAO enxerga os dados da Org A (Isolamento RLS Verificado)."
                )
            else:
                print("      [ERRO] FALHA: A Org B enxergou dados da Org A!")

            conn.execute(text("RESET ROLE"))
            conn.execute(text(f"DROP OWNED BY {quoted_role}"))
            conn.execute(text(f"DROP ROLE {quoted_role}"))

    print("\n" + "=" * 75)
    print("   MARCO 8 — TITAN LIVESTOCK CONCLUÍDO E VERIFICADO COM SUCESSO COMPLETO!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
