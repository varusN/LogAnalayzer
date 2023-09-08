import random
import unittest

from log_analayzer import UrlColection


class TestLogAnalayzer(unittest.TestCase):
    def test_count(self):
        data = UrlColection("test", 1)
        for i in range(5):
            data.add_item(1)
        self.assertEqual(data.count(), 6)

    def test_count_perc(self):
        data = UrlColection("test", 1)
        for i in range(5):
            data.add_item(0.2)
        self.assertEqual(data.count_perc(10), 60)

    def test_time_sum(self):
        data = UrlColection("test", 1)
        for i in range(5):
            data.add_item(0.1)
        self.assertEqual(data.time_sum(), 1.5)

    def test_time_perc(self):
        data = UrlColection("test", 0.99)
        for i in range(5):
            data.add_item(0.34)
        self.assertEqual(data.time_perc(5.309), 50.669)

    def test_time_avg(self):
        data = UrlColection("test", 0.54545)
        for i in range(5):
            data.add_item(0.1234)
        self.assertEqual(data.time_avg(), 0.194)

    def test_time_max(self):
        data = UrlColection("test", 99)
        for i in range(5):
            data.add_item(random.random())
        self.assertEqual(data.time_max(), 99)

    def test_time_med(self):
        data = UrlColection("test", 0.35)
        data.add_item(0.34)
        data.add_item(0.38)
        data.add_item(1)
        self.assertEqual(data.time_med(), 0.365)


if __name__ == "__main__":
    unittest.main()
