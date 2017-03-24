# carnival-ecs-parrot

ECS Parrot is a Lambda that subscribes to interesting ECS events and posts
the useful/interesting ones to Slack.


# Deployment

A site-specific configuration file needs to be created. This contains all
settings for the Lambda.

  cp serverless.env.yml.example serverless.env.yml
  # edit as appropriate.

To deploy or update the Lambda:

    serverless deploy

The `serverless deploy` command will advise what endpoint is created in API
gateway, or you can request it at any time with serverless info.

Additionally, we need to associate a cloudwatch event to the Lambda. This is
currently not configurable via the Serverless framework itself. To do this:

1. `AWS Console -> CloudWatch Dashboard`
2. `Events -> Rules`
3. Click `Create rule`
4. Select `ECS` as the event service. TODO: Confirm exact options
5. Click `Add target`
6. Select the Lambda to validate against.
7. Keep all other details.
8. Click `Configure details` when done.

TODO: We could probably script the above, but best solution is doing for some
form of native integration into Serverless framework. It might be possible to
use custom CFN resources to do this.


# Developer Notes

Python dependencies are installed to the local `vendored/` directory and then
get packaged and deployed to Lambda by the Serverless framework. We ship these
dependencies as part of this repo, so you don't need to install them yourself
unless you are developing and adding new requirements to the application.

     pip install -t vendored/ -r requirements.txt


# Testing

You can quickly deploy a single changed function with:

    serverless deploy function --function parrot

After deploying the Lambda, it can be involved with test data - for example:

    serverless invoke --function parrot --path samples/event.json


# Contributions

All contributions are welcome via Pull Requests including documentation fixes.


# License

    Copyright (c) 2017 Sailthru, Inc., https://www.sailthru.com/

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
