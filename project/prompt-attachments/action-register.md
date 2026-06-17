## Action Register

- **ID**: QA-BLOCK-1  
  **Source**: Problem Solver  
  **Finding**: Test execution is at risk of hanging because `QMessageBox` stubbing is inconsistent and not enforced suite-wide; current main-window test run exceeded the 30s cap.  
  **Disposition**: fix now  
  **Owner**: QA Engineer  
  **Target**: this task  
  **Status**: closed

- **ID**: DEV-1  
  **Source**: Product Developer  
  **Finding**: `FakeGenerationService.process_row()` in `tests/test_main_window.py` does not yet accept the new `attachments` keyword argument, so prompt-attachment-enabled generation tests will fail until the test double is updated.  
  **Disposition**: fix now  
  **Owner**: QA Engineer  
  **Target**: this task  
  **Status**: closed

- **ID**: AR-1  
  **Source**: Code Architect  
  **Finding**: When no project knowledge-base directory is configured, the blocked KB-file add action should explicitly explain why it is unavailable instead of only disabling the button.  
  **Disposition**: fix now  
  **Owner**: Product Developer  
  **Target**: this task  
  **Status**: closed
