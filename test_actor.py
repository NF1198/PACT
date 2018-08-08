
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
        actor_context = ActorContext()
        actor_context.execute(GreetingActor, 'root')


class GreetingActor(Actor):

    MSG_TERMINATE = "TERMINATE"

    async def __aenter__(self):
        self.log.info("__aenter__")

    async def __aexit__(self, ext, exv, tb):
        self.prune_children()
        await self.terminate_children()
        self.log.info("__aexit__")

    async def run(self, greeting=None):
        try:
            start_time = self.time
            if self.instance_id is 'root':
                child_greeter = self.spawn_child(
                    GreetingActor, instance_id='child', greeting="from child!")
                await child_greeter.terminate(self)
            self.log.info("Greetings {}".format(greeting))
            while True:
                try:
                    if self.time - start_time > 5:
                        break
                    sender, message = await asyncio.wait_for(self.message_queue.get(), 1)
                    self.log.info(
                        "message: {} -> {}".format((sender.__class__.__name__, sender.instance_id), str(message)))
                    if message is self.MSG_TERMINATE:
                        break
                    self.prune_children()
                except asyncio.TimeoutError:
                    self.log.info("waiting for messages...")
                    self.prune_children()
        except asyncio.CancelledError:
            self.log.error("the task running this actor was cancelled")
            await self.cancel_children()

    async def terminate(self, sender=None):
        self.log.info("terminate method called...")
        sender = sender if sender is not None and isinstance(
            sender, Actor) else self
        try:
            await self.terminate_children(sender)
        finally:
            await self.send_message(sender, self.MSG_TERMINATE)
