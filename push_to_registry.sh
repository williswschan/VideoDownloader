#!/bin/bash

docker tag videodownloader williswschan/videodownloader:latest
docker push williswschan/videodownloader:latest

docker tag videodownloader registry.mymsngroup.com/videodownloader:latest
docker push registry.mymsngroup.com/videodownloader:latest