# INFERno
A trial by fire in running an inference backend

## No but really, what is this?
This is a very simple toy example of running an inference cluster.

The cluster is structured as follows: 
- One VLLM deployment per LLM (TinyLlama-1.1B-Chat and the bimodal Qwen2.5-VL-7B)
- One FastAPI deployment that receives requests and sits in front of the VLLM servers



## Prereqs
* Docker
* kubectl
* 1xH100 Lambda on-demand instance (you can probably run this on any old x86 instance with an NVIDIA GPU, I just didn't test it on all of them because I need money for groceries)


# Setup

First, ssh to your on-demand instance.

Then install [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/#install-using-native-package-management) and the [GH CLI](https://github.com/cli/cli/blob/trunk/docs/install_linux.md).

## Setup instance

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

## Setup Kube Cluster

```bash
# Install GPU operator
k3s kubectl apply -f k8s/nvidia-gpu-operator.yaml

# Set the cluster MiG policy to 'mixed'
k3s kubectl patch clusterpolicies.nvidia.com/cluster-policy --type=json -p='[{"op":"replace","path":"/spec/mig/strategy","value":"mixed"}]'

# Define custom mig slices 3g.40gb and 4g.40gb
k3s kubectl apply -f k8s/mig-config-map.yaml

# overwrite the node label to create those mig slices
k3s kubectl label --overwrite node $(k3s kubectl get nodes -o jsonpath='{.items[0].metadata.name}') nvidia.com/mig.config=all-4g3g

# check the logs to see if it worked
k3s kubectl -n gpu-operator logs -f ds/nvidia-mig-manager

# Restart the daemonset to apply changes
k3s kubectl -n gpu-operator rollout restart ds/nvidia-device-plugin-daemonset

# Run nvidia-smi to check if the mig slices exist
k3s kubectl -n gpu-operator exec $(kk -n gpu-operator get pods | grep 'mig-manager' | awk '{print $1}') -t -- nvidia-smi -L
```

## Deploy models

### TinyLlama
**Note**: At this point we're going to run a few blocking operations. So it's best to run `tmux` then `ctrl^b` then `c` to create a new window after we run each of these operations.

```bash
tmux # Open a new tmux session

# Setup Hugging face API key as a secret
k3s kubectl create secret generic hf-credentials \
      --from-literal=HUGGING_FACE_HUB_TOKEN=$(grep '^HUGGING_FACE_HUB_TOKEN=' .env | cut -d '=' -f2-) \
      -n default

# Deploy Tinyllama and port-forward it so it's available outside the cluster
k3s kubectl apply -f k8s/models/tinyllama-vllm.yaml

# Make sure the pod started correctly
k3s kubectl get pods -w

# Port forward so it's available outside the clusters
k3s kubectl port-forward service/tinyllama 8000:8000

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

### Qwen2.5 VL 7B
This is a bimodal LLM so we can play around with image based inference as well.

```bash
k3s kubectl apply -f k8s/models/qwen2.5-vl-7b-vllm.yaml

# watch until Running
k3s kubectl get pods -w

# forward the new service on a second tmux pane
k3s kubectl port-forward service/qwen2-5-vl-7b 8001:8000
```

Again now open a new tmux session using `ctrl-b` then `c` and smoke test the model is working:

```bash
# Test the multimodal model is working
curl -X POST http://localhost:8001/v1/chat/completions   -H "Content-Type: application/json"   -d '{
    "model": "Qwen/Qwen2.5-VL-7B-Instruct",
    "messages": [
      {"role": "user", "content": [
        {
          "type": "text",
          "text": "Describe this image"
        }, 
        {
          "type": "image_url",
          "image_url": {"url": "https://placecats.com/neo/300/200.jpeg"}
        }
      ]}
    ],
    "temperature": 0.0,
    "max_tokens": 20
  }' | jq
```

## Deploy FastAPI gateway
This component is here as a demonstrate having an "app layer" in front of our compute deployments where you could do anything like caching, custom batching, auth, billing, custom telemtry, feature flagging, whatever. The component in this repo just proxies requests and does very basic error handling, but you can imagine how it could do a lot more.

First, build the server image and make it available to k3s: 
```bash
sudo docker build -t fastapi-gateway:local .
sudo docker save fastapi-gateway:local | sudo k3s ctr images import -
```

Then run it: 

```bash
k3s kubectl apply -f k8s/fastapi-gateway.yaml
k3s kubectl get pods -w
k3s kubectl port-forward service/fast-api-gateway 8080:80
```

Now test that it's running correctly: 

```bash
curl -X POST http://localhost:8080/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model":"TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  "messages":[{"role":"user","content":"Paris?"}],
  "temperature":0.0,
  "max_tokens":16
}' | jq .

curl -X POST http://localhost:8080/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model":"Qwen/Qwen2.5-VL-7B-Instruct",
  "messages":[{"role":"user","content":"say hello"}],
  "temperature":0.0,
  "max_tokens":16
}' | jq .
```

At this point, you should stop port forwarding to the vLLM servers directly and use the fastapi gateway. 