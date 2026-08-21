import os
import sys
import urllib.request
import subprocess
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_public_ip():
    """Gets the public IP of the current machine."""
    try:
        url = 'https://checkip.amazonaws.com'
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.read().decode('utf-8').strip()
    except Exception as e:
        print(f"Warning: Could not detect public IP ({e}). Defaulting to allow SSH from anywhere (0.0.0.0/0).")
        return "0.0.0.0"

def set_key_permissions_windows(key_path):
    """Sets restricted permissions on key file for Windows OpenSSH client using icacls."""
    try:
        # Get absolute path of the key
        abs_key_path = os.path.abspath(key_path)
        # Remove inheritance
        subprocess.run(["icacls.exe", abs_key_path, "/inheritance:r"], check=True, capture_output=True)
        # Grant read/write permission to the current user only
        username = os.environ.get("USERNAME") or os.environ.get("USER")
        if username:
            subprocess.run(["icacls.exe", abs_key_path, "/grant:r", f"{username}:F"], check=True, capture_output=True)
            print(f"Set file permissions for Windows on {key_path} for user {username}.")
        else:
            print("Warning: Could not determine current username. Please check key permissions manually if SSH fails.")
    except Exception as e:
        print(f"Warning: Could not set file permissions for Windows using icacls ({e}).")

def main():
    # 1. Validate credentials
    aws_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    use_localstack = os.getenv('USE_LOCALSTACK', 'false').lower() == 'true'

    if not use_localstack and (not aws_key or not aws_secret):
        print("Error: AWS credentials not found in .env file.")
        print("Please open the '.env' file in your editor and provide AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.")
        sys.exit(1)

    # In localstack mode, if keys are missing we default them to 'test'
    if use_localstack:
        aws_key = aws_key or 'test'
        aws_secret = aws_secret or 'test'

    print("Initializing AWS session...")
    try:
        session = boto3.Session(
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=region
        )
        endpoint_url = 'http://localhost:4566' if use_localstack else None
        
        ec2_client = session.client('ec2', endpoint_url=endpoint_url)
        ec2_resource = session.resource('ec2', endpoint_url=endpoint_url)
        
        # Test connection by getting caller identity
        sts_client = session.client('sts', endpoint_url=endpoint_url)
        caller = sts_client.get_caller_identity()
        print(f"Connected to AWS Account: {caller['Account']} (User/Role ARN: {caller['Arn']})")
        if use_localstack:
            print("--- RUNNING IN LOCALSTACK SIMULATION MODE ---")
    except ClientError as e:
        print(f"Authentication Error: {e}")
        print("Please check your Access Key ID and Secret Access Key in the '.env' file.")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to connect to AWS: {e}")
        sys.exit(1)

    # 2. Get Public IP
    user_ip = get_public_ip()
    ssh_cidr = f"{user_ip}/32" if user_ip != "0.0.0.0" else "0.0.0.0/0"
    print(f"Detected Public IP: {user_ip}. SSH access will be limited to: {ssh_cidr}")

    # 3. Create or Locate Key Pair
    key_name = 'aws-vm-key'
    key_file = f"{key_name}.pem"
    
    try:
        print(f"Checking for existing key pair '{key_name}'...")
        ec2_client.describe_key_pairs(KeyNames=[key_name])
        print(f"Key pair '{key_name}' already exists in AWS.")
        if not os.path.exists(key_file):
            print(f"Warning: Key pair '{key_name}' exists in AWS but local file '{key_file}' is missing!")
            print("To recreate, terminate the VM, delete the key pair in the AWS console/CLI, and run this script again.")
    except ClientError as e:
        if 'InvalidKeyPair.NotFound' in str(e):
            print(f"Key pair '{key_name}' not found. Creating a new one...")
            key_pair = ec2_resource.create_key_pair(KeyName=key_name, KeyType='rsa')
            # Save key content locally
            with open(key_file, 'w') as f:
                f.write(key_pair.key_material)
            print(f"Saved private key locally to: {key_file}")
            
            # Set permissions
            if os.name == 'nt':
                set_key_permissions_windows(key_file)
            else:
                os.chmod(key_file, 0o400)
        else:
            print(f"Error checking/creating key pair: {e}")
            sys.exit(1)

    # 4. Create or Locate Security Group
    sg_name = 'aws-vm-sg'
    sg_desc = 'Security Group for AWS VM allowing SSH'
    sg_id = None
    
    try:
        print(f"Checking for existing security group '{sg_name}'...")
        response = ec2_client.describe_security_groups(GroupNames=[sg_name])
        sg_id = response['SecurityGroups'][0]['GroupId']
        print(f"Found existing security group: {sg_name} ({sg_id})")
    except ClientError as e:
        if 'InvalidGroup.NotFound' in str(e):
            print(f"Security group '{sg_name}' not found. Creating...")
            # Find default VPC
            vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'is-default', 'Values': ['true']}])
            if not vpcs['Vpcs']:
                # If no default VPC, list available VPCs
                vpcs = ec2_client.describe_vpcs()
            if not vpcs['Vpcs']:
                print("Error: No VPCs found in your AWS account in this region.")
                sys.exit(1)
            vpc_id = vpcs['Vpcs'][0]['VpcId']
            
            sg = ec2_resource.create_security_group(
                GroupName=sg_name,
                Description=sg_desc,
                VpcId=vpc_id
            )
            sg_id = sg.id
            print(f"Created Security Group {sg_name} ({sg_id}) in VPC {vpc_id}")
            
            # Add SSH inbound rule
            print(f"Adding inbound rule: Allow SSH (Port 22) from {ssh_cidr}")
            sg.authorize_ingress(
                IpPermissions=[
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 22,
                        'ToPort': 22,
                        'IpRanges': [{'CidrIp': ssh_cidr, 'Description': 'SSH access from detected public IP'}]
                    }
                ]
            )
        else:
            print(f"Error checking/creating security group: {e}")
            sys.exit(1)

    # 5. Find the latest Amazon Linux 2023 AMI
    print("Finding the latest Amazon Linux 2023 AMI...")
    try:
        response = ec2_client.describe_images(
            Filters=[
                {'Name': 'name', 'Values': ['al2023-ami-2023.*-kernel-6.1-x86_64']},
                {'Name': 'state', 'Values': ['available']},
                {'Name': 'image-type', 'Values': ['machine']}
            ],
            Owners=['amazon']
        )
        images = response['Images']
        if not images:
            # Fallback filter just in case
            response = ec2_client.describe_images(
                Filters=[
                    {'Name': 'name', 'Values': ['amzn2-ami-hvm-2.*-x86_64-gp2']},
                    {'Name': 'state', 'Values': ['available']}
                ],
                Owners=['amazon']
            )
            images = response['Images']
        
        if not images:
            print("Error: Could not find Amazon Linux AMI in this region.")
            sys.exit(1)
            
        images.sort(key=lambda x: x['CreationDate'], reverse=True)
        ami_id = images[0]['ImageId']
        ami_name = images[0]['Name']
        print(f"Selected AMI: {ami_id} ({ami_name})")
    except Exception as e:
        print(f"Error finding AMI: {e}")
        sys.exit(1)

    # 6. Launch the EC2 Instance
    print("Launching EC2 instance...")
    try:
        instances = ec2_resource.create_instances(
            ImageId=ami_id,
            MinCount=1,
            MaxCount=1,
            InstanceType='t2.micro',
            KeyName=key_name,
            SecurityGroupIds=[sg_id],
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [{'Key': 'Name', 'Value': 'AWS-VM-EC2'}]
                }
            ]
        )
        instance = instances[0]
        print(f"Instance '{instance.id}' creation initiated. Waiting for instance to start...")
        
        # Wait for the instance to enter running state
        instance.wait_until_running()
        instance.reload() # Refresh instance details
        
        print("\n" + "="*50)
        print("AWS VM SUCCESSFULLY CREATED!")
        print("="*50)
        print(f"Instance ID:   {instance.id}")
        print(f"Instance Type: {instance.instance_type}")
        print(f"Public IP:     {instance.public_ip_address}")
        print(f"State:         {instance.state['Name']}")
        print(f"Key Pair File: {key_file}")
        print("-"*50)
        print("To connect via SSH, run:")
        print(f"ssh -i {key_file} ec2-user@{instance.public_ip_address}")
        print("="*50 + "\n")
        
    except Exception as e:
        print(f"Error launching EC2 instance: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
