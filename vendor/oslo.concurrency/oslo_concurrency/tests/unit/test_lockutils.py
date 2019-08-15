#    Copyright 2011 Justin Santa Barbara
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import collections
import multiprocessing
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

from oslo_config import cfg
from oslotest import base as test_base
import six

from oslo_concurrency.fixture import lockutils as fixtures
from oslo_concurrency import lockutils
from oslo_config import fixture as config

if sys.platform == 'win32':
    import msvcrt
else:
    import fcntl


def lock_file(handle):
    if sys.platform == 'win32':
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def unlock_file(handle):
    if sys.platform == 'win32':
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle, fcntl.LOCK_UN)


def lock_files(handles_dir, out_queue):
    with lockutils.lock('external', 'test-', external=True):
        # Open some files we can use for locking
        handles = []
        for n in range(50):
            path = os.path.join(handles_dir, ('file-%s' % n))
            handles.append(open(path, 'w'))

        # Loop over all the handles and try locking the file
        # without blocking, keep a count of how many files we
        # were able to lock and then unlock. If the lock fails
        # we get an IOError and bail out with bad exit code
        count = 0
        for handle in handles:
            try:
                lock_file(handle)
                count += 1
                unlock_file(handle)
            except IOError:
                os._exit(2)
            finally:
                handle.close()
        return out_queue.put(count)


class LockTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(LockTestCase, self).setUp()
        self.config = self.useFixture(config.Config(lockutils.CONF)).config

    def test_synchronized_wrapped_function_metadata(self):
        @lockutils.synchronized('whatever', 'test-')
        def foo():
            """Bar."""
            pass

        self.assertEqual('Bar.', foo.__doc__, "Wrapped function's docstring "
                                              "got lost")
        self.assertEqual('foo', foo.__name__, "Wrapped function's name "
                                              "got mangled")

    def test_lock_internally_different_collections(self):
        s1 = lockutils.Semaphores()
        s2 = lockutils.Semaphores()
        trigger = threading.Event()
        who_ran = collections.deque()

        def f(name, semaphores, pull_trigger):
            with lockutils.internal_lock('testing', semaphores=semaphores):
                if pull_trigger:
                    trigger.set()
                else:
                    trigger.wait()
                who_ran.append(name)

        threads = [
            threading.Thread(target=f, args=(1, s1, True)),
            threading.Thread(target=f, args=(2, s2, False)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual([1, 2], sorted(who_ran))

    def test_lock_internally(self):
        """We can lock across multiple threads."""
        saved_sem_num = len(lockutils._semaphores)
        seen_threads = list()

        def f(_id):
            with lockutils.lock('testlock2', 'test-', external=False):
                for x in range(10):
                    seen_threads.append(_id)

        threads = []
        for i in range(10):
            thread = threading.Thread(target=f, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        self.assertEqual(100, len(seen_threads))
        # Looking at the seen threads, split it into chunks of 10, and verify
        # that the last 9 match the first in each chunk.
        for i in range(10):
            for j in range(9):
                self.assertEqual(seen_threads[i * 10],
                                 seen_threads[i * 10 + 1 + j])

        self.assertEqual(saved_sem_num, len(lockutils._semaphores),
                         "Semaphore leak detected")

    def test_lock_internal_fair(self):
        """Check that we're actually fair."""

        def f(_id):
            with lockutils.lock('testlock', 'test-',
                                external=False, fair=True):
                lock_holder.append(_id)

        lock_holder = []
        threads = []
        # While holding the fair lock, spawn a bunch of threads that all try
        # to acquire the lock.  They will all block.  Then release the lock
        # and see what happens.
        with lockutils.lock('testlock', 'test-', external=False, fair=True):
            for i in range(10):
                thread = threading.Thread(target=f, args=(i,))
                threads.append(thread)
                thread.start()
                # Allow some time for the new thread to get queued onto the
                # list of pending writers before continuing.  This is gross
                # but there's no way around it without using knowledge of
                # fasteners internals.
                time.sleep(0.5)
        # Wait for all threads.
        for thread in threads:
            thread.join()

        self.assertEqual(10, len(lock_holder))
        # Check that the threads each got the lock in fair order.
        for i in range(10):
            self.assertEqual(i, lock_holder[i])

    def test_fair_lock_with_semaphore(self):
        def do_test():
            s = lockutils.Semaphores()
            with lockutils.lock('testlock', 'test-', semaphores=s, fair=True):
                pass
        self.assertRaises(NotImplementedError, do_test)

    def test_nested_synchronized_external_works(self):
        """We can nest external syncs."""
        tempdir = tempfile.mkdtemp()
        try:
            self.config(lock_path=tempdir, group='oslo_concurrency')
            sentinel = object()

            @lockutils.synchronized('testlock1', 'test-', external=True)
            def outer_lock():

                @lockutils.synchronized('testlock2', 'test-', external=True)
                def inner_lock():
                    return sentinel
                return inner_lock()

            self.assertEqual(sentinel, outer_lock())

        finally:
            if os.path.exists(tempdir):
                shutil.rmtree(tempdir)

    def _do_test_lock_externally(self):
        """We can lock across multiple processes."""
        handles_dir = tempfile.mkdtemp()
        try:
            children = []
            for n in range(50):
                queue = multiprocessing.Queue()
                proc = multiprocessing.Process(
                    target=lock_files,
                    args=(handles_dir, queue))
                proc.start()
                children.append((proc, queue))
            for child, queue in children:
                child.join()
                count = queue.get(block=False)
                self.assertEqual(50, count)
        finally:
            if os.path.exists(handles_dir):
                shutil.rmtree(handles_dir, ignore_errors=True)

    def test_lock_externally(self):
        lock_dir = tempfile.mkdtemp()
        self.config(lock_path=lock_dir, group='oslo_concurrency')

        try:
            self._do_test_lock_externally()
        finally:
            if os.path.exists(lock_dir):
                shutil.rmtree(lock_dir, ignore_errors=True)

    def test_lock_externally_lock_dir_not_exist(self):
        lock_dir = tempfile.mkdtemp()
        os.rmdir(lock_dir)
        self.config(lock_path=lock_dir, group='oslo_concurrency')

        try:
            self._do_test_lock_externally()
        finally:
            if os.path.exists(lock_dir):
                shutil.rmtree(lock_dir, ignore_errors=True)

    def test_synchronized_with_prefix(self):
        lock_name = 'mylock'
        lock_pfix = 'mypfix-'

        foo = lockutils.synchronized_with_prefix(lock_pfix)

        @foo(lock_name, external=True)
        def bar(dirpath, pfix, name):
            return True

        lock_dir = tempfile.mkdtemp()
        self.config(lock_path=lock_dir, group='oslo_concurrency')

        self.assertTrue(bar(lock_dir, lock_pfix, lock_name))

    def test_synchronized_without_prefix(self):
        lock_dir = tempfile.mkdtemp()
        self.config(lock_path=lock_dir, group='oslo_concurrency')

        @lockutils.synchronized('lock', external=True)
        def test_without_prefix():
            # We can't check much
            pass

        try:
            test_without_prefix()
        finally:
            if os.path.exists(lock_dir):
                shutil.rmtree(lock_dir, ignore_errors=True)

    def test_synchronized_prefix_without_hypen(self):
        lock_dir = tempfile.mkdtemp()
        self.config(lock_path=lock_dir, group='oslo_concurrency')

        @lockutils.synchronized('lock', 'hypen', True)
        def test_without_hypen():
            # We can't check much
            pass

        try:
            test_without_hypen()
        finally:
            if os.path.exists(lock_dir):
                shutil.rmtree(lock_dir, ignore_errors=True)

    def test_contextlock(self):
        lock_dir = tempfile.mkdtemp()
        self.config(lock_path=lock_dir, group='oslo_concurrency')

        try:
            # Note(flaper87): Lock is not external, which means
            # a semaphore will be yielded
            with lockutils.lock("test") as sem:
                if six.PY2:
                    self.assertIsInstance(sem, threading._Semaphore)
                else:
                    self.assertIsInstance(sem, threading.Semaphore)

                # NOTE(flaper87): Lock is external so an InterProcessLock
                # will be yielded.
                with lockutils.lock("test2", external=True) as lock:
                    self.assertTrue(lock.exists())

                with lockutils.lock("test1",
                                    external=True) as lock1:
                    self.assertIsInstance(lock1,
                                          lockutils.InterProcessLock)
        finally:
            if os.path.exists(lock_dir):
                shutil.rmtree(lock_dir, ignore_errors=True)

    def test_contextlock_unlocks(self):
        lock_dir = tempfile.mkdtemp()
        self.config(lock_path=lock_dir, group='oslo_concurrency')

        sem = None

        try:
            with lockutils.lock("test") as sem:
                if six.PY2:
                    self.assertIsInstance(sem, threading._Semaphore)
                else:
                    self.assertIsInstance(sem, threading.Semaphore)

                with lockutils.lock("test2", external=True) as lock:
                    self.assertTrue(lock.exists())

                # NOTE(flaper87): Lock should be free
                with lockutils.lock("test2", external=True) as lock:
                    self.assertTrue(lock.exists())

            # NOTE(flaper87): Lock should be free
            # but semaphore should already exist.
            with lockutils.lock("test") as sem2:
                self.assertEqual(sem, sem2)
        finally:
            if os.path.exists(lock_dir):
                shutil.rmtree(lock_dir, ignore_errors=True)

    def _test_remove_lock_external_file(self, lock_dir, use_external=False):
        lock_name = 'mylock'
        lock_pfix = 'mypfix-remove-lock-test-'

        if use_external:
            lock_path = lock_dir
        else:
            lock_path = None

        lockutils.remove_external_lock_file(lock_name, lock_pfix, lock_path)

        for ent in os.listdir(lock_dir):
            self.assertRaises(OSError, ent.startswith, lock_pfix)

        if os.path.exists(lock_dir):
            shutil.rmtree(lock_dir, ignore_errors=True)

    def test_remove_lock_external_file(self):
        lock_dir = tempfile.mkdtemp()
        self.config(lock_path=lock_dir, group='oslo_concurrency')
        self._test_remove_lock_external_file(lock_dir)

    def test_remove_lock_external_file_lock_path(self):
        lock_dir = tempfile.mkdtemp()
        self._test_remove_lock_external_file(lock_dir,
                                             use_external=True)

    def test_no_slash_in_b64(self):
        # base64(sha1(foobar)) has a slash in it
        with lockutils.lock("foobar"):
            pass

    def test_deprecated_names(self):
        paths = self.create_tempfiles([['fake.conf', '\n'.join([
            '[DEFAULT]',
            'lock_path=foo',
            'disable_process_locking=True'])
        ]])
        conf = cfg.ConfigOpts()
        conf(['--config-file', paths[0]])
        conf.register_opts(lockutils._opts, 'oslo_concurrency')
        self.assertEqual('foo', conf.oslo_concurrency.lock_path)
        self.assertTrue(conf.oslo_concurrency.disable_process_locking)


class FileBasedLockingTestCase(test_base.BaseTestCase):
    def setUp(self):
        super(FileBasedLockingTestCase, self).setUp()
        self.lock_dir = tempfile.mkdtemp()

    def test_lock_file_exists(self):
        lock_file = os.path.join(self.lock_dir, 'lock-file')

        @lockutils.synchronized('lock-file', external=True,
                                lock_path=self.lock_dir)
        def foo():
            self.assertTrue(os.path.exists(lock_file))

        foo()

    def test_interprocess_lock(self):
        lock_file = os.path.join(self.lock_dir, 'processlock')

        pid = os.fork()
        if pid:
            # Make sure the child grabs the lock first
            start = time.time()
            while not os.path.exists(lock_file):
                if time.time() - start > 5:
                    self.fail('Timed out waiting for child to grab lock')
                time.sleep(0)
            lock1 = lockutils.InterProcessLock('foo')
            lock1.lockfile = open(lock_file, 'w')
            # NOTE(bnemec): There is a brief window between when the lock file
            # is created and when it actually becomes locked.  If we happen to
            # context switch in that window we may succeed in locking the
            # file.  Keep retrying until we either get the expected exception
            # or timeout waiting.
            while time.time() - start < 5:
                try:
                    lock1.trylock()
                    lock1.unlock()
                    time.sleep(0)
                except IOError:
                    # This is what we expect to happen
                    break
            else:
                self.fail('Never caught expected lock exception')
            # We don't need to wait for the full sleep in the child here
            os.kill(pid, signal.SIGKILL)
        else:
            try:
                lock2 = lockutils.InterProcessLock('foo')
                lock2.lockfile = open(lock_file, 'w')
                have_lock = False
                while not have_lock:
                    try:
                        lock2.trylock()
                        have_lock = True
                    except IOError:
                        pass
            finally:
                # NOTE(bnemec): This is racy, but I don't want to add any
                # synchronization primitives that might mask a problem
                # with the one we're trying to test here.
                time.sleep(.5)
                os._exit(0)

    def test_interthread_external_lock(self):
        call_list = []

        @lockutils.synchronized('foo', external=True, lock_path=self.lock_dir)
        def foo(param):
            """Simulate a long-running threaded operation."""
            call_list.append(param)
            # NOTE(bnemec): This is racy, but I don't want to add any
            # synchronization primitives that might mask a problem
            # with the one we're trying to test here.
            time.sleep(.5)
            call_list.append(param)

        def other(param):
            foo(param)

        thread = threading.Thread(target=other, args=('other',))
        thread.start()
        # Make sure the other thread grabs the lock
        # NOTE(bnemec): File locks do not actually work between threads, so
        # this test is verifying that the local semaphore is still enforcing
        # external locks in that case.  This means this test does not have
        # the same race problem as the process test above because when the
        # file is created the semaphore has already been grabbed.
        start = time.time()
        while not os.path.exists(os.path.join(self.lock_dir, 'foo')):
            if time.time() - start > 5:
                self.fail('Timed out waiting for thread to grab lock')
            time.sleep(0)
        thread1 = threading.Thread(target=other, args=('main',))
        thread1.start()
        thread1.join()
        thread.join()
        self.assertEqual(['other', 'other', 'main', 'main'], call_list)

    def test_non_destructive(self):
        lock_file = os.path.join(self.lock_dir, 'not-destroyed')
        with open(lock_file, 'w') as f:
            f.write('test')
        with lockutils.lock('not-destroyed', external=True,
                            lock_path=self.lock_dir):
            with open(lock_file) as f:
                self.assertEqual('test', f.read())


class LockutilsModuleTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(LockutilsModuleTestCase, self).setUp()
        self.old_env = os.environ.get('OSLO_LOCK_PATH')
        if self.old_env is not None:
            del os.environ['OSLO_LOCK_PATH']

    def tearDown(self):
        if self.old_env is not None:
            os.environ['OSLO_LOCK_PATH'] = self.old_env
        super(LockutilsModuleTestCase, self).tearDown()

    def test_main(self):
        script = '\n'.join([
            'import os',
            'lock_path = os.environ.get("OSLO_LOCK_PATH")',
            'assert lock_path is not None',
            'assert os.path.isdir(lock_path)',
        ])
        argv = ['', sys.executable, '-c', script]
        retval = lockutils._lock_wrapper(argv)
        self.assertEqual(0, retval, "Bad OSLO_LOCK_PATH has been set")

    def test_return_value_maintained(self):
        script = '\n'.join([
            'import sys',
            'sys.exit(1)',
        ])
        argv = ['', sys.executable, '-c', script]
        retval = lockutils._lock_wrapper(argv)
        self.assertEqual(1, retval)

    def test_direct_call_explodes(self):
        cmd = [sys.executable, '-m', 'oslo_concurrency.lockutils']
        with open(os.devnull, 'w') as devnull:
            retval = subprocess.call(cmd, stderr=devnull)
            self.assertEqual(1, retval)


class TestLockFixture(test_base.BaseTestCase):

    def setUp(self):
        super(TestLockFixture, self).setUp()
        self.config = self.useFixture(config.Config(lockutils.CONF)).config
        self.tempdir = tempfile.mkdtemp()

    def _check_in_lock(self):
        self.assertTrue(self.lock.exists())

    def tearDown(self):
        self._check_in_lock()
        super(TestLockFixture, self).tearDown()

    def test_lock_fixture(self):
        # Setup lock fixture to test that teardown is inside the lock
        self.config(lock_path=self.tempdir, group='oslo_concurrency')
        fixture = fixtures.LockFixture('test-lock')
        self.useFixture(fixture)
        self.lock = fixture.lock


class TestGetLockPath(test_base.BaseTestCase):

    def setUp(self):
        super(TestGetLockPath, self).setUp()
        self.conf = self.useFixture(config.Config(lockutils.CONF)).conf

    def test_get_default(self):
        lockutils.set_defaults(lock_path='/the/path')
        self.assertEqual('/the/path', lockutils.get_lock_path(self.conf))

    def test_get_override(self):
        lockutils._register_opts(self.conf)
        self.conf.set_override('lock_path', '/alternate/path',
                               group='oslo_concurrency')
        self.assertEqual('/alternate/path', lockutils.get_lock_path(self.conf))
