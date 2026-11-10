<#
.SYNOPSIS
  Guarded setup of a LOCAL, disposable PostgreSQL test database for the DB-backed tests (docs/TEST_PLAN.md).
.DESCRIPTION
  Stages: Create (empty wealthpilot_test), Verify (read-only safety checks), Migrate (alembic upgrade head against the test target), Test (pytest the monthly-records file), All.
  Needs PostgreSQL already installed locally (see TEST_PLAN.md step 1; installing needs administrator approval and is not done here). Session-only environment variables are
  used; .env is never read for the destination or edited. Nothing is printed that contains the password. The script never contacts a hosted database and never drops anything.
.EXAMPLE
  .\scripts\local_test_db.ps1 -Stage All
#>
param(
    [ValidateSet("Create", "Verify", "Migrate", "Test", "All")][string]$Stage = "All",
    [string]$PgBin = "C:\Program Files\PostgreSQL\17\bin"
)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Db = "wealthpilot_test"
$psql = Join-Path $PgBin "psql.exe"
$py = Join-Path $Repo ".venv\Scripts\python.exe"

function Stop-Unsafe([string]$why) { Write-Host "STOP: $why" -ForegroundColor Red; exit 1 }
function Psql([string]$database, [string]$sql) { & $psql -U postgres -h localhost -d $database -tAc $sql }

if (-not (Test-Path $psql)) { Stop-Unsafe "psql not found at $psql. Install PostgreSQL first (docs/TEST_PLAN.md step 1) or pass -PgBin." }
$sec = Read-Host "postgres superuser password (local server)" -AsSecureString
$pw = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
if ($pw -notmatch '^[A-Za-z0-9]+$') { Stop-Unsafe "use a letters-and-digits password so the URL needs no escaping" }
$env:PGPASSWORD = $pw
$env:TEST_DATABASE_URL = "postgresql://postgres:$pw@localhost:5432/$Db"
$env:DATABASE_URL = $env:TEST_DATABASE_URL
Remove-Item Env:ALEMBIC_TARGET -ErrorAction SilentlyContinue

function Invoke-Create {
    $exists = Psql "postgres" "select 1 from pg_database where datname = '$Db';"
    if ($exists -eq "1") { Write-Host "$Db already exists; not recreating. Verify will decide whether it is empty." }
    else { & $psql -U postgres -h localhost -d postgres -c "CREATE DATABASE $Db;"; Write-Host "created empty $Db" }
}

function Invoke-Verify([bool]$requireEmpty) {
    # 1. effective destination, read through the application's own Settings (no database access, no secrets printed)
    $hosts = & $py -c "from urllib.parse import urlsplit as u; from wealthpilot.config import get_settings as g; s=g(); a=u(s.test_database_url); b=u(s.database_url); print(a.hostname, a.path.strip('/'), b.hostname, b.path.strip('/'))"
    $parts = $hosts -split ' '
    if ($parts.Count -ne 4 -or $parts[0] -ne "localhost" -or $parts[2] -ne "localhost") { Stop-Unsafe "effective host is not localhost for both settings: $hosts" }
    if ($parts[1] -ne $Db -or $parts[3] -ne $Db) { Stop-Unsafe "effective database name is not exactly $Db" }
    # 2. the server really is local and the database is the right one
    $row = Psql $Db "select current_database() || ' ' || coalesce(host(inet_server_addr()), 'socket');"
    $dbName, $addr = $row -split ' '
    if ($dbName -ne $Db) { Stop-Unsafe "connected database is $dbName" }
    if ($addr -notin @("127.0.0.1", "::1", "socket")) { Stop-Unsafe "server address $addr is not loopback" }
    # 3. a fresh local instance holds only the default databases plus this one
    $names = (Psql "postgres" "select datname from pg_database where not datistemplate order by 1;") -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $extra = $names | Where-Object { $_ -notin @("postgres", $Db) }
    if ($extra) { Stop-Unsafe "server holds other databases ($($extra -join ', ')); it is not a fresh instance" }
    # 4. no user tables yet (before the first migration)
    $tables = [int](Psql $Db "select count(*) from information_schema.tables where table_schema not in ('pg_catalog','information_schema');")
    if ($requireEmpty -and $tables -ne 0) { Stop-Unsafe "$Db already has $tables table(s); refusing to migrate a non-empty database" }
    Write-Host "VERIFIED: localhost, database $Db, loopback server, no other databases, tables=$tables"
}

if ($Stage -in @("Create", "All")) { Invoke-Create }
if ($Stage -in @("Verify", "All", "Migrate")) { Invoke-Verify $true }
if ($Stage -in @("Migrate", "All")) {
    Push-Location (Join-Path $Repo "backend")
    try {
        $env:ALEMBIC_TARGET = "test"
        & (Join-Path $Repo ".venv\Scripts\alembic.exe") upgrade head
        if ($LASTEXITCODE -ne 0) { Stop-Unsafe "alembic upgrade failed (exit $LASTEXITCODE)" }
        & (Join-Path $Repo ".venv\Scripts\alembic.exe") current
    } finally { Remove-Item Env:ALEMBIC_TARGET -ErrorAction SilentlyContinue; Pop-Location }
}
if ($Stage -in @("Test", "All")) {
    Invoke-Verify $false
    Push-Location $Repo
    try { & $py -m pytest tests/backend/api/test_monthly_records.py -v } finally { Pop-Location }
}
Remove-Item Env:PGPASSWORD, Env:TEST_DATABASE_URL, Env:DATABASE_URL -ErrorAction SilentlyContinue
