import time
import cumulusci.cli.logger as clilogger


class timer:
    start = time.time()
    logger = {}

    def __init__(self):
        self.start = time.time()
        self.logger = clilogger.logging.getLogger(clilogger.__name__)

    def log(self, str="Elapsed Time: ", start=start):
        end = time.time()
        timeRounded = "{:.2f}".format(end - start)
        self.logger.info(f"{str} {timeRounded} seconds")
