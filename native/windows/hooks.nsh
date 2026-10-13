; Kill UI + backend before install/uninstall (backend locks resources/*.exe).
; Client registration: mcp-clients.nsh (vendored fleet canonical) registers the
; stdio backend in detected AI tools (Claude/Cursor/Antigravity/OpenCode).
!define MCP_REG_NAME "beyondcompare-mcp"
!define MCP_REG_EXE "beyondcompare-mcp-backend.exe"
!include "mcp-clients.nsh"
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
  !insertmacro McpClientsUnregister
!macroend

!macro NSIS_HOOK_POSTINSTALL
  !insertmacro McpClientsRegister
!macroend
