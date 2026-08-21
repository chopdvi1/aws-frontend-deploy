#!/bin/bash
set -e

echo "=================================================="
echo "STARTING SERVICES INSTALLATION ON EC2 INSTANCE"
echo "=================================================="

# Update system packages
echo "Updating packages..."
sudo dnf update -y

# 1. Install Java 21 (Amazon Corretto)
echo "Installing Java 21..."
sudo dnf install java-21-amazon-corretto-devel -y

# 2. Install Git
echo "Installing Git..."
sudo dnf install git -y

# 3. Add Jenkins repository and import key
echo "Adding Jenkins repository..."
sudo wget -O /etc/yum.repos.d/jenkins.repo https://pkg.jenkins.io/redhat-stable/jenkins.repo
sudo rpm --import https://pkg.jenkins.io/redhat-stable/jenkins.io-2023.key

# 4. Install Jenkins
echo "Installing Jenkins..."
sudo dnf install jenkins -y

# 5. Optimize Jenkins JVM Memory for t2.micro (1 GiB RAM)
# We limit heap memory to 256MB max (-Xmx256m) to prevent OOM crashes on the micro instance.
echo "Configuring Jenkins memory limitations..."
sudo mkdir -p /etc/systemd/system/jenkins.service.d/
cat <<EOF | sudo tee /etc/systemd/system/jenkins.service.d/override.conf
[Service]
Environment="JAVA_OPTS=-Djava.awt.headless=true -Xmx256m -Xms128m"
EOF

sudo systemctl daemon-reload

# 6. Start and Enable Jenkins
echo "Starting Jenkins..."
sudo systemctl enable jenkins
sudo systemctl start jenkins

# 7. Install and Start Nginx
echo "Installing Nginx..."
sudo dnf install nginx -y

# Enable and start Nginx
echo "Starting Nginx..."
sudo systemctl enable nginx
sudo systemctl start nginx

# 8. Configure Directory Permissions for Deployment
# The 'jenkins' user needs write permission to Nginx's HTML folder.
echo "Configuring permissions for Jenkins deploy..."
sudo usermod -aG nginx jenkins
sudo chown -R root:nginx /usr/share/nginx/html
sudo chmod -R 775 /usr/share/nginx/html

# Clean up default Nginx welcome page files to prevent overrides
sudo rm -f /usr/share/nginx/html/index.html

echo "=================================================="
echo "INSTALLATION COMPLETE!"
echo "Jenkins is running on: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8080"
echo "Nginx is running on:   http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):80"
echo "Initial Jenkins admin password is:"
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
echo "=================================================="
