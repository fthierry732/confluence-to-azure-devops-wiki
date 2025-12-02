#!/usr/bin/env python3
"""
Simple script to run the Langflow migration flow.
Converts Confluence HTML to Azure DevOps Markdown.
"""

import json
import sys
from pathlib import Path

try:
    from langflow.load import run_flow_from_json as run_flow
except ImportError:
    try:
        from langflow import run_flow_from_json as run_flow
    except ImportError:
        print("Error: langflow package not found. Install it with: pip install langflow")
        sys.exit(1)


def _stringify_output(message: object) -> str:
    if message is None:
        return ""
    if isinstance(message, dict):
        return "\n".join(
            f"{key}: {_stringify_output(value)}" for key, value in message.items()
        )
    if isinstance(message, list):
        return "\n".join(_stringify_output(item) for item in message)
    return str(message)


def _extract_markdown_from_run_outputs(run_outputs, target_node: str) -> str:
    for run_output in run_outputs:
        for result_data in getattr(run_output, "outputs", []) or []:
            if not result_data:
                continue
            outputs = getattr(result_data, "outputs", {}) or {}
            if target_node in outputs:
                return _stringify_output(outputs[target_node].get("message"))
            for output in outputs.values():
                text = _stringify_output(output.get("message"))
                if text:
                    return text
    return ""


def run_migration(html_content: str, flow_path: str = "Migrator 2.0 (0) (openai).json") -> str:
    """
    Run the migration flow with the provided HTML content.
    
    Args:
        html_content: The HTML content to convert
        flow_path: Path to the Langflow JSON file
        
    Returns:
        The converted Markdown content
    """
    # Load the flow
    flow_file = Path(flow_path)
    if not flow_file.exists():
        raise FileNotFoundError(f"Flow file not found: {flow_path}")

    with open(flow_file, "r", encoding="utf-8") as f:
        flow_data = json.load(f)

    result = run_flow(
        flow=flow_data,
        input_value=html_content,
        input_type="text",
        output_type="text",
        output_component="TextOutput-AqzAN",
    )

    flow_output = _extract_markdown_from_run_outputs(result, "TextOutput-AqzAN")
    
    return flow_output or ""


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python migration_script.py <html_file> [flow_json_file]")
        print("\nExample:")
        print("  python migration_script.py input.html")
        print("  python migration_script.py input.html 'Migrator 2.0 (0) (openai).json'")
        sys.exit(1)
    
    html_file = sys.argv[1]
    flow_file = sys.argv[2] if len(sys.argv) > 2 else "Migrator 2.0 (0) (openai).json"
    
    # Read HTML content
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"Error: HTML file not found: {html_file}")
        sys.exit(1)
    
    # Run migration
    print(f"Running migration on {html_file}...")
    try:
        markdown_result = run_migration(html_content, flow_file)
        
        # Output to stdout
        print("\n" + "="*80)
        print("MIGRATION RESULT:")
        print("="*80 + "\n")
        print(markdown_result)
        
        # Also save to file
        output_file = Path(html_file).stem + "_converted.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_result)
        print(f"\n✓ Result also saved to: {output_file}")
        
    except Exception as e:
        print(f"Error running migration: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()