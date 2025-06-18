# Script to create the .env file
# NOTE: If you're experiencing "insufficient_quota" errors:
# 1. Try creating a new OpenAI project in the OpenAI dashboard
# 2. Generate a new API key in that project
# 3. Replace the API key below with your new project's API key

with open('.env', 'w') as f:
    f.write('OPENAI_API_KEY=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\n')
    f.write('PINECONE_API_KEY=pcsk_2nFAa7_RXos7jrxFi8DBEfGXUUGBz6x6RtQhB5AvpytRyem4SNxo2Ay58zmjDs2SCJY7PY\n')
    f.write('PINECONE_ENV=us-east-1-aws\n')
    f.write('PINECONE_INDEX=bayshoreai\n')
    f.write('MONGO_URI=mongodb+srv://iotcom:aZ6DZBszmjtT9cGY@cluster0.tdvw5wt.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0\n')
    
    # Add DigitalOcean Spaces credentials
    f.write('DO_SPACES_BUCKET=bayshore\n')
    f.write('DO_SPACES_REGION=nyc3\n')
    f.write('DO_SPACES_KEY=DO00HFNWVPYJBRTBVZZJ\n') 
    f.write('DO_SPACES_SECRET=VTaTd4LASdw+OjDylmiBOPa4GOD956R/25597C7ULX8\n') 
    f.write('DO_FOLDER_NAME=ai_bot\n')

print("Created .env file successfully!") 