# SnippetVault

SnippetVault is a collaborative code snippet manager for saving, tagging, searching, and sharing reusable code snippets. It includes a Flask API, a static S3 frontend, MySQL storage, and an AI summary workflow powered by an Anthropic-backed Lambda function.

## Architecture

```text
Browser
  |
  v
S3 Static Website
  |
  v
EC2 Elastic IP :8080
Docker container running Flask
  |
  v
RDS MySQL in private subnet

Browser
  |
  v
API Gateway HTTP API
  |------------------------------|
  v                              v
Lambda: save-snippet             Lambda: ai-summary
  |                              |
  v                              v
RDS MySQL in private subnet      Anthropic Claude API
```

## Tech Stack

- Frontend: vanilla HTML, CSS, JavaScript, highlight.js CDN
- Backend: Python 3.12, Flask, flask-cors, PyMySQL, python-dotenv
- Containerization: Docker and Docker Compose
- Database: MySQL 8.0 locally and Amazon RDS MySQL 8.0 in AWS
- Serverless: AWS Lambda Python 3.12 and API Gateway HTTP API
- Cloud hosting: S3 static website, EC2 t2.micro, custom VPC

## Project Structure

```text
snippetvault/
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .env.example
│   └── schema.sql
├── lambda/
│   ├── save-snippet/
│   │   ├── lambda_function.py
│   │   └── requirements.txt
│   └── ai-summary/
│       ├── lambda_function.py
│       └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── config.js
│   └── styles.css
├── DEPLOYMENT.md
├── README.md
└── .gitignore
```

## Local Development

1. Install Docker Desktop.
2. Open a terminal in `snippetvault/backend`.
3. Create a local environment file:

```bash
cp .env.example .env
```

4. Start MySQL and the Flask API:

```bash
docker compose up --build
```

5. Verify the backend:

```bash
curl http://localhost:8080/api/health
```

Expected output:

```json
{"status":"ok"}
```

6. Open `snippetvault/frontend/config.js` and set:

```javascript
const CONFIG = {
  EC2_API_BASE: 'http://localhost:8080/api',
  APIGW_BASE: 'https://REPLACE_WITH_YOUR_API_GATEWAY_ID.execute-api.us-east-1.amazonaws.com'
};
```

7. Open `snippetvault/frontend/index.html` in a browser. The AI summary button will only work after the API Gateway and Lambda deployment is complete.

## AWS Deployment

Follow [DEPLOYMENT.md](DEPLOYMENT.md) from Phase 1 through Phase 10. The guide covers the required custom VPC, EC2 Docker deployment, private RDS MySQL setup, S3 static website hosting, Lambda deployment packages, API Gateway routes, testing commands, cost notes, and cleanup.
