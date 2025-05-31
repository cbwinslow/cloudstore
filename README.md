# CloudStore

## Overview
CloudStore is a web scraping and price arbitrage system designed to scan various auction and e-commerce sites to identify price differences and dropshipping opportunities. The system integrates with IP Burger proxy services to manage IP rotation and uses the open-source Firecrawl model for efficient web data extraction.

## Features
- **Web Scraping System**: Crawls eBay, Amazon, ShopGoodwill.com, and PublicSurplus.com to collect product and pricing data
- **Proxy Integration**: Seamless rotation of IP addresses via IP Burger to prevent blocking
- **RESTful API**: Endpoints for data submission and retrieval
- **Price Analysis**: Sophisticated algorithms to detect arbitrage opportunities
- **PostgreSQL Database**: Efficient storage and retrieval of product listings and price history

## Project Structure
```
cloudstore/
├── api/             # API service implementation
├── crawlers/        # Site-specific web crawlers
├── database/        # Database models and migrations
├── proxy/           # IP Burger integration
├── analysis/        # Price analysis and arbitrage detection
├── docs/            # Project documentation
└── tests/           # Test suites
```

## Requirements
- Python 3.9+
- PostgreSQL 13+
- Docker (optional, for containerized deployment)
- IP Burger API access

## Installation

### Local Development Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/cloudstore.git
   cd cloudstore
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Initialize the database:
   ```bash
   python manage.py initialize_db
   ```

### Docker Setup
1. Build and start the containers:
   ```bash
   docker-compose up -d
   ```

2. Initialize the database:
   ```bash
   docker-compose exec app python manage.py initialize_db
   ```

## Usage

### Starting the API Server
```bash
python -m cloudstore.api.server
```

### Running the Crawlers
```bash
python -m cloudstore.crawlers.runner --site=ebay
```

### Analyzing Price Arbitrage
```bash
python -m cloudstore.analysis.arbitrage
```

## Documentation
For more detailed documentation, see:
- [Project Plan](PROJECT_PLAN.md)
- [Software Requirements Specification](SRS.md)
- [API Documentation](docs/api.md)
- [Database Schema](docs/schema.md)

## License
[MIT License](LICENSE)

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.
