import os
import sys
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def main():
    aws_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

    if not aws_key or not aws_secret:
        print("Error: AWS credentials not found in .env file.")
        sys.exit(1)

    print("Initializing AWS session...")
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

    # VM Details
    instance_id = "i-01761cb7f020219f3"
    key_name = "aws-vm-key"
    key_file = f"{key_name}.pem"
    sg_name = "aws-vm-sg"

    print("\nStarting clean up sequence...")

    # 1. Terminate the EC2 instance
    try:
        print(f"Terminating EC2 Instance '{instance_id}'...")
        instance = ec2_resource.Instance(instance_id)
        instance.terminate()
        
        print("Waiting for instance to terminate (this may take a couple of minutes)...")
        instance.wait_until_terminated()
        print(f"EC2 Instance '{instance_id}' terminated successfully.")
    except ClientError as e:
        if 'InvalidInstanceID.NotFound' in str(e):
            print(f"Instance '{instance_id}' does not exist or has already been deleted.")
        else:
            print(f"Error terminating instance: {e}")

    # 2. Delete Security Group
    try:
        print(f"Deleting Security Group '{sg_name}'...")
        # Need to find the group ID first
        response = ec2_client.describe_security_groups(GroupNames=[sg_name])
        sg_id = response['SecurityGroups'][0]['GroupId']
        ec2_client.delete_security_group(GroupId=sg_id)
        print(f"Security Group '{sg_name}' ({sg_id}) deleted successfully.")
    except ClientError as e:
        if 'InvalidGroup.NotFound' in str(e):
            print(f"Security Group '{sg_name}' not found.")
        elif 'DependencyViolation' in str(e):
            print(f"Warning: Could not delete security group yet: {e}")
            print("You may need to delete it manually from the AWS Console once all interfaces are detached.")
        else:
            print(f"Error deleting security group: {e}")

    # 3. Delete Key Pair
    try:
        print(f"Deleting Key Pair '{key_name}' from AWS...")
        ec2_client.delete_key_pair(KeyName=key_name)
        print(f"Key Pair '{key_name}' deleted from AWS.")
    except Exception as e:
        print(f"Error deleting key pair: {e}")

    # 4. Remove local private key file
    if os.path.exists(key_file):
        try:
            os.remove(key_file)
            print(f"Removed local private key file '{key_file}'.")
        except Exception as e:
            print(f"Warning: Could not delete local file '{key_file}': {e}")

    print("\nCleanup completed successfully!\n")

if __name__ == '__main__':
    main()
