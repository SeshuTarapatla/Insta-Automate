from base64 import b64decode
from json import loads
from subprocess import run
from typing import Any


class Kubernetes:
    """Module for all k8s related methods."""
    binary: str = "Rancher Desktop.exe"

    @staticmethod
    def is_running():
        """Checks if K8S cluster is running or not."""
        if run(f'tasklist | findstr "{Kubernetes.binary}"', shell=True, capture_output=True).returncode != 0:
            raise ProcessLookupError("Rancher Desktop is not running.")
    
    @staticmethod
    def get_json(name: str, kind: str, *, base64decode: bool = False) -> dict[str, Any]:
        """Gets K8S json representation of a given resource.

        Args:
            name (str): name of the resource.
            kind (str): kind of the resource.
            base64decode (bool, optional): to decode output json, useful to parse secrets. Defaults to False.

        Raises:
            AttributeError: if given resource is not found in K8S cluster.

        Returns:
            dict[str, Any]: json in python dict.
        """
        resp = run(f"kubectl get {kind} {name} -o jsonpath={{.data}}", capture_output=True, text=True)
        if resp.returncode == 0:
            data: dict[str, str] = loads(resp.stdout)
            if base64decode:
                data = {key: b64decode(value).decode() for key, value in data.items()}
            return data
        else:
            raise AttributeError(f"A kubernetes resource of kind {kind} and name {name} is not found.")
