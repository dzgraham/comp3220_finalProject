# Compulsory courses and graduation targets.

import unittest

from csp.data import (
    load_courses,
    load_constraints,
    load_tracks
)

from csp.data import get_degree_blueprint


class TestDegreeRequirements(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.courses = load_courses()
        cls.constraints = load_constraints()
        cls.tracks = load_tracks()

    def blueprint(self, major):
        return get_degree_blueprint(
            major,
            self.courses,
            self.constraints,
            self.tracks
        )

    def test_computer_science(self):
        result = self.blueprint("computer_science")

        self.assertEqual(result["targets"]["total"], 93)
        self.assertEqual(result["remaining_credits"], {
            "level1": 9,
            "advanced": 30
        })

    def test_information_technology(self):
        result = self.blueprint("information_technology")

        self.assertEqual(result["remaining_credits"], {
            "level1": 9,
            "advanced": 21
        })

    def test_cybersecurity(self):
        result = self.blueprint("cybersecurity")

        self.assertEqual(result["remaining_credits"], {
            "level1": 9,
            "advanced": 24
        })

    def test_software_engineering(self):
        result = self.blueprint("software_engineering")

        self.assertEqual(result["remaining_credits"], {
            "level1": 9,
            "advanced": 24
        })

    def test_invalid_major(self):
        with self.assertRaises(ValueError):
            self.blueprint("invalid_major")


if __name__ == "__main__":
    unittest.main()
