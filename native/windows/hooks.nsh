; Kill UI + backend before install/uninstall (backend locks resources/*.exe).
; NOTE 2026-10-13: the fleet mcp-clients.nsh !include pattern (defines +
; !include "mcp-clients.nsh") does NOT build — makensis cannot resolve the
; nested relative include from the generated installer.nsi dir, and no fleet
; repo has a post-change installer proving otherwise (arxiv's setup.exe
; predates its hooks.nsh change). Vendored copy kept at windows/mcp-clients.nsh
; for when the pattern is proven. Registration runs via install-mcp-clients.ps1.
!macro KillBeyondcompareMcpFleetProcesses
  DetailPrint "Stopping beyondcompare-mcp processes..."
  ExecWait 'taskkill /F /IM beyondcompare-mcp-backend.exe /T' $0
  ExecWait 'taskkill /F /IM beyondcompare-mcp-native.exe /T' $0
  !if "${INSTALLMODE}" == "currentUser"
    nsis_tauri_utils::KillProcessCurrentUser "beyondcompare-mcp-backend.exe"
    Pop $0
    nsis_tauri_utils::KillProcessCurrentUser "beyondcompare-mcp-native.exe"
    Pop $0
  !else
    nsis_tauri_utils::KillProcess "beyondcompare-mcp-backend.exe"
    Pop $0
    nsis_tauri_utils::KillProcess "beyondcompare-mcp-native.exe"
    Pop $0
  !endif
  Sleep 2000
!macroend

!macro NSIS_HOOK_PREINSTALL
  !insertmacro KillBeyondcompareMcpFleetProcesses
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  !insertmacro KillBeyondcompareMcpFleetProcesses
!macroend

!macro NSIS_HOOK_POSTINSTALL
  IfFileExists "$INSTDIR\resources\install-mcp-clients.ps1" 0 mcp_hook_done
    DetailPrint "Optional: register beyondcompare-mcp in Cursor / Claude Desktop"
    ExecWait 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\resources\install-mcp-clients.ps1" -Interactive'
  mcp_hook_done:
!macroend
