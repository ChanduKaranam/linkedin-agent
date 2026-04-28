import sqlite3
import pandas as pd
from sqlalchemy import create_engine

# =========================
# CONFIGURATION
# =========================

# SQLite file path
SQLITE_DB_PATH = r"C:\Users\Lenovo\Downloads\factor_data (1).db"

# PostgreSQL connection string
# Format: postgresql://user:password@host:port/dbname
POSTGRES_URL = "postgresql://postgres:chandu@localhost:5432/final"

# =========================
# FUNCTION TO TRANSFER TABLE
# =========================

def transfer_table(table_name, if_exists="replace", chunksize=1000):
    """
    Transfers a single table from SQLite to PostgreSQL.

    Parameters:
    - table_name (str): Name of the table to transfer
    - if_exists (str): 'fail', 'replace', or 'append'
    - chunksize (int): Number of rows per batch insert
    """

    print(f"\n🚀 Transferring table: {table_name}")

    try:
        # Connect to SQLite
        sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)

        # Read table into pandas DataFrame
        query = f'SELECT * FROM "{table_name}"'
        df = pd.read_sql_query(query, sqlite_conn)

        print(f"✅ Read {len(df)} rows from SQLite")

        # Connect to PostgreSQL
        engine = create_engine(POSTGRES_URL)

        # Upload to PostgreSQL
        df.to_sql(
            name=table_name,
            con=engine,
            if_exists=if_exists,
            index=False,
            chunksize=chunksize,
            method="multi"
        )

        print(f"✅ Successfully transferred '{table_name}' to PostgreSQL")

    except Exception as e:
        print(f"❌ Error transferring table '{table_name}': {e}")

    finally:
        sqlite_conn.close()


# =========================
# USAGE
# =========================

if __name__ == "__main__":
    # 👇 Give your table name here
    transfer_table("fund_ranks")
    # You can call multiple manually:
    # transfer_table("table1")
    # transfer_table("table2")
    # transfer_table("table3")