import os
import sys
import urllib.request
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load env variables
load_dotenv()

def get_public_ip():
    try:
        url = 'https://checkip.amazonaws.com'
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.read().decode('utf-8').strip()
    except Exception as e:
        print(f"Warning: Could not detect public IP ({e}). Defaulting to 0.0.0.0")
        return "0.0.0.0"

def main():
    aws_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

    if not aws_key or not aws_secret:
        print("Error: AWS credentials not found in .env file.")
        sys.exit(1)

    print("Connecting to AWS...")
    try:
        session = boto3.Session(
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=region
        )
        ec2_client = session.client('ec2')
        ec2_resource = session.resource('ec2')
    except Exception as e:
        print(f"Failed to connect to AWS: {e}")
        sys.exit(1)

    sg_name = 'aws-vm-sg'
    
    try:
        print(f"Locating security group '{sg_name}'...")
        response = ec2_client.describe_security_groups(GroupNames=[sg_name])
        sg_id = response['SecurityGroups'][0]['GroupId']
        sg = ec2_resource.SecurityGroup(sg_id)
        print(f"Found security group: {sg_name} ({sg_id})")
    except ClientError as e:
        print(f"Error finding security group: {e}")
        sys.exit(1)

    user_ip = get_public_ip()
    jenkins_cidr = f"{user_ip}/32" if user_ip != "0.0.0.0" else "0.0.0.0/0"
    
    # Define rules to add
    ip_permissions = []
    
    # Check if port 80 is already open to 0.0.0.0/0
    port_80_open = False
    port_8080_open = False
    
    for perm in response['SecurityGroups'][0].get('IpPermissions', []):
        from_port = perm.get('FromPort')
        to_port = perm.get('ToPort')
        if from_port == 80 and to_port == 80:
            for ip_range in perm.get('IpRanges', []):
                if ip_range.get('CidrIp') == '0.0.0.0/0':
                    port_80_open = True
        if from_port == 8080 and to_port == 8080:
            for ip_range in perm.get('IpRanges', []):
                if ip_range.get('CidrIp') == jenkins_cidr:
                    port_8080_open = True

    if not port_80_open:
        print(f"Adding rule: Allow HTTP (Port 80) from 0.0.0.0/0")
        ip_permissions.append({
            'IpProtocol': 'tcp',
            'FromPort': 80,
            'ToPort': 80,
            'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'Public web access'}]
        })
    else:
        print("HTTP Port 80 is already authorized for 0.0.0.0/0.")

    if not port_8080_open:
        print(f"Adding rule: Allow Jenkins (Port 8080) from {jenkins_cidr}")
        ip_permissions.append({
            'IpProtocol': 'tcp',
            'FromPort': 8080,
            'ToPort': 8080,
            'IpRanges': [{'CidrIp': jenkins_cidr, 'Description': 'Jenkins access from public IP'}]
        })
    else:
        print(f"Jenkins Port 8080 is already authorized for {jenkins_cidr}.")

    if ip_permissions:
        try:
            sg.authorize_ingress(IpPermissions=ip_permissions)
            print("Security Group inbound rules updated successfully!")
        except ClientError as e:
            print(f"Error authorizing rules: {e}")
            sys.exit(1)
    else:
        print("No new rules need to be added.")

if __name__ == '__main__':
    main()
