pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        timestamps()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git log -1 --oneline'
            }
        }

        stage('Verify') {
            steps {
                sh '''
                    test -f docker-compose.yml
                    test -f frontend/Dockerfile
                    test -f backend/spring/Dockerfile
                    test -f backend/fastapi/Dockerfile
                '''
            }
        }

        stage('Deploy') {
            steps {
                sh 'sudo /usr/local/sbin/deploy-s15p21e206'
            }
        }
    }

    post {
        success {
            echo 'Deployment success'
        }

        failure {
            echo 'Deployment failed'
        }
    }
}