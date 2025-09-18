# Script to create the .env file
# NOTE: If you're experiencing "insufficient_quota" errors:
# 1. Try creating a new OpenAI project in the OpenAI dashboard
# 2. Generate a new API key in that project
# 3. Replace the API key below with your new project's API  key

with open('.env', 'w') as f:
    f.write('OPENAI_API_KEY=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\n')
    f.write('PINECONE_API_KEY=pcsk_2nFAa7_RXos7jrxFi8DBEfGXUUGBz6x6RtQhB5AvpytRyem4SNxo2Ay58zmjDs2SCJY7PY\n')
    f.write('PINECONE_ENV=us-east-1-aws\n')
    f.write('PINECONE_INDEX=bayai\n')
    f.write('MONGO_URI=mongodb+srv://iotcom:aZ6DZBszmjtT9cGY@cluster0.tdvw5wt.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0\n')
    
    # Add DigitalOcean Spaces credentials
    f.write('DO_SPACES_BUCKET=bayshore\n')
    f.write('DO_SPACES_REGION=nyc3\n')
    f.write('DO_SPACES_KEY=DO00HFNWVPYJBRTBVZZJ\n') 
    f.write('DO_SPACES_SECRET=VTaTd4LASdw+OjDylmiBOPa4GOD956R/25597C7ULX8\n') 
    f.write('DO_FOLDER_NAME=ai_bot\n')
    
    # Add Google OAuth configuration
    f.write('GOOGLE_CLIENT_ID=580986048415-qpgtv2kvij47ae4if8ep47jjq8o2qtmj.apps.googleusercontent.com\n')
    f.write('GOOGLE_CLIENT_SECRET=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\n')
    
    # Add JWT configuration
    f.write('JWT_SECRET_KEY=e4f7c6d9b2a84f4aa01f1e3391e3e33e7c8a9cf23de141df97ad9e915c90b0f8\n')
    f.write('JWT_ALGORITHM=HS256\n')
    f.write('JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440\n')  # 24 hours
    
    # Add Redis configuration (WSL Ubuntu Redis server)
    f.write('REDIS_HOST=localhost\n')
    f.write('REDIS_PORT=6379\n')
    f.write('REDIS_DB=0\n')

print("Created .env file successfully!")
print("⚠️  IMPORTANT: Redis caching has been configured!")
print("   Make sure Redis is running on WSL Ubuntu: sudo service redis-server start")
print("   You can check Redis status: redis-cli ping")
print()
print("⚠️  IMPORTANT: You need to add your Google Client Secret to the .env file!")
print("   Go to Google Cloud Console > Credentials > Your OAuth Client > Client Secret")
print("   Replace 'YOUR_GOOGLE_CLIENT_SECRET_HERE' with your actual client secret") 