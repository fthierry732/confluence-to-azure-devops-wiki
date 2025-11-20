#!/usr/bin/env python3
"""
Test script for offline mode migration
This script demonstrates how to use the offline mode with the TEST folder
"""

import os
import sys

# Make sure beautifulsoup4 is installed
try:
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ beautifulsoup4 is not installed")
    print("Please install it with: pip install beautifulsoup4")
    sys.exit(1)

from confluence_migration_corrected import ConfluenceToAzureDevOpsHierarchicalMigrator

def test_offline_mode():
    """Test offline mode with the TEST folder"""
    
    print("🧪 Testing Offline Mode Migration")
    print("=" * 50)
    
    # Check if TEST folder exists
    test_folder = "TEST"
    if not os.path.exists(test_folder):
        print(f"❌ TEST folder not found: {test_folder}")
        print("Please ensure the TEST folder exists in the project root")
        return False
    
    print(f"✅ Found TEST folder: {test_folder}")
    
    # Dummy Confluence config (not used in offline mode)
    confluence_config = {
        'base_url': 'https://dummy.atlassian.net',
        'username': 'dummy@example.com',
        'api_token': 'dummy_token'
    }
    
    # Azure DevOps config (you need to provide real values)
    azuredevops_config = {
        'organization': os.getenv('DEVOPS_ORGANIZATION', 'YOUR_ORG'),
        'project': os.getenv('DEVOPS_PROJECT', 'YOUR_PROJECT'),
        'wiki_identifier': os.getenv('DEVOPS_WIKI_IDENTIFIER', 'YOUR_PROJECT.wiki'),
        'personal_access_token': os.getenv('DEVOPS_PAT', 'YOUR_PAT')
    }
    
    # Check if Azure DevOps config is set
    if 'YOUR' in azuredevops_config['organization']:
        print("\n⚠️ Azure DevOps configuration not set!")
        print("Please set the following environment variables:")
        print("  export DEVOPS_ORGANIZATION=your-org")
        print("  export DEVOPS_PROJECT=your-project")
        print("  export DEVOPS_WIKI_IDENTIFIER=your-project.wiki")
        print("  export DEVOPS_PAT=your-pat-token")
        print("\nOr edit this script to set the values directly.")
        return False
    
    print("\n📋 Configuration:")
    print(f"  Export Folder: {test_folder}")
    print(f"  Organization: {azuredevops_config['organization']}")
    print(f"  Project: {azuredevops_config['project']}")
    print(f"  Wiki: {azuredevops_config['wiki_identifier']}")
    print()
    
    # Create migrator instance
    migrator = ConfluenceToAzureDevOpsHierarchicalMigrator(
        confluence_config, 
        azuredevops_config
    )
    
    # Run migration in offline mode
    print("🚀 Starting offline migration...\n")
    success = migrator.migrate_from_local_export(test_folder)
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Test completed successfully!")
        print("\nNext steps:")
        print("1. Check your Azure DevOps Wiki")
        print("2. Verify pages are created correctly")
        print("3. Check that images are loading")
    else:
        print("❌ Test failed!")
        print("\nPlease check the error messages above.")
    
    return success

if __name__ == "__main__":
    print("Confluence to Azure DevOps Wiki - Offline Mode Test")
    print()
    
    try:
        success = test_offline_mode()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


