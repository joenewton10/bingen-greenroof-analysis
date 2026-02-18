"""
Verify row counts in all Bingen pipeline tables.

Tables checked:
- Ingested: ingested_empower_greenroof, ingested_kissel_greenroof, ingested_parkplatz
- Validated: val_ingested_empower_greenroof, val_ingested_kissel_greenroof, val_ingested_parkplatz
- Harmonized: harm_greenroof, harm_parkplatz
- Final: synchronized_data_filtered
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline.ingest.base import get_connection


def count_table(cur, table_name):
    """Get row count for a table, return 0 if table doesn't exist."""
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cur.fetchone()[0]
    except Exception:
        return None


def main():
    conn = get_connection()
    cur = conn.cursor()
    conn.autocommit = True  # Prevent transaction blocking on non-existent tables

    print("=" * 60)
    print("BINGEN GREENROOF PIPELINE - TABLE COUNTS")
    print("=" * 60)

    # INGESTED TABLES
    print("\n[INGESTED TABLES]")
    print("-" * 40)
    
    emp = count_table(cur, "ingested_empower_greenroof")
    kissel = count_table(cur, "ingested_kissel_greenroof")
    park_ing = count_table(cur, "ingested_parkplatz")
    
    if emp is not None:
        print(f"  ingested_empower_greenroof:  {emp:>12,} rows")
    else:
        print(f"  ingested_empower_greenroof:  (not created)")
        
    if kissel is not None:
        print(f"  ingested_kissel_greenroof:   {kissel:>12,} rows")
    else:
        print(f"  ingested_kissel_greenroof:   (not created)")
        
    if park_ing is not None:
        print(f"  ingested_parkplatz:          {park_ing:>12,} rows")
    else:
        print(f"  ingested_parkplatz:          (not created)")

    if emp is not None and kissel is not None:
        greenroof_total = emp + kissel
        print(f"  GREENROOF TOTAL:             {greenroof_total:>12,} rows")
        expected_greenroof = 2801240
        print(f"  (Expected: {expected_greenroof:,})")

    # VALIDATED TABLES
    print("\n[VALIDATED TABLES]")
    print("-" * 40)
    
    val_emp = count_table(cur, "val_ingested_empower_greenroof")
    val_kissel = count_table(cur, "val_ingested_kissel_greenroof")
    val_park = count_table(cur, "val_ingested_parkplatz")
    
    if val_emp is not None:
        print(f"  val_ingested_empower_greenroof:  {val_emp:>8,} rows")
    else:
        print(f"  val_ingested_empower_greenroof:  (not created)")
        
    if val_kissel is not None:
        print(f"  val_ingested_kissel_greenroof:   {val_kissel:>8,} rows")
    else:
        print(f"  val_ingested_kissel_greenroof:   (not created)")
        
    if val_park is not None:
        print(f"  val_ingested_parkplatz:          {val_park:>8,} rows")
    else:
        print(f"  val_ingested_parkplatz:          (not created)")

    # HARMONIZED TABLES
    print("\n[HARMONIZED TABLES]")
    print("-" * 40)
    
    harm_gr = count_table(cur, "harm_greenroof")
    harm_pk = count_table(cur, "harm_parkplatz")
    
    if harm_gr is not None:
        print(f"  harm_greenroof:   {harm_gr:>12,} rows")
    else:
        print(f"  harm_greenroof:   (not created)")
        
    if harm_pk is not None:
        print(f"  harm_parkplatz:   {harm_pk:>12,} rows")
    else:
        print(f"  harm_parkplatz:   (not created)")

    # SYNCHRONIZED TABLE
    print("\n[FINAL SYNCHRONIZED TABLE]")
    print("-" * 40)
    
    sync = count_table(cur, "synchronized_data_filtered")
    
    if sync is not None:
        print(f"  synchronized_data_filtered:  {sync:>8,} rows (minute-level)")
        
        # Get date range
        cur.execute("""
            SELECT MIN(timestamp), MAX(timestamp) 
            FROM synchronized_data_filtered
        """)
        result = cur.fetchone()
        if result and result[0]:
            print(f"  Date range: {result[0]} to {result[1]}")
    else:
        print(f"  synchronized_data_filtered:  (not created)")

    print("\n" + "=" * 60)
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
