# Read-only verification. This script never installs, edits or deletes SD files.
[CmdletBinding()]
param([string]$SdRoot)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-PackagePath([string]$Root, [string]$Relative) {
    if ($Relative -match '(^/|\\|:|(^|/)\.\.(/|$))') { throw "Unsafe package path: $Relative" }
    $resolvedRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    $candidate = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if (-not $candidate.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Package path is outside its root: $Relative"
    }
    return $candidate
}

try {
    $packageRoot = $PSScriptRoot
    $manifest = Get-Content -Raw -LiteralPath (Join-Path $packageRoot 'manifest.json') | ConvertFrom-Json
    if ($manifest.schema -ne 1 -or $manifest.abi -ne 'fxtmem-v1') { throw 'Unknown manifest format' }
    $checksumNames = @{}
    foreach ($line in Get-Content -LiteralPath (Join-Path $packageRoot 'SHA256SUMS.txt')) {
        if ($line -notmatch '^([a-f0-9]{64})  (.+)$') { throw 'Invalid SHA256SUMS.txt line' }
        $expected = $Matches[1]
        $relative = $Matches[2]
        if ($checksumNames.ContainsKey($relative)) { throw "Duplicate checksum: $relative" }
        $checksumNames[$relative] = $true
        $file = Get-PackagePath $packageRoot $relative
        if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $expected) {
            throw "Hash mismatch: $relative. Copy/download the package again."
        }
    }
    if (-not $checksumNames.ContainsKey('manifest.json')) { throw 'Manifest checksum missing' }
    if ($checksumNames.Count -ne @($manifest.files.PSObject.Properties).Count + 1) {
        throw 'Incomplete checksum list'
    }
    foreach ($file in Get-ChildItem -LiteralPath $packageRoot -File -Recurse) {
        $relative = $file.FullName.Substring($packageRoot.Length + 1).Replace('\', '/')
        if ($relative -ne 'SHA256SUMS.txt' -and -not $checksumNames.ContainsKey($relative)) {
            throw "Undeclared package file: $relative"
        }
    }
    foreach ($item in $manifest.files.PSObject.Properties) {
        if (-not $checksumNames.ContainsKey($item.Name)) { throw "Checksum missing: $($item.Name)" }
        $file = Get-PackagePath $packageRoot $item.Name
        if ((Get-Item -LiteralPath $file).Length -ne $item.Value.bytes -or
            (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $item.Value.sha256) {
            throw "Manifest mismatch: $($item.Name)"
        }
    }
    Write-Output "PASS package: FEXTendo Memory $($manifest.version), official HOC $($manifest.hoc) defaults"

    if ($SdRoot) {
        $sdPath = (Resolve-Path -LiteralPath $SdRoot).ProviderPath
        foreach ($item in $manifest.files.PSObject.Properties) {
            if (-not $item.Name.StartsWith('SD/')) { continue }
            $relative = $item.Name.Substring(3)
            $file = Get-PackagePath $sdPath $relative
            if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $item.Value.sha256) {
                throw "SD copy mismatch: $relative"
            }
        }
        $pkg3 = [IO.File]::ReadAllBytes((Get-PackagePath $sdPath 'atmosphere/package3'))
        if ($pkg3.Length -lt 64 -or [Text.Encoding]::ASCII.GetString($pkg3, 0, 4) -ne 'PK31' -or
            [Text.Encoding]::ASCII.GetString($pkg3, 32, 4) -ne 'FSS0' -or
            [BitConverter]::ToUInt32($pkg3, 36) -ne $pkg3.Length) {
            throw 'Invalid or incomplete atmosphere/package3'
        }
        $amsVersion = "$($pkg3[59]).$($pkg3[58]).$($pkg3[57])"
        if ($amsVersion -ne $manifest.atmosphere) {
            throw "Atmosphere $amsVersion is installed; this boot pair requires $($manifest.atmosphere)."
        }
        $lock = Get-Content -Raw -LiteralPath (Join-Path $packageRoot 'provenance/boot-lock.json') | ConvertFrom-Json
        $revision = '{0:x8}' -f [BitConverter]::ToUInt32($pkg3, 60)
        if ($revision -ne $lock.atmosphere_revision.Substring(0, 8)) {
            throw "Atmosphere source revision $revision differs from the pinned build."
        }
        $emuIni = Get-Content -LiteralPath (Get-PackagePath $sdPath 'emuMMC/emummc.ini')
        $inEmu = $false
        $enabled = $false
        foreach ($line in $emuIni) {
            if ($line -match '^\s*\[(.+)\]\s*$') { $inEmu = ($Matches[1] -eq 'emummc'); continue }
            if ($inEmu -and $line -match '^\s*enabled\s*=\s*1\s*$') { $enabled = $true }
        }
        if (-not $enabled) { throw 'emuMMC is missing/disabled. Enable it in Hekate; this entry never falls back to sysMMC.' }
        foreach ($module in @('bootloader/sys/nyx.bin', 'bootloader/sys/emummc.kipm')) {
            if (-not (Test-Path -LiteralPath (Get-PackagePath $sdPath $module) -PathType Leaf)) {
                throw "Hekate module is missing: $module"
            }
        }
        if (Test-Path -LiteralPath (Get-PackagePath $sdPath 'bootloader/ini/fextendo-memory-v1.ini')) {
            Write-Output 'NOTE: The old Memory v1 TEST entry is still present. Keep it for rollback until the new entry boots.'
        }
        Write-Output "PASS SD copy and prerequisites: Atmosphere $amsVersion, enabled emuMMC, Hekate modules"
        Write-Output "Check HOS $($manifest.hos_reference) on the console. This PC check does not boot Horizon or test hardware."
    } else {
        Write-Output 'Optional SD check after copying: .\Check-Package.ps1 -SdRoot E:\'
        Write-Output 'Use an SD reader or Hekate UMS drive letter; Windows MTP is not a filesystem drive.'
    }
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
