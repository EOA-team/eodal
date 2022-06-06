"""
Provides a base test class for other test classes to inherit from.

Includes the numpy testing functions as methods.
"""

import os.path
import sys
import unittest
from inspect import getsourcefile

import numpy as np
import pytest
from numpy.testing import (
    assert_allclose,
    assert_almost_equal,
    assert_approx_equal,
    assert_array_almost_equal,
    assert_array_almost_equal_nulp,
    assert_array_equal,
    assert_array_less,
    assert_array_max_ulp,
    assert_equal,
    assert_raises,
    assert_string_equal,
    assert_warns,
)

TEST_DIRECTORY = os.path.dirname(os.path.abspath(getsourcefile(lambda: 0)))


def assert_starts_with(actual, desired):
    """
    Check that a string starts with a certain substring.

    Parameters
    ----------
    actual : str-like
        Actual string or string-like object.
    desired : str
        Desired initial string.
    """
    try:
        assert len(actual) >= len(desired)
    except BaseException:
        print(
            "Actual string too short ({} < {} characters)".format(
                len(actual), len(desired)
            )
        )
        print("ACTUAL: {}".format(actual))
        raise
    try:
        return assert_string_equal(str(actual)[: len(desired)], desired)
    except BaseException as err:
        msg = "ACTUAL: {}".format(actual)
        if isinstance(getattr(err, "args", None), str):
            err.args += "\n" + msg
        elif isinstance(getattr(err, "args", None), tuple):
            if len(err.args) == 1:
                err.args = (err.args[0] + "\n" + msg,)
            else:
                err.args += (msg,)
        else:
            print(msg)
        raise


class BaseTestCase(unittest.TestCase):
    """
    Superclass for test cases, including support for numpy.
    """

    # The attribute `test_directory` provides the path to the directory
    # containing the file `base_test.py`, which is useful to obtain
    # test resources - files which are needed to run tests.
    test_directory = TEST_DIRECTORY

    def __init__(self, *args, **kwargs):
        """Instance initialisation."""
        # First do the __init__ associated with parent class
        super().__init__(*args, **kwargs)
        # Add a test to automatically use when comparing objects of
        # type numpy ndarray. This will be used for self.assertEqual().
        self.addTypeEqualityFunc(np.ndarray, self.assert_allclose)

    @pytest.fixture(autouse=True)
    def capsys(self, capsys):
        r"""
        Pass-through for accessing pytest.capsys fixture with class methods.

        Returns
        -------
        capture : pytest.CaptureFixture[str]

        Example
        -------
        To use this fixture with your own subclass of ``BaseTestCase``::

            class TestVerbose(BaseTestCase):
                def test_output(self):
                    print("hello")
                    captured = self.capsys.readouterr()
                    self.assert_string_equal(captured.out, "hello\n")

        Note
        ----
        capsys will capture all messages sent to stdout and stderr since the
        last call to capsys (or since execution began on the test). To test the
        output of a particular command, you may want to do a capture before the
        command to clear stdout/stderr before running the command and then
        capturing its output.

        See Also
        --------
        - https://docs.pytest.org/en/stable/reference.html#capsys
        - https://docs.pytest.org/en/stable/capture.html
        """
        self.capsys = capsys

    def recapsys(self, *captures):
        r"""
        Capture stdout and stderr, then write them back to stdout and stderr.

        Capture is done using the :func:`pytest.capsys` fixture. Used on its
        own, :func:`~pytest.capsys` captures outputs to stdout and stderr,
        which prevents the output from appearing in the usual way when an
        error occurs during testing.

        By chaining series of calls to ``capsys`` and ``recapsys`` around
        commands whose outputs must be inspected, all output directed to stdout
        and stderr will end up there and appear in the "Captured stdout call"
        block in the event of a test failure, as well as being captured here
        for the test.

        Parameters
        ----------
        *captures : pytest.CaptureResult, optional
            A series of extra captures to output. For each `capture` in
            `captures`, `capture.out` and `capture.err` are written to stdout
            and stderr, respectively.

        Returns
        -------
        capture : NamedTuple
            `capture.out` and `capture.err` contain all the outputs to stdout
            and stderr since the previous capture with :func:`~pytest.capsys`.

        Example
        -------
        To use this fixture with your own subclass of ``BaseTestCase``::

            class TestVerbose(BaseTestCase):
                def test_hello_world(self):
                    print("previous message here")
                    message = "Hello world!"
                    capture_pre = self.capsys.readouterr()  # Clear stdout
                    print(message)
                    capture_post = self.recapsys(capture_pre)  # Capture & output
                    self.assert_string_equal(capture_post.out, message + "\n")
        """
        capture_now = self.capsys.readouterr()
        for capture in captures + (capture_now,):
            sys.stdout.write(capture.out)
            sys.stderr.write(capture.err)
        return capture_now

    # Add assertions provided by numpy to this class, so they will be
    # available as methods to all subclasses when we do our tests.
    def assert_almost_equal(self, *args, **kwargs):
        """
        Check if two items are not equal up to desired precision.
        """
        return assert_almost_equal(*args, **kwargs)

    def assert_approx_equal(self, *args, **kwargs):
        """
        Check if two items are not equal up to significant digits.
        """
        return assert_approx_equal(*args, **kwargs)

    def assert_array_almost_equal(self, *args, **kwargs):
        """
        Check if two objects are not equal up to desired precision.
        """
        return assert_array_almost_equal(*args, **kwargs)

    def assert_allclose(self, *args, **kwargs):
        """
        Check if two objects are equal up to desired tolerance.
        """
        return assert_allclose(*args, **kwargs)

    def assert_array_almost_equal_nulp(self, *args, **kwargs):
        """
        Compare two arrays relatively to their spacing.
        """
        return assert_array_almost_equal_nulp(*args, **kwargs)

    def assert_array_max_ulp(self, *args, **kwargs):
        """
        Check that all items of arrays differ in at most N Units in the Last Place.
        """
        return assert_array_max_ulp(*args, **kwargs)

    def assert_array_equal(self, *args, **kwargs):
        """
        Check if two array_like objects are equal.
        """
        return assert_array_equal(*args, **kwargs)

    def assert_array_less(self, *args, **kwargs):
        """
        Check if two array_like objects are not ordered by less than.
        """
        return assert_array_less(*args, **kwargs)

    def assert_equal(self, *args, **kwargs):
        """
        Check if two objects are not equal.
        """
        return assert_equal(*args, **kwargs)

    def assert_raises(self, *args, **kwargs):
        """
        Check that an exception of class exception_class is thrown by callable.
        """
        return assert_raises(*args, **kwargs)

    def assert_warns(self, *args, **kwargs):
        """
        Check that the given callable throws the specified warning.
        """
        return assert_warns(*args, **kwargs)

    def assert_string_equal(self, *args, **kwargs):
        """
        Test if two strings are equal.
        """
        return assert_string_equal(*args, **kwargs)

    def assert_starts_with(self, *args, **kwargs):
        return assert_starts_with(*args, **kwargs)
