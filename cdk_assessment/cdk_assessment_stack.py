from constructs import Construct
from aws_cdk import (
    Stack,
    aws_autoscaling as autoscaling,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_rds as rds,
    RemovalPolicy,
)
from aws_cdk.aws_ec2 import Vpc
from aws_cdk.aws_autoscaling import AutoScalingGroup
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
import configparser

# Load the configuration file
config = configparser.ConfigParser()
config.read('config.ini')

# Read values from the configuration
user_data_script = config.get('CDKProject', 'UserDataScript')
min_capacity = config.getint('AutoScalingGroup', 'MinCapacity')
max_capacity = config.getint('AutoScalingGroup', 'MaxCapacity')
desired_capacity = config.getint('AutoScalingGroup', 'DesiredCapacity')
allowed_ports = [int(port) for port in config.get('SecurityGroup', 'AllowedPorts').split(',')]
db_name = config.get('DatabaseInstance', 'DBName')
allocated_storage = config.getint('DatabaseInstance', 'AllocatedStorage')

# Read the database engine version as a string from the config
db_engine_version_str = config.get('DatabaseInstance', 'DBEngineVersion').strip()  # Remove leading/trailing spaces
db_engine_version = None  # Default value

# Map the string to the corresponding enum value
if db_engine_version_str == '8.0.34':
    db_engine_version = rds.MysqlEngineVersion.VER_8_0_34
# Add more mappings as needed for other versions

if db_engine_version is None:
    raise ValueError(f"Unsupported DB engine version: {db_engine_version_str}")


class CdkAssessmentStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Create an IAM Role for SSM
        ssm_role = iam.Role(self, "SSM-Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
        )

        # Attach the AmazonSSMManagedInstanceCore managed policy to the IAM role
        ssm_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))

        vpc = ec2.Vpc(self, 'myVPC',
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                ),
            ],
        )

        my_security_group = ec2.SecurityGroup(self, "MySecurityGroup",
            vpc=vpc,
            description="Allow custom inbound rules",
        )
        
        for port in allowed_ports:
            my_security_group.add_ingress_rule(
                ec2.Peer.ipv4("0.0.0.0/0"),     # All IP addresses
                ec2.Port.tcp(port),             # Allow traffic to the current port in the loop
                description=f"Allow traffic on port {port} to all IP addresses",
            )

        # Create AutoScaling Group
        asg = autoscaling.AutoScalingGroup(self, "myASG",
            vpc=vpc,
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE2, ec2.InstanceSize.MICRO),
            machine_image=ec2.AmazonLinuxImage(generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2),
            min_capacity=min_capacity,
            max_capacity=max_capacity,
            desired_capacity=desired_capacity,
            user_data=ec2.UserData.custom(user_data_script),
            role=ssm_role,      # Attach ssm-role to the instances
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=my_security_group
        )

        # Create Application Load Balancer
        lb = elbv2.ApplicationLoadBalancer(self, "LB", vpc=vpc, internet_facing=True)
        
        # Add a listener for HTTP on port 80 with the specific protocol
        http_listener = lb.add_listener("HTTP-Listener", port=80, protocol=elbv2.ApplicationProtocol.HTTP)
        http_listener.add_targets("ASG-Target", port=80, targets=[asg])

        # Create an RDS Instance
        rds_instance = rds.DatabaseInstance(self, "MyRDSInstance",
            database_name=db_name,
            engine=rds.DatabaseInstanceEngine.mysql(version=db_engine_version),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE2, ec2.InstanceSize.MICRO),
            vpc=vpc,
            security_groups=[my_security_group],
            allocated_storage=allocated_storage,
            multi_az=False,  # Use the value from your config or set it to False
            removal_policy=RemovalPolicy.DESTROY
        )