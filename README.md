# simple-webpage-hosting-test

A web application project built with VS Code + Cline (AI assistant), developed inside a Docker Dev Container, and targeted for deployment on AWS.

## 🚀 Getting Started

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [VS Code](https://code.visualstudio.com/)
- [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-containers)

### Running in a Dev Container (Recommended)
1. Clone the repository:
   ```bash
   git clone https://github.com/tiforensicservices/simple-webpage-hosting-test.git
   cd simple-webpage-hosting-test
   ```
2. Open in VS Code:
   ```bash
   code .
   ```
3. When prompted **"Reopen in Container"** — click it!
4. VS Code will build the container and install all dependencies automatically.

## 📁 Project Structure
```
.
├── .devcontainer/          # Dev Container configuration
├── .github/                # GitHub Actions (CI/CD)
├── memory-bank/            # Project documentation & progress tracking
├── src/                    # Application source code
├── tests/                  # Tests
├── docs/                   # Additional documentation
├── .clinerules             # Cline AI assistant rules
├── .gitignore
└── README.md
```

## 🛠️ Tech Stack
| Category | Technology |
|----------|-----------|
| Language | Python 3.13 / JavaScript |
| Container | Docker (Dev Containers) |
| Version Control | Git + GitHub |
| Cloud | AWS |
| AI Assistant | Cline (Claude) |

## 📋 Development Guidelines
See [`.clinerules`](.clinerules) for coding standards and best practices.

## 📊 Progress
See [`memory-bank/progress.md`](memory-bank/progress.md) for current status and known issues.

## 🔐 Secrets & API Keys

- Copy `.env.example` to `.env` and fill in your values for local development.
- Never commit `.env` — this repository's `.gitignore` already excludes it.
- For production, prefer a secrets manager (AWS Secrets Manager, Azure Key Vault, GCP Secret Manager) or platform-provided environment variables.
- If a secret is accidentally committed or shared, rotate it immediately.

Example local workflow:

```bash
cp .env.example .env
# edit .env and set API_KEY and other secrets
```

Access from Python using the project's `src/config.py` helper:

```py
from src.config import get_config
cfg = get_config()
print(bool(cfg.api_key))  # True if configured (do not print the key itself)
```

## ☁️ AWS Deployment
Deployment documentation will be added once the deployment method is decided.

---
*Developed with ❤️ using VS Code + Cline*
