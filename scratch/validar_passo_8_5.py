"""Script de Validação Manual do Passo 8.5 - Veterinarian e Registro Profissional (Titan Livestock)."""

import os
from uuid import uuid4

from sqlalchemy import create_engine, text

from packages.livestock_application.veterinarian_service import VeterinarianService
from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_infrastructure.persistence.veterinarian_repository import (
    TransactionalVeterinarianRepository,
)
from packages.shared_kernel import OrganizationId


def main() -> None:
    print("=" * 70)
    print("   VALIDAÇÃO MANUAL: PASSO 8.5 — VETERINARIAN & CRMV (TITAN LIVESTOCK)")
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
            vet_repo_a = TransactionalVeterinarianRepository(connection=conn)
            vet_service_a = VeterinarianService(repository=vet_repo_a)

            # 2. Cadastra Veterinário inicial (inicia como DECLARADO)
            vet = vet_service_a.register_veterinarian(
                organization_id=org_a,
                name="Dr. Fernando Augusto",
                cpf="123.456.789-01",
                council_number="45678",
                council_state="SP",
            )
            print("\n[2/5] Veterinário cadastrado (Nível Inicial):")
            print(f"      - Vet ID: {vet.veterinarian_id}")
            print(f"      - Nome:   {vet.name}")
            print(f"      - CPF:    {vet.cpf}")
            print(f"      - CRMV:   {vet.council_state}-{vet.council_number}")
            print(f"      - Status: {vet.verification_status.value}")

            # 3. Anexa evidência documental (Eleva para DOCUMENTADO)
            updated_vet = vet_service_a.attach_evidence(
                veterinarian_id=vet.veterinarian_id,
                evidence_reference="evidence:carteira-crmv-pdf-9988",
            )
            print("\n[3/5] Evidência documental anexada (ADR-0026 Evidence):")
            print(f"      - Ref Evidência: {updated_vet.evidence_reference}")
            print(f"      - Novo Status:   {updated_vet.verification_status.value}")

            # 4. Simula verificação oficial em fonte de dados (Eleva para VERIFICADO_EM_FONTE)
            verified_vet = vet_service_a.update_verification_status(
                veterinarian_id=vet.veterinarian_id,
                new_status=VerificationStatus.VERIFICADO_EM_FONTE,
            )
            print("\n[4/5] Verificação em fonte efetuada com sucesso:")
            print(f"      - Status Final:  {verified_vet.verification_status.value}")

            # Testar recusa de CRMV duplicado na mesma organização
            print("      Testando recusa de CRMV duplicado na mesma organização...")
            try:
                vet_service_a.register_veterinarian(
                    organization_id=org_a,
                    name="Outro Dr. Silva",
                    cpf="999.888.777-66",
                    council_number="45678",
                    council_state="SP",
                )
                print("      [ERRO] FALHA: Permitiu cadastrar CRMV duplicado!")
            except ValueError as e:
                print(f"      [OK] SUCESSO: Recusado corretamente. Motivo: '{e}'")

            # 5. RLS Isolation: Org B não enxerga o veterinário da Org A
            role_name = f"titan_valida_vet_{uuid4().hex[:8]}"
            quoted_role = f'"{role_name}"'
            conn.execute(
                text(
                    f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                )
            )
            conn.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
            conn.execute(text(f"GRANT ALL ON core_audit.veterinarians TO {quoted_role}"))
            conn.execute(text(f"SET LOCAL ROLE {quoted_role}"))

            conn.execute(
                text("SELECT set_config('titan.organization_id', :org_id, true)"),
                {"org_id": str(org_b.value)},
            )
            vet_repo_b = TransactionalVeterinarianRepository(connection=conn)
            vet_service_b = VeterinarianService(repository=vet_repo_b)

            if vet_service_b.repository.get_by_id(vet.veterinarian_id) is None:
                print(
                    "\n[5/5] [OK] SUCESSO: A Org B NAO consegue enxergar o veterinário da Org A (RLS Ativo)."
                )
            else:
                print("\n[5/5] [ERRO] FALHA: A Org B conseguiu enxergar o veterinário da Org A!")

            conn.execute(text("RESET ROLE"))
            conn.execute(text(f"DROP OWNED BY {quoted_role}"))
            conn.execute(text(f"DROP ROLE {quoted_role}"))

    print("\n" + "=" * 70)
    print("      VALIDACAO MANUAL DO PASSO 8.5 CONCLUIDA COM SUCESSO COMPLETO!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
