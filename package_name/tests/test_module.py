"""
Tests for module in package_name.
"""
import math

import numpy as np

# from package_name.module import cubic_rectification
from ..module import cubic_rectification
from .base_test import BaseTestCase, unittest


class NumbersTest(BaseTestCase):
    def test_even(self):
        """
        Test that numbers between 0 and 5 are all even.
        """
        for i in range(0, 6, 2):
            with self.subTest(i=i):
                self.assertEqual(i % 2, 0)


class TestVerbose(BaseTestCase):
    """
    Test that things are printed to stdout correctly.
    """

    def test_hello_world(self):
        """Test printing to stdout."""
        message = "Hello world!"
        capture_pre = self.capsys.readouterr()  # Clear stdout
        print(message)  # Execute method (verbose)
        capture_post = self.recapsys(capture_pre)  # Capture and then re-output
        self.assert_string_equal(capture_post.out.strip(), message)

    def test_shakespeare(self):
        # Clear stdout (in this case, an empty capture)
        capture_pre = self.capsys.readouterr()
        # Execute method (verbose)
        print("To be, or not to be, that is the question:")
        # Capture the output to stdout, then re-output
        capture_post = self.recapsys(capture_pre)
        # Compare output to target
        self.assert_starts_with(capture_post.out, "To be, or not")
        # Clear stdout (in this case, capturing the re-output first print statement)
        capture_pre = self.capsys.readouterr()
        # Execute method (verbose)
        print("Whether 'tis nobler in the mind to suffer")
        # Capture the output to stdout, then re-output. This now prints both
        # lines to stdout at once, which otherwise would not appear due to our
        # captures.
        capture_post = self.recapsys(capture_pre)
        # Compare output to target
        self.assert_starts_with(capture_post.out.lower(), "whether 'tis nobler")


class TestCubicRectification(BaseTestCase):
    """
    Tests for the cubic_rectification function.
    """

    def test_int(self):
        """Test with integer inputs."""
        self.assertEqual(cubic_rectification(2), 8)
        self.assertEqual(cubic_rectification(-2), 0)
        self.assertEqual(cubic_rectification(3), 27)

    def test_float(self):
        """Test with float inputs."""
        # Need to use assert_allclose due to the real possibility of a
        # floating point inaccuracy.
        self.assert_allclose(cubic_rectification(1.2), 1.728)
        self.assert_allclose(cubic_rectification(-1.2), 0)

    def test_empty_array(self):
        """Test with empty array."""
        self.assert_equal(cubic_rectification(np.array([])), np.array([]))

    def test_array(self):
        """Test with numpy array inputs."""
        # Test with singleton array
        self.assert_equal(cubic_rectification(np.array(3)), np.array(27))
        # Test with vector
        self.assert_equal(
            cubic_rectification(np.array([0, 2, -2])), np.array([0, 8, 0])
        )

    def test_arange(self):
        """Test with numpy array input generated with arange."""
        # Test with arange input
        x = np.arange(-3, 4)
        actual = cubic_rectification(x)
        desired = np.array([0, 0, 0, 0, 1, 8, 27])
        self.assert_allclose(actual, desired)

    @unittest.expectedFailure
    def test_nan_skipped(self):
        """Test for NaN input with invalid comparison methods."""
        # We can't use the standard assertEquals for comparing two NaNs
        self.assertEqual(cubic_rectification(float("nan")), float("nan"))
        self.assertEqual(cubic_rectification(np.nan), np.nan)

    def test_nan(self):
        """Test for NaN input with valid comparison methods."""
        # Can use the assert_equal from numpy.testing to compare NaNs
        self.assert_equal(cubic_rectification(float("nan")), float("nan"))
        self.assert_equal(cubic_rectification(np.nan), np.nan)
        # Or we can use an isnan function from either math or numpy
        self.assertTrue(math.isnan(cubic_rectification(float("nan"))))
        self.assertTrue(np.isnan(cubic_rectification(np.nan)))

    def test_quiet(self):
        capture_pre = self.capsys.readouterr()  # Clear stdout
        cubic_rectification(2)
        capture_post = self.recapsys(capture_pre)  # Capture and then re-output
        self.assert_equal(capture_post.out, "")

    def test_verbose(self):
        capture_pre = self.capsys.readouterr()  # Clear stdout
        cubic_rectification(2, verbose=True)  # Execute method (verbose)
        capture_post = self.recapsys(capture_pre)  # Capture and then re-output
        self.assert_starts_with(capture_post.out, "Cubing")  # Test
