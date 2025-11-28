#!/usr/bin/env python3
"""
Collaborative Bug Fixing Experiment

Two agents (Alice and Bob) collaborate to identify and fix bugs in code.
Tracks communication patterns, function calls, and solution quality.
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.agent_manager import AgentManager
from src.infrastructure.logging_config import init_logging, get_logger
from src.infrastructure.metrics import init_metrics, get_metrics
from src.infrastructure.config_manager import init_config, get_config


class BugFixingExperiment:
    """Orchestrates collaborative bug fixing experiment"""

    def __init__(self, workspace_dir: Path, max_iterations: int = 10):
        """Initialize experiment

        Args:
            workspace_dir: Directory for experiment files
            max_iterations: Maximum collaboration iterations
        """
        self.workspace = workspace_dir
        self.max_iterations = max_iterations
        self.experiment_id = f"bug_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Initialize infrastructure
        init_logging(log_dir=Path("logs"))
        init_metrics(metrics_dir=Path("metrics"))
        self.config = init_config(Path("config.yaml"))

        self.logger = get_logger("bug_fixing_experiment")
        self.metrics = get_metrics()

        # Get experiment config
        self.exp_config = self.config.get_experiment_config("collaborative_bug_fixing")

        # Create agent manager
        self.manager = AgentManager(config_file=Path("config.yaml"))

        self.logger.info(f"Initialized experiment: {self.experiment_id}")

    def setup_test_case(self, test_case_name: str):
        """Setup test case files in workspace

        Args:
            test_case_name: Name of test case to setup
        """
        test_case_dir = Path("output/bug_fixing/test_cases") / test_case_name
        if not test_case_dir.exists():
            raise ValueError(f"Test case not found: {test_case_dir}")

        # Create experiment workspace
        exp_workspace = self.workspace / self.experiment_id
        exp_workspace.mkdir(parents=True, exist_ok=True)

        # Copy test case files
        import shutil
        for file in test_case_dir.glob("*"):
            shutil.copy(file, exp_workspace)

        self.logger.info(f"Setup test case: {test_case_name} in {exp_workspace}")
        return exp_workspace

    def run(self, test_case_name: str) -> dict:
        """Run the collaborative bug fixing experiment

        Args:
            test_case_name: Name of test case to run

        Returns:
            Dictionary with experiment results
        """
        # Start experiment tracking
        exp_start = self.metrics.start_experiment(self.exp_config.type)
        self.logger.info(f"Starting experiment: {self.experiment_id}")

        # Setup test case
        exp_workspace = self.setup_test_case(test_case_name)

        # Create agents from config
        self.logger.info("Creating agents...")
        alice_info = self.manager.create_agent_from_config("alice")
        bob_info = self.manager.create_agent_from_config("bob")
        self.logger.info(f"Agents created: {alice_info.name}, {bob_info.name}")

        # Track metrics
        results = {
            "experiment_id": self.experiment_id,
            "test_case": test_case_name,
            "start_time": datetime.now().isoformat(),
            "iterations": [],
            "success": False,
            "total_iterations": 0,
            "messages_exchanged": 0,
            "errors": [],
        }

        # Run collaboration loop
        iteration = 0
        tests_passing = False

        while iteration < self.max_iterations and not tests_passing:
            iteration += 1
            self.logger.info(f"\n{'='*70}")
            self.logger.info(f"Iteration {iteration}/{self.max_iterations}")
            self.logger.info(f"{'='*70}\n")

            iteration_start = time.time()
            iteration_data = {
                "number": iteration,
                "phases": [],
            }

            try:
                # Phase 1: Alice analyzes code
                self.logger.info("Phase 1: Alice analyzing code...")
                response, stats = self.manager.route_message(
                    "alice",
                    f"Read the file {exp_workspace}/buggy_code.py and identify any bugs. "
                    f"Also read {exp_workspace}/test_code.py to understand expected behavior. "
                    f"List all bugs you find and explain what's wrong."
                )
                iteration_data["phases"].append({
                    "name": "analysis",
                    "agent": "alice",
                    "response_preview": response[:200]
                })
                print(f"\n[Alice Analysis]: {response}\n")

                # Phase 2: Alice proposes fix
                self.logger.info("Phase 2: Alice proposing fix...")
                response, stats = self.manager.route_message(
                    "alice",
                    "Now message Bob with your bug analysis and proposed fix strategy. "
                    "Be specific about what you found and how you plan to fix it."
                )
                iteration_data["phases"].append({
                    "name": "proposal",
                    "agent": "alice",
                    "response_preview": response[:200]
                })
                results["messages_exchanged"] += 1
                print(f"\n[Alice → Bob]: {response}\n")

                # Phase 3: Alice implements fix
                self.logger.info("Phase 3: Alice implementing fix...")
                response, stats = self.manager.route_message(
                    "alice",
                    f"Now implement your proposed fix by editing {exp_workspace}/buggy_code.py. "
                    f"Use the edit_file function to make precise changes. "
                    f"After editing, save a note to memory about what you changed and why."
                )
                iteration_data["phases"].append({
                    "name": "implementation",
                    "agent": "alice",
                    "response_preview": response[:200]
                })
                print(f"\n[Alice Implementation]: {response}\n")

                # Phase 4: Bob reviews and tests
                self.logger.info("Phase 4: Bob reviewing and testing...")
                response, stats = self.manager.route_message(
                    "bob",
                    f"Read the code in {exp_workspace}/buggy_code.py and run the tests in "
                    f"{exp_workspace}/test_code.py using run_python. "
                    f"Report whether all tests pass or if there are still issues."
                )
                iteration_data["phases"].append({
                    "name": "review",
                    "agent": "bob",
                    "response_preview": response[:200]
                })
                print(f"\n[Bob Review]: {response}\n")

                # Check if tests pass
                if "all tests" in response.lower() and "pass" in response.lower():
                    tests_passing = True
                    self.logger.info("✓ Tests passing!")
                    print("\n" + "="*70)
                    print("✓ SUCCESS: All tests passing!")
                    print("="*70 + "\n")
                elif "✓" in response and not ("✗" in response or "fail" in response.lower()):
                    tests_passing = True
                    self.logger.info("✓ Tests passing!")
                    print("\n" + "="*70)
                    print("✓ SUCCESS: All tests passing!")
                    print("="*70 + "\n")
                else:
                    # Phase 5: Bob provides feedback
                    self.logger.info("Phase 5: Bob providing feedback...")
                    response, stats = self.manager.route_message(
                        "bob",
                        "Message Alice with your test results. "
                        "Be specific about what tests failed and what needs to be fixed."
                    )
                    iteration_data["phases"].append({
                        "name": "feedback",
                        "agent": "bob",
                        "response_preview": response[:200]
                    })
                    results["messages_exchanged"] += 1
                    print(f"\n[Bob → Alice]: {response}\n")

            except Exception as e:
                self.logger.error(f"Error in iteration {iteration}: {e}", exc_info=True)
                results["errors"].append({
                    "iteration": iteration,
                    "error": str(e)
                })

            iteration_data["duration"] = time.time() - iteration_start
            iteration_data["tests_passing"] = tests_passing
            results["iterations"].append(iteration_data)

        # Finalize results
        results["success"] = tests_passing
        results["total_iterations"] = iteration
        results["end_time"] = datetime.now().isoformat()
        results["duration_seconds"] = time.time() - exp_start

        # End experiment tracking
        self.metrics.end_experiment(self.exp_config.type, exp_start, tests_passing)

        # Export metrics
        self.metrics.export_to_file()

        # Save results
        results_file = exp_workspace / "experiment_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        self.logger.info(f"Experiment complete: {results}")
        self.logger.info(f"Results saved to: {results_file}")

        return results

    def print_summary(self, results: dict):
        """Print experiment summary

        Args:
            results: Experiment results dictionary
        """
        print("\n" + "="*70)
        print("EXPERIMENT SUMMARY")
        print("="*70)
        print(f"Experiment ID: {results['experiment_id']}")
        print(f"Test Case: {results['test_case']}")
        print(f"Success: {'✓ YES' if results['success'] else '✗ NO'}")
        print(f"Iterations: {results['total_iterations']}/{self.max_iterations}")
        print(f"Messages Exchanged: {results['messages_exchanged']}")
        print(f"Duration: {results['duration_seconds']:.2f} seconds")

        if results['errors']:
            print(f"\nErrors Encountered: {len(results['errors'])}")
            for error in results['errors']:
                print(f"  - Iteration {error['iteration']}: {error['error']}")

        print("\nGenerated Files:")
        print(f"  - Logs: logs/")
        print(f"  - Metrics: metrics/agent_metrics.prom")
        print(f"  - Results: {self.workspace}/{self.experiment_id}/experiment_results.json")
        print("="*70 + "\n")


def create_sample_test_case():
    """Create a sample test case for demonstration"""
    test_case_dir = Path("output/bug_fixing/test_cases/simple_average")
    test_case_dir.mkdir(parents=True, exist_ok=True)

    # Buggy code
    buggy_code = '''"""Calculate average of numbers"""

def calculate_average(numbers):
    """Calculate the average of a list of numbers."""
    if len(numbers) == 0:
        return 0
    total = sum(numbers)
    return total / len(numbers) + 1  # BUG: Should not add 1

if __name__ == "__main__":
    print(calculate_average([1, 2, 3, 4, 5]))
'''

    # Test code
    test_code = '''"""Test calculate_average function"""
import sys
from buggy_code import calculate_average

def test_calculate_average():
    """Test the calculate_average function"""
    # Test 1: Normal case
    result = calculate_average([1, 2, 3, 4, 5])
    assert result == 3.0, f"Expected 3.0, got {result}"
    print("✓ Test 1 passed: calculate_average([1, 2, 3, 4, 5]) == 3.0")

    # Test 2: Two numbers
    result = calculate_average([10, 20])
    assert result == 15.0, f"Expected 15.0, got {result}"
    print("✓ Test 2 passed: calculate_average([10, 20]) == 15.0")

    # Test 3: Empty list
    result = calculate_average([])
    assert result == 0, f"Expected 0, got {result}"
    print("✓ Test 3 passed: calculate_average([]) == 0")

    print("\\n✓ All tests passed!")

if __name__ == "__main__":
    test_calculate_average()
'''

    # Expected behavior
    expected = '''# Expected Behavior

The `calculate_average` function should return the mathematical average
of a list of numbers.

## Formula
average = sum(numbers) / count(numbers)

## Test Cases
1. [1, 2, 3, 4, 5] → 3.0
2. [10, 20] → 15.0
3. [] → 0

## Known Bug
The function currently adds 1 to the result, causing all non-empty
test cases to fail.
'''

    # Write files
    (test_case_dir / "buggy_code.py").write_text(buggy_code)
    (test_case_dir / "test_code.py").write_text(test_code)
    (test_case_dir / "expected_behavior.md").write_text(expected)

    print(f"✓ Created sample test case: {test_case_dir}")
    return test_case_dir


def main():
    """Main entry point"""
    print("="*70)
    print("Collaborative Bug Fixing Experiment")
    print("="*70)

    # Create sample test case
    test_case_dir = create_sample_test_case()

    # Run experiment
    experiment = BugFixingExperiment(
        workspace_dir=Path("output/bug_fixing"),
        max_iterations=10
    )

    results = experiment.run("simple_average")

    # Print summary
    experiment.print_summary(results)

    return 0 if results['success'] else 1


if __name__ == "__main__":
    sys.exit(main())
