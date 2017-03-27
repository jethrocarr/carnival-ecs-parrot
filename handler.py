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

# Load the bundled libraries inside vendored/ directory
here = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(here, "vendored/"))

import requests


# PutImage is triggered by ECS API events.
def parrot(event, context):
    # debug
    print "Input event:"
    print json.dumps(event);

    message = ''

    if (event['detail']['eventName'] == 'StopTask'):
        # A task has been terminated via the ECS API either by a human on the
        # console or a utility/tool of some kind.
        message = ':skull:'
        service_name = event['detail']['responseElements']['task']['group'].rsplit(':', 1)[1]
        reason = event['detail']['responseElements']['task']['stoppedReason']
        message += " "+ service_name +" stopped due to "+ reason

    elif (event['detail']['eventName'] == 'SubmitTaskStateChange'):
        # A container has changed state - typically RUNNING->STOPPED or
        # STOPPED->RUNNING
        if (event['detail']['requestParameters']['status'] == "RUNNING"):
            message = ':hatching_chick: Launched task'
        elif (event['detail']['requestParameters']['status'] == "STOPPED"):
            message = ':skull: Stopped task'

        task_arn        = event['detail']['requestParameters']['task']
        task_uuid       = task_arn.rsplit('/', 1)[1]
        task_short_uuid = task_uuid.split('-', 1)[0]
        cluster_name    = event['detail']['requestParameters']['cluster']
        task_details    = describe_task(cluster_name, task_arn)
        task_link       = 'https://console.aws.amazon.com/ecs/home?region=' + os.environ['AWS_DEFAULT_REGION'] +'#/clusters/'+ cluster_name +'/tasks/' + task_uuid

        if task_details:
            message += ' <'+ task_link +'|'+ task_short_uuid + '> in ' + task_details['group']
        else:
            message += ' <'+ task_link +'|'+ task_short_uuid + '> in ' + cluster_name

    else:
        # We haven't coded a handler for this event type.
        message = "A " + event['detail']['eventName'] + " event occured."


    slackmessage(message)

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
        print response # TODO: Debug remove me
        return response['tasks'][0]
