# Problem

There can be many prompts in the project, and the user may want to preview or process all of them at once.

When a processing is requested an prompt may reference a column in the template that is output by another prompt.

Effectively there will be a depedency graph of prompts, where each prompt depends on the output of the previous prompt.

# Solution

The application will have to compute the dependency graph and ensure that the prompts are processed in the correct order.

If there are cycles in the graph, the application will have to detect it and present an error message to the user (and stop processing).

Algorithm to detect cycles is very simple.

Create a list of dependencies for each prompt (column name -> list of column names).
1. If a prompt depends on itself, it has a cycle.
2. If a prompt does not depend on any other prompt, it is independent, and we will remove it from the graph and remove it as a dependency for any other prompts.
3. If not prompt is independent, it means there is a cycle. We will simply list the prompts in the cycle and present an error message to the user.
