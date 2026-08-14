Um comando só (equivalente aos dois terminais abaixo, cada um numa janela própria):

    .\scripts\dev-up.ps1

Para zerar o banco local antes ("testar, zerar, testar"):

    .\scripts\dev-reset.ps1

---

Os dois terminais manuais, se preferir controlar cada um à mão:

Terminal 1 — API:

cd C:\programing\Titan
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan_app:titan_local_runtime_password@127.0.0.1:5432/titan"
$env:TITAN_OPERATOR_ORGANIZATION_ID="20000000-0000-4000-8000-000000000001"
$env:TITAN_OIDC_ISSUER="http://localhost:8080/realms/titan"
$env:TITAN_OIDC_AUDIENCE="titan-api"
$env:TITAN_CORS_ORIGINS="http://localhost:5173"
python -m uv run --locked uvicorn apps.api.main:app --host 127.0.0.1 --port 8000

Atenção: TITAN_DATABASE_URL precisa apontar para o papel restrito `titan_app`,
nunca para o superusuário `titan` -- `assert_runtime_database_role` recusa a
conexão (e derruba a requisição sem resposta HTTP limpa, o que o navegador
mostra como falha de CORS) se a credencial for SUPERUSER ou BYPASSRLS.




Terminal 2 — Frontend:
cd C:\programing\Titan\apps\web
npm run dev