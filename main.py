from fastapi import FastAPI
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.msi.v2024_11_30 import ManagedServiceIdentityClient
from azure.mgmt.msi.v2024_11_30.models import FederatedIdentityCredential
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import logging
import os, time

app = FastAPI()
logging.basicConfig(level=logging.DEBUG)

credential = DefaultAzureCredential()
subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
tenant_id = os.environ["AZURE_TENANT_ID"]
resource_client = ResourceManagementClient(credential, subscription_id)


def wait_for_namespace_deletion(
    api: client.CoreV1Api, name: str, timeout: int = 60, interval: float = 1.0
):
    start = time.time()
    while True:
        try:
            api.read_namespace(name)
            # still exists
        except ApiException as e:
            if e.status == 404:
                return True
            raise
        if time.time() - start > timeout:
            return False
        time.sleep(interval)


@app.post("/create")
def create_fic(
    fic_name: str, managed_identity: str, rg: str, namespace: str, service_account: str
):
    """
    Create a FIC (Federated Identity Credentials) in the specified namespace
    using the provided service account.
    """
    logging.debug(
        f"Creating FIC for namespace: {namespace} with service account: {service_account}"
    )
    fic_class = FederatedIdentityCredential(
        issuer=f"https://sts.windows.net/{tenant_id}/",
        subject=f"system:serviceaccount:{namespace}:{service_account}",
        audiences=["api://AzureADTokenExchange"],
    )
    msi_client = ManagedServiceIdentityClient(credential, subscription_id)
    msi_client.federated_identity_credentials.create_or_update(
        resource_group_name=rg,
        resource_name=managed_identity,
        federated_identity_credential_resource_name=fic_name,
        parameters=fic_class,
    )

    return {
        "message": "FIC created successfully",
        "namespace": namespace,
        "service_account": service_account,
    }


@app.delete("/delete-fic")
def delete_fic(fic_name: str, rg: str, managed_identity: str):
    """
    Delete a FIC (Federated Identity Credentials) in the specified namespace
    using the provided service account.
    """
    logging.debug(
        f"Deleting FIC for namespace: {fic_name} with service account: {managed_identity}"
    )
    msi_client = ManagedServiceIdentityClient(credential, subscription_id)
    msi_client.federated_identity_credentials.delete(
        resource_group_name=rg,
        resource_name=managed_identity,
        federated_identity_credential_resource_name=fic_name,
    )

    return {
        "message": "FIC delete successfully",
        "namespace": fic_name,
        "service_account": managed_identity,
    }


@app.delete("/delete-k8s")
def delete_k8s_namespace(namespace: str):
    """
    Delete kubernetes namespace.
    """
    logging.debug(f"Deleting FIC for namespace: {namespace}")
    config.load_incluster_config()

    api = client.CoreV1Api()
    body = (
        client.V1DeleteOptions()
    )
    try:
        api.delete_namespace(name=namespace, body=body)
    except ApiException as e:
        if e.status == 404:
            print(f"Namespace '{namespace}' not found (already deleted).")
            return True
        # If API returns conflict/other, re-raise for caller to inspect
        raise

    success = wait_for_namespace_deletion(api, namespace, timeout=100)
    if success:
        print(f"Namespace '{namespace}' deleted.")
        return True

    # timed out; attempt optional force

    print(
        f"Timed out waiting for '{namespace}'. Attempting to remove finalizers to force delete."
    )
    try:
        # Patch metadata.finalizers = [] to force finalizer removal
        body = {"metadata": {"finalizers": []}}
        return api.patch_namespace(namespace, body)
    except ApiException as e:
        print("Failed to patch finalizers:", e)
        raise
    # wait again briefly
    success = wait_for_namespace_deletion(api, name, timeout=30)
    if success:
        print(f"Namespace '{name}' deleted after removing finalizers.")
        return True

    print(
        f"Timed out waiting for namespace '{namespace}' to be removed (still exists)."
    )

    return {"message": "FIC delete successfully", "namespace": namespace}
