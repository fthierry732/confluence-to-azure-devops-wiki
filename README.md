# Confluence to Azure DevOps Wiki Migration Tool

A comprehensive tool for migrating content from Confluence spaces to Azure DevOps wikis with hierarchical structure preservation, attachment handling, and a user-friendly web interface.

## Features

- **Complete Content Migration**: Pages, attachments, and hierarchical structure
- **Web-based Interface**: Easy-to-use GUI for configuration and monitoring
- **Connection Validation**: Test your configurations before running migrations
- **Real-time Progress Tracking**: Monitor migration progress with live logs
- **Hierarchical Structure**: Maintains parent-child page relationships
- **Attachment Support**: Migrates images and files with proper linking

## Prerequisites

- Python 3.7+
- Confluence Cloud account with API access
- Azure DevOps organization with a project and wiki

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd confluence-to-azure-devops-wiki
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install flask
   ```

3. **Run the web interface**:
   ```bash
   python3 web_ui.py
   ```

4. **Open your browser** and navigate to: `http://localhost:5001`

## Setup Instructions

### 1. Confluence API Token Setup

1. **Log in to Confluence Cloud**:
   - Go to [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)

2. **Create API Token**:
   - Click "Create API token"
   - Label: `Azure DevOps Migration`
   - Click "Create"
   - **Copy the token immediately** (you won't see it again)

3. **Find your Space Key**:
   - Go to your Confluence space
   - Look in the URL: `https://yourcompany.atlassian.net/wiki/spaces/SPACEKEY/`
   - The space key is the part after `/spaces/` (e.g., "SPACEKEY")

### 2. Azure DevOps Personal Access Token (PAT) Setup

1. **Sign in to Azure DevOps**:
   - Go to [https://dev.azure.com](https://dev.azure.com)
   - Sign in to your organization

2. **Create Personal Access Token**:
   - Click your profile picture (top right)
   - Select "Personal access tokens"
   - Click "New Token"
   - **Configure the token**:
     - Name: `Confluence Migration`
     - Organization: Select your organization
     - Expiration: Choose appropriate duration
     - Scopes: Select "Custom defined"
     - **Required Scopes**:
       - ✅ **Wiki (Read & write)** - Essential for creating wiki pages
       - ✅ **Code (Read)** - Required for wiki repository access
       - ✅ **Project and team (Read)** - For project validation
   - Click "Create"
   - **Copy the token immediately** (you won't see it again)

### 3. Azure DevOps Project Configuration

#### 3.1 Enable Azure Repos (Required for Wiki)

1. **Go to your project settings**:
   - Navigate to `https://dev.azure.com/{organization}/{project}`
   - Click "Project Settings" (bottom left)

2. **Enable Azure Repos**:
   - Go to "Services" under "General"
   - Find "Repos" and ensure it's **ON** (toggle to the right)
   - If disabled, click the toggle to enable it

#### 3.2 Create or Configure Wiki

1. **Navigate to Wiki section**:
   - In your project, click "Wiki" in the left sidebar
   
2. **Create Project Wiki** (if none exists):
   - Click "Create project wiki"
   - This creates a Git repository for your wiki

3. **Find Wiki Identifier**:
   - Go to Wiki
   - Check the URL: `https://dev.azure.com/{org}/{project}/_wiki/wikis/{wiki-identifier}`
   - The wiki identifier is typically: `{project}.wiki`

#### 3.3 Verify Wiki Repository Access

1. **Check Wiki Repository**:
   - Go to "Repos" in your project
   - You should see a repository named `{project}.wiki`
   - This confirms the wiki is properly configured

## Configuration Parameters

### Environment Variables (Recommended)

You can set up your configuration using environment variables to avoid entering credentials each time. Create a `.env` file in the project root:

```bash
# Copy the example file
cp .env.example .env

# Edit with your actual values
nano .env
```

**Required Environment Variables:**

**Confluence Configuration:**
- `CONFLUENCE_BASE_URL`: Your Confluence instance URL (e.g., `https://yourcompany.atlassian.net`)
- `CONFLUENCE_USERNAME`: Your Atlassian account email
- `CONFLUENCE_API_TOKEN`: Token created in step 1
- `CONFLUENCE_SPACE_KEY`: The key of the space to migrate

**Azure DevOps Configuration:**
- `DEVOPS_ORGANIZATION`: Your Azure DevOps organization name (from URL)
- `DEVOPS_PROJECT`: Your project name
- `DEVOPS_WIKI_IDENTIFIER`: Usually `{ProjectName}.wiki`
- `DEVOPS_PAT`: PAT created in step 2

When environment variables are set, the web interface will automatically populate the form fields, and the command-line scripts will use these values by default.

### Manual Configuration

If you prefer not to use environment variables, you can configure the settings manually:

**Confluence Settings:**
- **Base URL**: Your Confluence instance URL (e.g., `https://yourcompany.atlassian.net`)
- **Username**: Your Atlassian account email
- **API Token**: Token created in step 1
- **Space Key**: The key of the space to migrate

**Azure DevOps Settings:**
- **Organization**: Your Azure DevOps organization name (from URL)
- **Project**: Your project name
- **Wiki Identifier**: Usually `{ProjectName}.wiki`
- **Personal Access Token**: PAT created in step 2

## Usage

### Web Interface Method (Recommended)

1. **Start the application**:
   ```bash
   python3 web_ui.py
   ```

2. **Open browser**: Navigate to `http://localhost:5001`

3. **Fill in configuration**:
   - Enter all Confluence and Azure DevOps settings
   - Click "Validate Connections" to test your setup

4. **Run migration**:
   - Click "Start Migration" 
   - Monitor progress in real-time
   - Check logs for detailed information

### Command Line Method

You can also run migrations directly using the Python modules:

```python
from confluence_migration_corrected import ConfluenceToAzureDevOpsHierarchicalMigrator

# Configure your settings
confluence_config = {
    'base_url': 'https://yourcompany.atlassian.net',
    'username': 'your.email@company.com',
    'api_token': 'your_api_token',
    'space_key': 'YOURSPACE'
}

azuredevops_config = {
    'organization': 'yourorg',
    'project': 'YourProject',
    'wiki_identifier': 'YourProject.wiki',
    'personal_access_token': 'your_pat_token'
}

# Run migration
migrator = ConfluenceToAzureDevOpsHierarchicalMigrator(confluence_config, azuredevops_config)
success = migrator.migrate_space_corrected('YOURSPACE')
```

## Troubleshooting

### Common Issues

**"Confluence connection failed"**
- Verify your Confluence URL, username, and API token
- Ensure the space key exists and you have access
- Check if your API token has the required permissions

**"Azure DevOps connection failed"**
- Verify your organization and project names
- Ensure your PAT has Wiki (Read & write) permissions
- Confirm Azure Repos is enabled in your project
- Check that the wiki identifier is correct

**"Wiki repository not found"**
- Ensure Azure Repos is enabled in project settings
- Create a project wiki if one doesn't exist
- Verify the wiki identifier format (`{ProjectName}.wiki`)

**"Permission denied" errors**
- Check PAT scopes include Wiki (Read & write) and Code (Read)
- Verify you have contributor access to the Azure DevOps project
- Ensure you have read access to the Confluence space

### Debug Mode

Run with debug output:
```bash
python3 web_ui.py
```

Check the console output and web interface logs for detailed error information.

### Connection Testing

Use the web interface's "Validate Connections" button to test your configuration before running a full migration.

## Security Notes

- **Never commit credentials**: API tokens and PATs should never be stored in code
- **Token permissions**: Use minimum required scopes for PATs
- **Token rotation**: Regularly rotate your API tokens and PATs
- **Secure storage**: Store tokens in environment variables or secure vaults

## Project Structure

```
confluence-to-azure-devops-wiki/
├── README.md                           # This file
├── requirements.txt                    # Python dependencies
├── web_ui.py                          # Web interface application
├── confluence_migration_corrected.py  # Core migration logic
├── migration_utilities.py             # Utility functions
└── templates/
    └── index.html                     # Web interface template
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is provided as-is for educational and migration purposes. Please review and comply with Atlassian and Microsoft terms of service when using their APIs.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the Azure DevOps and Confluence API documentation
3. Create an issue in this repository with detailed error logs