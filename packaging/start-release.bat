@echo off
set "APP=%~dp0AIErrorReviewWorkbench.exe"
if not exist "%APP%" (
  echo Application files are incomplete. Extract the full release again.
  pause
  exit /b 1
)
start "" "%APP%"
echo Starting AI Error Review Workbench...
