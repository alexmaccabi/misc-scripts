from __future__ import print_function
from kubernetes import client, config
import argparse
import os
import re

def discover_running_images():
    #print("Discovering images in k8s")

    config.load_kube_config()  # Load Kubernetes configuration from default location or provide your own kubeconfig path

    running_containers = []

    v1 = client.CoreV1Api()

    # List all pods in all namespaces
    pods = v1.list_pod_for_all_namespaces(watch=False)

    for pod in pods.items:
        containers = pod.spec.containers
        for container in containers:
            if '.dkr.ecr.' in container.image and ":" in container.image:
                if container.image not in running_containers:
                    running_containers.append(container.image)

    #print("Images that are running from pods:")
    for image in running_containers:
        print(image)

# Below is the test harness
if __name__ == '__main__':
    discover_running_images()