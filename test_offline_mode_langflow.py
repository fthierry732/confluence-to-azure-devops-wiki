#!/usr/bin/env python3
"""
Test script for offline mode migration using Langflow
This script demonstrates how to use the offline mode with the TEST folder
using the Langflow-based migration script
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

# Check if langflow is installed
try:
    from langflow.load import run_flow_from_json as run_flow
except ImportError:
    try:
        from langflow import run_flow_from_json as run_flow
    except ImportError:
        print("❌ langflow is not installed")
        print("Please install it with: pip install langflow")
        sys.exit(1)

from confluence_migration_langflow_corrected import ConfluenceToAzureDevOpsHierarchicalMigrator

def test_offline_mode_langflow():
    """Test offline mode with the TEST folder using Langflow"""
    
    print("🧪 Testing Offline Mode Migration (Langflow)")
    print("=" * 50)
    
    # Check if TEST folder exists
    test_folder = os.getenv('EXPORT_FOLDER', 'TEST')
    if not os.path.exists(test_folder):
        print(f"❌ Export folder not found: {test_folder}")
        print("Please ensure the export folder exists in the project root")
        print("You can set EXPORT_FOLDER environment variable to specify a different folder")
        return False
    
    print(f"✅ Found export folder: {test_folder}")
    
    # Check if Langflow flow file exists
    langflow_flow = os.path.join('langflows', 'Migrator 2.0 (0) (openai).json')
    if not os.path.exists(langflow_flow):
        print(f"❌ Langflow flow file not found: {langflow_flow}")
        print("Please ensure the Langflow flow file exists")
        return False
    
    print(f"✅ Found Langflow flow: {langflow_flow}")
    
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
    print(f"  Langflow Flow: {langflow_flow}")
    print(f"  Organization: {azuredevops_config['organization']}")
    print(f"  Project: {azuredevops_config['project']}")
    print(f"  Wiki: {azuredevops_config['wiki_identifier']}")
    print()
    
    # Create migrator instance
    try:
        migrator = ConfluenceToAzureDevOpsHierarchicalMigrator(
            confluence_config, 
            azuredevops_config
        )
    except Exception as e:
        print(f"❌ Failed to create migrator: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # Run migration in offline mode
    print("🚀 Starting offline migration with Langflow...\n")
    try:
        success = migrator.migrate_from_local_export(test_folder)
    except Exception as e:
        print(f"\n❌ Migration failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Test completed successfully!")
        print("\nNext steps:")
        print("1. Check your Azure DevOps Wiki")
        print("2. Verify pages are created correctly")
        print("3. Check that images are loading")
        print("4. Verify markdown formatting is correct (converted by Langflow)")
    else:
        print("❌ Test failed!")
        print("\nPlease check the error messages above.")
    
    return success

if __name__ == "__main__":
    print("Confluence to Azure DevOps Wiki - Offline Mode Test (Langflow)")
    print()
    
    try:
        success = test_offline_mode_langflow()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

