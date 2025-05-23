#!/bin/bash
set -e

kubectl replace --force -f videodownloader-namespace.yaml
kubectl replace --force -f videodownloader-pvc.yaml
kubectl replace --force -f videodownloader-deployment.yaml
kubectl replace --force -f videodownloader-service.yaml
kubectl replace --force -f videodownloader-ingress.yaml