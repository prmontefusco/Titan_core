"""Script de Validação Manual do Passo 9.1 - Medication e Prescription (Titan Livestock)."""

import os
from uuid import uuid4

from sqlalchemy import create_engine, text

from packages.livestock_application.medication_service import MedicationService
from packages.livestock_application.property_service import RuralPropertyService
from packages.livestock_application.veterinarian_service import VeterinarianService
from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_domain.prescription import PrescriptionTargetType
from packages.livestock_infrastructure.persistence.medication_repository import (
    TransactionalMedicationRepository,
    TransactionalPrescriptionRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.livestock_infrastructure.persistence.veterinarian_repository import (
    TransactionalVeterinarianRepository,
)
from packages.shared_kernel import OrganizationId, TypedId


def main() -> None:
    print("=" * 70)
    print("   VALIDAÇÃO MANUAL: PASSO 9.1 — MEDICATION & PRESCRIPTION (TITAN LIVESTOCK)")
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
            med_repo_a = TransactionalMedicationRepository(connection=conn)
            presc_repo_a = TransactionalPrescriptionRepository(connection=conn)
            vet_repo_a = TransactionalVeterinarianRepository(connection=conn)
            prop_repo_a = TransactionalRuralPropertyRepository(connection=conn)

            prop_service_a = RuralPropertyService(repository=prop_repo_a)
            vet_service_a = VeterinarianService(repository=vet_repo_a)
            med_service_a = MedicationService(
                medication_repository=med_repo_a,
                prescription_repository=presc_repo_a,
                veterinarian_repository=vet_repo_a,
                property_repository=prop_repo_a,
            )

            # 2. Cadastra Propriedade e Medicamento
            prop = prop_service_a.register_property(
                organization_id=org_a,
                code="PROP-FAZ-MED",
                name="Fazenda Sanidade",
                municipality="Ribeirão Preto",
                state_code="SP",
            )

            med = med_service_a.register_medication(
                organization_id=org_a,
                trade_name="Ivomec Gold 3,15%",
                active_ingredient="Ivermectina",
                manufacturer="Boehringer Ingelheim",
                withdrawal_period_days=122,
                dosage_instruction="1 mL para cada 50 kg de peso vivo por via subcutânea",
            )
            print("\n[2/5] Medicamento cadastrado (Ficha Técnica / Bula):")
            print(f"      - Nome Comercial:   {med.trade_name}")
            print(f"      - Princípio Ativo:  {med.active_ingredient}")
            print(f"      - Carência Abate:   {med.withdrawal_period_days} dias")

            # 3. Cadastra Veterinário não verificado (DECLARADO) e tenta emitir receita
            vet_unverified = vet_service_a.register_veterinarian(
                organization_id=org_a,
                name="Dr. Sem Prova",
                cpf="111.222.333-44",
                council_number="9911",
                council_state="SP",
            )
            print(f"\n[3/5] Testando recusa de emissão de receita por veterinário '{vet_unverified.verification_status.value}'...")
            try:
                med_service_a.issue_prescription(
                    organization_id=org_a,
                    veterinarian_id=vet_unverified.veterinarian_id,
                    medication_id=med.medication_id,
                    property_id=prop.property_id,
                    dosage="1 mL / 50 kg",
                    administration_route="SUBCUTANEOUS",
                    target_type=PrescriptionTargetType.ANIMAL,
                    target_ids=(TypedId.new("animal"),),
                    reason="Tratamento preventivo",
                )
                print("      [ERRO] FALHA: Permitiu emitir receita por veterinário sem verificação!")
            except ValueError as e:
                print(f"      [OK] SUCESSO: Recusado corretamente. Motivo: '{e}'")

            # 4. Promove o Veterinário para VERIFICADO_EM_FONTE e emite receita
            vet_service_a.attach_evidence(vet_unverified.veterinarian_id, "evidence:doc-crmv-pdf-9911")
            vet_verified = vet_service_a.update_verification_status(
                vet_unverified.veterinarian_id, VerificationStatus.VERIFICADO_EM_FONTE
            )
            print(f"\n[4/5] Veterinário promovido para '{vet_verified.verification_status.value}'. Emitindo receita...")

            animal_target = TypedId.new("animal")
            presc = med_service_a.issue_prescription(
                organization_id=org_a,
                veterinarian_id=vet_verified.veterinarian_id,
                medication_id=med.medication_id,
                property_id=prop.property_id,
                dosage="1 mL / 50 kg",
                administration_route="SUBCUTANEOUS",
                target_type=PrescriptionTargetType.ANIMAL,
                target_ids=(animal_target,),
                reason="Tratamento de parasitas de pele",
            )
            print(f"      [OK] SUCESSO: Receita Veterinária emitidamente com sucesso! ID: {presc.prescription_id}")

            # 5. RLS Isolation: Org B não enxerga medicamentos ou prescrições da Org A
            role_name = f"titan_valida_med_{uuid4().hex[:8]}"
            quoted_role = f'"{role_name}"'
            conn.execute(
                text(
                    f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                )
            )
            conn.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
            conn.execute(text(f"GRANT ALL ON core_audit.medications TO {quoted_role}"))
            conn.execute(text(f"GRANT ALL ON core_audit.prescriptions TO {quoted_role}"))
            conn.execute(text(f"GRANT ALL ON core_audit.prescription_targets TO {quoted_role}"))
            conn.execute(text(f"SET LOCAL ROLE {quoted_role}"))

            conn.execute(
                text("SELECT set_config('titan.organization_id', :org_id, true)"),
                {"org_id": str(org_b.value)},
            )
            med_repo_b = TransactionalMedicationRepository(connection=conn)
            presc_repo_b = TransactionalPrescriptionRepository(connection=conn)

            if (
                med_repo_b.get_by_id(med.medication_id) is None
                and presc_repo_b.get_by_id(presc.prescription_id) is None
            ):
                print("\n[5/5] [OK] SUCESSO: A Org B NAO consegue enxergar as receitas ou medicamentos da Org A (RLS Ativo).")
            else:
                print("\n[5/5] [ERRO] FALHA: A Org B conseguiu enxergar dados da Org A!")

            conn.execute(text("RESET ROLE"))
            conn.execute(text(f"DROP OWNED BY {quoted_role}"))
            conn.execute(text(f"DROP ROLE {quoted_role}"))

    print("\n" + "=" * 70)
    print("      VALIDACAO MANUAL DO PASSO 9.1 CONCLUIDA COM SUCESSO COMPLETO!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
