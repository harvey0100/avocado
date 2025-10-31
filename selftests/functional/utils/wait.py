import os
import threading
import time
import unittest

from avocado.utils import wait
from selftests.utils import TestCaseTmpDir


class WaitForFunctionalTest(TestCaseTmpDir):
    """Functional tests for wait.wait_for with real-world scenarios."""

    def test_condition_becomes_true(self):
        """Test basic wait_for with condition that becomes true after delay."""
        filepath = os.path.join(self.tmpdir.name, "test_file.txt")

        # Create file after a delay
        def create_file_delayed():
            time.sleep(0.3)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("test content")

        # Start file creation in background
        thread = threading.Thread(target=create_file_delayed)
        thread.start()

        # Wait for file to exist
        result = wait.wait_for(
            lambda: os.path.exists(filepath),
            timeout=2.0,
            step=0.1,
            text="Waiting for file to appear",
        )

        thread.join()
        self.assertTrue(result)
        self.assertTrue(os.path.exists(filepath))

    def test_multiple_conditions_combined(self):
        """Test waiting for multiple conditions (AND logic)."""
        file1 = os.path.join(self.tmpdir.name, "file1.txt")
        file2 = os.path.join(self.tmpdir.name, "file2.txt")

        def create_files():
            time.sleep(0.2)
            with open(file1, "w", encoding="utf-8") as f:
                f.write("content1")
            time.sleep(0.2)
            with open(file2, "w", encoding="utf-8") as f:
                f.write("content2")

        thread = threading.Thread(target=create_files)
        thread.start()

        # Wait for both files to exist
        result = wait.wait_for(
            lambda: os.path.exists(file1) and os.path.exists(file2),
            timeout=2.0,
            step=0.1,
        )

        thread.join()
        self.assertTrue(result)
        self.assertTrue(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

    def test_timeout_when_condition_never_true(self):
        """Test that wait_for respects timeout when condition never becomes true."""
        filepath = os.path.join(self.tmpdir.name, "nonexistent.txt")

        # Wait for a file that will never be created
        start = time.time()
        result = wait.wait_for(lambda: os.path.exists(filepath), timeout=0.5, step=0.1)
        elapsed = time.time() - start

        self.assertIsNone(result)
        self.assertGreaterEqual(elapsed, 0.5)
        self.assertLess(elapsed, 0.7)

    def test_complex_condition_with_error_handling(self):
        """Test wait_for with complex condition function including error handling."""
        filepath = os.path.join(self.tmpdir.name, "numbers.txt")

        def write_numbers():
            with open(filepath, "w", encoding="utf-8") as f:
                for i in range(1, 11):
                    f.write(f"{i}\n")
                    f.flush()
                    time.sleep(0.05)

        thread = threading.Thread(target=write_numbers)
        thread.start()

        def check_sum_exceeds_threshold():
            """Check if sum of numbers in file exceeds 30."""
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if not lines:
                        return False
                    numbers = [int(line.strip()) for line in lines if line.strip()]
                    return sum(numbers) > 30
            except (FileNotFoundError, ValueError):
                return False

        result = wait.wait_for(check_sum_exceeds_threshold, timeout=2.0, step=0.1)

        thread.join()
        self.assertTrue(result)

    def test_immediate_success_with_fast_polling(self):
        """Test wait_for with very fast polling and immediate success."""
        counter = {"value": 0}

        def increment_counter():
            counter["value"] += 1
            return counter["value"] >= 50

        result = wait.wait_for(increment_counter, timeout=2.0, step=0.001)

        self.assertTrue(result)
        self.assertEqual(counter["value"], 50)


if __name__ == "__main__":
    unittest.main()
