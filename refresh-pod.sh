#!/bin/bash

podman_name=test-pod
yaml_file=podman_pod.yaml

podman pod kill $podman_name
podman pod rm $podman_name
podman play kube $yaml_file