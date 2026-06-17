# Action Register — Knowledge Base Manager

| ID | Source | Finding | Disposition | Owner | Target | Status |
|---|---|---|---|---|---|---|
| AR-1 | User review | Spec/implementation drifted from the original request by not explicitly carrying forward the user's input as a persistent note for downstream specialists. | fix now | Leader | this task | closed |
| AR-2 | User review | CSV editor behavior must include add/remove rows and columns, not just editing existing text cells. | fix now | Architect + Product Developer | this task | in_progress |
| AR-3 | Leader review | CSV editor must preserve heuristically detected CSV settings on save instead of rewriting every file as comma-delimited. | fix now | Product Developer | this task | open |
| AR-4 | Leader review | KB file operations must enforce KB-root boundaries and reject escape paths. | fix now | Product Developer | this task | open |
| AR-5 | Leader review | Embedded editor saves should refresh KB explorer state and the KB manager should reflect disabled states coherently when no KB root is configured. | fix now | Product Developer | this task | open |
