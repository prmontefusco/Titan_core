<#
.SYNOPSIS
    Zera o banco Titan local (Postgres) e reconstrói o mínimo para operar.

.DESCRIPTION
    Derruba e recria o volume `postgres_data` do Titan, reprovisiona o papel
    de runtime restrito, aplica as migrations do zero, roda o bootstrap mínimo
    da Organization operadora, concede ADMIN_MESTRE ao usuário administrador
    configurado abaixo, concede a ele também os papéis operacionais extras
    (governança de regras/política e LIVESTOCK_PERMISSIONS de operador -- ver
    apps/grant_local_admin_governance.py) e, por padrão, semeia dados de
    demonstração.

    NÃO afeta o Keycloak (usuários e realm sobrevivem -- outro volume) nem o
    Titan_geodata. Só o banco de aplicação do Titan.

    Pensado para o ciclo "testar, zerar, testar" durante o desenvolvimento --
    nunca rode isto contra um ambiente compartilhado ou com dado real.

.PARAMETER SemSemeadura
    Pula `apps.seed` (organizações e usuários de demonstração fictícios).

.EXAMPLE
    .\scripts\dev-reset.ps1
.EXAMPLE
    .\scripts\dev-reset.ps1 -SemSemeadura
#>

param(
    [switch]$SemSemeadura
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Invoke-TitanNative {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Comando falhou com exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

# Valores fixos e locais, sem segredo -- mesma convenção de
# scripts\iniciar_servidor.md e scripts\dev-up.ps1. Para administrar com outro
# usuário Keycloak, troque $TitanBootstrapSubject pelo "ID" dele (Keycloak
# Admin Console -> Users -> <usuario> -> ID, ou via admin API com
# GET /admin/realms/titan/users?username=<usuario>).
$TitanOperatorOrg = "20000000-0000-4000-8000-000000000001"
$TitanTargetOrg = "9ddb2b8b-2fed-48d4-b5ed-a0d308994dbc"
$TitanAuthorityActor = "20000000-0000-4000-8000-000000000002"
$TitanBootstrapIssuer = "http://localhost:8080/realms/titan"
$TitanBootstrapSubject = "1835563b-56e6-4701-b3c3-33f702884457"  # prmontefusco

Write-Host "== Derrubando e zerando o volume do Postgres do Titan ==" -ForegroundColor Cyan
Invoke-TitanNative "docker" @("compose", "down")
docker volume inspect titan_postgres_data *> $null
if ($LASTEXITCODE -eq 0) {
    Invoke-TitanNative "docker" @("volume", "rm", "titan_postgres_data")
}
Invoke-TitanNative "docker" @("compose", "up", "--detach", "--wait", "postgres", "keycloak")

$env:TITAN_MIGRATION_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
$env:TITAN_DATABASE_URL = $env:TITAN_MIGRATION_DATABASE_URL

Write-Host "== Aplicando migrations ==" -ForegroundColor Cyan
Invoke-TitanNative "python" @("-m", "uv", "run", "--locked", "alembic", "upgrade", "heads")

Write-Host "== Provisionando o papel de runtime restrito ==" -ForegroundColor Cyan
$env:TITAN_RUNTIME_DATABASE_PASSWORD = "titan_local_runtime_password"
Invoke-TitanNative "python" @(
    "-m", "uv", "run", "--locked", "python", "-m", "apps.provision_runtime_database_role"
)

Write-Host "== Bootstrap da Organization operadora ==" -ForegroundColor Cyan
$env:TITAN_OPERATOR_ORGANIZATION_ID = $TitanOperatorOrg
$env:TITAN_BOOTSTRAP_AUTHORITY_ACTOR_ID = $TitanAuthorityActor
$env:TITAN_ENVIRONMENT = "DESENVOLVIMENTO"
Invoke-TitanNative "python" @("-m", "uv", "run", "--locked", "python", "-m", "apps.bootstrap")

Write-Host "== Concedendo ADMIN_MESTRE ao usuario administrador ==" -ForegroundColor Cyan
$env:TITAN_BOOTSTRAP_ADMIN_CONFIRM = "1"
$env:TITAN_BOOTSTRAP_ORGANIZATION_ID = $TitanTargetOrg
$env:TITAN_BOOTSTRAP_ISSUER = $TitanBootstrapIssuer
$env:TITAN_BOOTSTRAP_SUBJECT = $TitanBootstrapSubject
Invoke-TitanNative "python" @(
    "-m", "uv", "run", "--locked", "python", "-m", "apps.bootstrap_admin"
)

Write-Host "== Concedendo papeis operacionais (regras/politica + livestock) ao mesmo usuario ==" -ForegroundColor Cyan
$env:TITAN_GRANT_ORGANIZATION_ID = $TitanTargetOrg
$env:TITAN_GRANT_ISSUER = $TitanBootstrapIssuer
$env:TITAN_GRANT_SUBJECT = $TitanBootstrapSubject
Invoke-TitanNative "python" @(
    "-m", "uv", "run", "--locked", "python", "-m", "apps.grant_local_admin_governance"
)

if (-not $SemSemeadura) {
    Write-Host "== Semeando dados de demonstracao ==" -ForegroundColor Cyan
    $env:TITAN_SEED_CONFIRM = "1"
    $env:TITAN_SEED_PRIMARY_ORGANIZATION_ID = $TitanTargetOrg
    Invoke-TitanNative "python" @("-m", "uv", "run", "--locked", "python", "-m", "apps.seed")
}

Write-Host ""
Write-Host "Pronto." -ForegroundColor Green
Write-Host "Organization operadora : $TitanOperatorOrg"
Write-Host "Organization de uso    : $TitanTargetOrg"
Write-Host "apps/web/.env.local ja aponta para essa Organization -- nada a mudar la."
Write-Host ""
Write-Host "Suba a API e o frontend com: .\scripts\dev-up.ps1" -ForegroundColor Green
