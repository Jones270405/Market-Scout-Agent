from fastapi import FastAPI
from market_scout_agent.agent import root_agent

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Market Scout Agent running"}

@app.post("/chat")
async def chat(query: str):
    
    # Run the ADK agent
    response = root_agent.run(query)

    return {
        "query": query,
        "response": response
    }