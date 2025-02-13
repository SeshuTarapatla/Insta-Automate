from utils.kubernetes import Kubernetes


Kubernetes.is_running()
print(Kubernetes.get_json("postgres-configmap", "configmap"))