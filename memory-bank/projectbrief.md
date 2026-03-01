# Project Brief

## Project Name
Shoe Print Image System (repo: simple-webpage-hosting-test)

## Overview
A forensic-grade web application that maintains a large database of shoe print images
and automates the search for new shoes and tread patterns. Built with VS Code + Cline
(AI assistant), containerized with Docker for safe local development, version-controlled
with Git/GitHub, and deployed on AWS.

## Goals
- Build and maintain a searchable database of shoe print images
- Automate the discovery of new shoes and tread patterns via scheduled scraping
- Provide a forensic search tool to match crime scene prints to known shoe models
- Host securely on AWS with encryption, audit logging, and least-privilege access
- Learn and apply best practices for modern software development throughout

## Core Features (Planned)
1. **Image Ingestion** — Upload shoe print images; normalize and store in S3
2. **Automated Scraper** — Scheduled job finds new shoe releases and prints online
3. **Visual Search** — Match an unknown print to known shoes (AWS Rekognition / ML)
4. **Metadata Database** — Brand, model, size, tread ID, source, confidence score (RDS)
5. **Web Interface** — Search UI and admin dashboard (FastAPI + frontend TBD)

## Target Hosting
- **Cloud Provider:** AWS (Amazon Web Services)
- **Storage:** S3 (images) + RDS PostgreSQL (metadata)
- **Compute:** ECS/Fargate (Docker containers)
- **Serverless:** Lambda (image processing triggers)
- **Search:** AWS Rekognition or custom ML via SageMaker
- **Scheduling:** EventBridge (automated scraper runs)
- **CDN:** CloudFront (fast image delivery)

## Key Stakeholders
- Developer / Owner: kigow (tiforensicservices)

## Status
🟡 In Progress — Infrastructure setup phase

## Created
2026-03-01

## Last Updated
2026-03-01
