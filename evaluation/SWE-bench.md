# SWE-bench Evaluation for Trae Agent

This document explains how to evaluate [Trae Agent](https://github.com/bytedance/trae-agent) using [SWE-bench](https://www.swebench.com/), a benchmark for evaluating language models and agents on software engineering tasks.

## Overview

SWE-bench is a benchmark that evaluates language models on real-world software engineering tasks. It contains GitHub issues from popular Python repositories that have been solved by human developers. The benchmark evaluates whether an agent can generate the correct patch to fix the issue.

The evaluation process involves:
1. **Setup**: Preparing the evaluation environment with Docker containers
2. **Execution**: Running Trae Agent on SWE-bench instances to generate patches
3. **Evaluation**: Testing the generated patches against the ground truth using SWE-bench harness

## Prerequisites

Before running the evaluation, ensure you have:

- **Docker**: Required for containerized evaluation environments
- **Python 3.12+**: For running the evaluation scripts
- **Git**: For cloning repositories
- **Sufficient disk space**: Docker images can be several GBs per instance
- **API Keys**: OpenAI/Anthropic API keys for Trae Agent

## Setup Instructions

Make sure installing extra dependencies for evaluation and running scripts in the `evaluation` directory.

```bash
uv sync --extra evaluation
cd evaluation
```

### 1. Clone and Setup SWE-bench Harness

The `swebench_setup.sh` script automates the setup of SWE-bench harness:

```bash
chmod +x swebench_setup.sh
./swebench_setup.sh
```

This script:
- Clones the SWE-bench repository
- Checks out a specific commit for reproducibility (it is the most recent commit hash at the time of writing this document.)
- Creates a Python virtual environment
- Installs the SWE-bench harness

### 2. Configure Trae Agent

Ensure your `trae_config.json` file is properly configured with valid API keys:

```json
{
  "default_provider": "anthropic",
  "max_steps": 200,
  "model_providers": {
    "anthropic": {
      "api_key": "your_anthropic_api_key",
      "model": "claude-sonnet-4-20250514",
      "max_tokens": 4096,
      "temperature": 0.5
    }
  }
}
```

### 3. Optional: Docker Environment Configuration

Create a `docker_env_config.json` file if you need custom environment variables:

```json
{
  "preparation_env": {
    "HTTP_PROXY": "http://proxy.example.com:8080",
    "HTTPS_PROXY": "https://proxy.example.com:8080"
  },
  "experiment_env": {
    "CUSTOM_VAR": "value"
  }
}
```

## Usage

The evaluation script `swebench.py` provides several modes of operation:

### Basic Usage

```bash
# Run evaluation on all instances of SWE-bench_Verified
python swebench.py --dataset SWE-bench_Verified --working-dir ./trae-workspace

# Run evaluation on specific instances
python swebench.py --instance_ids django__django-12345 scikit-learn__scikit-learn-67890

# Run with custom configuration
python swebench.py --config-file custom_config.json --run-id experiment-1
```

### Available Datasets

- **SWE-bench_Verified**: 500 verified instances (recommended for initial evaluation)
- **SWE-bench_Lite**: 300 instances (smaller subset)
- **SWE-bench**: 2,294 instances (full dataset)

### Evaluation Modes

The script supports three modes:

1. **`expr`** (Expression only): Generate patches without evaluation
2. **`eval`** (Evaluation only): Evaluate existing patches
3. **`e2e`** (End-to-end): Both generate and evaluate patches (default)

```bash
# Only generate patches
python swebench.py --mode expr --dataset SWE-bench_Verified

# Only evaluate existing patches
python swebench.py --mode eval --swebench-harness-path ./SWE-bench

# End-to-end evaluation (default)
python swebench.py --mode e2e --swebench-harness-path ./SWE-bench
```

### Full Command Reference

```bash
python swebench.py \
  --dataset SWE-bench_Verified \
  --config-file ../trae_config_local.json \
  --swebench-harness-path ./SWE-bench \
  --docker-env-config docker_env_config.json \
  --mode e2e
```

**Parameters:**
- `--dataset`: SWE-bench dataset to use
- `--config-file`: Trae Agent configuration file
- `--swebench-harness-path`: Path to SWE-bench harness (required for evaluation)
- `--docker-env-config`: Docker environment configuration file
- `--mode`: Evaluation mode (`e2e`, `expr`, `eval`)

## How It Works

### 1. Image Preparation

The script first checks for required Docker images:
- Each SWE-bench instance has a specific Docker image
- Images are pulled automatically if not present locally
- Base Ubuntu image is used for preparing Trae Agent

### 2. Trae Agent Preparation

The script builds Trae Agent in a Docker container:
- Creates artifacts (`trae-agent.tar`, `uv.tar`, `uv_shared.tar`)
- These artifacts are reused across all instances for efficiency

### 3. Instance Execution

For each instance:
1. **Container Setup**: Prepares a Docker container with the instance's environment
2. **Problem Statement**: Writes the GitHub issue description to a file
3. **Trae Agent Execution**: Runs Trae Agent to generate a patch
4. **Patch Collection**: Saves the generated patch for evaluation

### 4. Evaluation

Using SWE-bench harness:
1. **Patch Collection**: Collects all generated patches into `predictions.json`
2. **Test Execution**: Runs the patches against test suites in Docker containers
3. **Result Generation**: Produces evaluation results with pass/fail status

## Understanding Results

### Output Files

The evaluation creates several files in the working directory:

```
trae-workspace/
├── predictions.json              # Generated patches for evaluation
├── trae-agent.{run-id}.json     # Final evaluation results
├── {instance_id}/
│   ├── problem_statement.txt    # GitHub issue description
│   ├── {instance_id}.patch      # Generated patch
│   └── {instance_id}.json       # Trajectory file
├── trae-agent.tar           # Trae Agent build artifacts
├── uv.tar                   # UV binary
└── uv_shared.tar            # UV shared files
```
