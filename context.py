
import asyncio
import logging

import signal
import functools

from actor import Actor

SHUTDOWN_GRACE_SECONDS = 10


class ActorContext:

    def __init__(self, event_loop=None, shutdown_gace_seconds=SHUTDOWN_GRACE_SECONDS):
        self._event_loop = event_loop if event_loop is not None else asyncio.get_event_loop()
        self._shutdown_grace_seconds = shutdown_gace_seconds
        self._log = logging.getLogger(ActorContext.__name__)

    def execute(self, root_actor_class, root_instance_name='root', *args, **kwargs):

        loop = self._event_loop
        log = self._log
        shutdown_grace_sec = self._shutdown_grace_seconds

        def ask_exit(signame, loop, actor, actor_task):
            log.info("got signal {}: exit".format(signame))

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
            root_actor_class, loop, instance_id=root_instance_name, args=args, kwargs=kwargs)

        for signame in ('SIGINT', 'SIGTERM'):
            loop.add_signal_handler(getattr(signal, signame),
                                    functools.partial(ask_exit, signame, loop, root_actor, root_task))

        def stop_loop(task):
            loop.call_soon(lambda: loop.stop())
        root_task.add_done_callback(stop_loop)

        try:
            loop.run_forever()
        finally:
            loop.close()
