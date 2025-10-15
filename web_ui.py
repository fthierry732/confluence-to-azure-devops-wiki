#!/usr/bin/env python3
"""
Web UI for Confluence to Azure DevOps Migration Tool
Provides a simple web interface to configure and run migrations
"""

from flask import Flask, render_template, request, jsonify
import os
import sys
import threading
# from confluence_migration_fixed import ConfluenceToAzureDevOpsMigrator as FlatMigrator
from migration_utilities import MigrationUtilities, load_config_from_env, get_config_with_env_fallback
import importlib
import sys

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Environment variables loaded from .env file")
except ImportError:
    print("⚠️ python-dotenv not installed. Install with: pip install python-dotenv")
except Exception as e:
    print(f"⚠️ Could not load .env file: {e}")

# Force reload the corrected migration module to avoid caching
if 'confluence_migration_corrected' in sys.modules:
    importlib.reload(sys.modules['confluence_migration_corrected'])
from confluence_migration_corrected import ConfluenceToAzureDevOpsHierarchicalMigrator as HierarchicalMigrator

app = Flask(__name__)

class MigrationWebUI:
    def __init__(self):
        self.migration_status = {
            'running': False,
            'progress': 0,
            'message': '',
            'completed': False
        }
        self.migration_logs = []

    def create_config_from_form(self, form_data):
        """Create configuration dictionaries from form data with environment variable fallback"""
        # Try to load from environment variables first
        env_confluence, env_azuredevops = load_config_from_env()
        
        # Use form data if provided, otherwise fall back to environment variables
        confluence_config = {
            'base_url': form_data.get('confluence_base_url') or (env_confluence.get('base_url') if env_confluence else None),
            'username': form_data.get('confluence_username') or (env_confluence.get('username') if env_confluence else None),
            'api_token': form_data.get('confluence_api_token') or (env_confluence.get('api_token') if env_confluence else None),
            'space_key': form_data.get('confluence_space_key') or (env_confluence.get('space_key') if env_confluence else None)
        }
        
        azuredevops_config = {
            'organization': form_data.get('azuredevops_organization') or (env_azuredevops.get('organization') if env_azuredevops else None),
            'project': form_data.get('azuredevops_project') or (env_azuredevops.get('project') if env_azuredevops else None),
            'wiki_identifier': form_data.get('azuredevops_wiki_identifier') or (env_azuredevops.get('wiki_identifier') if env_azuredevops else None),
            'personal_access_token': form_data.get('azuredevops_pat') or (env_azuredevops.get('personal_access_token') if env_azuredevops else None)
        }
        
        return confluence_config, azuredevops_config

    def validate_connections(self, confluence_config, azuredevops_config):
        """Validate both Confluence and Azure DevOps connections"""
        try:
            utils = MigrationUtilities(confluence_config, azuredevops_config)
            
            # Validate Confluence connection
            confluence_ok = utils.validate_confluence_connection(confluence_config['space_key'])
            if not confluence_ok:
                return False, "Confluence connection failed. Check your credentials and space key."
            
            # Validate Azure DevOps connection
            azuredevops_ok = utils.validate_azure_devops_connection()
            if not azuredevops_ok:
                return False, "Azure DevOps connection failed. Check your organization, project, wiki, and PAT."
            
            return True, "All connections validated successfully"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def log_message(self, message):
        """Add a message to the migration logs"""
        self.migration_logs.append(message + '\n')
        print(message)  # Also print to console for debugging

    def run_migration_async(self, confluence_config, azuredevops_config, migration_type='hierarchical'):
        """Run migration in a separate thread"""
        
        try:
            self.migration_status['running'] = True
            self.migration_status['completed'] = False
            self.migration_status['message'] = f'Starting {migration_type} migration...'
            self.migration_logs = [f'Starting {migration_type} migration...\n']
            
            self.log_message(f'Initializing {migration_type} migrator...')
            
            # Choose the appropriate migrator based on migration type
            try:
                # Only hierarchical migration is available
                migrator = HierarchicalMigrator(confluence_config, azuredevops_config)
                self.log_message('Hierarchical migrator created successfully')
            except Exception as e:
                self.log_message(f'ERROR creating migrator: {str(e)}')
                raise
                
            self.log_message('Starting space migration...')
            
            # Run the migration without stdout capture - let it print directly
            try:
                success = migrator.migrate_space_corrected(confluence_config['space_key'])
                
                if success:
                    self.log_message('Space migration completed successfully')
                else:
                    self.log_message('Space migration failed')
                    raise Exception("Migration returned False")
                    
            except Exception as e:
                self.log_message(f'ERROR during migration: {str(e)}')
                raise
                
            self.migration_status['running'] = False
            self.migration_status['completed'] = True
            self.migration_status['message'] = f'{migration_type.title()} migration completed successfully'
            self.log_message('Migration finished successfully!')
            
        except Exception as e:
            self.migration_status['running'] = False
            self.migration_status['completed'] = False
            self.migration_status['message'] = f'Migration failed: {str(e)}'
            self.log_message(f'MIGRATION FAILED: {str(e)}')
            import traceback
            self.log_message(f'Full error traceback: {traceback.format_exc()}')

web_ui = MigrationWebUI()

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/config', methods=['GET'])
def get_config():
    """Get current configuration including environment variables"""
    try:
        # Try to load from environment variables
        env_confluence, env_azuredevops = load_config_from_env()
        
        config = {
            'confluence': {
                'base_url': env_confluence.get('base_url') if env_confluence else '',
                'username': env_confluence.get('username') if env_confluence else '',
                'api_token': env_confluence.get('api_token') if env_confluence else '',
                'space_key': env_confluence.get('space_key') if env_confluence else ''
            },
            'azuredevops': {
                'organization': env_azuredevops.get('organization') if env_azuredevops else '',
                'project': env_azuredevops.get('project') if env_azuredevops else '',
                'wiki_identifier': env_azuredevops.get('wiki_identifier') if env_azuredevops else '',
                'pat': env_azuredevops.get('personal_access_token') if env_azuredevops else ''
            },
            'has_env_config': env_confluence is not None and env_azuredevops is not None
        }
        
        return jsonify({
            'success': True,
            'config': config
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/validate', methods=['POST'])
def validate():
    """Validate connections endpoint"""
    try:
        form_data = request.json
        confluence_config, azuredevops_config = web_ui.create_config_from_form(form_data)
        
        success, message = web_ui.validate_connections(confluence_config, azuredevops_config)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/preview', methods=['POST'])
def preview():
    """Generate migration preview"""
    try:
        form_data = request.json
        confluence_config, azuredevops_config = web_ui.create_config_from_form(form_data)
        
        utils = MigrationUtilities(confluence_config, azuredevops_config)
        preview_data = utils.preview_migration(confluence_config['space_key'])
        
        return jsonify({
            'success': True,
            'preview': preview_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/migrate', methods=['POST'])
def migrate():
    """Start migration process"""
    try:
        if web_ui.migration_status['running']:
            return jsonify({
                'success': False,
                'message': 'Migration is already running'
            }), 400
        
        form_data = request.json
        migration_type = form_data.get('migration_type', 'hierarchical')
        print(f"📝 Received {migration_type} migration request: {form_data.get('confluence_space_key', 'Unknown space')}")
        
        confluence_config, azuredevops_config = web_ui.create_config_from_form(form_data)
        print(f"🔧 Configs created successfully")
        
        # Start migration in background thread
        migration_thread = threading.Thread(
            target=web_ui.run_migration_async,
            args=(confluence_config, azuredevops_config, migration_type),
            name=f"Migration-{migration_type}-Thread"
        )
        migration_thread.start()
        
        print(f"🚀 Migration thread started")
        
        return jsonify({
            'success': True,
            'message': 'Migration started successfully'
        })
        
    except Exception as e:
        print(f"❌ Migration error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/status', methods=['GET'])
def status():
    """Get migration status"""
    return jsonify(web_ui.migration_status)

@app.route('/progress', methods=['GET'])
def progress():
    """Get migration progress and logs"""
    return jsonify({
        'running': web_ui.migration_status['running'],
        'completed': web_ui.migration_status['completed'],
        'success': web_ui.migration_status['completed'] and not web_ui.migration_status.get('failed', False),
        'message': web_ui.migration_status['message'],
        'logs': ''.join(web_ui.migration_logs)
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("Starting Confluence to Azure DevOps Migration Web UI...")
    print("Access the web interface at: http://localhost:5001")
    print("Press Ctrl+C to stop the server")
    
    # Ensure templates directory exists
    if not os.path.exists('templates'):
        print("Error: templates directory not found!")
        print("Please make sure the templates/index.html file exists.")
        sys.exit(1)
    
    app.run(debug=True, host='0.0.0.0', port=5001)