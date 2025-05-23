pipeline {
    agent any

    environment {
        REGISTRY = "registry.mymsngroup.com"
        IMAGE = "videodownloader"
        TAG = "latest"
        K8S_DEPLOYMENT = "k8s/videodownloader-deployment.yaml"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                sh "docker build -t $REGISTRY/$IMAGE:$TAG ."
            }
        }

        stage('Push Docker Image') {
            steps {
                sh "docker push $REGISTRY/$IMAGE:$TAG"
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    sh "kubectl --kubeconfig=$KUBECONFIG replace --force -f $K8S_DEPLOYMENT"
                }
            }
        }

        stage('Cleanup Dangling Images') {
            steps {
                sh '''
                    docker image prune -f
                    for i in $(docker images | grep "<none>" | awk \'{print $3}\'); do
                        docker rmi --force $i || true
                    done
                '''
            }
        }
    }
}