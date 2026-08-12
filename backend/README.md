# AI-Order Backend

FastAPI backend with MySQL + RAG-powered product search + AI chat (Gemini / OpenAI).

## Setup

### 1. Create virtual environment
```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up MySQL
Open MySQL and run:
```bash
mysql -u root -p < schema.sql
```
This creates the `ai_order` database and seeds 15 sample products.

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env — fill in DB_PASSWORD, GEMINI_API_KEY / OPENAI_API_KEY, SMTP creds, SHOP_EMAIL
```

### 5. Embed products (RAG index)
```bash
python seed.py
```
Downloads `all-MiniLM-L6-v2` (~90 MB) once and writes vectors into MySQL.

### 6. Run the server
```bash
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat` | One-shot AI chat with RAG |
| POST | `/api/v1/orders` | Place order, save customer, send emails |
| GET  | `/api/v1/products` | List products (optional `?category=`) |
| POST | `/api/v1/products/index` | Re-embed unindexed products |
| GET  | `/health` | Health check |

## Chat flow

```
POST /api/v1/chat
{
  "message": "I need pure milk",
  "category_filter": "Dairy & Beverages",   // optional
  "latitude": 25.2048,                        // optional
  "longitude": 55.2708
}

→ {
    "reply": "We have Whole Milk at $1.80/litre and Skimmed Milk...",
    "products": [ { "id": 1, "name": "Whole Milk", ... }, ... ]
  }
```

## Order flow

```
POST /api/v1/orders
{
  "customer": {
    "name": "Ahmed Ali",
    "email": "ahmed@example.com",
    "phone": "+971501234567",
    "latitude": 25.2048,
    "longitude": 55.2708,
    "address": "Dubai Marina, Tower 3"
  },
  "items": [
    { "product_id": 1, "quantity": 2 },
    { "product_id": 6, "quantity": 1.5 }
  ],
  "notes": "Please deliver before 6 PM"
}
```
On success: saves customer + order to MySQL, sends receipt to customer and notification to shop email.
