# png-meta

png-meta is a proof of concept project that stores AI-generated image descriptions directly within PNG file metadata. This approach enables content-based searching and cataloging without needing to re-analyze images each time.

The project consists of two main components:
- **png-meta.py**: Watches directories and analyzes PNG files with AI and embeds meta data within the PNG
- **png-search.py**: Searches through analyzed PNG files using natural language queries

View a video here:    
https://www.youtube.com/watch?v=9_e3rYqtEFA

Example use cases include:

- Automatically cataloging screenshots from your desktop or downloads folder
- Adding rich metadata to photograph collections
- Finding specific screenshots or images using natural language searches
- Organizing large collections of PNG files based on their content
- Creating searchable archives of visual content with embedded analysis

## How it works

The png-meta system works by:

1. **Monitoring**: Watching specified directories for new PNG files
2. **Analysis**: Using OpenAI's GPT-4 Vision to analyze image content, extracting text, identifying applications, and categorizing images
3. **Storage**: Embedding the analysis results as metadata directly in the PNG files
4. **Search**: Providing intelligent search through the analyzed images using natural language queries

**Directory Watcher** -> **OpenAI Vision Analysis** -> **PNG Metadata Storage** -> **AI-Powered Search**

The analysis includes:
- Descriptive titles and descriptions
- Text extraction from screenshots and documents
- Application and interface identification
- Content categorization (screenshot, photograph, graphic)
- Explicit content detection

## Requirements

- Python 3.8 or higher
- OpenAI API key
- Required Python packages (automatically managed with uv)

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

### Download png-meta

Download or clone the png-meta project to your desired location.


### OpenAI API Setup

1. Get an OpenAI API key from [OpenAI Platform](https://platform.openai.com/)
2. Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=your-api-key-here
```

Alternatively, you can set the environment variable in your shell or pass it via the `--api-key` flag.

## Usage

### Analyzing PNG Files

The main script `png-meta.py` can operate in two modes:

#### Watch Mode
Monitor a directory for new PNG files and analyze them automatically:

```bash
# Basic watching with analysis
uv run png-meta.py --dir ~/Screenshots --watch

# Watch with verbose output
uv run png-meta.py --dir ~/Downloads --watch --verbose
```

#### Scan Mode
Analyze existing PNG files in a directory:

```bash
# Scan and analyze all PNG files
uv run png-meta.py --dir ~/Pictures --scan

# Scan with verbose output
uv run png-meta.py --dir ~/Desktop --scan --verbose
```

You can also scan and watch in the same command, with existing files in the directory scanned before the script starts watching the directory for changes:

```
python png-meta.py --dir ~/Screenshots --scan --watch
```

### Searching PNG Files

Use `png-search.py` to find specific images using natural language:

```bash
# Basic search
uv run png-search.py --dir ~/Screenshots --prompt "find screenshots with Terminal"

# Search with verbose output
uv run png-search.py --dir ~/Desktop --prompt "images containing error messages" --verbose

# Get full file paths instead of filenames
uv run png-search.py --dir . --prompt "code editors" --paths

# Output results as JSON
uv run png-search.py --dir ~/Desktop --prompt "screenshots with Python code" --json
```

### Command Line Options

#### png-meta.py

```
--dir PATH          Directory to watch or scan (required)
--scan              Scan existing PNG files and add analysis
--watch             Watch directory for new PNG files
--verbose, -v       Enable detailed output
--api-key KEY       OpenAI API key (or use OPENAI_API_KEY env var)
```

#### png-search.py

```
--dir PATH          Directory to search in (required)
--prompt TEXT       Search query describing what to find (required)
--verbose, -v       Enable detailed output
--paths, -p         Return full file paths instead of filenames
--json              Output results as JSON array
--api-key KEY       OpenAI API key (or use OPENAI_API_KEY env var)
```

## Examples

### Complete Workflow

1. **Set up automatic analysis** of your Screenshots folder:
```bash
uv run png-meta.py --dir ~/Screenshots --watch --verbose
```

2. **Analyze existing files** in your Downloads:
```bash
uv run png-meta.py --dir ~/Downloads --scan
```

3. **Search for specific content**:
```bash
# Find Terminal screenshots
uv run png-search.py --dir ~/Screenshots --prompt "Terminal or command line"

# Find code-related images
uv run png-search.py --dir ~/Desktop --prompt "programming or code editors"

# Find error messages
uv run png-search.py --dir ~/Downloads --prompt "error dialogs or warning messages"
```

4. Search and Open in Preview on Mac

```bash
# Find screenshots with specific applications and then open in preview on mac
uv run png-search.py --dir ~/Desktop --prompt "VS Code or code editor"  --path | xargs open
```

### Analysis Output

When analyzing images, png-meta extracts:

- **Title**: Concise description (3-8 words)
- **Descriptions**: Brief and detailed descriptions
- **Embedded Text**: All readable text from the image
- **Applications**: Detected software interfaces
- **Type**: Classification as screenshot, photograph, or graphic
- **Content Flags**: Explicit content detection

## Metadata Storage

png-meta embeds analysis data directly in PNG files using standard PNG text chunks. This means:

- Analysis travels with the file when copied or moved
- No external database required
- Standard PNG readers can access the metadata
- Original image quality is preserved

### Storage Method

The metadata is stored within the PNG in the `png-meta-data` tag. The data is serialized as JSON and embedded directly into the PNG file without affecting the image quality or visual appearance.


| Field | Type | Description |
|-------|------|-------------|
| title | string | Concise, descriptive title for the image (3-8 words) |
| short_description | string | Brief one-sentence description (under 100 characters) |
| long_description | string | Detailed description of what's shown in the image (2-4 sentences) |
| ai_description | string | Technical analysis for AI systems including visual elements, composition, colors, style, etc. (2-3 sentences) |
| explicit_content | boolean | true if image contains adult/explicit content, false otherwise |
| embedded_text | string | All readable text extracted from the image, preserving structure when possible (includes UI elements, buttons, menus, document content, code, etc.) |
| apps | array[string] | List of application names, window titles, or software interfaces visible in the image |
| type | string | Image classification - one of: "screenshot", "photograph", or "graphic" |



## Tips

### General Usage
- You can use tools like exiftool to view the data
- Let the analysis complete before making changes to files
- Use descriptive search terms for better results
- The AI is liberal in matching - if unsure, it includes results
- Verbose mode shows detailed progress and debugging info

### Search Optimization
- Use natural language in search prompts
- Be specific about what you're looking for
- Combine multiple search terms for refined results

### Performance
- Large directories may take time to analyze initially
- Subsequent searches are fast as they use embedded metadata
- Watch mode processes files as they appear, spreading the load


## Troubleshooting

### API Issues
- Verify your OpenAI API key is correct and has credit
- Check your internet connection
- Ensure you're using a supported OpenAI model

### File Access
- Make sure you have read/write permissions to the target directory
- Some system directories may be protected
- PNG files must be valid and readable

### Search Problems
- Ensure files have been analyzed first using png-meta.py
- Try broader search terms if no results found
- Use `--verbose` to see what files are being found and processed

### Performance Issues
- Large images take longer to analyze
- Consider processing smaller batches for initial scans
- Watch mode is more efficient than repeated scans

If you continue to have issues, check that all dependencies are installed correctly and that your OpenAI API key is valid.

## Development

The project is structured for easy extension:

- **Analysis Models**: Modify the Pydantic models in png-meta.py to change analysis structure
- **Search Logic**: Enhance search capabilities in png-search.py
- **File Handling**: Extend support for additional image formats
- **Metadata**: Add custom metadata fields or storage options

Key files:
- `png-meta.py`: Main analysis and watching functionality
- `png-search.py`: Search and retrieval system
- Analysis uses OpenAI's structured output for reliable results

## Questions, Feature Requests, Feedback

This project demonstrates the power of combining AI vision analysis with embedded metadata for intelligent file organization and retrieval.

For questions, feature requests, or feedback, please open an [issue](https://github.com/mikechambers/png-meta/issues) on the project repository.

## License

Project released under a [MIT License](LICENSE.md).

[![License: MIT](https://img.shields.io/badge/License-MIT-orange.svg)](LICENSE.md)