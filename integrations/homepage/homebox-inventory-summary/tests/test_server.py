import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

source = Path(__file__).resolve().parents[1] / "server.py"
spec = importlib.util.spec_from_file_location("homebox_summary", source)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class SummaryTest(unittest.TestCase):
    def test_only_aggregate_counts_and_empty_db(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / "homebox.db")
            c = sqlite3.connect(path)
            c.executescript("""
            CREATE TABLE entity_types(id TEXT PRIMARY KEY,is_location INTEGER);
            CREATE TABLE entities(id TEXT PRIMARY KEY,entity_type_entities TEXT,warranty_expires TEXT,lifetime_warranty INTEGER);
            CREATE TABLE tags(id TEXT PRIMARY KEY);
            INSERT INTO entity_types VALUES ('item',0),('location',1);
            INSERT INTO entities VALUES ('i1','item',null,0),('i2','item','2027-01-01',0),('l1','location',null,0);
            INSERT INTO tags VALUES ('t1'),('t2');
            """)
            c.commit()
            self.assertEqual(m.inventory_summary(path), {"items":2,"locations":1,"tags":2,"warranties":1})
            c.execute("DELETE FROM entities")
            c.execute("DELETE FROM tags")
            c.commit()
            self.assertEqual(m.inventory_summary(path), {"items":0,"locations":0,"tags":0,"warranties":0})
            c.close()

if __name__=="__main__":
    unittest.main()
