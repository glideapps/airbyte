from datetime import datetime
from destination_glide.glide import GlideBigTableRestStrategy, Column, GlideBigTableFactory
import os
import unittest
from unittest import skip
from unittest.mock import patch
import uuid
import logging
import random

log = logging.getLogger("test")
log.setLevel(logging.DEBUG)
    
class TestGlideBigTableRestStrategy(unittest.TestCase):
    '''
    Tests against a working Glide /tables API endpoint rather than being mocked like the one in unit tests.
    '''

    api_host = "https://functions.prod.internal.glideapps.com"
    api_key = None
    api_path_root = "api"

    
    def setUp(self):
        self.api_key = os.getenv("GLIDE_API_KEY")
        if self.api_key is None:
            raise Exception("GLIDE_API_KEY environment variable is not set.")

    # The protocol is to call `init`, `set_schema`, `add_rows` one or more times, and `commit` in that order.
    
    def test_new_table(self):
        
        # init
        gbt = GlideBigTableFactory().create("tables")

        table_name = f"test-table-{str(uuid.uuid4())}"
        gbt.init(self.api_host, self.api_key, self.api_path_root, table_name)
        
        # set_schema
        test_columns = [
            Column("test-str", "string"),
            Column("test-num", "number")
        ]
        gbt.set_schema(test_columns)
    
        # add_rows
        for batch in range(3):
            now = datetime.now()
            test_rows = range(3)
            test_rows = [
                {
                    "test-str": f"test-str-{now.isoformat()}-{batch}-{i}",
                    "test-num": (batch * 1000) + i,
                }
                for i in test_rows
            ]

            # this creates the stashes:
            gbt.add_rows(test_rows)

        ## this commits the stages by upserting the table:
        # wraps= allows us to spy on the gbt's method here and confirm it created the table rather than overwrote it:
        with patch.object(gbt, "overwrite_table_from_stash", wraps=gbt.overwrite_table_from_stash) as mock_overwrite_table_from_stash:
            with patch.object(gbt, "create_table_from_stash", wraps=gbt.create_table_from_stash) as mock_create_table_from_stash:
                gbt.commit()
                mock_overwrite_table_from_stash.assert_not_called()
                mock_create_table_from_stash.assert_called_once()
        

    def test_updating_table(self):
        # init
        
        table_name = f"test-table-{str(uuid.uuid4())}"
        gbt = GlideBigTableFactory().create("tables")
        gbt.init(self.api_host, self.api_key, self.api_path_root, table_name)
        
        # set_schema
        test_columns = [
            Column("test-str", "string"),
            Column("test-num", "number")
        ]
        gbt.set_schema(test_columns)
    
        # add_rows
        test_rows = [
            {
                "test-str": f"test-str-{datetime.now().isoformat()}",
                "test-num": random.randint(0, 100000),
            }
        ]
        gbt.add_rows(test_rows)

        ## this commits the stages by upserting the table:
        gbt.commit()

        ##### NOW update the existing table we just created:

        # now do the update the second table now:
        gbt = GlideBigTableFactory().create("tables")
        gbt.init(self.api_host, self.api_key, self.api_path_root, table_name)
        gbt.set_schema(test_columns)

        now = datetime.now()
        test_rows = [
            {
                "test-str": f"test-str-{datetime.now().isoformat()}",
                "test-num": random.randint(0, 100000),
            }
        ]
        gbt.add_rows(test_rows)

        # wraps= allows us to spy on the gbt's method here and confirm it overwrote the table rather than created it:
        with patch.object(gbt, "overwrite_table_from_stash", wraps=gbt.overwrite_table_from_stash) as mock_overwrite_table_from_stash:
            with patch.object(gbt, "create_table_from_stash", wraps=gbt.create_table_from_stash) as mock_create_table_from_stash:
                gbt.commit()
                mock_overwrite_table_from_stash.assert_called_once()
                mock_create_table_from_stash.assert_not_called()
        
        
