
# Overview

PACT is a simple actor framework build on top of Python's
asyncio library.

The ActorContext handles OS signals and attempts 
to safely shutdown the actor hierarchy.

The test_actor test case demonstrates how to implement
and call a simple actor hierarchy. Running the example
should produce the following:

    python3 -m unittest
    INFO:GreetingActor:root:Greetings from root
    INFO:GreetingActor:root:GreetingActor:child_0:Greetings from child 0!
    INFO:GreetingActor:root:waiting for messages...
    INFO:GreetingActor:root:waiting for messages...
    INFO:GreetingActor:root:waiting for messages...
    INFO:GreetingActor:root:waiting for messages...
    INFO:GreetingActor:root:waiting for messages...
    .
    ----------------------------------------------------------------------
    Ran 1 test in 5.012s

Cancelling the process with Ctrl-C will result in:

    python3 -m unittest
    INFO:GreetingActor:root:Greetings from root
    INFO:GreetingActor:root:GreetingActor:child_0:Greetings from child 0!
    ^CINFO:ActorContext:got signal SIGINT
    INFO:ActorContext:Waiting 10 seconds for actors to stop...
    INFO:ActorContext:actors terminated. stopping loop...
    .
    ----------------------------------------------------------------------
    Ran 1 test in 0.130s

# Testing

Run tests using the following:

    python3 -m unittest

# License

        Copyright 2018 tauTerra, LLC; Nicholas Folse

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.