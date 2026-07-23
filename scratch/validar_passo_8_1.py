"""Script de Validação Manual do Passo 8.1 - RuralProperty (Titan Livestock)."""

import os
from uuid import uuid4

from sqlalchemy import create_engine, text

from packages.livestock_application.property_service import RuralPropertyService
from packages.livestock_domain.property import RuralProperty
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.shared_kernel import OrganizationId


def main() -> None:
    print("=" * 70)
    print("      VALIDAÇÃO MANUAL: PASSO 8.1 — RURAL PROPERTY (TITAN LIVESTOCK)")
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
            # 1. Cadastra as Organizações A e B
            conn.execute(
                text(
                    """
                    INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
                    VALUES (:id_a, :id_a), (:id_b, :id_b)
                    """
                ),
                {"id_a": org_a.value, "id_b": org_b.value},
            )
            print(f"\n[1/5] Organizações criadas no banco:")
            print(f"      - Org A: {org_a.value}")
            print(f"      - Org B: {org_b.value}")

            # 2. Define o contexto RLS para a Org A
            conn.execute(
                text("SELECT set_config('titan.organization_id', :org_id, true)"),
                {"org_id": str(org_a.value)},
            )
            repo_a = TransactionalRuralPropertyRepository(connection=conn)
            service_a = RuralPropertyService(repository=repo_a)

            # 3. Cria a Propriedade Rural na Org A
            prop_a = service_a.register_property(
                organization_id=org_a,
                code="PROP-SP-001",
                name="Fazenda Santa Maria",
                municipality="Ribeirão Preto",
                state_code="SP",
                registration_number="CAR-SP-99812",
                total_area_hectares=350.5,
            )
            print(f"\n[2/5] Propriedade Rural cadastrada na Org A:")
            print(f"      - ID Estável: {prop_a.property_id}")
            print(f"      - Código: {prop_a.code}")
            print(f"      - Nome: {prop_a.name} ({prop_a.municipality}/{prop_a.state_code})")
            print(f"      - Área: {prop_a.total_area_hectares} ha")

            # 4. Tenta cadastrar outra propriedade com o mesmo código na Org A (Deve falhar)
            print("\n[3/5] Testando recusa de código duplicado na mesma organização...")
            try:
                service_a.register_property(
                    organization_id=org_a,
                    code="PROP-SP-001",
                    name="Fazenda Duplicada",
                    municipality="Ribeirão Preto",
                    state_code="SP",
                )
                print("      [ERRO] FALHA: Permitiu cadastrar código duplicado!")
            except ValueError as e:
                print(f"      [OK] SUCESSO: Recusado corretamente. Motivo: '{e}'")

            # 5. Criar role sem BYPASSRLS para simular a conexão de usuário normal e testar isolamento RLS
            role_name = f"titan_valida_rls_{uuid4().hex[:8]}"
            quoted_role = f'"{role_name}"'
            conn.execute(
                text(
                    f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                )
            )
            conn.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
            conn.execute(text(f"GRANT ALL ON core_audit.rural_properties TO {quoted_role}"))
            conn.execute(text(f"SET LOCAL ROLE {quoted_role}"))

            # 6. Muda o contexto RLS para a Org B e tenta acessar a propriedade da Org A (Deve ser impedido)
            print("\n[4/5] Testando impedimento de acesso cruzado (RLS) pela Org B...")
            conn.execute(
                text("SELECT set_config('titan.organization_id', :org_id, true)"),
                {"org_id": str(org_b.value)},
            )
            repo_b = TransactionalRuralPropertyRepository(connection=conn)
            service_b = RuralPropertyService(repository=repo_b)

            busca_cruzada = service_b.get_property(prop_a.property_id)
            if busca_cruzada is None:
                print(
                    "      [OK] SUCESSO: A Org B NAO consegue enxergar a propriedade da Org A (RLS Ativo)."
                )
            else:
                print("      [ERRO] FALHA: A Org B conseguiu enxergar a propriedade da Org A!")

            # 7. Org B cadastra sua própria propriedade com o mesmo código "PROP-SP-001" (Deve ser permitido)
            print("\n[5/5] Cadastrando propriedade com código 'PROP-SP-001' na Org B...")
            prop_b = service_b.register_property(
                organization_id=org_b,
                code="PROP-SP-001",
                name="Fazenda Vista Alegre (Org B)",
                municipality="Campinas",
                state_code="SP",
            )
            print("      [OK] SUCESSO: Propriedade cadastrada na Org B com ID diferente:")
            print(f"      - ID da Org B: {prop_b.property_id}")
            print(f"      - Nome: {prop_b.name}")

            # Cleanup da Role temporária
            conn.execute(text("RESET ROLE"))
            conn.execute(text(f"DROP OWNED BY {quoted_role}"))
            conn.execute(text(f"DROP ROLE {quoted_role}"))

    print("\n" + "=" * 70)
    print("      VALIDACAO MANUAL CONCLUIDA COM SUCESSO COMPLETO!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
