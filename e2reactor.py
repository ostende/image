# Embedded file name: /usr/lib/enigma2/python/e2reactor.py
import select, errno, sys
from twisted.python import log, failure
from twisted.internet import main, posixbase, error
from enigma import getApplication
reads = {}
writes = {}
selectables = {}
POLL_DISCONNECTED = select.POLLHUP | select.POLLERR | select.POLLNVAL

class E2SharedPoll:

    def __init__(self):
        self.dict = {}
        self.eApp = getApplication()

    def register(self, fd, eventmask = select.POLLIN | select.POLLERR | select.POLLOUT):
        self.dict[fd] = eventmask

    def unregister(self, fd):
        del self.dict[fd]

    def poll(self, timeout = None):
        try:
            r = self.eApp.poll(timeout, self.dict)
        except KeyboardInterrupt:
            return None

        return r


poller = E2SharedPoll()

class PollReactor(posixbase.PosixReactorBase):

    def _updateRegistration(self, fd):
        try:
            poller.unregister(fd)
        except KeyError:
            pass

        mask = 0
        if fd in reads:
            mask = mask | select.POLLIN
        if fd in writes:
            mask = mask | select.POLLOUT
        if mask != 0:
            poller.register(fd, mask)
        elif fd in selectables:
            del selectables[fd]
        poller.eApp.interruptPoll()

    def _dictRemove(self, selectable, mdict):
        try:
            fd = selectable.fileno()
            mdict[fd]
        except:
            for fd, fdes in selectables.items():
                if selectable is fdes:
                    break
            else:
                return

        if fd in mdict:
            del mdict[fd]
            self._updateRegistration(fd)

    def addReader(self, reader):
        fd = reader.fileno()
        if fd not in reads:
            selectables[fd] = reader
            reads[fd] = 1
            self._updateRegistration(fd)

    def addWriter(self, writer, writes = writes, selectables = selectables):
        fd = writer.fileno()
        if fd not in writes:
            selectables[fd] = writer
            writes[fd] = 1
            self._updateRegistration(fd)

    def removeReader(self, reader, reads = reads):
        return self._dictRemove(reader, reads)

    def removeWriter(self, writer, writes = writes):
        return self._dictRemove(writer, writes)

    def removeAll(self, reads = reads, writes = writes, selectables = selectables):
        if self.waker is not None:
            self.removeReader(self.waker)
        result = selectables.values()
        fds = selectables.keys()
        reads.clear()
        writes.clear()
        selectables.clear()
        for fd in fds:
            poller.unregister(fd)

        if self.waker is not None:
            self.addReader(self.waker)
        return result

    def doPoll(self, timeout, reads = reads, writes = writes, selectables = selectables, select = select, log = log, POLLIN = select.POLLIN, POLLOUT = select.POLLOUT):
        if timeout is not None:
            timeout = int(timeout * 1000)
        try:
            l = poller.poll(timeout)
            if l is None:
                if self.running:
                    self.stop()
                l = []
        except select.error as e:
            if e[0] == errno.EINTR:
                return
            raise

        _drdw = self._doReadOrWrite
        for fd, event in l:
            try:
                selectable = selectables[fd]
            except KeyError:
                continue

            log.callWithLogger(selectable, _drdw, selectable, fd, event, POLLIN, POLLOUT, log)

        return

    doIteration = doPoll

    def _doReadOrWrite(self, selectable, fd, event, POLLIN, POLLOUT, log, faildict = None):
        if not faildict:
            faildict = {error.ConnectionDone: failure.Failure(error.ConnectionDone()),
             error.ConnectionLost: failure.Failure(error.ConnectionLost())}
        why = None
        inRead = False
        if event & POLL_DISCONNECTED and not event & POLLIN:
            why = main.CONNECTION_LOST
        else:
            try:
                if event & POLLIN:
                    why = selectable.doRead()
                    inRead = True
                if not why and event & POLLOUT:
                    why = selectable.doWrite()
                    inRead = False
                if not selectable.fileno() == fd:
                    why = error.ConnectionFdescWentAway('Filedescriptor went away')
                    inRead = False
            except AttributeError as ae:
                if "'NoneType' object has no attribute 'writeHeaders'" not in ae.message:
                    log.deferr()
                    why = sys.exc_info()[1]
                else:
                    why = None
            except:
                log.deferr()
                why = sys.exc_info()[1]

        if why:
            try:
                self._disconnectSelectable(selectable, why, inRead)
            except RuntimeError:
                pass

        return

    def callLater(self, *args, **kwargs):
        poller.eApp.interruptPoll()
        return posixbase.PosixReactorBase.callLater(self, *args, **kwargs)


def install():
    p = PollReactor()
    main.installReactor(p)


__all__ = ['PollReactor', 'install']