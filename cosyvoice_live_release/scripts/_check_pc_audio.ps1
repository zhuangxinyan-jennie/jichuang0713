Write-Host "=== Playback endpoints ==="
Get-PnpDevice -Class AudioEndpoint -Status OK |
  Select-Object FriendlyName, Status |
  Format-Table -AutoSize

Write-Host "=== Error / Unknown PnP ==="
Get-PnpDevice |
  Where-Object { $_.Status -eq "Error" -or $_.Status -eq "Unknown" } |
  Select-Object Status, Class, FriendlyName |
  Format-Table -AutoSize

Write-Host "=== USB Composite / Audio-ish ==="
Get-PnpDevice -PresentOnly |
  Where-Object {
    $_.FriendlyName -match "Audio|CS202|Speaker|扬声|USB Device|Composite|Edifier|UGREEN|BlueTrm|CM564|1F3A|Sound"
  } |
  Select-Object Status, Class, FriendlyName |
  Format-Table -AutoSize

Write-Host "=== Default playback hint (registry / mmdevices) ==="
# List playback device names from AudioEndpoint that look like speakers
Get-PnpDevice -Class AudioEndpoint -PresentOnly |
  Where-Object { $_.InstanceId -like "*0.0.0.00000000*" } |
  Select-Object Status, FriendlyName |
  Format-Table -AutoSize
