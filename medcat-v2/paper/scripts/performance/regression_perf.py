from sys import argv
from pathlib import Path
import os
import logging
import re
from pydantic import BaseModel

from medcat.utils.regression.regression_checker import (
    main as regr_main, logger as regr_l)


DEFAULT_REGRESSION_SUITE = os.path.join(
    *"../tests/resources/default_regression_tests.yml".split("/"))


CASES_PATTERN = re.compile(
    r"The number of total (successful|failing) \(sub\) cases\s*: (\d+) "
    r"\( ?(\d+\.\d+)%\)"
)


class RegressionOverallResults(BaseModel):
    total_cases: int
    successful_cases: int
    failed_cases: int

    def is_valid(self,
                 success_percent: float,
                 fail_percent: float,
                 tolerance: float = 0.005) -> bool:
        got_good = self.successful_cases / self.total_cases
        got_bad = self.failed_cases / self.total_cases
        return (
            abs(got_good - success_percent) < tolerance and
            abs(got_bad - fail_percent) < tolerance)

    def final_comma_sep_out(self) -> str:
        return ",".join([str(self.successful_cases/self.total_cases),
                         str(self.failed_cases/self.total_cases),
                         str(self.total_cases)])

    @classmethod
    def from_records(cls, records: list[tuple[str, int, float]]
                     ) -> 'RegressionOverallResults':
        if len(records) != 2:
            raise ValueError(f"Unbalanced records: {records}")
        good, bad = records
        if "successful" != good[0] and "successful" in bad[0]:
            # NOTE: swapping order - shouldn't be needed though
            good, bad = bad, good
        good_cases, good_perc = good[1:]
        bad_cases, bad_perc = bad[1:]
        inst = cls(total_cases=good_cases + bad_cases,
                   successful_cases=good_cases,
                   failed_cases=bad_cases)
        if not inst.is_valid(good_perc / 100, bad_perc / 100):
            raise ValueError(
                f"Unbalanced totals:\nRecords:\n{records}"
                f"\nvs\nOutcome:\n{inst}\n"
                f"Expected: {good_perc}% S, {bad_perc}% F\n"
                f"Got: {inst.successful_cases / inst.total_cases} S, "
                f"{inst.failed_cases / inst.total_cases} F")
        return inst


class CapturingHandler(logging.Handler):
    """
    A custom logging handler that captures formatted messages
    in a list instead of outputting them.
    """
    def __init__(self, *args,
                 pattern: re.Pattern = CASES_PATTERN,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.pattern = pattern
        self.records: list[tuple[str, int, float]] = []

    def emit(self, record: logging.LogRecord):
        """
        Format the record and append the resulting string to the records list.
        """
        # Ensure the record is formatted before storing it
        msg = self.format(record)
        for line in msg.split("\n"):
            match = self.pattern.match(line)
            if match:
                self.records.append(
                    (match.group(1), int(match.group(2)),
                     float(match.group(3))))

    def get_captured_records(self) -> list[str]:
        """
        Returns the list of captured formatted log messages.
        """
        return self.records

    def get_results(self) -> RegressionOverallResults:
        return RegressionOverallResults.from_records(self.records)

    def clear(self):
        """
        Clears the list of captured records.
        """
        self.records.clear()


def main(model_pack_path: str,
         regression_suite_path: str = DEFAULT_REGRESSION_SUITE):
    regr_l.setLevel(logging.INFO)
    handler = CapturingHandler()
    regr_l.addHandler(handler)
    regr_main(Path(model_pack_path), Path(regression_suite_path))
    results = handler.get_results()
    print(results.final_comma_sep_out())


if __name__ == "__main__":
    main(*argv[1:])
