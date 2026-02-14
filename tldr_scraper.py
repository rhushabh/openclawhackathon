#!/usr/bin/env python3
"""
TDLR Project Scraper - Fixed Version
Scrapes project data from the Texas Department of Licensing and Regulation TABS system
and stores it in a SQLite database.

This version correctly accesses the API endpoint that returns JSON data.
"""

import requests
import sqlite3
import time
import argparse
import json
import uuid
from urllib.parse import urljoin, urlparse
import os
import sys


class TDLRScraper:
    def __init__(self, db_path='tdlr_projects.db'):
        self.base_url = 'https://www.tdlr.texas.gov'
        self.api_url = f'{self.base_url}/TABS/Search/SearchProjects'
        self.db_path = db_path
        self.session = requests.Session()
        # Set headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/plain, */*'
        })
        
        # Initialize database
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database with the required table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Drop table if it exists (to handle schema changes)
        cursor.execute('''DROP TABLE IF EXISTS projects''')
        
        # Create projects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT UNIQUE,
                project_number TEXT,
                project_name TEXT,
                project_created_on TEXT,
                project_status INTEGER,
                facility_name TEXT,
                city INTEGER,
                county INTEGER,
                type_of_work INTEGER,
                estimated_cost REAL,
                data_version_id INTEGER,
                estimated_start_date TEXT,
                estimated_end_date TEXT,
                date_scraped TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"Database initialized at {self.db_path}")
    
    def scrape_all_projects(self, batch_size=15, delay=1, max_records=None):
        """
        Scrape all project data from the API.
        
        Args:
            batch_size (int): Number of records to fetch per request (max 15 based on API)
            delay (int): Delay in seconds between requests
            max_records (int): Maximum number of records to fetch (None for all)
        """
        print("Starting to scrape TDLR projects...")
        
        # First, get total count to understand scope
        payload = {
            "draw": 1,
            "start": 0,
            "length": 1,
            "search-type": "default"
        }
        
        try:
            response = self.session.post(self.api_url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                total_records = data.get('recordsTotal', 0)
                print(f"Total records available: {total_records}")
                if max_records:
                    print(f"Will fetch up to {max_records} records as requested")
            else:
                print(f"Failed to get record count. Status code: {response.status_code}")
                return 0
        except Exception as e:
            print(f"Error getting record count: {e}")
            return 0
        
        # Now scrape in batches
        total_saved = 0
        start = 0
        
        while True:
            # Check if we've reached the maximum records requested
            if max_records and total_saved >= max_records:
                print(f"Reached the requested limit of {max_records} records.")
                break
                
            # Adjust batch size if we're close to the limit
            current_batch_size = min(batch_size, 15)  # API seems to max at 15
            if max_records and total_saved + current_batch_size > max_records:
                current_batch_size = max_records - total_saved
                if current_batch_size <= 0:
                    break
            
            print(f"Fetching records {start} to {start + current_batch_size}...")
            
            payload = {
                "draw": 1,
                "start": start,
                "length": current_batch_size,
                "search-type": "default"
            }
            
            try:
                response = self.session.post(self.api_url, json=payload, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    projects = data.get('data', [])
                    
                    if not projects:
                        print("No more projects to fetch.")
                        break
                    
                    saved_count = self.save_to_database(projects)
                    total_saved += saved_count
                    
                    print(f"Saved {saved_count} projects. Total saved: {total_saved}")
                    
                    # Check if we've reached the end
                    if len(projects) < current_batch_size:
                        print("Reached the end of available data.")
                        break
                    
                    # Move to next batch
                    start += len(projects)  # Use actual count, not requested count
                    
                    # Check if we've reached the maximum records requested
                    if max_records and total_saved >= max_records:
                        print(f"Reached the requested limit of {max_records} records.")
                        break
                    
                    # Be respectful - don't hammer the server
                    time.sleep(delay)
                else:
                    print(f"Failed to fetch records. Status code: {response.status_code}")
                    break
                    
            except KeyboardInterrupt:
                print("\nScraping interrupted by user.")
                break
            except Exception as e:
                print(f"Error scraping batch starting at {start}: {e}")
                # Continue with next batch rather than stopping completely
                start += 15  # Move forward by the typical batch size
                time.sleep(delay)
        
        print(f"Finished scraping. Total projects saved: {total_saved}")
        return total_saved
    
    def save_to_database(self, projects_data):
        """Save scraped project data to the SQLite database."""
        if not projects_data:
            return 0
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        for project in projects_data:
            try:
                # Handle missing project_id by generating a UUID
                project_id = project.get('ProjectId')
                if not project_id:
                    # Generate a UUID based on project number if available, otherwise random
                    project_number = project.get('ProjectNumber', '')
                    if project_number:
                        # Create a deterministic UUID based on project number
                        project_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, project_number))
                    else:
                        # Generate a random UUID
                        project_id = str(uuid.uuid4())
                
                cursor.execute('''
                    INSERT OR REPLACE INTO projects 
                    (project_id, project_number, project_name, project_created_on, 
                     project_status, facility_name, city, county, type_of_work,
                     estimated_cost, data_version_id, estimated_start_date, estimated_end_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    project_id,  # Fixed: Use generated or existing project_id
                    project.get('ProjectNumber'),
                    project.get('ProjectName'),
                    project.get('ProjectCreatedOn'),
                    project.get('ProjectStatus'),
                    project.get('FacilityName'),
                    project.get('City'),
                    project.get('County'),
                    project.get('TypeOfWork'),
                    project.get('EstimatedCost'),
                    project.get('DataVersionId'),
                    project.get('EstimatedStartDate'),
                    project.get('EstimatedEndDate')
                ))
                saved_count += 1
            except sqlite3.Error as e:
                print(f"Database error saving project {project.get('ProjectNumber')}: {e}")
            except Exception as e:
                print(f"Unexpected error saving project {project.get('ProjectNumber')}: {e}")
        
        conn.commit()
        conn.close()
        
        return saved_count


class ProjectSearcher:
    def __init__(self, db_path='tdlr_projects.db'):
        self.db_path = db_path
        
        # Check if database exists
        if not os.path.exists(self.db_path):
            print(f"Database {self.db_path} not found.")
            sys.exit(1)
    
    def search_projects(self, search_term, search_fields=None):
        """Search for projects in the database."""
        if search_fields is None:
            search_fields = ['project_number', 'project_name', 'facility_name']
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build query dynamically
        conditions = []
        params = []
        
        # Support for different search term formats
        search_patterns = [
            search_term,  # Exact match
            f"%{search_term}%",  # Contains
        ]
        
        for field in search_fields:
            for pattern in search_patterns:
                conditions.append(f"{field} LIKE ?")
                params.append(pattern)
        
        query = f"SELECT * FROM projects WHERE {' OR '.join(conditions)} ORDER BY date_scraped DESC LIMIT 100"
        
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Get column names
            column_names = [description[0] for description in cursor.description]
            
            conn.close()
            return column_names, results
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            conn.close()
            return [], []


def main():
    parser = argparse.ArgumentParser(description="TDLR Project Scraper and Searcher")
    parser.add_argument('--scrape', action='store_true', help='Scrape project data from TDLR website')
    parser.add_argument('--search', type=str, help='Search for projects in the database')
    parser.add_argument('--db-path', type=str, default='tdlr_projects.db', help='Path to SQLite database')
    parser.add_argument('--batch-size', type=int, default=15, help='Number of records to fetch per request (default: 15)')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay in seconds between requests (default: 1.0)')
    parser.add_argument('--max-records', type=int, help='Maximum number of records to fetch (default: all)')
    
    args = parser.parse_args()
    
    if args.scrape:
        print("Starting TDLR project scraping...")
        scraper = TDLRScraper(args.db_path)
        
        count = scraper.scrape_all_projects(
            batch_size=args.batch_size, 
            delay=args.delay,
            max_records=args.max_records
        )
        print(f"Successfully saved {count} projects to database.")
    
    elif args.search:
        print(f"Searching for projects containing '{args.search}'...")
        searcher = ProjectSearcher(args.db_path)
        
        columns, results = searcher.search_projects(args.search)
        
        if results:
            print(f"\nFound {len(results)} projects:")
            print("-" * 100)
            
            # Print header
            header = "{:<36} {:<15} {:<20} {:<20}".format("Project ID", "Project Number", "Facility Name", "Project Name")
            print(header)
            print("-" * len(header))
            
            # Print results (first 20 for brevity)
            for i, row in enumerate(results):
                if i >= 20:  # Limit output
                    print(f"... and {len(results) - 20} more results")
                    break
                    
                # Extract key fields (adjust indices based on your table structure)
                project_id = str(row[1])[:35] if row[1] else ""
                project_number = str(row[2])[:14] if row[2] else ""
                facility_name = str(row[6])[:19] if row[6] else ""
                project_name = str(row[3])[:19] if row[3] else ""
                
                print("{:<36} {:<15} {:<20} {:<20}".format(project_id, project_number, facility_name, project_name))
        else:
            print("No projects found matching your search criteria.")
            print("Note: You may need to run the scraper first to populate the database.")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
