<#
.SYNOPSIS
    Zera o banco Titan local (Postgres) e reconstrói o mínimo para operar.

.DESCRIPTION
    Derruba e recria o volume `postgres_data` do Titan, reprovisiona o papel
    de runtime restrito, aplica as migrations do zero, roda o bootstrap mínimo
    da Organization operadora, concede ADMIN_MESTRE ao usuário administrador
    configurado abaixo e, por padrão, semeia dados de demonstração.

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
docker compose down
docker volume rm titan_postgres_data -ErrorAction SilentlyContinue
docker compose up --detach --wait postgres

Write-Host "== Provisionando o papel de runtime restrito ==" -ForegroundColor Cyan
$env:TITAN_MIGRATION_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
$env:TITAN_RUNTIME_DATABASE_PASSWORD = "titan_local_runtime_password"
python -m uv run --locked python -m apps.provision_runtime_database_role

Write-Host "== Aplicando migrations ==" -ForegroundColor Cyan
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan_app:titan_local_runtime_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head

Write-Host "== Bootstrap da Organization operadora ==" -ForegroundColor Cyan
$env:TITAN_OPERATOR_ORGANIZATION_ID = $TitanOperatorOrg
$env:TITAN_BOOTSTRAP_AUTHORITY_ACTOR_ID = $TitanAuthorityActor
$env:TITAN_ENVIRONMENT = "DESENVOLVIMENTO"
python -m uv run --locked python -m apps.bootstrap

Write-Host "== Concedendo ADMIN_MESTRE ao usuario administrador ==" -ForegroundColor Cyan
$env:TITAN_BOOTSTRAP_ORGANIZATION_ID = $TitanTargetOrg
$env:TITAN_BOOTSTRAP_ISSUER = $TitanBootstrapIssuer
$env:TITAN_BOOTSTRAP_SUBJECT = $TitanBootstrapSubject
python -m uv run --locked python -m apps.bootstrap_admin

Write-Host "== Concedendo governanca de regras e politicas ao mesmo usuario ==" -ForegroundColor Cyan
$env:TITAN_GRANT_ORGANIZATION_ID = $TitanTargetOrg
$env:TITAN_GRANT_ISSUER = $TitanBootstrapIssuer
$env:TITAN_GRANT_SUBJECT = $TitanBootstrapSubject
python -m uv run --locked python scripts\grant_local_admin_governance.py

if (-not $SemSemeadura) {
    Write-Host "== Semeando dados de demonstracao ==" -ForegroundColor Cyan
    $env:TITAN_SEED_CONFIRM = "1"
    python -m uv run --locked python -m apps.seed
}

Write-Host ""
Write-Host "Pronto." -ForegroundColor Green
Write-Host "Organization operadora : $TitanOperatorOrg"
Write-Host "Organization de uso    : $TitanTargetOrg"
Write-Host "apps/web/.env.local ja aponta para essa Organization -- nada a mudar la."
Write-Host ""
Write-Host "Suba a API e o frontend com: .\scripts\dev-up.ps1" -ForegroundColor Green
