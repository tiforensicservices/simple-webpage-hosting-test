# AWS Setup Guide — Shoe Print Image System

This guide walks through setting up AWS resources manually via the AWS Console.
Follow these steps in order before running any application code.

---

## Step 1: Create an IAM User (Programmatic Access)

> ⚠️ Never use your root AWS account for day-to-day development.

1. Go to [AWS IAM Console](https://console.aws.amazon.com/iam/)
2. Click **Users** → **Create user**
3. Username: `shoeprint-dev`
4. **Do NOT** enable AWS Management Console access (this is a programmatic-only user)
5. Click **Next: Permissions**

---

## Step 2: Attach IAM Policies

On the permissions page, select **Attach policies directly** and add:

| Policy Name | Purpose |
|---|---|
| `AmazonS3FullAccess` | Read/write images to S3 |
| `AmazonRekognitionFullAccess` | Image analysis and similarity search |
| `AmazonRDSFullAccess` | PostgreSQL database for metadata |
| `AWSLambdaFullAccess` | Serverless image processing functions |
| `CloudWatchLogsFullAccess` | Application logging |

> 🔐 **Note:** In production, you should replace `FullAccess` policies with
> custom least-privilege policies. These broad permissions are acceptable for
> initial development only.

6. Click **Next** → **Create user**

---

## Step 3: Generate Access Keys

1. Click on the new user `shoeprint-dev`
2. Go to the **Security credentials** tab
3. Scroll to **Access keys** → Click **Create access key**
4. Use case: **Application running outside AWS**
5. Click **Create access key**
6. **⚠️ IMPORTANT:** Download the CSV or copy the keys NOW — you cannot see the Secret Key again!

---

## Step 4: Add Keys to Your `.env` File

In the project root, copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Then fill in your values:

```
AWS_ACCESS_KEY_ID=AKIA...your key...
AWS_SECRET_ACCESS_KEY=your secret key
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=shoeprint-images-123456789012
```

> Replace `123456789012` with your actual AWS Account ID (found in top-right of AWS Console).

---

## Step 5: Verify the Connection

Inside the Dev Container, run:

```bash
python -c "import boto3; print(boto3.client('sts').get_caller_identity())"
```

You should see your Account ID and ARN printed. If you see an error, double-check your `.env` values.

---

## Step 6: Create the S3 Bucket

```bash
python src/aws/setup_s3.py
```

This will:
- Create the bucket with the name from your `.env`
- Block all public access
- Enable AES-256 encryption
- Enable versioning
- Apply lifecycle policy (cheaper storage for older images)
- Create `raw/`, `processed/`, and `thumbnails/` folders

---

## AWS Resources Reference

| Resource | Name | Purpose |
|---|---|---|
| S3 Bucket | `shoeprint-images-{account_id}` | Image storage |
| RDS (later) | `shoeprint-db` | Shoe metadata |
| Lambda (later) | `shoeprint-processor` | Image processing on upload |
| Rekognition (later) | `shoeprint-collection` | Visual similarity search |
| EventBridge (later) | `shoeprint-scraper-schedule` | Automated daily scraping |

---

## Security Checklist

- [ ] IAM user created (not root)
- [ ] Access keys stored only in `.env` (never committed)
- [ ] S3 bucket has public access blocked
- [ ] S3 bucket has encryption enabled
- [ ] CloudTrail enabled on AWS account (audit logging)
- [ ] MFA enabled on root account
