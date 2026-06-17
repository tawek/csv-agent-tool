## Action Register

| ID | Source | Finding | Disposition | Owner | Target | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AR-1 | Architect | Replace derived expanded/collapsed panel layout logic with an explicit four-state model so temporary minimized panels can be restored correctly after de-maximize. | fix now | Product Developer | this task | closed |
| AR-2 | Architect | Remove or remap header-click toggling because it bypasses the requested grow/shrink state machine. | fix now | Product Developer | this task | closed |
| AR-3 | Architect | Growing a temporary minimized panel while another panel is maximized must not leave the other panel internally marked maximized; the state machine must resolve the active maximized panel back to normal and restore temporary minimized siblings coherently. | fix now | Product Developer | this task | closed |
