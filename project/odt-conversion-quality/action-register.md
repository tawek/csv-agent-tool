# Action Register

- ID: AR-1
  - source: Architect
  - finding: Cache identity was still MarkItDown-centric even for `.odt` and `.ods`, so cache metadata and invalidation did not follow the actual backend split.
  - disposition: fix now
  - owner: Product Developer
  - target: current task
  - status: closed
  - dev-implementation: Updated `ConversionCache._converter_identity()` to derive backend-specific identities from the source suffix: `.odt` uses the local parser revision, `.ods` uses the installed `odfpy` version, and other formats use the MarkItDown version.
  - architect-review: addressed

- ID: AR-2
  - source: Architect
  - finding: `.ods` backend-unavailable failures still used a MarkItDown-branded exception even though `odfpy` is the missing backend.
  - disposition: fix now
  - owner: Product Developer
  - target: current task
  - status: closed
  - dev-implementation: Added `ConversionBackendUnavailableError` as the shared backend-missing exception, kept `MarkItDownUnavailableError` as a specialized subclass for MarkItDown paths, and updated `.ods` conversion failures to raise the backend-generic exception with an `odfpy`-specific message.
  - architect-review: addressed

- ID: AR-3
  - source: Architect
  - finding: `load_markdown()` docstring still documented only the old MarkItDown-specific unavailable case after the backend error split.
  - disposition: fix now
  - owner: Product Developer
  - target: current task
  - status: closed
  - dev-implementation: Updated `load_markdown()` docstring to document `ConversionBackendUnavailableError` for backend-unavailable cases.
  - architect-review: addressed
