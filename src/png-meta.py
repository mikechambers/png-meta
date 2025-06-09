#!/usr/bin/env python3
"""
PNG Directory Watcher - Updated Version
Watches a directory for new PNG files and analyzes them with OpenAI.
"""

import argparse
import os
import sys
import time
import json
import base64
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Set, Literal
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from openai import OpenAI
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from pydantic import BaseModel
from config import META_TAG_NAME

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, skip loading .env file
    pass


class ScreenshotAnalysisModel(BaseModel):
    """Pydantic model for OpenAI structured output"""
    title: str
    short_description: str
    long_description: str
    ai_description: str
    explicit_content: bool
    embedded_text: str
    apps: List[str]
    type: Literal["screenshot", "photography", "graphic"]


@dataclass
class ScreenshotAnalysis:
    """Data class for screenshot analysis results"""
    title: str
    short_description: str
    long_description: str
    ai_description: str
    explicit_content: bool
    embedded_text: str
    apps: List[str]
    type: str
    filename: str
    file_path: str
    
    @classmethod
    def from_pydantic_model(cls, model: ScreenshotAnalysisModel, image_path: Path) -> 'ScreenshotAnalysis':
        """Create ScreenshotAnalysis from Pydantic model"""
        return cls(
            title=model.title,
            short_description=model.short_description,
            long_description=model.long_description,
            ai_description=model.ai_description,
            explicit_content=model.explicit_content,
            embedded_text=model.embedded_text,
            apps=model.apps,
            type=model.type,
            filename=image_path.name,
            file_path=str(image_path)
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'title': self.title,
            'short_description': self.short_description,
            'long_description': self.long_description,
            'ai_description': self.ai_description,
            'explicit_content': self.explicit_content,
            'embedded_text': self.embedded_text,
            'apps': self.apps,
            'type': self.type,
            'filename': self.filename,
            'file_path': self.file_path
        }
    
    def to_metadata_dict(self) -> dict:
        """Convert to dictionary for metadata storage (excludes filename and file_path)"""
        return {
            'title': self.title,
            'short_description': self.short_description,
            'long_description': self.long_description,
            'ai_description': self.ai_description,
            'explicit_content': self.explicit_content,
            'embedded_text': self.embedded_text,
            'apps': self.apps,
            'type': self.type
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    def to_metadata_json(self) -> str:
        """Convert to JSON string for metadata storage (excludes filename and file_path)"""
        return json.dumps(self.to_metadata_dict(), indent=2)


# Global state
known_files: Set[str] = set()
openai_client: Optional[OpenAI] = None
verbose_mode: bool = False
analyze_mode: bool = False


def setup_openai_client(api_key: Optional[str] = None) -> OpenAI:
    """Initialize OpenAI client"""
    global openai_client
    openai_client = OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
    return openai_client


def encode_image(image_path: Path) -> str:
    """Encode image to base64 string"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def analyze_screenshot(image_path: Path) -> ScreenshotAnalysis:
    """Analyze screenshot using OpenAI Vision API with structured output"""
    global openai_client
    
    try:
        # Encode the image
        base64_image = encode_image(image_path)
        
        # Create the system prompt
        system_prompt = """Analyze this image and provide detailed information:

**title**: A concise, descriptive title for the image (3-8 words)
**short_description**: A brief one-sentence description (under 100 characters)
**long_description**: A detailed description of what's shown in the image (2-4 sentences)
**ai_description**: Technical analysis to use to describe to AI including visual elements, composition, colors, style, etc. (2-3 sentences)
**explicit_content**: Boolean - true if image contains adult/explicit content, false otherwise
**embedded_text**: Extract ALL readable text from the image, preserving structure when possible (include UI elements, buttons, menus, document content, code, etc.)
**apps**: List of application names, window titles, or software interfaces visible in the image
**type**: Classify as one of:
  - "screenshot": Computer/mobile screen capture, UI elements, applications
  - "photography": Real-world photos, camera captures, people, places, objects
  - "graphic": Digital art, illustrations, logos, designs, charts, diagrams

Be thorough in text extraction and accurate in classification."""
        
        # Make API call with structured output
        response = openai_client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please analyze this image:"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            response_format=ScreenshotAnalysisModel,
            max_tokens=1500,
            temperature=0.1
        )
        
        # Extract the parsed result
        analysis_model = response.choices[0].message.parsed
        
        # Convert to ScreenshotAnalysis dataclass
        return ScreenshotAnalysis.from_pydantic_model(analysis_model, image_path)
        
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return create_error_analysis(image_path, f"API error: {e}")


def create_error_analysis(image_path: Path, error_msg: str) -> ScreenshotAnalysis:
    """Create an error analysis object"""
    return ScreenshotAnalysis(
        title="Analysis Error",
        short_description=f"Error analyzing image: {error_msg}",
        long_description=f"An error occurred while processing this image: {error_msg}",
        ai_description="Unable to perform AI analysis due to an error.",
        explicit_content=False,
        embedded_text="",
        apps=[],
        type="screenshot",
        filename=image_path.name,
        file_path=str(image_path)
    )


def store_analysis_in_png(image_path: Path, analysis: ScreenshotAnalysis) -> bool:
    """Store analysis results as metadata in the PNG file"""
    try:
        # Open the original image
        with Image.open(image_path) as img:
            # Create new metadata
            metadata = PngInfo()
            
            # Store the analysis as JSON (excluding filename and file_path)
            analysis_json = analysis.to_metadata_json()
            metadata.add_text(META_TAG_NAME, analysis_json)
            
            # Copy any existing metadata (except our analysis field)
            if hasattr(img, 'text') and img.text:
                for key, value in img.text.items():
                    if key != META_TAG_NAME:
                        metadata.add_text(key, value)
            
            # Save with metadata (overwrite original)
            img.save(image_path, "PNG", pnginfo=metadata)
            
            return True
            
    except Exception as e:
        print(f"Error storing metadata in PNG: {e}")
        return False


def has_analysis_metadata(image_path: Path) -> bool:
    """Check if PNG file already has analysis metadata"""
    try:
        with Image.open(image_path) as img:
            if hasattr(img, 'text') and img.text:
                return META_TAG_NAME in img.text
        return False
    except Exception as e:
        if verbose_mode:
            print(f"Error checking metadata for {image_path.name}: {e}")
        return False


def scan_and_analyze_directory(directory: Path):
    """Scan directory for PNG files and analyze those without metadata"""
    global verbose_mode
    
    png_files = list(directory.glob("*.png"))
    total_files = len(png_files)
    
    print(f"Scanning {total_files} PNG files in: {directory}")
    
    files_to_analyze = []
    files_with_metadata = 0
    
    # First pass: check which files need analysis
    for png_file in png_files:
        if has_analysis_metadata(png_file):
            files_with_metadata += 1
            if verbose_mode:
                print(f"{png_file.name} - already has analysis metadata")
        else:
            files_to_analyze.append(png_file)
            if verbose_mode:
                print(f"{png_file.name} - needs analysis")
    
    print(f"Summary: {files_with_metadata} files already analyzed, {len(files_to_analyze)} files need analysis")
    
    if not files_to_analyze:
        print("All PNG files already have analysis metadata!")
        return
    
    # Second pass: analyze files that need it
    print(f"\nStarting analysis of {len(files_to_analyze)} files...")
    
    for i, png_file in enumerate(files_to_analyze, 1):
        print(f"\n[{i}/{len(files_to_analyze)}] Analyzing: {png_file.name}")
        
        try:
            # Analyze the screenshot
            analysis = analyze_screenshot(png_file)
            
            if verbose_mode:
                display_analysis(analysis)
            else:
                # Show brief results in non-verbose mode
                print(f"{analysis.title}")
                print(f"{analysis.short_description}")
                print(f"Type: {analysis.type}")
                print(f"Apps: {', '.join(analysis.apps) if analysis.apps else 'None detected'}")
            
            # Store analysis in PNG metadata
            print(f"Storing analysis in PNG metadata...")
            success = store_analysis_in_png(png_file, analysis)
            if success:
                print(f"Analysis saved to PNG metadata")
            else:
                print(f"Failed to save analysis to PNG metadata")
                
        except Exception as e:
            print(f"Error analyzing {png_file.name}: {e}")
            continue
    
    print(f"\nScan complete! Analyzed {len(files_to_analyze)} PNG files.")


def scan_existing_files(watch_dir: Path):
    """Scan for existing PNG files to avoid duplicates on startup"""
    global known_files, verbose_mode
    
    try:
        for file_path in watch_dir.glob("*.png"):
            if file_path.is_file():
                known_files.add(file_path.name.lower())
        if verbose_mode:
            print(f"Found {len(known_files)} existing PNG files")
    except Exception as e:
        if verbose_mode:
            print(f"Warning: Could not scan existing files: {e}")


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    if size_bytes == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def display_analysis(analysis: ScreenshotAnalysis):
    """Display the analysis results"""
    global verbose_mode
    
    print(f"Analysis Results:")
    print(f"    Title: {analysis.title}")
    print(f"    Short: {analysis.short_description}")
    print(f"    Long: {analysis.long_description}")
    print(f"    AI: {analysis.ai_description}")
    print(f"    Type: {analysis.type}")
    print(f"    Explicit: {'Yes' if analysis.explicit_content else 'No'}")
    print(f"    Apps: {', '.join(analysis.apps) if analysis.apps else 'None detected'}")
    
    if analysis.embedded_text:
        # Truncate long text for display
        text_preview = analysis.embedded_text[:200] + "..." if len(analysis.embedded_text) > 200 else analysis.embedded_text
        print(f"    Text: {text_preview}")
    else:
        print(f"    Text: None detected")
    
    if verbose_mode:
        print(f"Full JSON:")
        print(f"      {analysis.to_json()}")


def handle_new_png(file_path: Path, event_type: str):
    """Process a new PNG file"""
    global known_files, verbose_mode, analyze_mode
    
    filename_lower = file_path.name.lower()
    
    # Check if it's actually a new file
    if filename_lower not in known_files:
        # Verify the file actually exists and is readable
        if file_path.exists() and file_path.is_file():
            # Add a small delay to ensure file is fully written
            time.sleep(0.1)
            
            try:
                # Try to get file size to confirm it's accessible
                file_size = file_path.stat().st_size
                
                # Print the filename
                print(f"New PNG: {file_path.name}")
                
                if verbose_mode:
                    print(f"Path: {file_path}")
                    print(f"Size: {format_file_size(file_size)}")
                    print(f"Event: {event_type}")
                
                # Analyze with OpenAI if enabled
                if analyze_mode:
                    print(f"Analyzing PNG with OpenAI...")
                    analysis = analyze_screenshot(file_path)
                    display_analysis(analysis)
                    
                    # Store analysis in PNG metadata
                    print(f"Storing analysis in PNG metadata...")
                    success = store_analysis_in_png(file_path, analysis)
                    if success:
                        print(f"Analysis saved to PNG metadata")
                    else:
                        print(f"Failed to save analysis to PNG metadata")
                
                # Add to known files
                known_files.add(filename_lower)
                
            except (OSError, PermissionError) as e:
                if verbose_mode:
                    print(f"Could not access {file_path.name}: {e}")


class SimpleFileHandler(FileSystemEventHandler):
    """Simple file system event handler"""
    
    def on_created(self, event):
        """Handle file creation events"""
        if not event.is_directory:
            self._handle_file_event(event.src_path, "created")
    
    def on_moved(self, event):
        """Handle file move events (includes renames)"""
        if not event.is_directory:
            self._handle_file_event(event.dest_path, "moved")
    
    def _handle_file_event(self, file_path_str: str, event_type: str):
        """Process file events and check if it's a new PNG"""
        file_path = Path(file_path_str)
        
        # Check if it's a PNG file
        if file_path.suffix.lower() == '.png':
            handle_new_png(file_path, event_type)


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
    global verbose_mode, analyze_mode
    
    parser = argparse.ArgumentParser(
        description="Watch a directory for new PNG files and print their filenames.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dir /path/to/watch                      # Watch specific directory
  %(prog)s --dir ~/Downloads --verbose               # Watch Downloads with verbose output
  %(prog)s --dir . --analyze                         # Watch current directory with OpenAI analysis
  %(prog)s --dir ~/Screenshots --analyze --verbose   # Full analysis with verbose output
  %(prog)s --dir ~/Screenshots --scan --analyze      # Scan existing files and add analysis
  %(prog)s --dir . --scan --analyze --verbose        # Scan with verbose output
  
Environment Variables (.env file or shell):
  OPENAI_API_KEY    Your OpenAI API key for screenshot analysis
  
Setup:
  1. Create .env file in project root with: OPENAI_API_KEY=your-key-here
  2. Run: uv add python-dotenv pillow
        """
    )
    
    parser.add_argument(
        '--dir',
        required=True,
        help='Directory path to watch for new PNG files'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output (show file paths, sizes, and event types)'
    )
    
    parser.add_argument(
        '--scan',
        action='store_true',
        help='Scan existing PNG files and add analysis metadata (instead of watching)'
    )

    parser.add_argument(
        '--watch',
        action='store_true',
        help='Watch specified directory and add analysis metadata for new PNG files'
    )
    
    parser.add_argument(
        '--api-key',
        help='OpenAI API key (can also use OPENAI_API_KEY environment variable)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='PNG Directory Watcher 2.0'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set global flags
    verbose_mode = args.verbose
    analyze_mode = True
    
    if not args.scan and not args.watch:
        print("Error: Either --scan or --watch is required")
        sys.exit(1)

    
    # Expand user path and resolve relative paths
    directory_path = Path(args.dir).expanduser().resolve()
    
    # Validate directory
    if not validate_directory(directory_path):
        sys.exit(1)
    
    # Check OpenAI setup if analysis is enabled
    if analyze_mode:
        api_key = args.api_key or os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("Error: OpenAI API key required for analysis.")
            print("   Set OPENAI_API_KEY environment variable or use --api-key flag")
            sys.exit(1)
        setup_openai_client(api_key)
    
    # Handle scan mode
    if args.scan:
        if not analyze_mode:
            print("Error: --scan requires --analyze flag to be set")
            print("   Use: --scan --analyze to scan and analyze existing files")
            sys.exit(1)
        
        print("📂 Scan mode: Analyzing existing PNG files...")
        scan_and_analyze_directory(directory_path)

    
    if not args.watch:
        return

    # Watch mode (original functionality)
    # Scan existing files
    scan_existing_files(directory_path)
    
    # Create event handler
    event_handler = SimpleFileHandler()
    
    # Set up observer
    observer = Observer()
    observer.schedule(event_handler, str(directory_path), recursive=False)
    
    try:
        # Start watching
        observer.start()
        print(f"Watching for new PNG files in: {directory_path}")
        if verbose_mode:
            print("Verbose mode enabled")
        if analyze_mode:
            print("OpenAI analysis enabled")
        print("Waiting for new PNG files... (Press Ctrl+C to stop)")
        
        # Keep the script running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping PNG watcher...")
        observer.stop()
        
    except Exception as e:
        print(f"\nError: {e}")
        observer.stop()
        sys.exit(1)
    
    # Wait for observer to finish
    observer.join()
    print("PNG watcher stopped")


if __name__ == "__main__":
    main()

# Installation requirements:
# uv add watchdog openai python-dotenv pillow pydantic