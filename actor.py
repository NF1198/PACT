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


from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Dict, List
import random


class Actor(ABC):

    @abstractmethod
    async def __aenter__(self):
        raise NotImplementedError()

    @abstractmethod
    async def __aexit__(self, ext, exv, tb):
        raise NotImplementedError()

    @abstractmethod
    async def run(self):
        raise NotImplementedError()

    @abstractmethod
    async def terminate(self, sender=None):
        raise NotImplementedError()

    def __init__(self, parent, log_hierarchy: List[str], instance_id: str = None, event_loop: asyncio.BaseEventLoop = None):
        self._parent = parent
        self._children = {}  # Actor -> asyncio.Task
        self._message_queue = asyncio.Queue()
        self._event_loop = event_loop if event_loop else asyncio.get_event_loop()
        self._instance_id = instance_id if instance_id is not None else bytearray(
            random.getrandbits(8) for _ in range(0, 6)).hex()
        self._log_hierarchy = [*log_hierarchy,
                               self.__class__.__name__,
                               self._instance_id]
        self._log = logging.getLogger(
            ":".join((str(a) for a in self._log_hierarchy)))

    @property
    def log(self):
        return self._log

    @property
    def event_loop(self):
        return self._event_loop

    @property
    def time(self):
        return self.event_loop.time()

    @property
    def parent(self):
        return self._parent

    @property
    def children(self):
        return self._children

    @property
    def message_queue(self):
        return self._message_queue

    @property
    def log_hierarchy(self):
        return self._log_hierarchy

    @property
    def instance_id(self):
        return self._instance_id

    def spawn_child(self, actor_class, instance_id=None, *args, **kwargs):
        actor, child_task = Actor.Spawn(
            actor_class, self._event_loop, parent=self, instance_id=instance_id,
            log_hierarchy=self.log_hierarchy, args=args, kwargs=kwargs)
        self._children[actor] = child_task
        return actor

    async def send_message(self, sender, message):
        await self._message_queue.put((sender, message))

    async def terminate_children(self, sender=None):
        try:
            for child_actor in (a for a,_ in self.children.items()):
                await child_actor.terminate()
            self.prune_children()
        except asyncio.CancelledError:
            pass

    async def cancel_children(self):
        try:
            children_tasks = asyncio.gather(
                *(v for _, v in self.children.items()))
            children_tasks.cancel()
            await asyncio.wait_for(children_tasks, 10)
        except asyncio.CancelledError:
            pass

    def prune_children(self):
        [t.exception() for _,t in self._children.items() if t.done()]
        self._children = {actor: task for actor, task in self._children.items() if not task.done() }

    def detach_child(self, child_actor):
        if child_actor in self.children:
            del(self.children[child_actor])
        else:
            self.log.warning("Attempted to remove unowned child.")

    @staticmethod
    def Spawn(actor_class, event_loop, parent=None, instance_id=None, log_hierarchy=[], args=[], kwargs={}):

        async def actor_runner(actor, *args, **kwargs):
            async with actor:
                await actor.run(*args, **kwargs)

        actor = actor_class(parent, log_hierarchy,
                            event_loop=event_loop, instance_id=instance_id)
        child_task = event_loop.create_task(
            actor_runner(actor, *args, **kwargs))
        return (actor, child_task)
