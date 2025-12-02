#!/usr/bin/env python3
"""
Corrected Confluence to Azure DevOps Wiki Migration Script
Properly handles Azure DevOps Wiki naming conventions with hyphens instead of spaces
"""

import requests
import os
import re
import json
import base64
from typing import Dict, List, Optional
import time
from datetime import datetime
from bs4 import BeautifulSoup
import glob

# Langflow imports for HTML to Markdown conversion
try:
    from langflow.load import run_flow_from_json as run_flow
except ImportError:
    try:
        from langflow import run_flow_from_json as run_flow
    except ImportError:
        print("⚠️ langflow package not found. Install it with: pip install langflow")
        run_flow = None

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Environment variables loaded from .env file")
except ImportError:
    print("⚠️ python-dotenv not installed. Install with: pip install python-dotenv")
except Exception as e:
    print(f"⚠️ Could not load .env file: {e}")

# Import the new proxy configuration system
from proxy_config import create_proxy_session

# Create a session with proxy configuration
session = create_proxy_session(test_connection=True)

class ConfluenceToAzureDevOpsHierarchicalMigrator:
    def __init__(self, confluence_config: Dict, azuredevops_config: Dict):
        """Initialize migrator with configuration for both systems"""
        self.confluence_config = confluence_config
        self.azuredevops_config = azuredevops_config
        
        # Setup authentication headers
        self.confluence_auth = (confluence_config['username'], confluence_config['api_token'])
        pat_token = azuredevops_config['personal_access_token']
        combined_pat_token = f"this-is-crazy:{pat_token}"
        # Azure DevOps REST APIs expect Bearer token authentication for PATs
        self.azuredevops_headers = {
            'Authorization': f'Basic {base64.b64encode(combined_pat_token.encode('utf-8')).decode("utf-8")}',
            'Content-Type': 'application/json'
        }
        
        # Tracking
        self.url_mapping = {}
        self.downloaded_images = {}
        self.created_folders = set()
        self.wiki_structure = {}
        self.committed_images = set()  # Track committed images to avoid duplicates
        
        # Langflow flow configuration
        self.langflow_flow_path = os.path.join('langflows', 'Migrator 2.0 (0) (openai).json')
        if not os.path.exists(self.langflow_flow_path):
            # Try alternative path
            alt_path = os.path.join(os.path.dirname(__file__), 'langflows', 'Migrator 2.0 (0) (openai).json')
            if os.path.exists(alt_path):
                self.langflow_flow_path = alt_path
            else:
                print(f"⚠️ Langflow flow file not found at {self.langflow_flow_path}")
                print("   HTML to Markdown conversion will fail. Please ensure the flow file exists.")
        
        # Create directories for local storage
        os.makedirs('temp_images', exist_ok=True)
        os.makedirs('processed_pages', exist_ok=True)

    def get_safe_filename_corrected(self, title: str) -> str:
        """Generate Azure DevOps Wiki compliant filename - SPACES TO HYPHENS!"""
        # Replace spaces with hyphens (Azure DevOps Wiki requirement)
        safe_title = title.replace(' ', '-')
        
        # Replace other problematic characters with hyphens
        safe_title = re.sub(r'[<>:"/\\|?*]', '-', safe_title)
        
        # Collapse multiple consecutive hyphens into single hyphen
        safe_title = re.sub(r'-+', '-', safe_title)
        
        # Remove leading and trailing hyphens
        safe_title = safe_title.strip('-')
        
        # Ensure it's not empty
        if not safe_title:
            safe_title = "untitled"
            
        return safe_title


    def get_confluence_pages(self, space_key: str) -> List[Dict]:
        """Get all pages from a Confluence space"""
        pages = []
        start = 0
        limit = 50
        
        try:
            while True:
                base_url = self.confluence_config['base_url'].rstrip('/')
                url = f"{base_url}/wiki/rest/api/content"
                params = {
                    'spaceKey': space_key,
                    'type': 'page',
                    'status': 'current',
                    'expand': 'body.storage,ancestors,children,metadata.labels',
                    'start': start,
                    'limit': limit
                }
                
                print(f"📡 Fetching pages {start}-{start+limit} from Confluence...")
                response = session.get(url, auth=self.confluence_auth, params=params, timeout=30)
                
                if response.status_code != 200:
                    print(f"❌ Confluence API error: {response.status_code} - {response.text}")
                    raise Exception(f"Confluence API failed with status {response.status_code}")
                
                data = response.json()
                batch_count = len(data['results'])
                pages.extend(data['results'])
                print(f"✅ Retrieved {batch_count} pages (total: {len(pages)})")
                
                if batch_count < limit:
                    break
                start += limit
                
        except requests.exceptions.Timeout:
            print(f"⏰ Confluence API timeout after 30 seconds")
            raise Exception("Confluence API timeout")
        except requests.exceptions.RequestException as e:
            print(f"🌐 Confluence API request error: {str(e)}")
            raise Exception(f"Confluence API request failed: {str(e)}")
        except Exception as e:
            print(f"💥 Unexpected error getting pages: {str(e)}")
            raise
            
        print(f"Found {len(pages)} pages in space {space_key}")
        return pages

    def get_hierarchical_wiki_path_corrected(self, title: str, ancestors: List[Dict]) -> str:
        """Generate proper Azure DevOps Wiki folder structure path with HYPHENS"""
        path_parts = []
        
        # Build proper folder hierarchy - Skip EVP root ancestor
        non_evp_ancestors = [a for a in ancestors if a.get('title') != 'EVP']
        
        # Each ancestor becomes a folder in the path
        for ancestor in non_evp_ancestors:
            if ancestor.get('title'):
                safe_ancestor = self.get_safe_filename_corrected(ancestor['title'])
                path_parts.append(safe_ancestor)
        
        # Add current page as the final .md file
        safe_title = self.get_safe_filename_corrected(title)
        path_parts.append(safe_title + '.md')
        
        return '/'.join(path_parts)

    def build_corrected_wiki_structure(self, pages: List[Dict]) -> Dict:
        """Build the corrected wiki structure with proper Azure DevOps naming"""
        print("🔧 Building corrected Azure DevOps Wiki structure...")
        
        # Sort pages by hierarchy level
        pages_by_level = {}
        for page in pages:
            ancestors = page.get('ancestors', [])
            level = len([a for a in ancestors if a.get('title') != 'EVP'])
            
            if level not in pages_by_level:
                pages_by_level[level] = []
            pages_by_level[level].append(page)
        
        print(f"📊 Sorted {len(pages)} pages by {len(pages_by_level)} hierarchy levels")
        
        # Build the complete structure
        wiki_files = {}
        folder_structure = {}
        
        # Process pages level by level
        for level in sorted(pages_by_level.keys()):
            print(f"  📁 Processing Level {level} ({len(pages_by_level[level])} pages)...")
            
            for page in pages_by_level[level]:
                page_title = page['title']
                ancestors = page.get('ancestors', [])
                
                # Generate corrected wiki path
                wiki_path = self.get_hierarchical_wiki_path_corrected(page_title, ancestors)
                
                # Convert content
                html_content = page['body']['storage']['value']
                markdown_content = self.convert_html_to_markdown(html_content, page['id'])
                
                # Store in structure
                wiki_files[wiki_path] = {
                    'content': markdown_content,
                    'page_id': page['id'],
                    'title': page_title,
                    'level': level,
                    'ancestors': ancestors
                }
                
                # Track folders needed
                path_parts = wiki_path.split('/')[:-1]  # Exclude the .md file
                current_path = ""
                
                for part in path_parts:
                    if current_path:
                        current_path += f"/{part}"
                    else:
                        current_path = part
                    
                    if current_path not in folder_structure:
                        folder_structure[current_path] = []
                
                print(f"    ✅ {page_title} → {wiki_path}")
        
        # Create .order files for folders with subpages
        for folder_path in folder_structure:
            # Find pages in this folder
            folder_pages = []
            for wiki_path in wiki_files:
                page_folder = '/'.join(wiki_path.split('/')[:-1])
                if page_folder == folder_path:
                    folder_pages.append(wiki_files[wiki_path])
            
            if folder_pages:
                # Sort pages by some logical order (you can customize this)
                folder_pages.sort(key=lambda x: x['title'])
                
                # Create .order file content
                order_content = '\n'.join([self.get_safe_filename_corrected(p['title']) for p in folder_pages])
                wiki_files[f"{folder_path}/.order"] = {
                    'content': order_content,
                    'is_order_file': True
                }
        
        print(f"📂 Created structure with {len(wiki_files)} files and {len(folder_structure)} folders")
        return wiki_files

    def get_page_attachments(self, page_id: str) -> List[Dict]:
        """Get all attachments for a specific page"""
        try:
            base_url = self.confluence_config['base_url'].rstrip('/')
            url = f"{base_url}/wiki/rest/api/content/{page_id}/child/attachment"
            params = {'expand': 'download'}
            
            response = session.get(url, auth=self.confluence_auth, params=params, timeout=30)
            response.raise_for_status()
            
            return response.json()['results']
        except Exception as e:
            print(f"  ⚠️ Error getting attachments for page {page_id}: {str(e)}")
            return []

    def download_image_safe(self, attachment: Dict, page_id: str) -> Optional[str]:
        """Download image from Confluence with error handling"""
        try:
            # Add /wiki to base URL for image downloads (different from REST API)
            base_url = self.confluence_config['base_url']
            if not base_url.endswith('/wiki'):
                base_url = base_url.rstrip('/') + '/wiki'
            download_url = base_url + attachment['_links']['download']
            filename = attachment['title']
            # Clean filename for Azure DevOps Wiki - handle files without extensions
            if '.' in filename:
                name_part = filename.rsplit('.', 1)[0]
                ext_part = filename.rsplit('.', 1)[1]
                safe_filename = self.get_safe_filename_corrected(name_part) + '.' + ext_part
            else:
                safe_filename = self.get_safe_filename_corrected(filename)
            local_path = f"temp_images/{page_id}_{safe_filename}"
            
            if local_path in self.downloaded_images:
                return self.downloaded_images[local_path]
            
            # Try downloading
            for attempt in range(2):
                try:
                    response = session.get(download_url, auth=self.confluence_auth, timeout=15)
                    response.raise_for_status()
                    
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                    
                    # Calculate and store the correct Azure path immediately
                    filename = os.path.basename(local_path).split('_', 1)[1]  # Remove page_id prefix
                    
                    # Apply same filename transformation as used in markdown
                    if '.' in filename:
                        name_part = filename.rsplit('.', 1)[0]
                        ext_part = filename.rsplit('.', 1)[1]
                        safe_filename = self.get_safe_filename_corrected(name_part) + '.' + ext_part
                    else:
                        safe_filename = self.get_safe_filename_corrected(filename)
                    
                    azure_path = f"/.attachments/{safe_filename}"
                    self.downloaded_images[local_path] = azure_path
                    print(f"  ✅ Downloaded image: {filename}")
                    return local_path
                    
                except requests.exceptions.RequestException:
                    if attempt == 1:
                        print(f"  ❌ Failed to download image: {filename}")
                        return None
                    time.sleep(0.5)
                        
        except Exception as e:
            print(f"  ❌ Error downloading image {attachment.get('title', 'unknown')}: {str(e)}")
            return None

    def process_confluence_images(self, html_content: str, page_id: str) -> str:
        """Process and download Confluence images, replacing with Azure DevOps paths"""
        try:
            # Get page attachments
            attachments = self.get_page_attachments(page_id)
            
            # Use BeautifulSoup to process all images at once
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for attachment in attachments:
                try:
                    filename = attachment['title']
                    if attachment['metadata']['mediaType'].startswith('image/'):
                        # Download image
                        local_path = self.download_image_safe(attachment, page_id)
                        
                        if local_path:
                            # Calculate safe filename (same logic as download_image_safe)
                            if '.' in filename:
                                name_part = filename.rsplit('.', 1)[0]
                                ext_part = filename.rsplit('.', 1)[1]
                                safe_filename = self.get_safe_filename_corrected(name_part) + '.' + ext_part
                            else:
                                safe_filename = self.get_safe_filename_corrected(filename)
                            
                            # Replace Confluence image references with Azure DevOps Wiki markdown syntax
                            # Azure DevOps Wiki requires: ![alt](.attachments/file.ext) format
                            # No subfolders - directly in .attachments/
                            attachment_path = f".attachments/{safe_filename}"
                            
                            # Find all img tags that reference this filename
                            # Check various patterns: direct filename, with page_id path, in URL params
                            img_tags = []
                            seen_tags = set()
                            
                            # Find by direct filename in src
                            for img in soup.find_all('img', src=re.compile(re.escape(filename))):
                                if id(img) not in seen_tags:
                                    img_tags.append(img)
                                    seen_tags.add(id(img))
                            
                            # Find by data-image-src
                            for img in soup.find_all('img', {'data-image-src': re.compile(re.escape(filename))}):
                                if id(img) not in seen_tags:
                                    img_tags.append(img)
                                    seen_tags.add(id(img))
                            
                            # Find by attachments path
                            for img in soup.find_all('img', src=re.compile(re.escape(f'attachments/{page_id}/{filename}'))):
                                if id(img) not in seen_tags:
                                    img_tags.append(img)
                                    seen_tags.add(id(img))
                            
                            # Find by wiki download path
                            for img in soup.find_all('img', src=re.compile(re.escape(f'/wiki/download/attachments/{page_id}/{filename}'))):
                                if id(img) not in seen_tags:
                                    img_tags.append(img)
                                    seen_tags.add(id(img))
                            
                            # Also find ac:image tags with ri:attachment
                            for ac_image in soup.find_all('ac:image'):
                                ri_attachment = ac_image.find('ri:attachment', {'ri:filename': filename})
                                if ri_attachment:
                                    # Extract width/length from ac:image attributes
                                    width = ac_image.get('ac:width') or ac_image.get('ac:thumbnail')
                                    height = ac_image.get('ac:height')
                                    
                                    # Build markdown with dimensions
                                    dimensions = ""
                                    if width and height:
                                        dimensions = f" ={width}x{height}"
                                    elif width:
                                        dimensions = f" ={width}x{width}"
                                    
                                    # Get alt text from ac:image or use safe_filename
                                    alt_text = ac_image.get('ac:alt') or ac_image.get('ac:title') or safe_filename
                                    
                                    markdown_img = f'![{alt_text}]({attachment_path}{dimensions})'
                                    
                                    # Replace the ac:image tag
                                    ac_image.replace_with(markdown_img)
                                    print(f"    📎 Processed image: {filename} → {attachment_path}{dimensions}")
                            
                            # Process img tags
                            for img in img_tags:
                                # Extract width and height attributes
                                width = img.get('width')
                                height = img.get('height')
                                
                                # Also check for width in src URL (e.g., ?width=100)
                                src = img.get('src', '')
                                width_match = re.search(r'[?&]width=(\d+)', src)
                                if width_match and not width:
                                    width = width_match.group(1)
                                
                                # Build markdown with dimensions
                                dimensions = ""
                                if width and height:
                                    dimensions = f" ={width}x{height}"
                                elif width:
                                    dimensions = f" ={width}x{width}"
                                
                                # Get alt text if available, otherwise use safe_filename
                                alt_text = img.get('alt') or img.get('title') or safe_filename
                                
                                markdown_img = f'![{alt_text}]({attachment_path}{dimensions})'
                                
                                # Replace the img tag (or its parent span if it's a wrapper)
                                parent = img.parent
                                if parent and parent.name == 'span' and 'confluence-embedded-file-wrapper' in parent.get('class', []):
                                    parent.replace_with(markdown_img)
                                else:
                                    img.replace_with(markdown_img)
                                
                                print(f"    📎 Processed image: {filename} → {attachment_path}{dimensions}")
                        else:
                            print(f"  ⚠️ Failed to download image: {filename}")
                            
                except Exception as img_error:
                    print(f"  ⚠️ Image processing error for {attachment.get('title', 'unknown')}: {str(img_error)}")
                    continue
            
            return str(soup)
                    
        except Exception as attachment_error:
            print(f"  ⚠️ Attachment processing error: {str(attachment_error)}")
            return html_content

    def check_file_exists_in_azure(self, file_path: str) -> bool:
        """Check if a file already exists in Azure DevOps Git repository"""
        try:
            # Rate limiting - small delay between API calls
            time.sleep(0.1)
            
            # Get current commit ID
            refs_url = f"https://dev.azure.com/{self.azuredevops_config['organization']}/{self.azuredevops_config['project']}/_apis/git/repositories/{self.azuredevops_config['wiki_identifier']}/refs"
            params = {'filter': 'heads/wikiMaster', 'api-version': '6.0'}
            
            response = session.get(refs_url, headers=self.azuredevops_headers, params=params, timeout=30)
            if response.status_code != 200:
                return False
            
            commit_id = response.json()['value'][0]['objectId']
            
            # Check if file exists in the current commit
            items_url = f"https://dev.azure.com/{self.azuredevops_config['organization']}/{self.azuredevops_config['project']}/_apis/git/repositories/{self.azuredevops_config['wiki_identifier']}/items"
            params = {
                'path': file_path,
                'versionDescriptor.version': commit_id,
                'versionDescriptor.versionType': 'commit',
                'api-version': '6.0'
            }
            
            response = session.get(items_url, headers=self.azuredevops_headers, params=params, timeout=30)
            return response.status_code == 200
            
        except Exception as e:
            # If we can't check, assume file doesn't exist to be safe
            print(f"  ⚠️ Unable to check if file exists: {file_path}, assuming it doesn't exist")
            return False

    def process_task_lists(self, html_content: str) -> str:
        """Convert Confluence inline task lists to Markdown checkboxes"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all inline-task-list elements
            task_lists = soup.find_all('ul', class_='inline-task-list')
            
            if not task_lists:
                return html_content
            
            for task_list in task_lists:
                markdown_tasks = []
                
                # Process each task item
                for li in task_list.find_all('li', recursive=False):
                    # Check if task is completed
                    is_checked = False
                    
                    # Check for various indicators of completed tasks
                    task_status = li.get('data-inline-task-status', '').lower()
                    if task_status in ['complete', 'completed', 'done', 'true', '1']:
                        is_checked = True
                    
                    li_classes = [c.lower() for c in li.get('class', [])]
                    if any(keyword in li_classes for keyword in ['checked', 'complete', 'completed', 'done']):
                        is_checked = True
                    
                    # Check for checked checkbox input
                    checkbox_input = li.find('input', type='checkbox')
                    if checkbox_input and checkbox_input.get('checked') is not None:
                        is_checked = True
                    
                    # Extract task text - get text content while preserving links
                    # Clone the li element to avoid modifying the original
                    li_clone = BeautifulSoup(str(li), 'html.parser')
                    # Get text but preserve link structure - links will be converted by Langflow
                    task_text = li_clone.get_text(separator=' ', strip=True)
                    
                    # Use placeholder for checkbox to avoid html2text escaping
                    # We'll replace these after html2text processes the content
                    checkbox_placeholder = '__CHECKBOX_X__' if is_checked else '__CHECKBOX_EMPTY__'
                    markdown_tasks.append(f"{checkbox_placeholder} {task_text}")
                
                # Replace the entire task list with a blockquote containing the markdown checkboxes
                # Use div with br tags to ensure line breaks are preserved
                if markdown_tasks:
                    blockquote_tag = soup.new_tag('blockquote')
                    blockquote_tag['class'] = '__TASK_LIST_MARKER__'
                    
                    # Create a div to hold all tasks with explicit line breaks
                    div_tag = soup.new_tag('div')
                    for i, task in enumerate(markdown_tasks):
                        # Add the task text
                        span_tag = soup.new_tag('span')
                        span_tag.string = task
                        div_tag.append(span_tag)
                        # Add <br> between tasks (except after the last one)
                        if i < len(markdown_tasks) - 1:
                            br_tag = soup.new_tag('br')
                            div_tag.append(br_tag)
                    
                    blockquote_tag.append(div_tag)
                    task_list.replace_with(blockquote_tag)
                    print(f"    ✅ Converted task list with {len(markdown_tasks)} items")
            
            return str(soup)
            
        except Exception as e:
            print(f"  ⚠️ Error processing task lists: {str(e)}")
            return html_content

    def process_tables_newlines(self, html_content: str) -> str:
        """Convert newlines in table cells to <br/> tags"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all tables
            tables = soup.find_all('table')
            
            for table in tables:
                # Find all cells (th and td)
                cells = table.find_all(['th', 'td'])
                
                for cell in cells:
                    # Process all text nodes in the cell
                    from bs4 import NavigableString
                    
                    # Collect text nodes that need processing
                    text_nodes = []
                    for element in cell.descendants:
                        if isinstance(element, NavigableString) and '\n' in element:
                            text_nodes.append(element)
                    
                    # Process each text node
                    for text_node in text_nodes:
                        if '\n' in text_node:
                            parts = text_node.split('\n')
                            parent = text_node.parent
                            
                            # Build replacement: text parts with <br/> between them
                            replacement_parts = []
                            for i, part in enumerate(parts):
                                if part:  # Add non-empty text
                                    replacement_parts.append(NavigableString(part))
                                # Add <br/> between parts
                                if i < len(parts) - 1:
                                    replacement_parts.append(soup.new_tag('br'))
                            
                            # Replace the text node with the new elements
                            if replacement_parts:
                                # Get the index of the text node
                                try:
                                    index = parent.contents.index(text_node)
                                    # Remove the text node
                                    text_node.extract()
                                    # Insert replacement parts at the same position
                                    for j, part in enumerate(replacement_parts):
                                        parent.insert(index + j, part)
                                except (ValueError, AttributeError):
                                    # Fallback: just replace with first part
                                    text_node.replace_with(replacement_parts[0] if replacement_parts else NavigableString(''))
            
            return str(soup)
            
        except Exception as e:
            print(f"  ⚠️ Error processing table newlines: {str(e)}")
            return html_content

    def _stringify_output(self, message: object) -> str:
        """Helper to stringify Langflow output"""
        if message is None:
            return ""
        if isinstance(message, dict):
            return "\n".join(
                f"{key}: {self._stringify_output(value)}" for key, value in message.items()
            )
        if isinstance(message, list):
            return "\n".join(self._stringify_output(item) for item in message)
        return str(message)

    def _extract_markdown_from_run_outputs(self, run_outputs, target_node: str) -> str:
        """Extract markdown from Langflow run outputs"""
        for run_output in run_outputs:
            for result_data in getattr(run_output, "outputs", []) or []:
                if not result_data:
                    continue
                outputs = getattr(result_data, "outputs", {}) or {}
                if target_node in outputs:
                    return self._stringify_output(outputs[target_node].get("message"))
                for output in outputs.values():
                    text = self._stringify_output(output.get("message"))
                    if text:
                        return text
        return ""

    def _run_langflow_migration(self, html_content: str) -> str:
        """Run the Langflow migration flow to convert HTML to Markdown"""
        if run_flow is None:
            raise ImportError("langflow package is not installed. Install it with: pip install langflow")
        
        if not os.path.exists(self.langflow_flow_path):
            raise FileNotFoundError(f"Langflow flow file not found: {self.langflow_flow_path}")
        
        try:
            # Load the flow JSON
            with open(self.langflow_flow_path, "r", encoding="utf-8") as f:
                flow_data = json.load(f)
            
            # Run the flow with HTML content as input
            result = run_flow(
                flow=flow_data,
                input_value=html_content,
                input_type="text",
                output_type="text",
                output_component="TextOutput-AqzAN",
            )
            
            # Extract markdown from the result
            markdown_output = self._extract_markdown_from_run_outputs(result, "TextOutput-AqzAN")
            
            return markdown_output or ""
            
        except Exception as e:
            print(f"  ⚠️ Langflow conversion error: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def convert_html_to_markdown(self, html_content: str, page_id: str) -> str:
        """Convert HTML to Markdown using Langflow (with image processing first)"""
        try:
            # First process images - replace Confluence image references with Azure DevOps paths
            html_content = self.process_confluence_images(html_content, page_id)
            
            # Process tables - convert newlines to <br/> tags (helps preserve table structure)
            html_content = self.process_tables_newlines(html_content)
            
            # Process task lists/checkboxes - convert to markdown-compatible format
            html_content = self.process_task_lists(html_content)
            
            # Use Langflow to convert HTML to Markdown
            print(f"    🤖 Converting HTML to Markdown using Langflow for page {page_id}...")
            markdown_content = self._run_langflow_migration(html_content)
            
            if not markdown_content:
                print(f"    ⚠️ Langflow returned empty markdown for page {page_id}")
                return f"# Content conversion failed\n\nError: Langflow returned empty output"
            
            # Basic cleanup - remove excessive blank lines (but keep single blank lines)
            markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
            
            return markdown_content.strip()
            
        except Exception as e:
            print(f"  ⚠️ HTML conversion error: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"# Content conversion failed\n\nError: {str(e)}"

    def commit_corrected_wiki_structure(self, wiki_files: Dict) -> bool:
        """Commit the corrected structure to Azure DevOps Wiki using Git API"""
        try:
            print("🚀 Committing corrected wiki structure to Azure DevOps...")
            
            # Get latest commit ID
            refs_url = f"https://dev.azure.com/{self.azuredevops_config['organization']}/{self.azuredevops_config['project']}/_apis/git/repositories/{self.azuredevops_config['wiki_identifier']}/refs"
            params = {'filter': 'heads/wikiMaster', 'api-version': '6.0'}
            
            response = session.get(refs_url, headers=self.azuredevops_headers, params=params)
            
            if response.status_code == 200:
                refs_data = response.json()['value']
                if refs_data:
                    old_commit_id = refs_data[0]['objectId']
                else:
                    old_commit_id = "0000000000000000000000000000000000000000"
            else:
                print(f"⚠️ Could not get refs, using empty commit: {response.status_code}")
                old_commit_id = "0000000000000000000000000000000000000000"
            
            # Prepare changes for commit
            changes = []
            
            # Add wiki pages
            for file_path, file_data in wiki_files.items():

                # if unsure if it exist, delete first
                changes.append({
                    "changeType": "delete",
                    "item": {"path": f"/{file_path}"}
                })

                # add file to commit
                changes.append({
                    "changeType": "add",
                    "item": {"path": f"/{file_path}"},
                    "newContent": {
                        "content": file_data['content'],
                        "contentType": "rawtext"
                    }
                })
            
            # Add downloaded images to .attachments folder
            import base64
            for local_path, azure_path in self.downloaded_images.items():
                if os.path.exists(local_path):
                    filename = os.path.basename(local_path).split('_', 1)[1]  # Remove page_id prefix
                    
                    with open(local_path, 'rb') as f:
                        image_content = base64.b64encode(f.read()).decode()
                    
                    # Extract safe filename from azure_path  
                    safe_filename = azure_path.split('/')[-1]
                    if safe_filename not in self.committed_images and not self.check_file_exists_in_azure(azure_path):

                        changes.append({
                            "changeType": "delete",
                            "item": {"path": azure_path}
                        })
                        changes.append({
                            "changeType": "add",
                            "item": {"path": azure_path},
                            "newContent": {
                                "content": image_content,
                                "contentType": "base64encoded"
                            }
                        })
                        self.committed_images.add(safe_filename)
                        print(f"  📎 Adding image to attachments: {filename} → {safe_filename}")
                    else:
                        if safe_filename in self.committed_images:
                            print(f"  ⏭️ Skipping duplicate image (session): {safe_filename}")
                        else:
                            print(f"  ⏭️ Skipping existing image (Azure): {safe_filename}")
            
            # Create the commit
            commits_url = f"https://dev.azure.com/{self.azuredevops_config['organization']}/{self.azuredevops_config['project']}/_apis/git/repositories/{self.azuredevops_config['wiki_identifier']}/pushes"
            
            commit_data = {
                "refUpdates": [{
                    "name": "refs/heads/wikiMaster",
                    "oldObjectId": old_commit_id
                }],
                "commits": [{
                    "comment": "Corrected Azure DevOps Wiki structure - spaces to hyphens",
                    "changes": changes
                }]
            }
            
            commit_response = session.post(
                f"{commits_url}?api-version=6.0",
                headers=self.azuredevops_headers,
                json=commit_data,
                timeout=300
            )
            
            if commit_response.status_code == 201:
                commit_data = commit_response.json()
                new_commit_id = commit_data['commits'][0]['commitId']
                print(f"✅ Successfully committed corrected structure: {new_commit_id}")
                return True
            else:
                print(f"❌ Failed to commit: {commit_response.status_code}")
                print(commit_response.text[:1000])
                return False
                
        except Exception as e:
            print(f"❌ Error committing structure: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def parse_local_html_file(self, html_file_path: str) -> Dict:
        """Parse a local Confluence HTML export file and extract page information"""
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract page ID from file name (e.g., "test_34627.html" -> "34627")
        page_id = os.path.basename(html_file_path).split('_')[-1].replace('.html', '')
        
        # Extract title
        title_elem = soup.find('span', id='title-text')
        if title_elem:
            title = title_elem.get_text().strip()
            # Remove space prefix (e.g., "test : test" -> "test")
            if ':' in title:
                title = title.split(':', 1)[-1].strip()
        else:
            title = page_id
        
        # Extract breadcrumbs (ancestors)
        ancestors = []
        breadcrumbs = soup.find('ol', id='breadcrumbs')
        if breadcrumbs:
            for crumb in breadcrumbs.find_all('li'):
                link = crumb.find('a')
                if link:
                    ancestor_title = link.get_text().strip()
                    ancestors.append({'title': ancestor_title})
        
        # Extract main content
        main_content = soup.find('div', class_='wiki-content')
        if main_content:
            content_html = str(main_content)
        else:
            content_html = ""
        
        return {
            'id': page_id,
            'title': title,
            'ancestors': ancestors,
            'body': {'storage': {'value': content_html}}
        }

    def get_local_pages(self, export_folder: str) -> List[Dict]:
        """Get all pages from a local Confluence export folder"""
        pages = []
        
        # Find all HTML files (excluding index.html)
        html_files = glob.glob(os.path.join(export_folder, '*.html'))
        html_files = [f for f in html_files if not f.endswith('index.html')]
        
        print(f"📁 Found {len(html_files)} HTML files in {export_folder}")
        
        for html_file in html_files:
            try:
                page_data = self.parse_local_html_file(html_file)
                pages.append(page_data)
                print(f"  ✅ Parsed: {page_data['title']} (ID: {page_data['id']})")
            except Exception as e:
                print(f"  ⚠️ Error parsing {html_file}: {str(e)}")
                continue
        
        return pages

    def process_local_images(self, html_content: str, page_id: str, export_folder: str) -> str:
        """Process images from local Confluence export folder"""
        try:
            # First, process base64-encoded images
            html_content = self.process_base64_images(html_content, page_id)
            
            # Find attachments folder for this page
            attachments_folder = os.path.join(export_folder, 'attachments', page_id)
            
            if not os.path.exists(attachments_folder):
                print(f"  ⚠️ No attachments folder found for page {page_id}")
                return html_content
            
            # Get all images in the attachments folder
            image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp', '*.svg']:
                image_files.extend(glob.glob(os.path.join(attachments_folder, ext)))
            
            # Use BeautifulSoup to process images with dimension extraction
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for image_path in image_files:
                filename = os.path.basename(image_path)
                
                # Clean filename for Azure DevOps Wiki
                if '.' in filename:
                    name_part = filename.rsplit('.', 1)[0]
                    ext_part = filename.rsplit('.', 1)[1]
                    safe_filename = self.get_safe_filename_corrected(name_part) + '.' + ext_part
                else:
                    safe_filename = self.get_safe_filename_corrected(filename)
                
                # Copy to temp_images with page_id prefix
                local_path = f"temp_images/{page_id}_{safe_filename}"
                
                # Copy file if not already copied
                if not os.path.exists(local_path):
                    with open(image_path, 'rb') as src:
                        with open(local_path, 'wb') as dst:
                            dst.write(src.read())
                
                # Store Azure path (no subfolders, directly in .attachments/)
                azure_path = f"/.attachments/{safe_filename}"
                self.downloaded_images[local_path] = azure_path
                
                # Replace image references in HTML with markdown
                attachment_path = f".attachments/{safe_filename}"
                
                # Find all img tags that reference this filename
                img_tags = []
                seen_tags = set()
                
                # Find by attachments path
                for img in soup.find_all('img', src=re.compile(re.escape(f'attachments/{page_id}/{filename}'))):
                    if id(img) not in seen_tags:
                        img_tags.append(img)
                        seen_tags.add(id(img))
                
                # Find by data-image-src
                for img in soup.find_all('img', {'data-image-src': re.compile(re.escape(f'attachments/{page_id}/{filename}'))}):
                    if id(img) not in seen_tags:
                        img_tags.append(img)
                        seen_tags.add(id(img))
                
                # Also check for filename in URL parameters
                for img in soup.find_all('img'):
                    src = img.get('src', '')
                    if filename in src and f'attachments/{page_id}' in src:
                        if id(img) not in seen_tags:
                            img_tags.append(img)
                            seen_tags.add(id(img))
                
                # Process each img tag
                for img in img_tags:
                    # Extract width and height attributes
                    width = img.get('width')
                    height = img.get('height')
                    
                    # Also check for width in src URL (e.g., ?width=100)
                    src = img.get('src', '')
                    width_match = re.search(r'[?&]width=(\d+)', src)
                    if width_match and not width:
                        width = width_match.group(1)
                    
                    # Build markdown with dimensions
                    dimensions = ""
                    if width and height:
                        dimensions = f" ={width}x{height}"
                    elif width:
                        dimensions = f" ={width}x{width}"
                    
                    # Get alt text if available, otherwise use safe_filename
                    alt_text = img.get('alt') or img.get('title') or safe_filename
                    
                    markdown_img = f'![{alt_text}]({attachment_path}{dimensions})'
                    
                    # Replace the img tag (or its parent span if it's a wrapper)
                    parent = img.parent
                    if parent and parent.name == 'span' and 'confluence-embedded-file-wrapper' in parent.get('class', []):
                        parent.replace_with(markdown_img)
                    else:
                        img.replace_with(markdown_img)
                    
                    print(f"    📎 Processed local image: {filename} → {attachment_path}{dimensions}")
            
            return str(soup)
            
        except Exception as e:
            print(f"  ⚠️ Error processing local images: {str(e)}")
            return html_content

    def process_base64_images(self, html_content: str, page_id: str) -> str:
        """Detect, decode, and save base64-encoded images from HTML"""
        try:
            # Pattern to match base64-encoded images
            # Matches: data:image/[format];base64,[base64-data]
            base64_pattern = r'data:image/([a-zA-Z]+);base64,([A-Za-z0-9+/=]+)'
            
            matches = re.finditer(base64_pattern, html_content)
            
            image_counter = 0
            for match in matches:
                image_format = match.group(1)  # png, jpeg, jpg, gif, etc.
                base64_data = match.group(2)
                
                # Decode base64 data
                try:
                    image_data = base64.b64decode(base64_data)
                except Exception as decode_error:
                    print(f"  ⚠️ Failed to decode base64 image: {str(decode_error)}")
                    continue
                
                # Generate filename with timestamp postfix
                image_counter += 1
                # Normalize format (jpeg -> jpg)
                if image_format.lower() == 'jpeg':
                    image_format = 'jpg'
                
                # Generate timestamp with microseconds to ensure uniqueness
                # Format: YYYYMMDDHHMMSSffffff (e.g., 20250119143025123456)
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
                
                safe_filename = self.get_safe_filename_corrected(f"base64-image-{timestamp}") + f".{image_format.lower()}"
                
                # Save to temp_images
                local_path = f"temp_images/{page_id}_{safe_filename}"
                
                try:
                    with open(local_path, 'wb') as f:
                        f.write(image_data)
                    
                    # Store Azure path
                    azure_path = f"/.attachments/{safe_filename}"
                    self.downloaded_images[local_path] = azure_path
                    
                    # Replace base64 data with link
                    attachment_path = f".attachments/{safe_filename}"
                    html_content = html_content.replace(match.group(0), attachment_path)
                    
                    print(f"    📎 Decoded base64 image: {safe_filename} ({len(image_data)} bytes)")
                    
                except Exception as save_error:
                    print(f"  ⚠️ Failed to save base64 image: {str(save_error)}")
                    continue
            
            if image_counter > 0:
                print(f"  ✅ Processed {image_counter} base64-encoded images")
            
        except Exception as e:
            print(f"  ⚠️ Error processing base64 images: {str(e)}")
        
        return html_content

    def migrate_from_local_export(self, export_folder: str):
        """Migrate from a local Confluence HTML export folder"""
        print(f"🚀 Starting migration from local export: {export_folder}")
        
        # Validate export folder
        if not os.path.exists(export_folder):
            print(f"❌ Export folder not found: {export_folder}")
            return False
        
        # Get all pages from local export
        print("📡 Reading pages from local export...")
        try:
            pages = self.get_local_pages(export_folder)
            print(f"✅ Successfully parsed {len(pages)} pages from local export")
        except Exception as e:
            print(f"❌ Failed to parse local export: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
        # Build corrected structure
        wiki_structure = self.build_corrected_wiki_structure_from_local(pages, export_folder)
        
        # Commit to Azure DevOps using chunked approach
        success = self.commit_chunked_wiki_structure_fixed(wiki_structure)
        
        if success:
            print("✅ Local export migration completed successfully!")
            print("✅ All spaces replaced with hyphens")
            print("✅ .order files created for proper page sequencing")
            print("✅ Azure DevOps Wiki naming conventions followed")
        else:
            print("❌ Migration failed")
        
        return success

    def build_corrected_wiki_structure_from_local(self, pages: List[Dict], export_folder: str) -> Dict:
        """Build wiki structure from local export pages"""
        print("🔧 Building Azure DevOps Wiki structure from local export...")
        
        # Sort pages by hierarchy level
        pages_by_level = {}
        for page in pages:
            ancestors = page.get('ancestors', [])
            level = len(ancestors)
            
            if level not in pages_by_level:
                pages_by_level[level] = []
            pages_by_level[level].append(page)
        
        print(f"📊 Sorted {len(pages)} pages by {len(pages_by_level)} hierarchy levels")
        
        # Build the complete structure
        wiki_files = {}
        folder_structure = {}
        
        # Process pages level by level
        for level in sorted(pages_by_level.keys()):
            print(f"  📁 Processing Level {level} ({len(pages_by_level[level])} pages)...")
            
            for page in pages_by_level[level]:
                page_title = page['title']
                ancestors = page.get('ancestors', [])
                
                # Generate corrected wiki path
                wiki_path = self.get_hierarchical_wiki_path_corrected(page_title, ancestors)
                
                # Process local images first
                html_content = page['body']['storage']['value']
                html_content = self.process_local_images(html_content, page['id'], export_folder)
                
                # Convert content to markdown
                markdown_content = self.convert_html_to_markdown(html_content, page['id'])
                
                # Store in structure
                wiki_files[wiki_path] = {
                    'content': markdown_content,
                    'page_id': page['id'],
                    'title': page_title,
                    'level': level,
                    'ancestors': ancestors
                }
                
                # Track folders needed
                path_parts = wiki_path.split('/')[:-1]  # Exclude the .md file
                current_path = ""
                
                for part in path_parts:
                    if current_path:
                        current_path += f"/{part}"
                    else:
                        current_path = part
                    
                    if current_path not in folder_structure:
                        folder_structure[current_path] = []
                
                print(f"    ✅ {page_title} → {wiki_path}")
        
        # Create .order files for folders with subpages
        for folder_path in folder_structure:
            # Find pages in this folder
            folder_pages = []
            for wiki_path in wiki_files:
                page_folder = '/'.join(wiki_path.split('/')[:-1])
                if page_folder == folder_path:
                    folder_pages.append(wiki_files[wiki_path])
            
            if folder_pages:
                # Sort pages by title
                folder_pages.sort(key=lambda x: x['title'])
                
                # Create .order file content
                order_content = '\n'.join([self.get_safe_filename_corrected(p['title']) for p in folder_pages])
                wiki_files[f"{folder_path}/.order"] = {
                    'content': order_content,
                    'is_order_file': True
                }
        
        print(f"📂 Created structure with {len(wiki_files)} files and {len(folder_structure)} folders")
        return wiki_files

    def migrate_space_corrected(self, space_key: str):
        """Run the corrected migration"""
        print(f"🚀 Starting CORRECTED hierarchical migration for space: {space_key}")
        
        # Get all pages
        print("📡 Getting pages from Confluence...")
        try:
            pages = self.get_confluence_pages(space_key)
            print(f"✅ Successfully retrieved {len(pages)} pages from Confluence")
        except Exception as e:
            print(f"❌ Failed to get pages from Confluence: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
        # Build corrected structure
        wiki_structure = self.build_corrected_wiki_structure(pages)
        
        # Commit to Azure DevOps using chunked approach (fixed image inclusion)
        success = self.commit_chunked_wiki_structure_fixed(wiki_structure)
        
        if success:
            print("✅ Corrected migration completed successfully!")
            print("✅ All spaces replaced with hyphens")
            print("✅ .order files created for proper page sequencing")
            print("✅ Azure DevOps Wiki naming conventions followed")
        else:
            print("❌ Migration failed")
        
        return success

    def commit_chunked_wiki_structure(self, wiki_files: Dict) -> bool:
        """Commit wiki structure in chunks by hierarchy level to avoid size limits"""
        print("📤 Committing wiki structure using chunked approach...")
        
        # Group pages by hierarchy level based on folder depth
        levels = {}
        for file_path in wiki_files.keys():
            depth = file_path.count('/') 
            if depth not in levels:
                levels[depth] = []
            levels[depth].append(file_path)
        
        print(f"📊 Organized into {len(levels)} hierarchy levels for chunked upload")
        
        try:
            # Get current commit ID for incremental commits
            current_commit_id = self.get_current_commit_id()
            
            # Process each level
            for level_num in sorted(levels.keys()):
                level_files = levels[level_num]
                print(f"📤 Committing Level {level_num} ({len(level_files)} pages)...")
                
                # Prepare changes for this level
                changes = []
                
                # Add wiki pages for this level
                for file_path in level_files:
                    file_data = wiki_files[file_path]

                    changes.append({
                        "changeType": "delete",
                        "item": {"path": f"/{file_path}"}
                    })

                    changes.append({
                        "changeType": "add",
                        "item": {"path": f"/{file_path}"},
                        "newContent": {
                            "content": file_data['content'],
                            "contentType": "rawtext"
                        }
                    })
                
                # Add images used by pages in this level
                level_images = set()
                for file_path in level_files:
                    file_data = wiki_files[file_path]
                    # Extract image references from content (Azure DevOps Wiki format: .attachments/file.ext)
                    import re
                    image_matches = re.findall(r'\.attachments/([^)]+)', file_data['content'])
                    level_images.update(image_matches)
                
                # Add image files to changes
                import base64
                for image_filename in level_images:
                    # Find the local file for this image
                    local_path = None
                    for local_file_path, _ in self.downloaded_images.items():
                        if os.path.exists(local_file_path):
                            local_filename = os.path.basename(local_file_path).split('_', 1)[1]
                            if local_filename == image_filename:
                                local_path = local_file_path
                                break
                    
                    if local_path and os.path.exists(local_path):
                        with open(local_path, 'rb') as f:
                            image_content = base64.b64encode(f.read()).decode()
                        

                        changes.append({
                            "changeType": "delete",
                            "item": {"path": f"/.attachments/{image_filename}"}
                        })

                        changes.append({
                            "changeType": "add",
                            "item": {"path": f"/.attachments/{image_filename}"},
                            "newContent": {
                                "content": image_content,
                                "contentType": "base64encoded"
                            }
                        })
                        print(f"  📎 Including image: {image_filename}")
                    else:
                        print(f"  ⚠️ Local file not found for image: {image_filename}")
                
                if not changes:
                    print(f"  ⚠️ No changes for Level {level_num}, skipping...")
                    continue
                
                # Create commit for this level
                commit_data = {
                    "refUpdates": [
                        {
                            "name": "refs/heads/wikiMaster",
                            "oldObjectId": current_commit_id
                        }
                    ],
                    "commits": [
                        {
                            "comment": f"Migrate Confluence content - Level {level_num} ({len(level_files)} pages, {len([c for c in changes if '/.attachments/' in c['item']['path']])} images)",
                            "changes": changes
                        }
                    ]
                }
                
                # Calculate approximate size
                total_size = sum(len(str(change)) for change in changes)
                print(f"  📏 Estimated commit size: {total_size:,} characters")
                
                # Commit this level
                commit_response = session.post(
                    f"https://dev.azure.com/{self.azuredevops_config['organization']}/{self.azuredevops_config['project']}/_apis/git/repositories/{self.azuredevops_config['wiki_identifier']}/pushes?api-version=6.0",
                    headers=self.azuredevops_headers,
                    json=commit_data,
                    timeout=120
                )
                
                if commit_response.status_code == 201:
                    new_commit_data = commit_response.json()
                    current_commit_id = new_commit_data['commits'][0]['commitId']
                    print(f"  ✅ Level {level_num} committed successfully: {current_commit_id[:8]}...")
                else:
                    print(f"  ❌ Failed to commit Level {level_num}: {commit_response.status_code}")
                    print(f"     Error: {commit_response.text[:500]}")
                    return False
            
            print("✅ All levels committed successfully using chunked approach!")
            return True
            
        except Exception as e:
            print(f"❌ Error in chunked commit: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def commit_chunked_wiki_structure_fixed(self, wiki_files: Dict) -> bool:
        """Fixed chunked commit using size-based batching to avoid 25MB limit"""
        print("📤 Committing wiki structure using SIZE-BASED chunked approach...")
        
        MAX_BATCH_SIZE = 20 * 1024 * 1024  # 20MB to leave buffer under 25MB limit
        
        try:
            # Get current commit ID
            # current_commit_id = self.get_current_commit_id()
            
            # Prepare all files and calculate their sizes
            all_files = []
            total_content_size = 0
            
            # Add all wiki pages
            for file_path, file_data in wiki_files.items():
                content_size = len(file_data['content'].encode('utf-8'))
                all_files.append({
                    'type': 'page',
                    'path': file_path,
                    'content': file_data['content'],
                    'size': content_size
                })
                total_content_size += content_size
            
            # Add all image files (with deduplication and lazy loading to avoid memory issues)
            added_azure_paths = set()
            for local_path, azure_path in self.downloaded_images.items():
                if os.path.exists(local_path) and azure_path not in added_azure_paths:
                    # Get file size without loading content into memory
                    file_size = os.path.getsize(local_path)
                    base64_size = int(file_size * 1.37)  # Base64 encoding overhead ~37%
                    all_files.append({
                        'type': 'image',
                        'path': azure_path,  # Ensure we use Azure path, not local path
                        'local_path': local_path,  # Store local path for lazy loading
                        'content': None,  # Will be loaded when needed
                        'size': base64_size
                    })
                    added_azure_paths.add(azure_path)
                    total_content_size += base64_size
                    print(f"  📎 Queued image for upload: {os.path.basename(local_path).split('_', 1)[1]} → {azure_path}")
                else:
                    if azure_path in added_azure_paths:
                        print(f"  ⏭️ Skipping duplicate image: {azure_path}")
                    else:
                        print(f"  ⚠️ Local file not found: {local_path}")
            
            print(f"📊 Total content: {len([f for f in all_files if f['type'] == 'page'])} pages, {len([f for f in all_files if f['type'] == 'image'])} images")
            print(f"📏 Total size: {total_content_size / (1024*1024):.1f} MB")
            
            # Sort files by size (largest first) to optimize batching
            all_files.sort(key=lambda x: x['size'], reverse=True)
            
            # Create batches based on size
            batches = []
            current_batch = []
            current_batch_size = 0
            
            for file_item in all_files:
                # If this single file exceeds the limit, it needs its own batch
                if file_item['size'] > MAX_BATCH_SIZE:
                    # Finish current batch if it has items
                    if current_batch:
                        batches.append(current_batch)
                        current_batch = []
                        current_batch_size = 0
                    
                    # Add large file as its own batch
                    batches.append([file_item])
                    continue
                
                # If adding this file would exceed the limit, start a new batch
                if current_batch_size + file_item['size'] > MAX_BATCH_SIZE and current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_batch_size = 0
                
                # Add file to current batch
                current_batch.append(file_item)
                current_batch_size += file_item['size']
            
            # Add the last batch
            if current_batch:
                batches.append(current_batch)
            
            print(f"📦 Created {len(batches)} size-optimized batches")
            
            # Commit each batch
            for batch_num, batch in enumerate(batches, 1):
                batch_size = sum(f['size'] for f in batch)
                pages_count = len([f for f in batch if f['type'] == 'page'])
                images_count = len([f for f in batch if f['type'] == 'image'])
                
                print(f"📤 Batch {batch_num}/{len(batches)}: {pages_count} pages, {images_count} images, {batch_size/(1024*1024):.1f} MB")
                print(f"  🔍 Checking which files already exist in Azure DevOps...")
                
                # Check which files already exist and prepare changes only for new files
                add_changes = []
                skipped_pages = 0
                skipped_images = 0
                
                for file_item in batch:
                    file_path = f"/{file_item['path']}"
                    
                    # Check if file already exists in Azure DevOps
                    if self.check_file_exists_in_azure(file_path):
                        if file_item['type'] == 'page':
                            skipped_pages += 1
                            print(f"  ⏭️ Skipping existing page: {file_item['path']}")
                        else:
                            skipped_images += 1
                            print(f"  ⏭️ Skipping existing image: {file_item['path']}")
                        continue
                    
                    # File doesn't exist, add it to changes
                    if file_item['type'] == 'page':
                        add_changes.append({
                            "changeType": "add",
                            "item": {"path": file_path},
                            "newContent": {
                                "content": file_item['content'],
                                "contentType": "rawtext"
                            }
                        })
                        print(f"  ➕ Adding new page: {file_item['path']}")
                    else:  # image - lazy load content now
                        import base64
                        with open(file_item['local_path'], 'rb') as f:
                            image_content = base64.b64encode(f.read()).decode()

                        add_changes.append({
                            "changeType": "add",
                            "item": {"path": file_path},
                            "newContent": {
                                "content": image_content,
                                "contentType": "base64encoded"
                            }
                        })
                        print(f"  ➕ Adding new image: {file_item['path']}")
                
                # If no changes needed, skip this batch
                if not add_changes:
                    print(f"  ⏭️ Batch {batch_num} skipped - all files already exist")
                    continue
                
                actual_pages = len([c for c in add_changes if c['item']['path'].endswith('.md') or c['item']['path'].endswith('.order')])
                actual_images = len([c for c in add_changes if '/.attachments/' in c['item']['path']])
                
                print(f"  📊 Adding {actual_pages} new pages, {actual_images} new images (skipped {skipped_pages} pages, {skipped_images} images)")

                # Prepare add commit data
                add_commit_data = {
                    "refUpdates": [
                        {
                            "name": "refs/heads/wikiMaster",
                            "oldObjectId": self.get_current_commit_id()
                        }
                    ],
                    "commits": [
                        {
                            "comment": f"Confluence migration - Batch {batch_num}/{len(batches)} ({actual_pages} new pages, {actual_images} new images)",
                            "changes": add_changes
                        }
                    ]
                }
                
                # Commit this batch
                commit_response = session.post(
                    f"https://dev.azure.com/{self.azuredevops_config['organization']}/{self.azuredevops_config['project']}/_apis/git/repositories/{self.azuredevops_config['wiki_identifier']}/pushes?api-version=6.0",
                    headers=self.azuredevops_headers,
                    json=add_commit_data,
                    timeout=300  # Increase timeout for large batches
                )
                
                if commit_response.status_code == 201:
                    new_commit_data = commit_response.json()
                    current_commit_id = new_commit_data['commits'][0]['commitId']
                    print(f"  ✅ Batch {batch_num} committed: {current_commit_id[:8]}...")
                    
                    # Rate limiting - delay between batch commits
                    if batch_num < len(batches):
                        time.sleep(1)
                else:
                    print(f"  ❌ Batch {batch_num} failed: {commit_response.status_code}")
                    print(f"     Error: {commit_response.text[:500]}")
                    return False
            
            print("✅ All batches committed successfully using size-based approach!")
            return True
            
        except Exception as e:
            print(f"❌ Error in size-based chunked commit: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def get_current_commit_id(self) -> str:
        """Get the current commit ID for the wikiMaster branch"""
        try:
            refs_url = f"https://dev.azure.com/{self.azuredevops_config['organization']}/{self.azuredevops_config['project']}/_apis/git/repositories/{self.azuredevops_config['wiki_identifier']}/refs"
            params = {'filter': 'heads/wikiMaster', 'api-version': '6.0'}
            
            response = session.get(refs_url, headers=self.azuredevops_headers, params=params)
            
            if response.status_code == 200:
                refs_data = response.json()['value']
                if refs_data:
                    return refs_data[0]['objectId']
                else:
                    # No wikiMaster branch exists yet, return zero commit ID
                    return "0000000000000000000000000000000000000000"
            else:
                print(f"⚠️ Could not get current commit ID: {response.status_code}")
                return "0000000000000000000000000000000000000000"
                
        except Exception as e:
            print(f"⚠️ Error getting current commit ID: {str(e)}")
            return "0000000000000000000000000000000000000000"


# Example usage
if __name__ == "__main__":
    # Try to load configuration from environment variables first
    confluence_config = {
        "base_url": os.getenv('CONFLUENCE_BASE_URL', "https://yourcompany.atlassian.net"),
        "username": os.getenv('CONFLUENCE_USERNAME', "your.email@company.com"), 
        "api_token": os.getenv('CONFLUENCE_API_TOKEN', "YOUR_TOKEN_HERE")
    }
    
    azuredevops_config = {
        "organization": os.getenv('DEVOPS_ORGANIZATION', "YourOrganization"),
        "project": os.getenv('DEVOPS_PROJECT', "YourProject"),
        "wiki_identifier": os.getenv('DEVOPS_WIKI_IDENTIFIER', "YourProject.wiki"),
        "personal_access_token": os.getenv('DEVOPS_PAT', "YOUR_TOKEN_HERE")
    }
    
    space_key = os.getenv('CONFLUENCE_SPACE_KEY', "YOUR_SPACE_KEY")
    
    # Check for offline mode
    offline_mode = os.getenv('OFFLINE_MODE', 'false').lower() == 'true'
    export_folder = os.getenv('EXPORT_FOLDER', 'TEST')
    
    # Check if we have environment variables loaded
    env_vars_loaded = all([
        azuredevops_config["organization"] != "YourOrganization",
        azuredevops_config["project"] != "YourProject",
        azuredevops_config["wiki_identifier"] != "YourProject.wiki",
        azuredevops_config["personal_access_token"] != "YOUR_TOKEN_HERE"
    ])
    
    if offline_mode:
        print("✅ Running in OFFLINE mode - reading from local export folder")
        print(f"📁 Export folder: {export_folder}")
        
        if not env_vars_loaded:
            print("⚠️ Azure DevOps configuration missing. Please set environment variables.")
            print("Required environment variables:")
            print("  DEVOPS_ORGANIZATION, DEVOPS_PROJECT, DEVOPS_WIKI_IDENTIFIER, DEVOPS_PAT")
            print("  OFFLINE_MODE=true, EXPORT_FOLDER=<path_to_export>")
        
        migrator = ConfluenceToAzureDevOpsHierarchicalMigrator(confluence_config, azuredevops_config)
        success = migrator.migrate_from_local_export(export_folder)
        print(f"Migration success: {success}")
    else:
        # Online mode - fetch from Confluence API
        online_vars_loaded = env_vars_loaded and all([
            confluence_config["base_url"] != "https://yourcompany.atlassian.net",
            confluence_config["username"] != "your.email@company.com",
            confluence_config["api_token"] != "YOUR_TOKEN_HERE",
            space_key != "YOUR_SPACE_KEY"
        ])
        
        if online_vars_loaded:
            print("✅ Using configuration from environment variables")
        else:
            print("⚠️ Using default configuration. Please set environment variables or update the script.")
            print("Required environment variables:")
            print("  CONFLUENCE_BASE_URL, CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN, CONFLUENCE_SPACE_KEY")
            print("  DEVOPS_ORGANIZATION, DEVOPS_PROJECT, DEVOPS_WIKI_IDENTIFIER, DEVOPS_PAT")
            print("Optional for offline mode:")
            print("  OFFLINE_MODE=true, EXPORT_FOLDER=<path_to_export>")
        
        migrator = ConfluenceToAzureDevOpsHierarchicalMigrator(confluence_config, azuredevops_config)
        success = migrator.migrate_space_corrected(space_key)
        print(f"Migration success: {success}")
