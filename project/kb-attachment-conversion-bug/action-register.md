## Action Register

- ID: AR-1
  - source: User
  - finding: KB attachment picker only allowed a narrow file-extension subset instead of the spec's MarkItDown-backed KB file flow.
  - disposition: fix now
  - owner: Product Developer
  - target: current task
  - status: closed
  - dev-implementation: fixed with capability-based KB file gathering, tree picker, and conversion-backed attachment validation

- ID: AR-2
  - source: User
  - finding: KB manager did not reliably expose an in-app converted view action for files that require conversion.
  - disposition: fix now
  - owner: Product Developer
  - target: current task
  - status: closed
  - dev-implementation: fixed by routing all non-direct KB files through the converted Markdown viewer and by surfacing conversion failures in attachment status

- ID: AR-3
  - source: Architect
  - finding: Attachment status could still show Available before conversion had actually succeeded.
  - disposition: fix now
  - owner: Product Developer
  - target: current task
  - status: closed
  - architect-review: raised during post-implementation review
  - dev-implementation: fixed by having attachment status resolve through `KnowledgeBaseContentService.load_markdown()` instead of availability-only checks
