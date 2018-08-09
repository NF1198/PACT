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
        """
        Initialize any resources used by the actor.

        This is an asynchronous method.
        """
        raise NotImplementedError()

    @abstractmethod
    async def __aexit__(self, ext, exv, tb):
        """
        Release any resources used by the actor.

        This is an asynchronous method.

        Implementions should be based on the following
        template:

        async def __aexit__(self, ext, exv, tb):
            await self.terminate_children()
            if self.parent:
                self.parent.detach_child(self)
        """
        raise NotImplementedError()

    @abstractmethod
    async def run(self):
        """
        The run method represents the actor's main loop.
        
        A minimal implementation can be based on the following:

        MSG_TERMINATE = "MSG_TERMINATE"
        async def run(self, *args, **kwargs):
            try:
                while True:
                    try:
                        sender, message = await asyncio.wait_for(self.message_queue.get(), 1)
                        if message is MSG_TERMINATE:
                            break
                        # handle message
                    except asyncio.TimeoutError:
                        # perform a periodic task
            except asyncio.CancelledError:
                await self.cancel_children()
        """
        raise NotImplementedError()

    @abstractmethod
    async def terminate(self, sender=None):
        """
        Called to trigger termination of the actor.
        A minimal implemenation should be based on the 
        following:

        async def terminate(self, sender=None):
            sender = self if sender is None else sender
            self.log.debug("terminate method called...")
            try:
                await self.terminate_children(sender)
            finally:
                await self.send_message(sender, self.MSG_TERMINATE)
        """
        raise NotImplementedError()

    def __actor_init__(self, parent, log_hierarchy: List[str], instance_id: str = None, event_loop: asyncio.BaseEventLoop = None):
        """
        This method is called by the framework to initialize
        actor instances. This method should not be overriden.
        """
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
        return self

    @property
    def log(self):
        """
        Return a logger for the current actor.
        """
        return self._log

    @property
    def event_loop(self):
        """
        Return the event_loop running the current actor.
        """
        return self._event_loop

    @property
    def time(self):
        """
        Return the current time from the event loop running the actor.
        """
        return self.event_loop.time()

    @property
    def parent(self):
        """
        Return the actor's parent (may be None)
        """
        return self._parent

    @property
    def children(self):
        """
        Return a dictionary of children actors and tasks.
        dict: Actor -> asyncio.Task
        """
        return self._children

    @property
    def message_queue(self):
        """
        Return an asyncio.Queue that can be used
        to send messages to the actor.

        In most cases you should use the send_message(...)
        method instead of enquing messages directly.
        """
        return self._message_queue

    @property
    def log_hierarchy(self):
        """
        Return an array of strings that represent
        the current path to the actor.
        """
        return self._log_hierarchy

    @property
    def instance_id(self):
        """
        Return the instance_id of the current actor.
        """
        return self._instance_id

    def spawn_child(self, actor_class, instance_id=None, *args, **kwargs):
        """
        Spawn a child actor attached to the current actor.

        actor_class         Actor or Subclass (not an instance)
        instance_id         an id to assign to the child
        *args               other arguments to pass to the new actor's run method
        *kwargs             other keyword arguments to pass to the new actor's run method

        returns             actor instance
        """
        assert issubclass(actor_class, Actor)
        actor, child_task = Actor.Spawn(
            actor_class, self._event_loop, parent=self, instance_id=instance_id,
            log_hierarchy=self.log_hierarchy, args=args, kwargs=kwargs)
        self._children[actor] = child_task
        return actor

    async def send_message(self, sender, message):
        """
        Sends a message to the actor. This method is an alias
        for actor.message_queue.put((sender, message)).

        This is an asynchronous method.

        sender               sender (preferably an actor, but not enforced)
        message              any

        returns              None
        """
        await self._message_queue.put((sender, message))

    async def terminate_children(self):
        """
        Call the .terminate() method on all children
        and swallows any ensuing asyncio.CancelledError.

        This method should be called in an actor's 
        implementation of __aexit__() and .terminate()

        Refer to the documentation for __aexit__ for more information.

        This is an asyncronous method.

        returns               None
        """
        try:
            for child_actor in (a for a,_ in self.children.items()):
                await child_actor.terminate()
            self.prune_children()
        except asyncio.CancelledError:
            pass

    async def cancel_children(self):
        """
        Cancels all children tasks by calling task.cancel()
        
        This method should be called in an actor's main loop
        an except asyncio.CancelledError exception handler.

        This is an asynchronous method.

        return                None
        """
        try:
            children_tasks = asyncio.gather(
                *(v for _, v in self.children.items()))
            children_tasks.cancel()
            await asyncio.wait_for(children_tasks, 10)
        except asyncio.CancelledError:
            pass

    def prune_children(self):
        """
        A utility method that will remove any child actors
        who's associated tasks are completed. This can be 
        used to clean up misbehaved children that didn't 
        notify the parent of their completion.
        """
        [t.exception() for _,t in self._children.items() if t.done()]
        self._children = {actor: task for actor, task in self._children.items() if not task.done() }

    def detach_child(self, child_actor):
        """
        Used by a child to notify a parent that it's complete.
        This method should be called from an actor's implemenation
        of __aexit__(...). 

        Refer to the documentation for __aexit__ for more information.
        
        This is a synchronous method.

        returns                None
        """
        if child_actor in self.children:
            del(self.children[child_actor])
        else:
            self.log.warning("Attempted to remove unowned child.")

    @staticmethod
    def Spawn(actor_class, event_loop, parent=None, instance_id=None, log_hierarchy=[], args=[], kwargs={}):
        """
        This is a static method used to spawn a free actor.
        In most cases, end-user code should not call this method.
        Instead, call self.spawn_child(...).

        The Actor.Spawn() static method is used by the ActorContext
        to spawn the root actor.

        actor_class            Actor Subclass (not an instance)
        event_loop             asyncio.AbstractEventLoop instance
        parent                 an optional parent actor instance
        instance_id            an id to assign to the child
        log_hierarchy          [str], used to construct a logger and passed to children
        args                   [arg] other arguments to pass to the new actor's run method
        kwargs                 {k:arg} other keyword arguments to pass to the new actor's run method      

        returns                (actor, child_task)
        """

        async def actor_runner(actor, *args, **kwargs):
            async with actor:
                await actor.run(*args, **kwargs)

        actor = actor_class()
        actor = actor.__actor_init__(parent, log_hierarchy,
                            event_loop=event_loop, instance_id=instance_id)
        child_task = event_loop.create_task(
            actor_runner(actor, *args, **kwargs))
        return (actor, child_task)
