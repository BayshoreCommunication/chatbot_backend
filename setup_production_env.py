#!/usr/bin/env python3
"""
Production Environment Setup Script
Helps configure environment variables for DigitalOcean deployment
"""
import os
import sys
from pathlib import Path

def check_environment_variables():
    """Check if all required environment variables are set"""
    required_vars = {
        'MONGO_URI': 'MongoDB connection string',
        'OPENAI_API_KEY': 'OpenAI API key',
        'PINECONE_API_KEY': 'Pinecone API key',
        'PINECONE_ENV': 'Pinecone environment',
        'PINECONE_INDEX': 'Pinecone index name'
    }
    
    optional_vars = {
        'CALENDLY_API_KEY': 'Calendly API key (optional)',
        'STRIPE_SECRET_KEY': 'Stripe secret key (optional)',
        'STRIPE_WEBHOOK_SECRET': 'Stripe webhook secret (optional)'
    }
    
    print("🔍 Checking Environment Variables...")
    print("=" * 50)
    
    missing_required = []
    missing_optional = []
    
    # Check required variables
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {description} - SET")
        else:
            print(f"❌ {var}: {description} - MISSING")
            missing_required.append(var)
    
    print("\n📋 Optional Variables:")
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {description} - SET")
        else:
            print(f"⚠️  {var}: {description} - NOT SET (optional)")
            missing_optional.append(var)
    
    return missing_required, missing_optional

def test_database_connection():
    """Test database connection"""
    print("\n🗄️  Testing Database Connection...")
    print("=" * 50)
    
    try:
        from services.database import client
        client.admin.command('ping')
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_api_services():
    """Test API service availability"""
    print("\n🔌 Testing API Services...")
    print("=" * 50)
    
    services = {
        'OpenAI': os.getenv('OPENAI_API_KEY') is not None,
        'Pinecone': os.getenv('PINECONE_API_KEY') is not None,
        'Calendly': os.getenv('CALENDLY_API_KEY') is not None,
        'Stripe': os.getenv('STRIPE_SECRET_KEY') is not None
    }
    
    for service, available in services.items():
        status = "✅ Available" if available else "❌ Not configured"
        print(f"{service}: {status}")
    
    return services

def generate_env_template():
    """Generate a template .env file"""
    print("\n📝 Generating .env template...")
    print("=" * 50)
    
    template = """# Production Environment Variables
# Copy this to .env and fill in your values

# Database
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/

# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key

# Pinecone
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENV=your-pinecone-environment
PINECONE_INDEX=your-pinecone-index-name

# Optional Services
CALENDLY_API_KEY=your-calendly-api-key
STRIPE_SECRET_KEY=sk_test_your-stripe-secret-key
STRIPE_WEBHOOK_SECRET=whsec_your-stripe-webhook-secret

# Logging
LOG_LEVEL=INFO
"""
    
    with open('.env.template', 'w') as f:
        f.write(template)
    
    print("✅ .env.template created")
    print("📋 Edit this file with your actual values and rename to .env")

def main():
    """Main function"""
    print("🚀 Production Environment Setup")
    print("=" * 50)
    
    # Check environment variables
    missing_required, missing_optional = check_environment_variables()
    
    # Test database connection
    db_ok = test_database_connection()
    
    # Test API services
    services = test_api_services()
    
    # Generate template if needed
    if missing_required:
        print(f"\n⚠️  Missing {len(missing_required)} required environment variables")
        generate_env_template()
    
    # Summary
    print("\n📊 Summary:")
    print("=" * 50)
    
    if not missing_required and db_ok:
        print("🎉 All required services are configured and working!")
        print("✅ Your production environment is ready")
    else:
        print("⚠️  Some issues need to be resolved:")
        if missing_required:
            print(f"   - Missing required variables: {', '.join(missing_required)}")
        if not db_ok:
            print("   - Database connection failed")
    
    # Feature availability
    print("\n🔧 Feature Availability:")
    print("=" * 50)
    
    features = {
        'Conversation Management': not missing_required and db_ok,
        'AI FAQ Bot': services['OpenAI'],
        'FAQ Management System': True,  # Always available
        'Instant Reply Configuration': True,  # Always available
        'Lead Capture Mode': True,  # Always available
        'Appointment & Booking Integration': True,  # Always available
        'Appointment Availability Configuration': True,  # Always available
        'Sales Assistant Mode': True,  # Always available
        'Multi-tenant organization support': not missing_required and db_ok,
        'Dashboard Analytics': not missing_required and db_ok,
        'Stripe Payment Processing': services['Stripe'],
        'Admin Dashboard': not missing_required and db_ok
    }
    
    for feature, available in features.items():
        status = "✅ Available" if available else "❌ Not available"
        print(f"{feature}: {status}")

if __name__ == "__main__":
    main()
