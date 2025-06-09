#!/usr/bin/env python3
"""
PNG Analysis Search Script
Searches through PNG files based on their stored ANALYSIS metadata using OpenAI.
"""

import argparse
import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
from PIL import Image
from openai import OpenAI
from pydantic import BaseModel
from config import META_TAG_NAME

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, skip loading .env file
    pass


class SearchResults(BaseModel):
    """Pydantic model for OpenAI structured search output"""
    matching_indices: List[int]


def read_analysis_from_png(image_path: Path) -> Optional[Dict[str, Any]]:
    """Read analysis metadata from PNG file"""
    try:
        with Image.open(image_path) as img:
            if hasattr(img, 'text') and img.text and META_TAG_NAME in img.text:
                analysis_json = img.text[META_TAG_NAME]
                return json.loads(analysis_json)
        return None
    except Exception as e:
        if args.verbose:
            print(f"Error reading {image_path.name}: {e}")
        return None


def collect_png_analyses(directory: Path) -> List[Dict[str, Any]]:
    """Collect analysis metadata from all PNG files in directory"""
    analyses = []
    
    png_files = list(directory.glob("*.png"))
    total_files = len(png_files)
    
    if args.verbose:
        print(f"Scanning {total_files} PNG files...")
    
    for png_file in png_files:
        analysis = read_analysis_from_png(png_file)
        if analysis:
            # Add the file path to the analysis data
            analysis['_file_path'] = str(png_file)
            analysis['_file_name'] = png_file.name
            analyses.append(analysis)
            if args.verbose:
                print(f"{png_file.name} - has analysis")
        elif args.verbose:
            print(f"{png_file.name} - no analysis, skipping")
    
    if args.verbose:
        print(f"Found {len(analyses)} PNG files with analysis metadata")
    
    return analyses


def search_analyses_with_openai(analyses: List[Dict[str, Any]], search_prompt: str, client: OpenAI) -> List[str]:
    """Use OpenAI to search through analyses based on prompt with structured output"""
    if not analyses:
        return []
    
    # Prepare the data for OpenAI (remove file paths from the analysis data sent to API)
    analysis_data = []
    file_mapping = {}
    
    for i, analysis in enumerate(analyses):
        # Create a clean analysis without internal fields
        clean_analysis = {k: v for k, v in analysis.items() if not k.startswith('_')}
        analysis_data.append({
            'index': i,
            'analysis': clean_analysis
        })
        file_mapping[i] = {
            'file_path': analysis['_file_path'],
            'file_name': analysis['_file_name']
        }
    
    # Create the system prompt for structured output
    system_prompt = """You are a screenshot search assistant. You will be given:
1. A search query from the user
2. Analysis data from multiple screenshots with index numbers

Your task is to determine which screenshots match the search query based on their analysis data.

You must return a list of indices (numbers) representing the screenshots that match the search criteria. 
The indices correspond to the 'index' field in the analysis data.

Be liberal in your matching - if there's any reasonable connection between the search query and the screenshot content, include it.
If no screenshots match, return an empty list."""

    user_prompt = f"""Search Query: "{search_prompt}"

Screenshot Analysis Data:
{json.dumps(analysis_data, indent=2)}

Return the indices of screenshots that match the search query."""

    try:
        if args.verbose:
            print(f"🤖 Querying OpenAI with {len(analyses)} analyses...")
        
        # Use structured output with Pydantic
        response = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=SearchResults,
            max_tokens=500,
            temperature=0.1
        )
        
        # Extract the parsed result
        search_results = response.choices[0].message.parsed
        matching_indices = search_results.matching_indices
        
        # Convert indices to file paths
        matching_files = []
        for index in matching_indices:
            if index in file_mapping:
                if args.paths:
                    matching_files.append(file_mapping[index]['file_path'])
                else:
                    matching_files.append(file_mapping[index]['file_name'])
        
        return matching_files
        
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return []


def validate_directory(directory_path: Path) -> bool:
    """Validate that the directory exists and is accessible"""
    if not directory_path.exists():
        print(f"Error: Directory does not exist: {directory_path}")
        return False
    
    if not directory_path.is_dir():
        print(f"Error: Path is not a directory: {directory_path}")
        return False
    
    if not os.access(directory_path, os.R_OK):
        print(f"Error: Directory is not readable: {directory_path}")
        return False
    
    return True

def main():
    """Main function"""
    global args
    
    parser = argparse.ArgumentParser(
        description="Search PNG files based on their stored analysis metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dir ~/Desktop/ --prompt "show me screenshots with Terminal"
  %(prog)s --dir ~/Screenshots/ --prompt "find images with code editors" --verbose
  %(prog)s --dir ~/Desktop/ --prompt "screenshots containing error messages"
  
Environment Variables:
  OPENAI_API_KEY    Your OpenAI API key for analysis search
        """
    )
    
    parser.add_argument(
        '--dir',
        required=True,
        help='Directory path to search for PNG files'
    )
    
    parser.add_argument(
        '--prompt',
        required=True,
        help='Search prompt describing what you\'re looking for'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '-p', '--paths',
        action='store_true',
        help='Return full file paths instead of just filenames'
    )
    
    parser.add_argument(
        '--api-key',
        help='OpenAI API key (can also use OPENAI_API_KEY environment variable)'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON array'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='PNG Analysis Search 1.0'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Expand user path and resolve relative paths
    directory_path = Path(args.dir).expanduser().resolve()
    
    # Validate directory
    if not validate_directory(directory_path):
        sys.exit(1)
    
    # Check OpenAI setup
    api_key = args.api_key or os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Error: OpenAI API key required for analysis search.")
        print("   Set OPENAI_API_KEY environment variable or use --api-key flag")
        sys.exit(1)
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Collect analysis data from PNG files
    if args.verbose:
        print(f"Searching directory: {directory_path}")
        print(f"Search prompt: \"{args.prompt}\"")
    
    analyses = collect_png_analyses(directory_path)
    
    if not analyses:
        print("No PNG files with analysis metadata found in directory")
        sys.exit(1)
    
    # Search using OpenAI
    matching_files = search_analyses_with_openai(analyses, args.prompt, client)
    
    # Output results
    if args.json:
        print(json.dumps(matching_files, indent=2))
    else:
        if matching_files:
            if args.verbose:
                print(f"\nFound {len(matching_files)} matching files:")
            for file in matching_files:
                print(f'"{file}"')
        else:
            if args.verbose:
                print("\nNo matching files found")
            else:
                print("No matches found")


if __name__ == "__main__":
    main()

# Installation requirements:
# uv add openai python-dotenv pillow pydantic