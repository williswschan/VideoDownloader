#!/bin/bash
set -e

kubectl delete -f videodownloader-ingress.yaml --ignore-not-found
kubectl delete -f videodownloader-service.yaml --ignore-not-found
kubectl delete -f videodownloader-deployment.yaml --ignore-not-found
kubectl delete -f videodownloader-pvc.yaml --ignore-not-found
kubectl delete -f videodownloader-namespace.yaml --ignore-not-found