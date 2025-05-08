# IRIP - VPN Account Management System

A Django-based system for managing VPN accounts via API, with integrated Stripe payment processing.

## Features

- Account Management: Extended Django user model for flexible user attribute management
- Stripe Integration: Financial gateway for handling payments
- RESTful API: Built with Django REST Framework
- Subscription Management: Handle user subscriptions connected to VPN accounts
- VPN Account Management: Manage VPN accounts connected to the Stripe Subscription Module
- JWT Authentication: Secure API endpoints
- Swagger Documentation: API documentation

## Tech Stack

- Python 3.12.1 (LTS)
- Django 5.2.1 (LTS)
- Django REST Framework
- PostgreSQL (Production)
- SQLite (Development)
- Docker for containerization

## Environment Variables

The project uses environment variables for configuration. Create a `.env` file in the project root by copying the `.env.example` file:

```bash
cp .env.example .env
```

Then edit the `.env` file to set your specific configuration values:

- `DEBUG`: Set to `True` for development, `False` for production
- `SECRET_KEY`: Django secret key for security
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `DATABASE_URL`: Database connection URL (leave empty for SQLite in development)
- `DB_*`: PostgreSQL database settings (used in production)
- `STRIPE_*`: Stripe API keys for payment processing
- `EMAIL_*`: Email server configuration
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed origins for CORS
- `JWT_*`: JWT token configuration

## Setup Instructions

### Development Environment

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd irip
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Run migrations:
   ```bash
   python manage.py migrate
   ```

6. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```

7. Start the development server:
   ```bash
   python manage.py runserver
   ```

### Production Environment

1. Build and run with Docker:
   ```bash
   docker-compose up -d
   ```

## API Documentation

API documentation is available at `/api/docs/` when the server is running.

## License

[Your License Information]
