# Per-repo fleet start config for beyondcompare-mcp
# Edit ports/backend target here - start.ps1 is fleet-standard.
@{
    Name         = 'beyondcompare-mcp'
    BackendPort  = 10841
    FrontendPort = 10840
    HealthPath   = '/api/v1/health'
    WebRoot      = 'D:\Dev\repos\beyondcompare-mcp\web_sota'
    Backend = @{
        Kind          = 'uvicorn'
        UvicornTarget = 'beyondcompare_mcp.server:app'
        SyncExtras    = @('dev')
        Env           = @{ WEB_PORT = '10841' }
    }
    Frontend = @{
        Kind           = 'vite-npm'
        PackageManager = 'npm'
        PortEnvVar     = 'VITE_PORT'
        ApiTargetEnv   = 'VITE_API_TARGET'
    }
}
