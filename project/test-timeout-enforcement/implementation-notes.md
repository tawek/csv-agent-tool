# Test timeout enforcement request

- Build a hardened pytest wrapper script so agents stop running raw `pytest` commands directly.
- The wrapper must enforce the full headless GUI test environment automatically.
- The wrapper must enforce a short hard timeout for each pytest invocation.
- The timeout should be shorter than 10 seconds; 10 seconds is already considered too long.
- Agents must be instructed to use only that wrapper for test execution.
- Provide strong, explicit examples in the repo instructions so specialists cannot plausibly misinterpret the rule.
- This is primarily a team-control and execution-discipline fix.
