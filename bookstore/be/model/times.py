import time

def get_time_stamp(): #get timestamp for auto cancelling orders that are not paid in time
    cur_time_stamp = time.time()
    return int(cur_time_stamp)

