# Action Register — Knowledge Base Manager

| ID | Source | Finding | Disposition | Owner | Target | Status |
|---|---|---|---|---|---|---|
| AR-1 | User review | Spec/implementation drifted from the original request by not explicitly carrying forward the user's input as a persistent note for downstream specialists. | fix now | Leader | this task | closed |
| AR-2 | User review | CSV editor behavior must include add/remove rows and columns, not just editing existing text cells. | fix now | Architect + Product Developer | this task | closed |
| AR-3 | Leader review | CSV editor must preserve heuristically detected CSV settings on save instead of rewriting every file as comma-delimited. | fix now | Product Developer | this task | closed |
| AR-4 | Leader review | KB file operations must enforce KB-root boundaries and reject escape paths. | fix now | Product Developer | this task | closed |
| AR-5 | Leader review | Embedded editor saves should refresh KB explorer state and the KB manager should reflect disabled states coherently when no KB root is configured. | fix now | Product Developer | this task | closed |
| ARCH-1 | Architect review | `KnowledgeBaseManager` copy/rename operations validate the source path but not the resolved target path, so user-entered names like `../outside.txt` can escape the KB root. | fix now | Product Developer | this task | closed |
| ARCH-2 | Architect review | Feature workspace closure artifacts are stale and must be updated to reflect actual validation/review state before reporting completion. | fix now | Leader | this task | closed |
| AR-6 | User review | The Knowledge Base menu is too complex; expose a single `Knowledge Base` entry and let the manager screen host the actions instead. | fix now | Architect + Product Developer | this task | closed |
| AR-7 | User review | The Knowledge Base manager is missing a `Close` button for exiting the manager directly from that screen. | fix now | Product Developer | this task | closed |
