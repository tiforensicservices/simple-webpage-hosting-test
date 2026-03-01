# System Patterns

## Architecture Overview
This project follows a containerized development workflow targeting AWS cloud hosting.

```
Developer (Windows 11 + VS Code)
    ↓
Dev Container (Docker)          ← All development happens here
    ↓
Git / GitHub                    ← Version control and collaboration
    ↓
AWS                             ← Production hosting
```

## Development Principles
1. **Container-first development** — No project dependencies installed directly on host PC
2. **Git for everything** — Every change committed with a meaningful message
3. **Document as you go** — Memory bank updated after significant changes
4. **Never commit secrets** — `.env` files always in `.gitignore`
5. **Small, focused commits** — Prefer many small commits over large ones

## Branching Strategy (Git Flow Lite)
- `main` — Production-ready code only
- `develop` — Integration branch for features
- `feature/[name]` — Individual feature branches
- `fix/[name]` — Bug fix branches

## File Structure Convention
```
project-root/
├── .devcontainer/          # Docker dev environment config
├── .github/                # GitHub Actions workflows (CI/CD)
├── memory-bank/            # Cline project memory files
├── src/                    # Application source code
├── tests/                  # Test files
├── docs/                   # Documentation
├── .clinerules             # Cline behavior and standards
├── .gitignore
└── README.md
```

## AWS Deployment Patterns (TBD)
Options being considered:
- **Static Site:** S3 + CloudFront (simplest, cheapest)
- **App Server:** EC2 or Elastic Beanstalk (Python/Flask)
- **Containers:** ECS/Fargate (Docker-based)
- **Serverless:** Lambda + API Gateway
