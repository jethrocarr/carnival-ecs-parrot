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
    slackmessage("Something happened!")
    return True

# Post notification to slack.
def slackmessage(text, icon_emoji=':hatching_chick:'):

    message = {
        'text': text,
        'channel': os.environ['SLACK_CHANNEL'],
        'link_names': 1,
        'username': os.environ['SLACK_USERNAME'],
        'icon_emoji':  icon_emoji,
    }

    headers = {
        'Content-type': 'application/json'
    }

    myrequest = requests.post(url=os.environ['SLACK_WEBHOOKURL'], headers=headers, data=json.dumps(message))

    if myrequest.status_code == 200:
        print "Slack Message: "+ text
    else:
        print "Unexpected error logging to Slack. Return code: "+ myrequest.status_code
