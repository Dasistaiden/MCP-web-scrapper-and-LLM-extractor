# MCP Web Scraper for Claude Desktop

A Model Context Protocol (MCP) server that enables Claude Desktop to perform advanced web scraping and crawling operations. Extract structured data, analyze website architectures, and discover content relationships - all through natural conversation with Claude.

## 🎯 Features

- **Static & Dynamic Scraping**: Handle both regular HTML and JavaScript-rendered pages
- **Website Crawling**: Discover and map entire website structures
- **Data Extraction**: Extract specific elements using CSS selectors
- **Batch Operations**: Process multiple URLs efficiently
- **Link Analysis**: Understand how pages connect and reference each other

## 📋 Prerequisites

- Python 3.10 or higher
- WSL2 with Ubuntu (for Windows users)
- Claude Desktop application
- `uv` package manager

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/samirsaci/mcp-webscraper.git
cd mcp-webscraper
```

### 2. Install uv Package Manager

If you don't have uv installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Initialize the project

```bash
# Initialize the virtual environment
uv init .
```

### 4. Install Dependencies

```bash
uv add "mcp[cli]"
source .venv/bin/activate
uv pip install -r requirements.txt
```

Do not forget to install playwright browser to scrape dynamic content

```bash
uv run playwright install chromium
```

### 5. Test the Installation

Run the test script to verify everything works using a website that loves to be scrapped `https://books.toscrape.com/`:

```
uv run python test_local.py
```

Expected Output:

```
Static Scraping Success: True
HTML length: 51294
---------
Dynamic Scraping Success: True
HTML length: 51004
---------
Testing Crawler...
Crawler Success: True
Pages crawled: 5
Pages discovered: 437
Failed URLs: 0

First 3 pages discovered:
  1. All products | Books to Scrape - Sandbox
     URL: https://books.toscrape.com/
     Links found: 73
     Depth: 0
  2. All products | Books to Scrape - Sandbox
     URL: https://books.toscrape.com/index.html
     Links found: 73
     Depth: 1
  3. Books |
     Books to Scrape - Sandbox
     URL: https://books.toscrape.com/catalogue/category/books_1/index.html
     Links found: 73
     Depth: 1

Statistics:
  Total unique links: 104
  Max depth reached: 1
  Avg load time: 0.21s
```

## ⚙️ Claude Desktop Configuration

For Windows Users with WSL

1. Locate your Claude Desktop configuration file:

```
File -> Settings -> Edit Config
```

2. Add the WebScrappingServer configuration

```json
{
  "mcpServers": {
    "WebScrapingServer": {
      "command": "wsl",
      "args": [
        "-d",
        "Ubuntu",
        "bash",
        "-lc",
        "cd ~/path/to/mcp-webscraper && uv run --with mcp[cli] mcp run scrapping.py"
      ]
    }
  }
}
```

**Important**: Replace ~/path/to/mcp-webscraper with the actual path to your project folder in WSL.
To find your WSL path:

```bash
pwd
```

### 3. Restart Claude Desktop

After updating the configuration:

1. Completely quit Claude Desktop (not just close the window)
2. Start Claude Desktop again
3. Look for the 🔌 icon in the text input area
4. Click it to verify "WebScrapingServer" appears

### 🔧 Usage Examples

Once configured, you can ask Claude to:

#### Basic Scraping

```bash
"Scrape the homepage of example.com and tell me what you find"
```

#### Advanced SEO analysis

```bash
Please help me to crawl my personal blog https://yourblog.com with a limit of 150 pages.
I would like to understand how articles are referring to each other.
Can you help me to perform this type of analysis?
```

### 📁 Project Structure

```
mcp-webscraper/
├── models/
│   └── scraping_models.py      # Pydantic models for data validation
├── utils/
│   └── web_scraper.py          # Core WebScraper class
├── scrapping.py                 # MCP server implementation
├── test_local.py                # Local testing script
├── requirements.txt             # Python dependencies
├── README.md                    # This file
└── scraping_server.log          # Server logs (created at runtime)
```

### 🛠️ Available MCP Tools

The server exposes these tools to Claude:

- `scrape_url`: Get raw HTML from any webpage
- `extract_data`: Extract multiple elements using CSS selectors
- `extract_first`: Get a single element from a page
- `batch_scrape`: Process multiple URLs
- `crawl_website`: Discover and map website structure

## 🐛 Troubleshooting

### Server not appearing in Claude

\*If the server does not appear in Claude, try first to restart Claude Desktop by terminating its processus.`

If this does not work, try to

1. Check the log file:

```
cat scraping_server.log
```

2. Verify the path in config matches your WSL path:

```
pwd
```

The output should match what you have in your config file.

3. Test the server directly:

```bash
uv run python scrapping.py
```

### Playwright issues

If JavaScript scraping fails, try to reinstall the browser

```bash
uv run playwright install chromium
```

### WSL-specific issues

Ensure WSL2 is properly installed:

Run this in Windows PowerShell opened as Administrator

```bash
wsl --status
```

### 📄 License

MIT License - feel free to use this in your own projects!

## About me 🤓

Senior Supply Chain and Data Science consultant with international experience working on Logistics and Transportation operations.
For consulting or advising on analytics and sustainable supply chain transformation, feel free to contact me via [Logigreen Consulting](https://logi-green.com) or [LinkedIn](https://linkedin.com/in/samir-saci)
