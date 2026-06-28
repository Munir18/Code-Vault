# SnippetVault AWS Deployment Guide

Use `us-east-1` for this guide. It has the broadest service availability and excellent free tier coverage.

## Phase 1 - AWS Account Setup

1. Sign in to the AWS Console.
2. Check Free Tier status at `https://console.aws.amazon.com/billing/home#/freetier`.
3. Open IAM, then choose **Users**.
4. Create a user named `snippetvault-deployer`.
5. Select programmatic access or create an access key after the user is created.
6. Attach these policies for a student lab account: `AmazonEC2FullAccess`, `AmazonRDSFullAccess`, `AmazonS3FullAccess`, `AWSLambda_FullAccess`, `AmazonAPIGatewayAdministrator`, and `IAMFullAccess`.
7. Save the access key ID and secret access key once. Do not commit them to Git.
8. Install AWS CLI from `https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html`.
9. Configure the CLI:

```bash
aws configure
```

10. Enter your access key ID, secret access key, default region `us-east-1`, and output format `json`.
11. Confirm the CLI identity:

```bash
aws sts get-caller-identity
```

## Phase 2 - VPC & Networking (Lab 1)

1. Open **VPC** in the AWS Console.
2. Choose **Your VPCs** and click **Create VPC**.
3. Select **VPC only**.
4. Name it `snippetvault-vpc`.
5. Set IPv4 CIDR to `10.0.0.0/16`.
6. Click **Create VPC**.
7. Open **Subnets** and click **Create subnet**.
8. Select `snippetvault-vpc`.
9. Create a public subnet:
   - Name: `snippetvault-public-subnet`
   - Availability Zone: `us-east-1a`
   - CIDR: `10.0.1.0/24`
10. Create a private subnet:
   - Name: `snippetvault-private-subnet`
   - Availability Zone: `us-east-1b`
   - CIDR: `10.0.2.0/24`
11. Open **Internet gateways** and click **Create internet gateway**.
12. Name it `snippetvault-igw`.
13. Select it, click **Actions**, then **Attach to VPC**.
14. Attach it to `snippetvault-vpc`.
15. Open **Route tables** and click **Create route table**.
16. Name it `snippetvault-public-rt` and select `snippetvault-vpc`.
17. Select `snippetvault-public-rt`, open **Routes**, and click **Edit routes**.
18. Add route `0.0.0.0/0` with target `snippetvault-igw`.
19. Open **Subnet associations** and associate `snippetvault-public-subnet`.
20. Create another route table named `snippetvault-private-rt` in `snippetvault-vpc`.
21. Associate `snippetvault-private-subnet` with `snippetvault-private-rt`.
22. Do not add a `0.0.0.0/0` internet route to the private route table.

## Phase 3 - RDS MySQL (Lab 4)

1. Open **EC2 > Security Groups**.
2. Create `sg-snippetvault-ec2` in `snippetvault-vpc` first if it does not exist yet. Add inbound SSH from your IP, app port `8080` from `0.0.0.0/0`, and HTTP `80` from `0.0.0.0/0`.
3. Create a second security group named `sg-snippetvault-rds` in `snippetvault-vpc`.
4. Add one inbound rule:
   - Type: MySQL/Aurora
   - Port: `3306`
   - Source: `sg-snippetvault-ec2`
5. Open **RDS > Subnet groups**.
6. Create DB subnet group `snippetvault-db-subnet-group`.
7. Select `snippetvault-vpc` and include the private subnet. If RDS requires two subnets, create a second private subnet such as `10.0.3.0/24` in another availability zone and include both private subnets.
8. Open **RDS > Databases** and click **Create database**.
9. Choose **Standard create**.
10. Engine: MySQL.
11. Version: MySQL 8.0.
12. Template: Free tier.
13. DB instance identifier: `snippetvault-db`.
14. Master username: `admin`.
15. Set and save a strong password.
16. Instance class: `db.t3.micro`.
17. Storage: 20 GiB or less for free tier.
18. Connectivity:
   - VPC: `snippetvault-vpc`
   - DB subnet group: `snippetvault-db-subnet-group`
   - Public access: **No**
   - Security group: `sg-snippetvault-rds`
19. Initial database name: `snippetvault`.
20. Create the database.
21. When available, copy the RDS endpoint hostname.
22. After EC2 is running, copy `backend/schema.sql` to EC2 and run:

```bash
mysql -h <rds-endpoint> -u admin -p < schema.sql
```

## Phase 4 - EC2 & Docker (Labs 2 & 6)

1. Open **EC2 > Security Groups**.
2. Create `sg-snippetvault-ec2` in `snippetvault-vpc` if you did not create it in Phase 3.
3. Add inbound rules exactly:
   - SSH, port `22`, source **My IP**
   - Custom TCP, port `8080`, source `0.0.0.0/0`
   - HTTP, port `80`, source `0.0.0.0/0`
4. Leave outbound as all traffic allowed.
5. Open **EC2 > Instances** and click **Launch instances**.
6. Name: `snippetvault-ec2`.
7. AMI: Amazon Linux 2023.
8. Instance type: `t2.micro`.
9. Create or select a key pair.
10. Network: `snippetvault-vpc`.
11. Subnet: `snippetvault-public-subnet`.
12. Auto-assign public IP: Enable.
13. Security group: `sg-snippetvault-ec2`.
14. Launch the instance.
15. Open **Elastic IPs** and allocate a new Elastic IP.
16. Associate the Elastic IP with `snippetvault-ec2`.
17. SSH into the instance:

```bash
ssh -i <your-key>.pem ec2-user@<EC2_ELASTIC_IP>
```

18. Install Docker:

```bash
sudo dnf update -y
sudo dnf install -y docker mysql
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user
exit
```

19. SSH back in so the Docker group change applies.
20. From your local machine, copy the backend folder:

```bash
scp -i <your-key>.pem -r snippetvault/backend ec2-user@<EC2_ELASTIC_IP>:/home/ec2-user/snippetvault-backend
```

21. SSH into EC2 and create the `.env` file:

```bash
cd /home/ec2-user/snippetvault-backend
nano .env
```

22. Paste real RDS values:

```bash
DB_HOST=<rds-endpoint>
DB_USER=admin
DB_PASSWORD=<your-rds-password>
DB_NAME=snippetvault
```

23. Load the schema:

```bash
mysql -h <rds-endpoint> -u admin -p < schema.sql
```

24. Build and run the Docker container:

```bash
docker build -t snippetvault-backend .
docker run -d -p 8080:5000 --env-file .env --name snippetvault-backend snippetvault-backend
```

25. Verify locally on EC2:

```bash
curl http://localhost:8080/api/health
```

26. Verify from your computer:

```bash
curl http://<EC2_ELASTIC_IP>:8080/api/health
```

## Phase 5 - S3 Frontend (Lab 3)

1. Open **S3** in the AWS Console.
2. Click **Create bucket**.
3. Bucket name: `snippetvault-frontend-<your-name>`.
4. Region: `us-east-1`.
5. Turn off **Block all public access** and acknowledge the warning.
6. Create the bucket.
7. Open the bucket and go to **Properties**.
8. Enable **Static website hosting**.
9. Hosting type: **Host a static website**.
10. Index document: `index.html`.
11. Save changes.
12. Open **Permissions > Bucket policy**.
13. Add this policy, replacing the bucket name:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::snippetvault-frontend-<your-name>/*"
    }
  ]
}
```

14. Edit `frontend/config.js` locally:

```javascript
const CONFIG = {
  EC2_API_BASE: 'http://<EC2_ELASTIC_IP>:8080/api',
  APIGW_BASE: 'https://<APIGW_ID>.execute-api.us-east-1.amazonaws.com'
};
```

15. Upload `index.html`, `config.js`, and `styles.css` from `snippetvault/frontend` to the S3 bucket.
16. Open the static website endpoint from **Properties > Static website hosting**.

## Phase 6 - Lambda & API Gateway (Labs 7 & 8)

1. Open **IAM > Roles** and create a role.
2. Trusted entity: AWS service.
3. Use case: Lambda.
4. Role name: `snippetvault-lambda-role`.
5. Attach `AWSLambdaBasicExecutionRole`.
6. Attach `AWSLambdaVPCAccessExecutionRole`.
7. On your local machine, package `snippetvault-save-snippet`:

```bash
cd snippetvault/lambda/save-snippet
mkdir package
pip install -r requirements.txt -t package
cp lambda_function.py package/
cd package
zip -r ../save-snippet.zip .
cd ..
```

8. Create the save Lambda:

```bash
aws lambda create-function \
  --function-name snippetvault-save-snippet \
  --runtime python3.12 \
  --handler lambda_function.lambda_handler \
  --role arn:aws:iam::<ACCOUNT_ID>:role/snippetvault-lambda-role \
  --zip-file fileb://save-snippet.zip \
  --environment Variables="{DB_HOST=<rds-endpoint>,DB_USER=admin,DB_PASSWORD=<your-rds-password>,DB_NAME=snippetvault}"
```

9. Configure save Lambda VPC access in the Console:
   - VPC: `snippetvault-vpc`
   - Subnet: `snippetvault-private-subnet`
   - Security group: a Lambda security group that RDS allows, or `sg-snippetvault-ec2` for a simple lab setup
10. Ensure `sg-snippetvault-rds` inbound allows MySQL from the security group used by the save Lambda.
11. Package `snippetvault-ai-summary`:

```bash
cd ../ai-summary
zip ai-summary.zip lambda_function.py
```

12. Create the AI summary Lambda:

```bash
aws lambda create-function \
  --function-name snippetvault-ai-summary \
  --runtime python3.12 \
  --handler lambda_function.lambda_handler \
  --role arn:aws:iam::<ACCOUNT_ID>:role/snippetvault-lambda-role \
  --zip-file fileb://ai-summary.zip \
  --environment Variables="{ANTHROPIC_API_KEY=<your-anthropic-api-key>}"
```

13. Do not configure VPC access for `snippetvault-ai-summary`.
14. Open **API Gateway** and choose **Create API**.
15. Choose **HTTP API**.
16. Add Lambda integrations for both functions.
17. Create routes:
   - `POST /snippet` to `snippetvault-save-snippet`
   - `POST /ai-summary` to `snippetvault-ai-summary`
18. Enable CORS:
   - Access-Control-Allow-Origin: `*`
   - Access-Control-Allow-Headers: `content-type`
   - Access-Control-Allow-Methods: `POST,OPTIONS`
19. Deploy the API.
20. Copy the invoke URL and place it in `frontend/config.js`.
21. Test save Lambda through API Gateway:

```bash
curl -X POST https://<APIGW_ID>.execute-api.us-east-1.amazonaws.com/snippet \
  -H "Content-Type: application/json" \
  -d '{"title":"Lambda Save","code":"print(\"lambda\")","language":"python","tags":["lambda"],"user_id":1}'
```

22. Test AI summary:

```bash
curl -X POST https://<APIGW_ID>.execute-api.us-east-1.amazonaws.com/ai-summary \
  -H "Content-Type: application/json" \
  -d '{"code":"print(\"hello world\")","language":"python"}'
```

## Phase 7 - Testing & Verification

1. Test EC2 health:

```bash
curl http://<EC2_IP>:8080/api/health
```

Expected:

```json
{"status":"ok"}
```

2. Test create snippet via EC2:

```bash
curl -X POST http://<EC2_IP>:8080/api/snippets \
  -H "Content-Type: application/json" \
  -d '{"title":"Hello World","code":"print(\"hello\")","language":"python","tags":["test"],"user_id":1}'
```

Expected:

```json
{"id":1}
```

3. Test list snippets:

```bash
curl http://<EC2_IP>:8080/api/snippets
```

Expected: a JSON array of snippets.

4. Test AI summary via API Gateway:

```bash
curl -X POST https://<APIGW_ID>.execute-api.us-east-1.amazonaws.com/ai-summary \
  -H "Content-Type: application/json" \
  -d '{"code":"print(\"hello world\")","language":"python"}'
```

Expected:

```json
{"summary":"Prints the string hello world to the console."}
```

5. Test S3 frontend by opening:

```text
http://snippetvault-frontend-<your-name>.s3-website-us-east-1.amazonaws.com
```

## Phase 8 - Getting the Anthropic API Key (Free)

1. Go to `https://console.anthropic.com`.
2. Sign up for a free account.
3. Navigate to **API Keys**.
4. Click **Create Key**.
5. Copy the key once and store it securely.
6. Anthropic commonly provides starter credit for new accounts; the Haiku model is low-cost and appropriate for this project.
7. Add the key as `ANTHROPIC_API_KEY` in the `snippetvault-ai-summary` Lambda environment variables.

## Phase 9 - Cost Estimate & Free Tier Notes

| Service | Free Tier Limit | Expected Usage | Cost |
|---------|----------------|----------------|------|
| EC2 t2.micro | 750 hrs/month | ~720 hrs always on | $0 |
| RDS db.t3.micro | 750 hrs/month | ~720 hrs | $0 |
| RDS storage | 20 GB | ~1 GB | $0 |
| S3 storage | 5 GB | ~1 MB | $0 |
| S3 requests | 20,000 GET/month | Minimal | $0 |
| Lambda | 1M requests/month | Minimal | $0 |
| API Gateway | 1M calls/month | Minimal | $0 |
| Data transfer | 15 GB/month | Minimal | $0 |
| **Total** | | | **$0** |

Important: if your AWS Free Tier has expired, expect approximately `$15-20/month` for EC2 and RDS together. Stop EC2 and RDS when not in use to reduce cost. Stop, do not terminate, if you want to keep the project state.

## Phase 10 - Cleanup (After Semester Ends)

1. Terminate the EC2 instance.
2. Release the Elastic IP.
3. Delete the RDS instance. Uncheck **Create final snapshot** if you do not need a backup.
4. Empty the S3 bucket.
5. Delete the S3 bucket.
6. Delete both Lambda functions.
7. Delete the API Gateway HTTP API.
8. Delete Lambda deployment roles if they are no longer needed.
9. Delete the custom VPC. AWS will also remove related subnets, route tables, and the internet gateway after dependencies are gone.
