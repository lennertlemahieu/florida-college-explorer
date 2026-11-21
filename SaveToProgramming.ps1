$ErrorActionPreference = 'Stop'
$destination = 'C:\Users\lenne\OneDrive - New College of Florida\NCFL\fall_cources\programming\Florida College Explorer'
$source = [System.IO.Path]::GetFullPath($PSScriptRoot)
$resolvedDestination = [System.IO.Path]::GetFullPath($destination)
if ($source -eq $resolvedDestination) {
    Write-Host "The project is already in $destination"
    exit 0
}
if (Test-Path -LiteralPath $destination) {
    throw "The destination already exists. No files were overwritten: $destination"
}
New-Item -ItemType Directory -Path $destination | Out-Null
$items = @('app.py','data_api.py','analysis.py','assets.py','ai.py','map_view.py','campus_map.py',
    'requirements.txt','README.md','DEMO.md','PROJECT_REPORT_OUTLINE.md',
    'start.ps1','SaveToProgramming.ps1','.gitignore',
    '.streamlit/config.toml','.streamlit/secrets.toml.example','data/overrides.csv',
    'tests/test_data.py','tests/test_app.py')
foreach ($item in $items) {
    $targetFile = Join-Path $destination $item
    $targetDirectory = Split-Path -Parent $targetFile
    New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $source $item) -Destination $targetFile
}
Write-Host "Saved all project files to: $destination"
Write-Host 'Open README.md for setup or run start.ps1 from the new folder.'
