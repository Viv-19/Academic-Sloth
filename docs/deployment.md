# Deployment Architecture (AWS)

Academic Sloth is designed to be deployed using a robust, highly available cloud architecture on Amazon Web Services (AWS), utilizing CI/CD pipelines for automated delivery.

## Infrastructure Overview

The production deployment utilizes a combination of managed AWS services and virtual machines to ensure security, scalability, and performance.

### 1. Amazon EC2 (Compute)
The application is hosted on EC2 instances running Amazon Linux 2 or Ubuntu.
- **Backend Instance**: Hosts the Node.js Express server.
- **AI Service Instance**: A separate compute-optimized instance hosts the Python FastAPI application. Keeping the AI service isolated ensures that CPU-intensive tasks (like local embeddings and cross-encoder re-ranking) do not starve the Node.js BFF of resources.

### 2. Application Load Balancer (ALB)
An AWS Application Load Balancer is positioned in front of the EC2 instances.
- **Traffic Routing**: Routes `/api/ai/*` traffic to the Python service and all other `/api/*` traffic to the Node.js service.
- **SSL Termination**: Integrates with AWS Certificate Manager (ACM) to handle HTTPS, securing data in transit.

### 3. Amazon RDS (Database)
- **PostgreSQL**: A managed Amazon RDS instance runs the PostgreSQL database, providing automated backups, patch management, and Multi-AZ deployments for high availability.

### 4. Amazon S3 (Storage)
- **Document Storage**: Uploaded PDFs are stored in an Amazon S3 bucket rather than the local EC2 filesystem. The Node.js application generates pre-signed URLs to grant temporary access to the frontend iframe and the Python parser.

### 5. Vector Database (ChromaDB)
- Currently, ChromaDB utilizes local persistent storage (EBS Volumes attached to the Python EC2 instance). 
- *Scaling Consideration*: As the dataset grows, this can be migrated to a managed cloud vector database (e.g., Pinecone or AWS OpenSearch Serverless).

## CI/CD Pipeline (GitHub Actions)

Continuous Integration and Continuous Deployment are managed via GitHub Actions to ensure reliable releases.

### 1. Continuous Integration (CI)
Triggered on pull requests and pushes to the `main` branch.
- **Linting & Formatting**: Runs ESLint for Node.js and Flake8/Black for Python.
- **Automated Testing**: Executes unit and integration tests.
- **Build Verification**: Ensures Prisma schema is valid and dependencies resolve successfully.

### 2. Continuous Deployment (CD)
Triggered upon a successful merge to `main`.
- **Secrets Management**: Injects environment variables securely from GitHub Secrets (e.g., Database URI, Groq API Keys).
- **AWS CodeDeploy / SSM**: GitHub Actions triggers AWS CodeDeploy (or utilizes AWS Systems Manager Run Command) to execute deployment scripts on the EC2 instances.
- **Deployment Steps**:
  1. Pulls the latest code from the repository.
  2. Runs `npm install` and `prisma generate` for the backend.
  3. Runs `pip install -r requirements.txt` for the AI service.
  4. Restarts both services using a process manager like `PM2` (Node.js) and `systemd` (Python/Uvicorn) to achieve zero-downtime deployments.

## Security Configurations

- **AWS Systems Manager (Parameter Store)**: Used to securely inject production secrets (`JWT_SECRET`, database passwords) into the EC2 instances at runtime, ensuring they are never checked into version control.
- **Security Groups**: 
  - EC2 instances are placed in private subnets, only accessible via the ALB.
  - RDS is strictly locked down to only accept connections from the backend EC2 instance's security group.
