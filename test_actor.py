#  Copyright 2018 tauTerra, LLC; Nicholas Folse

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at

#        http://www.apache.org/licenses/LICENSE-2.0

#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import unittest

import logging

import functools
import signal

import asyncio
from actor import Actor
from context import ActorContext


class ActorTest(unittest.TestCase):

    def test_actor(self):

        logging.basicConfig(level=logging.INFO)

        event_loop = asyncio.get_event_loop()
        actor_context = ActorContext(event_loop=event_loop)
        try:
            actor_context.execute(GreetingActor, 'root', greeting="from root")
        finally:
            event_loop.close()


class GreetingActor(Actor):

    MSG_TERMINATE = "TERMINATE"

    def __init__(self, greeting=None):
        self.greeting = greeting

    async def __aenter__(self):
        self.log.debug("__aenter__")
        pass

    async def __aexit__(self, ext, exv, tb):
        self.log.debug("__aexit__")
        await self.terminate_children()
        if self.parent:
            self.parent.detach_child(self)

    async def run(self):
        self.log.debug("run...")
        try:
            start_time = self.time
            if self.instance_id is 'root':
                for idx in range(0, 1):
                    child_greeter = self.spawn_child(
                        GreetingActor, instance_id='child_{}'.format(idx), greeting="from child {}!".format(idx))
                    await child_greeter.terminate(self)
            self.log.info("Greetings {}".format(self.greeting))
            while True:
                try:
                    if self.time - start_time > 5:
                        break
                    sender, message = await asyncio.wait_for(self.message_queue.get(), 1)
                    if message is self.MSG_TERMINATE:
                        break
                    else:
                        self.log.debug(
                            "message: {} -> {}".format((sender.__class__.__name__, sender.instance_id), str(message)))
                except asyncio.TimeoutError:
                    self.log.info("waiting for messages...")
        except asyncio.CancelledError:
            self.log.error("the task running this actor was cancelled")
            await self.cancel_children()

    async def terminate(self, sender=None):
        sender = self if sender is None else sender
        self.log.debug("terminate method called...")
        try:
            await self.terminate_children()
        finally:
            await self.send_message(sender, self.MSG_TERMINATE)
