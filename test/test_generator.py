#!/usr/bin/env python

import sys
import os
import unittest
sys.path.append(os.path.join(os.path.abspath('..'),'generator'))
import create_catalog


class TestGenerator(unittest.TestCase):
    def test_example(self):
        self.assertTrue('1')
    def test_fail(self):
        self.assertEqual('1','1')

if __name__ == '__main__':
    unittest.main()
