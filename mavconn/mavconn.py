from pymavlink.mavutil import mavudp
from collections import defaultdict
import datetime
from datetime import timedelta
from heapq import heappush, heappop
import time
import concurrent.futures
import threading


class MAVLinkConnection:
    """Manages threads that handle mavlink messages
    
    Attributes
    ----------
        mav : ()
            A generic mavlink port
        _stacks : (dict of str: func)
            Contains stacks for various mav message types and the associated 
            handlers for those message types. For example, 
            {'Heartbeat',[handler1, handler2, handler3']}
        _timers : (list)
            A heap queue that stores and compares handlers based on 
            the time to next call.
        _timers_cv: ()
            A condition variable that notifies the timer thread to start 
            when a timer is added into the _timers heap queue.
        _continue: (bool)
            Keeps timer thread active in a loop while True.
        _continue_lock: ()
            Lock for _continue to ensure the boolean value can be toggled.
    """

    def __init__(self, mavfile):
        self.mav = mavfile
        self._stacks = defaultdict(list)
        self._timers = []
        self._timers_cv = threading.Condition()
        self._continue = True
        self._continue_lock = threading.Lock()

    def start(self):
        """ Initializes the timer, listening, and handler worker threads."""
        executor = ThreadPoolExecutor() #Only for handling
        timer_thread = threading.Thread(target=self.timer_work)

    def stop(self):
        """ Stops the timer, listening, and handler worker threads."""
        with self._continue_lock:
            self._continue = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    def push_handler(self, message_name, handler):
        """Pushes mav message and associated handler unto appropriate stack

        Parameters
        ----------
        message_name : (str)
            The type of mav message. For example, 'HEARTBEAT'
        handler : (func)
            The function that is to be performed 
            (associated with a type of mav message)
        """
        self._stacks[message_name].append(handler)

    def pop_handler(self, message_name):
        """Pops the last handler in a stack with a given mav message type
        
        Parameters
        ----------
        message_name : (str)
            The type of mav message. For example, 'HEARTBEAT'
        
        Returns
        -------
        handler : (func)
            The function that is to be performed
            (associated with a type of mav message)
        """
        try:
       	    handler = self._stacks[message_name].pop()
       	    return handler
        except (KeyError, IndexError):
            raise KeyError('That message name key does not exist!')

    def clear_handler(self, message_name=None):
        if message_name:
            self._stacks.pop(message_name)
        else:
            self._stacks.clear()

    def add_timer(self, period, handler):
        with self._timers_cv:
            heappush(self._timers, Timer(period, handler))
            self._timers_cv.notify()

    def timer_work(self):
        def get_cont_val():
            with self._continue_lock:
                return self._continue
        def timer_status():
            return (self._timers != [])
        if get_cont_val(): # SET TO WHILE
            with self._timers_cv:
                self._timers_cv.wait_for(timer_status) #check if heap is empty
                current_timer = heappop(self._timers)
            current_timer.handle(self)
            with self._timers_cv:
                heappush(self._timers, current_timer)
                self._timers_cv.notify()

class Timer:
    """Definition of Timer class"""

    def __init__(self, period, handler):
        self._period = period
        self._handler = handler
        current_time = datetime.datetime.now()
        period_seconds = timedelta(seconds=self._period)
        self._next_time = current_time + period_seconds

    def wait_time(self):
        current_time = datetime.datetime.now()
        delta_time = (self._next_time - current_time).total_seconds()
        time.sleep(delta_time)

    def handle(self, mavconn_instance):
        self.wait_time()
        # pass handler to worker thread
        current_time = datetime.datetime.now()
        period_seconds = timedelta(seconds=self._period)
        self._next_time = current_time + period_seconds

    def __eq__(self, other):
        if self is other:
            return True
        elif type(self) != type(other):
            return False
        else:
            return self._next_time == other._next_time

    def __lt__(self, other):
        return self._next_time < other._next_time

    def __le__(self, other):
        return self._next_time <= other._next_time

    def __ge__(self, other):
        return self._next_time >= other._next_time

    def __gt__(self, other):
        return self._next_time > other._next_time

    def __ne__(self, other):
        return self._next_time != other._next_time


