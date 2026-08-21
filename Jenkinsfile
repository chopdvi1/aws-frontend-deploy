pipeline {
    agent any

    stages {
        stage('Deploy') {
            steps {
                echo 'Deploying frontend page to Nginx...'
                // Copy HTML and CSS files to Nginx web root
                sh 'cp index.html /usr/share/nginx/html/'
                sh 'cp style.css /usr/share/nginx/html/'
                echo 'Deployment successful!'
            }
        }
    }

    post {
        success {
            echo 'Pipeline executed successfully!'
        }
        failure {
            echo 'Pipeline execution failed. Check console logs.'
        }
    }
}
