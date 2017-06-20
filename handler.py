# Copyright (c) 2017 Sailthru, Inc., https://www.sailthru.com/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import re
import boto3
import os
import sys
from datetime import timedelta

# Load the bundled libraries inside vendored/ directory
here = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(here, "vendored/"))

import requests
from flowdock import Chat
import re


# PutImage is triggered by ECS API events.
def parrot(event, context):
    # debug
    print "Input event:"
    print json.dumps(event);

    message = ''
    ignore_quiet = False

    if (event['detail']['eventName'] == 'StopTask'):
        # A task has been terminated via the ECS API either by a human on the
        # console or a utility/tool of some kind.
        message = ':skull:'
        service_name = event['detail']['responseElements']['task']['group'].rsplit(':', 1)[1]
        reason = event['detail']['responseElements']['task']['stoppedReason']
        message += " "+ service_name +" stopped due to "+ reason

        # As these are somewhat unusual events for us, break quiet.
        ignore_quiet = True

    elif (event['detail']['eventName'] == 'SubmitTaskStateChange'):
        # A container has changed state - typically RUNNING->STOPPED or
        # STOPPED->RUNNING
        if (event['detail']['requestParameters']['status'] == "RUNNING"):
            message = ':hatching_chick: Launched task'
        elif (event['detail']['requestParameters']['status'] == "STOPPED"):
            message = ':skull: Stopped task'

        # Get some fundamentals around the task.
        task_arn        = event['detail']['requestParameters']['task']
        task_uuid       = task_arn.rsplit('/', 1)[1]
        task_short_uuid = task_uuid.split('-', 1)[0]
        cluster_name    = event['detail']['requestParameters']['cluster']
        task_details    = describe_task(cluster_name, task_arn)

        # Add a link to the task console
        task_link = 'https://console.aws.amazon.com/ecs/home?region=' + os.environ['AWS_DEFAULT_REGION'] +'#/clusters/'+ cluster_name +'/tasks/' + task_uuid
        message += ' <'+ task_link +'|'+ task_short_uuid + '>'

        # Add the most human friendly name possible for the service and hyper
        # link it to the console.
        if task_details:
            service_name = task_details['group'].split(':', 1)[1]
            service_link = 'https://console.aws.amazon.com/ecs/home?region=' + os.environ['AWS_DEFAULT_REGION'] +'#/clusters/'+ cluster_name +'/services/'+ service_name +'/tasks'

            message += ' in <'+ service_link +'|'+ service_name + '>'
        else:
            message +=' in ' + task_arn


        # If the task has stopped, then we should add the uptime - helps identify
        # flappy systems.
        if event['detail']['requestParameters']['status'] == "STOPPED":
            if task_details:
                uptime_delta = task_details['stoppedAt'] - task_details['startedAt']
                message += ' (Ran for '+ str(int(uptime_delta.total_seconds())/60) +' minutes)'

                # We want to catch any services stuck in reboots (eg unable to
                # start up successfully)
                if (uptime_delta.total_seconds() <= 300):
                    ignore_quiet = True

                for container in task_details['containers']:
                    if 'reason' in container and container['reason'].find('OutOfMemoryError') == 0:
                        # If a container has a stopped reason beginning with
                        # OutOfMemoryError, then we should know about it,
                        # regardless of how long the task had been running for.
                        ignore_quiet = True

        # Provide a link to the logs for each container inside the task for
        # handy debugging and following. Particularly useful for stopped tasks
        # but can also be useful for newly launched tasks
        if task_details:
            containers = link_container_logs(task_details['taskDefinitionArn'], task_uuid)

            if containers:
                message += '\nContainer logs: '

                for name, logurl in containers.iteritems():
                    message += '<'+ logurl +'|'+ name +'> '

    elif (event['detail']['eventName'] == 'RegisterContainerInstance'):
        # An underlying EC2 instance has started and joined the cluster. Note
        # that this can also include a restarting instance or upgraded agent.

        cluster        = event['detail']['requestParameters']['cluster']
        instance_id    = event['detail']['responseElements']['containerInstance']['ec2InstanceId']
        instance_uuid  = event['detail']['responseElements']['containerInstance']['containerInstanceArn'].split('/')[1]
        version_docker = event['detail']['responseElements']['containerInstance']['versionInfo']['dockerVersion'].split(' ')[1]
        version_agent  = event['detail']['responseElements']['containerInstance']['versionInfo']['agentVersion']

        instance_link  = 'https://console.aws.amazon.com/ecs/home?region=' + os.environ['AWS_DEFAULT_REGION'] +'#/clusters/'+ cluster +'/containerInstances/' + instance_uuid

        message        = cluster +" member <"+ instance_link +"|"+ instance_id +"> started ECS agent "+ version_agent +" with Docker "+ version_docker

        # ECS machine replacements are not overly common, so we should ignore
        # quiet - however we may change this in future when we roll autoscaling.
        ignore_quiet = True

    else:
        # We haven't coded a handler for this event type.
        message = "A " + event['detail']['eventName'] + " event occured."

    if os.environ['SLACK_WEBHOOKURL'] and os.environ['SLACK_WEBHOOKURL'] != 'DISABLED':
        if os.environ['SLACK_QUIET'] == "true":
            # Quiet mode enabled, only post if we've flagged this event as such.
            if ignore_quiet == True:
                slackmessage(message)
        else :
            slackmessage(message)
    elif os.environ['FLOWDOCK_API_TOKEN'] and os.environ['FLOWDOCK_API_TOKEN'] != 'DISABLED':
        if os.environ['FLOWDOCK_QUIET'] == "true":
            # Quiet mode enabled, only post if we've flagged this event as such.
            if ignore_quiet == True:
                flowdockmessage(message)
        else :
            flowdockmessage(message)
    else:
        print "No message service defined!"

    # Keep a copy of the messages in CloudWatch
    print "ECS Event: "+ message

    return True

# Post notification to slack.
def slackmessage(text):

    message = {
        'text': text,
        'channel': os.environ['SLACK_CHANNEL'],
        'link_names': 1,
        'username': os.environ['SLACK_USERNAME'],
        'icon_emoji':  os.environ['SLACK_ICON_EMOJI'],
    }

    headers = {
        'Content-type': 'application/json'
    }

    myrequest = requests.post(url=os.environ['SLACK_WEBHOOKURL'], headers=headers, data=json.dumps(message))

    if myrequest.status_code == 200:
        print "Slack Message: "+ text
    else:
        print "Unexpected error logging to Slack. Return code: "+ str(myrequest.status_code)

# Post notification to flowdock.
def flowdockmessage(text):

    # adjust links from slack message to flowdock syntax
    text = re.sub(r"<([^<]+)\|([^>]+)>", r"[\2](\1)", text)

    chat = Chat(os.environ['FLOWDOCK_API_TOKEN'])
    try:
        chat.post(text, os.environ['FLOWDOCK_USERNAME'])
        print "Flowdock Message: " + text
    except Exception as e:
        print "Unexpected error logging to Flowdock: " + str(e)

# Return the details of a specific task on a specific cluster
def describe_task(ecs_cluster_name, task_arn):

    client = boto3.client('ecs')
    response = client.describe_tasks(
        cluster=ecs_cluster_name,
        tasks=[ task_arn ]
    )

    if response['failures']:
        print "Unexpected error obtaining task details"
        return False
    else:
        return response['tasks'][0]


# Return a dict of containers and logs inside a given task.
def link_container_logs(task_definition_arn, task_uuid):

    client = boto3.client('ecs')
    response = client.describe_task_definition(
        taskDefinition=task_definition_arn
    )

    if response:
        containers = {}

        for container in response['taskDefinition']['containerDefinitions']:

            if container['logConfiguration']['logDriver'] == 'awslogs':
                # If the container us using AWS logs, we can assemble a dict of container names -> logs.
                url = 'https://console.aws.amazon.com/cloudwatch/home?region='
                url += container['logConfiguration']['options']['awslogs-region']
                url += '#logEventViewer:group='
                url += container['logConfiguration']['options']['awslogs-group']
                url += ';stream='
                url += container['logConfiguration']['options']['awslogs-stream-prefix']
                url += '/'
                url += container['name']
                url += '/'
                url += task_uuid
                containers[ container['name'] ] = url

        return containers

    return False
