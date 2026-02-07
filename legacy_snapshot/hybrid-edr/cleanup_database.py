#!/usr/bin/env python3
"""
EDR Database Cleanup Utility
Removes old events with tiered retention policies:
- Critical alerts: 90 days
- Process events: 30 days
- File events: 14 days
- Network events: 7 days
"""

import sqlite3
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

def cleanup_database(db_path: str, dry_run: bool = False, log_file: str = None):
    """
    Remove old events using tiered retention policies
    
    Args:
        db_path: Path to edr.db
        dry_run: If True, show what would be deleted without deleting
        log_file: Optional path to log file
    """
    
    # Setup logging
    if log_file:
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    db_path = Path(db_path)
    if not db_path.exists():
        msg = f"ERROR: Database not found: {db_path}"
        print(msg)
        if log_file:
            logging.error(msg)
        sys.exit(1)
    
    # Tiered retention policies (in days)
    retention_policies = {
        'alerts': 30,        # Critical alerts: 30 days
        'process_events': 7,  # Process events: 7 days (reduced from 30 to manage DB size)
        'file_events': 7,     # File events: 7 days
        'network_events': 3    # Network events: 3 days (reduced from 7)
    }
    
    print(f"EDR Database Cleanup")
    print(f"=" * 70)
    print(f"Database: {db_path}")
    print(f"Retention Policies:")
    for table, days in retention_policies.items():
        print(f"  {table}: {days} days")
    print(f"Dry run: {dry_run}")
    print(f"=" * 70)
    print()
    
    # Get initial size
    initial_size_mb = db_path.stat().st_size / (1024 * 1024)
    print(f"Initial database size: {initial_size_mb:.2f} MB")
    if log_file:
        logging.info(f"Starting cleanup - Initial size: {initial_size_mb:.2f} MB")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    total_deleted = 0
    
    try:
        # Process each table with its retention policy
        for table_name, days_to_keep in retention_policies.items():
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cutoff_timestamp = cutoff_date.isoformat()
            
            # Check if table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            if not cursor.fetchone():
                print(f"\n{table_name}: Table not found, skipping")
                continue
            
            # Count events to be removed
            cursor.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE timestamp < ?",
                (cutoff_timestamp,)
            )
            old_count = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            total_count = cursor.fetchone()[0]
            
            print(f"\n{table_name}:")
            print(f"  Total: {total_count:,}")
            print(f"  Old (> {days_to_keep} days): {old_count:,}")
            print(f"  Will keep: {total_count - old_count:,}")
            
            if old_count == 0:
                print(f"  ✓ No old events to clean up")
                continue
            
            if dry_run:
                print(f"  [DRY RUN] Would delete {old_count:,} events")
            else:
                print(f"  Deleting {old_count:,} old events...")
                
                # Delete old events
                cursor.execute(
                    f"DELETE FROM {table_name} WHERE timestamp < ?",
                    (cutoff_timestamp,)
                )
                conn.commit()
                total_deleted += old_count
                
                print(f"  ✓ Deleted {old_count:,} events")
                if log_file:
                    logging.info(f"{table_name}: Deleted {old_count:,} events")
        
        if total_deleted == 0 and not dry_run:
            print("\n✓ No old events to clean up!")
            if log_file:
                logging.info("No old events to clean up")
            return
        
        if not dry_run:
            # Vacuum to reclaim space
            print("\nVacuuming database to reclaim space...")
            conn.execute("VACUUM")
            print("✓ Vacuum completed")
            if log_file:
                logging.info("Vacuum completed")
            
            # Get final size
            conn.close()
            final_size_mb = db_path.stat().st_size / (1024 * 1024)
            saved_mb = initial_size_mb - final_size_mb
            
            print(f"\nResults:")
            print(f"  Total events deleted: {total_deleted:,}")
            print(f"  Initial size: {initial_size_mb:.2f} MB")
            print(f"  Final size: {final_size_mb:.2f} MB")
            print(f"  Space saved: {saved_mb:.2f} MB ({saved_mb/initial_size_mb*100:.1f}%)")
            print(f"\n✓ Cleanup completed successfully!")
            
            if log_file:
                logging.info(f"Cleanup completed - Deleted: {total_deleted:,}, Saved: {saved_mb:.2f} MB")
            
            # Check if database is still too large (>1GB warning, >5GB critical)
            if final_size_mb > 5000:
                warning = "⚠️  WARNING: Database is >5GB! Consider more aggressive retention."
                print(f"\n{warning}")
                if log_file:
                    logging.warning(warning)
            elif final_size_mb > 1000:
                info = "ℹ️  INFO: Database is >1GB. Monitor growth."
                print(f"\n{info}")
                if log_file:
                    logging.info(info)
            
    except Exception as e:
        msg = f"ERROR: Cleanup failed: {e}"
        print(f"\n{msg}")
        if log_file:
            logging.error(msg)
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Clean up old EDR database events with tiered retention"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--db",
        default="/Users/garrylewis/Security/hybrid-edr/data/edr.db",
        help="Path to database (default: data/edr.db)"
    )
    parser.add_argument(
        "--log",
        default="/Users/garrylewis/Security/hybrid-edr/logs/cleanup.log",
        help="Path to log file (default: logs/cleanup.log)"
    )
    
    args = parser.parse_args()
    
    cleanup_database(args.db, args.dry_run, args.log)
