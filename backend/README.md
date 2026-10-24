# Real Estate Recommendation System — Backend API

FastAPI-powered REST API providing hybrid search (full-text + vector + graph), conversational multi-agent chat, property management, and automated real estate price valuation.

---

## 1. Key API Endpoints

All endpoints are versioned under `/v1`.

### Properties & Valuation
- `POST /v1/properties/predict-price`: Predict estimated property price with segment-calibrated confidence bounds.
- `GET /v1/properties`: List and filter properties.
- `GET /v1/properties/{property_id}`: Retrieve property details.
- `GET /v1/properties/{property_id}/similar`: Find similar properties via pgvector cosine similarity.
- `GET /v1/properties/{property_id}/graph`: Query property relationship subgraph in Neo4j.
- `GET /v1/properties/image`: Stream property image from private MinIO storage.

### Search & Chat
- `POST /v1/search`: Hybrid search across PostgreSQL (FTS + vector) and Neo4j.
- `POST /v1/search/parse`: Parse natural Vietnamese query into structured search criteria.
- `POST /v1/chat`: Conversational real estate assistant via LangGraph.

---

## 2. Price Prediction API (`POST /v1/properties/predict-price`)

Estimates property market valuation using a trained machine learning model (`HistGradientBoostingRegressor`).

### Request Headers
```http
Content-Type: application/json
```

### Request Payload
| Field | Type | Required | Description | Example |
|---|---|---|---|---|
| `property_type` | `string` | Yes | Segment: `"Căn hộ"` or `"Nhà đất"` | `"Nhà đất"` |
| `area` | `float` | Yes | Usable area in m² | `80.0` |
| `bedrooms` | `integer` | Yes | Number of bedrooms (>= 1) | `3` |
| `latitude` | `float` | Yes | Coordinate latitude in HCMC | `10.745` |
| `longitude` | `float` | Yes | Coordinate longitude in HCMC | `106.705` |
| `district` | `string` | Yes | Ward or district name | `"Phường Tân Hưng"` |
| `legal_status` | `string` | No | Default: `"Sổ hồng riêng"` | `"Sổ hồng riêng"` |

#### Request Example
```json
{
  "property_type": "Nhà đất",
  "area": 80.0,
  "bedrooms": 3,
  "latitude": 10.745,
  "longitude": 106.705,
  "district": "Phường Tân Hưng",
  "legal_status": "Sổ hồng riêng"
}
```

### Response Payload
| Field | Type | Description |
|---|---|---|
| `estimated_price` | `float` | Model point estimate in billion VND |
| `lower_bound` | `float` | Calibrated lower confidence bound in billion VND |
| `upper_bound` | `float` | Calibrated upper confidence bound in billion VND |
| `unit` | `string` | Unit of currency (`"tỷ VND"`) |
| `property_type` | `string` | Evaluated property segment |
| `district` | `string` | Evaluated ward/district |
| `model_name` | `string` | Model algorithm (`"HistGradientBoosting"`) |

#### Response Example
```json
{
  "data": {
    "estimated_price": 9.01,
    "lower_bound": 7.21,
    "upper_bound": 10.81,
    "unit": "tỷ VND",
    "property_type": "Nhà đất",
    "district": "Phường Tân Hưng",
    "model_name": "HistGradientBoosting"
  },
  "errors": [],
  "status": "success"
}
```

*Note: The model calibrates `lower_bound` and `upper_bound` according to the empirical variance of the property segment:*
- *Căn hộ: ±12% (empirically MAPE is 14.89%)*
- *Nhà đất: ±20% (empirically MAPE is 21.01%)*

---

## 3. Running the Backend

### Via Docker Compose (Recommended)
From repository root:
```bash
docker compose up -d --build backend
```

API documentation (Swagger UI) is available at:
```
http://localhost:8000/docs
```
