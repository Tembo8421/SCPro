import logging
import time
from abc import ABC, abstractmethod
from typing import final

from .cyl_util import fail_sign, success_sign

mylogger = logging.getLogger(__name__)
mylogger.setLevel(logging.DEBUG)

class CYLTestCase(ABC):
    """The unit of test case"""

    def __init__(self, test_alias: str, **kwargs):
        self.alias = test_alias
        self.input = kwargs

    @abstractmethod
    def run(self, **kwargs):
        print(self.input)
        return (True, "pass")


class CYLTestRunner(CYLTestCase):
    """A framework to run testcase list"""

    def __init__(self, test_alias: str="CYLTestRunner", **kwargs):
        super().__init__(test_alias=test_alias, **kwargs)
        self._test_list = list()
        self.fail_recorder = []
        self.max_fail = kwargs.get("max_fail")
        self.result_dict = dict()
        pass

    @property
    def fail_counter(self):
        return len(self.fail_recorder)

    def setter(self, **kwargs):
        for k, v in kwargs.items():
            if kwargs.get(k):
                setattr(self, k, v)

    @abstractmethod
    def setup(self):
        return True, "PASS"

    @abstractmethod
    def tearDown(self):
        return True, "PASS"

    @final
    def addTest(self, test_object):
        self._test_list.append(test_object)

    @final
    def run(self, **kwargs):
        self.fail_recorder = []
        self.result_dict = {"msg": "FINISH"}

        ## setup
        ret, out = self.setup()
        self.result_dict["setup"] = {"result": ret, "out": out}

        if ret is False:
            self.result_dict["msg"] = "Failed at setup!"
            return False, self.result_dict

        ## execute case
        self.result_dict["cases"] = {}
        number_cases = len(self._test_list)
        self.result_dict["number of cases"] = number_cases
        if not self.max_fail:
            self.max_fail = number_cases
            
        finish_counter = 0
        for test in self._test_list:
            if self.max_fail <= self.fail_counter:
                mylogger.error(f"The Failed Test count is {self.fail_counter} >= {self.max_fail}.")
                break
            # print("Alias:", test.alias)
            mylogger.info(f"<{test.alias}> Start Test.")
            start_time = time.time()
            ret, out = test.run()
            time_spent = time.time() - start_time
            self.result_dict["cases"][test.alias] = {"result": ret, "out": out, "time spent": time_spent}
            finish_counter += 1
            
            if ret == False:
                self.fail_recorder.append(test.alias)
                mylogger.warning(f"<{test.alias}> Failed! Message: {out}")
                mylogger.warning(fail_sign)
            else:
                mylogger.info(f"<{test.alias}> Success! Message: {out}")
                mylogger.info(success_sign)

        mylogger.info(f"Test Result: {finish_counter-self.fail_counter}/{finish_counter} Success!")
        self.result_dict["failure count"] = self.fail_counter
        self.result_dict["failure rate"] = f"{(self.fail_counter*100/finish_counter)}%" if finish_counter else "100%"

        if self.fail_counter:
            self.result_dict["msg"] = f"Failed at {self.fail_recorder}!"

        ## tearDown
        ret, out = self.tearDown()
        self.result_dict["tearDown"] = {"result": ret, "out": out}
        if ret is False:
            self.result_dict["msg"] = "Failed at tearDown!"
            return False, self.result_dict

        return self.fail_counter==0, self.result_dict

