<#
.SYNOPSIS
    Sobe a stack local completa do Titan com um comando: infraestrutura,
    migrations, API e frontend.

.DESCRIPTION
    Substitui reunir os passos espalhados por AGENTS.md/DEVELOPMENT.md a cada
    vez que se quer testar. Pressupõe que o banco já foi inicializado ao menos
    uma vez (papel titan_app provisionado, migrations aplicadas, Organization
    operadora e usuário administrador existentes) -- para começar do zero, rode
    primeiro scripts\dev-reset.ps1.

    API e frontend sobem cada um em uma janela PowerShell própria, para que os
    logs de cada um fiquem visíveis e separados -- este script não bloqueia
    esperando por eles.

.EXAMPLE
    .\scripts\dev-up.ps1
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

# Mesma convenção já usada em scripts\dev-reset.ps1 e scripts\iniciar_servidor.md.
$TitanOperatorOrg = "20000000-0000-4000-8000-000000000001"
$TitanTargetOrg = "9ddb2b8b-2fed-48d4-b5ed-a0d308994dbc"
$TitanDatabaseUrl = "postgresql+psycopg://titan_app:titan_local_runtime_password@127.0.0.1:5432/titan"
$TitanDemoPassword = "titan_demo_local"
$TitanDemoOperatorUser = "titan_operador"
$TitanDemoAuditorUser = "titan_auditor"
$TitanKeycloakAdminUser = "titan_admin"
$TitanKeycloakAdminPassword = "titan_oidc_local_admin_password"

Write-Host "== Subindo containers de infraestrutura ==" -ForegroundColor Cyan
docker compose up --detach --wait postgres mongo keycloak rabbitmq valkey

Write-Host "== Aplicando migrations (idempotente) ==" -ForegroundColor Cyan
$env:TITAN_DATABASE_URL = $TitanDatabaseUrl
python -m uv run --locked alembic upgrade head

Write-Host "== Conferindo semeadura local da Organization da UI ==" -ForegroundColor Cyan
$organizationCheckCommand = @'
import os
import sys

from sqlalchemy import create_engine, text

database_url = os.environ["TITAN_DATABASE_URL"]
organization_id = os.environ["TITAN_DEV_TARGET_ORGANIZATION_ID"]

engine = create_engine(database_url)
try:
    with engine.connect() as connection, connection.begin():
        connection.execute(
            text("SELECT set_config('titan.organization_id', :organization_id, true)"),
            {"organization_id": organization_id},
        )
        exists = connection.execute(
            text(
                "SELECT 1 FROM core_identity.organizations "
                "WHERE organization_id = :organization_id"
            ),
            {"organization_id": organization_id},
        ).scalar_one_or_none()
finally:
    engine.dispose()

sys.exit(0 if exists is not None else 2)
'@
$env:TITAN_DEV_TARGET_ORGANIZATION_ID = $TitanTargetOrg
$organizationCheckCommand | python -m uv run --locked python -
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "A Organization local usada pela UI nao existe no banco: $TitanTargetOrg" -ForegroundColor Red
    Write-Host "Rode .\scripts\dev-reset.ps1 uma vez para recriar a semeadura local e depois execute .\scripts\dev-up.ps1 novamente." -ForegroundColor Yellow
    exit $LASTEXITCODE
}

Write-Host "== Iniciando a API numa janela separada ==" -ForegroundColor Cyan
$apiCommand = @"
Set-Location '$RepoRoot'
`$env:TITAN_DATABASE_URL = '$TitanDatabaseUrl'
`$env:TITAN_OPERATOR_ORGANIZATION_ID = '$TitanOperatorOrg'
`$env:TITAN_OIDC_ISSUER = 'http://localhost:8080/realms/titan'
`$env:TITAN_OIDC_AUDIENCE = 'titan-api'
`$env:TITAN_CORS_ORIGINS = 'http://localhost:5173'
python -m uv run --locked uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $apiCommand

Write-Host "== Iniciando o frontend numa janela separada ==" -ForegroundColor Cyan
$webCommand = @"
Set-Location '$RepoRoot\apps\web'
npm run dev
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $webCommand

Write-Host ""
Write-Host "API: acompanhe a janela dela até 'Application startup complete' (http://127.0.0.1:8000)." -ForegroundColor Green
Write-Host "Frontend: acompanhe a janela dele para a porta real do Vite (normalmente http://localhost:5173)." -ForegroundColor Green
Write-Host ""
Write-Host "Organization local da UI: $TitanTargetOrg" -ForegroundColor Cyan
Write-Host "Credenciais locais de teste (criadas pela semeadura de scripts\dev-reset.ps1):" -ForegroundColor Cyan
Write-Host "  Operador pecuario : $TitanDemoOperatorUser / $TitanDemoPassword"
Write-Host "  Auditor           : $TitanDemoAuditorUser / $TitanDemoPassword"
Write-Host "  Admin Keycloak    : $TitanKeycloakAdminUser / $TitanKeycloakAdminPassword"
Write-Host ""
Write-Host "Se o login entrar mas aparecer 'Falha ao verificar permissoes', rode scripts\dev-reset.ps1 para recriar a semeadura e os vinculos da Organization." -ForegroundColor Yellow
