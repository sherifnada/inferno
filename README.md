# INFERno
A trial by fire in running an inference backend

## No but really, what is this?
This is a local kube emulation of an inference cluster (CPU-backed, because the dog ate my H100). 

The cluster is structured as follows: 
- One deployment per LLM
- 



## Prereqs
* Docker
* kubectl
* kind
* GH CLI
* 1xH100 Lambda on-demand instance


### Setup

```bash
git clone git@github.com:sherifnada/inferno.git
```



## Quick Start
```bash
kind create cluster --image kindest/node:v1.30.0
kubectl apply -f k8s/
# (optional) kubectl apply -f k8s/hpa-fastapi.yaml
kubectl get pods -A
kubectl port-forward svc/fastapi-gateway 8080:80
curl -X POST http://localhost:8080/v1/chat/completions -d '{"prompt":"hello"}'
```