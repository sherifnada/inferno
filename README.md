# INFERno
A trial by fire in running an inference backend

## No but really, what is this?
This is a local kube emulation of an inference cluster.

The cluster is structured as follows: 
- One VLLM deployment per LLM (TinyLlama-1.1B-Chat and LLAMA 3.2 11B Vision Instruct)
- One FastAPI deployment that receives requests and sits in front of the VLLM servers
- Dashboard containing GPU utilization, request latency, volume, and throughput



## Prereqs
* Docker
* kubectl
* kind
* GH CLI
* 1xH100 Lambda on-demand instance (you can probably run this on any old x86 instance with an NVIDIA GPU, I just didn't test it on all of them because I need money for groceries)


### Initial Setup

First, ssh to your on-demand instance.

Then install [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/#install-using-native-package-management), [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installing-from-release-binaries), and the [GH CLI](https://github.com/cli/cli/blob/trunk/docs/install_linux.md).

Install `jq`:
```bash
sudo apt install -y jq
```

Then clone this repo
```bash
git clone git@github.com:sherifnada/inferno.git
```

Edit your `.env` file: 

```bash
cd inferno
cp .env.example .env
vim .env # then add the correct values
```

Make sure everything works fine by running
```bash
sudo docker pull vllm/vllm-openai
sudo docker run \
  --gpus all \
  --ipc=host \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -p 8000:8000 \
  --env-file .env \
  vllm/vllm-openai --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
    --disable-log-requests
```

Then in a separate SSH terminal or tmux window run: 
```bash
curl -X POST http://localhost:8000/v1/chat/completions   -H "Content-Type: application/json"   -d '{
    "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "messages": [
      {"role": "user", "content": "What is the capital of France?"}
    ],
    "temperature": 0.0,
    "max_tokens": 20
  }' | jq
```

You should see a response like: 

```bash
{
  "id": "chatcmpl-ae6e526144b7433fa38058d10b4c57c9",
  "object": "chat.completion",
  "created": 1748842347,
  "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "reasoning_content": null,
        "content": "The capital of France is Paris.",
        "tool_calls": []
      },
      "logprobs": null,
      "finish_reason": "stop",
      "stop_reason": null
    }
  ],
  "usage": {
    "prompt_tokens": 23,
    "total_tokens": 31,
    "completion_tokens": 8,
    "prompt_tokens_details": null
  },
  "prompt_logprobs": null,
  "kv_transfer_params": null
}
```

## Setup Kube Cluster
```bash
# Create the kind cluster
kind create cluster --config kind-gpu.yaml

# Verify the kind cluster is running
kubectl cluster-info --context kind-inferno


```