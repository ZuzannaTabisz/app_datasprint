import unittest

import duckdb

from transaction_groups import GRUPY, group_sql


class TransactionGroupTests(unittest.TestCase):
    def classify(self, records):
        values = []
        for index, (issuer, municipality) in enumerate(records):
            issuer_sql = "NULL" if issuer is None else str(issuer)
            municipality_sql = "NULL" if municipality is None else "'" + municipality.replace("'", "''") + "'"
            values.append(f"({index}, {issuer_sql}, {municipality_sql})")

        query = (
            f"SELECT {group_sql('issuer', 'municipality')} "
            f"FROM (VALUES {', '.join(values)}) AS source(position, issuer, municipality) ORDER BY position"
        )
        return [row[0] for row in duckdb.connect().execute(query).fetchall()]

    def test_classifies_known_groups(self):
        records = [
            (616, "POZNAN"),
            (616, "CZERWONAK"),
            (840, "POZNAN"),
            (616, "LUBLIN"),
        ]

        self.assertEqual(self.classify(records), [0, 1, 2, 3])

    def test_missing_municipality_is_not_outside_metro(self):
        records = [(616, None), (616, ""), (616, "   ")]

        self.assertEqual(self.classify(records), [4, 4, 4])

    def test_foreign_issuer_group_takes_precedence(self):
        self.assertEqual(self.classify([(840, None)]), [2])

    def test_group_label_matches_missing_municipality_index(self):
        self.assertEqual(GRUPY[4], "Brak danych gminy")


if __name__ == "__main__":
    unittest.main()