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
$TitanDatabaseUrl = "postgresql+psycopg://titan_app:titan_local_runtime_password@127.0.0.1:5432/titan"

Write-Host "== Subindo containers de infraestrutura ==" -ForegroundColor Cyan
docker compose up --detach --wait postgres mongo keycloak rabbitmq valkey

Write-Host "== Aplicando migrations (idempotente) ==" -ForegroundColor Cyan
$env:TITAN_DATABASE_URL = $TitanDatabaseUrl
python -m uv run --locked alembic upgrade head

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
