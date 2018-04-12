from fornax import settings
from django_cron import CronJobBase, Schedule
from django.core.exceptions import ValidationError
import json
import logging
from os.path import isfile, join
import pickle
from structlog import wrap_logger
import time
from uuid import uuid4
from sip_assembly.models import SIP

logger = wrap_logger(logger=logging.getLogger(__name__))


def read_time(time_filepath, log):
    if isfile(time_filepath):
        with open(time_filepath, 'rb') as pickle_handle:
            last_export = str(pickle.load(pickle_handle))
    else:
        last_export = 0
    log.debug("Got last update time of {time}".format(time=last_export))
    return last_export


def update_time(export_time, time_filepath, log):
    with open(time_filepath, 'wb') as pickle_handle:
        pickle.dump(export_time, pickle_handle)
    log.debug("Last update time set to {time}".format(time=export_time))
