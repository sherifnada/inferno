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
* 1xH100 Lambda on-demand instance (you can probably run this on any old x86 instance with an NVIDIA GPU, I just didn't test it on all of them because I need money for groceries)


# Setup

First, ssh to your on-demand instance.

Then install [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/#install-using-native-package-management) and the [GH CLI](https://github.com/cli/cli/blob/trunk/docs/install_linux.md).

Install K3s and `jq`:
```bash
# Install K3s
curl -sfL https://get.k3s.io | K3S_KUBECONFIG_MODE=644 sh -s - --default-runtime=nvidia

# Ensure the cluster is running 
k3s kubectl get nodes

# Install socat
sudo apt -y install socat

# Install jq
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

Then turn off the docker container using `docker stop`

## Enable MIG

Before we do anything, we need to enable Multi-instance GPU mode (MIG). This allows running multiple models on the same GPU. 

```bash
# turn MIG mode on
sudo nvidia-smi -i 0 -mig 1

# Create two 4g/40gb slices.
sudo nvidia-smi mig -cgi 19,19 -C

# Verify it worked: should list GPU 0: MIG 1g...etc. twice
```


## Setup Kube Cluster

```bash
# Install GPU operator
k3s kubectl apply -f k8s/nvidia-gpu-operator.yaml
```

## Deploy models

### TinyLlama
**Note**: At this point we're going to run a few blocking operations. So it's best to run `tmux` then `Ctrl^B` then `C` to create a new window after we run each of these operations.

```bash
tmux # Open a new tmux session

# Deploy Tinyllama and port-forward it so it's available outside the cluster
k3s kubectl apply -f k8s/tinyllama-vllm.yaml
k3s kubectl port-forward svc/tinyllama 8000:8000

# Wait a few minutes for the model to download and run. 
# You can monitor its status via k3s kubectl get pods.

# Now type ctrl^B then C to open a new tmux window

# Validate tinyllama is running
curl -X POST http://localhost:8000/v1/chat/completions   -H "Content-Type: application/json"   -d '{
    "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "messages": [
      {"role": "user", "content": "What is the capital of Spain?"}
    ],
    "temperature": 0.0,
    "max_tokens": 20
  }' | jq
```

### Llama3 11B-Vision
```bash
k3s kubectl apply -f k8s/llama11b-vllm.yaml

# watch until Running
k3s kubectl get pods -w

# forward the new service on a second tmux pane
k3s kubectl port-forward svc/llama11b 8001:8000
```

Again now open a new tmux window using `ctrl+b` then `c`, then smoke test that