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

import asyncio
import logging

import signal
import functools

from actor import Actor

SHUTDOWN_GRACE_SECONDS = 10


class ActorContext:
    """
    A context that manages execution of actors.

    Example usage: 

    def main():

        event_loop = asyncio.get_event_loop()
        actor_context = ActorContext(event_loop=event_loop)
        try:
            actor_context.execute(GreetingActor, 'root', greeting="from root")
        finally:
            event_loop.close()

    """

    def __init__(self, event_loop=None, shutdown_grace_seconds=SHUTDOWN_GRACE_SECONDS):
        """
        Constructs a new ActorContext instance.

        event_loop                (optional) asyncio.AbstractEventLoop instance
                                    If not specified, will use asyncio.get_event_loop()
        shutdown_grace_seconds    number of seconds to allow for the root actor to
                                  finish execution before cancelling the task
                                  running the actor
        """
        self._event_loop = event_loop if event_loop is not None else asyncio.get_event_loop()
        self._shutdown_grace_seconds = shutdown_grace_seconds
        self._log = logging.getLogger(ActorContext.__name__)

    def execute(self, root_actor_class, root_instance_name, log_hierarchy, *args, **kwargs):
        """
        Starts execution of the context using the specified
        root actor class. Calling this method will block 
        until the root actor task completes.

        root_actor_class            Actor (not an instance)
        root_instance_name          instance_name to apply to the root actor
        *args                       arguments to pass to the root actor's run method
        **kwargs                    keyword arguments to pass to the root actor's run method
        """
        loop = self._event_loop
        log = self._log
        shutdown_grace_sec = self._shutdown_grace_seconds

        def ask_exit(signame, loop, actor, actor_task):
            log.info("got signal {}".format(signame))

            async def wait_for_termination(loop, actor, actor_task):
                try:
                    log.info("Waiting {} seconds for actors to stop...".format(
                        SHUTDOWN_GRACE_SECONDS))
                    await actor.terminate()
                    await asyncio.wait_for(actor_task, shutdown_grace_sec)
                    log.info("actors terminated. stopping loop...")
                    loop.call_later(0.1, lambda: loop.stop())
                except asyncio.TimeoutError:
                    log.info("Actors did not stop. Cancelling tasks...")
                    actor_task.cancel()
                    try:
                        await asyncio.wait_for(actor_task, shutdown_grace_sec)
                    except asyncio.TimeoutError:
                        log.error("Fatal error! Unable to cancel tasks.")
                    finally:
                        loop.call_later(0.1, lambda: loop.stop())
                    exv = actor_task.exception()
                    if exv is not None and not isinstance(exv, asyncio.CancelledError):
                        raise exv

            loop.create_task(wait_for_termination(loop, actor, actor_task))

        loop = asyncio.get_event_loop()

        root_actor, root_task = Actor.Spawn(
            root_actor_class, loop, None, root_instance_name, log_hierarchy, *args, **kwargs)

        for signame in ('SIGINT', 'SIGTERM'):
            loop.add_signal_handler(getattr(signal, signame),
                                    functools.partial(ask_exit, signame, loop, root_actor, root_task))

        def stop_loop(task):
            loop.call_soon(lambda: loop.stop())
        root_task.add_done_callback(stop_loop)

        loop.run_forever()
