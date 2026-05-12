param(
  [string]$Root = ".\runs\my-rpg\build\web-rpg",
  [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$rootFull = [System.IO.Path]::GetFullPath($Root)
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $Port)
$listener.Start()
Write-Host "Serving $rootFull on http://0.0.0.0:$Port/"

function Get-ContentType([string]$Path) {
  switch ([System.IO.Path]::GetExtension($Path).ToLowerInvariant()) {
    ".html" { "text/html; charset=utf-8"; break }
    ".js" { "application/javascript; charset=utf-8"; break }
    ".css" { "text/css; charset=utf-8"; break }
    ".png" { "image/png"; break }
    ".jpg" { "image/jpeg"; break }
    ".jpeg" { "image/jpeg"; break }
    ".gif" { "image/gif"; break }
    ".mp3" { "audio/mpeg"; break }
    ".wav" { "audio/wav"; break }
    default { "application/octet-stream"; break }
  }
}

while ($true) {
  $client = $listener.AcceptTcpClient()
  try {
    $stream = $client.GetStream()
    $buffer = New-Object byte[] 8192
    $count = $stream.Read($buffer, 0, $buffer.Length)
    if ($count -le 0) { continue }

    $request = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $count)
    $first = ($request -split "`r?`n")[0]
    $parts = $first -split " "
    $url = if ($parts.Length -ge 2) { $parts[1] } else { "/" }
    $path = [System.Uri]::UnescapeDataString(($url -split "\?")[0])
    if ($path -eq "/") { $path = "/index.html" }

    $rel = $path.TrimStart("/").Replace("/", "\")
    $file = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($rootFull, $rel))
    if (-not $file.StartsWith($rootFull)) { throw "Bad path" }

    if ([System.IO.File]::Exists($file)) {
      $bytes = [System.IO.File]::ReadAllBytes($file)
      $type = Get-ContentType $file
      $header = "HTTP/1.1 200 OK`r`nContent-Type: $type`r`nContent-Length: $($bytes.Length)`r`nConnection: close`r`n`r`n"
    } else {
      $bytes = [System.Text.Encoding]::UTF8.GetBytes("Not Found")
      $header = "HTTP/1.1 404 Not Found`r`nContent-Type: text/plain`r`nContent-Length: $($bytes.Length)`r`nConnection: close`r`n`r`n"
    }

    $headerBytes = [System.Text.Encoding]::ASCII.GetBytes($header)
    $stream.Write($headerBytes, 0, $headerBytes.Length)
    $stream.Write($bytes, 0, $bytes.Length)
  } catch {
    try {
      $bytes = [System.Text.Encoding]::UTF8.GetBytes("Server Error")
      $header = [System.Text.Encoding]::ASCII.GetBytes("HTTP/1.1 500 Server Error`r`nContent-Length: $($bytes.Length)`r`nConnection: close`r`n`r`n")
      $stream.Write($header, 0, $header.Length)
      $stream.Write($bytes, 0, $bytes.Length)
    } catch {}
  } finally {
    $client.Close()
  }
}
