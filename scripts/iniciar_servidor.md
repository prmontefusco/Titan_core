Terminal 1 — API:

cd C:\programing\Titan
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
$env:TITAN_OPERATOR_ORGANIZATION_ID="20000000-0000-4000-8000-000000000001"
$env:TITAN_OIDC_ISSUER="http://localhost:8080/realms/titan"
$env:TITAN_OIDC_AUDIENCE="titan-api"
$env:TITAN_CORS_ORIGINS="http://localhost:5173"
python -m uv run --locked uvicorn apps.api.main:app --host 127.0.0.1 --port 8000




Terminal 2 — Frontend:
cd C:\programing\Titan\apps\web
npm run dev