#!/usr/bin/env python3
"""
Simple test script to verify the TDLR scraper is working correctly
"""

import sqlite3
import os

def test_database():
    """Test that the database was created correctly and has data"""
    db_path = 'tdlr_projects.db'
    
    # Check if database exists
    if not os.path.exists(db_path):
        print("ERROR: Database file not found!")
        return False
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Count records
    cursor.execute("SELECT COUNT(*) FROM projects")
    count = cursor.fetchone()[0]
    
    print(f"Database contains {count} records")
    
    if count > 0:
        # Show some sample data
        cursor.execute("SELECT project_number, project_name, facility_name FROM projects LIMIT 5")
        rows = cursor.fetchall()
        
        print("\nSample records:")
        print("-" * 80)
        for row in rows:
            print(f"Project: {row[0]:<15} | Name: {row[1]:<20} | Facility: {row[2]}")
        
        conn.close()
        return True
    else:
        print("ERROR: No records found in database!")
        conn.close()
        return False

if __name__ == "__main__":
    print("Testing TDLR Scraper Database...")
    success = test_database()
    
    if success:
        print("\n✓ Test PASSED - Database is working correctly")
    else:
        print("\n✗ Test FAILED - There are issues with the database")
        
    print("\nTo search for projects, run:")
    print("python3 tdlr_scraper_fixed.py --search \"YOUR_SEARCH_TERM\"")
