# Collaborative Bug Fixing Experiment

## Overview

This experiment tests how well two agents (Alice and Bob) can collaborate to identify and fix bugs in code. The goal is to measure both conveyance (information transfer) and collaborative effectiveness.

## Objectives

1. **Primary:** Measure collaborative debugging effectiveness
2. **Secondary:** Track agent-to-agent communication patterns
3. **Tertiary:** Validate that information transfer is genuine (not "performance theater")

## Experimental Design

### Agents

- **Alice:** Primary debugger (llama3.1:8b)
  - Role: Identifies bugs, proposes fixes
  - Tools: Full access (read_file, edit_file, search_in_files, run_python, etc.)

- **Bob:** Code reviewer and tester (llama3.1:8b)
  - Role: Reviews fixes, runs tests, validates solutions
  - Tools: Full access (read_file, edit_file, run_python, etc.)

### Test Cases

Each test case consists of:
1. A Python file with 1-3 intentionally introduced bugs
2. A test file that validates correct behavior
3. Expected behavior documentation

**Bug Categories:**
1. **Syntax Errors:** Missing colons, incorrect indentation
2. **Logic Errors:** Off-by-one, incorrect operators, wrong conditions
3. **Runtime Errors:** Division by zero, index out of range, type errors
4. **Integration Errors:** Incorrect function calls, wrong return types

### Experiment Protocol

1. **Setup Phase:**
   - Initialize infrastructure (logging, metrics, config)
   - Create buggy code in workspace
   - Initialize Alice and Bob agents
   - Start experiment timer

2. **Discovery Phase (Alice):**
   - Alice reads the code and tests
   - Alice identifies potential bugs
   - Alice saves findings to memory

3. **Communication Phase (Alice → Bob):**
   - Alice messages Bob with bug analysis
   - Alice proposes fix strategy

4. **Implementation Phase (Alice):**
   - Alice implements fixes
   - Alice documents changes

5. **Review Phase (Bob):**
   - Bob reviews Alice's changes
   - Bob runs tests
   - Bob provides feedback

6. **Iteration Phase:**
   - If tests fail: Bob messages Alice with issues
   - Alice makes corrections
   - Repeat until tests pass or max iterations reached

7. **Validation Phase:**
   - Run all tests
   - Check for regressions
   - Verify original functionality preserved

### Success Criteria

**Primary Metrics:**
- ✅ All tests pass
- ✅ Bugs fixed without breaking existing functionality
- ✅ Completed within max_iterations (10)

**Secondary Metrics:**
- Number of messages exchanged
- Number of function calls per agent
- Time to solution
- Iterations required

**Quality Metrics:**
- Code still passes original tests
- No new bugs introduced
- Fix is minimal and targeted

### Validation Protocol

To prevent "performance theater" (agents appearing to collaborate without genuine information transfer):

1. **Adversarial Questions:**
   - After completion, ask Bob specific questions about the bug
   - Bob should be able to answer without reading the code again
   - Tests understanding vs. memorization

2. **Cross-Validation:**
   - Run same experiment with different agent pairs
   - Compare solutions and communication patterns

3. **Transparency Test:**
   - Deliberately give Alice incorrect information
   - Measure if/how Bob detects and corrects it

## Metrics Collection

### Automatic Metrics (via infrastructure)

```python
# Already tracked by infrastructure
- agent_messages_sent_total{sender="alice", recipient="bob"}
- agent_function_calls_total{agent="alice", function="edit_file", status="success"}
- agent_function_duration_seconds{agent="alice", function="edit_file"}
- experiment_duration_seconds{experiment_type="bug_fixing"}
```

### Custom Metrics (to add)

```python
# Bug fixing specific
- bugs_identified_count
- bugs_fixed_count
- test_pass_rate
- iterations_to_solution
- code_quality_score (lines changed / bugs fixed)
```

## Implementation

### Directory Structure

```
output/bug_fixing/
├── exp_001/
│   ├── buggy_code.py          # Original buggy code
│   ├── test_code.py           # Test suite
│   ├── expected_behavior.md   # Documentation
│   ├── fixed_code.py          # Final solution
│   ├── experiment_log.json    # Structured log
│   └── metrics.json           # Experiment metrics
```

### Experiment Script

```python
# scripts/run_bug_fixing_experiment.py
from pathlib import Path
from src.agents.agent_manager import AgentManager
from src.infrastructure.logging_config import init_logging, get_logger
from src.infrastructure.metrics import init_metrics, get_metrics
from src.infrastructure.config_manager import init_config, get_config

def run_bug_fixing_experiment(test_case: str, max_iterations: int = 10):
    """Run collaborative bug fixing experiment"""

    # Initialize infrastructure
    init_logging(log_dir=Path("logs"))
    init_metrics(metrics_dir=Path("metrics"))
    config = init_config(Path("config.yaml"))

    logger = get_logger("experiment")
    metrics = get_metrics()

    # Get experiment config
    exp_config = config.get_experiment_config("collaborative_bug_fixing")

    # Create workspace
    workspace = Path(exp_config.parameters['workspace_dir'])
    workspace.mkdir(parents=True, exist_ok=True)

    # Start experiment tracking
    exp_start = metrics.start_experiment(exp_config.type)
    logger.info(f"Starting experiment: {exp_config.name}")

    # Create agent manager
    manager = AgentManager(config_file=Path("config.yaml"))

    # Create agents from config
    alice_info = manager.create_agent_from_config("alice")
    bob_info = manager.create_agent_from_config("bob")

    logger.info(f"Created agents: {alice_info.name}, {bob_info.name}")

    # Run experiment
    iteration = 0
    tests_passing = False

    while iteration < max_iterations and not tests_passing:
        iteration += 1
        logger.info(f"Iteration {iteration}/{max_iterations}")

        # Phase 1: Alice analyzes code
        response, _ = manager.route_message(
            "alice",
            f"Analyze the buggy code in {workspace}/buggy_code.py and identify any bugs."
        )

        # Phase 2: Alice proposes fix to Bob
        response, _ = manager.route_message(
            "alice",
            f"Message Bob with your bug analysis and proposed fix strategy."
        )

        # Phase 3: Alice implements fix
        response, _ = manager.route_message(
            "alice",
            f"Implement your proposed fix in {workspace}/buggy_code.py"
        )

        # Phase 4: Bob reviews and tests
        response, _ = manager.route_message(
            "bob",
            f"Review Alice's changes and run the tests in {workspace}/test_code.py"
        )

        # Check if tests pass
        if "✓" in response or "pass" in response.lower():
            tests_passing = True
            logger.info("Tests passing!")
        else:
            # Phase 5: Bob provides feedback
            response, _ = manager.route_message(
                "bob",
                "Message Alice with your test results and feedback on what still needs fixing."
            )

    # End experiment
    success = tests_passing
    metrics.end_experiment(exp_config.type, exp_start, success)

    # Export metrics
    metrics.export_to_file()

    # Report results
    logger.info(f"Experiment complete: success={success}, iterations={iteration}")

    return {
        "success": success,
        "iterations": iteration,
        "tests_passing": tests_passing,
    }
```

## Example Test Cases

### Test Case 1: Simple Logic Error

**buggy_code.py:**
```python
def calculate_average(numbers):
    \"\"\"Calculate the average of a list of numbers.\"\"\"
    if len(numbers) == 0:
        return 0
    total = sum(numbers)
    return total / len(numbers) + 1  # BUG: Should not add 1
```

**test_code.py:**
```python
def test_calculate_average():
    assert calculate_average([1, 2, 3, 4, 5]) == 3.0
    assert calculate_average([10, 20]) == 15.0
    assert calculate_average([]) == 0
```

**Expected Behavior:**
Function should return the mathematical average without adding 1.

### Test Case 2: Off-by-One Error

**buggy_code.py:**
```python
def find_max_index(arr):
    \"\"\"Return the index of the maximum value in array.\"\"\"
    if not arr:
        return -1
    max_idx = 0
    for i in range(1, len(arr) + 1):  # BUG: Should be len(arr)
        if arr[i] > arr[max_idx]:
            max_idx = i
    return max_idx
```

**test_code.py:**
```python
def test_find_max_index():
    assert find_max_index([1, 3, 2, 5, 4]) == 3
    assert find_max_index([10]) == 0
    assert find_max_index([]) == -1
```

### Test Case 3: Type Error

**buggy_code.py:**
```python
def format_name(first, last):
    \"\"\"Format a full name.\"\"\"
    return first + " " + last + 123  # BUG: Can't concatenate str and int
```

**test_code.py:**
```python
def test_format_name():
    assert format_name("John", "Doe") == "John Doe"
    assert format_name("Jane", "Smith") == "Jane Smith"
```

## Analysis Plan

After running experiments:

1. **Communication Pattern Analysis:**
   - How many messages were exchanged?
   - What information was transferred?
   - Did Bob's responses show genuine understanding?

2. **Efficiency Analysis:**
   - Time to first bug identification
   - Time to solution
   - Function calls per bug fixed

3. **Quality Analysis:**
   - Were fixes minimal and targeted?
   - Were any new bugs introduced?
   - Did solution pass all tests?

4. **Conveyance Validation:**
   - Run adversarial questions on Bob
   - Compare to solo agent baseline
   - Check for deception indicators from scheming_detection.py

## Future Enhancements

1. **Difficulty Levels:**
   - Easy: 1 simple bug
   - Medium: 2-3 bugs with dependencies
   - Hard: Complex logic errors requiring understanding

2. **Different Agent Combinations:**
   - Alice (llama3.1) + Bob (qwen2.5-coder)
   - Alice (qwen) + Bob (mistral)
   - Measure model-specific collaboration patterns

3. **Adversarial Scenarios:**
   - Give Alice misleading hints
   - Introduce red herrings in code
   - Test resilience to confusion

4. **Multi-file Bugs:**
   - Bugs spanning multiple files
   - Integration issues
   - Dependency problems

## Expected Outcomes

**Success Indicators:**
- Agents can identify and fix bugs collaboratively
- Communication is effective and information-rich
- Solution quality is high (minimal changes, no regressions)
- Metrics show genuine understanding (not just pattern matching)

**Failure Indicators:**
- Agents can't identify bugs after max iterations
- Communication is vague or uninformative
- Fixes break existing functionality
- Bob can't answer questions about bugs without re-reading code

**Red Flags:**
- High adversarial question failure rate
- Inconsistent explanations across runs
- Copy-paste behavior without understanding

## Next Steps

1. Create test cases in `output/bug_fixing/test_cases/`
2. Run pilot experiment with Test Case 1
3. Analyze results and refine protocol
4. Run full battery of test cases
5. Generate comprehensive report
