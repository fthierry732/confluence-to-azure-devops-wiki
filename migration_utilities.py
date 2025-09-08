#!/usr/bin/env python3
"""
Utility scripts for Confluence to Azure DevOps Wiki migration
Handles common scenarios and cleanup tasks
"""

import requests
import json
import re
import os
from typing import Dict, List
import base64

class MigrationUtilities:
    def __init__(self, confluence_config: Dict, azuredevops_config: Dict):
        self.confluence_config = confluence_config
        self.azuredevops_config = azuredevops_config
        
        self.confluence_auth = (confluence_config['username'], confluence_config['api_token'])
        pat_token = azuredevops_config['personal_access_token']
        auth_string = base64.b64encode(f":{pat_token}".encode()).decode()
        self.azuredevops_headers = {
            'Authorization': f'Basic {auth_string}',
            'Content-Type': 'application/json'
        }

    def preview_migration(self, space_key: str) -> Dict:
        """Preview what will be migrated without actually doing it"""
        print(f"Previewing migration for space: {space_key}")
        
        pages = self.get_confluence_pages(space_key)
        
        preview = {
            'total_pages': len(pages),
            'pages_by_level': {},
            'total_attachments': 0,
            'image_attachments': 0,
            'pages_with_issues': []
        }
        
        for page in pages:
            # Determine page level
            level = len(page.get('ancestors', []))
            if level not in preview['pages_by_level']:
                preview['pages_by_level'][level] = 0
            preview['pages_by_level'][level] += 1
            
            # Check attachments
            try:
                attachments = self.get_page_attachments(page['id'])
                preview['total_attachments'] += len(attachments)
                
                for attachment in attachments:
                    if attachment['metadata']['mediaType'].startswith('image/'):
                        preview['image_attachments'] += 1
                        
            except Exception as e:
                preview['pages_with_issues'].append({
                    'page': page['title'],
                    'issue': f"Attachment check failed: {str(e)}"
                })
        
        # Print preview
        print(f"\n--- Migration Preview ---")
        print(f"Total pages: {preview['total_pages']}")
        print(f"Total attachments: {preview['total_attachments']}")
        print(f"Image attachments: {preview['image_attachments']}")
        print(f"Pages by level:")
        for level, count in sorted(preview['pages_by_level'].items()):
            print(f"  Level {level}: {count} pages")
        
        if preview['pages_with_issues']:
            print(f"\nPages with potential issues: {len(preview['pages_with_issues'])}")
            for issue in preview['pages_with_issues'][:5]:  # Show first 5
                print(f"  - {issue['page']}: {issue['issue']}")
        
        return preview

    def get_confluence_pages(self, space_key: str) -> List[Dict]:
        """Get all pages from a Confluence space"""
        pages = []
        start = 0
        limit = 50
        
        while True:
            url = f"{self.confluence_config['base_url']}/wiki/rest/api/content"
            params = {
                'spaceKey': space_key,
                'type': 'page',
                'status': 'current',
                'expand': 'body.storage,ancestors,children,metadata.labels',
                'start': start,
                'limit': limit
            }
            
            response = requests.get(url, auth=self.confluence_auth, params=params)
            response.raise_for_status()
            
            data = response.json()
            pages.extend(data['results'])
            
            if len(data['results']) < limit:
                break
            start += limit
            
        return pages

    def get_page_attachments(self, page_id: str) -> List[Dict]:
        """Get all attachments for a specific page"""
        url = f"{self.confluence_config['base_url']}/wiki/rest/api/content/{page_id}/child/attachment"
        params = {'expand': 'download'}
        
        response = requests.get(url, auth=self.confluence_auth, params=params)
        response.raise_for_status()
        
        return response.json()['results']

    def validate_azure_devops_connection(self) -> bool:
        """Test Azure DevOps connection and permissions"""
        print("Validating Azure DevOps connection...")
        
        # Test basic API access
        url = f"https://dev.azure.com/{self.azuredevops_config['organization']}/_apis/projects"
        response = requests.get(url, headers=self.azuredevops_headers, params={'api-version': '6.0'})
        
        if response.status_code != 200:
            print(f"❌ Failed to connect to Azure DevOps: {response.status_code}")
            return False
        
        print("✅ Azure DevOps API connection successful")
        
        # Test wiki access
        wiki_url = (f"https://dev.azure.com/{self.azuredevops_config['organization']}/"
                   f"{self.azuredevops_config['project']}/_apis/wiki/wikis/"
                   f"{self.azuredevops_config['wiki_identifier']}")
        
        wiki_response = requests.get(wiki_url, headers=self.azuredevops_headers, params={'api-version': '6.0'})
        
        if wiki_response.status_code != 200:
            print(f"❌ Failed to access wiki: {wiki_response.status_code}")
            print("   Make sure the wiki exists and you have permissions")
            return False
        
        print("✅ Wiki access successful")
        return True

    def validate_confluence_connection(self, space_key: str) -> bool:
        """Test Confluence connection and space access"""
        print("Validating Confluence connection...")
        
        # Test basic API access
        url = f"{self.confluence_config['base_url']}/wiki/rest/api/space/{space_key}"
        response = requests.get(url, auth=self.confluence_auth)
        
        if response.status_code != 200:
            print(f"❌ Failed to access Confluence space: {response.status_code}")
            return False
        
        space_info = response.json()
        print(f"✅ Confluence space access successful: {space_info['name']}")
        return True

    def cleanup_temp_files(self):
        """Clean up temporary files created during migration"""
        import shutil
        
        directories_to_clean = ['temp_images', 'processed_pages']
        
        for directory in directories_to_clean:
            if os.path.exists(directory):
                shutil.rmtree(directory)
                print(f"Cleaned up {directory}/")
        
        print("Temporary files cleaned up")

    def generate_link_mapping_report(self, space_key: str) -> Dict:
        """Generate a report of all links that need to be updated"""
        pages = self.get_confluence_pages(space_key)
        link_report = {
            'internal_links': [],
            'external_links': [],
            'broken_links': [],
            'image_links': []
        }
        
        for page in pages:
            html_content = page['body']['storage']['value']
            
            # Find all links
            link_patterns = [
                r'<ac:link><ri:page ri:content-title="([^"]+)"',  # Internal page links
                r'href="([^"]+)"',  # Regular href links
                r'<ri:attachment ri:filename="([^"]+)"'  # Image attachments
            ]
            
            for pattern in link_patterns:
                matches = re.findall(pattern, html_content)
                for match in matches:
                    if 'ri:attachment' in pattern:
                        link_report['image_links'].append({
                            'page': page['title'],
                            'image': match
                        })
                    elif self.confluence_config['base_url'] in match:
                        link_report['internal_links'].append({
                            'page': page['title'],
                            'link': match
                        })
                    else:
                        link_report['external_links'].append({
                            'page': page['title'],
                            'link': match
                        })
        
        # Print report
        print(f"\n--- Link Mapping Report ---")
        print(f"Internal links to update: {len(link_report['internal_links'])}")
        print(f"External links (unchanged): {len(link_report['external_links'])}")
        print(f"Image links to process: {len(link_report['image_links'])}")
        
        return link_report

    def migrate_single_page(self, page_id: str) -> bool:
        """Migrate a single page (useful for testing)"""
        print(f"Migrating single page: {page_id}")
        
        # Get page content
        url = f"{self.confluence_config['base_url']}/wiki/rest/api/content/{page_id}"
        params = {'expand': 'body.storage,ancestors,children'}
        
        response = requests.get(url, auth=self.confluence_auth, params=params)
        if response.status_code != 200:
            print(f"❌ Failed to get page content: {response.status_code}")
            return False
        
        page = response.json()
        print(f"Processing page: {page['title']}")
        
        # Simple conversion (without full migration class)
        html_content = page['body']['storage']['value']
        
        # Basic HTML to Markdown conversion
        import html2text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.body_width = 0
        
        markdown_content = h.handle(html_content)
        
        # Save locally for review
        safe_title = re.sub(r'[<>:"/\\|?*]', '-', page['title'])
        with open(f"{safe_title}.md", 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        print(f"✅ Page content saved to {safe_title}.md")
        return True

    def batch_migrate_by_label(self, space_key: str, label: str):
        """Migrate only pages with a specific label"""
        print(f"Migrating pages with label: {label}")
        
        url = f"{self.confluence_config['base_url']}/wiki/rest/api/content/search"
        params = {
            'cql': f'space = {space_key} AND label = {label}',
            'expand': 'body.storage,ancestors'
        }
        
        response = requests.get(url, auth=self.confluence_auth, params=params)
        response.raise_for_status()
        
        pages = response.json()['results']
        print(f"Found {len(pages)} pages with label '{label}'")
        
        # Process each page (simplified version)
        for page in pages:
            try:
                self.migrate_single_page(page['id'])
            except Exception as e:
                print(f"❌ Failed to migrate {page['title']}: {str(e)}")

def main():
    """Interactive utility runner"""
    print("Confluence to Azure DevOps Migration Utilities")
    print("=" * 50)
    
    # Configuration
    confluence_config = {
        'base_url': 'https://yourcompany.atlassian.net',
        'username': 'your_email@company.com',
        'api_token': 'your_confluence_api_token',
        'space_key': 'YOURSPACE'
    }
    
    azuredevops_config = {
        'organization': 'your-organization',
        'project': 'your-project',
        'wiki_identifier': 'your-wiki-name',
        'personal_access_token': 'your_pat_token'
    }
    
    utils = MigrationUtilities(confluence_config, azuredevops_config)
    
    while True:
        print("\nAvailable utilities:")
        print("1. Preview migration")
        print("2. Validate connections")
        print("3. Generate link mapping report")
        print("4. Migrate single page")
        print("5. Clean up temp files")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ")
        
        try:
            if choice == '1':
                space_key = input("Enter space key: ")
                utils.preview_migration(space_key)
            
            elif choice == '2':
                space_key = input("Enter space key: ")
                confluence_ok = utils.validate_confluence_connection(space_key)
                azuredevops_ok = utils.validate_azure_devops_connection()
                if confluence_ok and azuredevops_ok:
                    print("✅ All connections validated successfully!")
                else:
                    print("❌ Please fix connection issues before migrating")
            
            elif choice == '3':
                space_key = input("Enter space key: ")
                utils.generate_link_mapping_report(space_key)
            
            elif choice == '4':
                page_id = input("Enter page ID: ")
                utils.migrate_single_page(page_id)
            
            elif choice == '5':
                utils.cleanup_temp_files()
            
            elif choice == '6':
                print("Goodbye!")
                break
            
            else:
                print("Invalid choice. Please try again.")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    main()
