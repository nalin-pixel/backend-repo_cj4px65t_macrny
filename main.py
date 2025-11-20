import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from database import create_document, get_documents, db
from schemas import Lead
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

# Helper to forward lead to CRM/email webhooks if configured
def forward_lead_to_integrations(payload: dict):
    webhook = os.getenv("CRM_WEBHOOK_URL")
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    try:
        if webhook:
            requests.post(webhook, json={"type": "lead", **payload}, timeout=5)
        if slack_webhook:
            text = f"New Lead: {payload.get('name')} <{payload.get('email')}>\nSource: {payload.get('source')}\nMessage: {payload.get('message', '')}".strip()
            requests.post(slack_webhook, json={"text": text}, timeout=5)
    except Exception:
        # Fail silently for integrations; core flow should still succeed
        pass

# API: Create a lead
@app.post("/api/leads", status_code=201)
def create_lead(lead: Lead):
    try:
        inserted_id = create_document("lead", lead)
        payload = lead.model_dump() if hasattr(lead, 'model_dump') else lead.dict()
        payload.update({"id": inserted_id})
        forward_lead_to_integrations(payload)
        return {"id": inserted_id, "status": "received"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# API: List leads (admin/testing)
@app.get("/api/leads")
def list_leads(limit: int = 50):
    try:
        docs = get_documents("lead", limit=limit)
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])
            if "created_at" in d:
                d["created_at"] = str(d["created_at"])  # ISO string
            if "updated_at" in d:
                d["updated_at"] = str(d["updated_at"])  # ISO string
        return {"items": docs, "count": len(docs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
