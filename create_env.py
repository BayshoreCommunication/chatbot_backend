# Script to create the .env file
with open('.env', 'w') as f:
    f.write('OPENAI_API_KEY=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\n')
    f.write('PINECONE_API_KEY=pcsk_2nFAa7_RXos7jrxFi8DBEfGXUUGBz6x6RtQhB5AvpytRyem4SNxo2Ay58zmjDs2SCJY7PY\n')
    f.write('PINECONE_ENV=us-east-1-aws\n')
    f.write('PINECONE_INDEX=bayshoreai\n')
    f.write('MONGO_URI=mongodb+srv://iotcom:aZ6DZBszmjtT9cGY@cluster0.tdvw5wt.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0\n')

print("Created .env file successfully!") 