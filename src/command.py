import os, subprocess, threading


class Command(object):
    """
    Thanks: http://stackoverflow.com/questions/1191374/using-module-subprocess-with-timeout
    """

    def __init__(self, cmd, killTimeoutCmd=None):
        self.cmd = cmd
        self.process = None
        self.killTimeoutCmd = killTimeoutCmd

    def run(self, timeout):
        code = 0

        def target():
            self.process = subprocess.Popen(self.cmd, shell=True)
            self.process.communicate()

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            self.process.terminate()
            thread.join()
            code = 256
            if self.killTimeoutCmd is not None:
                os.system(self.killTimeoutCmd)
        else:
            code = self.process.returncode

        return code
