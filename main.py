from fastapi import FastAPI
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.msi.v2022_01_31_preview import ManagedServiceIdentityClient
from azure.mgmt.msi.v2022_01_31_preview.models import FederatedIdentityCredential
import logging
import os, sys

app = FastAPI()
logging.basicConfig(level=logging.DEBUG)

credential = DefaultAzureCredential()
subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
tenant_id = "0f510a1b-c5e3-4209-8b58-1312c3193849"
resource_client = ResourceManagementClient(credential, subscription_id)


@app.post("/")
def create_fic(fic_name: str, managed_identity: str, rg: str, namespace: str, service_account: str):
    """
    Create a FIC (Federated Identity Credentials) in the specified namespace
    using the provided service account.
    """
    logging.debug(f"Creating FIC for namespace: {namespace} with service account: {service_account}")
    fic_class = FederatedIdentityCredential(
        issuer=f"https://sts.windows.net/{tenant_id}/",
        subject=f"system:serviceaccount:{namespace}:{service_account}",
        audiences=["api://AzureADTokenExchange"]
    )
    msi_client = ManagedServiceIdentityClient(credential, subscription_id)
    msi_client.federated_identity_credentials.create_or_update(
        resource_group_name=rg,
        resource_name=managed_identity,
        federated_identity_credential_resource_name=fic_name,
        parameters=fic_class
    )
    
    return {"message": "FIC created successfully", "namespace": namespace, "service_account": service_account}
    

