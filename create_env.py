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

print("Created .env file successfully!") 